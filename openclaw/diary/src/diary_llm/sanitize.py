"""Inbound message cleanup for diary sessions."""

from __future__ import annotations

import re

# OpenClaw sometimes prefixes Telegram bodies with node/runtime banners.
_SYSTEM_BANNER = re.compile(
    r"^System:\s*\[[^\]]+\]\s*Node:[^\n]*\n+",
    re.IGNORECASE,
)
_MULTI_BLANK = re.compile(r"\n{3,}")


def sanitize_user_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    cleaned = _SYSTEM_BANNER.sub("", cleaned).strip()
    # Drop leftover leading "System:" lines if present without the Node form.
    lines = []
    for line in cleaned.splitlines():
        if not lines and line.lower().startswith("system:"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    cleaned = _MULTI_BLANK.sub("\n\n", cleaned)
    return cleaned
