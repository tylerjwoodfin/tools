"""
Taiga ticket helpers for the Cursor taiga-ticket skill.

Provides get/finish for TJW-### stories without depending on the removed
backloggist package. Resolves ``taiga.api_root`` with Docker discovery when
the stored bridge IP is stale.
"""

from __future__ import annotations

import argparse
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
PROBE_PATH = "/projects/by_slug"


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
            timeout=8,
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


def resolve_working_api_root(
    cfg: dict[str, str],
    bearer: str,
    project_slug: str = DEFAULT_PROJECT_SLUG,
    persist: bool = True,
) -> str:
    """
    Return a reachable Taiga API root.

    Tries configured ``api_root``, then Docker-discovered taiga-back, then
    ``{base_url}/api/v1``. Persists a working Docker/discovered root to Cabinet
    when it differs from the stored value.
    """
    candidates: list[str] = []
    configured = resolve_api_root(cfg)
    if configured:
        candidates.append(configured.rstrip("/"))
    discovered = discover_taiga_back_api_root()
    if discovered and discovered not in candidates:
        candidates.append(discovered)
    base = (cfg.get("base_url") or "").strip().rstrip("/")
    if base:
        derived = f"{base}/api/v1"
        if derived not in candidates:
            candidates.append(derived)

    if not candidates:
        raise RuntimeError(
            "No Taiga API root configured. Set cabinet taiga.api_root or start "
            f"Docker container {TAIGA_BACK_CONTAINER}."
        )

    last_error = ""
    for root in candidates:
        if _probe_api_root(root, bearer, project_slug):
            if persist and configured and root != configured.rstrip("/"):
                _persist_api_root(root)
            elif persist and not configured:
                _persist_api_root(root)
            return root
        last_error = f"unreachable or unauthorized: {root}"

    raise RuntimeError(
        "Could not reach Taiga API. Tried: "
        + ", ".join(candidates)
        + f". Last error: {last_error}. "
        f"Check that {TAIGA_BACK_CONTAINER} is running (`docker ps`)."
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
        description="Fetch/finish Taiga TJW tickets for the Cursor agent workflow."
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
