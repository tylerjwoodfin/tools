---
name: food
description: Log meals to foodlog via the food plugin. Use for /food, reminder follow-ups, and messages like tacos 100. Do not handle food logging in the main agent turn.
user-invocable: false
metadata:
  {
    "openclaw":
      {
        "emoji": "🌮",
        "requires": { "bins": ["python3"] },
      },
  }
---

# Food

Meal logging is handled **only** by the `food` OpenClaw plugin (`food_cli.py` → `foodlog`).

## Hard rules

- Never invent a parallel food-log flow in the main session.
- Never claim food was logged unless the plugin/`food_cli.py` said `"action": "logged"`.
- Casual meal chat is not a log unless `/food` is used, a reminder is pending, or the text is clearly food-to-log.

## Commands

```bash
python3 ~/git/tools/openclaw/food/scripts/food_cli.py handle "tacos 100"
python3 ~/git/tools/openclaw/food/scripts/food_cli.py status
python3 ~/git/tools/openclaw/food/scripts/food_cli.py tick
```

Source of truth: `python3 ~/git/tools/foodlog/main.py`

## Flow

1. `/food …` or a reminder reply → plugin `before_agent_reply` → `food_cli.py handle`
2. Simple `name calories` / `name should be N` is parsed locally (no model)
3. Freeform meals use `openclaw infer` with the cloud model, then `foodlog`
4. 7pm `food-log-remind` runs `food_cli.py tick` (isolated command, not the main session)
