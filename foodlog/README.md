# Food Log

A simple command-line tool for logging food entries and tracking calories. The tool automatically classifies foods as healthy or junk and provides a visual summary of your eating habits. Daily totals sync to the existing Grafana/Loki stack so you can spot patterns over time.

## Features

- Log food entries with calorie counts
- Automatic food classification (healthy vs junk)
- Visual summary of daily calorie intake with healthy/junk breakdown
- Food lookup database to remember calorie counts
- AI-powered calorie suggestions for unknown foods
- `foodlog submit` to mark the day done (skips the dailystatus reminder email)
- Grafana sync via Cabinet `logging.loki_url` (updates as you log)

## Usage

### Basic Logging
```bash
foodlog "food name" calories
```

Example:
```bash
foodlog "chicken salad" 540
```

Each log (and undo) updates `food.json` and pushes that day's total to Loki so Grafana charts stay current.

### Multiple Entries
You can log multiple food entries in a single command using `//` as a separator. Each side of `//` is treated as a separate command:

```bash
# Log two foods with their own calorie counts
foodlog "apple" 50 // "banana" 60

# Mix and match with lookup
foodlog "apple" // "banana" 60 // "cookies"

# Use with --yesterday (only applies to the command it's associated with)
foodlog "apple" 50 // "banana" 60 --yesterday
```

### View Today's Log
```bash
foodlog
```

### Submit the day (disable dailystatus reminder)
```bash
foodlog submit
# or
foodlog --submit
```

Daily status sends the “log food” reminder only if today has **not** been submitted. Logging food alone does not clear the reminder.

### Sync history to Grafana
```bash
foodlog --sync-grafana
```

Backfills every day in `food.json` to Loki (uses Cabinet `logging.loki_url`).

### View Summary
```bash
foodlog --summary
```
The summary view shows:
- Food entries for the past 7 days
- Total calories and percentage of healthy vs junk food
- Visual bar graph where:
  - Bar length represents total calories (shorter = fewer calories)
  - Green portion represents healthy calories
  - Red portion represents junk calories

### Edit Food Log
```bash
foodlog --edit
```

### Log to Yesterday
```bash
# in case you forgot yesterday!
foodlog "chicken salad" 500 --yesterday
```

## Data Storage

Flat files under Cabinet `path -> cabinet -> log` (fallback `~/.cabinet/log`):

- `food.json` — entries keyed by ISO date (unchanged structure)
- `food_lookup.json` — remembered calorie counts / classifications
- `food_submitted.json` — days marked with `foodlog submit`

## Grafana

Uses the existing Grafana app (Loki datasource). Foodlog pushes `job=foodlog` daily snapshots when `logging.loki_url` is set in Cabinet config. Example LogQL:

```logql
{job="foodlog", type="daily"} | json | unwrap total_calories
```

## Configuration

The tool uses:
- [Cabinet](https://www.github.com/tylerjwoodfin/cabinet).
  - You can set:
    - `foodlog -> calorie_target`: Your daily calorie target (default: 1750)
    - `keys -> openai`: Your OpenAI API key for AI-powered features
    - `logging -> loki_url`: Loki base URL for Grafana sync (same as Cabinet logs)
- [tyler-python-helpers](https://github.com/tylerjwoodfin/python-helpers)
  - `pipx install tyler-python-helpers`

## Notes

- The tool automatically classifies foods as healthy or junk based on common nutritional knowledge
- For new foods, you can use the 'ai' option to get calorie suggestions from ChatGPT
- The summary view's bar graph scales based on your highest calorie day, making it easy to compare daily intake
