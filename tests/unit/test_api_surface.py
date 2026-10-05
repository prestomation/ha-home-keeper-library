"""Drift test for the API surface model (no Home Assistant runtime).

``api_surface.py`` declares each surface that an integrator can use. These tests
read the source of the component with :mod:`ast` and compare it to the model. A
service with no spec, an event in ``const.py`` that the model does not have, a
websocket command that is not registered, or a payload key that the model does
not document fails here.

**Limits.** The tests read literals. A name built at run time is invisible to
them. If you add such a name, extend this file.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import ex.api_surface as api_surface
import ex.const as const
import ex.events as events
import pytest

_COMPONENT = (
    Path(__file__).resolve().parents[2] / "custom_components" / "home_keeper_library"
)


def _tree(name: str) -> ast.Module:
    return ast.parse((_COMPONENT / name).read_text(encoding="utf-8"))


_INIT_TREE = _tree("__init__.py")
_SERVICES_TREE = _tree("services.py")
_WS_TREE = _tree("websocket_api.py")
_FRONTEND_TREE = _tree("frontend_assets.py")
_COVERS_TREE = _tree("covers.py")
_SURFACE_TREE = _tree("api_surface.py")
_STRINGS = json.loads((_COMPONENT / "strings.json").read_text(encoding="utf-8"))

_FIX = "Add or update its spec in custom_components/home_keeper_library/api_surface.py."


def _services_yaml() -> dict:
    yaml = pytest.importorskip("yaml", reason="PyYAML not installed")
    return yaml.safe_load((_COMPONENT / "services.yaml").read_text(encoding="utf-8"))


def _module_assign(tree: ast.Module, name: str) -> ast.expr:
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == name for t in targets):
                assert node.value is not None
                return node.value
    raise AssertionError(f"{name} is not assigned at module level")


def _dict_keys(tree: ast.Module, node: ast.expr) -> list[str]:
    """The string keys of a dict literal, with ``**NAME`` spreads resolved.

    A key is a string constant or a ``vol.Required("x")`` / ``vol.Optional("x")``
    call.
    """
    assert isinstance(node, ast.Dict), ast.unparse(node)
    keys: list[str] = []
    for key, value in zip(node.keys, node.values, strict=True):
        if key is None:
            assert isinstance(value, ast.Name), ast.unparse(value)
            keys.extend(_dict_keys(tree, _module_assign(tree, value.id)))
        elif isinstance(key, ast.Constant):
            keys.append(key.value)
        else:
            assert isinstance(key, ast.Call) and isinstance(key.args[0], ast.Constant)
            keys.append(key.args[0].value)
    return keys


def _service_fields() -> dict[str, list[str]]:
    table = _module_assign(_SERVICES_TREE, "SERVICE_FIELDS")
    assert isinstance(table, ast.Dict)
    out = {}
    for key, value in zip(table.keys, table.values, strict=True):
        assert isinstance(key, ast.Constant)
        out[key.value] = _dict_keys(_SERVICES_TREE, value)
    return out


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == name
        ):
            return node
    raise AssertionError(f"no function {name}")


# ── Services ─────────────────────────────────────────────────────────────────


def test_every_service_has_a_handler_and_fields() -> None:
    handlers = _dict_keys(
        _SERVICES_TREE, _module_assign(_SERVICES_TREE, "SERVICE_HANDLERS")
    )
    modelled = set(api_surface.SERVICE_NAMES)
    assert set(handlers) == modelled, (
        f"SERVICE_HANDLERS and the model disagree: {sorted(set(handlers) ^ modelled)}"
    )
    assert set(_service_fields()) == modelled


def test_registration_iterates_the_model() -> None:
    register = _function(_SERVICES_TREE, "async_register_services")
    loops = [n for n in ast.walk(register) if isinstance(n, ast.For)]
    assert any(ast.unparse(loop.iter) == "SERVICES" for loop in loops)
    calls = [
        n
        for n in ast.walk(register)
        if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("async_register")
    ]
    assert calls and ast.unparse(calls[0].args[1]) == "spec.name"


def test_service_gate_reads_the_model() -> None:
    run = _function(_SERVICES_TREE, "async_run")
    assert "spec.admin_only" in ast.unparse(run), (
        "async_run must apply the admin_only flag of the model."
    )


def test_service_names_are_unique() -> None:
    assert len(api_surface.SERVICE_NAMES) == len(set(api_surface.SERVICE_NAMES))


def test_service_teardown_iterates_the_model() -> None:
    unload = _function(_INIT_TREE, "async_unload_entry")
    loops = [node for node in ast.walk(unload) if isinstance(node, ast.For)]
    assert any(ast.unparse(loop.iter) == "SERVICE_NAMES" for loop in loops)
    assert any(
        isinstance(n, ast.Call) and ast.unparse(n.func).endswith("async_remove")
        for n in ast.walk(unload)
    )


def test_service_response_kinds_are_known() -> None:
    for spec in api_surface.SERVICES:
        assert spec.response in ("none", "optional", "only"), spec.name
        assert not (spec.admin_only and spec.caller_scoped), spec.name


def test_read_services_are_open_and_answer_only() -> None:
    for spec in api_surface.SERVICES:
        if spec.name in api_surface.READ_SERVICES:
            assert not spec.admin_only and spec.response == "only", spec.name


def test_services_yaml_matches_model() -> None:
    declared = set(_services_yaml())
    assert declared == set(api_surface.SERVICE_NAMES), sorted(
        declared ^ set(api_surface.SERVICE_NAMES)
    )


def test_service_strings_match_model() -> None:
    assert set(_STRINGS["services"]) == set(api_surface.SERVICE_NAMES)


@pytest.mark.parametrize("service", api_surface.SERVICE_NAMES)
def test_service_fields_match_yaml_strings_and_schema(service: str) -> None:
    yaml_fields = set((_services_yaml()[service] or {}).get("fields") or {})
    string_fields = set(_STRINGS["services"][service].get("fields", {}))
    schema_fields = set(_service_fields()[service])
    assert yaml_fields == string_fields == schema_fields, (
        f"{service}: services.yaml {sorted(yaml_fields)}, strings.json "
        f"{sorted(string_fields)}, SERVICE_FIELDS {sorted(schema_fields)}."
    )


# ── Events ───────────────────────────────────────────────────────────────────


def _const_event_names() -> dict[str, str]:
    return {
        name: getattr(const, name)
        for name in dir(const)
        if (name.startswith("EVENT_") or name.startswith("HOME_KEEPER_EVENT_"))
        and isinstance(getattr(const, name), str)
    }


def test_every_const_event_is_modelled() -> None:
    declared = _const_event_names()
    modelled = {spec.const_name: spec.name for spec in api_surface.EVENTS}
    assert set(declared) == set(modelled), sorted(set(declared) ^ set(modelled))
    for spec in api_surface.EVENTS:
        assert spec.name == declared[spec.const_name]


def test_event_names_follow_the_pattern() -> None:
    for spec in api_surface.EVENTS:
        if spec.direction == "fired":
            assert spec.name.startswith(f"{const.DOMAIN}_"), spec.name


def test_every_event_has_a_summary_and_a_known_payload() -> None:
    for spec in api_surface.EVENTS:
        assert spec.summary, spec.name
        assert spec.direction in ("fired", "listened"), spec.name
        assert spec.payload == "none" or spec.payload in api_surface.PAYLOAD_SPINES


_BOOK = {"id": "b1", "title": "Dune"}
_COPY = {"id": "c1", "shelf_id": "s1"}
_LOAN = {
    "id": "l1",
    "direction": "out",
    "copy_id": "c1",
    "party": "Alex",
    "person_id": None,
    "started": "2026-10-01",
    "due": None,
    "returned": None,
}


def _built() -> dict[str, dict[str, Any]]:
    """1 payload for each fired event, from the real builders."""
    room = {"id": "r1", "name": "Den"}
    bookcase = {"id": "k1", "room_id": "r1", "name": "Left"}
    shelf = {"id": "s1", "bookcase_id": "k1", "name": "Top"}
    entry = {"person_id": "p1", "buy": True, "bought": False}
    return {
        const.EVENT_ROOM_ADDED: events.room_event_data(room, None),
        const.EVENT_ROOM_UPDATED: events.location_changed_data(
            events.room_event_data(room, None), ["name"]
        ),
        const.EVENT_ROOM_REMOVED: events.room_event_data(room, None),
        const.EVENT_BOOKCASE_ADDED: events.bookcase_event_data(bookcase, None),
        const.EVENT_BOOKCASE_UPDATED: events.location_changed_data(
            events.bookcase_event_data(bookcase, None), ["name"]
        ),
        const.EVENT_BOOKCASE_REMOVED: events.bookcase_event_data(bookcase, None),
        const.EVENT_SHELF_ADDED: events.shelf_event_data(shelf, None),
        const.EVENT_SHELF_UPDATED: events.location_changed_data(
            events.shelf_event_data(shelf, None), ["name"]
        ),
        const.EVENT_SHELF_REMOVED: events.shelf_event_data(shelf, None),
        const.EVENT_BOOK_ADDED: events.book_event_data(_BOOK, None),
        const.EVENT_BOOK_UPDATED: events.book_updated_event_data(_BOOK, ["x"], None),
        const.EVENT_BOOK_REMOVED: events.book_event_data(_BOOK, None),
        const.EVENT_COPY_ADDED: events.copy_event_data(_BOOK, _COPY, None),
        const.EVENT_COPY_MOVED: events.copy_moved_event_data(_BOOK, _COPY, "s0", None),
        const.EVENT_COPY_REMOVED: events.copy_event_data(_BOOK, _COPY, None),
        const.EVENT_READING_CHANGED: events.reading_changed_event_data(
            _BOOK, "p1", "read", "reading", None
        ),
        const.EVENT_BOOK_FINISHED: events.book_finished_event_data(
            _BOOK, "p1", {"finished": "2026-10-01", "rating": 5}, None
        ),
        const.EVENT_LOAN_STARTED: events.loan_event_data(_BOOK, _LOAN, None),
        const.EVENT_LOAN_RETURNED: events.loan_event_data(_BOOK, _LOAN, None),
        const.EVENT_LOAN_OVERDUE: events.loan_event_data(_BOOK, _LOAN, None),
        const.EVENT_WISHLIST_ADDED: events.wishlist_event_data(_BOOK, entry, None),
        const.EVENT_WISHLIST_REMOVED: events.wishlist_event_data(_BOOK, entry, None),
        const.EVENT_IMPORT_COMPLETED: events.import_completed_event_data(
            {}, "p1", "goodreads", None
        ),
    }


def test_payloads_match_the_builders() -> None:
    built = _built()
    fired = [spec for spec in api_surface.EVENTS if spec.direction == "fired"]
    assert {spec.name for spec in fired} == set(built)
    for spec in fired:
        spine = {f.name for f in api_surface.PAYLOAD_SPINES[spec.payload]}
        expected = spine | {f.name for f in spec.extra}
        assert set(built[spec.name]) == expected, (
            f"{spec.name} ships {sorted(built[spec.name])}, the model documents "
            f"{sorted(expected)}. {_FIX}"
        )


def test_events_by_payload_keeps_declaration_order() -> None:
    names = [spec.name for spec in api_surface.events_by_payload("room")]
    assert names == [
        const.EVENT_ROOM_ADDED,
        const.EVENT_ROOM_UPDATED,
        const.EVENT_ROOM_REMOVED,
    ]


# ── Entity platforms ─────────────────────────────────────────────────────────


def test_entity_platforms_match_const_and_strings() -> None:
    modelled = {spec.platform for spec in api_surface.ENTITY_PLATFORMS}
    assert modelled == set(const.PLATFORMS)
    for spec in api_surface.ENTITY_PLATFORMS:
        declared = set(_STRINGS["entity"][spec.platform])
        assert set(spec.translation_keys) == declared, spec.platform


# ── Websocket commands ───────────────────────────────────────────────────────


def _decorated_commands() -> dict[str, str]:
    found: dict[str, str] = {}
    for node in ast.walk(_WS_TREE):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if not (
                isinstance(decorator, ast.Call)
                and ast.unparse(decorator.func).endswith("websocket_command")
            ):
                continue
            schema = decorator.args[0]
            assert isinstance(schema, ast.Dict)
            for key, value in zip(schema.keys, schema.values, strict=True):
                if key is not None and "type" in ast.unparse(key):
                    assert isinstance(value, ast.JoinedStr)
                    text = ast.unparse(value)
                    found[text.replace("{DOMAIN}", const.DOMAIN)[2:-1]] = node.name
    return found


def test_every_websocket_command_is_modelled() -> None:
    decorated = set(_decorated_commands())
    twins = {
        spec.type for spec in api_surface.WEBSOCKET_COMMANDS if spec.service is not None
    }
    plain = {
        spec.type for spec in api_surface.WEBSOCKET_COMMANDS if spec.service is None
    }
    assert decorated == plain, sorted(decorated ^ plain)
    assert twins, "no websocket twin of a service"


def test_decorated_commands_are_registered_and_twins_come_from_the_model() -> None:
    register = _function(_WS_TREE, "async_register")
    source = ast.unparse(register)
    for handler in _decorated_commands().values():
        assert f"async_register_command(hass, {handler})" in source, handler
    loops = [n for n in ast.walk(register) if isinstance(n, ast.For)]
    assert any(ast.unparse(loop.iter) == "WEBSOCKET_COMMANDS" for loop in loops)


def test_websocket_twins_match_their_service() -> None:
    services = {spec.name: spec for spec in api_surface.SERVICES}
    for spec in api_surface.WEBSOCKET_COMMANDS:
        if spec.service is None:
            continue
        assert spec.type == f"{const.DOMAIN}/{spec.service}"
        assert spec.admin_only == services[spec.service].admin_only, spec.type
    twins = {s.service for s in api_surface.WEBSOCKET_COMMANDS if s.service}
    assert twins == set(api_surface.SERVICE_NAMES) - set(api_surface.READ_SERVICES)


def test_websocket_types_are_unique() -> None:
    types = [spec.type for spec in api_surface.WEBSOCKET_COMMANDS]
    assert len(types) == len(set(types))


def test_frontend_command_names_stay_the_same() -> None:
    """The tab and the card use these names. A rename breaks the frontend."""
    types = {spec.type for spec in api_surface.WEBSOCKET_COMMANDS}
    for name in (
        "get_state",
        "subscribe",
        "list_todo_entities",
        "add_room",
        "scan_isbn",
        "set_reading",
        "lend_book",
        "borrow_book",
        "return_loan",
        "add_to_wishlist",
        "import_csv",
        "export_csv",
        "lookup_isbn",
        "set_cover",
        "set_person_settings",
    ):
        assert f"{const.DOMAIN}/{name}" in types, name


# ── HTTP routes ──────────────────────────────────────────────────────────────


def _view_urls() -> set[str]:
    urls = set()
    for node in ast.walk(_COVERS_TREE):
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if (
                isinstance(item, ast.Assign)
                and isinstance(item.targets[0], ast.Name)
                and item.targets[0].id == "url"
            ):
                urls.add(ast.unparse(item.value))
    return urls


def test_http_views_match_source() -> None:
    statics = {
        ast.unparse(n.args[0])
        for n in ast.walk(_FRONTEND_TREE)
        if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("StaticPathConfig")
    }
    assert statics == {"STATIC_URL"}
    assert _view_urls() == {"COVER_URL_PREFIX + '/{book_id}'", "COVER_UPLOAD_URL"}
    assert {view.url for view in api_surface.HTTP_VIEWS} == {
        const.STATIC_URL,
        const.COVER_URL_PREFIX + "/{book_id}",
        const.COVER_UPLOAD_URL,
    }
    static = next(v for v in api_surface.HTTP_VIEWS if v.url == const.STATIC_URL)
    assert not static.requires_auth


# ── Options and the ledger ───────────────────────────────────────────────────


def test_options_are_in_the_flow() -> None:
    flow = (_COMPONENT / "config_flow.py").read_text(encoding="utf-8")
    for option in api_surface.OPTIONS:
        assert option.in_flow
        name = next(n for n in dir(const) if getattr(const, n) == option.key)
        assert name in flow, option.key


def test_api_surface_imports_stay_light() -> None:
    for node in ast.walk(_SURFACE_TREE):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("homeassistant"), alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not module.startswith("homeassistant"), module
            if node.level:
                assert {alias.name for alias in node.names} <= {"const"}


def test_surface_kinds_are_known_and_unique() -> None:
    kinds = [kind.kind for kind in api_surface.SURFACE_KINDS]
    assert len(kinds) == len(set(kinds))
    for kind in api_surface.SURFACE_KINDS:
        assert kind.status in api_surface.STATUSES, kind.kind
        assert kind.note, kind.kind


def test_every_populated_table_has_a_surface_kind_row() -> None:
    statuses = {kind.kind: kind.status for kind in api_surface.SURFACE_KINDS}
    populated = {
        "Actions (services)": api_surface.SERVICES,
        "Bus events": api_surface.EVENTS,
        "Device triggers": api_surface.DEVICE_TRIGGERS,
        "Entity platforms": api_surface.ENTITY_PLATFORMS,
        "Config entry options": api_surface.OPTIONS,
        "Websocket commands": api_surface.WEBSOCKET_COMMANDS,
        "HTTP routes": api_surface.HTTP_VIEWS,
    }
    for kind, table in populated.items():
        assert kind in statuses, kind
        assert (statuses[kind] == "not_applicable") == (not table), kind
