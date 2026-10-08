"""Book covers: the files, the upload view and the cover view.

The cover files are in ``.storage/home_keeper_library_covers/``. The store file is
``.storage/home_keeper_library``, so the directory has a name of its own. A file name is
``<book_id>-<token>.jpg``. The token changes with each new cover, and the
``cover_url`` of a book carries it as ``?v=<token>``, so a browser cache never
shows an old cover.

* An Open Library cover is the large image, downloaded once.
* A custom cover comes through the upload view: a POST of a multipart body with
  1 file, from an admin user. The view accepts JPEG, PNG and WebP up to 10 MB. It
  reads the type from the first bytes of the file, never from the header of the
  request. Pillow writes a new JPEG of at most 1200 px in an executor job, so
  the stored file is always a clean JPEG. The view returns a ``file_id``, and
  the ``set_cover`` service puts that file on a book.
* The cover view serves the cover of a book to each signed-in user. Covers are
  not private. An ``<img>`` element cannot send a token, so the client signs
  the path with the ``auth/sign_path`` websocket command of Home Assistant, or
  reads the image with ``fetchWithAuth``.
"""

from __future__ import annotations

import io
import logging
import re
import secrets
import time
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiohttp import BodyPartReader, web
from homeassistant.components.http import KEY_HASS_USER, HomeAssistantView
from homeassistant.core import HomeAssistant
from PIL import Image, ImageOps, UnidentifiedImageError

from .backend_i18n import resolve_exception
from .const import (
    COVER_MAX_BYTES,
    COVER_MAX_PX,
    COVER_UPLOAD_URL,
    COVER_URL_PREFIX,
    COVERS_DIR,
    DOMAIN,
    SNIFF_BYTES,
)

if TYPE_CHECKING:
    from .coordinator import LibraryCoordinator

_LOGGER = logging.getLogger(__name__)
_CHUNK = 64 * 1024
_PENDING_MAX_AGE_S = 24 * 60 * 60
# The largest image that Pillow decodes here: 50 megapixels, as Home Keeper.
_MAX_PIXELS = 5e7
_FORMATS = ("JPEG", "PNG", "WEBP")
_FILE_RE = re.compile(r"^[0-9a-f]{32}-[0-9a-f]{8}\.jpg$")
_FILE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class CoverError(ValueError):
    """The file is not an image that the library accepts."""


def sniff_image(header: bytes) -> str | None:
    """The image type from the first bytes: ``jpeg``, ``png`` or ``webp``."""
    if header.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def reencode(data: bytes, dst: Path, max_px: int = COVER_MAX_PX) -> None:
    """Write *data* as a JPEG of at most *max_px* on each side to *dst*.

    This call blocks: run it in an executor job. Raise :class:`CoverError` if the
    data is not a readable image.
    """
    try:
        with Image.open(io.BytesIO(data), formats=_FORMATS) as image:
            if image.width * image.height > _MAX_PIXELS:
                raise CoverError("image_unreadable")
            image.draft("RGB", (max_px, max_px))
            frame = ImageOps.exif_transpose(image) or image
            frame.thumbnail((max_px, max_px))
            if frame.mode in ("RGBA", "LA", "P"):
                rgba = frame.convert("RGBA")
                flat = Image.new("RGB", rgba.size, (255, 255, 255))
                flat.paste(rgba, mask=rgba.getchannel("A"))
                frame = flat
            elif frame.mode != "RGB":
                frame = frame.convert("RGB")
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_suffix(".tmp")
            try:
                frame.save(tmp, "JPEG", quality=85, optimize=True)
                tmp.replace(dst)
            finally:
                tmp.unlink(missing_ok=True)
    except CoverError:
        # A CoverError is a ValueError: let it pass as it is.
        raise
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        SyntaxError,
        ValueError,
    ) as err:
        raise CoverError("image_unreadable") from err


def covers_dir(hass: HomeAssistant) -> Path:
    """The directory of the cover files.

    It is not below ``.storage/home_keeper_library``, because that path is the
    store file.
    """
    return Path(hass.config.path(".storage", COVERS_DIR))


def pending_dir(hass: HomeAssistant) -> Path:
    """The directory of the uploads that no book uses yet."""
    return covers_dir(hass) / "pending"


def new_cover_name(book_id: str) -> str:
    """A new file name for the cover of a book."""
    return f"{book_id}-{secrets.token_hex(4)}.jpg"


def cover_path(hass: HomeAssistant, file: str) -> Path | None:
    """The path of a stored cover file, or None for a name that is not valid."""
    if not _FILE_RE.match(file):
        return None
    return covers_dir(hass) / file


def _unlink(path: Path) -> None:
    path.unlink(missing_ok=True)


def _purge_pending(directory: Path, max_age: float) -> None:
    if not directory.is_dir():
        return
    limit = time.time() - max_age
    for path in directory.iterdir():
        try:
            if path.stat().st_mtime < limit:
                path.unlink(missing_ok=True)
        except OSError:
            continue


async def async_cleanup_pending(hass: HomeAssistant) -> None:
    """Delete the uploads that no book used in 24 hours."""
    await hass.async_add_executor_job(
        _purge_pending, pending_dir(hass), _PENDING_MAX_AGE_S
    )


def release_cover(hass: HomeAssistant, file: str) -> None:
    """Delete a cover file that no book uses now."""
    if (path := cover_path(hass, file)) is not None:
        hass.async_add_executor_job(_unlink, path)


async def async_store_openlibrary_cover(
    hass: HomeAssistant,
    coordinator: LibraryCoordinator,
    book_id: str,
    *,
    replace_custom: bool = False,
) -> bool:
    """Download the Open Library cover of a book and put it on the book.

    A book with a custom cover keeps it, unless *replace_custom* is true. Return
    whether the book got a cover. Raise ``OpenLibraryError`` if Open Library
    cannot be read.
    """

    def keeps_its_cover() -> bool:
        book = coordinator.store.state["books"].get(book_id)
        if book is None:
            return True
        return not replace_custom and (book.get("cover") or {}).get("kind") == "custom"

    if keeps_its_cover():
        return False
    book = coordinator.store.state["books"][book_id]
    cover_id = (book.get("openlibrary") or {}).get("cover_id")
    if not cover_id:
        return False
    data = await coordinator.client.async_cover(int(cover_id))
    if data is None or sniff_image(data[:SNIFF_BYTES]) is None:
        return False
    name = new_cover_name(book_id)
    try:
        await hass.async_add_executor_job(reencode, data, covers_dir(hass) / name)
    except CoverError:
        return False
    # The book can change during the download: a user can delete it or upload
    # a custom cover.
    if keeps_its_cover():
        await hass.async_add_executor_job(_unlink, covers_dir(hass) / name)
        return False
    await coordinator.store.set_cover(book_id, "openlibrary", name)
    return True


def _take_pending(src: Path, dst: Path) -> bool:
    if not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.replace(dst)
    return True


async def async_use_upload(
    hass: HomeAssistant, coordinator: LibraryCoordinator, book_id: str, file_id: str
) -> dict[str, Any]:
    """Put an uploaded file on a book as its custom cover."""
    from .models import LibraryError

    coordinator.store.book(book_id)
    if not _FILE_ID_RE.match(file_id or ""):
        raise LibraryError("upload_not_found", file_id=file_id)
    name = new_cover_name(book_id)
    moved = await hass.async_add_executor_job(
        _take_pending, pending_dir(hass) / f"{file_id}.jpg", covers_dir(hass) / name
    )
    if not moved:
        raise LibraryError("upload_not_found", file_id=file_id)
    return await coordinator.store.set_cover(book_id, "custom", name)


def _coordinator(hass: HomeAssistant) -> LibraryCoordinator | None:
    from .coordinator import find_coordinator

    return find_coordinator(hass)


class CoverView(HomeAssistantView):
    """Serves the cover of a book to each signed-in user."""

    url = COVER_URL_PREFIX + "/{book_id}"
    name = f"api:{DOMAIN}:cover"
    requires_auth = True

    async def get(self, request: web.Request, book_id: str) -> web.StreamResponse:
        """Return the cover file, or 404."""
        hass = request.app["hass"]
        coordinator = _coordinator(hass)
        book = coordinator.store.state["books"].get(book_id) if coordinator else None
        file = ((book or {}).get("cover") or {}).get("file")
        path = cover_path(hass, file) if isinstance(file, str) else None
        if path is None or not await hass.async_add_executor_job(path.is_file):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return web.FileResponse(
            path,
            headers={
                "Cache-Control": "private, max-age=31536000, immutable",
                "Content-Type": "image/jpeg",
            },
        )


class CoverUploadView(HomeAssistantView):
    """Takes a cover image from an admin user and returns its ``file_id``."""

    url = COVER_UPLOAD_URL
    name = f"api:{DOMAIN}:cover_upload"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        """Read 1 image file, check it and store a JPEG copy."""
        hass = request.app["hass"]
        lang = hass.config.language
        request._client_max_size = COVER_MAX_BYTES + 1024 * 1024
        user = request.get(KEY_HASS_USER)
        if user is None or user.system_generated:
            return self.json_message(
                resolve_exception(lang, "upload_requires_user"),
                HTTPStatus.UNAUTHORIZED,
            )
        if not user.is_admin:
            return self.json_message(
                resolve_exception(lang, "admin_required"), HTTPStatus.UNAUTHORIZED
            )
        if _coordinator(hass) is None:
            return self.json_message(
                resolve_exception(lang, "not_loaded"), HTTPStatus.NOT_FOUND
            )
        try:
            data = await self._read_file(request)
        except CoverError as err:
            key = str(err)
            status = (
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE
                if key == "file_too_large"
                else HTTPStatus.BAD_REQUEST
            )
            return self.json_message(
                resolve_exception(lang, key, mb=COVER_MAX_BYTES // (1024 * 1024)),
                status,
            )
        if sniff_image(data[:SNIFF_BYTES]) is None:
            return self.json_message(
                resolve_exception(lang, "unsupported_image"), HTTPStatus.BAD_REQUEST
            )
        file_id = secrets.token_hex(16)
        try:
            await hass.async_add_executor_job(
                reencode, data, pending_dir(hass) / f"{file_id}.jpg"
            )
        except CoverError:
            return self.json_message(
                resolve_exception(lang, "image_unreadable"), HTTPStatus.BAD_REQUEST
            )
        return self.json({"file_id": file_id})

    async def _read_file(self, request: web.Request) -> bytes:
        """The bytes of the 1 file part, at most ``COVER_MAX_BYTES``."""
        try:
            reader = await request.multipart()
        except (ValueError, AssertionError) as err:
            raise CoverError("expected_multipart_upload") from err
        try:
            while (part := await reader.next()) is not None:
                if not isinstance(part, BodyPartReader) or not part.filename:
                    continue
                buffer = bytearray()
                while chunk := await part.read_chunk(_CHUNK):
                    buffer += chunk
                    if len(buffer) > COVER_MAX_BYTES:
                        raise CoverError("file_too_large")
                return bytes(buffer)
        except web.HTTPRequestEntityTooLarge as err:
            raise CoverError("file_too_large") from err
        raise CoverError("no_file_in_upload")
