"""Unit tests for the pure parts of a send to Open Library."""

from __future__ import annotations

import ex.openlibrary_contribute as c
import pytest

BOOK = {
    "title": " Ferns of the Rain City ",
    "authors": ["Mara Ellison", "Second Author"],
    "publisher": "Cascade Leaf Press",
    "published": "2024",
    "isbn13": "9781735550127",
    "isbn10": "1735550124",
}


def test_send_fields_always_has_title_and_authors() -> None:
    assert c.send_fields(None) == ["title", "authors"]
    assert c.send_fields([]) == ["title", "authors"]
    assert c.send_fields(["isbn", "publisher", "title", "pages"]) == [
        "title",
        "authors",
        "publisher",
        "isbn",
    ]
    assert c.send_fields(["published"]) == ["title", "authors", "published"]


def test_add_book_form_with_every_field() -> None:
    form = c.add_book_form(BOOK, c.send_fields(list(c.OPTIONAL_SEND_FIELDS)), "__new__")
    assert form == {
        "book_title": "Ferns of the Rain City",
        "authors--0--author--key": "__new__",
        "author_names--0": "Mara Ellison",
        "publisher": "Cascade Leaf Press",
        "publish_date": "2024",
        "id_name": "isbn_13",
        "id_value": "9781735550127",
    }


def test_add_book_form_sends_only_the_selected_fields() -> None:
    form = c.add_book_form(BOOK, ["title", "authors"], "/authors/OL1A")
    assert form == {
        "book_title": "Ferns of the Rain City",
        "authors--0--author--key": "/authors/OL1A",
        "author_names--0": "Mara Ellison",
    }


def test_add_book_form_uses_isbn10_and_skips_empty_values() -> None:
    book = {"title": "T", "authors": [], "publisher": "", "isbn10": "1735550124"}
    form = c.add_book_form(book, ["title", "authors", "publisher", "isbn"], "__new__")
    assert form == {
        "book_title": "T",
        "authors--0--author--key": "__new__",
        "author_names--0": "",
        "id_name": "isbn_10",
        "id_value": "1735550124",
    }
    assert "id_name" not in c.add_book_form({"title": "T"}, ["isbn"], "__new__")


def test_add_book_form_sends_no_empty_title_or_date() -> None:
    book = {"title": None, "authors": ["A"], "published": None, "publisher": None}
    form = c.add_book_form(book, list(c.SEND_FIELDS), "__new__")
    assert form == {
        "book_title": "",
        "authors--0--author--key": "__new__",
        "author_names--0": "A",
    }


@pytest.mark.parametrize(
    ("search", "key"),
    [
        ({"docs": [{"key": "OL7A", "name": "Mara Ellison"}]}, "/authors/OL7A"),
        (
            {"docs": [{"key": "/authors/OL7A", "name": " mara ELLISON "}]},
            "/authors/OL7A",
        ),
        ({"docs": [{"key": "OL7A", "name": "Mara Ellis"}]}, "__new__"),
        (
            {
                "docs": [
                    {"key": "OL7A", "name": "Mara Ellison"},
                    {"key": "OL8A", "name": "Mara Ellison"},
                ]
            },
            "__new__",
        ),
        ({"docs": [{"key": "OL7W", "name": "Mara Ellison"}]}, "__new__"),
        ({"docs": [{"key": 7, "name": "Mara Ellison"}]}, "__new__"),
        ({"docs": [{"key": "OL7A", "name": None}]}, "__new__"),
        ({"docs": ["x", {"key": "OL9A", "name": "Mara Ellison"}]}, "/authors/OL9A"),
        ({"docs": "x"}, "__new__"),
        (None, "__new__"),
        ([], "__new__"),
    ],
)
def test_pick_author_key(search, key) -> None:
    assert c.pick_author_key(search, "Mara Ellison") == key


def test_pick_author_key_with_no_name() -> None:
    search = {"docs": [{"key": "OL7A", "name": ""}]}
    assert c.pick_author_key(search, "  ") == "__new__"


@pytest.mark.parametrize(
    ("status", "location", "result"),
    [
        (303, "/books/OL5M/Ferns/edit?mode=add-work", ("added", "OL5M")),
        (
            303,
            "https://openlibrary.org/books/OL5M/x/edit?mode=add-book",
            ("added", "OL5M"),
        ),
        (302, "/books/OL5M/x/edit?mode=found", ("existing", "OL5M")),
        (301, "/books/OL5M", ("existing", "OL5M")),
        (307, "/books/OL5M/edit", ("existing", "OL5M")),
        (303, "/works/OL5W/edit", ("ambiguous", None)),
        (303, "/books/OL5W/edit?mode=add-work", ("ambiguous", None)),
        (303, None, ("ambiguous", None)),
        (303, "", ("ambiguous", None)),
        (200, "/books/OL5M/edit?mode=add-work", ("ambiguous", None)),
        (304, "/books/OL5M/edit?mode=add-work", ("ambiguous", None)),
    ],
)
def test_parse_add_reply(status, location, result) -> None:
    assert c.parse_add_reply(status, location) == result


@pytest.mark.parametrize(
    ("cookie", "name"),
    [
        ("/people/alex_reads,2026-10-11T00:00:00,abc", "alex_reads"),
        ('"/people/alex_reads,2026,abc"', "alex_reads"),
        ('"/people/alex_reads\\0542026\\054abc"', "alex_reads"),
        ("/people/alex_reads\\0542026", "alex_reads"),
        ('"/people/alex_reads"', None),
        ('/people/alex"reads,2026', 'alex"reads'),
        ("%2Fpeople%2Falex_reads%2C2026%2Cabc", "alex_reads"),
        ("/people/,2026", None),
        ("/people/alex_reads", None),
        ("/other/alex,2026", None),
        ("", None),
        (None, None),
    ],
)
def test_session_username(cookie, name) -> None:
    assert c.session_username(cookie) == name


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("OL5M", "OL5M"),
        (" OL5M ", "OL5M"),
        ("/books/OL5M", "OL5M"),
        ("https://openlibrary.org/books/OL5M/Ferns_of_the_Rain_City", "OL5M"),
        ("https://openlibrary.org/books/OL5M.json", "OL5M"),
        ("https://openlibrary.org/books/OL5M?edition=x", "OL5M"),
        ("https://openlibrary.org/works/OL5W", None),
        ("OL5W", None),
        ("OL5MX", None),
        ("xOL5M", None),
        ("", None),
        (None, None),
        (5, None),
    ],
)
def test_edition_key(text, key) -> None:
    assert c.edition_key(text) == key


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("OL45W", "OL45W"),
        (" OL45W ", "OL45W"),
        ("/works/OL45W", "OL45W"),
        ("https://openlibrary.org/works/OL45W/The_Hobbit", "OL45W"),
        ("https://openlibrary.org/works/OL45W.json", "OL45W"),
        ("https://openlibrary.org/works/OL45W?edition=x", "OL45W"),
        ("https://openlibrary.org/works/OL45W#x", "OL45W"),
        ("https://openlibrary.org/books/OL5M", None),
        ("OL5M", None),
        ("OL45WX", None),
        ("xOL45W", None),
        ("", None),
        (None, None),
        (5, None),
    ],
)
def test_work_key(text, key) -> None:
    assert c.work_key(text) == key
