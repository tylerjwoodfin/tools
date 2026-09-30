#!/usr/bin/env python3
"""Fetch, list, and finish Vikunja TJW tickets.

    python3 ticket.py get TJW-242
    python3 ticket.py ls
    python3 ticket.py finish TJW-242 --comment "Fixed by Cursor."
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from main import api, load_config, project_id  # noqa: E402

try:
    from cabinet import Cabinet
except ImportError:
    Cabinet = None  # type: ignore[misc, assignment]

DEFAULT_REVIEW_STATUS = "Testing"


def parse_ref(raw: str) -> int:
    match = re.search(r"(\d+)\s*$", raw.strip())
    if not match:
        raise ValueError(f"Not a ticket ref: {raw!r}")
    return int(match.group(1))


def review_status() -> str:
    if Cabinet:
        value = Cabinet().get("backloggist", "vikunja_human_review_status", return_type=str) or ""
        value = str(value).strip()
        if value:
            return value
    return DEFAULT_REVIEW_STATUS


def kanban(cfg: dict[str, str], pid: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    views = api(cfg, "GET", f"/projects/{pid}/views") or []
    view = next((row for row in views if row.get("view_kind") == "kanban"), None)
    if not view:
        raise RuntimeError("TJW has no kanban view")
    buckets = api(cfg, "GET", f"/projects/{pid}/views/{view['id']}/buckets") or []
    return view, buckets


def task_by_ref(cfg: dict[str, str], pid: int, ref: int) -> dict[str, Any]:
    return api(cfg, "GET", f"/projects/{pid}/tasks/by-index/{ref}", params={"expand": "buckets"})


def status_name(task: dict[str, Any]) -> str:
    buckets = task.get("buckets") or []
    if buckets:
        return str(buckets[0].get("title") or "")
    return ""


def list_tasks(cfg: dict[str, str], pid: int, status: str | None, include_done: bool) -> list[dict[str, Any]]:
    wanted = status.casefold() if status else None
    closed = {"done", "archived"}
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = api(
            cfg,
            "GET",
            f"/projects/{pid}/tasks",
            params={"page": page, "per_page": 50, "expand": "buckets"},
        ) or []
        for task in batch:
            title = status_name(task)
            if wanted and title.casefold() != wanted:
                continue
            if not include_done and (task.get("done") or title.casefold() in closed):
                continue
            task = dict(task)
            task["status_name"] = title
            rows.append(task)
        if len(batch) < 50:
            break
        page += 1
    return rows


def move_to_bucket(cfg: dict[str, str], pid: int, task_id: int, title: str) -> None:
    view, buckets = kanban(cfg, pid)
    match = next((bucket for bucket in buckets if str(bucket.get("title") or "").casefold() == title.casefold()), None)
    if not match:
        names = ", ".join(str(bucket.get("title") or "") for bucket in buckets)
        raise RuntimeError(f"No Vikunja column {title!r}. Columns: {names}")
    api(
        cfg,
        "POST",
        f"/projects/{pid}/views/{view['id']}/buckets/{match['id']}/tasks",
        json={"task_id": task_id},
    )


def cmd_get(args: argparse.Namespace) -> int:
    cfg = load_config()
    pid = project_id(cfg)
    ref = parse_ref(args.ref)
    task = task_by_ref(cfg, pid, ref)
    status = status_name(task)
    print(f"ref=TJW-{task.get('index')}")
    print(f"title={task.get('title')}")
    print(f"status={status}")
    print("attachments=0")
    print("description=")
    print(task.get("description") or "")
    if args.json:
        print(json.dumps({"ref": task.get("index"), "title": task.get("title"), "status": status, "description": task.get("description") or "", "id": task.get("id"), "url": f"{cfg['base_url']}/tasks/{task['id']}"}, indent=2))
    return 0


def cmd_ls(args: argparse.Namespace) -> int:
    cfg = load_config()
    pid = project_id(cfg)
    rows = list_tasks(cfg, pid, args.status, include_done=args.all)
    rows.sort(key=lambda task: (str(task.get("status_name")), int(task.get("index") or 0)))
    if args.json:
        print(json.dumps([{"ref": row.get("index"), "status": row.get("status_name"), "subject": row.get("title")} for row in rows], indent=2))
        return 0
    if not rows:
        print("No tickets.")
        return 0
    current = None
    for row in rows:
        status = row.get("status_name") or "(no status)"
        if status != current:
            current = status
            print(f"\n{status}" if current else status)
        print(f"  TJW-{row.get('index')}  {row.get('title')}")
    print()
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    cfg = load_config()
    pid = project_id(cfg)
    ref = parse_ref(args.ref)
    task = task_by_ref(cfg, pid, ref)
    status = args.status or review_status()
    move_to_bucket(cfg, pid, int(task["id"]), status)
    api(cfg, "PUT", f"/tasks/{task['id']}/comments", json={"comment": args.comment})
    print(f"TJW-{task.get('index')} -> {status}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch, list, and finish Vikunja TJW tickets.")
    sub = parser.add_subparsers(dest="command", required=True)

    get_p = sub.add_parser("get", help="Print ticket title, status, and description")
    get_p.add_argument("ref")
    get_p.add_argument("--json", action="store_true")
    get_p.set_defaults(func=cmd_get)

    ls_p = sub.add_parser("ls", help="List tickets by Kanban column")
    ls_p.add_argument("--status", default=None)
    ls_p.add_argument("--all", action="store_true", help="Include done tickets in every column")
    ls_p.add_argument("--json", action="store_true")
    ls_p.set_defaults(func=cmd_ls)

    finish_p = sub.add_parser("finish", help="Move a ticket to Testing and add a comment")
    finish_p.add_argument("ref")
    finish_p.add_argument("--comment", required=True)
    finish_p.add_argument("--status", default=None, help="Column name (default: Testing)")
    finish_p.set_defaults(func=cmd_finish)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
