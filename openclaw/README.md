# OpenClaw

Personal OpenClaw skills and plugins that live next to the rest of `~/git/tools`.

| Path | What |
| --- | --- |
| [`diary/`](diary/) | Conversational Telegram diary (`/diary`) via `diary-llm` |
| [`food/`](food/) | Parse meals and log them with `foodlog` (`/food`) |
| [`words/`](words/) | Quiz definitions from `words_to_remember.md` (`/words`) |
| [`overflow-reset/`](overflow-reset/) | After context overflow, start a fresh session and retry once |

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
