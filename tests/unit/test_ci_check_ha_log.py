"""Unit tests for ci/check-ha-log.py.

Run with: python -m pytest tests/unit/test_ci_check_ha_log.py -v
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "ci" / "check-ha-log.py"
_spec = importlib.util.spec_from_file_location("check_ha_log", SCRIPT)
assert _spec is not None and _spec.loader is not None
check_ha_log = importlib.util.module_from_spec(_spec)
sys.modules["check_ha_log"] = check_ha_log
_spec.loader.exec_module(check_ha_log)

TS = "2026-11-02 10:00:00.123"

CLEAN_LOG = f"""\
{TS} INFO (MainThread) [homeassistant.core] Starting Home Assistant
{TS} WARNING (SyncWorker_0) [homeassistant.loader] We found a custom integration home_keeper_library which has not been tested by Home Assistant. This component might cause stability problems, be sure to disable it if you experience issues with Home Assistant
{TS} DEBUG (MainThread) [custom_components.home_keeper_library.coordinator] debug line is fine
{TS} INFO (MainThread) [custom_components.home_keeper_library] Setup done
{TS} WARNING (MainThread) [homeassistant.components.foo] Other integration warning
"""

BLOCKING_LOG = f"""\
{TS} INFO (MainThread) [homeassistant.core] Starting Home Assistant
{TS} WARNING (MainThread) [homeassistant.util.loop] Detected blocking call to read_text with args (PosixPath('/config/custom_components/home_keeper_library/manifest.json'),) inside the event loop by custom integration 'home_keeper_library' at custom_components/home_keeper_library/diagnostics.py, line 33: manifest_data = json.loads(manifest_path.read_text(encoding="utf-8")) (offender: /usr/local/lib/python3.13/pathlib/_local.py, line 546: return f.read()), please create a bug report at https://github.com/prestomation/ha-home-keeper-library/issues
Traceback (most recent call last):
  File "/config/custom_components/home_keeper_library/diagnostics.py", line 33, in async_get_config_entry_diagnostics
"""


def run(log: str, domain: str = "home_keeper_library", allowlist=None):
    records = check_ha_log.parse_records(log.splitlines())
    return check_ha_log.check_records(records, domain, allowlist or [])


def test_clean_log_has_no_findings():
    assert run(CLEAN_LOG) == []


def test_generic_custom_integration_notice_is_ignored():
    log = (
        f"{TS} WARNING (SyncWorker_0) [homeassistant.loader] We found a custom "
        "integration home_keeper_library which has not been tested by Home Assistant. "
        "This component might cause stability problems\n"
    )
    assert run(log) == []


@pytest.mark.parametrize("level", ["WARNING", "ERROR", "CRITICAL"])
def test_integration_logger_at_warning_or_higher_fails(level):
    log = f"{TS} {level} (MainThread) [custom_components.home_keeper_library.engine] boom\n"
    findings = run(log)
    assert len(findings) == 1
    assert "custom_components.home_keeper_library.engine" in findings[0].rule


def test_integration_root_logger_fails():
    log = f"{TS} ERROR (MainThread) [custom_components.home_keeper_library] boom\n"
    assert len(run(log)) == 1


def test_logger_of_other_domain_is_not_ours():
    log = (
        f"{TS} ERROR (MainThread) [custom_components.home_keeper_library_extra] boom\n"
    )
    assert run(log) == []
    log = f"{TS} ERROR (MainThread) [custom_components.other] boom\n"
    assert run(log) == []


def test_blocking_call_for_our_domain_fails():
    findings = run(BLOCKING_LOG)
    assert len(findings) == 1
    assert "blocking call" in findings[0].rule
    assert "diagnostics.py, line 33" in findings[0].text


def test_blocking_call_for_other_domain_is_ignored():
    log = (
        f"{TS} WARNING (MainThread) [homeassistant.util.loop] Detected blocking "
        "call to open inside the event loop by custom integration 'other' at "
        "custom_components/other/x.py, line 1\n"
    )
    assert run(log) == []


def test_docker_compose_prefix_is_accepted():
    log = "homeassistant-1  | " + BLOCKING_LOG.splitlines()[1] + "\n"
    assert len(run(log)) == 1


@pytest.mark.parametrize(
    "message",
    [
        (
            "/config/custom_components/home_keeper_library/engine.py:10: RuntimeWarning: "
            "coroutine 'foo' was never awaited"
        ),
        (
            "Task exception was never retrieved\nTraceback (most recent call last):\n"
            '  File "/config/custom_components/home_keeper_library/coordinator.py", line 5'
        ),
        (
            "Executing <Task pending name='Task-9' coro=<run() running at "
            "/config/custom_components/home_keeper_library/coordinator.py:55>> "
            "took 0.350 seconds"
        ),
        (
            "Unclosed client session client_session: <aiohttp.ClientSession> "
            "created at /config/custom_components/home_keeper_library/x.py:3"
        ),
        (
            "The integration 'home_keeper_library' uses a deprecated call "
            "(custom_components/home_keeper_library/__init__.py)"
        ),
    ],
)
def test_known_bad_patterns_for_our_domain_fail(message):
    log = f"{TS} WARNING (MainThread) [asyncio] {message}\n"
    assert len(run(log)) == 1


def test_known_bad_patterns_for_other_code_are_ignored():
    log = (
        f"{TS} WARNING (MainThread) [asyncio] Executing <Task pending name='T' "
        "coro=<run() running at /usr/src/homeassistant/foo.py:5>> took 0.4 seconds\n"
        f"{TS} WARNING (MainThread) [py.warnings] /config/custom_components/other/a.py:1: "
        "RuntimeWarning: coroutine 'x' was never awaited\n"
    )
    assert run(log) == []


def test_traceback_lines_belong_to_the_record_before_them():
    log = (
        f"{TS} ERROR (MainThread) [asyncio] Task exception was never retrieved\n"
        "future: <Task finished>\n"
        "Traceback (most recent call last):\n"
        '  File "/config/custom_components/home_keeper_library/engine.py", line 1, in f\n'
        f"{TS} INFO (MainThread) [homeassistant.core] later line\n"
    )
    findings = run(log)
    assert len(findings) == 1
    assert findings[0].line_no == 1


def test_allowlist_entry_hides_a_finding(tmp_path):
    path = tmp_path / "allow.txt"
    path.write_text(
        "# The test setup has no real light, so this warning is expected.\n"
        "light\\.missing is unavailable\n"
    )
    allow = check_ha_log.load_allowlist(path)
    log = (
        f"{TS} WARNING (MainThread) [custom_components.home_keeper_library.engine] "
        "light.missing is unavailable\n"
        f"{TS} WARNING (MainThread) [custom_components.home_keeper_library.engine] other\n"
    )
    findings = run(log, allowlist=allow)
    assert len(findings) == 1
    assert "other" in findings[0].text


def test_allowlist_entry_without_reason_is_rejected(tmp_path):
    path = tmp_path / "allow.txt"
    path.write_text("light\\.missing is unavailable\n")
    with pytest.raises(ValueError, match="no reason"):
        check_ha_log.load_allowlist(path)


def test_allowlist_reason_does_not_carry_over_a_blank_line(tmp_path):
    path = tmp_path / "allow.txt"
    path.write_text("# Reason one.\nfirst\n\nsecond\n")
    with pytest.raises(ValueError, match="no reason"):
        check_ha_log.load_allowlist(path)


def test_shipped_allowlist_is_valid():
    check_ha_log.load_allowlist(SCRIPT.with_name("ha-log-allowlist.txt"))


def _cli(tmp_path, log_text, *extra):
    log = tmp_path / "ha.log"
    log.write_text(log_text)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--domain",
            "home_keeper_library",
            *extra,
            str(log),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_exit_codes(tmp_path):
    assert _cli(tmp_path, CLEAN_LOG).returncode == 0
    failed = _cli(tmp_path, BLOCKING_LOG)
    assert failed.returncode == 1
    assert "diagnostics.py" in failed.stdout
    # An empty log must not pass.
    assert _cli(tmp_path, "").returncode == 2
    assert _cli(tmp_path, "no ha records here\n").returncode == 2


def test_cli_reads_stdin():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--domain", "home_keeper_library"],
        input=BLOCKING_LOG,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1


def test_cli_bad_allowlist_exits_2(tmp_path):
    allow = tmp_path / "allow.txt"
    allow.write_text("no reason here\n")
    assert _cli(tmp_path, CLEAN_LOG, "--allowlist", str(allow)).returncode == 2


# ---------------------------------------------------------------------------
# Realistic log text: compose prefix, colour codes, tracebacks
# ---------------------------------------------------------------------------

PREFIX = "homeassistant-1  | "

REAL_BLOCKING_LINE = (
    "2026-11-02 10:00:05.200 WARNING (MainThread) [homeassistant.util.loop] "
    "Detected blocking call to open with args "
    "(PosixPath('/config/custom_components/home_keeper_library/manifest.json'),) "
    "inside the event loop by custom integration 'home_keeper_library' at "
    "custom_components/home_keeper_library/diagnostics.py, line 34: "
    'manifest_data = json.loads(manifest_path.read_text(encoding="utf-8")) '
    "(offender: /usr/local/lib/python3.13/pathlib/_local.py, line 546: "
    "return f.read()), please create a bug report at "
    "https://github.com/prestomation/ha-home-keeper-library/issues"
)

REAL_COMPOSE_LOG = "\n".join(
    PREFIX + line
    for line in [
        "s6-rc: info: service s6rc-oneshot-runner: starting",
        "2026-11-02 10:00:00.100 INFO (MainThread) [homeassistant.bootstrap] Starting Home Assistant",
        "2026-11-02 10:00:01.000 WARNING (SyncWorker_3) [homeassistant.loader] We found a custom integration home_keeper_library which has not been tested by Home Assistant.",
        REAL_BLOCKING_LINE,
        "Traceback (most recent call last):",
        '  File "/config/custom_components/home_keeper_library/diagnostics.py", line 34, in async_get_config_entry_diagnostics',
        '    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))',
        "2026-11-02 10:00:06.000 INFO (MainThread) [homeassistant.components.http] Request done",
    ]
)


def test_real_compose_log_is_parsed():
    records = check_ha_log.parse_records(REAL_COMPOSE_LOG.splitlines())
    levels = [r.level for r in records]
    # The s6 line has no level. The other four are records.
    assert levels == [None, "INFO", "WARNING", "WARNING", "INFO"]
    assert records[3].logger == "homeassistant.util.loop"
    # The traceback lines belong to the blocking-call record.
    assert "manifest_path.read_text" in records[3].text
    assert "Traceback" in records[3].text


def test_real_compose_log_finds_the_blocking_call():
    findings = run(REAL_COMPOSE_LOG)
    assert len(findings) == 1
    assert "blocking call" in findings[0].rule
    assert "diagnostics.py, line 34" in findings[0].text


def test_colour_codes_are_removed():
    log = f"{PREFIX}\x1b[33m{REAL_BLOCKING_LINE}\x1b[0m\n"
    assert len(run(log)) == 1


def test_compose_prefix_with_colour_codes_is_removed():
    log = f"\x1b[36mhomeassistant-1  |\x1b[0m {REAL_BLOCKING_LINE}\n"
    assert len(run(log)) == 1


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-11-02T10:00:05.200",
        "2026-11-02T10:00:05.200Z",
        "2026-11-02 10:00:05.200+00:00",
        "2026-11-02 10:00:05",
    ],
)
def test_other_timestamp_forms(stamp):
    log = f"{stamp} ERROR (MainThread) [custom_components.home_keeper_library] boom\n"
    assert len(run(log)) == 1


def test_prefix_forms():
    line = "2026-11-02 10:00:05.200 ERROR (MainThread) [custom_components.home_keeper_library] boom"
    for prefix in ("ha-1 | ", "ha_test.1  |", "homeassistant  | "):
        assert len(run(prefix + line + "\n")) == 1


def test_cli_prints_log_sample_when_no_records(tmp_path):
    lines = [f"unknown format line {i} " + "x" * 300 for i in range(40)]
    result = _cli(tmp_path, "\n".join(lines) + "\n")
    assert result.returncode == 2
    assert "no Home Assistant log records found" in result.stderr
    assert "unknown format line 0 " in result.stderr
    assert "unknown format line 14 " in result.stderr
    assert "unknown format line 15 " not in result.stderr
    assert "unknown format line 24 " not in result.stderr
    assert "unknown format line 39 " in result.stderr
    # Every shown line is cut to 200 characters (plus the "  | " lead).
    shown = [ln for ln in result.stderr.splitlines() if ln.startswith("  | ")]
    assert len(shown) == 30
    assert all(len(ln) <= 5 + 200 for ln in shown)


def test_cli_empty_log_exits_2_without_sample_lines(tmp_path):
    result = _cli(tmp_path, "")
    assert result.returncode == 2
    assert "no Home Assistant log records found" in result.stderr


# ---------------------------------------------------------------------------
# The test container also runs Home Keeper. Only our domain counts.
# ---------------------------------------------------------------------------


def _hk_line(level: str, logger: str, message: str) -> str:
    return f"2026-11-02 10:00:07.000 {level} (MainThread) [{logger}] {message}"


def test_home_keeper_warning_and_error_records_are_ignored():
    log = "\n".join(
        PREFIX + line
        for line in [
            _hk_line("WARNING", "custom_components.home_keeper.coordinator", "boom"),
            _hk_line("ERROR", "custom_components.home_keeper", "boom"),
            _hk_line("CRITICAL", "custom_components.home_keeper.services", "boom"),
        ]
    )
    assert run(log) == []


def test_home_keeper_bad_patterns_are_ignored():
    log = "\n".join(
        PREFIX + line
        for line in [
            _hk_line(
                "WARNING",
                "homeassistant.util.loop",
                "Detected blocking call to open inside the event loop by custom "
                "integration 'home_keeper' at custom_components/home_keeper/store.py, "
                "line 9: data = f.read()",
            ),
            _hk_line(
                "WARNING",
                "asyncio",
                "Executing <Task pending name='T' coro=<run() running at "
                "/config/custom_components/home_keeper/coordinator.py:5>> took 0.4 "
                "seconds",
            ),
            _hk_line(
                "WARNING",
                "py.warnings",
                "/config/custom_components/home_keeper/x.py:1: DeprecationWarning: "
                "old call",
            ),
        ]
    )
    assert run(log) == []


def test_home_keeper_is_not_a_prefix_match_of_our_domain():
    # The Home Keeper domain is the start of ours. The check must see the boundary
    # in both directions.
    ours = _hk_line("WARNING", "custom_components.home_keeper_library.store", "boom")
    theirs = _hk_line("WARNING", "custom_components.home_keeper.store", "boom")
    assert len(run(ours)) == 1
    assert run(theirs) == []
    # Asked for the Home Keeper domain, a record of the library is not a finding.
    assert run(ours, domain="home_keeper") == []
    assert len(run(theirs, domain="home_keeper")) == 1


def test_home_keeper_blocking_call_is_ignored_but_ours_is_found():
    mixed = "\n".join(
        [
            _hk_line(
                "WARNING",
                "homeassistant.util.loop",
                "Detected blocking call to read_text inside the event loop by "
                "custom integration 'home_keeper' at "
                "custom_components/home_keeper/store.py, line 9: x",
            ),
            _hk_line(
                "WARNING",
                "homeassistant.util.loop",
                "Detected blocking call to read_text inside the event loop by "
                "custom integration 'home_keeper_library' at "
                "custom_components/home_keeper_library/covers.py, line 7: x",
            ),
        ]
    )
    findings = run(mixed)
    assert len(findings) == 1
    assert "covers.py, line 7" in findings[0].text


def test_cli_ignores_home_keeper_and_fails_on_the_library(tmp_path):
    clean = "\n".join(
        [
            CLEAN_LOG,
            _hk_line("ERROR", "custom_components.home_keeper.coordinator", "boom"),
        ]
    )
    assert _cli(tmp_path, clean).returncode == 0
    bad = (
        clean
        + "\n"
        + _hk_line("ERROR", "custom_components.home_keeper_library.store", "boom")
    )
    assert _cli(tmp_path, bad).returncode == 1


# ---------------------------------------------------------------------------
# Grouped output and the shipped allowlist
# ---------------------------------------------------------------------------


def _real_blocking_line(call: str) -> str:
    return REAL_BLOCKING_LINE.replace("to open with", f"to {call} with")


GROUP_LOG = "\n".join(
    PREFIX + line
    for line in [
        "2026-11-02 10:00:00.100 INFO (MainThread) [homeassistant.bootstrap] Start",
        _hk_line("ERROR", "custom_components.home_keeper_library.store", "bad 1"),
        _hk_line("ERROR", "custom_components.home_keeper_library.store", "bad 22"),
        _hk_line("ERROR", "custom_components.home_keeper_library.store", "bad 333"),
        _real_blocking_line("read_text"),
        _real_blocking_line("open"),
    ]
)


def test_findings_are_grouped_by_rule_and_shape():
    groups = check_ha_log.group_findings(run(GROUP_LOG))
    assert [len(g.findings) for g in groups] == [3, 1, 1]
    # The 3 errors differ only in a number.
    assert "333" not in groups[0].shape
    assert groups[0].rule.startswith("ERROR from logger")
    assert groups[1].shape != groups[2].shape


def test_report_has_summary_counts_examples_and_details():
    report = check_ha_log.format_report(run(GROUP_LOG))
    summary, details = report.split("Details:")
    assert "5 problem(s) in 3 group(s)" in summary
    assert "1. 3 x ERROR from logger" in summary
    # Only the first two examples are shown for a group of three.
    assert summary.count("bad 22") == 1
    assert "bad 333" not in summary
    starts = [ln for ln in details.splitlines() if ln.startswith("line ")]
    assert len(starts) == 5
    assert "bad 333" in details
    assert "diagnostics.py, line 34" in details


def test_cli_prints_the_final_line_last_in_one_stream(tmp_path):
    result = _cli(tmp_path, GROUP_LOG + "\n")
    assert result.returncode == 1
    assert result.stderr == ""
    lines = result.stdout.rstrip("\n").splitlines()
    assert lines[0].startswith("Summary:")
    assert lines.index("Details:") < len(lines) - 1
    assert lines[-1].endswith(
        "Fix them, or add a reason and a pattern to the allowlist."
    )
    assert "problem(s) found for 'home_keeper_library'" in lines[-1]


def test_shipped_allowlist_does_not_hide_blocking_calls():
    findings = run(_real_blocking_line("open"), allowlist=SHIPPED_ALLOWLIST)
    assert len(findings) == 1


SHIPPED_ALLOWLIST = check_ha_log.load_allowlist(
    SCRIPT.with_name("ha-log-allowlist.txt")
)
