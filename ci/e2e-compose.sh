#!/usr/bin/env bash
# Run `docker compose` on the browser-test stack: the compose project `hkl-e2e`
# (override with COMPOSE_PROJECT) with both compose files. ci/e2e-up.sh, e2e.yml,
# walkthrough-preview.yml and ha-beta.yml all start, read and stop the stack
# through this script, so they cannot use different projects or files.
#
#   bash ci/e2e-compose.sh logs homeassistant
#   bash ci/e2e-compose.sh down -v
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec docker compose -p "${COMPOSE_PROJECT:-hkl-e2e}" \
  -f "$ROOT/tests/integration/docker-compose.yml" \
  -f "$ROOT/tests/e2e/docker-compose.e2e.yml" "$@"
