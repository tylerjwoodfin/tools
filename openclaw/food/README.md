# /food

OpenClaw **plugin** that turns any meal description into a `foodlog` entry without using the main Telegram session model.

## What it does

- `/food tacos 100` logs that item as-is
- `matcha should be 200` (or a reply to the 7pm nudge) is parsed locally and logged
- Freeform meals (`I had 2 taco bell tacos…`) are parsed with a cloud `openclaw infer` call, then written with `foodlog`
- `/food` with no args shows today's log
- At 7pm America/Los_Angeles, if nothing is logged or the day is under 1000 calories, `food_cli.py tick` sends a **fresh** Telegram nudge. Replies are claimed by the plugin.

Logged format matches `foodlog`:

```bash
python3 ~/git/tools/foodlog/main.py "taco bell tacos" 340 // "blueberries" 50
```

## Install

```bash
~/git/tools/openclaw/food/scripts/install_openclaw.sh
```

This copies the skill, links the plugin, and registers the `food-log-remind` cron job.

Restart the gateway after install:

```bash
~/git/tools/openclaw/openclaw-gateway gateway restart
```

## Related

- [`~/git/tools/foodlog`](../../foodlog) — CLI + Mongo source of truth
- [`~/git/tools/openclaw/diary`](../diary) — `/diary` plugin + skill
