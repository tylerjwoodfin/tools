#!/usr/bin/env python3
"""Create a Vikunja task on the TJW board.

    python3 main.py --name "Short title"

Prints ``Created tjw-<n>: <url>``.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests

try:
    from cabinet import Cabinet
except ImportError:
    Cabinet = None  # type: ignore[misc, assignment]

DEFAULT_API_ROOT = "http://127.0.0.1:3456/api/v1"
DEFAULT_BASE_URL = "https://v.tyler.cloud"
NEW_BUCKET = "New"


def load_config() -> dict[str, str]:
    cfg = {
        "base_url": (os.environ.get("VIKUNJA_BASE_URL") or "").strip().rstrip("/"),
        "api_root": (os.environ.get("VIKUNJA_API_ROOT") or "").strip().rstrip("/"),
        "auth_token": (os.environ.get("VIKUNJA_API_TOKEN") or "").strip(),
    }
    if Cabinet:
        cabinet = Cabinet()
        if not cfg["base_url"]:
            cfg["base_url"] = str(cabinet.get("vikunja", "base_url", return_type=str) or "").strip().rstrip("/")
        if not cfg["api_root"]:
            cfg["api_root"] = str(cabinet.get("vikunja", "api_root", return_type=str) or "").strip().rstrip("/")
        if not cfg["auth_token"]:
            cfg["auth_token"] = str(cabinet.get("vikunja", "api_token", return_type=str) or "").strip()
    cfg["base_url"] = cfg["base_url"] or DEFAULT_BASE_URL
    cfg["api_root"] = cfg["api_root"] or DEFAULT_API_ROOT
    if not cfg["auth_token"]:
        raise RuntimeError("Vikunja API token missing (cabinet vikunja.api_token)")
    return cfg


def api(cfg: dict[str, str], method: str, path: str, **kwargs) -> Any:
    response = requests.request(
        method,
        f"{cfg['api_root']}{path}",
        headers={"Authorization": f"Bearer {cfg['auth_token']}"},
        timeout=45,
        **kwargs,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {path} -> {response.status_code}: {response.text[:400]}")
    if not response.content:
        return None
    return response.json()


def project_id(cfg: dict[str, str]) -> int:
    for project in api(cfg, "GET", "/projects") or []:
        if project.get("identifier") == "TJW":
            return int(project["id"])
    raise RuntimeError("Vikunja project TJW not found")


def new_bucket_id(cfg: dict[str, str], pid: int) -> int:
    views = api(cfg, "GET", f"/projects/{pid}/views") or []
    kanban = next((view for view in views if view.get("view_kind") == "kanban"), None)
    if not kanban:
        raise RuntimeError("TJW has no kanban view")
    buckets = api(cfg, "GET", f"/projects/{pid}/views/{kanban['id']}/buckets") or []
    match = next((bucket for bucket in buckets if bucket.get("title") == NEW_BUCKET), None)
    if not match:
        raise RuntimeError(f"Kanban column {NEW_BUCKET!r} not found")
    return int(match["id"])


def format_created_message(index: int, url: str) -> str:
    label = f"tjw-{index}"
    if sys.stdout.isatty():
        link = f"\033]8;;{url}\033\\{url}\033]8;;\033\\"
        return f"Created \033[32m{label}\033[0m: {link}"
    return f"Created {label}: {url}"


def create_task(cfg: dict[str, str], title: str, description: str) -> dict[str, Any]:
    pid = project_id(cfg)
    created = api(
        cfg,
        "PUT",
        f"/projects/{pid}/tasks",
        json={
            "title": title,
            "description": description,
            "bucket_id": new_bucket_id(cfg, pid),
            "done": False,
        },
    )
    return created


def list_open(cfg: dict[str, str]) -> str:
    pid = project_id(cfg)
    tasks: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = api(cfg, "GET", f"/projects/{pid}/tasks", params={"page": page, "per_page": 50}) or []
        tasks.extend(batch)
        if len(batch) < 50:
            break
        page += 1
    open_tasks = [task for task in tasks if not task.get("done")]
    open_tasks.sort(key=lambda task: int(task.get("index") or 0))
    if not open_tasks:
        return "No open tickets.\n"
    lines = []
    width = max(len(f"TJW-{task.get('index')}") for task in open_tasks)
    for task in open_tasks:
        label = f"TJW-{task.get('index')}".ljust(width)
        lines.append(f"{label}  {task.get('title')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Vikunja TJW task")
    parser.add_argument("--name", default="", help="Task title")
    parser.add_argument("--description", default="", help="Task description")
    parser.add_argument("--ls", action="store_true", help="List open tickets")
    args = parser.parse_args()
    try:
        cfg = load_config()
        if args.ls:
            print(list_open(cfg), end="")
            return 0
        title = args.name.strip()
        if not title:
            print("Pass a title.", file=sys.stderr)
            return 2
        description = args.description.strip() or title
        created = create_task(cfg, title, description)
        index = int(created["index"])
        url = f"{cfg['base_url']}/tasks/{created['id']}"
        print(format_created_message(index, url))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
