# Finance Transaction Parser

Imports a Robinhood credit-card CSV and a Venmo CSV from `~/Downloads` into [Sure](https://sure.tyler.cloud).

Cursor: see [AGENTS.md](AGENTS.md).

## Usage

```bash
python3 main.py              # arrow-pick Robinhood CSV, then Venmo CSV
python3 main.py --dry-run    # match only, no writes
python3 main.py --month 2026-09
```

With no arguments, the five newest CSVs in `~/Downloads` are listed with filename and last-modified time. Arrow keys move, Enter selects. Under the files, `skip Robinhood` or `skip Venmo` imports nothing for that institution. Add another institution by appending to `INSTITUTIONS` in `main.py`.

The preview is a table. Up and down scroll. Left sorts by date and right sorts by category; press the same arrow again to reverse. A red asterisk marks a row that updates an existing transaction. Enter continues to Keep, Undo, or Re-run Categories. Keep writes to Sure. Undo leaves Sure unchanged. Re-run Categories reloads `transaction_categories.json` and shows the table again before anything is posted.

Requires Cabinet keys `sure.api_key` and (optionally) `sure.base_url` / `sure.account_name` (Venmo). Robinhood uses the Sure account whose name starts with `Robinhood Credit Card` (`Robinhood Credit Card **4696`). Categories come from `~/syncthing/notes/docs/selfhosted/transaction_categories.json`.
