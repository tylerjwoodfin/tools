# Tools
- This repository serves as a centralized location for various tools and scripts that have been customized to streamline my personal workflow.
- This is all organized into folders, each representing a specific aspect of my workflow and containing relevant tools and scripts.
- Feel free to use this code as you see fit (within the bounds of the license), but don't expect it to work on your machine.

## Recommended: Cabinet
- If you intend to run any of this in any meaningful way, you'll need [cabinet](https://pypi.org/project/cabinet/), my utility for storing and managing variables across projects.

## OpenClaw
- [`openclaw/`](openclaw/) — personal OpenClaw skills: conversational diary (`/diary`) and food logging (`/food`).

## Life-ops MCP
- [`lifeops-mcp/`](lifeops-mcp/) — stdio MCP server exposing Cabinet, RemindMail, foodlog, milestone, and Immich search to Cursor.

## Vikunja / GitHub agent helpers
- [`vikunja/ticket.py`](vikunja/ticket.py) — fetch/list/finish TJW tickets (`get`, `ls`, `finish`) via `http://127.0.0.1:3456/api/v1`.
- [`github/ensure_gh_auth.py`](github/ensure_gh_auth.py) — sync Cabinet `backloggist.github_token` into `gh` auth.

## Amazon order (Playwright)
- [`amazon/`](amazon/) — `amazon <description>` searches Amazon, uses ChatGPT to pick a match, confirms, and places the order. Optional browser server: `~/git/docker/playwright`.

## See Other READMEs
- Most folders contain a README that you should check out for more specific information. Happy coding!