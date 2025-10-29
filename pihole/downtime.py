#!/usr/bin/env python3
"""
Pi-hole downtime management script.

This script manages blocking and unblocking of domains based on time schedules
and holiday configurations. It integrates with Cabinet for configuration
and logging.

Usage:
    python downtime.py allow <mode>    # Unblock domains for specified mode
    python downtime.py block <mode>    # Block domains for specified mode
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from cabinet import Cabinet


class PiHoleDowntime:
    """Manages Pi-hole domain blocking based on schedules and holidays."""

    def __init__(self):
        self.cabinet = Cabinet()
        self.home_directory = Path.home()

    def check_parent_process(self) -> bool:
        """
        Check if the script is being run from Python, crontab, or atd.

        Returns:
            bool: True if parent process is allowed, False otherwise
        """
        try:
            # Get parent process ID
            parent_pid = os.getppid()

            # Get parent process info
            result = subprocess.run(
                ["ps", "-o", "comm=", "-p", str(parent_pid)],
                capture_output=True,
                text=True,
                check=True,
            )
            parent_process = result.stdout.strip()

            # Check if parent process is allowed
            allowed_processes = ["cron", "python", "atd"]
            return any(allowed in parent_process for allowed in allowed_processes)

        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def is_direct_terminal_run(self) -> bool:
        """
        Check if the script is being run directly from a terminal.

        Returns:
            bool: True if running directly from terminal, False otherwise
        """
        try:
            # Check if we have a controlling terminal
            if not os.isatty(sys.stdin.fileno()):
                return False

            # Get the command line that was used to start this process
            cmdline_result = subprocess.run(
                ["ps", "-o", "args=", "-p", str(os.getpid())],
                capture_output=True,
                text=True,
                check=True,
            )
            cmdline = cmdline_result.stdout.strip()

            # Check if this script was called from a known legitimate script
            legitimate_callers = ["one_hour_of_distraction.py", "cron", "atd"]

            for caller in legitimate_callers:
                if caller in cmdline:
                    return False

            # Get parent process ID
            parent_pid = os.getppid()

            # Get parent process info
            result = subprocess.run(
                ["ps", "-o", "comm=", "-p", str(parent_pid)],
                capture_output=True,
                text=True,
                check=True,
            )
            parent_process = result.stdout.strip()

            # If parent is Python, allow it (called from another script)
            if "python" in parent_process:
                return False

            # If parent is a shell, check the grandparent process
            shell_processes = ["bash", "zsh", "sh", "fish", "tcsh", "ksh"]
            if any(shell in parent_process for shell in shell_processes):
                try:
                    # Get grandparent process ID
                    grandparent_result = subprocess.run(
                        ["ps", "-o", "ppid=", "-p", str(parent_pid)],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    grandparent_pid = grandparent_result.stdout.strip()

                    if grandparent_pid:
                        # Get grandparent process info
                        grandparent_info = subprocess.run(
                            ["ps", "-o", "comm=", "-p", grandparent_pid],
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        grandparent_process = grandparent_info.stdout.strip()

                        # If grandparent is Python, allow it (called from Python script via shell)
                        if "python" in grandparent_process:
                            return False
                except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                    pass

            # Check if parent process is a shell (indicating direct terminal run)
            return any(shell in parent_process for shell in shell_processes)

        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            return False

    def get_holidays(self) -> List[str]:
        """
        Get the list of holidays from cabinet.

        Returns:
            List[str]: List of holiday dates in YYYY-MM-DD format
        """
        try:
            holidays = self.cabinet.get("holidays")
            if holidays is None:
                return []

            # remove past holidays
            _holidays = [holiday for holiday in holidays if holiday > datetime.now()]
            # save updated holidays to cabinet if lengths differ
            if len(_holidays) != len(holidays):
                self.cabinet.put("holidays", _holidays)
            return _holidays
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.cabinet.log(f"Error getting holidays: {e}", level="error")
            return []

    def is_holiday(self, date_obj: datetime) -> bool:
        """
        Check if a given date is a holiday.

        Args:
            date_obj: datetime object to check

        Returns:
            bool: True if the date is a holiday, False otherwise
        """
        date_str = date_obj.strftime("%Y-%m-%d")
        holidays = self.get_holidays()
        return date_str in holidays

    def should_block(self) -> bool:
        """
        Determine if blocking should proceed based on current time and holiday status.

        Returns:
            bool: True if blocking should proceed, False otherwise
        """
        now = datetime.now()
        current_hour = now.hour

        # If it's after 8PM, check tomorrow's holiday status
        if current_hour >= 20:
            tomorrow = now + timedelta(days=1)
            if self.is_holiday(tomorrow):
                self.cabinet.log(
                    "After 8PM and tomorrow is a holiday, skipping blocking"
                )
                return False
            # After 8PM: if tomorrow is not a holiday, proceed with blocking
            self.cabinet.log(
                "After 8PM and tomorrow is not a holiday, proceeding with blocking"
            )
            return True
        else:
            # Before 8PM: if today is a holiday, don't block
            if self.is_holiday(now):
                self.cabinet.log("Today is a holiday, skipping blocking")
                return False
            return True

    def get_blocklist_file(self, mode: str) -> Optional[Path]:
        """
        Get the blocklist file path for the specified mode.

        Args:
            mode: The mode (e.g., 'afternoon', 'overnight')

        Returns:
            Optional[Path]: Path to the blocklist file, or None if not found
        """
        try:
            blocklist_path = self.cabinet.get("path", "blocklist", mode)
            if not blocklist_path:
                return None

            # Resolve home directory references
            blocklist_path = blocklist_path.replace("~", str(self.home_directory))
            blocklist_path = blocklist_path.replace("$HOME", str(self.home_directory))

            return Path(blocklist_path)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.cabinet.log(
                f"Error getting blocklist file for mode '{mode}': {e}", level="error"
            )
            return None

    def read_blocklist_domains(self, blocklist_file: Path) -> List[str]:
        """
        Read domains from the blocklist file.

        Args:
            blocklist_file: Path to the blocklist file

        Returns:
            List[str]: List of domains to block/unblock
        """
        try:
            if not blocklist_file.exists():
                self.cabinet.log(
                    f"Blocklist file not found: {blocklist_file}", level="error"
                )
                return []

            with open(blocklist_file, "r", encoding="utf-8") as f:
                domains = [line.strip() for line in f if line.strip()]
            return domains

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.cabinet.log(f"Error reading blocklist file: {e}", level="error")
            return []

    def execute_pihole_command(self, command: List[str]) -> bool:
        """
        Execute a Pi-hole command via Docker.

        Args:
            command: List of command arguments

        Returns:
            bool: True if command succeeded, False otherwise
        """
        try:
            docker_cmd = ["docker", "exec", "pihole"] + command
            subprocess.run(docker_cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            self.cabinet.log(f"Pi-hole command failed: {e}", level="error")
            return False

    def cleanup_scheduled_jobs(self, mode: str):
        """
        Clean up scheduled at jobs for the specified mode.

        Args:
            mode: The mode to clean up jobs for
        """
        try:
            # Get current script path
            script_path = Path(__file__).resolve()

            # List all pending at jobs
            result = subprocess.run(["atq"], capture_output=True, text=True, check=True)

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue

                job_number = line.split()[0]

                # Check if this job contains our script and the reblock command
                job_content = subprocess.run(
                    ["at", "-c", job_number], capture_output=True, text=True, check=True
                )

                if (
                    str(script_path) in job_content.stdout
                    and "block" in job_content.stdout
                    and mode in job_content.stdout
                ):

                    # Remove the job
                    subprocess.run(["atrm", job_number], check=True)
                    self.cabinet.log(f"Removed scheduled job #{job_number} for {mode}")

        except subprocess.CalledProcessError as e:
            self.cabinet.log(f"Error cleaning up scheduled jobs: {e}", level="error")

    def allow_domains(self, mode: str):
        """
        Unblock domains for the specified mode.

        Args:
            mode: The mode (e.g., 'afternoon', 'overnight')
        """
        blocklist_file = self.get_blocklist_file(mode)
        if not blocklist_file:
            print(f"Error: blocklist_file (cabinet -g path blocklist {mode}) is empty")
            sys.exit(1)

        print(f"blocklist_file = '{blocklist_file}'")

        domains = self.read_blocklist_domains(blocklist_file)
        if not domains:
            print("Error: No domains found in blocklist file")
            sys.exit(1)

        for domain in domains:
            print(f"Unblocking: {domain}")
            # Remove regex and wildcard entries
            self.execute_pihole_command(["pihole", "--regex", "-d", domain])
            self.execute_pihole_command(["pihole", "--wild", "-d", domain])

    def block_domains(self, mode: str):
        """
        Block domains for the specified mode.

        Args:
            mode: The mode (e.g., 'afternoon', 'overnight')
        """
        # Check if blocking should proceed
        if not self.should_block():
            print("Skipping blocking functions due to holiday/time restrictions")
            return

        blocklist_file = self.get_blocklist_file(mode)
        if not blocklist_file:
            print(f"Error: blocklist_file (cabinet -g path blocklist {mode}) is empty")
            sys.exit(1)

        print(f"blocklist_file = '{blocklist_file}'")

        domains = self.read_blocklist_domains(blocklist_file)
        if not domains:
            print("Error: No domains found in blocklist file")
            sys.exit(1)

        for domain in domains:
            print(f"Blocking: {domain}")
            self.execute_pihole_command(["pihole", "--wild", domain])

    def run(self, action: str, mode: str):
        """
        Main execution method.

        Args:
            action: 'allow' or 'block'
            mode: The mode (e.g., 'afternoon', 'overnight')
        """
        print("starting")

        # Check if running directly from terminal (prevent direct execution)
        if self.is_direct_terminal_run():
            print("Error: This script cannot be run directly from the terminal.")
            print("It can only be executed from Python scripts, crontab, or atd.")
            sys.exit(1)

        # If running in allow mode from crontab, clean up scheduled jobs
        if action == "allow" and self.check_parent_process():
            print("Cleaning up scheduled jobs...")
            self.cleanup_scheduled_jobs(mode)

        # Execute the requested action
        if action == "allow":
            self.allow_domains(mode)
        elif action == "block":
            self.block_domains(mode)
        else:
            print(f"Invalid argument: {action}. Use 'allow' or 'block'.")
            sys.exit(1)

        print("done")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Manage Pi-hole domain blocking")
    parser.add_argument("action", choices=["allow", "block"], help="Action to perform")
    parser.add_argument("mode", help="Mode (e.g., 'afternoon', 'overnight')")

    args = parser.parse_args()

    # Validate mode argument
    if not args.mode:
        print("Error: Missing mode argument")
        sys.exit(1)

    # Create and run the downtime manager
    downtime = PiHoleDowntime()
    downtime.run(args.action, args.mode)


if __name__ == "__main__":
    main()
