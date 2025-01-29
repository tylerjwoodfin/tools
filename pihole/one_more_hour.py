#!/usr/bin/env python3
"""
This script allows me one hour of unblocking my "distraction list"
in Pihole. After 1 hour, it reintroduces the block.
"""

import argparse
import subprocess
from datetime import datetime, timedelta
from cabinet import Cabinet

# Define common variables
SCRIPT_PATH = "/home/tyler/git/tools/pihole/downtime.sh"
CMD_UNBLOCK = f"zsh {SCRIPT_PATH} allow afternoon"
CMD_REBLOCK = f"zsh {SCRIPT_PATH} block afternoon"

cabinet = Cabinet()
times_used = cabinet.get("pihole", "times_unblocked") or 0

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
    # Unblock immediately
    execute_command(CMD_UNBLOCK)

    # Schedule re-block in 1 hour
    reblock_time = datetime.now() + timedelta(hours=1)
    at_command = f"echo '{CMD_REBLOCK}' | at {reblock_time.strftime('%H:%M')}"

    # Log Times Used
    cabinet.put("pihole", "times_unblocked", times_used + 1)


    # Capture the at job ID
    result = subprocess.run(at_command, shell=True, check=True, capture_output=True, text=True)
    job_id = result.stdout.strip().split()[-1]  # Extract job ID

    # Store the job ID
    cabinet.put("pihole", "scheduled_reblock_job", job_id)
    cabinet.update_cache()

    print(f"Fine, unblocking, but you've used this {times_used} times before.")
    print("Sleep is important!")
    print("\n\nRun 'one-more-hour end' to end the unblock early.")


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
    # 00 13 * * 1-5 zsh -c "atrm $(atq | awk '{print $1}') 2>/dev/null; \
    # zsh $HOME/git/tools/pihole/downtime.sh allow afternoon"

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Manage Pihole unblock scheduling.")
    parser.add_argument('action', nargs='?', choices=['end'], help="Action to perform")
    args = parser.parse_args()

    if args.action == 'end':
        reblock()
    else:
        schedule_commands()
