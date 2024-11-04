"""
venmo parser
"""

import json
import argparse
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from typing import Dict
import pandas as pd  # type: ignore # pylint: disable=import-error

class VenmoParser:
    """
    Parses Venmo transactions from a CSV file and categorizes them based on keywords.
    See the README for more information.
    """

    def __init__(self, file_path: str, category_file: Path):
        """
        initializes the transaction processor with the CSV file path and category mapping file path
        """
        self.file_path = file_path
        self.category_file = category_file
        self.transactions_df = pd.DataFrame()
        self.category_mapping: Dict[str, list] = {}

    def load_categories(self) -> None:
        """loads categories from the specified JSON file"""
        try:
            with open(self.category_file, 'r', encoding='utf-8') as file:
                self.category_mapping = json.load(file)['categories']
        except FileNotFoundError:
            print("categories JSON file not found.")
            exit()

    def load_transactions(self) -> None:
        """loads the transactions from the CSV file"""
        self.transactions_df = pd.read_csv(self.file_path, skiprows=2, dtype=str)
        print("CSV file successfully loaded!")

    def categorize_transaction(self, note: str) -> str:
        """
        categorizes transactions based on keywords from the JSON file
        """
        note_lower = note.lower()
        for category, keywords in self.category_mapping.items():
            if any(keyword in note_lower for keyword in keywords):
                return category
        return 'Other'

    def clean_amount(self, value: str) -> float:
        """
        cleans and converts the amount to a float
        """
        if isinstance(value, str):
            cleaned_value = value.replace('$', '').replace(',', '').replace(' ', '').strip()
            return float(cleaned_value)
        elif pd.isnull(value):
            return 0.0  # handle NaN as 0
        else:
            return float(value)  # if already a number, return it as is

    def process_transactions(self) -> pd.DataFrame:
        """processes transactions by categorizing and cleaning amounts"""
        self.transactions_df['Note'] = self.transactions_df['Note'].fillna('')
        self.transactions_df['Category'] = \
            self.transactions_df['Note'].apply(self.categorize_transaction)

        self.transactions_df['Adjusted Amount'] = self.transactions_df.apply(
            lambda row: -self.clean_amount(row['Amount (total)']) if row['Type'] == 'Charge'
            else self.clean_amount(row['Amount (total)']),
            axis=1
        )

        # ensure the datetime column is formatted for sorting
        self.transactions_df['Datetime'] = pd.to_datetime(
            self.transactions_df['Datetime'], errors='coerce')

        # create and sort the summary DataFrame
        category_order = sorted(self.category_mapping.keys()) + ['Other']
        summary_df = self.transactions_df.loc[:, ['Datetime', 'Category',
                                                  'Adjusted Amount', 'Note']]
        summary_df['Category'] = pd.Categorical(summary_df['Category'],
                                                categories=category_order, ordered=True)
        summary_df = summary_df.sort_values(by=['Category', 'Datetime']) # type: ignore # pylint: disable=no-member

        return summary_df

    def print_summary(self, summary_df: pd.DataFrame) -> None:
        """prints the transaction summary and category totals"""
        print("\nTransaction Summary (Sorted by Category and Date):")
        print(summary_df.to_string(index=False))

        # calculate totals for each category
        totals_df = summary_df.groupby('Category',
                                       observed=True)['Adjusted Amount'].sum().reset_index()

        # move 'Other' category to the end
        totals_df['Category'] = pd.Categorical(totals_df['Category'],
                                               categories=sorted(self.category_mapping.keys()) \
                                                   + ['Other'],
                                               ordered=True)
        totals_df = totals_df.sort_values(by='Category')

        # verify calculations
        totals_sum = summary_df['Adjusted Amount'].sum()
        calculated_totals_sum = totals_df['Adjusted Amount'].sum()
        totals_df['Check'] = calculated_totals_sum == totals_sum

        print("\nCategory Totals:")
        print(totals_df.to_string(index=False))

def main() -> None:
    """main function to handle argument parsing and execution"""
    parser = argparse.ArgumentParser(description="Parse and categorize Venmo transactions.")
    parser.add_argument('--file', type=str, help='Path to the CSV file', required=False)

    args = parser.parse_args()

    # if no --file argument is provided, use tkinter to select the file
    file_path = args.file
    if not file_path:
        Tk().withdraw()
        file_path = askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not file_path:
            print("No file selected.")
            exit()

    # set the path for the category JSON file
    categories_file_path = Path.home() / "syncthing/md/docs/selfhosted/venmo_categories.json"

    # process transactions
    processor = VenmoParser(file_path=file_path, category_file=categories_file_path)
    processor.load_categories()
    processor.load_transactions()
    summary_df = processor.process_transactions()
    processor.print_summary(summary_df)

if __name__ == "__main__":
    main()
