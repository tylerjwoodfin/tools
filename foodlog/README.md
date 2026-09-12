# Food Log

A simple command-line tool for logging food entries and tracking calories. Data lives in a dedicated **MongoDB database `foodlog`** on the same server as Cabinet (peer to the `cabinet` DB). Grafana charts the `days` collection directly; optional Loki snapshots remain for log-style views.

## Features

- Log food entries with calorie counts (MongoDB source of truth)
- Automatic food classification (healthy vs junk)
- Visual summary of daily calorie intake with healthy/junk breakdown
- Food lookup database to remember calorie counts
- AI-powered calorie suggestions for unknown foods
- `foodlog submit` to mark the day done (daily email calorie total shows submitted)
- Grafana: MongoDB datasource + Foodlog dashboard; optional Loki sync

## Usage

### Basic Logging
```bash
foodlog "food name" calories
```

Example:
```bash
foodlog "chicken salad" 540
```

### Multiple Entries
```bash
foodlog "apple" 50 // "banana" 60
foodlog "apple" // "banana" 60 // "cookies"
foodlog "apple" 50 // "banana" 60 --yesterday
```

### View Today's Log
```bash
foodlog
foodlog --json
```

### Submit the day
```bash
foodlog submit
# or
foodlog --submit
```

Marks the day done for Grafana and the daily status calorie line. Evening “log food” nudges are Telegram-only (`food-log-remind`).

### Migrate legacy flat files → Mongo
```bash
foodlog --migrate
```

On first use, if the `foodlog` DB is empty, flat files under Cabinet’s log path are imported automatically.

### Sync snapshots to Loki (optional)
```bash
foodlog --sync-grafana
```

### View Summary
```bash
foodlog --summary
```

### Edit Food Log
```bash
foodlog --edit
```
Exports days to a temp JSON, opens your Cabinet editor, then re-imports into Mongo.

### Log to Yesterday
```bash
foodlog "chicken salad" 500 --yesterday
```

## Data Storage

**MongoDB** (same URI as Cabinet `mongodb_connection_string`, database name `foodlog`):

| Collection | Contents |
|------------|----------|
| `days` | One document per ISO date: `entries[]`, `total_calories`, `submitted`, `date_time` |
| `lookup` | Food name → calories / healthy\|junk type |

Legacy flat files (migration only): `food.json`, `food_lookup.json`, `food_submitted.json` under Cabinet `path -> cabinet -> log`.

## Grafana

The Loki stack provisions:

1. **Foodlog MongoDB** datasource (`haohanyang-mongodb-datasource`) → database `foodlog`
2. **Foodlog** dashboard (Mongo time series of `total_calories`)

OSS Grafana cannot use Grafana’s Enterprise Mongo plugin; the community plugin is installed via compose.

## Configuration

- [Cabinet](https://www.github.com/tylerjwoodfin/cabinet)
  - `foodlog -> calorie_target` (default 1750)
  - `mongodb_connection_string` / `mongodb_enabled` (shared Mongo server)
  - `logging -> loki_url` (optional Loki sync)
  - `keys -> openai` for AI features
- Override URI with env `FOODLOG_MONGO_URI` if needed
- [tyler-python-helpers](https://github.com/tylerjwoodfin/python-helpers) — `pipx install tyler-python-helpers`
- `pymongo` (same as Cabinet)

## Notes

- Foods are classified as healthy or junk for the summary view
- Use `ai` at the calorie prompt for ChatGPT suggestions
- Summary bar graph scales to your highest calorie day in the window
