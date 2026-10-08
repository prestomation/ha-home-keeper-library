"""Server-side string lookup for text that Home Assistant does not translate later.

Home Assistant translates a ``ServiceValidationError`` when the frontend shows it.
Some surfaces need the final text at once:

* A websocket error (``connection.send_error``) and an HTTP view error show their
  message as is.
* The name of a loan task in Home Keeper, the title of the panel tab, the
  completion prompt and the to-do item text are not exceptions, and they have no
  place in ``strings.json``. They are in ``backend_strings/<lang>.json``.

Each helper reads a JSON file and fills ``{token}`` placeholders. The module
imports no Home Assistant code. The copy follows ``backend_i18n.py`` of Home
Keeper.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

_DEFAULT_LANG = "en"
_COMPONENT_DIR = Path(__file__).parent
_TRANSLATIONS_DIR = _COMPONENT_DIR / "translations"
_BACKEND_STRINGS_DIR = _COMPONENT_DIR / "backend_strings"
_TOKEN_RE = re.compile(r"\{(\w+)\}")


def language_chain(lang: str | None) -> tuple[str, ...]:
    """The string tables to try for *lang*, in order.

    First the exact tag, then its base language, then English. ``es-419`` tries
    ``es-419``, ``es`` and ``en``. The panel uses the same order (``i18n.ts``), so a
    regional language gets the same text in the panel and in the backend.
    """
    lang = lang or _DEFAULT_LANG
    return tuple(dict.fromkeys((lang, lang.split("-")[0], _DEFAULT_LANG)))


def _interpolate(template: str, params: dict[str, Any]) -> str:
    return _TOKEN_RE.sub(
        lambda m: str(params[m.group(1)]) if m.group(1) in params else m.group(0),
        template,
    )


def _read_json(path: Path) -> Any:
    """The JSON value of the file at *path*, or None if it cannot be read."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _resolve(
    table: Callable[[str], dict[str, str]], lang: str, key: str, params: dict[str, Any]
) -> str:
    """The first template for *key* in the language chain of *lang*, filled."""
    template = next(
        (t for name in language_chain(lang) if (t := table(name).get(key))),
        key,
    )
    return _interpolate(template, params)


@functools.cache
def _exceptions(lang: str) -> dict[str, str]:
    """The ``exceptions.<key>.message`` templates for *lang*, flattened."""
    data = _read_json(_TRANSLATIONS_DIR / f"{lang}.json")
    exceptions = data.get("exceptions") if isinstance(data, dict) else None
    if not isinstance(exceptions, dict):
        return {}
    return {
        key: value["message"]
        for key, value in exceptions.items()
        if isinstance(value, dict) and isinstance(value.get("message"), str)
    }


def resolve_exception(lang: str, key: str, **params: Any) -> str:
    """Resolve ``exceptions.<key>.message`` for *lang* (see :func:`language_chain`).

    The key itself is the last fallback.
    """
    return _resolve(_exceptions, lang, key, params)


@functools.cache
def _backend_strings(lang: str) -> dict[str, str]:
    """The flat ``backend_strings/<lang>.json`` table for *lang*."""
    data = _read_json(_BACKEND_STRINGS_DIR / f"{lang}.json")
    return data if isinstance(data, dict) else {}


def resolve_string(lang: str, key: str, **params: Any) -> str:
    """Resolve a ``backend_strings/<lang>.json`` key (see :func:`language_chain`).

    The key itself is the last fallback.
    """
    return _resolve(_backend_strings, lang, key, params)


def preload(lang: str) -> None:
    """Read every string table for *lang* into the cache.

    This call blocks. Call it from an executor job, in ``async_setup_entry``, so
    that a later lookup on the event loop reads no file.
    """
    for wanted in language_chain(lang):
        _exceptions(wanted)
        _backend_strings(wanted)


def all_strings(key: str) -> dict[str, str]:
    """The value of a backend string key in each language that has it.

    This call blocks the first time for each language.
    """
    out: dict[str, str] = {}
    for path in sorted(_BACKEND_STRINGS_DIR.glob("*.json")):
        value = _backend_strings(path.stem).get(key)
        if isinstance(value, str) and value:
            out[path.stem] = value
    return out
