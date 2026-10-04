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

echo "==> Ask LM Studio Gemma not to spend the reply on hidden reasoning"
python3 - <<'PY'
import json
from pathlib import Path
path = Path.home() / ".openclaw" / "openclaw.json"
if not path.is_file():
    raise SystemExit(f"missing {path}")
cfg = json.loads(path.read_text())
models = cfg.get("models", {}).get("providers", {}).get("lmstudio", {}).get("models", [])
updated = False
for model in models:
    if model.get("id") == "gemma4-26b":
        extra = model.setdefault("params", {}).setdefault("extra_body", {})
        extra["reasoning_effort"] = "none"
        updated = True
if not updated:
    raise SystemExit("lmstudio model gemma4-26b not found in openclaw.json")
path.write_text(json.dumps(cfg, indent=2) + "\n")
print("reasoning_effort=none")
PY

echo "==> Linking local-model plugin"
"${OPENCLAW}" plugins install --link --force --accept-capabilities "${ROOT}/plugin" || \
  "${OPENCLAW}" plugins install -l --force --accept-capabilities "${ROOT}/plugin"
"${OPENCLAW}" plugins enable local-model --accept-capabilities || true
"${OPENCLAW}" config set plugins.entries.local-model.enabled true || true

LABEL="com.tyler.lmstudio-gemma"
AGENTS="${HOME}/Library/LaunchAgents"
PLIST="${AGENTS}/${LABEL}.plist"
NODE="$(command -v node || true)"
if [[ -z "${NODE}" ]]; then
  echo "node not found"
  exit 1
fi
mkdir -p "${AGENTS}"
cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${NODE}</string>
        <string>${ROOT}/scripts/ensure-model.js</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${HOME}/.lmstudio/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/lmstudio-gemma/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/lmstudio-gemma/stderr.log</string>
</dict>
</plist>
EOF
mkdir -p "${HOME}/Library/Logs/lmstudio-gemma"
UID_NUM="$(id -u)"
launchctl bootout "gui/${UID_NUM}" "${PLIST}" 2>/dev/null || true
launchctl bootstrap "gui/${UID_NUM}" "${PLIST}"
launchctl enable "gui/${UID_NUM}/${LABEL}" || true

echo "==> Done. Restart the gateway so the hook is live:"
echo "    ${OPENCLAW} gateway restart"
