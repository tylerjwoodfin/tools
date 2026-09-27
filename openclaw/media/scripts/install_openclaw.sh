#!/usr/bin/env bash
# Link the media skill into the OpenClaw workspace.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE_SKILL="${HOME}/.openclaw/workspace/skills/media"
DOTFILES="${DOTFILES:-${HOME}/git/dotfiles}"

mkdir -p "${HOME}/.openclaw/workspace/skills"
if [[ -d "${DOTFILES}/openclaw/workspace/skills/media" ]]; then
  ln -sfn "${DOTFILES}/openclaw/workspace/skills/media" "${WORKSPACE_SKILL}"
else
  mkdir -p "${WORKSPACE_SKILL}"
  cp "${ROOT}/SKILL.md" "${WORKSPACE_SKILL}/SKILL.md"
  echo "Warning: dotfiles media skill missing; copied the tools stub."
fi

echo "Media skill linked. Restart the gateway if the new instructions do not show up:"
echo "    ~/git/tools/openclaw/openclaw-gateway gateway restart"
