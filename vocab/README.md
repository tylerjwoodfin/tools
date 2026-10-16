# vocab

Add a word to Cherry's vocabulary list.

```bash
vocab luminous
```

That appends `luminous` to `~/syncthing/network/vocab.json` with `times_asked` and `times_correct` set to 0. The file is a JSON array:

```json
[
  {
    "name": "luminous",
    "times_asked": 0,
    "times_correct": 0
  }
]
```

The first run creates the file from `~/syncthing/notes/words_to_remember.md`. Recall counts come from `~/.local/share/word-recall/state.json` when that file exists: `times_correct` is the stored correct streak, and `times_asked` is that streak plus one when the last result was wrong.

On hosts other than ice and icecream, the shell alias runs `cloud vocab` so the list is updated on the synced copy.
