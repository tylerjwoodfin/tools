#!/usr/bin/env python3

"""A simple food logging tool that logs food entries and calorie counts."""

import json
import sys
import os
import datetime
from tyler_python_helpers import ChatGPT
from prompt_toolkit import print_formatted_text, HTML
from cabinet import Cabinet

cabinet = Cabinet()
chatgpt = ChatGPT()

# define file paths
LOG_DIR = cabinet.get("path", "cabinet", "log") or os.path.expanduser("~/.cabinet/log")
FOOD_LOG_FILE = os.path.join(LOG_DIR, "food.json")
FOOD_LOOKUP_FILE = os.path.join(LOG_DIR, "food_lookup.json")

def ensure_log_directory() -> None:
    """create log directory if it doesn't exist."""
    os.makedirs(LOG_DIR, exist_ok=True)

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

def log_food(food_name: str, calories: int, is_yesterday: bool = False) -> None:
    """log food entry for today's date."""
    ensure_log_directory()
    log_data = load_json(FOOD_LOG_FILE)
    today = datetime.date.today().isoformat()

    if is_yesterday:
        today = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    if today not in log_data:
        log_data[today] = []

    # Ensure calories is an integer
    if isinstance(calories, dict):
        calories = calories.get("calories", 0)
    elif isinstance(calories, str) and calories.isnumeric():
        calories = int(calories)

    log_data[today].append({"food": food_name, "calories": calories})
    save_json(FOOD_LOG_FILE, log_data)
    print_formatted_text(HTML(
        f'<green>Logged:</green> {food_name} <yellow>({calories} cal)</yellow>'))

    display_today_calories()

def update_food_lookup(food_name: str, calories: int) -> None:
    """update food lookup file with food and calorie information."""
    lookup_data = load_json(FOOD_LOOKUP_FILE)

    if isinstance(calories, str) and calories.isnumeric():
        calories = int(calories)

    if food_name in lookup_data:
        if lookup_data[food_name]["calories"] != calories:
            print_formatted_text(HTML(
                f'<yellow>{food_name}</yellow> has <yellow>{lookup_data[food_name]["calories"]} cal</yellow>.'))
            choice = input("Overwrite? (y/n): ").strip().lower()
            if choice != 'y':
                return
        lookup_data[food_name]["calories"] = calories
    else:
        lookup_data[food_name] = {"calories": calories, "type": "unknown"}

    save_json(FOOD_LOOKUP_FILE, lookup_data)

def display_today_calories() -> None:
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
            # Ensure calories is an integer
            if isinstance(calories, dict):
                calories = calories.get("calories", 0)
            total_calories += calories

            # Pad calories to maintain consistent alignment
            padded_calories = str(calories).ljust(4)  # Use fixed width of 4 characters

            print_formatted_text(HTML(
                f'{padded_calories}cal - <green>{food}</green>'))

        calorie_target = cabinet.get("foodlog", "calorie_target")
        if calorie_target is None:
            cabinet.log("Calorie target not set, using 1750", level="warning")
            calorie_target = 1750

        # Color-code total calories. +- 150 is green, 150-300 is yellow, over 300 is red
        if abs(total_calories - calorie_target) <= 150:
            total_color = 'green'
        elif abs(total_calories - calorie_target) <= 300:
            total_color = 'yellow'
        else:
            total_color = 'red'
            
        print_formatted_text(HTML(
            f'\n<bold>Total today:</bold> <{total_color}>{total_calories}</{total_color}>'))
    else:
        print_formatted_text(HTML('<yellow>No food logged for today.</yellow>'))

def get_calories(food_name: str, lookup_data: dict) -> int:
    """get calorie count for a food item, either from lookup or user input."""
    if food_name in lookup_data:
        calories = lookup_data[food_name].get("calories")
        if calories is None:
            raise ValueError(f"No calorie data found for {food_name}")
        print(f"{calories} cal found for {food_name}.\n")
        choice = input("Use this? (y/n): ").strip().lower()
        if choice == 'y':
            return calories

    calories = input("Enter calorie count, or 'ai' to ask ChatGPT: ").strip()
    if calories == 'ai':
        ai_calories = query_chatgpt(food_name)
        print(f"\nChatGPT suggests: {ai_calories} calories")
        calories = input("Use this value? (y/n): ").strip().lower()
        if calories == 'y':
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
    
    # Create a prompt that lists all foods and asks for classification
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

    # Parse the response into a dictionary
    classifications = {}
    for line in response.split('\n'):
        if ':' in line:
            food, classification = line.split(':', 1)
            classifications[food.strip()] = classification.strip().lower()
    
    return classifications

def show_summary() -> None:
    """Display a summary of the past 7 days of food entries with AI classification."""
    log_data = load_json(FOOD_LOG_FILE)
    lookup_data = load_json(FOOD_LOOKUP_FILE)
    today = datetime.date.today()
    
    print_formatted_text(HTML('<bold><underline>Food Summary (Last 7 Days)</underline></bold>\n'))
    
    # First, collect all unique food items from the past 7 days
    all_foods = set()
    daily_totals = {}  # Store daily totals for the bar graph
    daily_healthy = {}  # Store daily healthy calories
    daily_junk = {}     # Store daily junk calories
    for i in range(7):
        date = today - datetime.timedelta(days=i)
        date_str = date.isoformat()
        if date_str in log_data:
            daily_totals[date] = sum(entry["calories"] for entry in log_data[date_str])
            daily_healthy[date] = 0
            daily_junk[date] = 0
            for entry in log_data[date_str]:
                all_foods.add(entry["food"])
    
    # Get classifications for all foods at once
    foods_to_classify = []
    for food in all_foods:
        if food not in lookup_data or "type" not in lookup_data[food] or \
            lookup_data[food]["type"] == "unknown":
            foods_to_classify.append(food)
    
    if foods_to_classify:
        classifications = classify_food(foods_to_classify)
        
        # Update the lookup file with new classifications
        for food, classification in classifications.items():
            if food not in lookup_data:
                lookup_data[food] = {"calories": 0, "type": classification}
            else:
                lookup_data[food]["type"] = classification
        save_json(FOOD_LOOKUP_FILE, lookup_data)
    else:
        classifications = {}
    
    total_calories = 0
    healthy_calories = 0
    junk_calories = 0
    
    # Display entries in reverse chronological order
    for i in range(6, -1, -1):
        date = today - datetime.timedelta(days=i)
        date_str = date.isoformat()
        
        if date_str in log_data:
            print_formatted_text(HTML(f'\n<bold>{date.strftime("%a, %Y-%m-%d")}</bold>'))
            
            for entry in log_data[date_str]:
                food = entry["food"]
                calories = entry["calories"]
                total_calories += calories
                
                # Get the classification from the lookup file
                if food in lookup_data:
                    classification = lookup_data[food].get("type", "unknown")
                else:
                    classification = "unknown"
                
                if classification == "healthy":
                    healthy_calories += calories
                    daily_healthy[date] += calories
                    food_color = "green"
                else:
                    junk_calories += calories
                    daily_junk[date] += calories
                    food_color = "red"
                
                print_formatted_text(HTML(
                    f'  {calories} cal - <{food_color}>{food}</{food_color}> ({classification})'))
    
    # Print summary statistics
    print_formatted_text(HTML('\n<bold>Summary Statistics:</bold>'))
    print_formatted_text(HTML(f'  Total calories: {total_calories}'))
    if total_calories > 0:
        print_formatted_text(HTML(f'  Healthy calories: <green>{healthy_calories}</green> ({healthy_calories/total_calories*100:.1f}%)'))
        print_formatted_text(HTML(f'  Junk calories: <red>{junk_calories}</red> ({junk_calories/total_calories*100:.1f}%)'))
    else:
        print_formatted_text(HTML('  No calories logged in the past 7 days'))
    
    # Add daily totals bar graph
    print_formatted_text(HTML('\n<bold>Daily Calorie Totals:</bold>'))
    
    # Find the maximum calories for scaling the bar graph
    max_calories = max(daily_totals.values()) if daily_totals else 0
    bar_width = 25  # Maximum width of the bar graph in characters
    
    # Display bars in reverse chronological order
    for i in range(6, -1, -1):
        date = today - datetime.timedelta(days=i)
        if date in daily_totals:
            total = daily_totals[date]
            healthy = daily_healthy[date]
            junk = daily_junk[date]
            
            # Calculate the scaled bar length based on total calories
            scaled_length = int((total / max_calories) * bar_width) if max_calories > 0 else 0
            
            # Calculate the healthy/junk ratio within the scaled length
            healthy_length = int((healthy / total) * scaled_length) if total > 0 else 0
            junk_length = scaled_length - healthy_length
            
            # Create the bar with both colors
            bar = f'<green>{"█" * healthy_length}</green><red>{"█" * junk_length}</red>'
            
            print_formatted_text(HTML(
                f'  {date.strftime("%a")}: {bar} {total} cal'))

def main() -> None:
    """parse command-line arguments and log food entry."""
    is_yesterday = False

    if len(sys.argv) < 2:
        display_today_calories()
        sys.exit(0)

    if sys.argv[1] == "--edit":
        edit_food_json()
        sys.exit(0)
        
    if sys.argv[1] == "--summary":
        show_summary()
        sys.exit(0)

    try:
        # Join all arguments and split by //
        full_command = " ".join(sys.argv[1:])
        if "//" in full_command:
            # Split into separate commands and process each one
            commands = [cmd.strip() for cmd in full_command.split("//")]
            for cmd in commands:
                # Create new sys.argv for each command
                cmd_args = cmd.split()
                # Save original sys.argv and restore it after each command
                original_argv = sys.argv.copy()
                sys.argv = [sys.argv[0]] + cmd_args
                try:
                    main()
                finally:
                    sys.argv = original_argv
            return

        # Check if --yesterday is present and remove it
        if "--yesterday" in sys.argv:
            is_yesterday = True
            sys.argv.remove("--yesterday")

        # Regular single command processing
        food_name = " ".join(sys.argv[1:-1])
        calories = sys.argv[-1]

        # last arg is a string -> calories not set; get from lookup
        if isinstance(calories, str) and not calories.isnumeric():
            food_name = " ".join(sys.argv[1:])
            lookup_data = load_json(FOOD_LOOKUP_FILE)
            calories = get_calories(food_name, lookup_data)
        else:
            calories = int(calories)

        log_food(food_name, calories, is_yesterday)
        update_food_lookup(food_name, calories)

    except ValueError as e:
        print_formatted_text(HTML(f'<red>Error: {e}</red>'))
        sys.exit(1)

def edit_food_json() -> None:
    """Edit the food.json file."""
    os.system(f"{cabinet.editor} {FOOD_LOG_FILE}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)