# /words

OpenClaw plugin that quizzes definitions from `~/syncthing/notes/words_to_remember.md`.

## What it does

- `/words` (or `/recall`) asks for a word. The question is sometimes the stored definition, sometimes "what word starting with B means …?" with a definition written at ask time, and sometimes a fill-in-the-blank sentence (`b____`)
- `/words add ephemeral — lasting for a very short time` adds a card
- `/words list` shows the deck; `/words skip` drops the open quiz
- A short reply while a quiz is open is graded without the main session model
- Three correct recalls move the word to `## Completed`
- Completed words are asked again about every three weeks, or immediately with `/words`
- If the list has fewer than 10 words, Cherry sometimes quizzes a new college-level word instead. The chance is (10 − count) × 10% (8 words → 20%). A word you get right on the first try is marked completed (3/3). A miss is added under Active at 0/3.
- A tick every two hours may send one quiz between 5pm and 9pm Pacific, then waits a random 3–5 days. An unanswered quiz holds that slot only until the next window, then a new question replaces it. Diary uses the same window on its own clock, so they sometimes land on the same evening and sometimes do not.
- Words in `~/syncthing/network/vocab.json` that are not already on the deck are quizzed too. `vocab --list` shows that file; `vocab -rm <word>` removes one.

## List file

```markdown
## Active

- **ephemeral** — lasting for a very short time

## Completed

- **serendipity** — a happy accident
```

Recall counts live in `~/.local/share/word-recall/state.json`.

## Install

```bash
~/git/tools/openclaw/words/scripts/install_openclaw.sh
```

Restart the gateway after install:

```bash
~/git/tools/openclaw/openclaw-gateway gateway restart
```
