"""Send a book to Open Library with the account of the household.

The admin connects an account with 2 Archive.org S3 keys in the options flow. For
each send the writer:

1. logs in with the keys (``POST /account/login``) and keeps the ``session``
   cookie for this send only,
2. finds the key of the author (``GET /search/authors.json``),
3. posts the "Add a book" form (``POST /books/add``) and reads the redirect,
4. if the admin asks for it, uploads the cover (``POST /books/OL…M/add-cover``).

Every request goes through ``OpenLibraryClient``, with its User-Agent, its timeout
and its limit of 1 request a second. The keys never leave this module and the
config entry.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

import aiohttp

from . import openlibrary_contribute as contribute
from .const import CONF_OPENLIBRARY_ACCESS, CONF_OPENLIBRARY_SECRET
from .openlibrary_client import OpenLibraryClient, OpenLibraryError

_LOGGER = logging.getLogger(__name__)
_SESSION_COOKIE = "session"


class OpenLibraryAuthError(Exception):
    """Open Library refused the S3 keys."""


class OpenLibraryWriter:
    """Adds books to Open Library as 1 account."""

    def __init__(self, client: OpenLibraryClient) -> None:
        self._client = client

    async def async_login(self, access: str, secret: str) -> tuple[str, str | None]:
        """Log in. Return ``(cookie, username)``.

        Raise :class:`OpenLibraryAuthError` if Open Library refuses the keys, and
        :class:`OpenLibraryError` if it cannot be reached.
        """
        reply = await self._client.async_post(
            "/account/login", json={"access": access, "secret": secret}
        )
        session = reply["cookies"].get(_SESSION_COOKIE)
        if reply["status"] >= 400 or not session:
            raise OpenLibraryAuthError(f"HTTP {reply['status']}")
        return f"{_SESSION_COOKIE}={session}", contribute.session_username(session)

    async def async_author_key(self, name: str) -> str:
        """The key of an author that Open Library has, else ``__new__``."""
        if not name.strip():
            return contribute.NEW_AUTHOR
        found = await self._client.async_get_json(
            f"/search/authors.json?{urlencode({'q': name, 'limit': '5'})}"
        )
        return contribute.pick_author_key(found, name)

    async def async_add_book(
        self, cookie: str, form: dict[str, str]
    ) -> tuple[str, str | None]:
        """Post the "Add a book" form. Return ``(result, edition_key)``."""
        reply = await self._client.async_post("/books/add", data=form, cookie=cookie)
        if reply["status"] in (401, 403):
            raise OpenLibraryAuthError(f"HTTP {reply['status']}")
        return contribute.parse_add_reply(reply["status"], reply["location"])

    async def async_add_cover(
        self, cookie: str, edition_key: str, image: bytes
    ) -> bool:
        """Upload a JPEG cover to an edition. Return True if Open Library took it.

        Open Library replies with a page in both cases, so the writer reads the
        edition again and checks that it has a cover.
        """
        form = aiohttp.FormData()
        form.add_field("file", image, filename="cover.jpg", content_type="image/jpeg")
        try:
            reply = await self._client.async_post(
                f"/books/{edition_key}/add-cover", data=form, cookie=cookie
            )
            if reply["status"] >= 400:
                return False
            edition = await self._client.async_get_json(f"/books/{edition_key}.json")
        except OpenLibraryError as err:
            _LOGGER.info("The cover upload of %s failed: %s", edition_key, err)
            return False
        return isinstance(edition, dict) and bool(edition.get("covers"))


def account_keys(data: Any) -> tuple[str, str] | None:
    """The 2 S3 keys in the config entry data, or None if no account is connected."""
    if not isinstance(data, Mapping):
        return None
    access = data.get(CONF_OPENLIBRARY_ACCESS)
    secret = data.get(CONF_OPENLIBRARY_SECRET)
    if isinstance(access, str) and isinstance(secret, str) and access and secret:
        return access, secret
    return None
