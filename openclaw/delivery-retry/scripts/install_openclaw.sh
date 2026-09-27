#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OPENCLAW="$(cd "$(dirname "$0")/../.." && pwd)/openclaw-gateway"
if [[ ! -x "${OPENCLAW}" ]]; then
  OPENCLAW="$(command -v openclaw || true)"
fi
if [[ -z "${OPENCLAW}" ]]; then
  echo "openclaw CLI not found"
  exit 1
fi

echo "==> Linking delivery-retry plugin"
"${OPENCLAW}" plugins install --link --force --accept-capabilities "${ROOT}/plugin"
"${OPENCLAW}" plugins enable delivery-retry --accept-capabilities || true
"${OPENCLAW}" config set plugins.entries.delivery-retry.enabled true || true

echo "==> Done. Restart the gateway so the hook is live:"
echo "    ${OPENCLAW} gateway restart"
