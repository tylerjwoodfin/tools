#!/usr/bin/env bash
set -euo pipefail

JOB_NAME="openai-auth-watch"

OPENCLAW="$(cd "$(dirname "$0")/../.." && pwd)/openclaw-gateway"
if [[ ! -x "${OPENCLAW}" ]]; then
  OPENCLAW="$(command -v openclaw || true)"
fi
if [[ -z "${OPENCLAW}" ]]; then
  echo "openclaw CLI not found; left cron jobs untouched."
  exit 0
fi

echo "==> Removing hourly OpenAI auth watch, if it is still scheduled"
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
  "${OPENCLAW}" cron rm "${existing}"
  echo "==> Removed ${JOB_NAME}"
else
  echo "==> ${JOB_NAME} is not scheduled"
fi
