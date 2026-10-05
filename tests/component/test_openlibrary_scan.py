"""Component tests: the Open Library client, the scan flow and the covers."""

from __future__ import annotations

import io
import json
from http import HTTPStatus
from pathlib import Path

import aiohttp
import pytest
from homeassistant.exceptions import ServiceValidationError
from PIL import Image

from custom_components.home_keeper_library.const import LOOKUP_MAX_TRIES
from custom_components.home_keeper_library.openlibrary_client import (
    OpenLibraryClient,
    OpenLibraryError,
)

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "openlibrary"
OL = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org"
ISBN = "9780441478125"


def _json(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _jpeg(size=(1600, 2400), color="red", fmt="JPEG") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, fmt)
    return out.getvalue()


def _mock_left_hand(aioclient_mock, *, cover: bool = True) -> None:
    aioclient_mock.get(f"{OL}/isbn/{ISBN}.json", json=_json(f"edition_{ISBN}.json"))
    aioclient_mock.get(f"{OL}/works/OL59863W.json", json=_json("work_OL59863W.json"))
    aioclient_mock.get(
        f"{OL}/authors/OL26320A.json", json=_json("author_OL26320A.json")
    )
    if cover:
        aioclient_mock.get(
            f"{COVERS}/b/id/8231856-L.jpg?default=false", content=_jpeg()
        )


async def test_client_lookup_and_miss_cache(hass, setup_entry, aioclient_mock) -> None:
    _mock_left_hand(aioclient_mock)
    client = OpenLibraryClient(hass, min_interval=0)
    draft = await client.async_lookup_isbn(ISBN)
    assert draft["title"] == "The Left Hand of Darkness"
    assert draft["authors"] == ["Ursula K. Le Guin"]
    headers = aioclient_mock.mock_calls[0][3]
    assert headers["User-Agent"].startswith("HomeKeeperLibrary/0.1.0b1 (+https://")
    aioclient_mock.get(f"{OL}/isbn/9780000000002.json", status=404)
    assert await client.async_lookup_isbn("9780000000002") is None
    calls = aioclient_mock.call_count
    assert await client.async_lookup_isbn("9780000000002") is None
    assert aioclient_mock.call_count == calls, "a miss is cached"


async def test_client_errors(hass, setup_entry, aioclient_mock) -> None:
    client = OpenLibraryClient(hass, min_interval=0)
    aioclient_mock.get(f"{OL}/isbn/{ISBN}.json", status=503)
    with pytest.raises(OpenLibraryError):
        await client.async_lookup_isbn(ISBN)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{OL}/isbn/{ISBN}.json", exc=aiohttp.ClientError())
    with pytest.raises(OpenLibraryError):
        await client.async_lookup_isbn(ISBN)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{OL}/isbn/{ISBN}.json", exc=TimeoutError())
    with pytest.raises(OpenLibraryError):
        await client.async_lookup_isbn(ISBN)


async def test_client_search_and_cover(hass, setup_entry, aioclient_mock) -> None:
    client = OpenLibraryClient(hass, min_interval=0)
    aioclient_mock.get(
        f"{OL}/search.json?title=Dune&limit=5&author=Frank+Herbert",
        json=_json("search_dune.json"),
    )
    draft = await client.async_search("Dune", ["Frank Herbert"])
    assert draft["openlibrary"]["work_key"] == "OL893415W"
    aioclient_mock.get(
        f"{OL}/search.json?title=Nothing&limit=5", json=_json("search_empty.json")
    )
    assert await client.async_search("Nothing", []) is None
    aioclient_mock.get(f"{COVERS}/b/id/1-L.jpg?default=false", status=404)
    assert await client.async_cover(1) is None


async def test_client_rate_limit(
    hass, setup_entry, aioclient_mock, monkeypatch
) -> None:
    from custom_components.home_keeper_library import openlibrary_client

    slept: list[float] = []

    async def _sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(openlibrary_client.asyncio, "sleep", _sleep)
    aioclient_mock.get(f"{OL}/isbn/9780000000002.json", status=404)
    aioclient_mock.get(f"{OL}/isbn/9780441013593.json", status=404)
    client = OpenLibraryClient(hass, min_interval=1.0)
    await client.async_lookup_isbn("9780000000002")
    await client.async_lookup_isbn("9780441013593")
    assert len(slept) == 1 and 0 < slept[0] <= 1.0


async def test_scan_isbn_adds_the_book_and_the_cover(
    hass, setup_entry, call, aioclient_mock, hass_client
) -> None:
    _mock_left_hand(aioclient_mock)
    reply = await call("scan_isbn", {"isbn": "0441478123"})
    assert reply["result"] == "added"
    book = reply["book"]
    assert book["title"] == "The Left Hand of Darkness" and book["owned"] is True
    assert book["pages"] == 304 and book["needs_details"] is False
    assert book["cover"]["kind"] == "openlibrary"
    assert book["cover_url"].startswith(
        f"/api/home_keeper_library/cover/{book['id']}?v="
    )
    assert reply["copy"]["book_id"] == book["id"]
    client = await hass_client()
    response = await client.get(book["cover_url"])
    assert response.status == HTTPStatus.OK
    assert response.headers["Content-Type"] == "image/jpeg"
    image = Image.open(io.BytesIO(await response.read()))
    assert max(image.size) == 1200
    duplicate = await call("scan_isbn", {"isbn": ISBN})
    assert duplicate["result"] == "duplicate" and duplicate["copy"] is None
    assert len(duplicate["existing_copies"]) == 1
    assert (await call("scan_isbn", {"isbn": ISBN, "on_duplicate": "skip"}))[
        "result"
    ] == "skipped"
    second = await call("scan_isbn", {"isbn": ISBN, "on_duplicate": "add_copy"})
    assert second["result"] == "added" and len(second["existing_copies"]) == 2
    room = (await call("add_room", {"name": "Den"}))["room"]
    case = (await call("add_bookcase", {"room_id": room["id"], "name": "L"}))[
        "bookcase"
    ]
    shelf = (await call("add_shelf", {"bookcase_id": case["id"], "name": "T"}))["shelf"]
    moved = await call(
        "scan_isbn", {"isbn": ISBN, "on_duplicate": "move", "shelf_id": shelf["id"]}
    )
    assert moved["result"] == "moved" and moved["copy"]["shelf_id"] == shelf["id"]
    assert moved["existing_copies"][0]["location"] in ([], ["Den", "L", "T"])
    with pytest.raises(ServiceValidationError) as info:
        await call("scan_isbn", {"isbn": "12345"})
    assert info.value.translation_key == "invalid_isbn"


async def test_scan_not_found_and_unavailable(
    hass, setup_entry, call, aioclient_mock
) -> None:
    aioclient_mock.get(f"{OL}/isbn/9780000000002.json", status=404)
    reply = await call("scan_isbn", {"isbn": "9780000000002"})
    assert reply["result"] == "not_found"
    assert reply["book"]["needs_details"] is True
    assert reply["book"]["title"] == "9780000000002"
    aioclient_mock.get(f"{OL}/isbn/9780441013593.json", status=500)
    reply = await call("scan_isbn", {"isbn": "9780441013593"})
    assert reply["result"] == "not_found" and reply["copy"] is not None
    lookup = setup_entry.runtime_data.lookup
    await lookup.async_join()
    # The queue tried once, failed and waits on a timer for the next try.
    store = setup_entry.runtime_data.store
    assert store.state["books"][reply["book"]["id"]]["lookup_tries"] == 1
    assert len(lookup._timers) == 1
    # Open Library does not have the first book: the queue never tries it again.
    first = next(
        b for b in store.state["books"].values() if b["isbn13"] == "9780000000002"
    )
    assert first["lookup_tries"] == LOOKUP_MAX_TRIES


def _requests(aioclient_mock, isbn: str) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if isbn in str(call[1]))


async def test_lookup_queue_starts_again_after_a_restart(
    hass, setup_entry, aioclient_mock
) -> None:
    first, second, done = "9780441478125", "9780441013593", "9780000000002"
    for isbn in (first, second, done):
        aioclient_mock.get(f"{OL}/isbn/{isbn}.json", status=503)
    store = setup_entry.runtime_data.store
    ids = {}
    for isbn, tries in ((first, 0), (second, 2), (done, LOOKUP_MAX_TRIES)):
        book, _ = await store.add_book(
            {"isbn": isbn, "title": isbn, "needs_details": True}
        )
        await store.set_lookup_tries(book["id"], tries)
        ids[isbn] = book["id"]
    # A book with Open Library data or no ISBN is not queued.
    await store.add_book({"title": "No ISBN", "needs_details": True})
    await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    lookup = setup_entry.runtime_data.lookup
    await lookup.async_join()
    store = setup_entry.runtime_data.store
    tries = {isbn: store.state["books"][i]["lookup_tries"] for isbn, i in ids.items()}
    assert tries == {first: 1, second: LOOKUP_MAX_TRIES, done: LOOKUP_MAX_TRIES}
    assert _requests(aioclient_mock, first) == 1
    assert _requests(aioclient_mock, second) == 1
    assert _requests(aioclient_mock, done) == 0
    assert len(lookup._timers) == 1, "only the first book waits for a retry"
    # The count stays across a second restart.
    await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    await setup_entry.runtime_data.lookup.async_join()
    store = setup_entry.runtime_data.store
    assert store.state["books"][ids[first]]["lookup_tries"] == 2
    assert _requests(aioclient_mock, second) == 1


async def test_lookup_queue_fills_details(
    hass, setup_entry, call, aioclient_mock
) -> None:
    aioclient_mock.get(f"{OL}/isbn/{ISBN}.json", status=503)
    reply = await call("add_book", {"isbn": ISBN})
    assert reply["lookup"] == "unavailable" and reply["book"]["needs_details"] is True
    lookup = setup_entry.runtime_data.lookup
    await lookup.async_join()
    aioclient_mock.clear_requests()
    _mock_left_hand(aioclient_mock, cover=False)
    aioclient_mock.get(f"{COVERS}/b/id/8231856-L.jpg?default=false", status=404)
    lookup.async_enqueue(reply["book"]["id"])
    await lookup.async_join()
    book = setup_entry.runtime_data.store.state["books"][reply["book"]["id"]]
    assert book["needs_details"] is False and book["authors"] == ["Ursula K. Le Guin"]
    assert book["cover"]["kind"] == "none"


async def test_lookup_isbn_and_refresh(hass, setup_entry, call, aioclient_mock) -> None:
    _mock_left_hand(aioclient_mock)
    reply = await call("lookup_isbn", {"isbn": "0441478123"})
    assert reply["found"] is True and reply["existing_book_id"] is None
    assert reply["draft"]["title"] == "The Left Hand of Darkness"
    assert setup_entry.runtime_data.store.state["books"] == {}
    book = (
        await call("add_book", {"isbn": ISBN, "title": "My title", "lookup": False})
    )["book"]
    refreshed = await call("refresh_book", {"book_id": book["id"]})
    assert refreshed["found"] is True
    assert refreshed["book"]["title"] == "My title", "a user edit stays"
    assert refreshed["book"]["pages"] == 304
    again = await call("lookup_isbn", {"isbn": ISBN})
    assert again["existing_book_id"] == book["id"]
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{OL}/isbn/{ISBN}.json", status=500)
    with pytest.raises(ServiceValidationError) as info:
        await call("refresh_book", {"book_id": book["id"]})
    assert info.value.translation_key == "lookup_unavailable"


async def _upload(hass_client, data: bytes, name: str = "c.png"):
    client = await hass_client()
    form = aiohttp.FormData()
    form.add_field("file", data, filename=name, content_type="image/png")
    return await client.post("/api/home_keeper_library/upload", data=form)


async def test_cover_upload_and_custom_cover(
    hass, setup_entry, call, hass_client, aioclient_mock
) -> None:
    book = (await call("add_book", {"title": "Dune", "lookup": False}))["book"]
    png = io.BytesIO()
    Image.new("RGBA", (100, 150), (0, 0, 255, 128)).save(png, "PNG")
    response = await _upload(hass_client, png.getvalue())
    assert response.status == HTTPStatus.OK
    file_id = (await response.json())["file_id"]
    reply = await call(
        "set_cover", {"book_id": book["id"], "kind": "custom", "file_id": file_id}
    )
    assert reply["book"]["cover"]["kind"] == "custom"
    url = reply["book"]["cover_url"]
    client = await hass_client()
    assert (await client.get(url)).status == HTTPStatus.OK
    with pytest.raises(ServiceValidationError) as info:
        await call(
            "set_cover", {"book_id": book["id"], "kind": "custom", "file_id": file_id}
        )
    assert info.value.translation_key == "upload_not_found"
    with pytest.raises(ServiceValidationError) as info:
        await call("set_cover", {"book_id": book["id"], "kind": "custom"})
    assert info.value.translation_key == "field_required"
    with pytest.raises(ServiceValidationError) as info:
        await call("set_cover", {"book_id": book["id"], "kind": "openlibrary"})
    assert info.value.translation_key == "no_openlibrary_cover"
    reply = await call("set_cover", {"book_id": book["id"], "kind": "none"})
    assert reply["book"]["cover_url"] is None
    assert (await client.get(url)).status == HTTPStatus.NOT_FOUND
    assert (await client.get("/api/home_keeper_library/cover/nope")).status == 404


async def test_cover_upload_rules(
    hass, setup_entry, hass_client, hass_read_only_access_token, aiohttp_client
) -> None:
    response = await _upload(hass_client, b"GIF89a not an image we take")
    assert response.status == HTTPStatus.BAD_REQUEST
    assert "JPEG, PNG or WebP" in (await response.json())["message"]
    response = await _upload(hass_client, b"\x89PNG\r\n\x1a\n" + b"0" * 64)
    assert response.status == HTTPStatus.BAD_REQUEST
    assert (await response.json())["message"] == "The image cannot be read."
    big = b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024)
    response = await _upload(hass_client, big)
    assert response.status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
    client = await hass_client()
    response = await client.post(
        "/api/home_keeper_library/upload",
        data=b"x",
        headers={"Content-Type": "text/plain"},
    )
    assert response.status == HTTPStatus.BAD_REQUEST
    form = aiohttp.FormData()
    form.add_field("name", "no file", content_type="text/plain")
    response = await client.post("/api/home_keeper_library/upload", data=form)
    assert (await response.json())["message"] == "The upload has no file."
    user = await hass_client(hass_read_only_access_token)
    form = aiohttp.FormData()
    form.add_field("file", _jpeg((10, 10)), filename="c.jpg")
    response = await user.post("/api/home_keeper_library/upload", data=form)
    assert response.status == HTTPStatus.UNAUTHORIZED
    webp = _jpeg((20, 20), fmt="WEBP")
    response = await _upload(hass_client, webp, "c.webp")
    assert response.status == HTTPStatus.OK


def test_openlibrary_urls_from_the_environment() -> None:
    from custom_components.home_keeper_library.openlibrary_client import (
        openlibrary_urls,
    )

    assert openlibrary_urls({}) == {}
    assert openlibrary_urls({"HOME_KEEPER_LIBRARY_OPENLIBRARY_URL": "  "}) == {}
    assert openlibrary_urls(
        {
            "HOME_KEEPER_LIBRARY_OPENLIBRARY_URL": "http://ol:8080/",
            "HOME_KEEPER_LIBRARY_OPENLIBRARY_COVERS_URL": "http://ol:8080",
        }
    ) == {"base_url": "http://ol:8080", "covers_url": "http://ol:8080"}


async def test_client_reads_the_base_urls(hass, setup_entry, aioclient_mock) -> None:
    aioclient_mock.get("http://ol:8080/isbn/9780000000002.json", status=404)
    aioclient_mock.get("http://ol:8080/b/id/1-L.jpg?default=false", content=b"jpg")
    client = OpenLibraryClient(
        hass, base_url="http://ol:8080", covers_url="http://ol:8080", min_interval=0
    )
    assert await client.async_lookup_isbn("9780000000002") is None
    assert await client.async_cover(1) == b"jpg"


async def test_covers_dir_is_not_the_store_file(hass, setup_entry) -> None:
    from custom_components.home_keeper_library import covers

    store_file = Path(hass.config.path(".storage", "home_keeper_library"))
    directory = covers.covers_dir(hass)
    assert directory.parent == store_file.parent
    assert directory != store_file and store_file not in directory.parents


async def test_signed_cover_url_needs_no_token(
    hass, setup_entry, call, hass_client, hass_client_no_auth, hass_ws_client
) -> None:
    """The tab and the card sign a cover path, because an <img> sends no token."""
    book = (await call("add_book", {"title": "Dune", "lookup": False}))["book"]
    response = await _upload(hass_client, _jpeg((60, 90)))
    file_id = (await response.json())["file_id"]
    url = (
        await call(
            "set_cover", {"book_id": book["id"], "kind": "custom", "file_id": file_id}
        )
    )["book"]["cover_url"]
    anon = await hass_client_no_auth()
    assert (await anon.get(url)).status == HTTPStatus.UNAUTHORIZED
    ws = await hass_ws_client(hass)
    await ws.send_json(
        {"id": 1, "type": "auth/sign_path", "path": url, "expires": 3600}
    )
    signed = (await ws.receive_json())["result"]["path"]
    assert signed.startswith(url) and "authSig=" in signed
    assert (await anon.get(signed)).status == HTTPStatus.OK
