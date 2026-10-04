# OpenClaw

Personal OpenClaw skills and plugins that live next to the rest of `~/git/tools`.

| Path | What |
| --- | --- |
| [`diary/`](diary/) | Conversational Telegram diary (`/diary`) via `diary-llm` |
| [`food/`](food/) | Parse meals and log them with `foodlog` (`/food`) |
| [`words/`](words/) | Quiz definitions from `words_to_remember.md` (`/words`) |
| [`overflow-reset/`](overflow-reset/) | After context overflow, start a fresh session and retry once |
| [`delivery-retry/`](delivery-retry/) | Resend a Telegram reply OpenClaw dropped after an ambiguous send |
| [`media/`](media/) | Movies, TV, and music via Radarr, Sonarr, qBittorrent, and Sockseek |
| [`local-model/`](local-model/) | Load Gemma in LM Studio before a Cherry turn so chat does not fall back to OpenAI |

## Install

```bash
~/git/tools/openclaw/install.sh
```

That runs each skill's `scripts/install_openclaw.sh` (venv + plugin for diary,
plugin + 7pm reminder for food, plugin + evening word-recall tick). Workspace skill markdown is linked from
`~/git/dotfiles/openclaw/workspace/skills/` via
`~/git/dotfiles/scripts/link_ai_markdown.sh` when that repo is present.

Restart the gateway if commands do not show up:

```bash
openclaw gateway restart
```
