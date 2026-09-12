#!/usr/bin/env bash
# Install the /food OpenClaw skill, plugin, and 7pm log reminder.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_SKILL="${HOME}/.openclaw/workspace/skills/food"
JOB_NAME="food-log-remind"
CLI="${ROOT}/scripts/food_cli.py"
PYTHON="${HOMEBREW_PREFIX:-/opt/homebrew}/bin/python3"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

echo "==> Installing OpenClaw food skill into workspace"
mkdir -p "$(dirname "${WORKSPACE_SKILL}")"
rm -rf "${WORKSPACE_SKILL}"
mkdir -p "${WORKSPACE_SKILL}"
cp "${ROOT}/SKILL.md" "${WORKSPACE_SKILL}/SKILL.md"

# Prefer Gateway-bundled CLI when present (Homebrew openclaw often lags).
OPENCLAW="$(cd "$(dirname "$0")/../.." && pwd)/openclaw-gateway"
if [[ ! -x "${OPENCLAW}" ]]; then
  OPENCLAW="$(command -v openclaw || true)"
fi
if [[ -z "${OPENCLAW}" ]]; then
  echo "openclaw CLI not found; copied skill only."
  echo "    ${WORKSPACE_SKILL}"
  exit 0
fi

echo "==> Linking OpenClaw food plugin"
"${OPENCLAW}" plugins install -l --force --accept-capabilities "${ROOT}/plugin" || \
  "${OPENCLAW}" plugins install --link --force "${ROOT}/plugin" || true
"${OPENCLAW}" plugins enable food || true
"${OPENCLAW}" config set plugins.entries.food.enabled true || true
"${OPENCLAW}" config set plugins.entries.food.hooks.allowConversationAccess true || true
"${OPENCLAW}" config set plugins.entries.food.config.cliPath "${CLI}" || true
"${OPENCLAW}" config set plugins.entries.food.config.pythonPath "${PYTHON}" || true

echo "==> Registering 7pm food-log reminder (isolated command; plugin handles replies)"
existing="$("${OPENCLAW}" cron list --json 2>/dev/null | python3 -c '
import json,sys
try:
  data=json.load(sys.stdin)
except Exception:
  data=[]
jobs = data if isinstance(data, list) else data.get("jobs") or data.get("items") or []
want = sys.argv[1]
for j in jobs:
  name=(j.get("name") or j.get("displayName") or "")
  if name == want:
    print(j.get("id") or "")
    break
' "${JOB_NAME}" || true)"
if [[ -n "${existing}" ]]; then
  "${OPENCLAW}" cron rm "${existing}" || true
fi

"${OPENCLAW}" cron add \
  --name "${JOB_NAME}" \
  --description "Gentle Telegram nudge if today is under 1000 logged calories" \
  --cron "0 19 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --command "${PYTHON} ${CLI} tick" \
  --no-deliver \
  || echo "Warning: could not create cron job; create manually with openclaw cron add"

echo "==> Done. Restart gateway if the plugin does not load immediately:"
echo "    openclaw gateway restart"
echo
echo "Try: /food tacos 100"
echo "     matcha should be 200"
