#!/usr/bin/env python3

"""A simple food logging tool that logs food entries and calorie counts."""

import json
import sys
import os
import datetime
from prompt_toolkit import print_formatted_text, HTML
from cabinet import Cabinet

cabinet = Cabinet()

# define file paths
LOG_DIR = cabinet.get("path", "cabinet", "log") or os.path.expanduser("~/.cabinet/log")
FOOD_LOG_FILE = os.path.join(LOG_DIR, "food.json")
FOOD_LOOKUP_FILE = os.path.join(LOG_DIR, "food_lookup.json")

def ensure_log_directory():
    """create log directory if it doesn't exist."""
    os.makedirs(LOG_DIR, exist_ok=True)

def load_json(file_path):
    """load json data from a file, return empty dict if file doesn't exist."""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(file_path, data):
    """save data to a json file."""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def log_food(food_name, calories):
    """log food entry for today's date."""
    ensure_log_directory()
    log_data = load_json(FOOD_LOG_FILE)
    today = datetime.date.today().isoformat()

    if today not in log_data:
        log_data[today] = []

    if isinstance(calories, str) and calories.isnumeric():
        calories = int(calories)
    elif not isinstance(calories, int):
        raise ValueError("Calories must be an integer or a numeric string.")

    log_data[today].append({"food": food_name, "calories": calories})
    save_json(FOOD_LOG_FILE, log_data)
    print_formatted_text(HTML(
        f'<green>Logged:</green> {food_name} <yellow>({calories} cal)</yellow>'))

    display_today_calories()

def update_food_lookup(food_name, calories):
    """update food lookup file with food and calorie information."""
    lookup_data = load_json(FOOD_LOOKUP_FILE)

    if isinstance(calories, str) and calories.isnumeric():
        calories = int(calories)

    if food_name in lookup_data and lookup_data[food_name] != calories:
        print_formatted_text(HTML(
            f'<yellow>{food_name}</yellow> has <yellow>{lookup_data[food_name]} cal</yellow>.'))
        choice = input("Overwrite? (y/n): ").strip().lower()
        if choice != 'y':
            return

    lookup_data[food_name] = calories
    save_json(FOOD_LOOKUP_FILE, lookup_data)

def display_today_calories():
    """display total calorie count and entries for today."""
    log_data = load_json(FOOD_LOG_FILE)
    today = datetime.date.today()
    today_str = today.isoformat()

    if today_str in log_data:
        # Format the date as "Food for Day, YYYY-MM-DD"
        formatted_date = f"\n{today.strftime('%a')}, {today_str}"
        print_formatted_text(HTML(f'<underline><bold>{formatted_date}</bold></underline>'))
        total_calories = 0

        # Find the maximum length of calories for alignment
        if log_data[today_str]:
            max_calories_length = max(len(str(entry["calories"])) for entry in log_data[today_str])
        else:
            max_calories_length = 0
        for entry in log_data[today_str]:
            food = entry["food"]
            calories = entry["calories"]
            total_calories += calories

            # Pad calories to maintain consistent alignment
            padded_calories = str(calories).rjust(max_calories_length)

            print_formatted_text(HTML(
                f'<blue>{padded_calories} cal - </blue> <green>{food}</green>'))

        # Color-code total calories
        if total_calories <= 1700:
            total_color = 'green'
        elif total_calories <= 2000:
            total_color = 'yellow'
        else:
            total_color = 'red'

        print_formatted_text(HTML(
            f'\n<bold>Total today:</bold> <{total_color}>{total_calories}</{total_color}>'))
    else:
        print_formatted_text(HTML('<yellow>No food logged for today.</yellow>'))

def main():
    """Parse command-line arguments and log food entry."""

    if len(sys.argv) < 2:
        display_today_calories()
        sys.exit(0)

    if sys.argv[1] == "--edit":
        edit_food_json()
        sys.exit(0)

    try:
        if len(sys.argv) < 2:
            raise ValueError("Usage: main.py <food name> <calories>")

        food_name = " ".join(sys.argv[1:-1])
        calories = sys.argv[-1]

        # last arg is a string -> calories not set; get from lookup
        if isinstance(calories, str) and not calories.isnumeric():
            food_name = " ".join(sys.argv[1:])
            lookup_data = load_json(FOOD_LOOKUP_FILE)

            if food_name in lookup_data:
                print(f"{lookup_data[food_name]} cal found for {food_name}.\n")
                choice = input("Use this? (y/n): ").strip().lower()
                if choice == 'y':
                    calories = lookup_data[food_name]
                else:
                    calories = input("Enter calorie count: ").strip()
                    if not calories.isnumeric():
                        raise ValueError("Calorie count must be a number.")
                    calories = int(calories)
            else:
                calories = input("Enter calorie count: ").strip()
                if not calories.isnumeric():
                    raise ValueError("Calorie count must be a number.")
                calories = int(calories)

        log_food(food_name, calories)
        update_food_lookup(food_name, calories)

    except ValueError as e:
        print_formatted_text(HTML(f'<red>Error: {e}</red>'))
        sys.exit(1)

def edit_food_json():
    """Edit the food.json file."""
    os.system(f"{cabinet.editor} {FOOD_LOG_FILE}")

if __name__ == "__main__":
    main()
