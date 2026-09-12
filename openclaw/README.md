# OpenClaw

Personal OpenClaw skills and plugins that live next to the rest of `~/git/tools`.

| Path | What |
| --- | --- |
| [`diary/`](diary/) | Conversational Telegram diary (`/diary`) via `diary-llm` |
| [`food/`](food/) | Parse meals and log them with `foodlog` (`/food`) |

## Install

```bash
~/git/tools/openclaw/install.sh
```

That runs each skill's `scripts/install_openclaw.sh` (venv + plugin for diary, workspace skill + 7pm reminder for food).

Restart the gateway if commands do not show up:

```bash
openclaw gateway restart
```
