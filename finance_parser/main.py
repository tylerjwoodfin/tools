"""
Multi-file transaction parser for Venmo and Citi CSV files.
"""

import json
import argparse
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from typing import Dict
import argcomplete
import pandas as pd  # type: ignore # pylint: disable=import-error

class BaseParser:
    """
    Base class for all parsers.
    """
    def __init__(self, file_path: str, category_file: Path):
        self.file_path = file_path
        self.category_file = category_file
        self.transactions_df = pd.DataFrame()
        self.category_mapping: Dict[str, list] = {}
        self.filtered_rows: list = []

    def load_categories(self) -> None:
        """Loads categories from the specified JSON file."""
        try:
            with open(self.category_file, 'r', encoding='utf-8') as file:
                print("Opening categories JSON file:", self.category_file)
                self.category_mapping = json.load(file)['categories']
        except FileNotFoundError:
            print("Categories JSON file not found.")
            exit()

    def categorize_transaction(self, note: str) -> str:
        """
        Categorizes transactions based on keywords from the JSON file.
        """
        note_lower = note.lower()
        for category, keywords in self.category_mapping.items():
            if any(keyword.lower() in note_lower for keyword in keywords):
                return category
        return 'Other'

    def clean_amount(self, value: str) -> float:
        """
        Cleans and converts the amount to a float.
        """
        if isinstance(value, str):
            cleaned_value = value.replace('$', '').replace(',', '').replace(' ', '').strip()
            return float(cleaned_value)
        elif pd.isnull(value):
            return 0.0  # Handle NaN as 0
        else:
            return float(value)

    def process_transactions(self, source: str) -> pd.DataFrame:
        """Processes transactions to categorize and clean amounts."""
        raise NotImplementedError("Subclasses must implement this method.")

    def print_summary(self, summary_df: pd.DataFrame) -> None:
        """Prints the transaction summary and category totals."""
        print("\nTransaction Summary (Sorted by Category and Date):")
        print(summary_df.to_string(index=False))

        # Calculate totals for each category
        totals_df = summary_df.groupby('Category',
                                       observed=True)['Adjusted Amount'].sum().reset_index()

        # Move 'Other' category to the end
        totals_df['Category'] = pd.Categorical(
            totals_df['Category'],
            categories=sorted(self.category_mapping.keys()) + ['Other'],
            ordered=True
        )
        totals_df = totals_df.sort_values(by='Category')

        print("\nCategory Totals:")
        print(totals_df.to_string(index=False))


class VenmoParser(BaseParser):
    """
    Parses Venmo transactions from a CSV file.
    """
    def load_transactions(self) -> None:
        """Loads Venmo transactions from the CSV file."""
        # Automatically find the header row
        with open(self.file_path, 'r', encoding='utf-8') as file:
            for i, line in enumerate(file):
                if "Datetime" in line and "Note" in line:
                    header_row = i
                    break
            else:
                print("Error: Could not find the header row in the Venmo CSV file.")
                exit()

        # Load the CSV starting from the header row
        self.transactions_df = pd.read_csv(self.file_path, skiprows=header_row, dtype=str)
        print("Venmo CSV file successfully loaded!")

    def process_transactions(self, source: str = "Venmo") -> pd.DataFrame:
        """Processes Venmo transactions to categorize and clean amounts."""
        self.transactions_df['Note'] = self.transactions_df['Note'].fillna('')
        self.transactions_df['Category'] = \
            self.transactions_df['Note'].apply(self.categorize_transaction)

        self.transactions_df['Adjusted Amount'] = self.transactions_df.apply(
            lambda row: -self.clean_amount(row['Amount (total)']),
            axis=1
        )

        self.transactions_df['Datetime'] = pd.to_datetime(
            self.transactions_df['Datetime'], errors='coerce')

        self.transactions_df['Source'] = source
        return self.transactions_df.loc[:, ['Datetime',
                                            'Category', 'Adjusted Amount', 'Note', 'Source']]


class CitiParser(BaseParser):
    """
    Parses Citi transactions from a CSV file in the format:
    Status,Date,Description,Debit,Credit
    For budget tracking: debits (spending) are positive, credits (money received) are negative
    """
    def load_categories(self) -> None:
        """Loads categories and filtered rows from the specified JSON file."""
        try:
            with open(self.category_file, 'r', encoding='utf-8') as file:
                config = json.load(file)
                self.category_mapping = config['categories']
                self.filtered_rows = config.get('filteredRows', [])
        except FileNotFoundError:
            print("Categories JSON file not found.")
            exit()

    def load_transactions(self) -> None:
        """Loads Citi transactions from the CSV file."""
        try:
            self.transactions_df = pd.read_csv(self.file_path, dtype=str)
            print("Citi CSV file successfully loaded!")
        except Exception as e: # pylint: disable=broad-except
            print(f"Error loading Citi CSV file: {e}")
            exit()

    def should_include_transaction(self, description: str) -> bool:
        """
        Determines if a transaction should be included based on filtered rows.
        """
        return not any(filtered_text.lower() in description.lower() 
                      for filtered_text in self.filtered_rows)

    def process_transactions(self, source: str = "Citi") -> pd.DataFrame:
        """Processes Citi transactions to categorize and clean amounts."""
        # Filter out unwanted transactions
        self.transactions_df = self.transactions_df[
            self.transactions_df['Description'].apply(self.should_include_transaction)
        ]

        # Categorize based on Description
        self.transactions_df['Category'] = \
            self.transactions_df['Description'].apply(self.categorize_transaction)

        # Handle amount calculation from Debit and Credit columns
        def calculate_amount(row):
            debit = self.clean_amount(row['Debit']) if pd.notna(row['Debit']) else 0
            credit = self.clean_amount(row['Credit']) if pd.notna(row['Credit']) else 0
            # Debits should be positive (money spent)
            # Credits remain negative (money received)
            return debit + credit

        self.transactions_df['Adjusted Amount'] = \
            self.transactions_df.apply(calculate_amount, axis=1)

        # Convert date string to datetime
        self.transactions_df['Datetime'] = pd.to_datetime(
            self.transactions_df['Date'], format='%m/%d/%Y', errors='coerce')

        # Add source column
        self.transactions_df['Source'] = source

        # Return only the columns we need
        return self.transactions_df.loc[:, ['Datetime', 'Category', 'Adjusted Amount', 'Description', 'Source']]

def ask_for_file(file_description: str) -> str:
    """Prompts the user to select a file via a file dialog."""
    print(f"Please select the {file_description} file.")
    Tk().withdraw()
    file_path = askopenfilename(filetypes=[("CSV files", "*.csv")])
    if not file_path:
        print("No file selected.")
        exit()
    return file_path


def main() -> None:
    """Main function to handle argument parsing and execution."""
    parser = argparse.ArgumentParser(description=
                                     "Parse and categorize transactions from relevant CSV files.")
    parser.add_argument("-venmo", type=str,
                        help="Path to the Venmo transactions CSV file", required=False)
    parser.add_argument("-citi", type=str,
                        help="Path to the Citi transactions CSV file", required=False)
    args = parser.parse_args()

    # Enable autocompletion
    argcomplete.autocomplete(parser)

    # Set the path for the category JSON file
    categories_file_path = Path.home() / "syncthing/md/docs/selfhosted/transaction_categories.json"

    # Use provided paths or fall back to file dialogs
    venmo_file_path = args.venmo or ask_for_file("Venmo transactions CSV")
    citi_file_path = args.citi or ask_for_file("Citi transactions CSV")

    # Process Venmo transactions
    venmo_parser = VenmoParser(file_path=venmo_file_path, category_file=categories_file_path)
    venmo_parser.load_categories()
    venmo_parser.load_transactions()
    venmo_summary_df = venmo_parser.process_transactions()

    # Process Citi transactions
    citi_parser = CitiParser(file_path=citi_file_path, category_file=categories_file_path)
    citi_parser.load_categories()
    citi_parser.load_transactions()
    citi_summary_df = citi_parser.process_transactions()

    # Combine and sort transactions
    combined_df = pd.concat([venmo_summary_df, citi_summary_df]).sort_values(by=[
        'Source', 'Category', 'Datetime'])
    print("\nCombined Transactions:")
    print(combined_df.to_string(index=False))

    # Calculate totals for all transactions
    print("\nTotal Amounts by Category:")
    totals_df = combined_df.groupby('Category')['Adjusted Amount'].sum().reset_index()
    print(totals_df.to_string(index=False))


if __name__ == "__main__":
    main()
