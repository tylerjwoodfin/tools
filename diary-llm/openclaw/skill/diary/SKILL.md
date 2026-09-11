---
name: diary
description: Conversational Telegram diary via diary-llm. Use for /diary, active diary sessions, proactive journaling, and finishing entries. Never treat normal chats as diary entries.
metadata:
  {
    "openclaw":
      {
        "emoji": "📓",
        "requires": { "bins": ["diary-llm"] },
      },
  }
---

# Diary

Conversational journaling is handled by `diary-llm`. Prefer the `/diary` slash command and the installed `diary-llm` OpenClaw plugin. Do not invent a parallel diary flow.

## Rules

- Normal Telegram chats are **not** diary sessions.
- A diary session starts only via `/diary`, `diary-llm start`, or a proactive cron tick.
- If a diary session is already active, continue it — never start a second one.
- Usually ask **one** follow-up question at a time.
- Do not force a fixed questionnaire or a fixed number of questions.
- When generating entries, stay conservative: first person, only what was said, no invented psychology.

## Commands

```bash
diary-llm status --json
diary-llm start --stub-llm          # manual start (tests); omit --stub-llm in prod
diary-llm reply "user text"
diary-llm done
diary-llm tick                      # inactivity finalize + maybe proactive prompt
```

Config lives at `~/.config/diary-llm/config.yaml`. Entries are stored under the configured `diary_dir` as `YYYY/MM/YYYY-MM-DD.md`. Raw conversations are preserved in `conversations/<session-id>.json`.

## Manual flow

1. User sends `/diary` (or asks to journal).
2. Run `diary-llm start` if needed; send the returned opening question.
3. While `diary-llm status` reports `active: true`, route user replies through `diary-llm reply`.
4. User can send `/diary done`, or inactivity finalization will save the entry later.

## Proactive flow

OpenClaw cron runs `diary-llm tick` periodically. It will:

- finalize timed-out active sessions
- skip if a session is already active
- otherwise send a non-generic reflection question every ~2–4 days during allowed evening hours
