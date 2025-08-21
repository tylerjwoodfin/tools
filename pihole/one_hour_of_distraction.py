#!/usr/bin/env python3
"""
This script allows me one hour of unblocking my "distraction list"
in Pihole. After 1 hour, it reintroduces the block.
Uses the Python downtime.py script for blocking/unblocking operations.

New features:
- Limited to 6 uses per 24-hour period
- No effect on weekends or holidays (except non-holiday Saturdays 12AM-4AM)
- Renamed from one-more-hour to one-hour-of-distraction
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


def get_usage_data():
    """
    Get usage data from cabinet, including times used and last reset date.

    Returns:
        tuple: (times_used, last_reset_date)
    """
    times_used = cabinet.get("pihole", "distraction_times_used") or 0
    last_reset_str = cabinet.get("pihole", "distraction_last_reset")

    if last_reset_str:
        try:
            last_reset = datetime.fromisoformat(last_reset_str)
        except ValueError:
            last_reset = datetime.now() - timedelta(days=1)  # Reset if invalid date
    else:
        last_reset = datetime.now() - timedelta(days=1)  # Reset if no date

    return times_used, last_reset


def reset_usage_if_needed():
    """
    Reset usage count if 24 hours have passed since last reset.

    Returns:
        int: Current times used (after potential reset)
    """
    times_used, last_reset = get_usage_data()
    now = datetime.now()

    # If 24 hours have passed since last reset, reset the counter
    if now - last_reset >= timedelta(days=1):
        times_used = 0
        cabinet.put("pihole", "distraction_times_used", times_used)
        cabinet.put("pihole", "distraction_last_reset", now.isoformat())
        cabinet.update_cache()

    return times_used


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
            except Exception:
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
    times_used = reset_usage_if_needed()

    if times_used >= 6:
        print("You've already used your 6 distraction hours for today.")
        print("Please wait until tomorrow to use this feature again.")
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

    # Update usage count
    new_times_used = times_used + 1
    cabinet.put("pihole", "distraction_times_used", new_times_used)
    cabinet.update_cache()

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
    print(f"You've used this {new_times_used}/6 times today.")
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
