"""Tests that this integration does not block the event loop.

The autouse ``blockbuster`` fixture in ``conftest.py`` does the checking. A
blocking call on the loop thread, with a frame of this integration in the
stack, fails the test with the file and line of the call.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from blockbuster import BlockingError

from custom_components.home_keeper_library import backend_i18n, const, covers


async def test_blockbuster_finds_a_blocking_call(tmp_path: Path) -> None:
    """Guard test: the fixture must be active, or the other tests prove nothing."""
    # read_bundle_cover reads the disk. It is meant for an executor job.
    with pytest.raises(BlockingError):
        covers.read_bundle_cover(tmp_path, "missing.jpg")


async def test_blockbuster_ignores_the_executor(hass, tmp_path: Path) -> None:
    """The same call in an executor job is allowed."""
    data = await hass.async_add_executor_job(
        covers.read_bundle_cover, tmp_path, "missing.jpg"
    )
    assert data is None


async def test_setup_preloads_every_language(hass, setup_entry) -> None:
    """After the setup, a lookup in any shipped language reads no file."""
    for lang in const.LANGUAGES:
        assert backend_i18n.resolve_exception(lang, "not_loaded") != "not_loaded"
        assert backend_i18n.resolve_string(lang, "tab.title")


async def test_a_new_language_reads_no_file_on_the_loop(hass, setup_entry) -> None:
    """The user changes the language of Home Assistant after the setup."""
    hass.config.language = "fr"
    assert backend_i18n.resolve_exception(hass.config.language, "not_loaded")


async def test_a_language_without_a_file_reads_no_file(hass, setup_entry) -> None:
    """A language with no shipped file falls back to English with no disk access."""
    # Blockbuster does not see an open() of a missing file, so the test checks
    # that no read starts at all for a language with no file.
    with patch.object(backend_i18n, "_read_json") as read:
        for lang in ("xx", "xx-YY"):
            text = backend_i18n.resolve_exception(lang, "not_loaded")
            assert text != "not_loaded"
        backend_i18n.resolve_string("xx", "tab.title")
    read.assert_not_called()
    # pt-BR has no file, and pt has one.
    assert backend_i18n.resolve_exception("pt-BR", "not_loaded") != "not_loaded"
    assert backend_i18n.resolve_exception("xx", "not_loaded") == (
        backend_i18n.resolve_exception("en", "not_loaded")
    )
    assert backend_i18n.resolve_string("xx", "tab.title") == "Library"


async def test_a_second_preload_reads_nothing(hass, setup_entry) -> None:
    """A reload of the config entry runs the preload again. It is a no-op."""
    with patch.object(backend_i18n, "_read_json") as read:
        backend_i18n.preload()
    read.assert_not_called()
