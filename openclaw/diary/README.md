# diary-llm

Conversational AI diary for [OpenClaw](https://docs.openclaw.ai): natural Telegram journaling, proactive reflection prompts every few days, and Markdown diary entries.

## What it does

- `/diary` starts (or continues) a diary session on Telegram
- Follow-ups stay conversational — one question at a time, no fixed questionnaire
- `/diary done` finishes early; inactivity (~3h, configurable) finalizes automatically
- Sessions become first-person Markdown under `syncthing/notes/diary/YYYY/MM/`
- Raw transcripts are kept in `diary/conversations/<session-id>.json`
- Cron tick sends non-generic prompts every ~2–4 days during evening hours
- Normal OpenClaw chats are never treated as diary entries unless a session is active

## Install

```bash
~/git/tools/openclaw/diary/scripts/install_openclaw.sh
```

This will:

1. Create a venv and install `diary-llm` plus local Cabinet (`telegram.target` lives there)
2. Write `~/.config/diary-llm/config.yaml` from the example (if missing)
3. Install the workspace skill + link the OpenClaw plugin
4. Register an `openclaw cron` job for `diary-llm tick`

Restart the gateway after install if needed:

```bash
openclaw gateway restart
```

## CLI

```bash
diary-llm status
diary-llm start
diary-llm reply "Probably this whole situation at work with QA."
diary-llm done
diary-llm tick
```

Use `--stub-llm` for offline/deterministic runs and `--dry-run` to skip Telegram sends.

## Config

See `config.example.yaml`. Important knobs:

| Key | Purpose |
| --- | --- |
| `diary_dir` | Markdown diary root |
| Cabinet `telegram.target` | Telegram chat id (`cabinet -p telegram target …`) |
| `proactive.*` | Cadence + allowed hours |
| `inactivity_timeout_hours` | Auto-finalize window |
| `history.*` | How much prior diary context to feed the LLM |
| `llm.*` | Model backend (`openai`, `openclaw`, or `stub`) |

## Tests

```bash
cd ~/git/tools/openclaw/diary
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
```
