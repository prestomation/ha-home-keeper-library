"""Unit tests for the pure Open Library parser."""

from __future__ import annotations

import json
from pathlib import Path

import ex.openlibrary as ol
import pytest

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "openlibrary"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_edition_with_work_and_author() -> None:
    edition = _load("edition_9780441478125.json")
    work = _load("work_OL59863W.json")
    author = _load("author_OL26320A.json")
    assert ol.work_key(edition) == "OL59863W"
    assert ol.author_keys(edition, work) == ["OL26320A"]
    draft = ol.parse_edition(edition, work, [author])
    assert draft == {
        "title": "The Left Hand of Darkness",
        "subtitle": "",
        "authors": ["Ursula K. Le Guin"],
        "isbn13": "9780441478125",
        "isbn10": "0441478123",
        "publisher": "Ace Books",
        "published": "1987",
        "pages": 304,
        "language": "en",
        "subjects": ["Science fiction", "Gender identity -- Fiction", "Hainish"],
        "series": {"name": "Hainish Cycle", "number": "4"},
        "description": (
            "A groundbreaking work of science fiction about an envoy on the planet "
            "Gethen."
        ),
        "openlibrary": {
            "edition_key": "OL7254097M",
            "work_key": "OL59863W",
            "cover_id": 8231856,
        },
    }


def test_parse_minimal_edition() -> None:
    draft = ol.parse_edition(_load("edition_minimal.json"))
    assert draft["authors"] == ["Jane Doe"]
    assert draft["published"] == "n.d."
    assert draft["description"] == "A short pamphlet."
    assert draft["series"] == {"name": "Pamphlets", "number": "3"}
    assert draft["isbn13"] == "9780000000002"
    assert draft["isbn10"] == "0000000000"
    assert draft["pages"] is None and draft["language"] is None
    assert draft["openlibrary"] == {
        "edition_key": "OL1M",
        "work_key": None,
        "cover_id": None,
    }


def test_edition_falls_back_to_the_work() -> None:
    work = _load("work_OL59863W.json")
    draft = ol.parse_edition({"works": [{"key": "/works/OL59863W"}]}, work, [])
    assert draft["title"] == "The Left Hand of Darkness"
    assert draft["subjects"] == ["Science fiction", "Androgyny", "Fiction"]
    assert draft["openlibrary"]["cover_id"] == 8231856
    assert ol.author_keys({}, work) == ["OL26320A"]
    assert ol.author_keys({}, None) == []
    assert ol.author_keys({"authors": [{"key": "/works/OL1W"}, "x"]}, None) == []
    draft = ol.parse_edition({"key": "/works/OL5W"}, {"key": "/works/OL9W"})
    assert draft["openlibrary"]["work_key"] == "OL9W"
    assert draft["openlibrary"]["edition_key"] is None


def test_parser_ignores_wrong_types() -> None:
    draft = ol.parse_edition(
        {
            "title": 5,
            "number_of_pages": True,
            "covers": [-1],
            "publishers": "x",
            "languages": [],
            "subjects": [1, "A", "A"],
            "isbn_13": ["bad"],
            "description": {"value": 3},
        }
    )
    assert draft["title"] == "" and draft["pages"] is None
    assert draft["openlibrary"]["cover_id"] is None
    assert draft["publisher"] == "" and draft["subjects"] == ["A"]
    assert draft["isbn13"] is None and draft["description"] == ""
    assert draft["language"] is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (["Dune Chronicles (1)"], {"name": "Dune Chronicles", "number": "1"}),
        (["Earthsea", "#2"], {"name": "Earthsea", "number": "2"}),
        (["Earthsea", "2.5"], {"name": "Earthsea", "number": "2.5"}),
        (["Discworld"], {"name": "Discworld", "number": None}),
        (["Saga", "vol"], {"name": "Saga", "number": None}),
        ([], None),
        ("x", None),
    ],
)
def test_series(raw: object, expected: object) -> None:
    assert ol.parse_edition({"series": raw})["series"] == expected


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ([{"key": "/languages/eng"}], "en"),
        ([{"key": "/languages/ger"}], "de"),
        ([{"key": "/languages/xyz"}], "xyz"),
        (["fre"], "fr"),
        ([{"key": ""}], None),
        (None, None),
    ],
)
def test_language(value: object, code: str | None) -> None:
    assert ol.parse_edition({"languages": value})["language"] == code


def test_year_from_publish_date() -> None:
    assert ol.parse_edition({"publish_date": "1965"})["published"] == "1965"
    assert ol.parse_edition({"publish_date": "Oct 2003"})["published"] == "2003"
    assert ol.parse_edition({"publish_date": "1499"})["published"] == "1499"
    assert ol.parse_edition({})["published"] == ""


def test_parse_search() -> None:
    drafts = ol.parse_search(_load("search_dune.json"))
    assert len(drafts) == 2
    dune = drafts[0]
    assert dune["title"] == "Dune" and dune["authors"] == ["Frank Herbert"]
    assert dune["isbn13"] == "9780340960196" and dune["isbn10"] == "0340960191"
    assert dune["published"] == "1965" and dune["pages"] == 612
    assert dune["language"] == "en" and dune["publisher"] == "Chilton Books"
    assert dune["openlibrary"] == {
        "edition_key": "OL26242482M",
        "work_key": "OL893415W",
        "cover_id": 11481354,
    }
    assert drafts[1]["isbn13"] is None and drafts[1]["openlibrary"]["cover_id"] is None
    assert ol.parse_search(_load("search_empty.json")) == []
    assert ol.parse_search({"docs": "x"}) == []
    assert ol.parse_search(None) == []
    assert ol.parse_search({"docs": ["x", {}]})[0]["title"] == ""


def test_search_prefers_a_978_isbn() -> None:
    doc = {"isbn": ["9791032305690", "0441478123"]}
    assert ol.parse_search_doc(doc)["isbn13"] == "9780441478125"
    assert ol.parse_search_doc({"isbn": ["9791032305690"]})["isbn13"] == (
        "9791032305690"
    )


def test_best_match() -> None:
    drafts = ol.parse_search(_load("search_dune.json"))
    assert ol.best_match(drafts, "Dune", ["Herbert, Frank"])["title"] == "Dune"
    assert ol.best_match(drafts, "Dune Messiah", ["F. Herbert"])["title"] == (
        "Dune Messiah"
    )
    assert ol.best_match(drafts, "Dune: Deluxe", [])["title"] == "Dune"
    assert ol.best_match(drafts, "Dune", ["Brian Herbert Jr"]) is None
    assert ol.best_match(drafts, "Emma", []) is None


def test_urls() -> None:
    base = "https://openlibrary.org"
    assert ol.edition_url(base, "9780441478125") == (
        "https://openlibrary.org/isbn/9780441478125.json"
    )
    assert ol.work_url(base, "OL1W") == "https://openlibrary.org/works/OL1W.json"
    assert ol.author_url(base, "OL1A") == "https://openlibrary.org/authors/OL1A.json"
    assert ol.cover_image_url("https://covers.openlibrary.org", 5) == (
        "https://covers.openlibrary.org/b/id/5-L.jpg?default=false"
    )
