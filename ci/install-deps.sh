#!/usr/bin/env bash
set -euo pipefail
npm ci
npm ci --prefix custom_components/home_keeper_library/frontend
pip install -r requirements-test.txt
