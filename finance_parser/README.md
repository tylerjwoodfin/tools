# Finance Transaction Parser

Reads the latest Venmo statement CSV from `~/Downloads` and imports it into [Sure](https://sure.tyler.cloud).

Cursor: see [AGENTS.md](AGENTS.md).

## Usage

```bash
python3 main.py              # previous calendar month → Sure
python3 main.py --dry-run    # match only, no writes
python3 main.py --month 2026-08
```

Requires Cabinet keys `sure.api_key` and (optionally) `sure.base_url`. Categories come from `~/syncthing/notes/docs/selfhosted/transaction_categories.json`.
