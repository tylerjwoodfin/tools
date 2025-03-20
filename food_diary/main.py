"""Food Diary Script
This script logs food entries and their calorie counts for the current day.
It maintains a log of food entries in a JSON file and allows for updating
a lookup file for food names and their corresponding calorie counts.
It also provides a summary of total calories logged for the current day.
Usage:
    python main.py <food_name> [calories]
If no food name is provided, it displays the total calories logged for today.
"""
#!/usr/bin/env python3

import json
import sys
import os
import datetime

# define file paths
LOG_DIR = os.path.expanduser("~/syncthing/log")
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

    log_data[today].append({"food": food_name, "calories": calories})
    save_json(FOOD_LOG_FILE, log_data)
    print(f"Logged: {food_name} ({calories} cal)")

def update_food_lookup(food_name, calories):
    """update food lookup file with food and calorie information."""
    lookup_data = load_json(FOOD_LOOKUP_FILE)

    if food_name in lookup_data and lookup_data[food_name] != calories:
        print(f"{food_name} is already recorded with {lookup_data[food_name]} cal.")
        choice = input("Overwrite? (y/n): ").strip().lower()
        if choice != 'y':
            return

    lookup_data[food_name] = calories
    save_json(FOOD_LOOKUP_FILE, lookup_data)

def display_today_calories():
    """display total calorie count for today."""
    log_data = load_json(FOOD_LOG_FILE)
    today = datetime.date.today().isoformat()

    if today in log_data:
        total_calories = sum(entry["calories"] for entry in log_data[today])
        print(f"Total calories today:\n{total_calories}")
    else:
        print("No food logged for today.")

def main():
    """parse command-line arguments and log food entry."""
    if len(sys.argv) < 2:
        display_today_calories()
        sys.exit(0)

    try:
        food_name = sys.argv[1]
        if food_name.isnumeric():
            raise ValueError("First argument must be a food name, not a number.")

        lookup_data = load_json(FOOD_LOOKUP_FILE)
        if len(sys.argv) == 2:
            if food_name in lookup_data:
                choice = input(f"{lookup_data[food_name]} cal? (y/n): ").strip().lower()
                if choice == 'y':
                    calories = lookup_data[food_name]
                else:
                    calories = input("Enter calorie count: ").strip()
            else:
                calories = input("Enter calorie count: ").strip()
        else:
            calories = sys.argv[2]

        if not isinstance(calories, int) and not calories.isnumeric():
            raise ValueError("Calorie count must be a number.")

        calories = int(calories)
        log_food(food_name, calories)
        update_food_lookup(food_name, calories)

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
