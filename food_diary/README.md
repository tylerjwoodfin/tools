# Food Log

A simple Python script for logging daily food intake and tracking calories.

## Features
- Logs food items and calorie counts to `food.json` under the current date.
- Maintains a `food_lookup.json` file to store known food items and their calorie counts.
- If only a food name is provided, checks the lookup file and suggests the stored calorie count.
- Displays the total calories logged for the current day when run without arguments.
- Ensures the logging directory exists (`~/syncthing/log`).

## Installation
Ensure you have Python 3 installed. Clone or download the script and place it in a convenient location.

## Usage
```sh
python3 food.py <food name> <# of calories>
```

### Examples
#### Logging a new food entry
```sh
python3 food.py Apple 95
```
This logs "Apple" with 95 calories to today's entry.

#### Checking today's total calories
```sh
python3 food.py
```
Displays the total calories consumed today.

#### Using stored calorie values
```sh
python3 food.py Banana
```
If "Banana" exists in `food_lookup.json`, the script will ask:
```
105 cal? (y/n):
```
If you confirm with `y`, it logs 105 calories. Otherwise, you can enter a new calorie count.

#### Handling duplicate food entries
If a food item exists in `food_lookup.json` but with a different calorie count, the script will prompt:
```
Banana is already recorded with 100 cal.
Overwrite? (y/n):
```
If `y` is selected, the stored value is updated.

## File Storage
- **Food log**: `~/syncthing/log/food.json`
- **Food lookup table**: `~/syncthing/log/food_lookup.json`

## Error Handling
- If the first argument is numeric, the script exits with an error.
- If no calorie count is provided and the food is not in the lookup file, the script prompts for input.
- If an invalid calorie value is entered, the script exits with an error.

## License
This script is provided as-is with no warranty. Feel free to modify and improve it!