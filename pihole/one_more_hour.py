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
    # unblock immediately
    execute_command(CMD_UNBLOCK)

    # schedule re-block in 1 hour
    reblock_time = datetime.now() + timedelta(hours=1)
    at_command = f"echo '{CMD_REBLOCK}' | at {reblock_time.strftime('%H:%M')}"
    execute_command(at_command)

    # Log Times Used
    cabinet.put("pihole", "times_unblocked", times_used + 1)
    cabinet.update_cache()

    print(f"Fine, unblocking, but you've used this {times_used} times before.")
    print("Sleep is important!")
    print("\n\nRun 'one-more-hour end' to end the unblock early.")

def end_unblock():
    """
    Immediately re-block and cancel the scheduled re-block.
    """
    # Execute the re-block command immediately
    execute_command(CMD_REBLOCK)

    print("\nThank you. Get some rest, please.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Manage Pihole unblock scheduling.")
    parser.add_argument('action', nargs='?', choices=['end'], help="Action to perform")
    args = parser.parse_args()

    if args.action == 'end':
        end_unblock()
    else:
        schedule_commands()
