"""
LifeLog - A simple tool to log certain life events.
"""

from datetime import datetime
from cabinet import Cabinet

class LifeLog:
    """
    LifeLog class to log certain life events.
    """

    def __init__(self):
        self.cabinet = Cabinet()
        self.path_csv: str | None = self.cabinet.get("lifelog", "file", return_type=str)
        self.options: list[str] | None = self.cabinet.get("lifelog", "options", return_type=list)

    def present_options(self) -> int:
        """
        Present the options to the user.
        """
        if not self.options:
            raise ValueError("Options are not set.")

        print("Choose an option:")
        for i, option in enumerate(self.options):
            print(f"{i + 1}. {option}")

        selected_option: int = int(input("\n"))
        if selected_option not in range(1, len(self.options) + 1):
            raise ValueError("Invalid option selected.")

        return selected_option

    def update_log(self, event: str) -> None:
        """
        Write the event to the log file.

        Args:
            event (str): event (one of self.options) to log
        """
        if self.options and event not in self.options:
            raise ValueError(f"Event '{event}' is not in the options.")

        # create the file if it doesn't exist
        if not self.path_csv:
            raise FileNotFoundError("Path to the log file is not set.")

        with open(self.path_csv, "a", encoding="utf-8") as file:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file.write(f"{current_time},{event}\n")

        print(f"Event '{event}' logged to '{self.path_csv}'.")

def main() -> None:
    """
    Main function to run the LifeLog tool.
    """
    lifelog = LifeLog()
    event_index: int = lifelog.present_options()

    if not lifelog.options:
        raise ValueError("Options are not set.")

    lifelog.update_log(lifelog.options[event_index - 1])

if __name__ == "__main__":
    main()
