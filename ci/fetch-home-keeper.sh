#!/usr/bin/env bash
# Put the Home Keeper component next to the library for the Docker tier.
#
# The library needs Home Keeper for its panel tab and its loan tasks, so the
# Docker container gets a real Home Keeper. The copy goes to
# tests/integration/.home_keeper/custom_components/home_keeper, which git
# ignores, and docker-compose.yml mounts it read-only.
#
#   HOME_KEEPER_SRC=/path/to/ha-home-keeper bash ci/fetch-home-keeper.sh
#   HOME_KEEPER_REF=main bash ci/fetch-home-keeper.sh   # clone from GitHub
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/tests/integration/.home_keeper/custom_components"
REPO="${HOME_KEEPER_REPO:-https://github.com/prestomation/ha-home-keeper.git}"
REF="${HOME_KEEPER_REF:-main}"

rm -rf "$DEST/home_keeper"
mkdir -p "$DEST"
if [ -n "${HOME_KEEPER_SRC:-}" ]; then
  echo "[home-keeper] copying $HOME_KEEPER_SRC/custom_components/home_keeper"
  mkdir -p "$DEST/home_keeper"
  tar -C "$HOME_KEEPER_SRC/custom_components/home_keeper" \
    --exclude=node_modules --exclude=__pycache__ -cf - . | tar -C "$DEST/home_keeper" -xf -
else
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  echo "[home-keeper] cloning $REPO at $REF"
  git clone --quiet --depth 1 --branch "$REF" "$REPO" "$TMP/hk"
  mkdir -p "$DEST/home_keeper"
  tar -C "$TMP/hk/custom_components/home_keeper" \
    --exclude=node_modules --exclude=__pycache__ -cf - . | tar -C "$DEST/home_keeper" -xf -
fi
find "$DEST/home_keeper" -name "__pycache__" -type d -prune -exec rm -rf {} +
echo "[home-keeper] version: $(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$DEST/home_keeper/manifest.json")"
