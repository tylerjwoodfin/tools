# Food Log

A simple command-line tool for logging food entries and tracking calories. The tool automatically classifies foods as healthy or junk and provides a visual summary of your eating habits.

## Features

- Log food entries with calorie counts
- Automatic food classification (healthy vs junk)
- Visual summary of daily calorie intake with healthy/junk breakdown
- Food lookup database to remember calorie counts
- AI-powered calorie suggestions for unknown foods

## Usage

### Basic Logging
```bash
foodlog "food name" calories
```

Example:
```bash
foodlog "chicken salad" 540
```

### View Today's Log
```bash
foodlog
```

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

## Data Storage

- Food entries are stored in `~/.cabinet/log/food.json`
- Food lookup database is stored in `~/.cabinet/log/food_lookup.json`

## Configuration

The tool uses:
- [Cabinet](https://www.github.com/tylerjwoodfin/cabinet). 
  - You can set:
    - `foodlog -> calorie_target`: Your daily calorie target (default: 1750)
    - `keys -> openai`: Your OpenAI API key for AI-powered features
- [tyler-python-helpers](https://github.com/tylerjwoodfin/python-helpers)
  - `pipx install tyler-python-helpers`

## Notes

- The tool automatically classifies foods as healthy or junk based on common nutritional knowledge
- For new foods, you can use the 'ai' option to get calorie suggestions from ChatGPT
- The summary view's bar graph scales based on your highest calorie day, making it easy to compare daily intake