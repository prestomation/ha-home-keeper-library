#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../custom_components/home_keeper_library/frontend"
npm run build
