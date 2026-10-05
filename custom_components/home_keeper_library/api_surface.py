"""The index of every surface that an integrator can use.

The public API of Home Keeper Library is in registries that do not know about
each other: the services in ``services.py``, the bus events in ``const.py`` with
payloads from ``events.py``, the websocket commands in ``websocket_api.py``, the
entity platforms in ``const.PLATFORMS``, and the HTTP views in ``covers.py`` and
``frontend_assets.py``. This module declares each surface once.

The runtime reads this model. ``services.py`` registers each service of
:data:`SERVICES` and applies its admin gate, ``websocket_api.py`` registers the
websocket twin of each service from :data:`WEBSOCKET_COMMANDS`, and
``async_unload_entry`` removes :data:`SERVICE_NAMES`. The unit test
``tests/unit/test_api_surface.py`` reads the source and fails on drift.

**The model holds names and structure only.** The labels and descriptions are in
``services.yaml`` and ``strings.json``. :attr:`EventSpec.summary` is the 1
exception, because a bus event has no Home Assistant string source.

The module is pure. It imports no Home Assistant code, and only ``const`` from the
integration.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import const

# ── Descriptors ──────────────────────────────────────────────────────────────
#
# Each table is a tuple, never a set, so that each rendering has the same order.


@dataclass(frozen=True, slots=True)
class Field:
    """One key in an event payload or an entity attribute map."""

    name: str
    type: str = ""
    """Shown as is, such as ``"str | None"``. Never parsed."""
    note: str = ""


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    """A ``home_keeper_library.*`` service.

    ``name`` is the key in ``services.yaml``, in ``strings.json`` ``services`` and
    in the handler table of ``services.py``.
    """

    name: str
    admin_only: bool = False
    """The service handler rejects a non-admin user with ``Unauthorized``."""
    response: str = "none"
    """``"none"``, ``"optional"`` or ``"only"``, as ``SupportsResponse``."""
    caller_scoped: bool = False
    """Open to every user, but a non-admin user can change only their own person."""


@dataclass(frozen=True, slots=True)
class EventSpec:
    """A bus event that the integration fires, or one that it listens for."""

    name: str
    """The value of the ``const`` attribute. Never a typed copy."""
    const_name: str
    """The ``const`` attribute that holds the name."""
    direction: str
    """``"fired"`` or ``"listened"``."""
    payload: str
    """A key of :data:`PAYLOAD_SPINES`, or ``"none"``."""
    summary: str = ""
    """When the event fires. Required for a fired event."""
    extra: tuple[Field, ...] = ()
    """The keys that the event adds to its spine."""


@dataclass(frozen=True, slots=True)
class DeviceTriggerSpec:
    """A device trigger for a bus event. The library has none."""

    type: str
    event: str
    scope: str


@dataclass(frozen=True, slots=True)
class EntityPlatformSpec:
    """An entity platform and the state attributes of its entities."""

    platform: str
    translation_keys: tuple[str, ...] = ()
    """Keys in ``strings.json`` ``entity.<platform>``."""
    attributes: tuple[Field, ...] = ()


@dataclass(frozen=True, slots=True)
class WebsocketSpec:
    """A websocket command of the tab and the card.

    A command with a ``service`` is the twin of that service: it takes the same
    fields, has the same gate and calls the same code. The runtime registers it
    from this table.
    """

    type: str
    admin_only: bool = False
    service: str | None = None


@dataclass(frozen=True, slots=True)
class HttpViewSpec:
    """An HTTP route that the integration registers."""

    name: str
    url: str
    methods: tuple[str, ...]
    requires_auth: bool = True
    admin_methods: tuple[str, ...] = ()
    """The methods that only an admin user can call."""


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """A config entry option key."""

    key: str
    in_flow: bool
    """Whether the options flow shows it."""


@dataclass(frozen=True, slots=True)
class SurfaceKind:
    """One kind of Home Assistant integration surface, and the stance of the library.

    The table lists also the kinds that the library does not offer, each with a
    reason. A list of only the offered kinds cannot show what is missing.
    """

    kind: str
    status: str
    """``"published"``, ``"internal"``, ``"not_applicable"`` or ``"deferred"``."""
    note: str
    """One sentence. Required."""


STATUSES = ("published", "internal", "not_applicable", "deferred")


# ── Services ─────────────────────────────────────────────────────────────────

_ADMIN = {"admin_only": True}

SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec("add_room", response="optional", **_ADMIN),
    ServiceSpec("update_room", response="optional", **_ADMIN),
    ServiceSpec("delete_room", response="optional", **_ADMIN),
    ServiceSpec("add_bookcase", response="optional", **_ADMIN),
    ServiceSpec("update_bookcase", response="optional", **_ADMIN),
    ServiceSpec("delete_bookcase", response="optional", **_ADMIN),
    ServiceSpec("add_shelf", response="optional", **_ADMIN),
    ServiceSpec("update_shelf", response="optional", **_ADMIN),
    ServiceSpec("delete_shelf", response="optional", **_ADMIN),
    ServiceSpec("lookup_isbn", response="only", **_ADMIN),
    ServiceSpec("add_book", response="optional", **_ADMIN),
    ServiceSpec("update_book", response="optional", **_ADMIN),
    ServiceSpec("delete_book", response="optional", **_ADMIN),
    ServiceSpec("refresh_book", response="optional", **_ADMIN),
    ServiceSpec("scan_isbn", response="optional", **_ADMIN),
    ServiceSpec("add_copy", response="optional", **_ADMIN),
    ServiceSpec("update_copy", response="optional", **_ADMIN),
    ServiceSpec("move_copy", response="optional", **_ADMIN),
    ServiceSpec("delete_copy", response="optional", **_ADMIN),
    ServiceSpec("set_cover", response="optional", **_ADMIN),
    ServiceSpec("set_reading", response="optional", caller_scoped=True),
    ServiceSpec("lend_book", response="optional", **_ADMIN),
    ServiceSpec("borrow_book", response="optional", **_ADMIN),
    ServiceSpec("return_loan", response="optional", **_ADMIN),
    ServiceSpec("update_loan", response="optional", **_ADMIN),
    ServiceSpec("delete_loan", response="optional", **_ADMIN),
    ServiceSpec("add_to_wishlist", response="optional", **_ADMIN),
    ServiceSpec("update_wishlist", response="optional", **_ADMIN),
    ServiceSpec("remove_from_wishlist", response="optional", **_ADMIN),
    ServiceSpec("got_wishlist_book", response="optional", **_ADMIN),
    ServiceSpec("set_person_settings", response="optional", caller_scoped=True),
    ServiceSpec("set_settings", response="optional", **_ADMIN),
    ServiceSpec("import_csv", response="optional", **_ADMIN),
    ServiceSpec("export_csv", response="only", **_ADMIN),
    ServiceSpec("list_books", response="only"),
    ServiceSpec("get_book", response="only"),
    ServiceSpec("list_locations", response="only"),
    ServiceSpec("list_loans", response="only"),
    ServiceSpec("list_people", response="only"),
)

#: The services that ``async_unload_entry`` removes.
SERVICE_NAMES: tuple[str, ...] = tuple(spec.name for spec in SERVICES)

#: The read services. Each reply goes through ``projections``. They have no
#: websocket twin, because ``get_state`` gives the same data to the tab and card.
READ_SERVICES: tuple[str, ...] = (
    "list_books",
    "get_book",
    "list_locations",
    "list_loans",
    "list_people",
)


# ── Event payloads ───────────────────────────────────────────────────────────
#
# One spine per payload shape. The drift test calls the builders in events.py
# and compares the keys.

_ORIGIN = Field("origin", "str | None", "The origin marker of the caller.")

PAYLOAD_SPINES: dict[str, tuple[Field, ...]] = {
    "room": (
        Field("room_id", "str"),
        Field("name", "str"),
        _ORIGIN,
    ),
    "bookcase": (
        Field("bookcase_id", "str"),
        Field("room_id", "str"),
        Field("name", "str"),
        _ORIGIN,
    ),
    "shelf": (
        Field("shelf_id", "str"),
        Field("bookcase_id", "str"),
        Field("name", "str"),
        _ORIGIN,
    ),
    "book": (
        Field("book_id", "str", "Stable id. A rename keeps it."),
        Field("title", "str", "The title at the time of the event."),
        Field("person_id", "str | None", "The Home Assistant person, if any."),
        _ORIGIN,
    ),
    "import": (
        Field("person_id", "str | None"),
        Field("source", "str", "goodreads, storygraph or library."),
        Field("rows", "int"),
        Field("books_added", "int"),
        Field("books_matched", "int"),
        Field("copies_added", "int"),
        Field("reading_set", "int"),
        Field("wishlist_added", "int"),
        Field("errors", "int"),
        _ORIGIN,
    ),
    "person_settings": (
        Field("person_id", "str", "The Home Assistant person."),
        Field("changed_fields", "list[str]", "The names of the changed settings."),
        _ORIGIN,
    ),
    "settings": (
        Field("changed_fields", "list[str]", "The changed options."),
        Field("currency", "str", "The currency code now."),
        _ORIGIN,
    ),
}

_CHANGED = (Field("changed_fields", "list[str]", "The fields that changed."),)
_COPY = (Field("copy_id", "str"), Field("shelf_id", "str | None"))
_LOAN = (
    Field("loan_id", "str"),
    Field("direction", "str", "out (lent) or in (borrowed)."),
    Field("copy_id", "str | None"),
    Field("party", "str", "The other person of the loan."),
    Field("started", "str", "YYYY-MM-DD."),
    Field("due", "str | None", "YYYY-MM-DD."),
    Field("returned", "str | None", "YYYY-MM-DD."),
)
_WISH = (Field("buy", "bool"), Field("bought", "bool"))


def _event(
    const_name: str, payload: str, summary: str, extra: tuple[Field, ...] = ()
) -> EventSpec:
    return EventSpec(
        getattr(const, const_name), const_name, "fired", payload, summary, extra
    )


# ── Events ───────────────────────────────────────────────────────────────────

EVENTS: tuple[EventSpec, ...] = (
    _event("EVENT_ROOM_ADDED", "room", "A room was added."),
    _event("EVENT_ROOM_UPDATED", "room", "A room changed.", _CHANGED),
    _event("EVENT_ROOM_REMOVED", "room", "A room was deleted."),
    _event("EVENT_BOOKCASE_ADDED", "bookcase", "A bookcase was added."),
    _event("EVENT_BOOKCASE_UPDATED", "bookcase", "A bookcase changed.", _CHANGED),
    _event("EVENT_BOOKCASE_REMOVED", "bookcase", "A bookcase was deleted."),
    _event("EVENT_SHELF_ADDED", "shelf", "A shelf was added."),
    _event("EVENT_SHELF_UPDATED", "shelf", "A shelf changed.", _CHANGED),
    _event("EVENT_SHELF_REMOVED", "shelf", "A shelf was deleted."),
    _event("EVENT_BOOK_ADDED", "book", "A book was added."),
    _event(
        "EVENT_BOOK_UPDATED",
        "book",
        "The fields, the cover or the wishlist entry of a book changed.",
        _CHANGED,
    ),
    _event(
        "EVENT_BOOK_REMOVED",
        "book",
        "A book was deleted, with its copies, reading rows and loans.",
    ),
    _event("EVENT_COPY_ADDED", "book", "A copy of a book was added.", _COPY),
    _event(
        "EVENT_COPY_MOVED",
        "book",
        "A copy moved to another shelf, or off its shelf.",
        (*_COPY, Field("previous_shelf_id", "str | None")),
    ),
    _event(
        "EVENT_COPY_UPDATED",
        "book",
        "The fields of a copy changed, other than its shelf.",
        (*_COPY, *_CHANGED),
    ),
    _event("EVENT_COPY_REMOVED", "book", "A copy was deleted.", _COPY),
    _event(
        "EVENT_READING_CHANGED",
        "book",
        "The reading row of a person changed. status is None for a removed row.",
        (Field("status", "str | None"), Field("previous_status", "str | None")),
    ),
    _event(
        "EVENT_READING_UPDATED",
        "book",
        "The rating, page, dates, count or notes of a reading row changed, and "
        "the status stayed. Names the fields, never the notes.",
        (Field("status", "str"), *_CHANGED),
    ),
    _event(
        "EVENT_BOOK_FINISHED",
        "book",
        "The reading status of a person became read.",
        (
            Field("finished", "str | None", "YYYY-MM-DD."),
            Field("rating", "int | None"),
            Field("read_count", "int"),
        ),
    ),
    _event("EVENT_LOAN_STARTED", "book", "A book was lent or borrowed.", _LOAN),
    _event("EVENT_LOAN_RETURNED", "book", "A loan was returned.", _LOAN),
    _event(
        "EVENT_LOAN_UPDATED",
        "book",
        "The party, the dates, the format or the note of a loan changed.",
        (*_LOAN, *_CHANGED),
    ),
    _event("EVENT_LOAN_REMOVED", "book", "A loan was deleted.", _LOAN),
    _event(
        "EVENT_LOAN_OVERDUE",
        "book",
        "An open loan passed its due date. Fires once for each due date.",
        _LOAN,
    ),
    _event("EVENT_WISHLIST_ADDED", "book", "A book was added to a wishlist.", _WISH),
    _event("EVENT_WISHLIST_REMOVED", "book", "A book left the wishlist.", _WISH),
    _event("EVENT_IMPORT_COMPLETED", "import", "A CSV import was written."),
    _event(
        "EVENT_PERSON_SETTINGS_UPDATED",
        "person_settings",
        "The library settings of a person changed. Names the settings only.",
    ),
    _event(
        "EVENT_SETTINGS_UPDATED",
        "settings",
        "The options of the library changed, such as the currency.",
    ),
    EventSpec(
        const.HOME_KEEPER_EVENT_TASK_COMPLETED,
        "HOME_KEEPER_EVENT_TASK_COMPLETED",
        "listened",
        "none",
        summary="A completed loan task returns its loan.",
    ),
    EventSpec(
        const.HOME_KEEPER_EVENT_TASK_DELETED,
        "HOME_KEEPER_EVENT_TASK_DELETED",
        "listened",
        "none",
        summary="A deleted loan task clears the task id of its loan.",
    ),
    EventSpec(
        const.HOME_KEEPER_EVENT_REGISTER_COMPANIONS,
        "HOME_KEEPER_EVENT_REGISTER_COMPANIONS",
        "listened",
        "none",
        summary="The library registers as a companion again.",
    ),
)


# ── Device triggers ──────────────────────────────────────────────────────────

DEVICE_TRIGGERS: tuple[DeviceTriggerSpec, ...] = ()


# ── Entity platforms ─────────────────────────────────────────────────────────

ENTITY_PLATFORMS: tuple[EntityPlatformSpec, ...] = (
    EntityPlatformSpec(
        "sensor",
        translation_keys=(
            "books",
            "loans_out",
            "loans_overdue",
            "books_read_this_year",
            "reading_now",
        ),
        attributes=(
            Field("goal", "int | None", "Books read this year: the yearly goal."),
            Field("pages", "int", "Books read this year: the pages read."),
            Field("year", "int", "Books read this year: the year."),
            Field("books", "list[str]", "Reading now: at most 10 titles."),
            Field("person_id", "str", "The person of a per-person sensor."),
        ),
    ),
    EntityPlatformSpec(
        "todo",
        translation_keys=("to_read",),
        attributes=(Field("person_id", "str", "The person of the list."),),
    ),
)


# ── Websocket commands (internal) ────────────────────────────────────────────

WEBSOCKET_COMMANDS: tuple[WebsocketSpec, ...] = (
    WebsocketSpec(f"{const.DOMAIN}/get_state"),
    WebsocketSpec(f"{const.DOMAIN}/subscribe"),
    WebsocketSpec(f"{const.DOMAIN}/list_todo_entities", admin_only=True),
    *(
        WebsocketSpec(
            f"{const.DOMAIN}/{spec.name}", admin_only=spec.admin_only, service=spec.name
        )
        for spec in SERVICES
        if spec.name not in READ_SERVICES
    ),
)


# ── HTTP routes (internal) ───────────────────────────────────────────────────

HTTP_VIEWS: tuple[HttpViewSpec, ...] = (
    HttpViewSpec(
        "static",
        const.STATIC_URL,
        ("GET",),
        # Home Assistant serves a static path before authentication, so only the
        # built bundles in frontend/dist/ are in this path.
        requires_auth=False,
    ),
    HttpViewSpec("cover", const.COVER_URL_PREFIX + "/{book_id}", ("GET",)),
    HttpViewSpec(
        "cover_upload", const.COVER_UPLOAD_URL, ("POST",), admin_methods=("POST",)
    ),
)


# ── Config entry options ─────────────────────────────────────────────────────

OPTIONS: tuple[OptionSpec, ...] = (OptionSpec(const.CONF_CURRENCY, in_flow=True),)


# ── The whole surface space ──────────────────────────────────────────────────

SURFACE_KINDS: tuple[SurfaceKind, ...] = (
    SurfaceKind(
        "Actions (services)",
        "published",
        "Each operation that changes or exports library data is a "
        "`home_keeper_library.*` service.",
    ),
    SurfaceKind(
        "Bus events",
        "published",
        "Each state change fires a `home_keeper_library_<noun>_<verb>` event with a "
        "payload from a pure builder.",
    ),
    SurfaceKind(
        "Device triggers",
        "not_applicable",
        "The library has 1 service device and no device per book for a trigger.",
    ),
    SurfaceKind(
        "Device conditions",
        "not_applicable",
        "The sensors and the to-do lists give the state that a condition reads.",
    ),
    SurfaceKind(
        "Device actions",
        "not_applicable",
        "The services cover each operation and take a book id directly.",
    ),
    SurfaceKind(
        "Entity platforms",
        "published",
        "A `sensor` platform with library and per-person counts, and a per-person "
        "`todo` list of the books to read.",
    ),
    SurfaceKind(
        "Entity attributes",
        "published",
        "The per-person sensors give the yearly goal, the pages and the titles.",
    ),
    SurfaceKind(
        "Config entry options",
        "published",
        "The currency of the prices and values of the copies.",
    ),
    SurfaceKind(
        "Config flow",
        "published",
        "A single-instance setup flow with a currency field.",
    ),
    SurfaceKind(
        "Websocket commands",
        "internal",
        "The tab and the card read the state and call the twin of each service.",
    ),
    SurfaceKind(
        "HTTP routes",
        "internal",
        "A static path for the bundles, and the cover upload and cover views.",
    ),
    SurfaceKind(
        "Diagnostics",
        "published",
        "The config entry gives a diagnostics download, with names and notes redacted.",
    ),
    SurfaceKind(
        "Reauth / reconfigure flows",
        "not_applicable",
        "The storage is local and needs no credentials.",
    ),
    SurfaceKind(
        "Repairs / issue registry",
        "published",
        "An issue shows when Home Keeper is missing, not set up or too old for "
        "the tab.",
    ),
    SurfaceKind(
        "Discovery",
        "not_applicable",
        "No device or service on the network is a library.",
    ),
    SurfaceKind(
        "Home Keeper panel tab",
        "internal",
        "The admin UI is a tab in the Home Keeper panel, registered through the "
        "Python API of Home Keeper.",
    ),
)


def events_by_payload(payload: str) -> tuple[EventSpec, ...]:
    """Return every fired event sharing one payload shape, in declaration order."""
    return tuple(
        spec for spec in EVENTS if spec.direction == "fired" and spec.payload == payload
    )


__all__ = [
    "DEVICE_TRIGGERS",
    "ENTITY_PLATFORMS",
    "EVENTS",
    "HTTP_VIEWS",
    "OPTIONS",
    "PAYLOAD_SPINES",
    "READ_SERVICES",
    "SERVICES",
    "SERVICE_NAMES",
    "STATUSES",
    "SURFACE_KINDS",
    "WEBSOCKET_COMMANDS",
    "DeviceTriggerSpec",
    "EntityPlatformSpec",
    "EventSpec",
    "Field",
    "HttpViewSpec",
    "OptionSpec",
    "ServiceSpec",
    "SurfaceKind",
    "WebsocketSpec",
    "events_by_payload",
]
