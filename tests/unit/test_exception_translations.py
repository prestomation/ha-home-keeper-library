"""Drift guard for the ``exception-translations`` quality-scale rule (no HA).

Platinum integrations raise *localizable* exceptions: every user-facing
``ServiceValidationError`` / ``HomeAssistantError`` must be constructed with a
``translation_key`` (plus ``translation_domain``) rather than a bare English
string, and that key must exist under ``exceptions`` in ``strings.json``.

This pure-AST check fails the build if someone adds a bare-string raise or a
``translation_key`` with no matching strings.json entry — so the rule can't
silently regress.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

_COMPONENT = (
    Path(__file__).resolve().parents[2] / "custom_components" / "home_keeper_library"
)
# Exception types that surface to the user and therefore must be translatable.
_TRANSLATABLE = {"ServiceValidationError", "HomeAssistantError"}


def _raise_calls() -> list[tuple[str, int, ast.Call]]:
    """Every ``raise <TranslatableError>(...)`` call in the component source."""
    found: list[tuple[str, int, ast.Call]] = []
    for path in sorted(_COMPONENT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
                continue
            func = node.exc.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name in _TRANSLATABLE:
                found.append((path.name, node.lineno, node.exc))
    return found


def _kwarg(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def test_user_facing_raises_use_translation_keys() -> None:
    """No bare-string raises: each must pass translation_domain + translation_key."""
    offenders = [
        f"{file}:{line}"
        for file, line, call in _raise_calls()
        if _kwarg(call, "translation_key") is None
        or _kwarg(call, "translation_domain") is None
    ]
    assert not offenders, (
        "User-facing exceptions must use translation_domain + translation_key "
        f"(exception-translations rule); offenders: {offenders}"
    )


def test_translation_keys_exist_in_strings() -> None:
    """Every translation_key raised must have an entry under strings.json exceptions."""
    strings = json.loads((_COMPONENT / "strings.json").read_text(encoding="utf-8"))
    defined = set(strings.get("exceptions", {}))
    missing = sorted(
        {
            key.value
            for _, _, call in _raise_calls()
            if isinstance((key := _kwarg(call, "translation_key")), ast.Constant)
            and key.value not in defined
        }
    )
    assert not missing, (
        f"translation_key(s) missing from strings.json exceptions: {missing}"
    )


def _literal_keys(func_names: set[str]) -> set[str]:
    """The first string argument of each call to one of *func_names*."""
    keys: set[str] = set()
    for path in sorted(_COMPONENT.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name not in func_names:
                continue
            arg = (
                node.args[0]
                if name in ("LibraryError", "CoverError")
                else node.args[-1]
            )
            if name in ("resolve_exception", "_error") and len(node.args) >= 2:
                arg = node.args[1] if name == "resolve_exception" else node.args[3]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keys.add(arg.value)
    return keys


def test_library_error_keys_exist_in_strings() -> None:
    """Each ``LibraryError`` key and each eager lookup key has a message.

    The test reads the source. In the ``mutants/`` copy of mutmut the source
    holds mutated strings, so the test skips there.
    """
    if "mutants" in _COMPONENT.parts:
        pytest.skip("mutmut copies mutated source")
    strings = json.loads((_COMPONENT / "strings.json").read_text(encoding="utf-8"))
    defined = set(strings["exceptions"])
    used = _literal_keys({"LibraryError", "CoverError", "resolve_exception", "_error"})
    # A raise with a constant ``translation_key`` uses its key too.
    used |= {
        key.value
        for _, _, call in _raise_calls()
        if isinstance((key := _kwarg(call, "translation_key")), ast.Constant)
    }
    # ``store._get`` builds ``<kind>_not_found`` for these kinds.
    used |= {
        f"{kind}_not_found"
        for kind in ("room", "bookcase", "shelf", "book", "copy", "loan")
    }
    assert "invalid_field" in used and "not_loaded" in used
    assert not used - defined, f"keys missing from strings.json: {used - defined}"
    unused = defined - used
    assert not unused, f"exception keys that no code uses: {sorted(unused)}"
