# Tools
- This repository serves as a centralized location for various tools and scripts that have been customized to streamline my personal workflow.
- This is all organized into folders, each representing a specific aspect of my workflow and containing relevant tools and scripts.
- Feel free to use this code as you see fit (within the bounds of the license), but don't expect it to work on your machine.

## Recommended: Cabinet
- If you intend to run any of this in any meaningful way, you'll need [cabinet](https://pypi.org/project/cabinet/), my utility for storing and managing variables across projects.

## Life-ops MCP
- [`lifeops-mcp/`](lifeops-mcp/) — stdio MCP server exposing Cabinet, RemindMail, foodlog, milestone, and Immich search to Cursor.

## Taiga / GitHub agent helpers
- [`taiga/ticket.py`](taiga/ticket.py) — fetch/finish TJW tickets for Cursor (`get`, `finish`, `resolve-api`); auto-heals stale Docker `api_root`.
- [`github/ensure_gh_auth.py`](github/ensure_gh_auth.py) — sync Cabinet `backloggist.github_token` into `gh` auth.

## See Other READMEs
- Most folders contain a README that you should check out for more specific information. Happy coding!