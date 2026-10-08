#!/usr/bin/env bash
# One-shot local / session runner for the browser tests:
#   prepare env -> build the bundles -> fetch Home Keeper -> seed -> start HA ->
#   wait -> run Playwright -> tear down.
#
# Usage: bash ci/e2e-up.sh [extra playwright args...]
#   KEEP_UP=1 bash ci/e2e-up.sh                # leave the containers running
#   NO_TESTS=1 KEEP_UP=1 bash ci/e2e-up.sh     # only start (for a capture)
#   HOME_KEEPER_SRC=/path/to/ha-home-keeper bash ci/e2e-up.sh   # a local Home Keeper
#   HOME_KEEPER_REF=<tag or branch> bash ci/e2e-up.sh                   # clone from GitHub
#   SKIP_BROWSER_ENV=1 bash ci/e2e-up.sh   # CI: Docker and Chromium are ready
#
# CI runs this script too (NO_TESTS=1 KEEP_UP=1), so CI and a local run seed and
# start the same stack. ci/e2e-compose.sh names the compose project `hkl-e2e`
# (override with COMPOSE_PROJECT) and both compose files. Other work on the same
# machine can use port 8123, so a local run holds a lock round the whole script:
#   flock /tmp/claude-0/docker.lock -c 'bash ci/e2e-up.sh'
#
# Each run starts from the committed seed: the runtime files under
# tests/integration/ha_config/ are removed, and tests/e2e/seed/ gives the
# library store and its cover files. The Docker tier and the browser tier use
# the same ha_config, so the committed core.config_entries is put back at the end.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE=(bash ci/e2e-compose.sh)
CONFIG="tests/integration/ha_config"
SEED="tests/e2e/seed"

cleanup() {
  if [ "${KEEP_UP:-0}" != "1" ]; then
    echo "[e2e-up] tearing down the containers..."
    "${COMPOSE[@]}" down -v || true
    git checkout -- "$CONFIG/.storage/core.config_entries" 2>/dev/null || true
  fi
}
trap cleanup EXIT

if [ "${SKIP_BROWSER_ENV:-0}" != "1" ]; then
  echo "[e2e-up] preparing browser environment..."
  bash ci/setup-browser-env.sh
fi
echo "[e2e-up] building the tab and card bundles..."
bash ci/build-panel.sh
echo "[e2e-up] fetching Home Keeper..."
bash ci/fetch-home-keeper.sh

echo "[e2e-up] seeding the Home Assistant config..."
"${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
# Remove what an earlier run wrote (auth, registries, the stores). Only files that
# git ignores go; the committed fixtures stay.
git clean -fdXq "$CONFIG/"
git checkout -- "$CONFIG/.storage/core.config_entries"
# The browser tests add entries that the Docker tier does not need: a to-do list
# for the wishlist of Alex. The committed fixture stays as it is.
python3 - "$CONFIG/.storage/core.config_entries" "$SEED/config_entries.json" <<'PY'
import json
import sys

path, extra = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as handle:
    document = json.load(handle)
with open(extra, encoding="utf-8") as handle:
    document["data"]["entries"].extend(json.load(handle))
with open(path, "w", encoding="utf-8") as handle:
    json.dump(document, handle, indent=2)
PY
mkdir -p "$CONFIG/.storage/home_keeper_library_covers"
cp "$SEED/home_keeper_library.json" "$CONFIG/.storage/home_keeper_library"
cp "$SEED"/covers/*.jpg "$CONFIG/.storage/home_keeper_library_covers/"

echo "[e2e-up] starting Home Assistant..."
"${COMPOSE[@]}" up -d
echo "[e2e-up] waiting for Home Assistant..."
# /api/ answers 401 once Home Assistant is up. The root path answers 302 before
# onboarding, so it cannot tell a started Home Assistant from one that is not up.
up=0
for _ in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8123/api/ 2>/dev/null || true)
  if [ "$code" = "200" ] || [ "$code" = "401" ]; then up=1; echo "[e2e-up] HA is up."; break; fi
  sleep 2
done
if [ "$up" != "1" ]; then
  echo "[e2e-up] Home Assistant did not start within 180 s." >&2
  "${COMPOSE[@]}" logs homeassistant >&2 || true
  exit 1
fi

if [ "${NO_TESTS:-0}" = "1" ]; then
  echo "[e2e-up] NO_TESTS=1: the containers are up; no tests ran."
  exit 0
fi
echo "[e2e-up] running Playwright..."
bash ci/test-e2e.sh "$@"
