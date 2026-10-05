"""Constants for Home Keeper Library.

Home Keeper Library is a companion of Home Keeper. It stores the books of a
household: the rooms, bookcases and shelves where the copies are, the reading
status of each person, the loans and the wishlist. The admin UI is a tab in the
Home Keeper panel. The usage surfaces are the card, the per-person entities and
the services.

This module is pure. It imports no Home Assistant code, so the unit tier can load
it.
"""

from __future__ import annotations

DOMAIN = "home_keeper_library"
NAME = "Home Keeper Library"
ICON = "mdi:bookshelf"
DOCS_URL = "https://github.com/prestomation/ha-home-keeper-library"
USER_AGENT = "HomeKeeperLibrary/{version} (+" + DOCS_URL + ")"

# The Home Keeper integration that this integration requires.
HOME_KEEPER_DOMAIN = "home_keeper"
HOME_KEEPER_EVENT_TASK_COMPLETED = "home_keeper_task_completed"
HOME_KEEPER_EVENT_TASK_DELETED = "home_keeper_task_deleted"
HOME_KEEPER_EVENT_REGISTER_COMPANIONS = "home_keeper_register_companions"
# The first Home Keeper version with the panel tab API (``panel_tabs.py``).
HOME_KEEPER_MIN_VERSION = "0.30.0b2"
HOME_KEEPER_INSTALL_URL = "https://github.com/prestomation/ha-home-keeper#installation"
# The reasons why Home Keeper cannot take the library tab. Each is a config flow
# abort reason and a repair issue id with the same translation key.
ISSUE_HOME_KEEPER_MISSING = "home_keeper_missing"
ISSUE_HOME_KEEPER_NOT_SET_UP = "home_keeper_not_set_up"
ISSUE_HOME_KEEPER_TOO_OLD = "home_keeper_too_old"
HOME_KEEPER_REASONS = (
    ISSUE_HOME_KEEPER_MISSING,
    ISSUE_HOME_KEEPER_NOT_SET_UP,
    ISSUE_HOME_KEEPER_TOO_OLD,
)

# The entity platforms of the config entry.
PLATFORMS = ["sensor", "todo"]

# PANEL_VERSION is the same string as the manifest version. release.yml checks it,
# and rollup.config.mjs reads it.
PANEL_VERSION = "0.2.0"

# The built bundles are in frontend/dist/ and Home Assistant serves them here.
STATIC_URL = "/home_keeper_library_static"
TAB_JS_FILENAME = "library-tab.js"
CARD_JS_FILENAME = "library-card.js"
TAB_ID = "library"
TAB_ELEMENT = "home-keeper-library-tab"
TAB_ORDER = 50
TAB_HOST_API = 1
CARD_ELEMENT = "home-keeper-library-card"

# The cover HTTP views.
COVER_URL_PREFIX = "/api/home_keeper_library/cover"
COVER_UPLOAD_URL = "/api/home_keeper_library/upload"
COVER_MAX_BYTES = 10 * 1024 * 1024
COVER_MAX_PX = 1200
# The cover files, below `.storage/`. The store file has the name of the domain.
COVERS_DIR = f"{DOMAIN}_covers"
# The first bytes that the upload view reads to identify the image type.
SNIFF_BYTES = 16

# The storage document, ``.storage/home_keeper_library``.
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 1

# The config entry option.
CONF_CURRENCY = "currency"
DEFAULT_CURRENCY = "EUR"

# The CSV import limits.
MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROW_RESULTS = 200

# The Open Library client.
OPENLIBRARY_URL = "https://openlibrary.org"
OPENLIBRARY_COVERS_URL = "https://covers.openlibrary.org"
# Environment variables that replace the 2 Open Library base URLs. Only the
# browser test setup sets them, to point at a fixture server, because Open
# Library is not reachable from the test container.
OPENLIBRARY_URL_ENV = "HOME_KEEPER_LIBRARY_OPENLIBRARY_URL"
OPENLIBRARY_COVERS_URL_ENV = "HOME_KEEPER_LIBRARY_OPENLIBRARY_COVERS_URL"
OPENLIBRARY_TIMEOUT_S = 10
OPENLIBRARY_MIN_INTERVAL_S = 1.0
OPENLIBRARY_MISS_TTL_S = 24 * 60 * 60
LOOKUP_MAX_TRIES = 3
LOOKUP_BACKOFF_S = (60, 300, 1800)

# The overdue loan check interval.
OVERDUE_CHECK_INTERVAL_S = 60 * 60

# The number of titles that the "Reading now" sensor lists.
READING_NOW_MAX_TITLES = 10

# The origin marker that this integration sends to Home Keeper, and that it reads
# back in the events of Home Keeper to stop a loop.
ORIGIN = DOMAIN

# The bus events. Each name is ``home_keeper_library_<noun>_<verb>``. The pure
# builders in events.py make the payloads, and the store fires them.
EVENT_ROOM_ADDED = f"{DOMAIN}_room_added"
EVENT_ROOM_UPDATED = f"{DOMAIN}_room_updated"
EVENT_ROOM_REMOVED = f"{DOMAIN}_room_removed"
EVENT_BOOKCASE_ADDED = f"{DOMAIN}_bookcase_added"
EVENT_BOOKCASE_UPDATED = f"{DOMAIN}_bookcase_updated"
EVENT_BOOKCASE_REMOVED = f"{DOMAIN}_bookcase_removed"
EVENT_SHELF_ADDED = f"{DOMAIN}_shelf_added"
EVENT_SHELF_UPDATED = f"{DOMAIN}_shelf_updated"
EVENT_SHELF_REMOVED = f"{DOMAIN}_shelf_removed"
EVENT_BOOK_ADDED = f"{DOMAIN}_book_added"
EVENT_BOOK_UPDATED = f"{DOMAIN}_book_updated"
EVENT_BOOK_REMOVED = f"{DOMAIN}_book_removed"
EVENT_COPY_ADDED = f"{DOMAIN}_copy_added"
EVENT_COPY_MOVED = f"{DOMAIN}_copy_moved"
EVENT_COPY_UPDATED = f"{DOMAIN}_copy_updated"
EVENT_COPY_REMOVED = f"{DOMAIN}_copy_removed"
EVENT_READING_CHANGED = f"{DOMAIN}_reading_changed"
EVENT_READING_UPDATED = f"{DOMAIN}_reading_updated"
EVENT_BOOK_FINISHED = f"{DOMAIN}_book_finished"
EVENT_LOAN_STARTED = f"{DOMAIN}_loan_started"
EVENT_LOAN_RETURNED = f"{DOMAIN}_loan_returned"
EVENT_LOAN_OVERDUE = f"{DOMAIN}_loan_overdue"
EVENT_LOAN_UPDATED = f"{DOMAIN}_loan_updated"
EVENT_LOAN_REMOVED = f"{DOMAIN}_loan_removed"
EVENT_WISHLIST_ADDED = f"{DOMAIN}_wishlist_added"
EVENT_WISHLIST_REMOVED = f"{DOMAIN}_wishlist_removed"
EVENT_IMPORT_COMPLETED = f"{DOMAIN}_import_completed"
EVENT_PERSON_SETTINGS_UPDATED = f"{DOMAIN}_person_settings_updated"
EVENT_SETTINGS_UPDATED = f"{DOMAIN}_settings_updated"

# The languages of every string table: strings.json, translations/ and
# backend_strings/. The same 16 languages as Home Keeper.
LANGUAGES = (
    "ca",
    "cs",
    "da",
    "de",
    "en",
    "es",
    "fi",
    "fr",
    "it",
    "nb",
    "nl",
    "pl",
    "pt-BR",
    "ru",
    "sv",
    "zh-Hans",
)
