---
name: words
description: Word-recall quizzes from words_to_remember.md via the words plugin. Use for /words, /recall, and short replies to an open quiz. Do not quiz words in the main agent turn.
user-invocable: false
metadata:
  {
    "openclaw":
      {
        "emoji": "🔤",
        "requires": { "bins": ["python3"] },
      },
  }
---

# Word recall

Quizzes are handled **only** by the `words` OpenClaw plugin (`words_cli.py`).

## Hard rules

- Never invent a parallel quiz in the main session.
- Never claim a word was added, graded, or moved unless the plugin said so.
- A normal chat is not an answer unless a quiz is already waiting and the reply is a short word guess.
- Definitions live in `~/syncthing/notes/words_to_remember.md`.

## Commands

```bash
python3 ~/git/tools/openclaw/words/scripts/words_cli.py handle "/words"
python3 ~/git/tools/openclaw/words/scripts/words_cli.py handle "/words add ephemeral — lasting for a very short time"
python3 ~/git/tools/openclaw/words/scripts/words_cli.py list
python3 ~/git/tools/openclaw/words/scripts/words_cli.py tick
```

## Flow

1. `/words` or `/recall` asks for the word that matches a definition
2. A short reply while a quiz is open is graded by the plugin
3. Three correct recalls move the word under `## Completed`
4. Every 2 hours the tick may send one quiz, only between 5pm and 9pm, and only after a random 3–5 day gap. Diary is on its own 3–5 day clock.
5. An empty active list gets one college-level word chosen for you; completed words come back about every three weeks
