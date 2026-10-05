"""Component test: a change made while an import runs survives the import."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from custom_components.home_keeper_library import csv_io

BOB = "p_bob"
OL = "https://openlibrary.org"
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "openlibrary"


async def test_import_keeps_changes_made_while_it_runs(
    hass, setup_entry, call, aioclient_mock, monkeypatch
) -> None:
    aioclient_mock.get(
        f"{OL}/search.json?title=Emma&limit=5&author=Jane+Austen",
        json=json.loads((FIX / "search_empty.json").read_text(encoding="utf-8")),
    )
    store = setup_entry.runtime_data.store
    dune = (
        await call(
            "add_book",
            {"title": "Dune", "authors": ["Frank Herbert"], "lookup": False},
        )
    )["book"]
    hyperion = (await call("add_book", {"title": "Hyperion", "lookup": False}))["book"]
    # The import plan waits in the executor until the test lets it go on.
    started, release = threading.Event(), threading.Event()
    real = csv_io.apply_import

    def slow_plan(*args, **kwargs):
        started.set()
        assert release.wait(10)
        return real(*args, **kwargs)

    monkeypatch.setattr(csv_io, "apply_import", slow_plan)
    csv_text = (
        "Title,Author,ISBN13,My Rating,Exclusive Shelf,Owned Copies,Bookshelves\n"
        'Dune,Frank Herbert,,4,read,0,"read, classics"\n'
        "Emma,Jane Austen,,0,currently-reading,0,\n"
    )
    task = hass.async_create_task(
        call(
            "import_csv",
            {"content": csv_text, "source": "goodreads", "person_id": BOB},
        )
    )
    assert await hass.async_add_executor_job(started.wait, 10)
    # Changes while the import runs.
    room = (await call("add_room", {"name": "Attic"}))["room"]
    await call(
        "set_reading",
        {"book_id": hyperion["id"], "person_id": BOB, "status": "reading"},
    )
    await call("update_book", {"book_id": dune["id"], "shared_notes": "Signed."})
    release.set()
    reply = await task
    assert reply["counts"]["errors"] == 0 and reply["counts"]["title_match"] == 1
    state = store.state
    # The concurrent changes survive.
    assert state["rooms"][room["id"]]["name"] == "Attic"
    assert state["reading"][BOB][hyperion["id"]]["status"] == "reading"
    assert state["books"][dune["id"]]["shared_notes"] == "Signed."
    # The import is written too.
    assert state["books"][dune["id"]]["tags"] == ["classics"]
    assert state["reading"][BOB][dune["id"]]["status"] == "read"
    emma = next(b for b in state["books"].values() if b["title"] == "Emma")
    assert state["reading"][BOB][emma["id"]]["status"] == "reading"
