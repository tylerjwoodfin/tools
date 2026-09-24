#!/usr/bin/env bash
# Install the /words OpenClaw skill, plugin, and evening recall tick.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_SKILL="${HOME}/.openclaw/workspace/skills/words"
JOB_NAME="word-recall-tick"
CLI="${ROOT}/scripts/words_cli.py"
PYTHON="${HOMEBREW_PREFIX:-/opt/homebrew}/bin/python3"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

echo "==> Linking OpenClaw words skill from dotfiles (canonical)"
DOTFILES="${DOTFILES:-$HOME/git/dotfiles}"
LINK_AI="${DOTFILES}/scripts/link_ai_markdown.sh"
if [[ -x "${LINK_AI}" || -f "${LINK_AI}" ]]; then
  bash "${LINK_AI}"
elif [[ -d "${DOTFILES}/openclaw/workspace/skills/words" ]]; then
  mkdir -p "$(dirname "${WORKSPACE_SKILL}")"
  ln -sfn "${DOTFILES}/openclaw/workspace/skills/words" "${WORKSPACE_SKILL}"
else
  echo "Warning: dotfiles openclaw words skill missing; copying from ${ROOT}/SKILL.md"
  mkdir -p "$(dirname "${WORKSPACE_SKILL}")"
  rm -rf "${WORKSPACE_SKILL}"
  mkdir -p "${WORKSPACE_SKILL}"
  cp "${ROOT}/SKILL.md" "${WORKSPACE_SKILL}/SKILL.md"
fi

OPENCLAW="$(cd "$(dirname "$0")/../.." && pwd)/openclaw-gateway"
if [[ ! -x "${OPENCLAW}" ]]; then
  OPENCLAW="$(command -v openclaw || true)"
fi
if [[ -z "${OPENCLAW}" ]]; then
  echo "openclaw CLI not found; copied skill only."
  echo "    ${WORKSPACE_SKILL}"
  exit 0
fi

echo "==> Linking OpenClaw words plugin"
"${OPENCLAW}" plugins install -l --force --accept-capabilities "${ROOT}/plugin" || \
  "${OPENCLAW}" plugins install --link --force "${ROOT}/plugin" || true
"${OPENCLAW}" plugins enable words || true
"${OPENCLAW}" config set plugins.entries.words.enabled true || true
"${OPENCLAW}" config set plugins.entries.words.hooks.allowConversationAccess true || true
"${OPENCLAW}" config set plugins.entries.words.config.cliPath "${CLI}" || true
"${OPENCLAW}" config set plugins.entries.words.config.pythonPath "${PYTHON}" || true

echo "==> Registering word-recall tick (same window as diary; CLI decides whether to send)"
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
  --description "Occasionally quiz a word from words_to_remember.md" \
  --cron "0 */2 * * *" \
  --tz "America/Los_Angeles" \
  --session isolated \
  --command "${PYTHON} ${CLI} tick" \
  --no-deliver \
  || echo "Warning: could not create cron job; create manually with openclaw cron add"

NOTES="${HOME}/syncthing/notes/words_to_remember.md"
if [[ ! -f "${NOTES}" ]]; then
  "${PYTHON}" "${CLI}" list >/dev/null
  echo "==> Created ${NOTES}"
fi

echo "==> Done. Restart gateway if the plugin does not load immediately:"
echo "    openclaw gateway restart"
echo
echo "Try: /words"
echo "     /words add ephemeral — lasting for a very short time"
