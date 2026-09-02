# Finance parser

Import bank, card, Venmo, and other CSVs into self-hosted Sure (`https://sure.tyler.cloud`).

`main.py` currently automates **Venmo** (latest `VenmoStatement*.csv` → previous calendar month). For other institutions, import with the Sure API using the same conventions below. Do **not** update a spreadsheet. Do **not** invent a second budget system.

Household facts (pay, property, debt, last month’s numbers) live **only** in the private file `~/git/backend/finances/AGENTS.md`. Do **not** copy balances, salary, addresses, loan rates, or people’s names into this file.

## When to use this

- **Import:** the user asks to import transactions, load a statement CSV, or sync a download into Sure / the budget — Venmo, EverBank, Robinhood Credit Card, Amazon orders, or another CSV they name. If they point at a specific file, use that file. Otherwise pick the newest matching download in `~/Downloads`.
- **Monthly recap:** the user asks to summarize finances, recap a month, or review Sure spending. Read `~/git/backend/finances/AGENTS.md` first, then follow **Monthly recap** below. After the recap, update that file’s **Last snapshot**.

## Venmo (parser)

```bash
cd ~/git/tools/finance_parser
python3 main.py              # previous calendar month → Sure Venmo
python3 main.py --dry-run
python3 main.py --file /path/to/VenmoStatement_….csv
python3 main.py --month YYYY-MM
```

Looks for the newest `~/Downloads/VenmoStatement*.csv`. If none exist, tell the user to download the monthly statement from Venmo (Activity → statements) into Downloads. Do not open a file picker.

Exit `0` with a create/update/skip summary means it worked.

## Other CSVs (Sure API)

`main.py` is Venmo-only until it grows. For anything else, import via the LAN Sure API (do not wait on a parser rewrite unless the user asks). Typical Downloads globs:

| Source | Typical file | Sure account |
|--------|----------------|--------------|
| Venmo | `VenmoStatement*.csv` | `Venmo` |
| EverBank | `Transactions_*.csv` (cols: Date, Check#, Transaction Type, Description, Debits(-), Credits(+)) | `Everbank` |
| Robinhood CC | UUID-named CSV with `Cardholder,Amount,Points,Balance,Status,Type,Merchant,Description` | `Robinhood Credit Card` |
| Amazon orders | `amazon-orders-*.csv` (line items) | `Amazon Credit Card [Ally Checking]` |

List accounts with `GET /api/v1/accounts` and match by name (do not hard-code IDs).

### CSV shape notes

- **EverBank:** `Debits(-)` are usually already negative (money out → Sure `expense`); `Credits(+)` are money in → `income`. Parse `$` and commas. Date is `MM/DD/YYYY`.
- **Robinhood CC:** Keep `Status == Posted`. Skip `$0` rows. Positive `Amount` = purchase (`expense`); negative = refund/payment (`income`). Use Merchant as `name`, Description as `notes`.
- **Amazon orders:** Many rows share an `Order ID` and repeat `Total Amount`. Collapse to **one Sure transaction per order** using order total. Skip `Cancelled` / zero totals. Split mixed orders only if the user asks.
- **Venmo:** Header row contains `Datetime` and `Note` (not row 0). `Amount (total)` sign is cash flow (`+` received / `-` sent). Filter `filteredRows`. Default window is the **previous calendar month**.

### Sure API

Public UI is Authentik-fronted (`https://sure.tyler.cloud`); `/api` is **not** skipped. Call the LAN origin from Cabinet `sure.base_url` (default `http://192.168.1.101:3006`).

```
GET/POST  /api/v1/accounts
GET       /api/v1/categories?per_page=100   (paginate; ~70 categories)
GET       /api/v1/transactions?account_id=&start_date=&end_date=&page=&per_page=100
POST      /api/v1/transactions
PUT       /api/v1/transactions/{id}
DELETE    /api/v1/transactions/{id}
GET       /api/v1/balance_sheet             (live net worth / assets / liabilities)
GET       /api/v1/balances?account_id=&start_date=&end_date=&page=&per_page=100
```

Header: `X-Api-Key` (Cabinet `sure.api_key`). JSON body:

```json
{ "transaction": {
    "account_id": "<uuid>",
    "date": "YYYY-MM-DD",
    "amount": 12.34,
    "nature": "expense",
    "name": "…",
    "notes": "…",
    "category_id": "<uuid>",
    "external_id": "stable-id",
    "source": "venmo|everbank|robinhood_cc|amazon",
    "user_modified": true
}}
```

- `amount` is always **positive**. `nature` is `expense`/`outflow` (money leaving the account) or `income`/`inflow` (money entering). Credit-card purchases are `expense`; card payments and refunds are `income`.
- List responses use `signed_amount_cents`: **income positive, expense negative**. Match CSV rows to existing txns on **date + signed cents**, then name/merchant. Skip Sure names like `Manual balance update`.
- Do **not** stamp category `Other`. Leave unmatched notes uncategorized. Do **not** overwrite a more specific Sure category with a weaker keyword match.
- Re-runs: skip when date/amount (and `external_id` if present) already exist. Prefer a stable `external_id` (Venmo `ID`, Amazon order ID, hash of date+description+amount).
- Paginate everything (`per_page` max 100).

Compose / Rails: Sure host in `sure.base_url` (`~/git/docker/sure.am`). Category tree edits that the API cannot do (rename, merge, destroy) go through `docker exec sure-web bin/rails runner '…'`.

## Credentials (Cabinet)

Never print or commit these. Local Mac Cabinet and `cloud` Cabinet are **separate** MongoDBs — set keys on the machine that runs the import.

| Key | Purpose |
|-----|---------|
| `sure.api_key` | `read_write` key named `finance_parser` |
| `sure.base_url` | Default `http://192.168.1.101:3006` |
| `sure.account_name` | Default `Venmo` (parser only) |

If `sure.api_key` is missing: create it in Sure **Settings → API Key**, or reuse `plain_key` from Rails `ApiKey.find_by(name: "finance_parser")` on `sure-web`, then `cabinet put` on this Mac.

## Categories

`~/syncthing/notes/docs/selfhosted/transaction_categories.json`

- `parents` — tree (`null` = top-level). Food & Drink children include **`Restaurants`** (tea/boba/coffee merged here; there is no separate Boba category) and `Groceries`.
- `categories` — keyword lists for this parser and Sure rules. `!prefix` = skip that category if the note contains the rest of the token (`!STEAM` so `Tea` does not match Steam). `!prefix` is **parser-only**; Sure rules are substring `ILIKE` with no exclusions. Prefer a tighter token over a short one that matches inside unrelated words (`pho ` / ` pho` plus `!IPHONE`, not bare `pho`, which matches `iPhone`). Phone cases belong in **`Electronic Accessories (USB, etc.)`**.
- `keyword_skip` — never turn into Sure rules (e.g. `cha` matched CHASE).
- `filteredRows` — drop CSV rows whose description contains the substring.
- `transfers` — Venmo payment/cashout → transfer rules.
- `classification` — income categories.

First matching category in JSON object order wins. After editing the JSON, copy it to the Sure host if Syncthing is lagging, then:

```bash
~/git/docker/sure.am/scripts/sync-category-rules.sh
```

Dry run: `DRY_RUN=1`; skip re-applying to existing txns: `APPLY_RULES=0`. Sync creates/updates rules from JSON and **prunes keyword rules** whose names are no longer in the JSON. It does **not** delete removed **categories** — do that in Rails (reassign `Transaction.category_id`, rewrite/destroy rules, then `category.destroy!`).

`sure-web` runs on the LAN host in `sure.base_url` (SSH there if this Mac has no container). Copy the JSON if Syncthing has not caught up, then run the script on that host.

## Monthly recap

Read `~/git/backend/finances/AGENTS.md` first. That file has pay, property, debt, classification exceptions, and the last snapshot. Overlay mortgages and real estate from there — Sure is financial accounts only until those exist.

Default window is the **previous calendar month** (inclusive). “Past month” on the 1st means that month. If they say “this month” mid-month, use month-to-date and say so. Compare to the prior calendar month the same way.

Fetch (paginate everything): accounts, categories (keep `parent`), all transactions in the window **and** the prior month (no `account_id` unless asked), `GET /api/v1/balance_sheet` (today), and `GET /api/v1/balances` covering both month-end dates. Match categories by name; do not hard-code IDs.

Present as a Cursor canvas (charts + tables). Lead the chat with headline numbers. Never print API keys. Never write household facts into this parser file.

### Classify (do not double-count)

Treat each transaction as exactly one of: internal transfer, card payment, investment contribution, investment income, earned income, reimbursement, gift-in, refund, or spending. Named payees, payroll splits, and housing Zelle rules are in the backend facts file.

- **Internal transfer** — Sure `transfer` to another family account, or names like transfer / cashout / ACH / P2P / electronic withdrawal. Ignore `Manual balance update`. **Do not** trust a Sure transfer link when the two legs are unrelated payees that happen to share an amount — keep those as normal income/expense.
- **Card payment** — credit-card `income` that is a payment / autopay / thank-you; depository expenses that pay a card (including a bounce plus retry). Parent category `Card Payments` counts here. Exclude principal from spending. A returned-payment **fee** is a fee, not the payment.
- **Investment contribution** — cash leaving a depository into a brokerage (not a card payoff). Not consumption.
- **Investment income** — dividends, brokerage interest, card cashback swept to brokerage. Report separately from earned income.
- **Earned income** — payroll and rental-income categories (see backend file for names). A paycheck split across deposit accounts is still one paycheck, not extra income.
- **Reimbursements** — Venmo (or similar) **income** that is a split or payback for a shared expense. Net it against the matching spend category. Not earned income.
- **Gift pooling** — if the user paid for an event and collected for that event, net **that event** as (amount they sent for it) minus (amount received earmarked for it). Do **not** fold unrelated gifts from the same month into the event.
- **Recurring housing transfer** — a repeating Zelle (or similar) that last month was `Mortgage or Rent - Primary Home` is the primary-home share. Amount and counterparty: backend file. Include in spending; `PUT` if uncategorized and the user wants it fixed.
- **Spending** — remaining expenses. Credit-card refunds reduce spend. Group by Sure **parent** category. Call out leftover uncategorized names and keyword collisions.

### Net worth month-over-month

Live `GET /api/v1/balance_sheet` is **today**, not month-end.

For each month-end date, take the latest `balances` row **on or before** that date per account. Net-worth contribution is `end_balance_cents * flows_factor` (liabilities use `-1`). Sum contributions. Compare to the prior month-end. Split the delta into cash (depository), investments, and cards. If an account has no history on or before the date, skip it and say so.

### After the recap

Update **Last snapshot** (and facts if salary/loans changed) in `~/git/backend/finances/AGENTS.md`. If the user names a miscategorization, `PUT` with `user_modified: true`, persist keywords in the JSON, and sync. Same as after import.

## After import

Summarize create/update/skip. Call out leftover uncategorized names and any keyword collisions (substring false positives). Recategorize in Sure with `PUT` when the user names the fix; persist new keywords in the JSON and sync.
