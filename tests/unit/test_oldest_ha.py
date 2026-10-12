"""The oldest supported Home Assistant is named in 1 file and must agree."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]


def _load_checker():
    # The filename has a hyphen, so it is not importable as a module name.
    spec = importlib.util.spec_from_file_location(
        "check_ha_version", ROOT / "ci" / "check-ha-version.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()
ENV = CHECKER.read_env((ROOT / "ci" / "oldest-ha.env").read_text())
MAJOR_MINOR = ".".join(ENV["OLDEST_HA_MIN"].split(".")[:2])


def test_env_has_every_key():
    assert set(ENV) == {"OLDEST_HA", "OLDEST_HA_MIN", "OLDEST_PHCC", "OLDEST_PYTHON"}


def test_hacs_json_minimum_matches():
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["homeassistant"] == ENV["OLDEST_HA_MIN"]


def test_readme_badge_matches():
    assert f"Home%20Assistant-{MAJOR_MINOR}%2B" in (ROOT / "README.md").read_text()


def test_install_guide_matches():
    guide = (ROOT / "docs" / "guide" / "start" / "installation.md").read_text()
    assert f"Home Assistant {MAJOR_MINOR} or later" in guide


def test_tested_version_is_not_below_the_minimum():
    assert Version(ENV["OLDEST_HA"]) >= Version(ENV["OLDEST_HA_MIN"])


def test_tested_version_is_in_the_same_minor_release_as_the_minimum():
    # HACS offers the install from OLDEST_HA_MIN. CI must test that minor release.
    assert ENV["OLDEST_HA"].split(".")[:2] == ENV["OLDEST_HA_MIN"].split(".")[:2]


def test_read_env_skips_comments_and_blank_lines():
    assert CHECKER.read_env("# note\n\nA=1\n B = two \n") == {"A": "1", "B": "two"}
