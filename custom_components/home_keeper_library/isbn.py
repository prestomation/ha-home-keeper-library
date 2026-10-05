"""Pure ISBN helpers: clean, validate and convert ISBN-10 and ISBN-13 values.

An ISBN-13 has 13 digits and a check digit that uses the weights 1 and 3. An
ISBN-10 has 9 digits and a check character (0 to 9, or ``X`` for 10) that uses
the weights 10 down to 1. An ISBN-10 converts to the ISBN-13 with the ``978``
prefix and a new check digit. Only an ISBN-13 with the ``978`` prefix converts
back to an ISBN-10.

This module imports no Home Assistant code.
"""

from __future__ import annotations

ISBN13_PREFIXES = ("978", "979")
ISBN10_PREFIX = "978"


class IsbnError(ValueError):
    """The value is not a valid ISBN."""


def clean(raw: object) -> str:
    """Return *raw* with only its digits and an upper-case ``X``.

    Spaces, hyphens, quotes and an ``=`` (as in a Goodreads CSV cell) are removed.
    A value that is not a string gives an empty string.
    """
    if isinstance(raw, int) and not isinstance(raw, bool):
        raw = str(raw)
    if not isinstance(raw, str):
        return ""
    return "".join(ch for ch in raw.upper() if ch.isdigit() or ch == "X")


def isbn13_check_digit(first12: str) -> str:
    """The check digit for the 12 digits *first12*."""
    total = sum(int(ch) * (3 if index % 2 else 1) for index, ch in enumerate(first12))
    return str((10 - total % 10) % 10)


def isbn10_check_char(first9: str) -> str:
    """The check character (``0`` to ``9`` or ``X``) for the 9 digits *first9*."""
    total = sum(int(ch) * (10 - index) for index, ch in enumerate(first9))
    check = (11 - total % 11) % 11
    return "X" if check == 10 else str(check)


def is_valid_isbn13(value: str) -> bool:
    """Whether *value* is 13 digits with a correct check digit."""
    if len(value) != 13 or not value.isdigit():
        return False
    return isbn13_check_digit(value[:12]) == value[12]


def is_valid_isbn10(value: str) -> bool:
    """Whether *value* is 9 digits and a correct check character."""
    if len(value) != 10 or not value[:9].isdigit():
        return False
    return isbn10_check_char(value[:9]) == value[9]


def to_isbn13(isbn10: str) -> str:
    """The ISBN-13 for a valid ISBN-10."""
    first12 = ISBN10_PREFIX + isbn10[:9]
    return first12 + isbn13_check_digit(first12)


def to_isbn10(isbn13: str) -> str | None:
    """The ISBN-10 for a valid ISBN-13, or None if its prefix is not ``978``."""
    if not isbn13.startswith(ISBN10_PREFIX):
        return None
    first9 = isbn13[3:12]
    return first9 + isbn10_check_char(first9)


def normalize(raw: object) -> tuple[str, str | None]:
    """Return ``(isbn13, isbn10)`` for an ISBN-10 or an ISBN-13.

    Raise :class:`IsbnError` if *raw* is not a valid ISBN. ``isbn10`` is None for
    an ISBN-13 that has no ISBN-10 form.
    """
    value = clean(raw)
    if len(value) == 13:
        if not is_valid_isbn13(value) or not value.startswith(ISBN13_PREFIXES):
            raise IsbnError(value)
        return value, to_isbn10(value)
    if len(value) == 10 and is_valid_isbn10(value):
        return to_isbn13(value), value
    raise IsbnError(value)


def try_normalize(raw: object) -> tuple[str | None, str | None]:
    """Like :func:`normalize`, but return ``(None, None)`` for a bad value."""
    try:
        return normalize(raw)
    except IsbnError:
        return None, None


def is_isbn_barcode(code: object) -> bool:
    """Whether the EAN-13 barcode *code* is an ISBN (prefix ``978`` or ``979``)."""
    value = clean(code)
    return (
        len(value) == 13
        and value.startswith(ISBN13_PREFIXES)
        and is_valid_isbn13(value)
    )


__all__ = [
    "IsbnError",
    "clean",
    "is_isbn_barcode",
    "is_valid_isbn10",
    "is_valid_isbn13",
    "isbn10_check_char",
    "isbn13_check_digit",
    "normalize",
    "to_isbn10",
    "to_isbn13",
    "try_normalize",
]
