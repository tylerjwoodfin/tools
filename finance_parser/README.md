# Finance Transaction Parser

Reads the latest Venmo statement CSV from `~/Downloads` and imports it into [Sure](https://sure.tyler.cloud).

Cursor: see [AGENTS.md](AGENTS.md).

## Usage

```bash
python3 main.py              # previous calendar month → Sure
python3 main.py --dry-run    # match only, no writes
python3 main.py --month 2026-08
```

Amazon orders (previous calendar month) use the Firefox Order History Exporter, then the Sure API on cloud:

```bash
python3 amazon.py
python3 amazon.py --dry-run
python3 amazon.py --month 2026-08
python3 amazon.py --file ~/Downloads/amazon-orders-2026-08-01.csv
```

`launchd/com.tyler.amazon-sure.plist` runs that at 03:00 local time on the 1st. The Mac has to be awake. Cherry sends a Telegram note when it finishes.

Requires Cabinet keys `sure.api_key` and (optionally) `sure.base_url`. Categories come from `~/syncthing/notes/docs/selfhosted/transaction_categories.json`.
