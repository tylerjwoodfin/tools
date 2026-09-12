#!/usr/bin/env bash
# Install personal OpenClaw skills (diary + food).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> Diary"
"${ROOT}/diary/scripts/install_openclaw.sh"

echo
echo "==> Food"
"${ROOT}/food/scripts/install_openclaw.sh"
