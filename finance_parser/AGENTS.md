# Finance parser

Import Tyler's latest **Venmo** statement into self-hosted Sure.

## When to use this

The user asks to import Venmo transactions, load the latest Venmo statement, or sync Venmo into Sure / the budget.

Do **not** import EverBank or Schwab. Do **not** update a spreadsheet.

## What to run

From this directory:

```bash
python3 main.py
```

Preview without writing:

```bash
python3 main.py --dry-run
```

Optional flags:

- `--file /path/to/VenmoStatement_….csv` — skip Downloads lookup
- `--month YYYY-MM` — import that month instead of the previous calendar month
- `--categories /path/to/transaction_categories.json`

Exit `0` with a create/update/skip summary means it worked. If it errors, fix the cause (missing CSV, Cabinet key, Sure down) and retry. Do not invent a parallel importer.

## File location

1. Newest `~/Downloads/VenmoStatement*.csv` (same glob as before).
2. If none exist, tell the user to download the monthly statement from Venmo (Activity → statements) into Downloads. Do not open a file picker.

Default window is **the previous calendar month** (on 1 Sep that is August).

## Sure

- UI: `https://sure.tyler.cloud` (Authentik). The parser talks to the LAN API because Authentik does not skip `/api`.
- Compose / docs: `cloud:~/git/docker/sure.am`
- Account: **Venmo** (already Plaid-synced). This tool matches CSV rows onto those transactions (date + signed amount, then note/counterparty), updates the Sure **name** to the Venmo note and **category** from keywords, and **creates** only rows Sure does not already have.
- It will not replace a more specific Sure category with `Other`, and it will not stamp the `Other` category (leave unmatched notes uncategorized).
- Re-runs are safe: matched rows that already have the same name/category are skipped; creates use Venmo's statement `ID` as `external_id` / `source=venmo`.

## Credentials (Cabinet)

Never print or commit these.

| Key | Purpose |
|-----|---------|
| `sure.api_key` | Sure `X-Api-Key` (`read_write`, name `finance_parser`) |
| `sure.base_url` | Default `http://192.168.1.101:3006` |
| `sure.account_name` | Default `Venmo` |

If `sure.api_key` is missing, create a key in Sure **Settings → API Key** (or reuse `finance_parser` via Rails `ApiKey#plain_key` on `sure-web`) and `cabinet put sure api_key --value <key>` on the Mac running Cursor. Local and `cloud` Cabinets are separate MongoDBs.

## Categories

Shared with Sure rule sync:

`~/syncthing/notes/docs/selfhosted/transaction_categories.json`

Keyword lists live under `categories`. `filteredRows` drops matching notes. After editing that file, category **rules** in Sure are updated with `~/git/docker/sure.am/scripts/sync-category-rules.sh` on `cloud` — not by this parser.

## After import

Summarize create/update/skip counts. Mention leftover uncategorized (`Other`) notes so the user can fix keywords or recategorize in Sure.
