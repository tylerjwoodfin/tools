---
name: diary
description: Conversational Telegram diary via diary-llm. Use for /diary, active diary sessions, proactive journaling, and finishing entries. Never treat normal chats as diary entries.
user-invocable: false
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

Conversational journaling is handled **only** by the `diary-llm` CLI / OpenClaw plugin.

## Hard rules

- Never invent a parallel diary flow.
- Never claim an entry was saved unless `diary-llm done` (or auto-finalize) returned JSON with `"action": "finalized"` and an `entry_path`.
- If tools are unavailable, say so plainly. Do **not** pretend the file was written.
- Normal Telegram chats are not diary sessions.
- Prefer `/diary` (plugin command). Do not freehand journal replies in the main agent turn.

## Commands

```bash
diary-llm status --json
diary-llm start
diary-llm reply "user text"
diary-llm done
diary-llm tick
```

Entries: `~/syncthing/notes/diary/YYYY/MM/YYYY-MM-DD.md`  
Raw transcripts: `~/syncthing/notes/diary/conversations/<session-id>.json`

## Flow

1. `/diary` → `diary-llm start` → send opening question
2. Active session → every user reply through `diary-llm reply`
3. Close via `/diary done`, model closing words, or inactivity tick
