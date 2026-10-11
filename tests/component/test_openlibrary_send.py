"""Component tests: the Open Library account, the send, the link and the skip."""

from __future__ import annotations

import io
from typing import Any

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from PIL import Image
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.home_keeper_library.const import (
    CONF_OPENLIBRARY_ACCESS,
    CONF_OPENLIBRARY_SECRET,
    CONF_OPENLIBRARY_USERNAME,
)
from custom_components.home_keeper_library.covers import covers_dir
from custom_components.home_keeper_library.diagnostics import (
    async_get_config_entry_diagnostics,
)

OL = "https://openlibrary.org"
COVERS = "https://covers.openlibrary.org"
# A synthetic book that Open Library does not have.
ISBN = "9780000000002"
SESSION = "/people/alex_reads,2026-10-11T00:00:00,0a1b2c"
KEYS = {
    CONF_OPENLIBRARY_ACCESS: "ACCESS1",
    CONF_OPENLIBRARY_SECRET: "SECRET1",
    CONF_OPENLIBRARY_USERNAME: "alex_reads",
}
EDITION = {
    "key": "/books/OL5M",
    "title": "Ferns of the Rain City",
    "publishers": ["Cascade Leaf Press"],
    "publish_date": "2024",
    "isbn_13": [ISBN],
    "works": [{"key": "/works/OL9W"}],
}
WORK = {"key": "/works/OL9W", "title": "Ferns of the Rain City"}


@pytest.fixture(autouse=True)
def _isbn_not_found(aioclient_mock) -> None:
    """Open Library does not have the test book, also for the lookup queue."""
    aioclient_mock.get(f"{OL}/isbn/{ISBN}.json", status=404)


def _error_key(info: pytest.ExceptionInfo) -> str:
    return info.value.translation_key


def _connect(entry: Any, hass) -> None:
    hass.config_entries.async_update_entry(entry, data={**entry.data, **KEYS})


async def _book(call, **data) -> dict:
    fields = {
        "title": "Ferns of the Rain City",
        "authors": ["Mara Ellison"],
        "publisher": "Cascade Leaf Press",
        "published": "2024",
        "isbn": ISBN,
        "lookup": False,
        **data,
    }
    return (await call("add_book", fields))["book"]


def _mock_login(aioclient_mock, status: int = 200) -> None:
    cookies = {"session": SESSION} if status < 400 else None
    aioclient_mock.post(f"{OL}/account/login", status=status, cookies=cookies)


def _mock_added(aioclient_mock, *, covers: list[int] | None = None) -> None:
    _mock_login(aioclient_mock)
    aioclient_mock.get(f"{OL}/search/authors.json", json={"docs": []})
    aioclient_mock.post(
        f"{OL}/books/add",
        status=303,
        headers={"Location": "/books/OL5M/Ferns_of_the_Rain_City/edit?mode=add-work"},
    )
    edition = {**EDITION, "covers": covers} if covers else EDITION
    aioclient_mock.get(f"{OL}/books/OL5M.json", json=edition)
    aioclient_mock.get(f"{OL}/works/OL9W.json", json=WORK)


def _calls(aioclient_mock, method: str, path: str) -> list:
    return [
        c
        for c in aioclient_mock.mock_calls
        if c[0].lower() == method and str(c[1]).startswith(f"{OL}{path}")
    ]


# ── Account ──────────────────────────────────────────────────────────────────


async def _openlibrary_step(hass, entry) -> dict:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "openlibrary"}
    )


async def test_connect_keeps_the_keys_in_the_entry_data(
    hass, setup_entry, aioclient_mock
) -> None:
    updated = async_capture_events(hass, "home_keeper_library_settings_updated")
    _mock_login(aioclient_mock)
    result = await _openlibrary_step(hass, setup_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "openlibrary"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"access_key": " ACCESS1 ", "secret_key": "SECRET1"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert dict(setup_entry.data) == KEYS
    assert setup_entry.options == {"currency": "EUR"}
    assert aioclient_mock.mock_calls[-1][2] == {
        "access": "ACCESS1",
        "secret": "SECRET1",
    }
    assert setup_entry.runtime_data.openlibrary_account == {
        "connected": True,
        "username": "alex_reads",
    }
    assert [e.data for e in updated] == [
        {"changed_fields": ["openlibrary_account"], "currency": "EUR", "origin": None}
    ]
    for value in ("ACCESS1", "SECRET1"):
        assert value not in str([e.data for e in updated])


@pytest.mark.parametrize(
    ("status", "error"), [(401, "invalid_auth"), (500, "cannot_connect")]
)
async def test_connect_errors(hass, setup_entry, aioclient_mock, status, error) -> None:
    _mock_login(aioclient_mock, status)
    result = await _openlibrary_step(hass, setup_entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"access_key": "A", "secret_key": "S"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert dict(setup_entry.data) == {}


async def test_disconnect_and_diagnostics(hass, setup_entry, call) -> None:
    _connect(setup_entry, hass)
    diag = await async_get_config_entry_diagnostics(hass, setup_entry)
    assert diag["openlibrary_connected"] is True
    for value in ("ACCESS1", "SECRET1"):
        assert value not in str(diag)
    reply = await call("disconnect_openlibrary")
    assert reply == {"openlibrary_account": {"connected": False, "username": None}}
    assert dict(setup_entry.data) == {}


# ── Send ─────────────────────────────────────────────────────────────────────


async def test_send_adds_and_links_the_book(
    hass, setup_entry, call, aioclient_mock
) -> None:
    _connect(setup_entry, hass)
    book = await _book(call)
    await setup_entry.runtime_data.store.set_openlibrary_status(book["id"], "missing")
    _mock_added(aioclient_mock)
    reply = await call(
        "send_to_openlibrary",
        {"book_id": book["id"], "fields": ["publisher", "published", "isbn"]},
    )
    assert reply["result"] == "added" and reply["edition_key"] == "OL5M"
    assert reply["cover"] == "skipped"
    linked = reply["book"]
    assert linked["openlibrary"] == {
        "edition_key": "OL5M",
        "work_key": "OL9W",
        "cover_id": None,
    }
    assert linked["openlibrary_status"] is None
    (add,) = _calls(aioclient_mock, "post", "/books/add")
    assert add[2] == {
        "book_title": "Ferns of the Rain City",
        "authors--0--author--key": "__new__",
        "author_names--0": "Mara Ellison",
        "publisher": "Cascade Leaf Press",
        "publish_date": "2024",
        "id_name": "isbn_13",
        "id_value": ISBN,
    }
    assert add[3]["Cookie"] == f'session="{SESSION}"'
    assert add[3]["User-Agent"].startswith("HomeKeeperLibrary/")
    assert not _calls(aioclient_mock, "post", "/books/OL5M/add-cover")


async def test_send_without_the_optional_fields_uses_the_known_author(
    hass, setup_entry, call, aioclient_mock
) -> None:
    _connect(setup_entry, hass)
    book = await _book(call)
    aioclient_mock.get(
        f"{OL}/search/authors.json?q=Mara+Ellison&limit=5",
        json={"docs": [{"key": "OL7A", "name": "Mara Ellison"}]},
    )
    await setup_entry.runtime_data.lookup.async_join()
    before = len(_calls(aioclient_mock, "get", "/isbn/"))
    _mock_added(aioclient_mock)
    reply = await call("send_to_openlibrary", {"book_id": book["id"]})
    assert reply["result"] == "added"
    assert len(_calls(aioclient_mock, "get", "/isbn/")) == before
    (add,) = _calls(aioclient_mock, "post", "/books/add")
    assert add[2] == {
        "book_title": "Ferns of the Rain City",
        "authors--0--author--key": "/authors/OL7A",
        "author_names--0": "Mara Ellison",
    }


async def test_send_stops_when_open_library_has_the_isbn(
    hass, setup_entry, call, aioclient_mock
) -> None:
    _connect(setup_entry, hass)
    book = await _book(call)
    await setup_entry.runtime_data.lookup.async_join()
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{OL}/isbn/{ISBN}.json", json=EDITION)
    aioclient_mock.get(f"{OL}/works/OL9W.json", json=WORK)
    reply = await call(
        "send_to_openlibrary", {"book_id": book["id"], "fields": ["isbn"]}
    )
    assert reply["result"] == "existing" and reply["edition_key"] == "OL5M"
    assert reply["book"]["openlibrary"] is None
    assert not _calls(aioclient_mock, "post", "/account/login")


async def test_send_reads_a_found_edition_as_existing(
    hass, setup_entry, call, aioclient_mock
) -> None:
    _connect(setup_entry, hass)
    book = await _book(call)
    _mock_login(aioclient_mock)
    aioclient_mock.get(f"{OL}/search/authors.json", json={"docs": []})
    aioclient_mock.post(
        f"{OL}/books/add",
        status=303,
        headers={"Location": "/books/OL6M/x/edit?mode=found"},
    )
    reply = await call("send_to_openlibrary", {"book_id": book["id"]})
    assert reply["result"] == "existing" and reply["edition_key"] == "OL6M"
    assert reply["book"]["openlibrary"] is None


@pytest.mark.parametrize(
    ("setup", "key"),
    [
        ("not_connected", "openlibrary_not_connected"),
        ("no_author", "openlibrary_needs_author"),
        ("linked", "openlibrary_already_linked"),
        ("ambiguous", "openlibrary_ambiguous"),
        ("refused", "openlibrary_login_failed"),
        ("forbidden", "openlibrary_login_failed"),
        ("down", "lookup_unavailable"),
    ],
)
async def test_send_errors(hass, setup_entry, call, aioclient_mock, setup, key) -> None:
    if setup != "not_connected":
        _connect(setup_entry, hass)
    book = await _book(call, authors=[] if setup == "no_author" else ["Mara Ellison"])
    if setup == "linked":
        link = {"openlibrary": {"edition_key": "OL1M"}}
        await setup_entry.runtime_data.store.fill_book(book["id"], link)
    _mock_login(aioclient_mock, 401 if setup == "refused" else 200)
    aioclient_mock.get(f"{OL}/search/authors.json", json={"docs": []})
    if setup == "down":
        aioclient_mock.post(f"{OL}/books/add", status=502)
    else:
        aioclient_mock.post(
            f"{OL}/books/add",
            status=403 if setup == "forbidden" else 200,
            text="<html>",
        )
    with pytest.raises(ServiceValidationError) as info:
        await call("send_to_openlibrary", {"book_id": book["id"]})
    assert _error_key(info) == key


def _custom_cover(hass, setup_entry, book_id: str) -> None:
    folder = covers_dir(hass)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{book_id}-0a1b2c3d.jpg"
    out = io.BytesIO()
    Image.new("RGB", (10, 15), "green").save(out, "JPEG")
    (folder / name).write_bytes(out.getvalue())
    store = setup_entry.runtime_data.store
    store.state["books"][book_id]["cover"] = {"kind": "custom", "file": name}


@pytest.mark.parametrize(("covers", "result"), [([77], "sent"), (None, "failed")])
async def test_send_with_the_cover(
    hass, setup_entry, call, aioclient_mock, covers, result
) -> None:
    _connect(setup_entry, hass)
    book = await _book(call)
    await hass.async_add_executor_job(_custom_cover, hass, setup_entry, book["id"])
    _mock_added(aioclient_mock, covers=covers)
    aioclient_mock.post(f"{OL}/books/OL5M/add-cover", status=200, text="<html>")
    aioclient_mock.get(f"{COVERS}/b/id/77-L.jpg?default=false", status=404)
    reply = await call(
        "send_to_openlibrary", {"book_id": book["id"], "include_cover": True}
    )
    assert reply["cover"] == result
    (upload,) = _calls(aioclient_mock, "post", "/books/OL5M/add-cover")
    assert upload[3]["Cookie"] == f'session="{SESSION}"'
    assert reply["book"]["cover"]["kind"] == "custom"


async def test_send_links_the_key_when_the_new_edition_cannot_be_read(
    hass, setup_entry, call, aioclient_mock
) -> None:
    _connect(setup_entry, hass)
    book = await _book(call)
    _mock_login(aioclient_mock)
    aioclient_mock.get(f"{OL}/search/authors.json", json={"docs": []})
    aioclient_mock.post(
        f"{OL}/books/add",
        status=303,
        headers={"Location": "/books/OL5M/x/edit?mode=add-book"},
    )
    aioclient_mock.get(f"{OL}/books/OL5M.json", status=404)
    reply = await call("send_to_openlibrary", {"book_id": book["id"]})
    assert reply["result"] == "added"
    assert reply["book"]["openlibrary"]["edition_key"] == "OL5M"


# ── Link and skip ────────────────────────────────────────────────────────────


async def test_link_openlibrary(hass, setup_entry, call, aioclient_mock) -> None:
    book = await _book(call, publisher="", published="")
    await setup_entry.runtime_data.store.set_openlibrary_status(book["id"], "missing")
    aioclient_mock.get(f"{OL}/books/OL5M.json", json=EDITION)
    aioclient_mock.get(f"{OL}/works/OL9W.json", json=WORK)
    reply = await call(
        "link_openlibrary",
        {"book_id": book["id"], "edition": "https://openlibrary.org/books/OL5M/Ferns"},
    )
    linked = reply["book"]
    assert linked["openlibrary"]["edition_key"] == "OL5M"
    assert linked["publisher"] == "Cascade Leaf Press"
    assert linked["openlibrary_status"] is None


async def test_link_errors(hass, setup_entry, call, aioclient_mock) -> None:
    book = await _book(call)
    with pytest.raises(ServiceValidationError) as info:
        await call("link_openlibrary", {"book_id": book["id"], "edition": "OL5W"})
    assert _error_key(info) == "invalid_openlibrary_edition"
    aioclient_mock.get(f"{OL}/books/OL5M.json", status=404)
    with pytest.raises(ServiceValidationError) as info:
        await call("link_openlibrary", {"book_id": book["id"], "edition": "OL5M"})
    assert _error_key(info) == "openlibrary_not_found"
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{OL}/books/OL5M.json", status=500)
    with pytest.raises(ServiceValidationError) as info:
        await call("link_openlibrary", {"book_id": book["id"], "edition": "OL5M"})
    assert _error_key(info) == "lookup_unavailable"


async def test_skip_openlibrary(hass, setup_entry, call) -> None:
    book = await _book(call)
    await setup_entry.runtime_data.lookup.async_join()
    updated = async_capture_events(hass, "home_keeper_library_book_updated")
    reply = await call("skip_openlibrary", {"book_id": book["id"]})
    assert reply["book"]["openlibrary_status"] == "skipped"
    reply = await call("skip_openlibrary", {"book_id": book["id"], "skip": False})
    assert reply["book"]["openlibrary_status"] == "missing"
    await call("skip_openlibrary", {"book_id": book["id"], "skip": False})
    await hass.async_block_till_done()
    assert [e.data["changed_fields"] for e in updated] == [
        ["openlibrary_status"],
        ["openlibrary_status"],
    ]
    link = {"openlibrary": {"edition_key": "OL1M"}}
    await setup_entry.runtime_data.store.fill_book(book["id"], link)
    reply = await call("skip_openlibrary", {"book_id": book["id"]})
    assert reply["book"]["openlibrary_status"] is None
