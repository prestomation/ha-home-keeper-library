"""Build the seed library for the browser tests and the frontend fixture.

Run from the repository root:

    python3 tests/e2e/seed/build_seed.py            # the 2 JSON files
    python3 tests/e2e/seed/build_seed.py --covers   # also draw the cover images

The script writes:

* ``tests/e2e/seed/home_keeper_library.json``: the store document that
  ``ci/e2e-up.sh`` copies to ``.storage/home_keeper_library`` before Home
  Assistant starts.
* ``custom_components/home_keeper_library/frontend/test/fixtures/state.json``:
  the ``get_state`` reply that an admin (Alex) gets for that store. It comes from
  ``projections.project_state``, the same code as the websocket command.
* With ``--covers``: ``tests/e2e/seed/covers/<file>.jpg``, which ``ci/e2e-up.sh``
  copies to ``.storage/home_keeper_library_covers/``. The images need Pillow and
  the DejaVu fonts, so they are made once and committed.

Every record is built by the pure ``models`` builders, so the seed has the shape
that the store writes. The ids are uuid4 values made from a hash of a stable
key, so a new run gives the same ids. The person ids are the ids that Home
Assistant gives to a person named Alex, Sam and Jo (``tests/e2e/global-setup.ts``
makes them).
"""

# The seed tables stay 1 record to a line, so they are easy to read and change.
# ruff: noqa: E501

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import types
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SEED_DIR = Path(__file__).resolve().parent
COMPONENT = ROOT / "custom_components" / "home_keeper_library"
STORE_OUT = SEED_DIR / "home_keeper_library.json"
STATE_OUT = COMPONENT / "frontend" / "test" / "fixtures" / "state.json"
COVERS_OUT = SEED_DIR / "covers"

ALEX, SAM, JO = "alex", "sam", "jo"
PERSONS = [
    {
        "person_id": ALEX,
        "name": "Alex",
        "entity_id": "person.alex",
        "user_id": "u-alex",
    },
    {"person_id": SAM, "name": "Sam", "entity_id": "person.sam", "user_id": "u-sam"},
    {"person_id": JO, "name": "Jo", "entity_id": "person.jo", "user_id": None},
]
NOW = "2026-10-04T18:00:00+00:00"


def _load_pure() -> tuple[types.ModuleType, types.ModuleType]:
    """Load ``models`` and ``projections`` with no Home Assistant (as tests/unit)."""
    pkg = "custom_components.home_keeper_library"
    for name, path in (
        ("custom_components", ROOT / "custom_components"),
        (pkg, COMPONENT),
    ):
        if name not in sys.modules:
            module = types.ModuleType(name)
            module.__path__ = [str(path)]
            sys.modules[name] = module
    loaded = []
    for mod in ("const", "isbn", "models", "projections"):
        full = f"{pkg}.{mod}"
        if full not in sys.modules:
            spec = importlib.util.spec_from_file_location(full, COMPONENT / f"{mod}.py")
            assert spec and spec.loader
            module = importlib.util.module_from_spec(spec)
            sys.modules[full] = module
            spec.loader.exec_module(module)
        loaded.append(sys.modules[full])
    return loaded[2], loaded[3]


def seed_id(kind: str, key: str) -> str:
    """A stable uuid4 hex for a seed record."""
    digest = hashlib.sha256(f"home-keeper-library-seed:{kind}:{key}".encode()).digest()
    return uuid.UUID(bytes=digest[:16], version=4).hex


def isbn13(first12: str) -> str:
    """An ISBN-13 with a correct check digit for the first 12 digits."""
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return first12 + str((10 - total % 10) % 10)


# fmt: off
# ── Places ───────────────────────────────────────────────────────────────────

ROOMS = [("living", "Living room", "living_room"), ("office", "Office", "office")]
BOOKCASES = [
    ("case_a", "living", "Bookcase A", "By the window"),
    ("case_b", "living", "Bookcase B", "Next to the TV"),
    ("tall", "office", "Tall bookcase", ""),
]
SHELVES = [
    ("a1", "case_a", "Shelf 1"),
    ("a2", "case_a", "Shelf 2"),
    ("a3", "case_a", "Shelf 3"),
    ("a4", "case_a", "Shelf 4"),
    ("top", "case_b", "Top"),
    ("oversize", "case_b", "Oversize"),
    ("o1", "tall", "Shelf 1"),
    ("o2", "tall", "Shelf 2"),
    ("o3", "tall", "Shelf 3"),
]

# ── Books ────────────────────────────────────────────────────────────────────
# key: (title, authors, ISBN first 12 digits, publisher, published, pages,
#       subjects, series, tags, cover)
# cover: None, "ol" (an Open Library cover file) or "custom".
LE_GUIN = ["Ursula K. Le Guin"]
SF = ["Science fiction"]
FANTASY = ["Fantasy"]
BOOKS: dict[str, tuple[Any, ...]] = {
    "left_hand": ("The Left Hand of Darkness", LE_GUIN, "978044147812", "Ace Books",
                  "1969", 304, [*SF, "Gender"], ("Hainish Cycle", 4), ["Hugo winner"], "custom"),
    "earthsea": ("A Wizard of Earthsea", LE_GUIN, "978054777374", "Clarion Books",
                 "1968", 183, FANTASY, ("Earthsea", 1), [], "ol"),
    "dispossessed": ("The Dispossessed", LE_GUIN, "978006105488", "Harper Voyager",
                     "1974", 387, [*SF, "Utopias"], ("Hainish Cycle", 6), ["Hugo winner"], "ol"),
    "lathe": ("The Lathe of Heaven", LE_GUIN, "978141655696", "Scribner",
              "1971", 184, SF, None, [], None),
    "atuan": ("The Tombs of Atuan", LE_GUIN, "978141650960", "Atheneum",
              "1970", 180, FANTASY, ("Earthsea", 2), [], "ol"),
    "farthest": ("The Farthest Shore", LE_GUIN, "978141650963", "Atheneum",
                 "1972", 223, FANTASY, ("Earthsea", 3), [], None),
    "tehanu": ("Tehanu", LE_GUIN, "978068931595", "Atheneum",
               "1990", 252, FANTASY, ("Earthsea", 4), ["Nebula winner"], None),
    "always": ("Always Coming Home", LE_GUIN, "978159853705", "Library of America",
               "1985", 523, SF, None, [], None),
    "word_world": ("The Word for World Is Forest", LE_GUIN, "978076532345", "Tor Books",
                   "1972", 189, SF, ("Hainish Cycle", 5), [], None),
    "lavinia": ("Lavinia", LE_GUIN, "978015603368", "Mariner Books",
                "2008", 279, ["Historical fiction"], None, [], None),
    "piranesi": ("Piranesi", ["Susanna Clarke"], "978163557563", "Bloomsbury",
                 "2020", 272, FANTASY, None, ["Book club"], "ol"),
    "hail_mary": ("Project Hail Mary", ["Andy Weir"], "978059313520", "Ballantine Books",
                  "2021", 476, SF, None, [], "ol"),
    "fifth_season": ("The Fifth Season", ["N. K. Jemisin"], "978031622929", "Orbit",
                     "2015", 468, [*FANTASY, "Science fiction"], ("The Broken Earth", 1),
                     ["Hugo winner"], "ol"),
    "dune": ("Dune", ["Frank Herbert"], "978044101359", "Ace Books",
             "1965", 688, SF, ("Dune", 1), [], "ol"),
    "name_wind": ("The Name of the Wind", ["Patrick Rothfuss"], "978075640474", "DAW Books",
                  "2007", 662, FANTASY, ("The Kingkiller Chronicle", 1), [], None),
    "klara": ("Klara and the Sun", ["Kazuo Ishiguro"], "978059331817", "Knopf",
              "2021", 303, SF, None, [], "ol"),
    "grain_rice": ("Every Grain of Rice", ["Fuchsia Dunlop"], "978039308928", "W. W. Norton",
                   "2012", 352, ["Cooking", "Chinese cooking"], None, ["Kitchen"], None),
    "salt_fat": ("Salt, Fat, Acid, Heat", ["Samin Nosrat"], "978147675383", "Simon & Schuster",
                 "2017", 480, ["Cooking"], None, ["Kitchen"], "custom"),
    "food_lab": ("The Food Lab", ["J. Kenji López-Alt"], "978039308108", "W. W. Norton",
                 "2015", 958, ["Cooking", "Science"], None, ["Kitchen"], None),
    "atlas": ("Atlas of Remote Islands", ["Judith Schalansky"], "978014311820", "Penguin Books",
              "2009", 144, ["Travel", "Maps"], None, [], None),
    "geb": ("Gödel, Escher, Bach", ["Douglas Hofstadter"], "978046502656", "Basic Books",
            "1979", 777, ["Mathematics", "Philosophy"], None, [], None),
    "overstory": ("The Overstory", ["Richard Powers"], "978039363552", "W. W. Norton",
                  "2018", 502, ["Literary fiction", "Trees"], None, ["Pulitzer winner"], None),
    "sweetgrass": ("Braiding Sweetgrass", ["Robin Wall Kimmerer"], "978157131356",
                   "Milkweed Editions", "2013", 391, ["Nature", "Botany"], None, [], None),
    "hobbit": ("The Hobbit", ["J. R. R. Tolkien"], "978054792822", "Mariner Books",
               "1937", 310, FANTASY, None, ["Family"], "ol"),
    "wild_things": ("Where the Wild Things Are", ["Maurice Sendak"], "978006025492",
                    "HarperCollins", "1963", 48, ["Picture books"], None, ["Family"], None),
    "chinese_1": ("Integrated Chinese 1", ["Yuehua Liu", "Tao-chung Yao"], "978162291135",
                  "Cheng & Tsui", "2017", 420, ["Chinese language"], ("Integrated Chinese", 1),
                  ["Study"], None),
    "sicp": ("Structure and Interpretation of Computer Programs",
             ["Harold Abelson", "Gerald Jay Sussman"], "978026251087", "MIT Press",
             "1996", 657, ["Computer science"], None, ["Study"], None),
    "pragmatic": ("The Pragmatic Programmer", ["Andrew Hunt", "David Thomas"], "978020161622",
                  "Addison-Wesley", "1999", 352, ["Computer science"], None, [], None),
    "thinking": ("Thinking, Fast and Slow", ["Daniel Kahneman"], "978037453355",
                 "Farrar, Straus and Giroux", "2011", 499, ["Psychology"], None, [], None),
    "sapiens": ("Sapiens", ["Yuval Noah Harari"], "978006231609", "Harper",
                "2011", 443, ["History"], None, [], None),
    "memory_empire": ("A Memory Called Empire", ["Arkady Martine"], "978125018643", "Tor Books",
                      "2019", 462, SF, ("Teixcalaan", 1), ["Hugo winner"], None),
    "station_eleven": ("Station Eleven", ["Emily St. John Mandel"], "978080417244", "Vintage",
                       "2014", 333, ["Literary fiction"], None, [], None),
    "unreal": ("The Unreal and the Real", LE_GUIN, "978161873079", "Saga Press",
               "2012", 320, ["Short stories"], None, [], None),
    "untitled": ("Untitled paperback", [], "978098012345", "", "", None, [], None, [], None),
    "isbn_only": ("9780980123468", [], "978098012346", "", "", None, [], None, [], None),
    "steering": ("Steering the Craft", LE_GUIN, "978054461161", "Mariner Books",
                 "1998", 176, ["Writing"], None, [], None),
    "ministry": ("The Ministry for the Future", ["Kim Stanley Robinson"], "978031630013",
                 "Orbit", "2020", 563, SF, None, [], "custom"),
    "tomorrow": ("Tomorrow, and Tomorrow, and Tomorrow", ["Gabrielle Zevin"], "978059332120",
                 "Knopf", "2022", 401, ["Literary fiction"], None, [], None),
    # Books with no copy: a borrowed book and the wishlist.
    "spinning": ("Spinning Silver", ["Naomi Novik"], "978039958103", "Del Rey",
                 "2018", 466, FANTASY, None, [], None),
    "sea_tranquility": ("Sea of Tranquility", ["Emily St. John Mandel"], "978059332144",
                        "Knopf", "2022", 255, SF, None, [], None),
    "other_wind": ("The Other Wind", LE_GUIN, "978054777376", "Clarion Books",
                   "2001", 246, FANTASY, ("Earthsea", 6), [], None),
    "obelisk": ("The Obelisk Gate", ["N. K. Jemisin"], "978031622926", "Orbit",
                "2016", 448, FANTASY, ("The Broken Earth", 2), [], None),
    "fish_rice": ("Land of Fish and Rice", ["Fuchsia Dunlop"], "978039325438", "W. W. Norton",
                  "2016", 368, ["Cooking", "Chinese cooking"], None, [], None),
    "chinese_2": ("Integrated Chinese 2", ["Yuehua Liu", "Tao-chung Yao"], "978162291140",
                  "Cheng & Tsui", "2018", 412, ["Chinese language"], ("Integrated Chinese", 2),
                  [], None),
}
NEEDS_DETAILS = {"untitled", "isbn_only"}
SHARED_NOTES = {
    "left_hand": "Book club pick, **Oct 2026**. Sam has the map of Gethen bookmarked on page 6.",
    "food_lab": "The *pancake* recipe is on page 102.\n\n- Sticky notes from Jo\n- Do not lend",
    "hobbit": "First edition of the family. Keep it out of the sun.",
}

# (book, shelf or None, format, condition, acquired, acquired_from, price, value,
#  signed, first_edition, note)
COPIES = [
    ("left_hand", "a2", "paperback", "good", "2019-05-04", "Elliott Bay Book Co.", 7.99, 45,
     True, False, "Signed at a reading in Portland."),
    ("left_hand", "o1", "hardcover", "fine", "2023-12-24", "Gift from Jo", None, None,
     False, False, ""),
    ("earthsea", "a2", "paperback", "fair", "2008-07-01", "", 6.5, None, False, False, ""),
    ("dispossessed", "a2", "paperback", "good", "2015-02-10", "Powell's Books", 9.99, None,
     False, False, ""),
    ("lathe", "a2", "paperback", "good", "2015-02-10", "Powell's Books", 8.99, None,
     False, False, ""),
    ("atuan", "a2", "paperback", "good", "2008-07-01", "", 6.5, None, False, False, ""),
    ("farthest", "a2", "paperback", "good", "2008-07-01", "", 6.5, None, False, False, ""),
    ("tehanu", "a2", "paperback", "good", "2009-01-15", "", 7.5, None, False, False, ""),
    ("always", "a3", "hardcover", "new", "2019-09-01", "Library of America", 45, 45,
     False, False, ""),
    ("word_world", "a3", "paperback", "good", "2016-03-03", "", 8, None, False, False, ""),
    ("lavinia", "a3", "paperback", "good", "2010-05-05", "", 12, None, False, False, ""),
    ("piranesi", "a1", "hardcover", "fine", "2020-09-15", "Elliott Bay Book Co.", 27,
     None, False, True, ""),
    ("hail_mary", "a1", "hardcover", "fine", "2021-05-04", "Amazon", 28.99, None,
     False, False, ""),
    ("fifth_season", "a1", "paperback", "good", "2018-11-02", "", 15.99, None,
     False, False, ""),
    ("dune", "a1", "paperback", "fair", "2004-06-01", "Garage sale", 1,
     None, False, False, "Spine is cracked."),
    ("name_wind", "a1", "paperback", "good", "2012-08-08", "", 9.99, None, False, False, ""),
    ("klara", "a1", "hardcover", "fine", "2021-03-02", "Elliott Bay Book Co.", 28, None,
     False, False, ""),
    ("grain_rice", "oversize", "hardcover", "good", "2014-01-20", "", 35, None,
     False, False, ""),
    ("salt_fat", "oversize", "hardcover", "fine", "2018-04-01", "", 35, None, False, False, ""),
    ("food_lab", "oversize", "hardcover", "good", "2016-12-25", "Gift from Sam", 49.95, 30,
     False, False, ""),
    ("atlas", "oversize", "hardcover", "fine", "2011-06-06", "", 25, None, False, False, ""),
    ("geb", "o1", "paperback", "fair", "2001-09-01", "University Book Store", 22, None,
     False, False, ""),
    ("overstory", "top", "paperback", "good", "2019-10-10", "", 18, None, False, False, ""),
    ("sweetgrass", "top", "paperback", "good", "2021-02-14", "", 20, None, False, False, ""),
    ("hobbit", "top", "hardcover", "good", "1985-12-25", "Inherited", None, 120,
     False, True, ""),
    ("wild_things", "top", "hardcover", "fair", "2016-04-01", "", 17.99, None,
     False, False, ""),
    ("chinese_1", "o2", "paperback", "good", "2024-01-08", "Cheng & Tsui", 59.99, None,
     False, False, ""),
    ("sicp", "o2", "hardcover", "good", "2003-09-01", "University Book Store", 75, 60,
     False, False, ""),
    ("pragmatic", "o2", "paperback", "good", "2005-02-02", "", 39.99, None, False, False, ""),
    ("thinking", "o3", "paperback", "good", "2013-07-07", "", 17, None, False, False, ""),
    ("sapiens", "o3", "paperback", "good", "2017-08-08", "", 18.99, None, False, False, ""),
    ("memory_empire", "a4", "paperback", "fine", "2020-04-04", "", 17.99, None,
     False, False, ""),
    ("station_eleven", "a4", "paperback", "good", "2015-05-05", "", 15.95, None,
     False, False, ""),
    ("unreal", "a4", "hardcover", "fine", "2013-01-01", "", 30, None, False, False, ""),
    ("untitled", "a3", "paperback", None, None, "", None, None, False, False, ""),
    ("isbn_only", None, "paperback", None, None, "", None, None, False, False, ""),
    ("steering", None, "paperback", "good", "2024-05-05", "", 16, None, False, False, ""),
    ("ministry", "a4", "hardcover", "fine", "2020-10-06", "", 28, None, False, False, ""),
    ("tomorrow", "a4", "hardcover", "fine", "2022-07-05", "", 28, None, False, False, ""),
]

# (book, person, status, rating, page, started, finished, read_count, private notes,
#  updated_at)
READING = [
    ("left_hand", ALEX, "read", 4, None, "2025-02-01", "2025-03-02", 2,
     "Reread before the club.", "2026-09-20T10:00:00+00:00"),
    ("left_hand", SAM, "reading", None, 112, "2026-09-01", None, 0, "",
     "2026-10-03T19:30:00+00:00"),
    ("earthsea", ALEX, "read", 5, None, None, "2026-02-11", 1, "", "2026-02-11T21:00:00+00:00"),
    ("earthsea", JO, "read", 4, None, None, "2026-08-30", 1, "", "2026-08-30T19:00:00+00:00"),
    ("dispossessed", ALEX, "read", 5, None, None, "2026-04-20", 1, "",
     "2026-04-20T22:00:00+00:00"),
    ("lathe", ALEX, "want", None, None, None, None, 0, "", "2026-05-01T10:00:00+00:00"),
    ("atuan", JO, "reading", None, 40, "2026-09-28", None, 0, "", "2026-10-02T18:00:00+00:00"),
    ("atuan", ALEX, "want", None, None, None, None, 0, "", "2026-08-31T10:00:00+00:00"),
    ("word_world", SAM, "read", 3, None, None, "2026-06-01", 1, "", "2026-06-01T20:00:00+00:00"),
    ("piranesi", ALEX, "read", 5, None, "2026-09-20", "2026-10-03", 1, "",
     "2026-10-03T21:45:00+00:00"),
    ("piranesi", SAM, "want", None, None, None, None, 0, "", "2026-10-04T08:00:00+00:00"),
    ("hail_mary", ALEX, "reading", None, 210, "2026-09-25", None, 0, "",
     "2026-10-04T07:10:00+00:00"),
    ("hail_mary", SAM, "want", None, None, None, None, 0, "", "2026-09-26T10:00:00+00:00"),
    ("fifth_season", ALEX, "read", 5, None, None, "2026-05-14", 1, "",
     "2026-05-14T22:00:00+00:00"),
    ("dune", ALEX, "read", 4, None, None, "2024-12-01", 1, "", "2024-12-01T22:00:00+00:00"),
    ("dune", JO, "dnf", None, 140, None, None, 0, "", "2026-07-12T10:00:00+00:00"),
    ("klara", SAM, "read", 4, None, None, "2026-09-28", 1, "", "2026-09-28T21:00:00+00:00"),
    ("grain_rice", ALEX, "reading", None, 80, "2026-08-01", None, 0, "",
     "2026-09-12T18:00:00+00:00"),
    ("geb", ALEX, "dnf", 3, 320, None, None, 0, "Try again one day.",
     "2025-11-11T10:00:00+00:00"),
    ("overstory", SAM, "read", 5, None, None, "2026-03-03", 1, "", "2026-03-03T21:00:00+00:00"),
    ("hobbit", JO, "read", 5, None, None, "2026-07-07", 1, "", "2026-07-07T19:00:00+00:00"),
    ("hobbit", ALEX, "read", None, None, None, "2019-01-01", 1, "", "2019-01-01T10:00:00+00:00"),
    ("wild_things", JO, "read", None, None, None, "2026-01-02", 12, "",
     "2026-01-02T19:00:00+00:00"),
    ("chinese_1", ALEX, "reading", None, 150, "2026-01-08", None, 0, "",
     "2026-09-30T18:00:00+00:00"),
    ("pragmatic", ALEX, "read", 4, None, None, "2026-07-20", 1, "", "2026-07-20T22:00:00+00:00"),
    ("sapiens", SAM, "dnf", None, 120, None, None, 0, "", "2026-04-04T10:00:00+00:00"),
    ("memory_empire", ALEX, "read", 4, None, None, "2026-08-08", 1, "",
     "2026-08-08T22:00:00+00:00"),
    ("ministry", ALEX, "reading", None, 300, "2026-09-01", None, 0, "",
     "2026-09-29T21:00:00+00:00"),
    ("tomorrow", SAM, "reading", None, 20, "2026-10-01", None, 0, "",
     "2026-10-01T22:00:00+00:00"),
    ("spinning", ALEX, "reading", None, 64, "2026-09-21", None, 0, "",
     "2026-10-01T20:00:00+00:00"),
    ("sea_tranquility", SAM, "want", None, None, None, None, 0, "",
     "2026-09-25T10:00:00+00:00"),
]

# (key, direction, book, copy index of the book or None, party, person, format,
#  started, due, returned, note)
LOANS = [
    ("priya_piranesi", "out", "piranesi", 0, "Priya", None, None, "2026-08-12",
     "2026-09-13", None, ""),
    ("priya_left", "out", "left_hand", 1, "Priya", None, None, "2026-09-12", "2026-10-13",
     None, ""),
    ("club_ministry", "out", "ministry", 0, "Book club", None, None, "2026-10-01", None,
     None, "For the November meeting."),
    ("friend_dispossessed", "out", "dispossessed", 0, "Sam's friend Lee", None, None,
     "2026-05-01", "2026-06-01", "2026-05-28", ""),
    ("spl_spinning", "in", "spinning", None, "Seattle Public Library", ALEX, "paperback",
     "2026-09-20", "2026-10-11", None, ""),
    ("spl_sea", "in", "sea_tranquility", None, "Seattle Public Library", SAM, "ebook",
     "2026-09-25", "2026-10-25", None, ""),
]

# (book, person, buy, added_at)
WISHLIST = [
    ("other_wind", ALEX, True, "2026-09-02T10:00:00+00:00"),
    ("obelisk", ALEX, False, "2026-08-15T10:00:00+00:00"),
    ("fish_rice", SAM, True, "2026-09-18T10:00:00+00:00"),
    ("chinese_2", ALEX, False, "2026-06-01T10:00:00+00:00"),
]

PEOPLE = {
    ALEX: {"share_reading": True, "wishlist_todo": "todo.alex_books", "yearly_goal": 24},
    SAM: {"share_reading": True, "wishlist_todo": None, "yearly_goal": 12},
    JO: {"share_reading": True, "wishlist_todo": None, "yearly_goal": None},
}

# The Open Library cover ids of the books with an "ol" cover.
OL_COVER_IDS = {
    "earthsea": 12623421,
    "dispossessed": 8231862,
    "atuan": 12623433,
    "piranesi": 10307413,
    "hail_mary": 11200092,
    "fifth_season": 8296560,
    "dune": 11481354,
    "klara": 10958358,
    "hobbit": 12003830,
}

# fmt: on


def cover_file(key: str) -> str:
    """The stored cover file name of a book: ``<book_id>-<token>.jpg``."""
    token = hashlib.sha256(f"cover:{key}".encode()).hexdigest()[:8]
    return f"{seed_id('book', key)}-{token}.jpg"


def build_store(models: types.ModuleType) -> dict[str, Any]:
    """The store document."""
    state = models.empty_state()
    for order, (key, name, area) in enumerate(ROOMS, 1):
        room = models.build_room({"name": name, "area_id": area}, order=order)
        room["id"] = seed_id("room", key)
        state["rooms"][room["id"]] = room
    for order, (key, room, name, note) in enumerate(BOOKCASES, 1):
        case = models.build_bookcase(
            {"room_id": seed_id("room", room), "name": name, "note": note}, order=order
        )
        case["id"] = seed_id("bookcase", key)
        state["bookcases"][case["id"]] = case
    orders: dict[str, int] = {}
    for key, case, name in SHELVES:
        orders[case] = orders.get(case, 0) + 1
        shelf = models.build_shelf(
            {"bookcase_id": seed_id("bookcase", case), "name": name}, order=orders[case]
        )
        shelf["id"] = seed_id("shelf", key)
        state["shelves"][shelf["id"]] = shelf
    for n, (key, row) in enumerate(BOOKS.items()):
        (
            title,
            authors,
            isbn,
            publisher,
            published,
            pages,
            subjects,
            series,
            tags,
            cov,
        ) = row
        created = f"2026-0{1 + n // 12}-{1 + n % 12 * 2:02d}T10:00:00+00:00"
        data: dict[str, Any] = {
            "title": title,
            "authors": authors,
            "isbn13": isbn13(isbn),
            "publisher": publisher,
            "published": published,
            "pages": pages,
            "language": "en" if authors else None,
            "subjects": subjects,
            "series": {"name": series[0], "number": series[1]} if series else None,
            "tags": tags,
            "shared_notes": SHARED_NOTES.get(key, ""),
        }
        book = models.build_book(data, now=created)
        book["id"] = seed_id("book", key)
        book["updated_at"] = created
        book["needs_details"] = key in NEEDS_DETAILS
        if cov:
            book["cover"] = {
                "kind": "custom" if cov == "custom" else "openlibrary",
                "file": cover_file(key),
            }
        if key in OL_COVER_IDS:
            work = int(seed_id("work", key)[:6], 16)
            book["openlibrary"] = {
                "edition_key": f"OL{work}M",
                "work_key": f"/works/OL{work}W",
                "cover_id": OL_COVER_IDS[key],
            }
        state["books"][book["id"]] = book
    copy_ids: dict[str, list[str]] = {}
    for row in COPIES:
        book, shelf, fmt, cond, acquired, source, price, value, signed, first, note = (
            row
        )
        copy = models.build_copy(
            {
                "book_id": seed_id("book", book),
                "shelf_id": seed_id("shelf", shelf) if shelf else None,
                "format": fmt,
                "condition": cond,
                "acquired": acquired,
                "acquired_from": source,
                "price": price,
                "value": value,
                "signed": signed,
                "first_edition": first,
                "note": note,
            },
            now=state["books"][seed_id("book", book)]["created_at"],
        )
        index = len(copy_ids.setdefault(book, []))
        copy["id"] = seed_id("copy", f"{book}:{index}")
        copy_ids[book].append(copy["id"])
        state["copies"][copy["id"]] = copy
    for (
        book,
        person,
        status,
        rating,
        page,
        started,
        finished,
        count,
        notes,
        at,
    ) in READING:
        row = models.empty_reading(now=at)
        row.update(
            {
                "status": status,
                "rating": rating,
                "page": page,
                "started": started,
                "finished": finished,
                "read_count": count,
                "private_notes": notes,
            }
        )
        state["reading"].setdefault(person, {})[seed_id("book", book)] = row
    for (
        key,
        direction,
        book,
        index,
        party,
        person,
        fmt,
        started,
        due,
        back,
        note,
    ) in LOANS:
        loan = models.build_loan(
            {
                "direction": direction,
                "book_id": seed_id("book", book),
                "copy_id": copy_ids[book][index] if index is not None else None,
                "party": party,
                "person_id": person,
                "format": fmt,
                "started": started,
                "due": due,
                "note": note,
            },
            today=started,
        )
        loan["id"] = seed_id("loan", key)
        loan["returned"] = back
        # The loan sync at setup finds no Home Keeper task with this id, so it
        # adds a new task (loan_tasks.plan_reconcile) and stores its id.
        if due and not back:
            loan["hk_task_id"] = seed_id("task", key)
        state["loans"][loan["id"]] = loan
    for book, person, buy, at in WISHLIST:
        state["books"][seed_id("book", book)]["wishlist"] = models.build_wishlist(
            person, buy=buy, now=at
        )
    state["people"] = {pid: dict(settings) for pid, settings in PEOPLE.items()}
    return state


def project(projections: types.ModuleType, state: dict[str, Any]) -> dict[str, Any]:
    """The ``get_state`` reply of Alex, an admin."""
    return projections.project_state(
        state,
        persons=PERSONS,
        viewer=ALEX,
        is_admin=True,
        viewer_name="Alex",
        currency="EUR",
        tab=True,
        revision=1,
    )


def draw_covers(state: dict[str, Any]) -> None:
    """Draw a simple cover image for each book with a cover file."""
    from PIL import Image, ImageDraw, ImageFont

    fonts = Path("/usr/share/fonts/truetype/dejavu")
    palette = [
        ("#16324f", "#f4d35e"),
        ("#7a1f2b", "#f6e7d8"),
        ("#204e4a", "#e9d985"),
        ("#3d2c52", "#f2c6de"),
        ("#8c3b0b", "#fff1d6"),
        ("#0f4c5c", "#ffe8a3"),
        ("#2f2f2f", "#e4572e"),
        ("#5b7553", "#f5f1e3"),
        ("#123c69", "#edc7b7"),
        ("#6a0572", "#f9e2ae"),
        ("#264653", "#e9c46a"),
        ("#9b2226", "#fefae0"),
    ]
    COVERS_OUT.mkdir(parents=True, exist_ok=True)
    for old in COVERS_OUT.glob("*.jpg"):
        old.unlink()
    for n, book in enumerate(sorted(state["books"].values(), key=lambda b: b["id"])):
        file = book["cover"]["file"]
        if not file:
            continue
        bg, ink = palette[n % len(palette)]
        img = Image.new("RGB", (400, 600), bg)
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, 18, 600), fill=ink)
        draw.rectangle((40, 330, 360, 334), fill=ink)
        title_font = ImageFont.truetype(str(fonts / "DejaVuSerif-Bold.ttf"), 40)
        words, lines, line = book["title"].split(), [], ""
        for word in words:
            test = f"{line} {word}".strip()
            if draw.textlength(test, font=title_font) > 310 and line:
                lines.append(line)
                line = word
            else:
                line = test
        lines.append(line)
        y = 300 - 50 * len(lines)
        for text in lines:
            draw.text((40, y), text, font=title_font, fill=ink)
            y += 50
        author_font = ImageFont.truetype(str(fonts / "DejaVuSans.ttf"), 22)
        draw.text(
            (40, 360), ", ".join(book["authors"]).upper(), font=author_font, fill=ink
        )
        img.save(COVERS_OUT / file, "JPEG", quality=82)


def main() -> None:
    models, projections = _load_pure()
    state = build_store(models)
    document = {
        "version": 1,
        "minor_version": 1,
        "key": "home_keeper_library",
        "data": state,
    }
    STORE_OUT.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n")
    STATE_OUT.write_text(
        json.dumps(project(projections, state), indent=1, ensure_ascii=False) + "\n"
    )
    if "--covers" in sys.argv:
        draw_covers(state)
    print(
        f"{len(state['books'])} books, {len(state['copies'])} copies, "
        f"{len(state['loans'])} loans"
    )


if __name__ == "__main__":
    main()
