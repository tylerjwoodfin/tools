#!/usr/bin/env bash
# Install diary-llm and wire it into the local OpenClaw setup.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${HOME}/.config/diary-llm"
CONFIG_PATH="${CONFIG_DIR}/config.yaml"
VENV="${ROOT}/.venv"
WORKSPACE_SKILL="${HOME}/.openclaw/workspace/skills/diary"

echo "==> Creating venv at ${VENV}"
python3 -m venv "${VENV}"
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
pip install -U pip
pip install -e "${ROOT}[dev]"

mkdir -p "${HOME}/.local/bin"
ln -sfn "${VENV}/bin/diary-llm" "${HOME}/.local/bin/diary-llm"
echo "==> Linked ~/.local/bin/diary-llm"

echo "==> Writing config (if missing) to ${CONFIG_PATH}"
mkdir -p "${CONFIG_DIR}"
if [[ ! -f "${CONFIG_PATH}" ]]; then
  cp "${ROOT}/config.example.yaml" "${CONFIG_PATH}"
  echo "Created ${CONFIG_PATH}"
else
  echo "Keeping existing ${CONFIG_PATH}"
fi

mkdir -p "$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path.home().joinpath('.config/diary-llm/config.yaml').read_text())
print(cfg.get('diary_dir', str(Path.home() / 'syncthing/notes/diary')))
PY
)"
mkdir -p "${HOME}/.local/share/diary-llm"

echo "==> Installing OpenClaw skill into workspace"
mkdir -p "$(dirname "${WORKSPACE_SKILL}")"
rm -rf "${WORKSPACE_SKILL}"
cp -R "${ROOT}/openclaw/skill/diary" "${WORKSPACE_SKILL}"

echo "==> Linking OpenClaw plugin"
if command -v openclaw >/dev/null 2>&1; then
  openclaw plugins install -l --force --accept-capabilities "${ROOT}/openclaw/plugin" || \
    openclaw plugins install --link --force "${ROOT}/openclaw/plugin" || true
  openclaw plugins enable diary-llm || true
  # Allow conversation interception for active diary sessions
  openclaw config set plugins.entries.diary-llm.enabled true || true
  openclaw config set plugins.entries.diary-llm.hooks.allowConversationAccess true || true
  openclaw config set plugins.entries.diary-llm.config.cliPath "${VENV}/bin/diary-llm" || true
  openclaw config set plugins.entries.diary-llm.config.configPath "${CONFIG_PATH}" || true

  echo "==> Registering cron tick automation"
  # Remove prior job with same name if present
  existing="$(openclaw cron list --json 2>/dev/null | python3 -c '
import json,sys
try:
  data=json.load(sys.stdin)
except Exception:
  data=[]
jobs = data if isinstance(data, list) else data.get("jobs") or data.get("items") or []
for j in jobs:
  name=(j.get("name") or j.get("displayName") or "")
  if name == "diary-llm-tick":
    print(j.get("id") or "")
    break
' || true)"
  if [[ -n "${existing}" ]]; then
    openclaw cron rm "${existing}" || true
  fi

  TICK_CRON="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path.home().joinpath('.config/diary-llm/config.yaml').read_text()) or {}
print(cfg.get('tick_cron', '0 */2 * * *'))
PY
)"
  TARGET="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path.home().joinpath('.config/diary-llm/config.yaml').read_text()) or {}
print((cfg.get('telegram') or {}).get('target') or '8974380881')
PY
)"

  openclaw cron add \
    --name "diary-llm-tick" \
    --description "Finalize inactive diary sessions and maybe send a proactive diary prompt" \
    --cron "${TICK_CRON}" \
    --tz "America/Los_Angeles" \
    --command "${VENV}/bin/diary-llm --config ${CONFIG_PATH} tick" \
    --announce \
    --channel telegram \
    --to "${TARGET}" \
    --session isolated \
    || echo "Warning: could not create cron job; create manually with openclaw cron add"

  echo "==> Done. Restart gateway if the plugin does not load immediately:"
  echo "    openclaw gateway restart"
else
  echo "openclaw CLI not found; installed Python package + skill only."
fi

echo
echo "Try: diary-llm --stub-llm status"
echo "     /diary in Telegram"
