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

echo "==> Linking overflow-reset plugin"
"${OPENCLAW}" plugins install -l --force --accept-capabilities "${ROOT}/plugin" || \
  "${OPENCLAW}" plugins install --link --force --accept-capabilities "${ROOT}/plugin"
"${OPENCLAW}" plugins enable overflow-reset --accept-capabilities || true
"${OPENCLAW}" config set plugins.entries.overflow-reset.enabled true || true
"${OPENCLAW}" config set plugins.entries.overflow-reset.hooks.allowConversationAccess true || true

echo "==> Done. Restart gateway if the plugin does not load immediately:"
echo "    ${OPENCLAW} gateway restart"
