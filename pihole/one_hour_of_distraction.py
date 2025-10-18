#!/usr/bin/env python3
"""
This script allows me one hour of unblocking my "distraction list"
in Pihole. After 1 hour, it reintroduces the block.
Uses the Python downtime.py script for blocking/unblocking operations.

New features:
- Limited to configurable uses per rolling 24-hour period
- No effect on weekends or holidays (except non-holiday Saturdays 12AM-4AM)
- Renamed from one-more-hour to one-hour-of-distraction
- Uses rolling 24-hour window instead of daily reset
"""

import argparse
import os
import re
import subprocess
from datetime import datetime, timedelta
from cabinet import Cabinet

# Define common variables
SCRIPT_PATH = os.path.expanduser("~/git/tools/pihole/downtime.py")
CMD_UNBLOCK = f"/usr/bin/python3 {SCRIPT_PATH} allow afternoon"
CMD_REBLOCK = f"/usr/bin/python3 {SCRIPT_PATH} block afternoon"

cabinet = Cabinet()


def get_usage_limit():
    """
    Get the usage limit from cabinet, defaulting to 6 if not set.

    Returns:
        int: The maximum number of uses allowed in a 24-hour period
    """
    return cabinet.get("pihole", "distraction_usage_limit") or 6


def get_timestamps():
    """
    Get the list of timestamps from cabinet.

    Returns:
        list: List of datetime objects representing usage timestamps
    """
    timestamps_data = cabinet.get("pihole", "timestamps") or []
    timestamps = []

    for timestamp_str in timestamps_data:
        try:
            timestamps.append(datetime.fromisoformat(timestamp_str))
        except ValueError:
            # Skip invalid timestamps
            continue

    return timestamps


def clean_old_timestamps(timestamps):
    """
    Remove timestamps older than 24 hours from the list.

    Args:
        timestamps (list): List of datetime objects

    Returns:
        list: Filtered list with only timestamps from the last 24 hours
    """
    cutoff_time = datetime.now() - timedelta(hours=24)
    return [ts for ts in timestamps if ts > cutoff_time]


def save_timestamps(timestamps):
    """
    Save timestamps to cabinet.

    Args:
        timestamps (list): List of datetime objects to save
    """
    timestamp_strings = [ts.isoformat() for ts in timestamps]
    cabinet.put("pihole", "timestamps", timestamp_strings)
    cabinet.update_cache()


def get_current_usage():
    """
    Get current usage count within the rolling 24-hour window.

    Returns:
        int: Number of times used in the last 24 hours
    """
    timestamps = get_timestamps()
    timestamps = clean_old_timestamps(timestamps)
    save_timestamps(timestamps)  # Save the cleaned list
    return len(timestamps)


def add_usage_timestamp():
    """
    Add current timestamp to the usage list.
    """
    timestamps = get_timestamps()
    timestamps = clean_old_timestamps(timestamps)
    timestamps.append(datetime.now())
    save_timestamps(timestamps)


def is_weekend_or_holiday() -> bool:
    """
    Check if current time is weekend or holiday.

    Returns:
        bool: True if weekend/holiday (with Saturday 12AM-4AM exception), False otherwise
    """
    now = datetime.now()
    weekday = now.weekday()  # Monday=0, Sunday=6

    # Check if it's weekend (Saturday=5, Sunday=6)
    is_weekend = weekday >= 5

    if not is_weekend:
        return False  # Weekday, not weekend

    # It's weekend, check for Saturday 12AM-4AM exception
    if weekday == 5:  # Saturday
        if 0 <= now.hour < 4:  # Between midnight and 4AM
            # Check if it's a holiday
            try:
                holidays = cabinet.get("holidays") or []
                date_str = now.strftime("%Y-%m-%d")
                if date_str not in holidays:
                    return False  # Non-holiday Saturday 12AM-4AM is allowed
            except Exception:  # pylint: disable=broad-exception-caught
                pass  # If error getting holidays, treat as holiday

    return True  # Weekend or holiday


def execute_command(command):
    """
    Execute a specified shell command.

    Args:
    command (str): A command string to be executed in the shell environment.
    """
    subprocess.run(command, shell=True, check=True)


def schedule_commands():
    """
    Schedule commands using the `at` command. This sets up two commands:
    one to execute immediately and another to execute one hour later.
    """
    # Check usage limits
    current_usage = get_current_usage()
    usage_limit = get_usage_limit()

    if current_usage >= usage_limit:
        print(f"You've already used your {usage_limit} distraction hours in the last 24 hours.")
        print("Please wait until some time has passed to use this feature again.")
        return

    # Check weekend/holiday restrictions
    if is_weekend_or_holiday():
        print("This feature is not available on weekends or holidays.")
        print("Exception: Non-holiday Saturdays between midnight and 4AM are allowed.")
        return

    # Unblock immediately
    execute_command(CMD_UNBLOCK)

    # Schedule re-block in 1 hour
    reblock_time = datetime.now() + timedelta(hours=1)
    at_command = f"echo '{CMD_REBLOCK}' | at {reblock_time.strftime('%H:%M')}"

    # Add current usage timestamp
    add_usage_timestamp()

    # Capture the at job ID
    result = subprocess.run(
        at_command, shell=True, check=True, capture_output=True, text=True
    )

    # Combine stdout and stderr
    job_str = result.stdout.strip() or result.stderr.strip()

    # Use regex to extract the job ID (first number in the output)
    match = re.search(r"job (\d+) ", job_str)
    if match:
        job_id = match.group(1)  # Extract just the job number
        cabinet.put("pihole", "scheduled_reblock_job", job_id)
        cabinet.update_cache()
        print(f"Scheduled re-block with job ID: {job_id}")
    else:
        print("Failed to extract job ID.")

    print(f"You have until {reblock_time.strftime('%H:%M')}.")
    print(f"You've used this {current_usage + 1}/{usage_limit} times in the last 24 hours.")
    print("\n\nRun 'one-hour-of-distraction end' to end the unblock early.")


def reblock():
    """
    Immediately re-block and cancel the scheduled re-block.
    """
    # Retrieve and cancel the pending at job if it exists
    job_id = cabinet.get("pihole", "scheduled_reblock_job")
    if job_id:
        execute_command(f"atrm {job_id}")
        cabinet.remove("pihole", "scheduled_reblock_job")
        cabinet.update_cache()

    # Execute the re-block command immediately
    execute_command(CMD_REBLOCK)

    print("\nThank you. Get some rest, please.")

    # syntax in crontab to reblock:
    # 00 13 * * 1-5 /usr/bin/python3 ~/git/tools/pihole/downtime.py allow afternoon


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manage Pihole distraction unblock scheduling."
    )
    parser.add_argument("action", nargs="?", choices=["end"], help="Action to perform")
    args = parser.parse_args()

    if args.action == "end":
        reblock()
    else:
        schedule_commands()
