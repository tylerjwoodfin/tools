#!/usr/bin/env bash
# Install personal OpenClaw skills (diary, food, words, overflow reset, delivery retry).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Diary"
"${ROOT}/diary/scripts/install_openclaw.sh"

echo
echo "==> Food"
"${ROOT}/food/scripts/install_openclaw.sh"

echo
echo "==> Words"
"${ROOT}/words/scripts/install_openclaw.sh"

echo
echo "==> Overflow reset"
"${ROOT}/overflow-reset/scripts/install_openclaw.sh"

echo
echo "==> Delivery retry"
"${ROOT}/delivery-retry/scripts/install_openclaw.sh"

echo
echo "==> Media"
"${ROOT}/media/scripts/install_openclaw.sh"
