# Amazon order automation

Describe a product in everyday language; Playwright searches Amazon, ChatGPT
picks the best match, you confirm, and the order is placed on your account.

## Setup

```bash
pip install -r ~/git/tools/amazon/requirements.txt
# Local Chromium (if not using the Docker Playwright server):
playwright install chromium
```

Optional Playwright browser server (matches Python package major.minor):

```bash
cd ~/git/docker/playwright && docker compose up -d
```

Default WebSocket: `ws://127.0.0.1:9311/` (override with env
`PLAYWRIGHT_WS_ENDPOINT` or Cabinet `amazon` → `playwright_ws`).

### Amazon login (once)

```bash
amazon --login
```

Sign in in the opened browser (2FA if needed). Session is saved to
`~/.local/share/amazon-order/storage_state.json` (override with Cabinet
`amazon` → `storage_state`).

## Usage

```bash
amazon strawberry flavored huel
amazon --dry-run protein bars no sugar
amazon --login
amazon --help
```

Each step prints a cue. You must confirm before checkout and again before
placing the order (`--yes` skips the product confirmation only, not place-order).

## Cabinet (optional)

| Path | Purpose |
|------|---------|
| `amazon` → `playwright_ws` | Playwright server WebSocket URL |
| `amazon` → `storage_state` | Path to Playwright storage state JSON |
| `amazon` → `headless` | `true` / `false` for local Chromium (default false) |
