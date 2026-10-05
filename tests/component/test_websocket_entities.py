"""Component tests: websocket commands, entities, to-do lists, wishlist sync."""

from __future__ import annotations

import pytest
from homeassistant.components.todo import DOMAIN as TODO

ALICE = "p_alice"
BOB = "p_bob"
CAROL = "p_carol"
WS = "home_keeper_library/"


async def _send(client, **msg):
    await client.send_json_auto_id(msg)
    return await client.receive_json()


async def _book(call, **data):
    return (await call("add_book", {"title": "Dune", "lookup": False, **data}))["book"]


async def test_get_state_shape_and_projection(hass, setup_entry, call, ws) -> None:
    book = await _book(call, authors=["Frank Herbert"])
    copy = (await call("add_copy", {"book_id": book["id"], "price": 9}))["copy"]
    await call("lend_book", {"copy_id": copy["id"], "party": "Zed"})
    await call(
        "set_reading",
        {"book_id": book["id"], "person_id": CAROL, "private_notes": "secret"},
    )
    admin = await ws("admin")
    reply = await _send(admin, type=WS + "get_state")
    assert reply["success"]
    result = reply["result"]
    assert set(result) == {
        "revision",
        "rooms",
        "bookcases",
        "shelves",
        "books",
        "copies",
        "loans",
        "people",
        "me",
        "currency",
        "home_keeper",
    }
    assert result["me"] == {"person_id": ALICE, "name": "Alice", "is_admin": True}
    assert result["currency"] == "EUR" and result["home_keeper"] == {"tab": True}
    assert result["copies"][0]["price"] == 9 and result["loans"][0]["party"] == "Zed"
    assert result["books"][0]["owned"] is True
    assert result["books"][0]["reading"][CAROL]["private_notes"] == "secret"
    user = await ws("user")
    reply = await _send(user, type=WS + "get_state")
    result = reply["result"]
    assert result["me"]["person_id"] == BOB and result["me"]["is_admin"] is False
    assert "price" not in result["copies"][0] and "party" not in result["loans"][0]
    assert "private_notes" not in result["books"][0]["reading"][CAROL]


async def test_subscribe_pushes_changes(hass, setup_entry, call, ws) -> None:
    client = await ws("user")
    reply = await _send(client, type=WS + "subscribe")
    assert reply["success"]
    revision = reply["result"]["revision"]
    await call("add_room", {"name": "Den"})
    event = await client.receive_json()
    assert event["type"] == "event"
    assert event["event"] == {"type": "changed", "revision": revision + 1}


async def test_twin_commands_share_the_gate(hass, setup_entry, ws) -> None:
    admin = await ws("admin")
    reply = await _send(admin, type=WS + "add_room", name="Den")
    assert reply["success"] and reply["result"]["room"]["name"] == "Den"
    reply = await _send(admin, type=WS + "delete_room", room_id="nope")
    assert not reply["success"]
    assert reply["error"]["code"] == "room_not_found"
    assert reply["error"]["message"] == "No room has the ID nope."
    user = await ws("user")
    reply = await _send(user, type=WS + "add_room", name="Den")
    assert reply["error"]["code"] == "unauthorized"
    book = await _send(admin, type=WS + "add_book", title="Dune", lookup=False)
    book_id = book["result"]["book"]["id"]
    reply = await _send(user, type=WS + "set_reading", book_id=book_id, status="read")
    assert reply["success"] and reply["result"]["person_id"] == BOB
    reply = await _send(user, type=WS + "set_reading", book_id=book_id, person_id=ALICE)
    assert reply["error"]["code"] == "unauthorized"
    reply = await _send(user, type=WS + "list_todo_entities")
    assert reply["error"]["code"] == "unauthorized"
    reply = await _send(admin, type=WS + "add_room")
    assert reply["error"]["code"] == "invalid_format"


async def test_list_todo_entities_skips_library_lists(
    hass, setup_entry, ws, todo_list
) -> None:
    admin = await ws("admin")
    reply = await _send(admin, type=WS + "list_todo_entities")
    assert reply["result"]["entities"] == [{"entity_id": todo_list, "name": "Books"}]


async def test_sensors(hass, setup_entry, call) -> None:
    book = await _book(call, pages=400)
    await call("add_copy", {"book_id": book["id"]})
    await call("set_person_settings", {"person_id": ALICE, "yearly_goal": 12})
    await call(
        "set_reading", {"book_id": book["id"], "person_id": ALICE, "status": "read"}
    )
    other = await _book(call, title="Emma")
    await call(
        "set_reading", {"book_id": other["id"], "person_id": BOB, "status": "reading"}
    )
    assert hass.states.get("sensor.home_keeper_library_books").state == "1"
    read = hass.states.get("sensor.home_keeper_library_alice_books_read_this_year")
    assert read.state == "1"
    assert read.attributes["goal"] == 12 and read.attributes["pages"] == 400
    assert read.attributes["person_id"] == ALICE
    now = hass.states.get("sensor.home_keeper_library_bob_reading_now")
    assert now.state == "1" and now.attributes["books"] == ["Emma"]


async def test_to_read_list(hass, setup_entry, call) -> None:
    entity = "todo.home_keeper_library_bob_to_read"
    book = await _book(call, authors=["Frank Herbert"])
    await call(
        "set_reading", {"book_id": book["id"], "person_id": BOB, "status": "want"}
    )
    items = await hass.services.async_call(
        TODO,
        "get_items",
        {},
        target={"entity_id": entity},
        blocking=True,
        return_response=True,
    )
    assert items[entity]["items"] == [
        {
            "uid": book["id"],
            "summary": "Dune by Frank Herbert",
            "status": "needs_action",
        }
    ]
    assert hass.states.get(entity).state == "1"
    await hass.services.async_call(
        TODO,
        "update_item",
        {"item": book["id"], "status": "completed"},
        target={"entity_id": entity},
        blocking=True,
    )
    store = setup_entry.runtime_data.store
    assert store.reading_row(BOB, book["id"])["status"] == "read"
    await hass.services.async_call(
        TODO, "add_item", {"item": "dune"}, target={"entity_id": entity}, blocking=True
    )
    assert store.reading_row(BOB, book["id"])["status"] == "want"
    await hass.services.async_call(
        TODO,
        "add_item",
        {"item": "A new book"},
        target={"entity_id": entity},
        blocking=True,
    )
    new = next(b for b in store.state["books"].values() if b["title"] == "A new book")
    assert new["needs_details"] is True
    assert store.reading_row(BOB, new["id"])["status"] == "want"
    await hass.services.async_call(
        TODO,
        "remove_item",
        {"item": [new["id"]]},
        target={"entity_id": entity},
        blocking=True,
    )
    assert store.reading_row(BOB, new["id"]) is None


async def test_wishlist_sync(hass, setup_entry, call, todo_list) -> None:
    await call("set_person_settings", {"person_id": BOB, "wishlist_todo": todo_list})
    book = await _book(call, authors=["Jane Austen"], title="Emma")
    await call(
        "add_to_wishlist", {"book_id": book["id"], "person_id": BOB, "buy": True}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    state = hass.states.get(todo_list)
    assert state.state == "1"
    entry = setup_entry.runtime_data.store.state["books"][book["id"]]["wishlist"]
    assert entry["todo_entity"] == todo_list and entry["todo_uid"]
    # Completed on the list: the book is bought and the item stays.
    await hass.services.async_call(
        TODO,
        "update_item",
        {"item": "Emma by Jane Austen", "status": "completed"},
        target={"entity_id": todo_list},
        blocking=True,
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = setup_entry.runtime_data.store.state["books"][book["id"]]["wishlist"]
    assert entry["bought"] is True and entry["todo_uid"] is None
    items = await hass.services.async_call(
        TODO,
        "get_items",
        {},
        target={"entity_id": todo_list},
        blocking=True,
        return_response=True,
    )
    assert [i["status"] for i in items[todo_list]["items"]] == ["completed"]
    # A second book that leaves the wishlist loses its item.
    other = await _book(call, title="Persuasion", authors=["Jane Austen"])
    await call(
        "add_to_wishlist", {"book_id": other["id"], "person_id": BOB, "buy": True}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(todo_list).state == "1"
    await call("remove_from_wishlist", {"book_id": other["id"]})
    await hass.async_block_till_done(wait_background_tasks=True)
    items = await hass.services.async_call(
        TODO,
        "get_items",
        {},
        target={"entity_id": todo_list},
        blocking=True,
        return_response=True,
    )
    assert [i["summary"] for i in items[todo_list]["items"]] == ["Emma by Jane Austen"]
    assert setup_entry.runtime_data.store.state["todo_orphans"] == []


async def _todo_items(hass, entity: str) -> list[dict]:
    items = await hass.services.async_call(
        TODO,
        "get_items",
        {},
        target={"entity_id": entity},
        blocking=True,
        return_response=True,
    )
    return items[entity]["items"]


async def test_first_copy_of_a_wishlist_book_clears_the_wishlist(
    hass, setup_entry, call, todo_list, aioclient_mock
) -> None:
    from pytest_homeassistant_custom_component.common import async_capture_events

    aioclient_mock.get("https://openlibrary.org/isbn/9780441478125.json", status=404)

    removed = async_capture_events(hass, "home_keeper_library_wishlist_removed")
    added = async_capture_events(hass, "home_keeper_library_copy_added")
    await call("set_person_settings", {"person_id": BOB, "wishlist_todo": todo_list})
    book = await _book(call, title="Emma", authors=["Jane Austen"], isbn="0441478123")
    await call(
        "add_to_wishlist", {"book_id": book["id"], "person_id": BOB, "buy": True}
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(await _todo_items(hass, todo_list)) == 1
    reply = await call("scan_isbn", {"isbn": "0441478123"})
    assert reply["result"] == "added" and reply["from_wishlist"] is True
    await hass.async_block_till_done(wait_background_tasks=True)
    store = setup_entry.runtime_data.store
    assert store.state["books"][book["id"]]["wishlist"] is None
    assert await _todo_items(hass, todo_list) == []
    assert [e.data["person_id"] for e in removed] == [BOB]
    assert removed[0].data["book_id"] == book["id"]
    assert [e.data["copy_id"] for e in added] == [reply["copy"]["id"]]
    # A second copy is not from the wishlist.
    again = await call("scan_isbn", {"isbn": "0441478123", "on_duplicate": "add_copy"})
    assert again["result"] == "added" and again["from_wishlist"] is False
    skipped = await call("scan_isbn", {"isbn": "0441478123", "on_duplicate": "skip"})
    assert skipped["from_wishlist"] is False
    # add_copy clears the wishlist too.
    other = await _book(call, title="Persuasion", authors=["Jane Austen"])
    await call("add_to_wishlist", {"book_id": other["id"], "person_id": BOB})
    reply = await call("add_copy", {"book_id": other["id"]})
    assert reply["from_wishlist"] is True
    assert store.state["books"][other["id"]]["wishlist"] is None
    assert len(removed) == 2


def _todo_entity(hass, entity_id: str):
    from homeassistant.components.todo import DATA_COMPONENT

    return hass.data[DATA_COMPONENT].get_entity(entity_id)


async def test_to_read_list_refuses_other_users(
    hass, setup_entry, call, persons
) -> None:
    from homeassistant.components.todo import TodoItem, TodoItemStatus
    from homeassistant.core import Context
    from homeassistant.exceptions import HomeAssistantError

    store = setup_entry.runtime_data.store
    book = await _book(call)
    bob_id = persons["user"].id
    own = _todo_entity(hass, "todo.home_keeper_library_bob_to_read")
    other = _todo_entity(hass, "todo.home_keeper_library_alice_to_read")
    # Bob changes his own list.
    own.async_set_context(Context(user_id=bob_id))
    await own.async_create_todo_item(TodoItem(summary="Dune"))
    assert store.reading_row(BOB, book["id"])["status"] == "want"
    # Bob cannot change the list of Alice.
    await call(
        "set_reading", {"book_id": book["id"], "person_id": ALICE, "status": "want"}
    )
    other.async_set_context(Context(user_id=bob_id))
    for attempt in (
        other.async_create_todo_item(TodoItem(summary="Dune")),
        other.async_update_todo_item(
            TodoItem(uid=book["id"], status=TodoItemStatus.COMPLETED)
        ),
        other.async_delete_todo_items([book["id"]]),
    ):
        with pytest.raises(HomeAssistantError) as info:
            await attempt
        assert info.value.translation_key == "todo_not_allowed"
        assert info.value.translation_placeholders == {"person": "Alice"}
    assert store.reading_row(ALICE, book["id"])["status"] == "want"
    # The admin user changes any list.
    own.async_set_context(Context(user_id=persons["admin"].id))
    await own.async_update_todo_item(
        TodoItem(uid=book["id"], status=TodoItemStatus.COMPLETED)
    )
    assert store.reading_row(BOB, book["id"])["status"] == "read"
    # Through the todo service, a user with no person cannot change the list.
    dan = await hass.auth.async_create_user("Dan", group_ids=["system-users"])
    with pytest.raises(HomeAssistantError) as info:
        await hass.services.async_call(
            TODO,
            "remove_item",
            {"item": [book["id"]]},
            target={"entity_id": "todo.home_keeper_library_alice_to_read"},
            blocking=True,
            context=Context(user_id=dan.id),
        )
    assert info.value.translation_key == "todo_not_allowed"
    assert store.reading_row(ALICE, book["id"])["status"] == "want"


async def test_entities_are_unavailable_while_sharing_is_off(
    hass, setup_entry, call, ws
) -> None:
    book = await _book(call)
    await call(
        "set_reading", {"book_id": book["id"], "person_id": BOB, "status": "want"}
    )
    ids = (
        "todo.home_keeper_library_bob_to_read",
        "sensor.home_keeper_library_bob_books_read_this_year",
        "sensor.home_keeper_library_bob_reading_now",
    )
    assert all(hass.states.get(e).state != "unavailable" for e in ids)
    await call("set_person_settings", {"person_id": BOB, "share_reading": False})
    await hass.async_block_till_done()
    for entity_id in ids:
        state = hass.states.get(entity_id)
        assert state.state == "unavailable", entity_id
        assert "books" not in state.attributes and "goal" not in state.attributes
    # The to-do list gives no items while sharing is off.
    assert _todo_entity(hass, ids[0]).todo_items == []
    client = await ws("admin")
    reply = await _send(client, type="todo/item/list", entity_id=ids[0])
    assert reply["result"] == {"items": []}
    # Alice still shares her reading.
    alice = hass.states.get("sensor.home_keeper_library_alice_reading_now")
    assert alice.state == "0"
    await call("set_person_settings", {"person_id": BOB, "share_reading": True})
    await hass.async_block_till_done()
    assert hass.states.get(ids[0]).state == "1"
    assert hass.states.get(ids[2]).state == "0"
