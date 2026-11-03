"""Tests that this integration does not block the event loop.

The autouse ``blockbuster`` fixture in ``conftest.py`` does the checking. A
blocking call on the loop thread, with a frame of this integration in the
stack, fails the test with the file and line of the call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from blockbuster import BlockingError

from custom_components.home_keeper_library import backend_i18n, covers


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


async def test_a_loaded_language_reads_no_file(hass) -> None:
    """After ``preload``, a lookup in that language reads no file on the loop."""
    await hass.async_add_executor_job(backend_i18n.preload, "de")
    assert "{" not in backend_i18n.resolve_exception("de", "not_loaded")


@pytest.mark.xfail(
    strict=True,
    raises=BlockingError,
    reason="A language that was not preloaded is read on the loop. This happens "
    "when the user changes the language of Home Assistant after the setup.",
)
async def test_a_new_language_reads_no_file_on_the_loop(hass) -> None:
    """Known gap: only the language at setup is preloaded."""
    backend_i18n._exceptions.cache_clear()
    backend_i18n._backend_strings.cache_clear()
    backend_i18n.resolve_exception("fr", "not_loaded")
