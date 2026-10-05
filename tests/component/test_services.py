"""Component tests: the services, their gates, their events and their replies."""

from __future__ import annotations

import pytest
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.home_keeper_library.api_surface import SERVICES

ALICE = "p_alice"
BOB = "p_bob"
CAROL = "p_carol"
EVENT = "home_keeper_library_{}".format

# The smallest valid data for each admin-only service. A non-admin user must
# get Unauthorized before the data is even read.
_ADMIN_DATA = {
    "add_room": {"name": "x"},
    "update_room": {"room_id": "x"},
    "delete_room": {"room_id": "x"},
    "add_bookcase": {"room_id": "x", "name": "x"},
    "update_bookcase": {"bookcase_id": "x"},
    "delete_bookcase": {"bookcase_id": "x"},
    "add_shelf": {"bookcase_id": "x", "name": "x"},
    "update_shelf": {"shelf_id": "x"},
    "delete_shelf": {"shelf_id": "x"},
    "lookup_isbn": {"isbn": "0441478123"},
    "add_book": {"title": "x"},
    "update_book": {"book_id": "x"},
    "delete_book": {"book_id": "x"},
    "refresh_book": {"book_id": "x"},
    "scan_isbn": {"isbn": "0441478123"},
    "add_copy": {"book_id": "x"},
    "update_copy": {"copy_id": "x"},
    "move_copy": {"copy_id": "x"},
    "delete_copy": {"copy_id": "x"},
    "set_cover": {"book_id": "x", "kind": "none"},
    "lend_book": {"copy_id": "x", "party": "x"},
    "borrow_book": {"title": "x", "party": "x", "person_id": BOB},
    "return_loan": {"loan_id": "x"},
    "update_loan": {"loan_id": "x"},
    "delete_loan": {"loan_id": "x"},
    "add_to_wishlist": {"title": "x", "person_id": BOB},
    "update_wishlist": {"book_id": "x"},
    "remove_from_wishlist": {"book_id": "x"},
    "got_wishlist_book": {"book_id": "x"},
    "import_csv": {"content": "Title\nx\n", "source": "goodreads", "person_id": BOB},
    "export_csv": {},
}


def test_every_admin_service_has_gate_data() -> None:
    admin = {spec.name for spec in SERVICES if spec.admin_only}
    assert admin == set(_ADMIN_DATA)


@pytest.mark.parametrize("service", sorted(_ADMIN_DATA))
async def test_admin_services_reject_a_non_admin_user(
    hass, setup_entry, call, service
) -> None:
    with pytest.raises(Unauthorized):
        await call(service, _ADMIN_DATA[service], as_="user")


async def _shelf(call) -> dict:
    room = (await call("add_room", {"name": "Den"}))["room"]
    case = (await call("add_bookcase", {"room_id": room["id"], "name": "Left"}))[
        "bookcase"
    ]
    return (await call("add_shelf", {"bookcase_id": case["id"], "name": "Top"}))[
        "shelf"
    ]


async def _book(call, **data) -> dict:
    return (await call("add_book", {"title": "Dune", "lookup": False, **data}))["book"]


async def test_locations_and_delete_rules(hass, setup_entry, call) -> None:
    added = async_capture_events(hass, EVENT("room_added"))
    updated = async_capture_events(hass, EVENT("room_updated"))
    removed = async_capture_events(hass, EVENT("shelf_removed"))
    moved = async_capture_events(hass, EVENT("copy_moved"))
    shelf = await _shelf(call)
    case_id = shelf["bookcase_id"]
    room_id = setup_entry.runtime_data.store.state["bookcases"][case_id]["room_id"]
    assert added[0].data == {"room_id": room_id, "name": "Den", "origin": None}
    second = (await call("add_room", {"name": "Attic"}))["room"]
    assert second["order"] == 1
    reply = await call("update_room", {"room_id": room_id, "name": "Study"})
    assert reply["room"]["name"] == "Study"
    assert updated[0].data["changed_fields"] == ["name"]
    book = await _book(call)
    copy = (await call("add_copy", {"book_id": book["id"], "shelf_id": shelf["id"]}))[
        "copy"
    ]
    with pytest.raises(ServiceValidationError) as info:
        await call("delete_room", {"room_id": room_id})
    assert info.value.translation_key == "room_not_empty"
    assert info.value.translation_placeholders == {"count": "1"}
    with pytest.raises(ServiceValidationError) as info:
        await call("delete_bookcase", {"bookcase_id": case_id})
    assert info.value.translation_key == "bookcase_not_empty"
    with pytest.raises(ServiceValidationError) as info:
        await call("delete_shelf", {"shelf_id": shelf["id"]})
    assert info.value.translation_key == "shelf_not_empty"
    await call("delete_room", {"room_id": room_id, "force": True})
    state = setup_entry.runtime_data.store.state
    assert state["copies"][copy["id"]]["shelf_id"] is None
    assert state["shelves"] == {} and state["bookcases"] == {}
    assert removed[0].data["shelf_id"] == shelf["id"]
    assert moved[0].data["previous_shelf_id"] == shelf["id"]
    assert moved[0].data["shelf_id"] is None
    with pytest.raises(ServiceValidationError) as info:
        await call("update_room", {"room_id": "nope", "name": "x"})
    assert info.value.translation_key == "room_not_found"
    with pytest.raises(ServiceValidationError) as info:
        await call("add_bookcase", {"room_id": "nope", "name": "x"})
    assert info.value.translation_key == "room_not_found"


async def test_move_bookcase_and_shelf(hass, setup_entry, call) -> None:
    shelf = await _shelf(call)
    other = (await call("add_room", {"name": "Attic"}))["room"]
    case = await call(
        "update_bookcase", {"bookcase_id": shelf["bookcase_id"], "room_id": other["id"]}
    )
    assert case["bookcase"]["room_id"] == other["id"]
    new_case = (await call("add_bookcase", {"room_id": other["id"], "name": "B"}))[
        "bookcase"
    ]
    moved = await call(
        "update_shelf", {"shelf_id": shelf["id"], "bookcase_id": new_case["id"]}
    )
    assert moved["shelf"]["bookcase_id"] == new_case["id"]
    await call("delete_shelf", {"shelf_id": shelf["id"]})
    await call("delete_bookcase", {"bookcase_id": new_case["id"]})


async def test_books_and_duplicates(hass, setup_entry, call) -> None:
    added = async_capture_events(hass, EVENT("book_added"))
    book = await _book(call, isbn="0441478123", authors=["Ursula K. Le Guin"])
    assert book["isbn13"] == "9780441478125" and book["isbn10"] == "0441478123"
    assert book["owned"] is False and book["cover_url"] is None
    again = await call("add_book", {"isbn": "978-0-441-47812-5", "lookup": False})
    assert again["existing"] is True and again["book"]["id"] == book["id"]
    assert len(added) == 1
    with pytest.raises(ServiceValidationError) as info:
        await call("add_book", {"lookup": False})
    assert info.value.translation_key == "isbn_or_title_required"
    with pytest.raises(ServiceValidationError) as info:
        await call("add_book", {"isbn": "123", "lookup": False})
    assert info.value.translation_key == "invalid_isbn"
    updated = async_capture_events(hass, EVENT("book_updated"))
    reply = await call("update_book", {"book_id": book["id"], "pages": 304})
    assert reply["book"]["pages"] == 304
    assert updated[0].data["changed_fields"] == ["pages"]
    other = await _book(call, title="Other")
    with pytest.raises(ServiceValidationError) as info:
        await call("update_book", {"book_id": other["id"], "isbn": "0441478123"})
    assert info.value.translation_key == "duplicate_isbn"
    with pytest.raises(ServiceValidationError) as info:
        await call("update_book", {"book_id": book["id"], "pages": 0})
    assert info.value.translation_key == "out_of_range"


async def test_delete_book_cascades(hass, setup_entry, call) -> None:
    book = await _book(call)
    copy = (await call("add_copy", {"book_id": book["id"]}))["copy"]
    await call("set_reading", {"book_id": book["id"], "status": "reading"})
    await call("lend_book", {"copy_id": copy["id"], "party": "Zed", "add_task": False})
    removed = async_capture_events(hass, EVENT("book_removed"))
    copies_removed = async_capture_events(hass, EVENT("copy_removed"))
    await call("delete_book", {"book_id": book["id"]})
    state = setup_entry.runtime_data.store.state
    assert state["books"] == {} and state["copies"] == {}
    assert state["loans"] == {} and state["reading"] == {}
    assert removed[0].data["book_id"] == book["id"]
    assert copies_removed[0].data["copy_id"] == copy["id"]


async def test_copies(hass, setup_entry, call) -> None:
    shelf = await _shelf(call)
    book = await _book(call)
    added = async_capture_events(hass, EVENT("copy_added"))
    moved = async_capture_events(hass, EVENT("copy_moved"))
    copy = (
        await call(
            "add_copy",
            {
                "book_id": book["id"],
                "format": "hardcover",
                "price": 12.5,
                "signed": True,
            },
        )
    )["copy"]
    assert copy["price"] == 12.5 and copy["signed"] is True
    assert added[0].data["copy_id"] == copy["id"]
    reply = await call("move_copy", {"copy_id": copy["id"], "shelf_id": shelf["id"]})
    assert reply["copy"]["shelf_id"] == shelf["id"]
    assert moved[0].data["previous_shelf_id"] is None
    reply = await call("update_copy", {"copy_id": copy["id"], "condition": "good"})
    assert reply["copy"]["condition"] == "good" and len(moved) == 1
    with pytest.raises(ServiceValidationError) as info:
        await call("add_copy", {"book_id": book["id"], "shelf_id": "nope"})
    assert info.value.translation_key == "shelf_not_found"
    await call("lend_book", {"copy_id": copy["id"], "party": "Zed", "add_task": False})
    with pytest.raises(ServiceValidationError) as info:
        await call("delete_copy", {"copy_id": copy["id"]})
    assert info.value.translation_key == "copy_on_loan"
    with pytest.raises(ServiceValidationError) as info:
        await call("lend_book", {"copy_id": copy["id"], "party": "Al"})
    assert info.value.translation_key == "copy_on_loan"


async def test_set_reading_gates_and_events(hass, setup_entry, call) -> None:
    book = await _book(call)
    changed = async_capture_events(hass, EVENT("reading_changed"))
    finished = async_capture_events(hass, EVENT("book_finished"))
    reply = await call(
        "set_reading", {"book_id": book["id"], "status": "read"}, as_="user"
    )
    assert reply["person_id"] == BOB and reply["reading"]["read_count"] == 1
    assert changed[0].data["status"] == "read"
    assert changed[0].data["previous_status"] is None
    assert finished[0].data["person_id"] == BOB
    with pytest.raises(Unauthorized):
        await call(
            "set_reading", {"book_id": book["id"], "person_id": ALICE}, as_="user"
        )
    reply = await call(
        "set_reading", {"book_id": book["id"], "person_id": CAROL, "rating": 4}
    )
    assert reply["reading"]["rating"] == 4 and reply["reading"]["status"] == "want"
    with pytest.raises(ServiceValidationError) as info:
        await call("set_reading", {"book_id": book["id"]}, as_=None)
    assert info.value.translation_key == "no_person"
    with pytest.raises(ServiceValidationError) as info:
        await call("set_reading", {"book_id": book["id"], "person_id": "ghost"})
    assert info.value.translation_key == "person_not_found"
    reply = await call(
        "set_reading", {"book_id": book["id"], "status": "none"}, as_="user"
    )
    assert reply["reading"] is None
    assert changed[-1].data["status"] is None
    assert changed[-1].data["previous_status"] == "read"


async def test_read_services_project_for_a_non_admin(hass, setup_entry, call) -> None:
    shelf = await _shelf(call)
    book = await _book(call, authors=["Frank Herbert"])
    await call(
        "add_copy",
        {
            "book_id": book["id"],
            "shelf_id": shelf["id"],
            "price": 10,
            "value": 20,
            "acquired_from": "Shop",
        },
    )
    copy_id = next(iter(setup_entry.runtime_data.store.state["copies"]))
    await call("lend_book", {"copy_id": copy_id, "party": "Zed", "add_task": False})
    for person in (ALICE, CAROL):
        await call(
            "set_reading",
            {
                "book_id": book["id"],
                "person_id": person,
                "status": "read",
                "private_notes": "secret",
            },
        )
    await call("set_person_settings", {"person_id": CAROL, "share_reading": False})
    user_books = await call("list_books", {}, as_="user")
    text = str(user_books)
    for secret in ("Zed", "Shop", "secret", "'price'", "'value'"):
        assert secret not in text, secret
    assert set(user_books["books"][0]["reading"]) == {ALICE}
    detail = await call("get_book", {"book_id": book["id"]}, as_="user")
    assert "party" not in detail["book"]["loans"][0]
    assert "price" not in detail["book"]["copies"][0]
    assert detail["book"]["copies"][0]["location"] == ["Den", "Left", "Top"]
    admin = await call("get_book", {"book_id": book["id"]})
    assert admin["book"]["loans"][0]["party"] == "Zed"
    assert admin["book"]["reading"][CAROL]["private_notes"] == "secret"
    loans = await call("list_loans", {"status": "open"}, as_="user")
    assert loans["loans"][0]["title"] == "Dune" and "party" not in loans["loans"][0]
    assert (await call("list_loans", {"status": "returned"}))["loans"] == []
    assert (await call("list_loans", {"direction": "in"}))["loans"] == []
    filtered = await call(
        "list_books", {"status": "read", "person_id": CAROL}, as_="user"
    )
    assert filtered == {"books": []}
    own = await call("list_books", {"status": "read", "person_id": ALICE}, as_="user")
    assert len(own["books"]) == 1
    locations = await call("list_locations", {}, as_="user")
    assert locations["rooms"][0]["bookcases"][0]["shelves"][0]["copies"] == 1
    assert locations["no_shelf"] == 0
    people = await call("list_people", {}, as_="user")
    rows = {p["person_id"]: p for p in people["people"]}
    assert rows[CAROL]["share_reading"] is False
    assert "wishlist_todo" not in rows[CAROL] and "wishlist_todo" in rows[BOB]
    with pytest.raises(ServiceValidationError) as info:
        await call("get_book", {"book_id": "nope"}, as_="user")
    assert info.value.translation_key == "book_not_found"


async def test_person_settings(hass, setup_entry, call, todo_list) -> None:
    reply = await call(
        "set_person_settings", {"person_id": BOB, "yearly_goal": 20}, as_="user"
    )
    assert reply["settings"]["yearly_goal"] == 20
    with pytest.raises(Unauthorized):
        await call(
            "set_person_settings",
            {"person_id": BOB, "wishlist_todo": todo_list},
            as_="user",
        )
    with pytest.raises(Unauthorized):
        await call("set_person_settings", {"person_id": ALICE}, as_="user")
    with pytest.raises(ServiceValidationError) as info:
        await call(
            "set_person_settings", {"person_id": BOB, "wishlist_todo": "todo.none"}
        )
    assert info.value.translation_key == "todo_entity_not_found"
    reply = await call(
        "set_person_settings", {"person_id": BOB, "wishlist_todo": todo_list}
    )
    assert reply["settings"]["wishlist_todo"] == todo_list


async def test_wishlist_services(hass, setup_entry, call) -> None:
    shelf = await _shelf(call)
    added = async_capture_events(hass, EVENT("wishlist_added"))
    removed = async_capture_events(hass, EVENT("wishlist_removed"))
    reply = await call(
        "add_to_wishlist",
        {"title": "Emma", "authors": ["Jane Austen"], "person_id": BOB, "buy": True},
    )
    book = reply["book"]
    assert book["wishlist"]["person_id"] == BOB and book["wishlist"]["buy"] is True
    assert book["needs_details"] is True
    assert added[0].data["buy"] is True
    with pytest.raises(ServiceValidationError) as info:
        await call("add_to_wishlist", {"book_id": book["id"], "person_id": BOB})
    assert info.value.translation_key == "already_on_wishlist"
    # A title and author that match a stored book give that book.
    with pytest.raises(ServiceValidationError) as info:
        await call(
            "add_to_wishlist",
            {"title": "emma", "authors": ["Austen, Jane"], "person_id": BOB},
        )
    assert info.value.translation_key == "already_on_wishlist"
    reply = await call("update_wishlist", {"book_id": book["id"], "buy": False})
    assert reply["book"]["wishlist"]["buy"] is False
    copy = await call(
        "got_wishlist_book",
        {"book_id": book["id"], "shelf_id": shelf["id"], "format": "hardcover"},
    )
    assert copy["copy"]["shelf_id"] == shelf["id"]
    state = setup_entry.runtime_data.store.state
    assert state["books"][book["id"]]["wishlist"] is None
    assert removed[0].data["book_id"] == book["id"]
    with pytest.raises(ServiceValidationError) as info:
        await call("remove_from_wishlist", {"book_id": book["id"]})
    assert info.value.translation_key == "not_on_wishlist"
    await call("add_to_wishlist", {"book_id": book["id"], "person_id": CAROL})
    await call("remove_from_wishlist", {"book_id": book["id"]})
    assert len(removed) == 2


async def test_import_and_export(hass, setup_entry, call) -> None:
    shelf = await _shelf(call)
    csv_text = (
        "Title,Author,ISBN13,My Rating,Exclusive Shelf,Owned Copies,Binding,Date Read\n"
        'Dune,Frank Herbert,"=""9780441013593""",5,read,1,Hardcover,2024/01/02\n'
        "Emma,Jane Austen,,0,to-read,0,,\n"
    )
    done = async_capture_events(hass, EVENT("import_completed"))
    dry = await call(
        "import_csv",
        {
            "content": csv_text,
            "source": "goodreads",
            "person_id": BOB,
            "shelf_id": shelf["id"],
            "dry_run": True,
        },
    )
    assert dry["dry_run"] is True and dry["summary"]["books_added"] == 2
    assert setup_entry.runtime_data.store.state["books"] == {}
    assert done == []
    real = await call(
        "import_csv",
        {
            "content": csv_text,
            "source": "goodreads",
            "person_id": BOB,
            "shelf_id": shelf["id"],
        },
    )
    assert real["summary"]["copies_added"] == 1 and real["truncated"] is False
    assert [row["result"] for row in real["rows"]] == ["added", "added"]
    assert done[0].data["books_added"] == 2 and done[0].data["person_id"] == BOB
    state = setup_entry.runtime_data.store.state
    assert len(state["books"]) == 2 and len(state["copies"]) == 1
    exported = await call("export_csv", {"person_id": BOB})
    assert exported["filename"].startswith("library-goodreads-")
    assert '"=""9780441013593"""' in exported["content"]
    assert ",read," in exported["content"]
    library = await call("export_csv", {"format": "library"})
    assert library["content"].startswith("book_id,title")
    with pytest.raises(ServiceValidationError) as info:
        await call(
            "import_csv",
            {"content": "Name\nx\n", "source": "goodreads", "person_id": BOB},
        )
    assert info.value.translation_key == "csv_unreadable"
    with pytest.raises(ServiceValidationError) as info:
        await call(
            "import_csv",
            {
                "content": "x" * (5 * 1024 * 1024 + 1),
                "source": "goodreads",
                "person_id": BOB,
            },
        )
    assert info.value.translation_key == "csv_too_large"


async def test_service_without_a_loaded_entry(hass, setup_entry, call) -> None:
    from custom_components.home_keeper_library import services

    await hass.config_entries.async_unload(setup_entry.entry_id)
    with pytest.raises(ServiceValidationError) as info:
        services.coordinator_or_error(hass)
    assert info.value.translation_key == "not_loaded"
