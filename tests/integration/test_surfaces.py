"""Docker integration: touch every surface of the integration once.

The other tests in this tier check one behavior each. This module calls the
diagnostics download, each config flow and options flow step, and every
``home_keeper_library`` service against the real container. The CI log gate
(``ci/check-ha-log.py``) then reads the container log. Home Assistant runs in
Python dev mode there (see ``docker-compose.yml``), so a blocking call in the
event loop, a coroutine that nobody awaited or a slow callback shows in the log.

No call here reaches Open Library: a service that would reach it gets input that
fails the validation first. The tests prove only that a surface runs and does not
crash. The component tier checks the results.
"""

from __future__ import annotations

import pytest

DOMAIN = "home_keeper_library"

# Services that Open Library would answer. A valid call reaches the network, so
# the test sends input that fails validation, and the service answers with an error.
VALIDATION_ONLY = {
    "lookup_isbn": {"isbn": "not-an-isbn"},
    "search_catalog": {"title": " "},
    "scan_isbn": {"isbn": "not-an-isbn"},
    "refresh_book": {"book_id": "missing"},
    "send_to_catalog": {"book_id": "missing"},
    "link_catalog": {"book_id": "missing", "record": "missing"},
}


def _service(api, name: str, data: dict | None = None) -> dict:
    """Call a service and return its response. A 4xx or 5xx fails the test."""
    resp = api.post(f"/api/services/{DOMAIN}/{name}?return_response", json=data or {})
    assert resp.status_code == 200, (name, resp.status_code, resp.text)
    return resp.json().get("service_response") or {}


def _entry_id(api) -> str:
    entries = api.get("/api/config/config_entries/entry").json()
    return next(e["entry_id"] for e in entries if e["domain"] == DOMAIN)


def test_diagnostics_download(api):
    resp = api.get(f"/api/diagnostics/config_entry/{_entry_id(api)}")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["revision"] >= 0 and "library" in data and "counts" in data
    assert "openlibrary_connected" in data


def test_config_flow_aborts_when_the_entry_exists(api):
    resp = api.post("/api/config/config_entries/flow", json={"handler": DOMAIN})
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["type"] == "abort", result
    assert result["reason"] in ("already_configured", "single_instance_allowed")


def test_options_flow_steps(api):
    entry_id = _entry_id(api)
    base = "/api/config/config_entries/options/flow"
    menu = api.post(base, json={"handler": entry_id}).json()
    assert menu["type"] == "menu" and menu["step_id"] == "init", menu

    # The Open Library step shows its form. The test does not submit it, because
    # a login would reach Open Library.
    form = api.post(f"{base}/{menu['flow_id']}", json={"next_step_id": "openlibrary"})
    assert form.json()["type"] == "form", form.text
    assert form.json()["step_id"] == "openlibrary"

    menu = api.post(base, json={"handler": entry_id}).json()
    form = api.post(f"{base}/{menu['flow_id']}", json={"next_step_id": "currency"})
    assert form.json()["type"] == "form" and form.json()["step_id"] == "currency"
    done = api.post(f"{base}/{menu['flow_id']}", json={"currency": "EUR"})
    assert done.json()["type"] == "create_entry", done.text


def test_every_service_is_touched(api):
    """Run each service once, from a new room to the delete of it."""

    people = _service(api, "list_people")["people"]
    assert people, "the container has no person"
    person = people[0]["person_id"]

    room = _service(api, "add_room", {"name": "Surface room"})["room"]
    _service(api, "update_room", {"room_id": room["id"], "name": "Surface room 2"})
    case = _service(
        api, "add_bookcase", {"room_id": room["id"], "name": "Surface case"}
    )["bookcase"]
    _service(api, "update_bookcase", {"bookcase_id": case["id"], "name": "Case 2"})
    shelf = _service(api, "add_shelf", {"bookcase_id": case["id"], "name": "Shelf"})[
        "shelf"
    ]
    _service(api, "update_shelf", {"shelf_id": shelf["id"], "name": "Shelf 2"})

    book = _service(api, "add_book", {"title": "Surface book", "lookup": False})["book"]
    _service(api, "update_book", {"book_id": book["id"], "title": "Surface book 2"})
    copy = _service(api, "add_copy", {"book_id": book["id"], "shelf_id": shelf["id"]})[
        "copy"
    ]
    _service(api, "update_copy", {"copy_id": copy["id"], "note": "Signed"})
    _service(api, "move_copy", {"copy_id": copy["id"], "shelf_id": shelf["id"]})
    _service(api, "set_cover", {"book_id": book["id"], "kind": "none"})
    _service(
        api,
        "set_reading",
        {"book_id": book["id"], "person_id": person, "status": "reading", "page": 3},
    )
    _service(api, "set_person_settings", {"person_id": person, "yearly_goal": 12})
    _service(api, "set_settings", {"currency": "EUR"})

    loan = _service(
        api, "lend_book", {"copy_id": copy["id"], "party": "Zed", "due": "2030-01-01"}
    )["loan"]
    _service(api, "update_loan", {"loan_id": loan["id"], "note": "Be kind"})
    _service(api, "return_loan", {"loan_id": loan["id"]})
    _service(api, "delete_loan", {"loan_id": loan["id"]})
    borrowed = _service(
        api,
        "borrow_book",
        {"title": "Surface borrowed", "party": "Library", "person_id": person},
    )["loan"]
    _service(api, "delete_loan", {"loan_id": borrowed["id"]})

    wish = _service(
        api, "add_to_wishlist", {"person_id": person, "title": "Surface wish"}
    )["book"]
    _service(api, "update_wishlist", {"book_id": wish["id"], "person_id": person})
    _service(api, "got_wishlist_book", {"book_id": wish["id"]})
    other = _service(api, "add_to_wishlist", {"person_id": person, "title": "Other"})[
        "book"
    ]
    _service(api, "remove_from_wishlist", {"book_id": other["id"]})

    _service(api, "disconnect_catalog")
    _service(api, "skip_catalog", {"book_id": book["id"]})

    for name in ("list_books", "list_locations", "list_loans"):
        _service(api, name)
    _service(api, "get_book", {"book_id": book["id"]})
    csv_text = _service(api, "export_csv")["content"]
    _service(
        api,
        "import_csv",
        {
            "content": csv_text,
            "source": "goodreads",
            "person_id": person,
            "dry_run": True,
        },
    )
    document = _service(api, "export_data")
    _service(api, "import_data", {"document": document, "dry_run": True})

    for name in ("delete_copy",):
        _service(api, name, {"copy_id": copy["id"]})
    _service(api, "delete_book", {"book_id": book["id"]})
    _service(api, "delete_book", {"book_id": wish["id"]})
    _service(api, "delete_shelf", {"shelf_id": shelf["id"]})
    _service(api, "delete_bookcase", {"bookcase_id": case["id"]})
    _service(api, "delete_room", {"room_id": room["id"]})


@pytest.mark.parametrize("name", sorted(VALIDATION_ONLY))
def test_network_services_answer_a_validation_error(api, name):
    resp = api.post(
        f"/api/services/{DOMAIN}/{name}?return_response", json=VALIDATION_ONLY[name]
    )
    # Home Assistant 2025.7 answers a ServiceValidationError with 500 and the
    # traceback. Newer versions answer with 400. Both are a handled error.
    assert resp.status_code in (400, 500), (name, resp.status_code, resp.text)
    assert "ServiceValidationError" in resp.text or resp.status_code == 400, resp.text


def test_every_service_has_a_touch(api):
    """A new service must get a call above, or an entry in VALIDATION_ONLY."""
    import re
    from pathlib import Path

    services_yaml = (
        Path(__file__).resolve().parents[2]
        / "custom_components"
        / DOMAIN
        / "services.yaml"
    )
    # A service name is a key at the start of a line. The pip install of this tier
    # has no YAML parser.
    declared = set(
        re.findall(r"^(\w+):", services_yaml.read_text(encoding="utf-8"), re.M)
    )
    source = Path(__file__).read_text(encoding="utf-8")
    missing = {
        name
        for name in declared
        if name not in VALIDATION_ONLY and f'"{name}"' not in source
    }
    assert not missing, f"no call in test_surfaces.py for: {sorted(missing)}"
