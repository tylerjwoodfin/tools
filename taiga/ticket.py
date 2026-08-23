"""
Taiga ticket helpers for the Cursor taiga-ticket skill.

Provides get/finish/ls for TJW-### stories without depending on the removed
backloggist package. Resolves ``taiga.api_root`` with Docker discovery when
the stored bridge IP is stale.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests

# Reuse auth/config helpers from the create-story CLI in this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from main import (  # noqa: E402
    REQUEST_TIMEOUT,
    auth_headers,
    fetch_project_by_slug,
    fetch_userstory_statuses,
    load_taiga_config,
    obtain_bearer_token,
    public_base_url,
    resolve_api_root,
    _status_matches_selector,
)

DEFAULT_PROJECT_SLUG = "tjw"
TAIGA_BACK_CONTAINER = "taiga-docker-taiga-back-1"
# Published by taiga-docker (host loopback only); stable across container recreates.
LOCALHOST_API_ROOT = "http://127.0.0.1:8000/api/v1"
PROBE_PATH = "/projects/by_slug"
# Fail fast on stale Docker bridge IPs (connection refused).
PROBE_TIMEOUT = (1.5, 5)
LIST_PAGE_SIZE = 100
SORT_CHOICES = ("status", "ref", "subject")


@dataclass
class Ticket:
    """Minimal user-story view used by the agent workflow."""

    id: int
    ref: int
    title: str
    description: str
    status_name: str
    version: int
    project_id: int
    project_slug: str
    raw: dict[str, Any]

    @property
    def attachments(self) -> list[dict[str, Any]]:
        return list(self.raw.get("_attachments") or [])


@dataclass(frozen=True)
class StorySummary:
    """One row in ``taiga ls``: ticket number, status, and subject."""

    ref: int
    subject: str
    status_name: str
    status_order: int
    kanban_order: int
    is_closed: bool


def status_order_map(statuses: list[dict[str, Any]]) -> dict[str, int]:
    """Map Kanban column display names to their board order."""
    return {
        str(row.get("name") or ""): int(row.get("order") or 0) for row in statuses
    }


def summarize_story(
    raw: dict[str, Any], order_by_status: dict[str, int]
) -> StorySummary:
    """Build a ``StorySummary`` from a Taiga user-story list payload."""
    extra = raw.get("status_extra_info") or {}
    status_name = str(extra.get("name") or "")
    return StorySummary(
        ref=int(raw.get("ref") or 0),
        subject=str(raw.get("subject") or ""),
        status_name=status_name,
        status_order=order_by_status.get(status_name, 10_000),
        kanban_order=int(raw.get("kanban_order") or 0),
        is_closed=bool(raw.get("is_closed")),
    )


def sort_story_rows(
    rows: list[StorySummary],
    sort_by: str,
    reverse: bool = False,
) -> list[StorySummary]:
    """Sort ticket rows by status (Kanban order), ref, or subject."""

    def sort_key(row: StorySummary) -> tuple:
        if sort_by == "ref":
            return (row.ref,)
        if sort_by == "subject":
            return (row.subject.lower(), row.ref)
        return (row.status_order, row.kanban_order, row.ref)

    return sorted(rows, key=sort_key, reverse=reverse)


def _ansi(code: str, text: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"


def format_story_list(
    rows: list[StorySummary],
    *,
    group_by_status: bool = True,
    color: bool = False,
) -> str:
    """Render ticket rows for the terminal (grouped by status, or a flat table)."""
    if not rows:
        return "No tickets.\n"
    ref_width = max(len(f"TJW-{row.ref}") for row in rows)
    lines: list[str] = []
    if group_by_status:
        for status, group in itertools.groupby(
            rows, key=lambda row: row.status_name or "(no status)"
        ):
            group_list = list(group)
            header = f"{status} ({len(group_list)})"
            lines.append(_ansi("1;36", header, color))
            for row in group_list:
                label = f"TJW-{row.ref}".ljust(ref_width)
                lines.append(f"  {_ansi('32', label, color)}  {row.subject}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    status_width = max((len(row.status_name) for row in rows), default=0)
    for row in rows:
        label = f"TJW-{row.ref}".ljust(ref_width)
        status = row.status_name.ljust(status_width)
        lines.append(f"{_ansi('32', label, color)}  {status}  {row.subject}")
    return "\n".join(lines) + "\n"


def discover_taiga_back_api_root(
    container: str = TAIGA_BACK_CONTAINER,
) -> Optional[str]:
    """
    Return ``http://<bridge-ip>:8000/api/v1`` for the running taiga-back container.

    Docker bridge IPs change across restarts; never rely on a hard-coded IP alone.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                container,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    ip = (result.stdout or "").strip()
    if not ip or not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", ip):
        return None
    return f"http://{ip}:8000/api/v1"


def _probe_api_root(api_root: str, bearer: str, project_slug: str) -> bool:
    """Return True if ``api_root`` accepts authenticated requests."""
    try:
        r = requests.get(
            f"{api_root.rstrip('/')}{PROBE_PATH}",
            params={"slug": project_slug},
            headers=auth_headers(bearer),
            timeout=PROBE_TIMEOUT,
        )
    except requests.RequestException:
        return False
    return r.status_code == 200


def _persist_api_root(api_root: str) -> None:
    """Best-effort write of a working api_root back into Cabinet."""
    try:
        from cabinet import Cabinet

        Cabinet().put("taiga", "api_root", value=api_root)
    except Exception:  # noqa: BLE001 — persistence is optional
        pass


def _api_root_candidates(cfg: dict[str, str]) -> list[str]:
    """
    Ordered API roots to try after reboot / container recreate.

    Prefer loopback (stable publish) and live Docker inspect over a Cabinet
    bridge IP, which goes stale when the compose network is recreated.
    """
    candidates: list[str] = []

    def add(root: Optional[str]) -> None:
        if not root:
            return
        normalized = root.rstrip("/")
        if normalized not in candidates:
            candidates.append(normalized)

    add(LOCALHOST_API_ROOT)
    add(discover_taiga_back_api_root())
    add(resolve_api_root(cfg) or None)
    base = (cfg.get("base_url") or "").strip().rstrip("/")
    if base:
        add(f"{base}/api/v1")
    return candidates


def resolve_working_api_root(
    cfg: dict[str, str],
    bearer: str,
    project_slug: str = DEFAULT_PROJECT_SLUG,
    persist: bool = True,
) -> str:
    """
    Return a reachable Taiga API root.

    Tries localhost publish, Docker-discovered taiga-back, configured
    ``api_root``, then ``{base_url}/api/v1``. Persists a working root to
    Cabinet when it differs from the stored value.
    """
    configured = (resolve_api_root(cfg) or "").rstrip("/")
    candidates = _api_root_candidates(cfg)

    if not candidates:
        raise RuntimeError(
            "No Taiga API root configured. Set cabinet taiga.api_root or start "
            f"Docker container {TAIGA_BACK_CONTAINER}."
        )

    last_error = ""
    for root in candidates:
        if _probe_api_root(root, bearer, project_slug):
            if persist and root != configured:
                _persist_api_root(root)
            return root
        last_error = f"unreachable or unauthorized: {root}"

    raise RuntimeError(
        "Could not reach Taiga API. Tried: "
        + ", ".join(candidates)
        + f". Last error: {last_error}. "
        f"Check that {TAIGA_BACK_CONTAINER} is running (`docker ps`) and "
        "publishes 127.0.0.1:8000."
    )


def _bearer_from_cfg(cfg: dict[str, str], api_root_hint: str) -> str:
    if cfg.get("auth_token"):
        return cfg["auth_token"]
    if cfg.get("username") and cfg.get("password"):
        # Prefer Docker/direct root for login when available.
        login_root = discover_taiga_back_api_root() or api_root_hint
        return obtain_bearer_token(login_root, cfg["username"], cfg["password"])
    raise RuntimeError(
        "Provide cabinet taiga.auth_token (preferred) or username/password."
    )


def parse_ref(ref: str) -> int:
    """Accept ``318``, ``TJW-318``, or ``tjw-318``."""
    text = ref.strip()
    match = re.fullmatch(r"(?i)(?:tjw-)?(\d+)", text)
    if not match:
        raise ValueError(f"Invalid ticket ref: {ref!r} (expected TJW-318 or 318)")
    return int(match.group(1))


class TaigaClient:
    """Fetch and finish TJW user stories."""

    def __init__(
        self,
        cfg: Optional[dict[str, str]] = None,
        project_slug: str = DEFAULT_PROJECT_SLUG,
    ) -> None:
        self.cfg = cfg or load_taiga_config()
        self.project_slug = project_slug
        hint = resolve_api_root(self.cfg) or discover_taiga_back_api_root() or ""
        self.bearer = _bearer_from_cfg(self.cfg, hint)
        self.api_root = resolve_working_api_root(
            self.cfg, self.bearer, project_slug=project_slug
        )
        self.project = fetch_project_by_slug(
            self.api_root, self.bearer, project_slug
        )
        self.project_id = int(self.project["id"])

    def get_ticket(self, ref: str | int) -> Ticket:
        """Load a user story by project ref (e.g. TJW-318 → 318)."""
        num = parse_ref(str(ref))
        r = requests.get(
            f"{self.api_root}/userstories/by_ref",
            params={"ref": num, "project": self.project_id},
            headers=auth_headers(self.bearer),
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"Failed to load TJW-{num} ({r.status_code}): {r.text[:500]}"
            )
        data = r.json()
        attachments = self._list_attachments(int(data["id"]))
        data["_attachments"] = attachments
        status_info = data.get("status_extra_info") or {}
        return Ticket(
            id=int(data["id"]),
            ref=int(data["ref"]),
            title=str(data.get("subject") or ""),
            description=str(data.get("description") or ""),
            status_name=str(status_info.get("name") or ""),
            version=int(data.get("version") or 1),
            project_id=self.project_id,
            project_slug=self.project_slug,
            raw=data,
        )

    def _list_attachments(self, story_id: int) -> list[dict[str, Any]]:
        r = requests.get(
            f"{self.api_root}/userstories/attachments",
            params={"object_id": story_id, "project": self.project_id},
            headers=auth_headers(self.bearer),
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        return data if isinstance(data, list) else []

    def download_attachments(
        self, ticket: Ticket, dest_dir: str | Path
    ) -> list[Path]:
        """Download ticket attachments into ``dest_dir``; return saved paths."""
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        for att in ticket.attachments:
            url = att.get("url")
            name = att.get("name") or f"attachment-{att.get('id')}"
            if not url:
                continue
            # Attachment URLs may be relative to the public site.
            if url.startswith("/"):
                url = urljoin(public_base_url(self.cfg) + "/", url.lstrip("/"))
            r = requests.get(
                url,
                headers=auth_headers(self.bearer),
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code != 200:
                continue
            path = dest / name
            path.write_bytes(r.content)
            saved.append(path)
        return saved

    def _status_id_by_name(self, status_name: str) -> int:
        statuses = fetch_userstory_statuses(
            self.api_root, self.bearer, self.project_id
        )
        for row in statuses:
            if _status_matches_selector(row, status_name):
                return int(row["id"])
        choices = ", ".join(
            f"{r.get('name')} ({r.get('slug')})" for r in statuses
        )
        raise RuntimeError(
            f"No Kanban status matches {status_name!r}. Available: {choices}"
        )

    def finish_ticket(
        self,
        ticket: Ticket | str | int,
        comment: str,
        status_name: Optional[str] = None,
    ) -> Ticket:
        """
        Move the story to the human-review column and attach a comment.

        Status defaults to cabinet ``backloggist.taiga_human_review_status``
        or ``Testing``.
        """
        if not isinstance(ticket, Ticket):
            ticket = self.get_ticket(ticket)

        if not status_name:
            try:
                from cabinet import Cabinet

                status_name = (
                    Cabinet().get(
                        "backloggist", "taiga_human_review_status", return_type=str
                    )
                    or "Testing"
                )
            except Exception:  # noqa: BLE001
                status_name = "Testing"
            status_name = str(status_name).strip() or "Testing"

        status_id = self._status_id_by_name(status_name)
        # Re-fetch for current version to avoid edit conflicts.
        current = self.get_ticket(ticket.ref)
        r = requests.patch(
            f"{self.api_root}/userstories/{current.id}",
            headers=auth_headers(self.bearer),
            json={
                "status": status_id,
                "version": current.version,
                "comment": comment,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            raise RuntimeError(
                f"Failed to finish TJW-{current.ref} ({r.status_code}): {r.text[:800]}"
            )
        return self.get_ticket(current.ref)

    def list_user_stories(
        self,
        status: Optional[str] = None,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Return user-story list payloads for the project.

        Pages through ``GET /userstories``. By default only stories in
        open (non-closed, non-archived) Kanban columns are included.
        """
        params: dict[str, Any] = {
            "project": self.project_id,
            "page_size": LIST_PAGE_SIZE,
        }
        if status:
            params["status"] = self._status_id_by_name(status)
        elif not include_all:
            params["status__is_archived"] = "false"
            params["status__is_closed"] = "false"

        stories: list[dict[str, Any]] = []
        page = 1
        while True:
            params["page"] = page
            r = requests.get(
                f"{self.api_root}/userstories",
                params=params,
                headers=auth_headers(self.bearer),
                timeout=REQUEST_TIMEOUT,
            )
            if r.status_code != 200:
                raise RuntimeError(
                    f"Failed to list user stories ({r.status_code}): {r.text[:800]}"
                )
            data = r.json()
            if not isinstance(data, list):
                raise RuntimeError(
                    f"Unexpected userstories payload: {type(data)}"
                )
            stories.extend(data)
            if not r.headers.get("x-pagination-next") or not data:
                break
            page += 1
            if page > 200:
                break
        return stories

    def list_story_rows(
        self,
        status: Optional[str] = None,
        include_all: bool = False,
    ) -> list[StorySummary]:
        """Return summarized tickets for ``ls``, with Kanban column order."""
        statuses = fetch_userstory_statuses(
            self.api_root, self.bearer, self.project_id
        )
        order_by_status = status_order_map(statuses)
        raw_stories = self.list_user_stories(
            status=status, include_all=include_all
        )
        return [summarize_story(raw, order_by_status) for raw in raw_stories]


def _cmd_get(args: argparse.Namespace) -> int:
    client = TaigaClient(project_slug=args.project_slug)
    ticket = client.get_ticket(args.ref)
    print(f"ref=TJW-{ticket.ref}")
    print(f"title={ticket.title}")
    print(f"status={ticket.status_name}")
    print(f"attachments={len(ticket.attachments)}")
    print("description=")
    print(ticket.description)
    if args.json:
        payload = {
            "ref": ticket.ref,
            "title": ticket.title,
            "status": ticket.status_name,
            "description": ticket.description,
            "attachments": ticket.attachments,
            "api_root": client.api_root,
        }
        print(json.dumps(payload, indent=2))
    return 0


def _cmd_finish(args: argparse.Namespace) -> int:
    client = TaigaClient(project_slug=args.project_slug)
    ticket = client.finish_ticket(
        args.ref, comment=args.comment, status_name=args.status
    )
    print(f"TJW-{ticket.ref} -> {ticket.status_name}")
    return 0


def _cmd_ls(args: argparse.Namespace) -> int:
    client = TaigaClient(project_slug=args.project_slug)
    rows = client.list_story_rows(
        status=args.status, include_all=args.all
    )
    rows = sort_story_rows(rows, args.sort, reverse=args.reverse)
    if args.json:
        payload = [
            {"ref": row.ref, "status": row.status_name, "subject": row.subject}
            for row in rows
        ]
        print(json.dumps(payload, indent=2))
        return 0
    grouped = args.sort == "status"
    sys.stdout.write(
        format_story_list(
            rows, group_by_status=grouped, color=sys.stdout.isatty()
        )
    )
    return 0


def _cmd_resolve_api(args: argparse.Namespace) -> int:
    cfg = load_taiga_config()
    hint = resolve_api_root(cfg) or discover_taiga_back_api_root() or ""
    bearer = _bearer_from_cfg(cfg, hint)
    root = resolve_working_api_root(
        cfg, bearer, project_slug=args.project_slug, persist=not args.no_persist
    )
    print(root)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch, list, and finish Taiga TJW tickets."
    )
    parser.add_argument(
        "--project-slug",
        default=DEFAULT_PROJECT_SLUG,
        help=f"Taiga project slug (default: {DEFAULT_PROJECT_SLUG})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    get_p = sub.add_parser("get", help="Print ticket title/description")
    get_p.add_argument("ref", help="Ticket ref, e.g. TJW-318 or 318")
    get_p.add_argument(
        "--json", action="store_true", help="Also print a JSON blob"
    )
    get_p.set_defaults(func=_cmd_get)

    finish_p = sub.add_parser(
        "finish", help="Move ticket to Testing (or configured column) with comment"
    )
    finish_p.add_argument("ref", help="Ticket ref, e.g. TJW-318 or 318")
    finish_p.add_argument(
        "--comment",
        required=True,
        help="Markdown comment (include PR links)",
    )
    finish_p.add_argument(
        "--status",
        default=None,
        help="Kanban column override (default: Testing / cabinet setting)",
    )
    finish_p.set_defaults(func=_cmd_finish)

    ls_p = sub.add_parser(
        "ls",
        help="List tickets by status (ref + summary); sortable",
    )
    ls_p.add_argument(
        "--status",
        default=None,
        metavar="NAME_OR_SLUG",
        help="Only this Kanban column (display name or slug)",
    )
    ls_p.add_argument(
        "--sort",
        choices=SORT_CHOICES,
        default="status",
        help="Sort by Kanban status (default), ticket number, or subject",
    )
    ls_p.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse the sort order",
    )
    ls_p.add_argument(
        "--all",
        action="store_true",
        help="Include closed and archived columns",
    )
    ls_p.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of a table",
    )
    ls_p.set_defaults(func=_cmd_ls)

    api_p = sub.add_parser(
        "resolve-api",
        help="Print a working api_root (updates cabinet unless --no-persist)",
    )
    api_p.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not write the working root back to cabinet taiga.api_root",
    )
    api_p.set_defaults(func=_cmd_resolve_api)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
