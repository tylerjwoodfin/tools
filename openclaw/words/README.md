# /words

OpenClaw plugin that quizzes definitions from `~/syncthing/notes/words_to_remember.md`.

## What it does

- `/words` (or `/recall`) sends a definition and waits for the word
- `/words add ephemeral — lasting for a very short time` adds a card
- `/words list` shows the deck; `/words skip` drops the open quiz
- A short reply while a quiz is open is graded without the main session model
- Three correct recalls move the word to `## Completed`
- Completed words are asked again about every three weeks, or immediately with `/words`
- If Active is empty, Cherry picks one college-level everyday word and adds it
- A tick every two hours may send one quiz between 5pm and 9pm Pacific, then waits 2–4 days (same window as diary)

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
