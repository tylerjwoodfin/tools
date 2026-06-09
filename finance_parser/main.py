"""
Multi-file transaction parser for Venmo and other CSV files.
"""

import json
import argparse
from pathlib import Path
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from datetime import datetime, timedelta
from typing import Dict, Optional
import argcomplete  # type: ignore # pylint: disable=import-error
import pandas as pd  # type: ignore # pylint: disable=import-error
import pyperclip  # type: ignore # pylint: disable=import-error
import ezodf  # type: ignore # pylint: disable=import-error


def find_latest_file_in_downloads(pattern: str) -> Optional[str]:
    """Finds the latest file in Downloads matching the given pattern."""
    downloads_path = Path.home() / "Downloads"
    matching_files = list(downloads_path.glob(pattern))
    if not matching_files:
        return None
    return str(max(matching_files, key=lambda x: x.stat().st_mtime))


def find_all_files_in_downloads(pattern: str) -> list[str]:
    """Finds all files in Downloads matching the given pattern."""
    downloads_path = Path.home() / "Downloads"
    matching_files = list(downloads_path.glob(pattern))
    if not matching_files:
        return []
    return [str(f) for f in matching_files]


class BaseParser:
    """Base class for all parsers."""

    def __init__(self, file_path: str, category_file: Path):
        self.file_path = file_path
        self.category_file = category_file
        self.transactions_df = pd.DataFrame()
        self.category_mapping: Dict[str, list] = {}
        self.filtered_rows: list = []

    def load_categories(self) -> None:
        """Loads categories and filtered rows from the specified JSON file."""
        try:
            with open(self.category_file, "r", encoding="utf-8") as file:
                config = json.load(file)
                self.category_mapping = config["categories"]
                self.filtered_rows = config.get("filteredRows", [])
        except FileNotFoundError:
            print("Categories JSON file not found.")
            exit()

    def should_include_transaction(self, description: str) -> bool:
        """
        Determines if a transaction should be included based on filtered rows.
        """
        if pd.isnull(description) or not isinstance(description, str):
            return True  # Include non-string values by default
        return not any(
            filtered_text.lower() in description.lower()
            for filtered_text in self.filtered_rows
        )

    def categorize_transaction(self, note: str) -> str:
        """Categorizes transactions based on keywords from the JSON file.
        Keywords starting with ! are exclusions - if matched, the category is skipped.
        """
        if pd.isnull(note) or not isinstance(note, str):
            return "Other"
        note_lower = note.lower()
        for category, keywords in self.category_mapping.items():
            # Separate include and exclude patterns
            include_keywords = [k for k in keywords if not k.startswith("!")]
            exclude_keywords = [k[1:] for k in keywords if k.startswith("!")]

            # Check if any exclusion patterns match
            if any(keyword.lower() in note_lower for keyword in exclude_keywords):
                continue  # Skip this category

            # Check if any inclusion patterns match
            if any(keyword.lower() in note_lower for keyword in include_keywords):
                return category
        return "Other"

    def clean_amount(self, value: str) -> float:
        """Cleans and converts the amount to a float."""
        if pd.isnull(value):
            return 0.0  # Handle NaN as 0

        # Skip rows with formulas
        if isinstance(value, str) and value.startswith("="):
            return 0.0

        try:
            if isinstance(value, str):
                cleaned_value = (
                    value.replace("$", "").replace(",", "").replace(" ", "").strip()
                )
                return float(cleaned_value)
            return float(value)
        except (ValueError, AttributeError):
            print(f"Warning: Could not parse amount '{value}', using 0.0")
            return 0.0

    def filter_previous_month(self, date_column: str) -> None:
        """Filters transactions to only include the previous month."""
        today = datetime.now()
        first_day_of_current_month = today.replace(day=1)
        last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
        first_day_of_previous_month = last_day_of_previous_month.replace(day=1)

        self.transactions_df = self.transactions_df[
            (self.transactions_df[date_column] >= first_day_of_previous_month)
            & (self.transactions_df[date_column] <= last_day_of_previous_month)
        ]

    def process_transactions(self, source: str) -> pd.DataFrame:
        """Processes transactions to categorize and clean amounts."""
        raise NotImplementedError("Subclasses must implement this method.")

    def print_summary(self, summary_df: pd.DataFrame) -> None:
        """Prints the transaction summary and category totals."""
        print("\nTransaction Summary (Sorted by Category and Date):")
        print(summary_df.to_string(index=False))

        # Calculate totals for each category
        totals_df = (
            summary_df.groupby("Category", observed=True)["Adjusted Amount"]
            .sum()
            .reset_index()
        )

        # Move 'Other' category to the end
        totals_df["Category"] = pd.Categorical(
            totals_df["Category"],
            categories=sorted(self.category_mapping.keys()) + ["Other"],
            ordered=True,
        )
        totals_df = totals_df.sort_values(by="Category")

        print("\nCategory Totals:")
        print(totals_df.to_string(index=False))


class VenmoParser(BaseParser):
    """
    Parses Venmo transactions from a CSV file.
    """

    def load_transactions(self) -> None:
        """Loads Venmo transactions from the CSV file."""
        # Automatically find the header row
        with open(self.file_path, "r", encoding="utf-8") as file:
            for i, line in enumerate(file):
                if "Datetime" in line and "Note" in line:
                    header_row = i
                    break
            else:
                print("Error: Could not find the header row in the Venmo CSV file.")
                exit()

        # Load the CSV starting from the header row
        self.transactions_df = pd.read_csv(
            self.file_path, skiprows=header_row, dtype=str
        )
        print("Venmo CSV file successfully loaded!")

    def process_transactions(self, source: str = "Venmo") -> pd.DataFrame:
        """Processes Venmo transactions to categorize and clean amounts."""
        # Filter out unwanted transactions
        self.transactions_df = self.transactions_df[
            self.transactions_df["Note"].apply(self.should_include_transaction)
        ]

        self.transactions_df["Note"] = self.transactions_df["Note"].fillna("")
        self.transactions_df["Category"] = self.transactions_df["Note"].apply(
            self.categorize_transaction
        )

        self.transactions_df["Adjusted Amount"] = self.transactions_df.apply(
            lambda row: -self.clean_amount(row["Amount (total)"]), axis=1
        )

        self.transactions_df["Datetime"] = pd.to_datetime(
            self.transactions_df["Datetime"], errors="coerce"
        )

        # Filter for previous month
        self.filter_previous_month("Datetime")

        self.transactions_df["Source"] = source
        return self.transactions_df.loc[
            :, ["Datetime", "Category", "Adjusted Amount", "Note", "Source"]
        ]


class EverBankParser(BaseParser):
    """
    Parses EverBank transactions from a CSV file in the format:
    Date,Check#,Transaction Type,Description,Debits(-),Credits(+)
    Debits are negative in the export; credits are positive.
    """

    def __init__(self, file_path: str, category_file: Path):
        super().__init__(file_path, category_file)
        self.transactions_df = pd.DataFrame()

    def load_transactions(self) -> None:
        """Loads EverBank transactions from the CSV file."""
        try:
            self.transactions_df = pd.read_csv(
                self.file_path, dtype=str, index_col=False
            )
            print("EverBank CSV file successfully loaded!")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error loading EverBank CSV file: {e}")
            exit()

    def process_transactions(self, source: str = "EverBank") -> pd.DataFrame:
        """Processes EverBank transactions to categorize and clean amounts."""
        self.transactions_df["Datetime"] = pd.to_datetime(
            self.transactions_df["Date"], format="%m/%d/%Y", errors="coerce"
        )

        self.filter_previous_month("Datetime")

        def calculate_amount(row):
            debit = (
                self.clean_amount(row["Debits(-)"])
                if pd.notna(row["Debits(-)"])
                else 0
            )
            credit = (
                self.clean_amount(row["Credits(+)"])
                if pd.notna(row["Credits(+)"])
                else 0
            )
            # Negative debits are spending (positive); credits are income (negative)
            return -debit - credit

        self.transactions_df["Adjusted Amount"] = self.transactions_df.apply(
            calculate_amount, axis=1
        )

        self.transactions_df = self.transactions_df[
            self.transactions_df["Description"].apply(self.should_include_transaction)
        ]

        self.transactions_df["Category"] = self.transactions_df["Description"].apply(
            self.categorize_transaction
        )

        income_categories = ["Apiture"]
        self.transactions_df.loc[
            self.transactions_df["Category"].isin(income_categories), "Adjusted Amount"
        ] *= -1

        self.transactions_df["Source"] = source

        return self.transactions_df.loc[
            :, ["Datetime", "Category", "Adjusted Amount", "Description", "Source"]
        ]


class RobinhoodParser(BaseParser):
    """
    Parses Robinhood Credit Card transactions from a CSV file.
    """

    def __init__(self, file_path: str, category_file: Path):
        super().__init__(file_path, category_file)
        self.transactions_df = pd.DataFrame()

    def load_transactions(self) -> None:
        """Loads Robinhood transactions from the CSV file."""
        try:
            self.transactions_df = pd.read_csv(self.file_path, dtype=str)
            print("Robinhood CSV file successfully loaded!")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error loading Robinhood CSV file: {e}")
            exit()

    def process_transactions(self, source: str = "Robinhood CC") -> pd.DataFrame:
        """Processes Robinhood transactions to categorize and clean amounts."""
        # Filter out declined transactions
        self.transactions_df = self.transactions_df[
            self.transactions_df["Status"] == "Posted"
        ]

        # Convert date string to datetime
        self.transactions_df["Datetime"] = pd.to_datetime(
            self.transactions_df["Date"], format="%Y-%m-%d", errors="coerce"
        )

        # Filter for previous month
        self.filter_previous_month("Datetime")

        # Clean amounts (all purchases are positive spending)
        self.transactions_df["Adjusted Amount"] = self.transactions_df["Amount"].apply(
            self.clean_amount
        )

        # Filter out unwanted transactions
        self.transactions_df = self.transactions_df[
            self.transactions_df["Description"].apply(self.should_include_transaction)
        ]

        # Categorize based on Description
        self.transactions_df["Category"] = self.transactions_df["Description"].apply(
            self.categorize_transaction
        )

        # Add source column
        self.transactions_df["Source"] = source

        # Return only the columns we need
        return self.transactions_df.loc[
            :, ["Datetime", "Category", "Adjusted Amount", "Description", "Source"]
        ]


class SchwabParser(BaseParser):
    """
    Parses Schwab transactions from a CSV file.
    """

    def __init__(self, file_path: str, category_file: Path):
        super().__init__(file_path, category_file)
        self.transactions_df = pd.DataFrame()

    def load_transactions(self) -> None:
        """Loads Schwab transactions from the CSV file."""
        try:
            # Read the CSV file directly with pandas
            self.transactions_df = pd.read_csv(self.file_path, dtype=str)
            print("Schwab CSV file successfully loaded!")
        except Exception as e:  # pylint: disable=broad-except
            print(f"Error loading Schwab CSV file: {e}")
            exit()

    def process_transactions(self, source: str = "Schwab") -> pd.DataFrame:
        """Processes Schwab transactions to categorize and clean amounts."""
        # Convert date string to datetime
        self.transactions_df["Datetime"] = pd.to_datetime(
            self.transactions_df["Date"], format="%m/%d/%Y", errors="coerce"
        )

        # Filter for previous month
        self.filter_previous_month("Datetime")

        # Clean and convert amounts, making deposits negative (money received)
        def calculate_amount(row):
            withdrawal = (
                self.clean_amount(row["Withdrawal"])
                if pd.notna(row["Withdrawal"])
                else 0
            )
            deposit = (
                self.clean_amount(row["Deposit"]) if pd.notna(row["Deposit"]) else 0
            )
            # Withdrawals are positive (money spent)
            # Deposits are negative (money received)
            return withdrawal - deposit

        self.transactions_df["Adjusted Amount"] = self.transactions_df.apply(
            calculate_amount, axis=1
        )

        # Filter out unwanted transactions
        self.transactions_df = self.transactions_df[
            self.transactions_df["Description"].apply(self.should_include_transaction)
        ]

        # Categorize based on Description
        self.transactions_df["Category"] = self.transactions_df["Description"].apply(
            self.categorize_transaction
        )

        # Income categories should be positive (flip the sign for deposits)
        income_categories = ["Apiture"]
        self.transactions_df.loc[
            self.transactions_df["Category"].isin(income_categories), "Adjusted Amount"
        ] *= -1

        # Add source column
        self.transactions_df["Source"] = source

        # Return only the columns we need
        return self.transactions_df.loc[
            :, ["Datetime", "Category", "Adjusted Amount", "Description", "Source"]
        ]


def ask_for_file(file_description: str) -> Optional[str]:
    """Prompts the user to select a file via a file dialog."""
    print(f"Please select the {file_description}.")
    Tk().withdraw()
    file_path = askopenfilename(
        filetypes=[("CSV files", "*.csv"), ("ODS files", "*.ods")]
    )
    if not file_path:
        print("No file selected.")
        return None
    return file_path


def update_spreadsheet_with_totals(
    spreadsheet_path: str,
    totals_df: pd.DataFrame,
    schwab_balance: Optional[float],
    venmo_balance: Optional[float],
) -> None:
    """Reads an ODS spreadsheet, allows the user to select a sheet, and updates only Column C."""
    # Open the spreadsheet
    doc = ezodf.opendoc(spreadsheet_path)
    sheet_names = [sheet.name for sheet in doc.sheets]

    # Display available sheets
    print("Available sheets:")
    for i, sheet in enumerate(sheet_names, start=1):
        print(f"{i}. {sheet}")

    # Ask user to select a sheet
    selected_index = int(input(f"Select a sheet (1-{len(sheet_names)}): ")) - 1
    if selected_index < 0 or selected_index >= len(sheet_names):
        print("Invalid sheet selection.")
        return

    selected_sheet = doc.sheets[selected_index]

    # Map totals to their respective categories
    unmatched_categories = []
    for _, row in totals_df.iterrows():
        category = row["Category"]
        total = row["Adjusted Amount"]
        matched = False

        # Iterate over rows in the selected sheet
        for row_idx in range(1, selected_sheet.nrows()):  # Skip the header
            cell_value = selected_sheet[row_idx, 0].value  # Column A
            if isinstance(cell_value, str):
                # Write the total to Column C
                if cell_value.strip().lower() == category.lower():
                    selected_sheet[row_idx, 2].set_value(total)
                    matched = True
                    break
                # Update Schwab balance (only if we loaded Schwab data)
                elif (
                    cell_value.strip().lower() == "schwab checking"
                    and schwab_balance is not None
                ):
                    selected_sheet[row_idx, 3].set_value(schwab_balance)
                    matched = True
                # Update Venmo balance (only if we loaded Venmo data)
                elif (
                    cell_value.strip().lower().startswith("venmo")
                    and venmo_balance is not None
                ):
                    selected_sheet[row_idx, 3].set_value(venmo_balance)
                    matched = True

        if not matched:
            unmatched_categories.append(category)

    # Save the updated document
    doc.save()
    print(f"Spreadsheet updated successfully: {spreadsheet_path}")

    # Print unmatched categories
    if unmatched_categories:
        print("\nUnmatched categories:")
        print("\n".join(unmatched_categories))
    else:
        print("\nAll categories matched successfully.")


def get_default_spreadsheet_path() -> str:
    """Returns the default spreadsheet path with the current year."""
    current_year = datetime.now().year
    return str(
        Path.home()
        / f"syncthing/documents/spreadsheets/budget/Budget {current_year}.ods"
    )


def main() -> None:
    """Main function to handle argument parsing and execution."""
    try:
        parser = argparse.ArgumentParser(
            description="Parse and categorize transactions from relevant CSV files."
        )
        parser.add_argument(
            "-spreadsheet",
            type=str,
            help="Path to the spreadsheet file",
            required=False,
        )
        args = parser.parse_args()

        # Enable autocompletion
        argcomplete.autocomplete(parser)

        # Set the path for the category JSON file
        categories_file_path = (
            Path.home() / "syncthing/md/docs/selfhosted/transaction_categories.json"
        )

        # Find files in Downloads or fall back to file browser
        venmo_file_path = (
            find_latest_file_in_downloads("VenmoStatement*.csv")
            or ask_for_file("Venmo transactions CSV")
            or None
        )

        schwab_file_path = (
            find_latest_file_in_downloads("schwab.csv")
            or find_latest_file_in_downloads("Checking_*.csv")
            or ask_for_file("Schwab transactions CSV")
            or None
        )
        everbank_file_path = (
            find_latest_file_in_downloads("Transactions_*.csv")
            or ask_for_file("EverBank transactions CSV")
            or None
        )

        # Try to find Robinhood CSV by checking for the characteristic column structure
        robinhood_file_path = None
        downloads_path = Path.home() / "Downloads"
        for csv_file in downloads_path.glob("*.csv"):
            try:
                df = pd.read_csv(csv_file, nrows=1)
                if (
                    "Cardholder" in df.columns
                    and "Points" in df.columns
                    and "Merchant" in df.columns
                ):
                    robinhood_file_path = str(csv_file)
                    print(f"Found Robinhood CSV: {csv_file.name}")
                    break
            except Exception:  # pylint: disable=broad-except
                continue

        if not robinhood_file_path:
            robinhood_file_path = ask_for_file("Robinhood Credit Card CSV") or None

        spreadsheet_path = args.spreadsheet or get_default_spreadsheet_path()

        # Process Venmo transactions
        venmo_summary_df = None
        venmo_balance = None
        if venmo_file_path:
            venmo_parser = VenmoParser(
                file_path=venmo_file_path, category_file=categories_file_path
            )
            venmo_parser.load_categories()
            venmo_parser.load_transactions()
            venmo_summary_df = venmo_parser.process_transactions()
            venmo_balance = (
                float(venmo_summary_df["Balance"].iloc[-1])
                if "Balance" in venmo_summary_df.columns
                else None
            )

        # Process Schwab transactions
        schwab_summary_df = None
        schwab_balance = None
        if schwab_file_path:
            schwab_parser = SchwabParser(
                file_path=schwab_file_path, category_file=categories_file_path
            )
            schwab_parser.load_categories()
            schwab_parser.load_transactions()
            schwab_summary_df = schwab_parser.process_transactions()
            schwab_balance = (
                float(schwab_summary_df["Balance"].iloc[-1])
                if "Balance" in schwab_summary_df.columns
                else None
            )

        # Process EverBank transactions
        everbank_summary_df = None
        if everbank_file_path:
            everbank_parser = EverBankParser(
                file_path=everbank_file_path, category_file=categories_file_path
            )
            everbank_parser.load_categories()
            everbank_parser.load_transactions()
            everbank_summary_df = everbank_parser.process_transactions()

        # Process Robinhood Credit Card transactions
        robinhood_summary_df = None
        if robinhood_file_path:
            robinhood_parser = RobinhoodParser(
                file_path=robinhood_file_path, category_file=categories_file_path
            )
            robinhood_parser.load_categories()
            robinhood_parser.load_transactions()
            robinhood_summary_df = robinhood_parser.process_transactions()

        # Combine and sort transactions
        dataframes = [
            venmo_summary_df,
            schwab_summary_df,
            everbank_summary_df,
            robinhood_summary_df,
        ]
        valid_dfs = [df for df in dataframes if df is not None]
        if not valid_dfs:
            print("No transaction files were loaded. Exiting.")
            return

        combined_df = pd.concat(valid_dfs).sort_values(
            by=["Source", "Category", "Datetime"]
        )
        print("\nCombined Transactions:")
        print(combined_df.to_string(index=False))

        # Calculate totals for all transactions
        print("\nTotal Amounts by Category:")
        totals_df = (
            combined_df.groupby("Category")["Adjusted Amount"].sum().reset_index()
        )
        print(totals_df.to_string(index=False))

        # Convert totals DataFrame to CSV format (no index)
        totals_csv = totals_df.to_csv(index=False)

        # Copy the CSV to the clipboard
        pyperclip.copy(totals_csv)
        print("\nThe CSV output has been copied to your clipboard!")

        # Update spreadsheet with totals and balances
        update_spreadsheet_with_totals(
            spreadsheet_path, totals_df, schwab_balance, venmo_balance
        )

    except KeyboardInterrupt:
        print("\nProgram interrupted by user. Exiting gracefully...")
        exit(0)
    except Exception as e:  # pylint: disable=broad-except
        print(f"\nAn error occurred: {e}")
        exit(1)


if __name__ == "__main__":
    main()
