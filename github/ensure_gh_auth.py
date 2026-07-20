#!/usr/bin/env python3
"""Sync GitHub CLI auth from Cabinet ``backloggist.github_token`` into hosts.yml."""

from __future__ import annotations

import json
import os
import stat
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    try:
        from cabinet import Cabinet
    except ImportError:
        print("cabinet is required", file=sys.stderr)
        return 1

    token = str(Cabinet().get("backloggist", "github_token") or "").strip()
    if not token:
        print("cabinet backloggist.github_token is empty", file=sys.stderr)
        return 1

    req = urllib.request.Request(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ensure-gh-auth",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        login = json.load(resp)["login"]

    config_dir = Path.home() / ".config" / "gh"
    config_dir.mkdir(parents=True, exist_ok=True)
    hosts = config_dir / "hosts.yml"
    hosts.write_text(
        "github.com:\n"
        f"    oauth_token: {token}\n"
        f"    user: {login}\n"
        "    git_protocol: https\n",
        encoding="utf-8",
    )
    os.chmod(hosts, stat.S_IRUSR | stat.S_IWUSR)
    # Token may lack read:org; PR create/view still work with repo scope.
    print(f"gh auth synced for {login} (github.com)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
