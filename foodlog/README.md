# foodlog

A simple command-line tool for tracking daily food intake and calories.

## Features

- 🍽️ Log food entries with calories
- 📊 Track daily calorie intake
- 🔍 Food lookup and memory
- 🌈 Color-coded calorie tracking
- 📝 Easy editing of food log

## Installation

1. Ensure you have Python 3.7+ installed
2. Install required dependencies:
   ```bash
   pip install prompt_toolkit
   ```

## Usage

### Log a Food Entry

```bash
# Log a food item with calories
python main.py "Chicken Salad" 350

# Log a food item by name (if in lookup)
python main.py "Chicken Salad"
```

### View Today's Food Log

```bash
# Simply run without arguments to display today's entries
python main.py
```

### Edit Food Log

```bash
# Open food log in default editor
python main.py --edit
```

## How It Works

- Logs are stored in `~/.cabinet/log/food.json`
- Food calories are remembered in `~/.cabinet/log/food_lookup.json`
- Calories are color-coded:
  - 🟢 Green: ≤ 1700 calories
  - 🟡 Yellow: Between 1700-2000 calories
  - 🔴 Red: > 2000 calories

## Dependencies

- Python 3.7+
- `prompt_toolkit`
- `cabinet` (custom library)

## Configuration

The tool uses [Cabinet](https://www.github.com/tylerjwoodfin/cabinet) to determine log directories and editor preferences.