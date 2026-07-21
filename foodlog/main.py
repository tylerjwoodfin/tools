#!/usr/bin/env python3

"""A simple food logging tool that logs food entries and calorie counts."""

import json
import sys
import os
import datetime
import socket
import tempfile
import urllib.error
import urllib.request
from tyler_python_helpers import ChatGPT
from prompt_toolkit import print_formatted_text, HTML
from cabinet import Cabinet

from store import (
    day_total_calories,
    get_store,
    normalize_calories,
)

cabinet = Cabinet()
chatgpt = ChatGPT()

# Legacy flat-file paths (used for one-time Mongo migration / optional export)
LOG_DIR = cabinet.get("path", "cabinet", "log") or os.path.expanduser("~/.cabinet/log")
FOOD_LOG_FILE = os.path.join(LOG_DIR, "food.json")
FOOD_LOOKUP_FILE = os.path.join(LOG_DIR, "food_lookup.json")
FOOD_SUBMITTED_FILE = os.path.join(LOG_DIR, "food_submitted.json")

_MIGRATED = False


def ensure_log_directory() -> None:
    """create log directory if it doesn't exist (legacy export / edit temp)."""
    os.makedirs(LOG_DIR, exist_ok=True)


def _ensure_migrated() -> None:
    """Import flat files into Mongo once if the foodlog DB is empty."""
    global _MIGRATED  # pylint: disable=global-statement
    if _MIGRATED:
        return
    store = get_store()
    imported = store.migrate_from_json_files(
        FOOD_LOG_FILE,
        FOOD_LOOKUP_FILE,
        FOOD_SUBMITTED_FILE,
        only_if_empty=True,
    )
    if imported:
        print_formatted_text(
            HTML(
                f"<green>Migrated</green> <yellow>{imported}</yellow> day(s) "
                "from flat files into MongoDB database <yellow>foodlog</yellow>."
            )
        )
    _MIGRATED = True


def load_json(file_path: str) -> dict:
    """load json data from a file, return empty dict if file doesn't exist."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json(file_path: str, data: dict) -> None:
    """save data to a json file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def is_day_submitted(day: str, submitted_data: dict | None = None) -> bool:
    """Return True if ``foodlog submit`` has been run for ``day`` (ISO date)."""
    if submitted_data is not None:
        value = submitted_data.get(day)
        if isinstance(value, dict):
            return bool(value.get("submitted"))
        return bool(value)
    _ensure_migrated()
    return get_store().is_day_submitted(day)


def mark_day_submitted(day: str | None = None) -> str:
    """
    Mark a day as submitted so dailystatus skips the foodlog reminder email.

    Returns the ISO date that was marked.
    """
    _ensure_migrated()
    return get_store().mark_submitted(day)


def _loki_base_url() -> str | None:
    """Cabinet Loki base URL (no /push), or None if unset."""
    url = getattr(cabinet, "logging_loki_url", "") or ""
    url = url.strip().rstrip("/")
    return url or None


def build_daily_grafana_event(
    day: str,
    entries: list,
    submitted: bool,
    hostname: str | None = None,
) -> dict:
    """Build a structured daily snapshot for Loki / Grafana."""
    return {
        "type": "daily",
        "date": day,
        "total_calories": day_total_calories(entries),
        "entry_count": len(entries),
        "submitted": submitted,
        "hostname": hostname or socket.gethostname(),
        "foods": [
            {
                "food": e.get("food", "unknown"),
                "calories": normalize_calories(e.get("calories", 0)),
            }
            for e in entries
        ],
    }


def build_loki_push_body(event: dict, timestamp: datetime.datetime | None = None) -> dict:
    """Build a Loki push API body for a single foodlog event."""
    ts = timestamp or datetime.datetime.now(datetime.timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    # Anchor daily snapshots at noon UTC on that calendar day so charts stay stable
    # when the day is updated throughout local logging.
    if event.get("type") == "daily" and event.get("date"):
        try:
            day = datetime.date.fromisoformat(event["date"])
            ts = datetime.datetime(
                day.year, day.month, day.day, 12, 0, 0, tzinfo=datetime.timezone.utc
            )
        except ValueError:
            pass
    ns = str(int(ts.timestamp() * 1_000_000_000))
    labels = {
        "job": "foodlog",
        "type": str(event.get("type", "daily")),
        "hostname": str(event.get("hostname") or socket.gethostname()),
    }
    return {
        "streams": [
            {
                "stream": labels,
                "values": [[ns, json.dumps(event, separators=(",", ":"))]],
            }
        ]
    }


def push_event_to_loki(event: dict, loki_url: str | None = None) -> bool:
    """
    POST a foodlog event to Loki (optional; Grafana charts Mongo directly).

    Returns True on success. No-op (False) when Loki URL is unset or unreachable.
    """
    base = (loki_url or _loki_base_url() or "").rstrip("/")
    if not base:
        return False
    body = json.dumps(build_loki_push_body(event)).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/loki/api/v1/push",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= getattr(resp, "status", 200) < 300
    except (urllib.error.URLError, TimeoutError, OSError, socket.gaierror) as exc:
        cabinet.log(
            f"foodlog optional Loki push failed (Mongo is source of truth): {exc}",
            level="debug",
        )
        return False


def sync_day_to_grafana(day: str | None = None, log_data: dict | None = None) -> bool:
    """Push one day's totals from Mongo (or provided map) to Loki."""
    _ensure_migrated()
    day = day or datetime.date.today().isoformat()
    store = get_store()
    if log_data is None:
        entries = store.get_entries(day)
        submitted = store.is_day_submitted(day)
    else:
        entries = log_data.get(day, [])
        submitted = is_day_submitted(day)
    event = build_daily_grafana_event(day, entries, submitted=submitted)
    return push_event_to_loki(event)


def sync_all_to_grafana(log_data: dict | None = None) -> int:
    """Backfill all days to Loki. Returns number of successful pushes."""
    _ensure_migrated()
    if log_data is None:
        log_data = get_store().all_days_map()
    ok = 0
    for day in sorted(log_data.keys()):
        if sync_day_to_grafana(day, log_data=log_data):
            ok += 1
    return ok


def log_food(food_name: str, calories: int, is_yesterday: bool = False) -> None:
    """log food entry for today's date."""
    _ensure_migrated()
    today = datetime.date.today().isoformat()
    if is_yesterday:
        today = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    calories = normalize_calories(calories)
    food_name_lower = food_name.lower()
    get_store().append_entry(today, food_name_lower, calories)
    print_formatted_text(
        HTML(f"<green>Logged:</green> {food_name} <yellow>({calories} cal)</yellow>")
    )

    if globals().get("_is_last_main_call", False):
        display_daily_calories()


def update_food_lookup(food_name: str, calories: int) -> None:
    """update food lookup with food and calorie information."""
    _ensure_migrated()
    store = get_store()
    lookup_data = store.get_lookup()
    calories = normalize_calories(calories)
    food_name_lower = food_name.lower()

    if food_name_lower in lookup_data:
        if lookup_data[food_name_lower]["calories"] != calories:
            print_formatted_text(
                HTML(
                    f'<yellow>Warning:</yellow> <yellow>{food_name}</yellow> has <yellow>{\
                    lookup_data[food_name_lower]["calories"]} cal</yellow>.'
                )
            )
            print_formatted_text(
                HTML(
                    f"<yellow>Undo with 'foodlog undo'\n"
                    f"Update with 'foodlog update {food_name} {calories}'</yellow>\n"
                )
            )
    else:
        store.upsert_lookup(food_name_lower, calories, food_type="unknown")


def force_update_food_lookup(food_name: str, calories: int) -> None:
    """force update food lookup with new calorie information."""
    _ensure_migrated()
    store = get_store()
    lookup_data = store.get_lookup()
    calories = normalize_calories(calories)
    food_name_lower = food_name.lower()

    old_calories = lookup_data.get(food_name_lower, {}).get("calories", "unknown")
    store.upsert_lookup(food_name_lower, calories, food_type="unknown")

    print_formatted_text(
        HTML(
            f"<green>Updated:</green> {food_name} from "
            f"<yellow>{old_calories}</yellow> to <yellow>{calories}</yellow> cal"
        )
    )


def display_daily_calories(target_date: datetime.date = None) -> None:
    """display total calorie count and entries for a specific date (defaults to today)."""
    _ensure_migrated()
    store = get_store()
    if target_date is None:
        target_date = datetime.date.today()

    target_date_str = target_date.isoformat()
    entries = store.get_entries(target_date_str)

    if entries:
        formatted_date = f"\n{target_date.strftime('%a')}, {target_date_str}"
        print_formatted_text(
            HTML(f"<underline><bold>{formatted_date}</bold></underline>")
        )
        total_calories = 0

        for entry in entries:
            food = entry["food"]
            calories = normalize_calories(entry["calories"])
            total_calories += calories
            padded_calories = str(calories).ljust(4)
            print_formatted_text(HTML(f"{padded_calories}cal - <green>{food}</green>"))

        calorie_target = cabinet.get("foodlog", "calorie_target")
        if calorie_target is None:
            cabinet.log("Calorie target not set, using 1750", level="warning")
            calorie_target = 1750

        if abs(total_calories - calorie_target) <= 150:
            total_color = "green"
        elif abs(total_calories - calorie_target) <= 300:
            total_color = "yellow"
        else:
            total_color = "red"

        submitted_note = ""
        if store.is_day_submitted(target_date_str):
            submitted_note = " <green>(submitted)</green>"

        print_formatted_text(
            HTML(
                f"\n<bold>Total:</bold> <{total_color}>{total_calories}</{total_color}>"
                f"{submitted_note}"
            )
        )
    else:
        date_description = (
            "today"
            if target_date == datetime.date.today()
            else f"for {target_date.strftime('%A, %Y-%m-%d')}"
        )
        print_formatted_text(
            HTML(f"<yellow>No food logged {date_description}.</yellow>")
        )


def get_calories(food_name: str, lookup_data: dict) -> int:
    """get calorie count for a food item, either from lookup or user input."""
    food_name_lower = food_name.lower()

    if food_name_lower in lookup_data:
        calories = lookup_data[food_name_lower].get("calories")
        if calories is None:
            raise ValueError(f"No calorie data found for {food_name}")
        print(f"{calories} cal found for {food_name}.\n")
        choice = input("Use this? (y/n): ").strip().lower()
        if choice == "y":
            return calories

    calories = input("Enter calorie count, or 'ai' to ask ChatGPT: ").strip()
    if calories == "ai":
        ai_calories = query_chatgpt(food_name)
        print(f"\nChatGPT suggests: {ai_calories} calories")
        calories = input("Use this value? (y/n): ").strip().lower()
        if calories == "y":
            return int(ai_calories)
        calories = input("Enter calorie count: ").strip()

    if not calories.isnumeric():
        raise ValueError("Calorie count must be a number.")
    return int(calories)


def query_chatgpt(food_name: str) -> str:
    """Query ChatGPT for the calorie count of a food item."""
    query = f"What is the calorie count of {food_name}? \
        Only output your best guess as a number, no other text."
    return chatgpt.query(query)


def classify_food(food_names: list[str]) -> dict[str, str]:
    """Classify multiple food items as 'junk' or 'healthy' using AI."""

    food_list = "\n".join([f"- {food}" for food in food_names])
    prompt = f"""Classify each of these food items as either 'junk' or 'healthy'.
For each item, output the food name followed by a colon and its classification.
Only use the words 'junk' or 'healthy' for classification.

Foods to classify:
{food_list}

Output format:
food1: junk
food2: healthy
food3: junk
"""

    response = chatgpt.query(prompt)

    classifications = {}
    for line in response.split("\n"):
        if ":" in line:
            food, classification = line.split(":", 1)
            classifications[food.strip()] = classification.strip().lower()

    return classifications


def show_summary() -> None:
    """Display a summary of the past 7 days of food entries with AI classification."""
    _ensure_migrated()
    store = get_store()
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=6)).isoformat()
    log_data = store.list_days_between(start, today.isoformat())
    lookup_data = store.get_lookup()

    print_formatted_text(
        HTML("<bold><underline>Food Summary (Last 7 Days)</underline></bold>\n")
    )

    all_foods = set()
    daily_totals = {}
    daily_healthy = {}
    daily_junk = {}
    for i in range(7):
        date = today - datetime.timedelta(days=i)
        date_str = date.isoformat()
        if date_str in log_data:
            daily_totals[date] = sum(
                normalize_calories(entry["calories"]) for entry in log_data[date_str]
            )
            daily_healthy[date] = 0
            daily_junk[date] = 0
            for entry in log_data[date_str]:
                all_foods.add(entry["food"])

    foods_to_classify = []
    for food in all_foods:
        food_lower = food.lower()
        if (
            food_lower not in lookup_data
            or "type" not in lookup_data[food_lower]
            or lookup_data[food_lower]["type"] == "unknown"
        ):
            foods_to_classify.append(food)

    if foods_to_classify:
        classifications = classify_food(foods_to_classify)
        for food, classification in classifications.items():
            store.set_lookup_type(food, classification)
        lookup_data = store.get_lookup()
    else:
        classifications = {}

    total_calories = 0
    healthy_calories = 0
    junk_calories = 0

    for i in range(6, -1, -1):
        date = today - datetime.timedelta(days=i)
        date_str = date.isoformat()

        if date_str in log_data:
            print_formatted_text(
                HTML(f'\n<bold>{date.strftime("%a, %Y-%m-%d")}</bold>')
            )

            for entry in log_data[date_str]:
                food = entry["food"]
                calories = normalize_calories(entry["calories"])
                total_calories += calories

                food_lower = food.lower()
                classification = lookup_data.get(food_lower, {}).get("type", "unknown")

                if classification == "healthy":
                    healthy_calories += calories
                    daily_healthy[date] += calories
                    food_color = "green"
                else:
                    junk_calories += calories
                    daily_junk[date] += calories
                    food_color = "red"

                print_formatted_text(
                    HTML(
                        f"  {calories} cal - <{food_color}>{food}</{food_color}> ({classification})"
                    )
                )

    print_formatted_text(HTML("\n<bold>Calorie Summary:</bold>"))
    if total_calories > 0:
        print_formatted_text(
            HTML(
                f"  Healthy: <green>{healthy_calories}</green> "
                f"({healthy_calories/total_calories*100:.1f}%)"
            )
        )
        print_formatted_text(
            HTML(
                f"  Junk:    <red>{junk_calories}</red> ({junk_calories/total_calories*100:.1f}%)"
            )
        )
        print("")
        print_formatted_text(HTML(f"  Total: {total_calories} cal"))
        print_formatted_text(HTML(f"  Daily Average: {total_calories / 7} cal"))
    else:
        print_formatted_text(HTML("  No calories logged in the past 7 days"))

    print_formatted_text(HTML("\n<bold>Daily Calorie Totals:</bold>"))

    max_calories = max(daily_totals.values()) if daily_totals else 0
    bar_width = 25

    for i in range(6, -1, -1):
        date = today - datetime.timedelta(days=i)
        if date in daily_totals:
            total = daily_totals[date]
            healthy = daily_healthy[date]

            scaled_length = (
                int((total / max_calories) * bar_width) if max_calories > 0 else 0
            )
            healthy_length = int((healthy / total) * scaled_length) if total > 0 else 0
            junk_length = scaled_length - healthy_length

            health_bar = (
                f'<green>{"█" * healthy_length}</green><red>{"█" * junk_length}</red>'
            )

            print_formatted_text(
                HTML(f'  {date.strftime("%a")}: {health_bar} {total} cal')
            )


def submit_day(day: str | None = None) -> None:
    """Mark the day submitted (Mongo). Optional Loki sync is via --sync-grafana."""
    day = mark_day_submitted(day)
    print_formatted_text(
        HTML(
            f"<green>Submitted</green> food log for <yellow>{day}</yellow>. "
            "Daily status will skip the foodlog reminder."
        )
    )
    display_daily_calories(datetime.date.fromisoformat(day))


def main() -> None:
    """parse command-line arguments and log food entry."""
    is_yesterday = False

    if len(sys.argv) < 2:
        display_daily_calories()
        sys.exit(0)

    if "--yesterday" in sys.argv:
        is_yesterday = True
        sys.argv.remove("--yesterday")

        if len(sys.argv) < 2:
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            display_daily_calories(yesterday)
            sys.exit(0)

    if sys.argv[1] in ("submit", "--submit"):
        submit_day()
        sys.exit(0)

    if sys.argv[1] in ("--sync-grafana", "sync-grafana"):
        count = sync_all_to_grafana()
        print_formatted_text(
            HTML(
                f"<green>Synced</green> <yellow>{count}</yellow> day(s) from MongoDB "
                "foodlog to Grafana (Loki)."
            )
        )
        sys.exit(0)

    if sys.argv[1] in ("--migrate", "migrate"):
        store = get_store()
        imported = store.migrate_from_json_files(
            FOOD_LOG_FILE,
            FOOD_LOOKUP_FILE,
            FOOD_SUBMITTED_FILE,
            only_if_empty=False,
        )
        print_formatted_text(
            HTML(
                f"<green>Imported</green> <yellow>{imported}</yellow> day(s) "
                "into MongoDB database <yellow>foodlog</yellow>."
            )
        )
        sys.exit(0)

    if sys.argv[1] == "--edit":
        edit_food_json()
        sys.exit(0)

    if sys.argv[1] == "--summary":
        show_summary()
        sys.exit(0)

    if sys.argv[1] == "undo":
        undo_latest_entry()
        sys.exit(0)

    if sys.argv[1] == "update":
        if len(sys.argv) < 4:
            print_formatted_text(
                HTML("<red>Error: Usage: foodlog update <food_name> <calories></red>")
            )
            sys.exit(1)
        food_name = " ".join(sys.argv[2:-1])
        calories = int(sys.argv[-1])
        force_update_food_lookup(food_name, calories)
        sys.exit(0)

    try:
        full_command = " ".join(sys.argv[1:])
        if "//" in full_command:
            commands = [cmd.strip() for cmd in full_command.split("//")]
            for i, cmd in enumerate(commands):
                globals()["_is_last_main_call"] = i == len(commands) - 1

                cmd_args = cmd.split()
                original_argv = sys.argv.copy()
                sys.argv = [sys.argv[0]] + cmd_args
                try:
                    main()
                finally:
                    sys.argv = original_argv
            return

        food_name = " ".join(sys.argv[1:-1])
        calories = sys.argv[-1]

        if isinstance(calories, str) and not calories.isnumeric():
            food_name = " ".join(sys.argv[1:])
            _ensure_migrated()
            lookup_data = get_store().get_lookup()
            calories = get_calories(food_name, lookup_data)
        else:
            calories = int(calories)

        log_food(food_name, calories, is_yesterday)
        update_food_lookup(food_name, calories)

    except ValueError as e:
        print_formatted_text(HTML(f"<red>Error: {e}</red>"))
        sys.exit(1)


def undo_latest_entry() -> None:
    """Remove the latest food entry from today's log."""
    _ensure_migrated()
    store = get_store()
    today = datetime.date.today().isoformat()

    removed_entry = store.pop_latest_entry(today)
    if not removed_entry:
        print_formatted_text(HTML("<yellow>No entries to undo for today.</yellow>"))
        return

    food_name = removed_entry["food"]
    calories = removed_entry["calories"]
    print_formatted_text(
        HTML(f"<green>Removed:</green> {food_name} <yellow>({calories} cal)</yellow>")
    )
    display_daily_calories()


def edit_food_json() -> None:
    """Export Mongo days to a temp JSON, edit, re-import."""
    _ensure_migrated()
    store = get_store()
    ensure_log_directory()
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix="-food.json",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        json.dump(store.export_log_map(), tmp, indent=4)
        tmp_path = tmp.name
    os.system(f"{cabinet.editor} {tmp_path}")
    try:
        with open(tmp_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        submitted = store.export_submitted_map()
        store.days.delete_many({})
        store.replace_all_from_maps(data, submitted_data=submitted)
        print_formatted_text(
            HTML("<green>Re-imported</green> edited food log into MongoDB.")
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
