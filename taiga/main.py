"""
Create user stories on a Taiga Kanban board from the command line.

Reads Taiga connection settings from environment variables (highest priority)
or from `Cabinet` under the ``taiga`` key::

    {
        "taiga": {
            "base_url": "https://taiga.example.com",
            "username": "me@example.com",
            "password": "…"
        }
    }

Environment variables (optional)::

    TAIGA_BASE_URL   — origin only, e.g. https://taiga.example.com (no /api/v1)
    TAIGA_API_ROOT   — full API base, e.g. http://172.30.0.10:8000/api/v1 (see below)
    TAIGA_USERNAME   — login username or email
    TAIGA_PASSWORD   — login password
    TAIGA_AUTH_TOKEN — if set, used as Bearer token; username/password ignored

If your public URL sits behind Authentik (or similar), ``POST /api/v1/auth`` may be
redirected to an HTML login flow and JSON parsing will fail. In that case set
``TAIGA_API_ROOT`` (or cabinet ``taiga.api_root``) to a URL that reaches
**taiga-back** directly from the machine running this script (often the Docker
bridge IP on port 8000, e.g. ``http://172.25.0.10:8000/api/v1`` — get the IP with
``docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <taiga-back-container>``).

By default the script targets project slug ``tjw`` and places the story in the
**New** column (display name or slug ``new``). Use ``--status`` for another column.

Usage::

    python main.py --name "Short title" --description "Longer body (Markdown ok)"
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

DEFAULT_PROJECT_SLUG = "tjw"
REQUEST_TIMEOUT = 45


def api_v1_root(base_url: str) -> str:
    """Return the Taiga REST API root ``…/api/v1`` for a site origin."""
    return base_url.rstrip("/") + "/api/v1"


def resolve_api_root(cfg: dict[str, str]) -> str:
    """
    Return the Taiga API v1 root URL.

    Prefers ``cfg["api_root"]`` (full ``…/api/v1``) when set; otherwise derives
    ``{base_url}/api/v1``.
    """
    direct = (cfg.get("api_root") or "").strip().rstrip("/")
    if direct:
        return direct
    base = (cfg.get("base_url") or "").strip()
    if not base:
        return ""
    return api_v1_root(base)


def load_taiga_config() -> dict[str, str]:
    """
    Merge Taiga settings from environment variables and Cabinet config.

    Returns:
        Dict with ``base_url``, optional ``api_root`` (full ``…/api/v1``),
        ``username``, ``password``, and optional ``auth_token``, filled from the
        environment first, then Cabinet for any missing entries.
    """
    cfg: dict[str, str] = {
        "base_url": (os.environ.get("TAIGA_BASE_URL") or "").strip(),
        "api_root": (os.environ.get("TAIGA_API_ROOT") or "").strip().rstrip("/"),
        "username": (os.environ.get("TAIGA_USERNAME") or "").strip(),
        "password": (os.environ.get("TAIGA_PASSWORD") or "").strip(),
        "auth_token": (os.environ.get("TAIGA_AUTH_TOKEN") or "").strip(),
    }
    if not Cabinet:
        return cfg
    cabinet = Cabinet()
    if not cfg["base_url"]:
        val = cabinet.get("taiga", "base_url", return_type=str) or ""
        cfg["base_url"] = str(val).strip()
    if not cfg["auth_token"]:
        val = cabinet.get("taiga", "auth_token", return_type=str) or ""
        cfg["auth_token"] = str(val).strip()
    if not cfg["username"]:
        val = cabinet.get("taiga", "username", return_type=str) or ""
        cfg["username"] = str(val).strip()
    if not cfg["password"]:
        val = cabinet.get("taiga", "password", return_type=str) or ""
        cfg["password"] = str(val).strip()
    if not cfg["api_root"]:
        val = cabinet.get("taiga", "api_root", return_type=str) or ""
        cfg["api_root"] = str(val).strip().rstrip("/")
    return cfg


def obtain_bearer_token(api_root: str, username: str, password: str) -> str:
    """
    Perform normal-user login and return a short-lived API Bearer token.

    Raises:
        RuntimeError: if login fails or the response omits ``auth_token``.
    """
    url = f"{api_root}/auth"
    payload = {"type": "normal", "username": username, "password": password}
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    r = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        allow_redirects=False,
    )
    text = (r.text or "").strip()
    preview = text[:900] if text else "(empty body)"

    if r.status_code in (301, 302, 303, 307, 308):
        loc = r.headers.get("Location", "")
        raise RuntimeError(
            "Taiga /auth was redirected (HTTP "
            f"{r.status_code}) — usually Authentik or another SSO proxy blocking "
            "the API login. Set TAIGA_API_ROOT / cabinet taiga.api_root to the "
            "taiga-back URL reachable from this host (e.g. "
            "http://<docker-bridge-ip>:8000/api/v1). "
            f"Location: {loc!r}"
        )

    if r.status_code != 200:
        raise RuntimeError(
            f"Taiga login failed (HTTP {r.status_code}). Response preview: {preview!r}"
        )

    content_type = (r.headers.get("Content-Type") or "").lower()
    looks_like_html = text.lstrip().lower().startswith("<!") or "<html" in text[:200].lower()
    if looks_like_html or ("json" not in content_type and text and not text.lstrip().startswith("{")):
        raise RuntimeError(
            "Taiga /auth did not return JSON (got HTML or another format). "
            "This usually means requests are hitting a reverse proxy login page "
            "(Authentik, Cloudflare) instead of taiga-back, or the URL is wrong. "
            "Fix TAIGA_BASE_URL / tunnel routing, or set TAIGA_AUTH_TOKEN / "
            "cabinet taiga.auth_token (API token) instead of password login. "
            f"Content-Type={r.headers.get('Content-Type')!r}. Preview: {preview!r}"
        )

    try:
        data = r.json()
    except ValueError as exc:
        raise RuntimeError(
            "Taiga /auth returned invalid JSON. Password login may be unavailable "
            "with SSO-only accounts — use taiga.auth_token. "
            f"Preview: {preview!r}"
        ) from exc
    token = data.get("auth_token")
    if not token:
        raise RuntimeError(f"Taiga login returned no auth_token: {data!r}")
    return str(token)


def auth_headers(bearer: str) -> dict[str, str]:
    """Build default headers for authenticated Taiga API requests."""
    return {
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def fetch_project_by_slug(
    api_root: str, bearer: str, slug: str
) -> dict[str, Any]:
    """
    Load a single project by slug via ``GET /projects/by_slug``.

    Raises:
        RuntimeError: if the project is missing or the request fails.
    """
    url = f"{api_root}/projects/by_slug"
    r = requests.get(
        url,
        params={"slug": slug},
        headers=auth_headers(bearer),
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code != 200:
        raise RuntimeError(
            f"Failed to load project '{slug}' ({r.status_code}): {r.text[:500]}"
        )
    return r.json()


def fetch_userstory_statuses(
    api_root: str, bearer: str, project_id: int
) -> list[dict[str, Any]]:
    """Return all user-story statuses for a project (Kanban columns)."""
    url = f"{api_root}/userstory-statuses"
    r = requests.get(
        url,
        params={"project": project_id},
        headers=auth_headers(bearer),
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code != 200:
        raise RuntimeError(
            f"Failed to list User Story statuses ({r.status_code}): {r.text[:500]}"
        )
    data = r.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected userstory-statuses payload: {type(data)}")
    return data


def _status_matches_selector(
    row: dict[str, Any], selector: str
) -> bool:
    """Return True if a status row matches a user-provided name or slug."""
    sel = selector.strip()
    if not sel:
        return False
    name = (row.get("name") or "").strip().lower()
    slug = (row.get("slug") or "").strip().lower()
    sel_l = sel.lower()
    return name == sel_l or slug == sel_l or slug == sel_l.replace(" ", "-")


def resolve_kanban_status_id(
    statuses: list[dict[str, Any]], status_selector: str | None
) -> tuple[int, str]:
    """
    Pick the Kanban column id for a new user story.

    If ``status_selector`` is set, the first non-archived status whose name or
    slug matches (case-insensitive) is used.

    Otherwise a non-archived status matching display name **New** or slug
    ``new`` is used.

    Returns:
        ``(status_id, status_name)`` for logging and success output.

    Raises:
        RuntimeError: if no suitable status exists.
    """
    active = [s for s in statuses if not s.get("is_archived")]

    if status_selector:
        for row in active:
            if _status_matches_selector(row, status_selector):
                return int(row["id"]), str(row["name"])
        choices = ", ".join(
            f"{r.get('name')} ({r.get('slug')})" for r in sorted(active, key=lambda x: x.get("order", 0))
        )
        raise RuntimeError(
            f"No Kanban status matches {status_selector!r}. Available: {choices}"
        )

    for row in active:
        name = (row.get("name") or "").strip().lower()
        slug = (row.get("slug") or "").strip().lower()
        if name == "new" or slug == "new":
            return int(row["id"]), str(row["name"])

    choices = ", ".join(
        f"{r.get('name')} ({r.get('slug')})" for r in sorted(active, key=lambda x: x.get("order", 0))
    )
    raise RuntimeError(
        f"No 'New' status found. Set --status, or add a column in Taiga. "
        f"Available: {choices}"
    )


def create_user_story(
    api_root: str,
    bearer: str,
    project_id: int,
    status_id: int,
    subject: str,
    description: str,
) -> dict[str, Any]:
    """
    Create a user story via ``POST /userstories``.

    Returns:
        Parsed JSON object for the new story (includes ``id``, ``ref``, etc.).

    Raises:
        RuntimeError: on non-success HTTP status.
    """
    url = f"{api_root}/userstories"
    body: dict[str, Any] = {
        "project": project_id,
        "subject": subject,
        "description": description,
        "status": status_id,
    }
    r = requests.post(
        url,
        json=body,
        headers=auth_headers(bearer),
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(
            f"Create user story failed ({r.status_code}): {r.text[:1200]}"
        )
    return r.json()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Build the CLI argument parser for ``main.py``."""
    parser = argparse.ArgumentParser(
        description="Create a Taiga Kanban user story on project TJW (or another slug)."
    )
    parser.add_argument(
        "--name",
        required=True,
        help="User story subject (title shown on the card).",
    )
    parser.add_argument(
        "--description",
        required=True,
        help="Longer description; Taiga accepts Markdown.",
    )
    parser.add_argument(
        "--project-slug",
        default=DEFAULT_PROJECT_SLUG,
        help=(
            f"Taiga project slug (default: {DEFAULT_PROJECT_SLUG!r}). "
            "Your TJW board uses slug 'tjw'."
        ),
    )
    parser.add_argument(
        "--status",
        default=None,
        metavar="NAME_OR_SLUG",
        help=(
            "Kanban column: match display name or slug (e.g. 'In progress', 'in-progress'). "
            "Default: 'New'."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """
    Entry point: authenticate, resolve column, create user story.

    Returns:
        Process exit code ``0`` on success, ``1`` on recoverable failure.
    """
    args = parse_args(argv)
    cfg = load_taiga_config()

    api_root = resolve_api_root(cfg)
    if not api_root:
        print(
            "Set TAIGA_BASE_URL (site origin) and/or TAIGA_API_ROOT (full …/api/v1), "
            "or cabinet taiga.base_url / taiga.api_root.",
            file=sys.stderr,
        )
        return 1

    try:
        if cfg.get("auth_token"):
            bearer = cfg["auth_token"]
        elif cfg["username"] and cfg["password"]:
            bearer = obtain_bearer_token(api_root, cfg["username"], cfg["password"])
        else:
            print(
                "Provide TAIGA_AUTH_TOKEN or both TAIGA_USERNAME and TAIGA_PASSWORD "
                "(or cabinet taiga.auth_token / username / password).",
                file=sys.stderr,
            )
            return 1

        project = fetch_project_by_slug(api_root, bearer, args.project_slug)
        project_id = int(project["id"])
        statuses = fetch_userstory_statuses(api_root, bearer, project_id)
        status_id, status_name = resolve_kanban_status_id(statuses, args.status)

        created = create_user_story(
            api_root,
            bearer,
            project_id,
            status_id,
            args.name,
            args.description,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    ref = created.get("ref")
    sid = created.get("id")
    print(
        f"Created user story id={sid} ref=#{ref} in column {status_name!r} "
        f"(project slug={args.project_slug})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

