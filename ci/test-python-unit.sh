#!/usr/bin/env bash
# Pure unit tier: needs only `pip install pytest PyYAML hypothesis` (no HA harness).
#
# `-p no:homeassistant`: when pytest-homeassistant-custom-component is installed
# (the .venv of ci/setup-ci-deps.sh, the test.yml job), its plugin loads into
# every pytest run, and its autouse async fixture errors on each unit test. The
# flag is a no-op where the harness is not installed.
set -euo pipefail
find custom_components -name "*.py" -exec python -m py_compile {} +
python -m pytest tests/unit -v -p no:homeassistant "$@"
