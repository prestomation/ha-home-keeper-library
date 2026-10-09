"""Unit tests for the pure ISBN helpers."""

from __future__ import annotations

import ex.isbn as isbn
import pytest
from hypothesis import given
from hypothesis import strategies as st


def test_clean_keeps_digits_and_x() -> None:
    assert isbn.clean('="0-441-47812-3"') == "0441478123"
    assert isbn.clean("080442957x") == "080442957X"
    assert isbn.clean(9780441478125) == "9780441478125"
    assert isbn.clean(None) == ""
    assert isbn.clean(True) == ""
    assert isbn.clean(["978"]) == ""


def test_only_ascii_digits_count() -> None:
    # "²" and "٣" pass str.isdigit, but they are not ISBN digits.
    assert isbn.clean("97803064061²7") == "978030640617"
    assert isbn.clean("٣") == ""
    assert isbn.try_normalize("97803064061²7") == (None, None)
    assert not isbn.is_valid_isbn13("97803064061²7"[:12] + "7")
    assert not isbn.is_valid_isbn13("٣" * 13)
    assert not isbn.is_valid_isbn10("٣" * 9 + "X")
    assert not isbn.is_isbn_barcode("97803064061²7")


def test_check_digits() -> None:
    assert isbn.isbn13_check_digit("978044147812") == "5"
    assert isbn.isbn13_check_digit("979103230569") == "0"
    assert isbn.isbn10_check_char("044147812") == "3"
    assert isbn.isbn10_check_char("080442957") == "X"
    assert isbn.isbn10_check_char("012345678") == "9"
    # A sum that is a multiple of 11 gives 0.
    assert isbn.isbn10_check_char("000000000") == "0"
    assert isbn.isbn13_check_digit("000000000000") == "0"


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("9780441478125", True),
        ("9780441478124", False),
        ("978044147812", False),
        ("97804414781255", False),
        ("978044147812X", False),
    ],
)
def test_is_valid_isbn13(value: str, valid: bool) -> None:
    assert isbn.is_valid_isbn13(value) is valid


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("0441478123", True),
        ("080442957X", True),
        ("0441478124", False),
        ("044147812", False),
        ("X441478123", False),
        ("04414781233", False),
    ],
)
def test_is_valid_isbn10(value: str, valid: bool) -> None:
    assert isbn.is_valid_isbn10(value) is valid


def test_conversions() -> None:
    assert isbn.to_isbn13("0441478123") == "9780441478125"
    assert isbn.to_isbn10("9780441478125") == "0441478123"
    assert isbn.to_isbn10("9780804429573") == "080442957X"
    assert isbn.to_isbn10("9791032305690") is None


def test_normalize() -> None:
    assert isbn.normalize("978-0-441-47812-5") == ("9780441478125", "0441478123")
    assert isbn.normalize("0441478123") == ("9780441478125", "0441478123")
    assert isbn.normalize("9791032305690") == ("9791032305690", None)
    issn = "977123456700" + isbn.isbn13_check_digit("977123456700")
    assert isbn.is_valid_isbn13(issn)
    for bad in ("9780441478124", "0441478124", "123", "", issn):
        with pytest.raises(isbn.IsbnError):
            isbn.normalize(bad)


def test_try_normalize() -> None:
    assert isbn.try_normalize("0441478123") == ("9780441478125", "0441478123")
    assert isbn.try_normalize("nope") == (None, None)


def test_is_isbn_barcode() -> None:
    assert isbn.is_isbn_barcode("9780441478125")
    assert isbn.is_isbn_barcode("9791032305690")
    assert not isbn.is_isbn_barcode("4006381333931")  # an EAN that is not a book
    assert not isbn.is_isbn_barcode("9780441478124")
    assert not isbn.is_isbn_barcode("0441478123")
    issn = "977123456700" + isbn.isbn13_check_digit("977123456700")
    assert not isbn.is_isbn_barcode(issn)


_DIGITS = st.text(alphabet="0123456789", min_size=9, max_size=9)


@given(_DIGITS)
def test_isbn10_round_trips_through_isbn13(first9: str) -> None:
    isbn10 = first9 + isbn.isbn10_check_char(first9)
    assert isbn.is_valid_isbn10(isbn10)
    isbn13 = isbn.to_isbn13(isbn10)
    assert isbn.is_valid_isbn13(isbn13)
    assert isbn.to_isbn10(isbn13) == isbn10
    assert isbn.normalize(isbn10) == (isbn13, isbn10)
    assert isbn.normalize("-".join(isbn10)) == (isbn13, isbn10)


@given(_DIGITS, st.integers(min_value=0, max_value=8))
def test_one_changed_digit_fails_the_check(first9: str, position: int) -> None:
    isbn10 = first9 + isbn.isbn10_check_char(first9)
    digit = int(isbn10[position])
    changed = isbn10[:position] + str((digit + 1) % 10) + isbn10[position + 1 :]
    assert not isbn.is_valid_isbn10(changed)
    isbn13 = isbn.to_isbn13(isbn10)
    pos13 = position + 3
    digit13 = int(isbn13[pos13])
    changed13 = isbn13[:pos13] + str((digit13 + 1) % 10) + isbn13[pos13 + 1 :]
    assert not isbn.is_valid_isbn13(changed13)
