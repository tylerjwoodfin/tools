"""
Multi-file transaction parser for Venmo and Citi CSV files.
"""

import json
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from typing import Dict
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

    def load_categories(self) -> None:
        """Loads categories from the specified JSON file."""
        try:
            with open(self.category_file, 'r', encoding='utf-8') as file:
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
        self.transactions_df = pd.read_csv(self.file_path, skiprows=2, dtype=str)
        print("Venmo CSV file successfully loaded!")

    def process_transactions(self, source: str = "Venmo") -> pd.DataFrame:
        """Processes Venmo transactions to categorize and clean amounts."""
        self.transactions_df['Note'] = self.transactions_df['Note'].fillna('')
        self.transactions_df['Category'] = \
            self.transactions_df['Note'].apply(self.categorize_transaction)

        self.transactions_df['Adjusted Amount'] = self.transactions_df.apply(
            lambda row: -self.clean_amount(row['Amount (total)']) if row['Type'] == 'Charge'
            else self.clean_amount(row['Amount (total)']),
            axis=1
        )

        self.transactions_df['Datetime'] = pd.to_datetime(
            self.transactions_df['Datetime'], errors='coerce')

        self.transactions_df['Source'] = source
        return self.transactions_df.loc[:, ['Datetime',
                                            'Category', 'Adjusted Amount', 'Note', 'Source']]


class CitiParser(BaseParser):
    """
    Parses Citi transactions from a CSV file.
    """
    def load_transactions(self) -> None:
        """Loads Citi transactions from the CSV file."""
        raw_data = pd.read_csv(self.file_path,
                               skiprows=1, names=["Amount", "Date", "Description"], dtype=str)
        raw_data = raw_data[~raw_data["Amount"].str.contains("Total", na=False)]
        raw_data = raw_data.dropna(subset=["Amount", "Description"])
        raw_data["Amount"] = raw_data["Amount"].str.replace("[^0-9.-]", "", regex=True)
        self.transactions_df = raw_data
        print("Citi CSV file successfully loaded!")

    def process_transactions(self, source: str = "Citi") -> pd.DataFrame:
        """Processes Citi transactions to categorize and clean amounts."""
        self.transactions_df['Category'] = \
            self.transactions_df['Description'].apply(self.categorize_transaction)

        self.transactions_df['Adjusted Amount'] = \
            self.transactions_df['Amount'].apply(self.clean_amount)

        self.transactions_df['Datetime'] = pd.to_datetime(
            self.transactions_df['Date'], errors='coerce')

        self.transactions_df['Source'] = source
        return self.transactions_df.loc[:, ['Datetime',
                                            'Category', 'Adjusted Amount', 'Description', 'Source']]


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
    # Set the path for the category JSON file
    categories_file_path = Path.home() / "syncthing/md/docs/selfhosted/transaction_categories.json"

    # Ask for Venmo and Citi files
    venmo_file_path = ask_for_file("Venmo transactions CSV")
    citi_file_path = ask_for_file("Citi transactions CSV")

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
        'Category', 'Datetime'])
    print("\nCombined Transactions:")
    print(combined_df.to_string(index=False))

    # Calculate totals for all transactions
    print("\nTotal Amounts by Category:")
    totals_df = combined_df.groupby('Category')['Adjusted Amount'].sum().reset_index()
    print(totals_df.to_string(index=False))


if __name__ == "__main__":
    main()
