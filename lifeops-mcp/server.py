#!/usr/bin/env python3
"""
Life-ops MCP server — Cabinet, RemindMail, foodlog, milestone, Immich.

Stdout is reserved for MCP JSON-RPC; all diagnostics go to stderr.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("life-ops")

TOOLS_ROOT = Path.home() / "git" / "tools"
FOODLOG = TOOLS_ROOT / "foodlog" / "main.py"
MILESTONE = TOOLS_ROOT / "milestone" / "main.py"

_SENSITIVE_RE = re.compile(
    r"(token|password|secret|passwd|api[_-]?key|auth|credential|private)",
    re.IGNORECASE,
)


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _run(cmd: list[str], *, timeout: int = 60) -> str:
    """Run a command; return combined stdout/stderr or raise ValueError."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ},
        )
    except FileNotFoundError as exc:
        raise ValueError(f"Command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"Timed out after {timeout}s: {' '.join(cmd)}") from exc

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    combined = out if out else err
    if result.returncode != 0:
        detail = err or out or f"exit {result.returncode}"
        raise ValueError(f"{' '.join(cmd)} failed: {detail}")
    return combined or "(ok, no output)"


def _cabinet_bin() -> str:
    return shutil.which("cabinet") or str(Path.home() / ".local" / "bin" / "cabinet")


def _looks_sensitive(path_parts: list[str]) -> bool:
    return any(_SENSITIVE_RE.search(p) for p in path_parts)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: ("***REDACTED***" if _SENSITIVE_RE.search(str(k)) else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


@mcp.tool()
def cabinet_get(path: str) -> str:
    """Get a Cabinet value by space- or dot-separated path (e.g. 'taiga api_root' or 'quality.cloud').

    Sensitive keys (token, password, secret, api_key, auth, …) are redacted in the response.
    """
    parts = path.replace(".", " ").split()
    if not parts:
        raise ValueError("path is required")
    raw = _run([_cabinet_bin(), "--get", *parts])
    if _looks_sensitive(parts):
        return "***REDACTED***"
    try:
        parsed = json.loads(raw)
        return json.dumps(_redact(parsed), indent=2, default=str)
    except json.JSONDecodeError:
        return raw


@mcp.tool()
def cabinet_put(path: str, value: str) -> str:
    """Put a Cabinet value. path is space- or dot-separated; value is stored as a string.

    Example: path='foodlog calorie_target', value='2000'
    """
    parts = path.replace(".", " ").split()
    if not parts:
        raise ValueError("path is required")
    if not value and value != "0":
        raise ValueError("value is required")
    return _run([_cabinet_bin(), "--put", *parts, value])


@mcp.tool()
def remind_save(title: str, when: str, notes: str = "", tags: str = "") -> str:
    """Save a RemindMail reminder without confirmation.

    when: natural language or date (e.g. 'tomorrow', '2026-07-25', 'every monday').
    tags: optional comma-separated tags.
    """
    if not title.strip():
        raise ValueError("title is required")
    if not when.strip():
        raise ValueError("when is required")
    remind = shutil.which("remind")
    if not remind:
        raise ValueError("remind executable not found on PATH")
    cmd = [remind, "--save", "--when", when.strip(), "--title", title.strip()]
    if notes.strip():
        cmd.extend(["--notes", notes.strip()])
    if tags.strip():
        cmd.extend(["--tags", tags.strip()])
    return _run(cmd)


@mcp.tool()
def foodlog_add(food: str, calories: int) -> str:
    """Log food non-interactively. Requires food name and calorie count (integer).

    Equivalent to: foodlog <food> <calories>
    """
    if not food.strip():
        raise ValueError("food is required")
    if calories < 0:
        raise ValueError("calories must be >= 0")
    if not FOODLOG.is_file():
        raise ValueError(f"foodlog not found: {FOODLOG}")
    return _run([sys.executable, str(FOODLOG), food.strip(), str(int(calories))])


@mcp.tool()
def milestone_add(text: str) -> str:
    """Append a milestone to milestones.md for the current year/month."""
    if not text.strip():
        raise ValueError("text is required")
    if not MILESTONE.is_file():
        raise ValueError(f"milestone script not found: {MILESTONE}")
    return _run([sys.executable, str(MILESTONE), text.strip()])


def _immich_config() -> tuple[str, str]:
    """Return (api_url, api_key) from Cabinet. Never log the key."""
    raw_url = _run([_cabinet_bin(), "--get", "immich", "api_url"])
    raw_key = _run([_cabinet_bin(), "--get", "immich", "api_key"])
    url = (raw_url or "").strip().rstrip("/")
    key = (raw_key or "").strip()
    if not url or url.lower().startswith("warning:") or "missing" in url.lower():
        raise ValueError(
            "Cabinet immich.api_url is not set. "
            "Example: cabinet --put immich api_url https://immich.example.com"
        )
    if not key or key.lower().startswith("warning:") or "missing" in key.lower():
        raise ValueError(
            "Cabinet immich.api_key is not set. "
            "Create an API key in Immich Account Settings, then: "
            "cabinet --put immich api_key <key>"
        )
    return url, key


@mcp.tool()
def immich_search(query: str, limit: int = 10) -> str:
    """Search Immich assets by smart/text query. Requires Cabinet immich.api_url and immich.api_key.

    Returns a short JSON list of id, type, originalFileName, takenAt (when present).
    """
    if not query.strip():
        raise ValueError("query is required")
    limit = max(1, min(int(limit), 50))
    base, key = _immich_config()
    headers = {"x-api-key": key, "Accept": "application/json", "Content-Type": "application/json"}
    # Immich smart search
    url = f"{base}/api/search/smart"
    resp = requests.post(
        url,
        headers=headers,
        json={"query": query.strip(), "size": limit},
        timeout=45,
    )
    if resp.status_code == 404:
        # Older Immich: metadata search
        url = f"{base}/api/search/metadata"
        resp = requests.post(
            url,
            headers=headers,
            json={"originalFileName": query.strip(), "size": limit},
            timeout=45,
        )
    if resp.status_code != 200:
        raise ValueError(f"Immich search failed HTTP {resp.status_code}: {resp.text[:400]}")

    data = resp.json()
    assets: list[dict[str, Any]] = []
    if isinstance(data, dict):
        nested = data.get("assets") or data.get("items") or {}
        if isinstance(nested, dict):
            assets = list(nested.get("items") or nested.get("assets") or [])
        elif isinstance(nested, list):
            assets = nested
    elif isinstance(data, list):
        assets = data

    slim = []
    for a in assets[:limit]:
        if not isinstance(a, dict):
            continue
        exif = a.get("exifInfo") or {}
        slim.append(
            {
                "id": a.get("id"),
                "type": a.get("type"),
                "originalFileName": a.get("originalFileName"),
                "takenAt": exif.get("dateTimeOriginal") or a.get("fileCreatedAt"),
                "city": exif.get("city"),
                "country": exif.get("country"),
            }
        )
    return json.dumps({"count": len(slim), "assets": slim}, indent=2)


if __name__ == "__main__":
    _log("life-ops MCP starting (stdio)")
    mcp.run(transport="stdio")
