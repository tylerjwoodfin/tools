"""
venmo parser
"""

import json
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from pathlib import Path
import pandas as pd # type: ignore # pylint: disable=import-error

# Hide the main tkinter window
Tk().withdraw()

# Prompt the user to pick a CSV file
file_path = askopenfilename(filetypes=[("CSV files", "*.csv")])

# Check if a file was selected
if file_path:
    # Read the selected CSV file into a DataFrame, skipping the extra header rows if needed
    transactions_df = pd.read_csv(file_path, skiprows=2, dtype=str)
    print("CSV file successfully loaded!")
    print("Columns in the DataFrame:", transactions_df.columns)
else:
    print("No file selected.")
    exit()

# Load categories from JSON file
categories_file_path = Path.home() / "syncthing/md/docs/selfhosted/venmo_categories.json"
try:
    with open(categories_file_path, 'r', encoding='utf-8') as file:
        category_mapping = json.load(file)['categories']
except FileNotFoundError:
    print("Categories JSON file not found.")
    exit()

# Define categorization logic
def categorize_transaction(note):
    """
    Categorizes transactions based on keywords from the JSON file.
    """
    note_lower = note.lower()
    for category, keywords in category_mapping.items():
        if any(keyword in note_lower for keyword in keywords):
            return category
    return 'Other'

# Apply categorization
transactions_df['Note'] = transactions_df['Note'].fillna('')
transactions_df['Category'] = transactions_df['Note'].apply(categorize_transaction)

def clean_amount(value):
    """
    function to clean and convert the amount
    """
    if isinstance(value, str):
        # Remove dollar signs, commas, spaces, and ensure correct formatting
        cleaned_value = value.replace('$', '').replace(',', '').replace(' ', '').strip()
        return float(cleaned_value)
    elif pd.isnull(value):
        return 0.0  # Handle NaN as 0, or set to another default if needed
    else:
        return float(value)  # If already a number, just return it as is

# Adjust amounts: negative for "Charge" and positive for "Payment"
transactions_df['Adjusted Amount'] = transactions_df.apply(
    lambda row: -clean_amount(row['Amount (total)']) if row['Type'] == 'Charge' \
        else clean_amount(row['Amount (total)']),
    axis=1
)

# Ensure the Datetime column is properly formatted for sorting
transactions_df['Datetime'] = pd.to_datetime(transactions_df['Datetime'], errors='coerce')

# Create a filtered DataFrame with the relevant columns and sort by Category and Date
summary_df = transactions_df[['Datetime', 'Category', 'Adjusted Amount', 'Note']].sort_values(
    ['Category', 'Datetime']
) # type: ignore

# Print the summary table to the terminal
print("\nTransaction Summary (Sorted by Category and Date):")
print(summary_df.to_string(index=False))

# Calculate the totals for each category
totals_df = summary_df.groupby('Category')['Adjusted Amount'].sum().reset_index()

# Verify the calculations
totals_sum = summary_df['Adjusted Amount'].sum()
calculated_totals_sum = totals_df['Adjusted Amount'].sum()

totals_df['Check'] = calculated_totals_sum == totals_sum

# Print the totals for verification to the terminal
print("\nCategory Totals:")
print(totals_df.to_string(index=False))
