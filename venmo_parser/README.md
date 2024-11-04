# Venmo Transaction Parser

A simple Python script to read a Venmo transaction CSV and parse it into categories.

## Dependencies
- Python 3.6+
- pandas
- tkinter (`brew install python-tk` on macOS)

## Usage

- Set up a categories JSON file (modify the path as needed) like the example below:
```
{
    "categories": {
        "Groceries": [
            "groceries",
            "trader joe",
            "mochi",
            "onion",
            "grapes",
            "cookies",
            "milk",
            "paper towels",
            "apples",
            "factor",
            "frozen meal"
        ],
        "Restaurants": [
            "dinner",
            "restaurant",
            "pho",
            "korean",
            "meal"
        ]
    }
}
```
- `python3 venmo_parser.py` to run the script.
- Select the CSV file to parse. I recommend your monthly Venmo transaction statement.

Any transaction containing any of the keywords (wildcard) in the categories will be assigned to that category.

## Example Output
```
2024-10-29 03:51:23   Groceries            -4.98                                   Apples
2024-10-29 03:51:40   Groceries           -39.26                       Delivery - 6 meals
2024-10-31 17:01:59   Groceries             3.00                                Groceries
2024-10-02 20:30:53       Other          -353.48                 Flights for Thanksgiving
2024-10-06 06:31:23       Other          -104.81                                    Hotel
2024-10-12 03:04:33       Other           -25.00                                      Gas
2024-10-14 01:55:57       Other           -33.16                                      Gas
2024-10-14 01:56:16       Other           -15.19                     Electricity, October
2024-10-12 01:29:12 Restaurants            18.45                         Tulan restaurant
2024-10-13 01:15:31 Restaurants           -21.60                         🇰🇷 Korean dinner
2024-10-13 04:06:08 Restaurants            22.50                              Pho Vietnam

Category Totals:
   Category  Adjusted Amount  Check
  Groceries          -102.20   True
      Other          -973.40   True
Restaurants           -53.15   True
```

If the transaction is a 'charge', it is counted as a positive amount. If it is a 'payment', it is counted as a negative amount.