"""Unit tests for the backend strings and their translations."""

from __future__ import annotations

import json
import re
from pathlib import Path

import ex.backend_i18n as i18n
import ex.const as const
import pytest

_DIR = (
    Path(__file__).resolve().parents[2]
    / "custom_components"
    / "home_keeper_library"
    / "backend_strings"
)
_SOURCE = json.loads((_DIR / "en.json").read_text(encoding="utf-8"))
# A word that is the same in English and in the language.
_SAME = {("fr", "tab.title")}


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", value))


def test_every_language_has_a_table() -> None:
    assert sorted(p.stem for p in _DIR.glob("*.json")) == sorted(const.LANGUAGES)


@pytest.mark.parametrize("lang", [x for x in const.LANGUAGES if x != "en"])
def test_backend_string_parity(lang: str) -> None:
    table = json.loads((_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    assert set(table) == set(_SOURCE), lang
    for key, value in _SOURCE.items():
        assert _tokens(table[key]) == _tokens(value), (lang, key)
        if (lang, key) not in _SAME:
            assert table[key] != value, f"{lang}.{key} is not translated"


def test_language_chain() -> None:
    assert i18n.language_chain("pt-BR") == ("pt-BR", "pt", "en")
    assert i18n.language_chain("en") == ("en",)
    assert i18n.language_chain(None) == ("en",)


def test_resolve_string() -> None:
    assert i18n.resolve_string(
        "en", "loan_task.name_out", title="Dune", party="Al"
    ) == ("Get Dune back from Al")
    assert i18n.resolve_string("de", "tab.title") == "Bibliothek"
    assert i18n.resolve_string("de-CH", "tab.title") == "Bibliothek"
    assert i18n.resolve_string("xx", "tab.title") == "Library"
    assert i18n.resolve_string("en", "missing.key") == "missing.key"
    assert i18n.resolve_string("en", "loan_task.name_in", title="X") == (
        "Return X to {party}"
    )


def test_resolve_exception() -> None:
    assert i18n.resolve_exception("en", "book_not_found", id="b1") == (
        "No book has the ID b1."
    )
    assert i18n.resolve_exception("en", "not_a_key") == "not_a_key"


def test_all_strings_and_preload() -> None:
    titles = i18n.all_strings("tab.title")
    assert set(titles) == set(const.LANGUAGES)
    assert titles["en"] == "Library"
    assert i18n.all_strings("missing") == {}
    i18n.preload("fr")
