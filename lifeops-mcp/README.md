# Life-ops MCP

Stdio [MCP](https://modelcontextprotocol.io/) server that wraps Tyler's personal life-ops CLIs for Cursor (and other MCP clients).

## Tools

| Tool | Wraps |
|------|--------|
| `cabinet_get` / `cabinet_put` | `cabinet --get` / `--put` (sensitive keys redacted on get) |
| `remind_save` | `remind --save --when … --title …` |
| `foodlog_add` | `~/git/tools/foodlog/main.py <food> <calories>` |
| `milestone_add` | `~/git/tools/milestone/main.py <text>` |
| `immich_search` | Immich HTTP API (`/api/search/smart`) |

## Setup

```bash
cd ~/git/tools/lifeops-mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Immich (optional)

```bash
cabinet --put immich api_url https://immich.tyler.cloud   # your URL
cabinet --put immich api_key <api-key-from-immich-settings>
```

### Cursor `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "life-ops": {
      "command": "/home/tyler/git/tools/lifeops-mcp/.venv/bin/python",
      "args": ["/home/tyler/git/tools/lifeops-mcp/server.py"]
    }
  }
}
```

Restart Cursor (or reload MCP) after editing.

## Skill

See `~/git/dotfiles/.cursor/skills/life-ops/` (symlinked as `~/.cursor/skills/life-ops`).

## Smoke test

```bash
# List tools via MCP inspector if installed, or import-check:
.venv/bin/python -c "import server; print([t for t in dir(server) if not t.startswith('_')])"
```

Do not print to stdout from this server except via the MCP SDK — stdout is the transport.
