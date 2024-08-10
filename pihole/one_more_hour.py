#!/usr/bin/env python3
"""
This script allows me one hour of unblocking my "distraction list"
in Pihole. After 1 hour, it reintroduces the block.
"""

import subprocess
from datetime import datetime, timedelta
from cabinet import Cabinet

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
    path_script = "/home/tyler/git/tools/pihole/downtime.sh"
    cmd_unblock = f"zsh {path_script} allow afternoon"
    cmd_reblock = f"zsh {path_script} block afternoon"

    # unblock immediately
    execute_command(cmd_unblock)

    # schedule re-block in 1 hour
    reblock_time = datetime.now() + timedelta(hours=1)
    at_command = f"echo '{cmd_reblock}' | at {reblock_time.strftime('%H:%M')}"

    # Schedule the re-block command
    subprocess.run(at_command, shell=True, check=True)

    # Log Times Used
    cabinet.put("pihole", "times_unblocked", times_used + 1)
    cabinet.update_cache()

    print(f"Fine, unblocking, but you've used this {times_used} times before.")
    print("Sleep is important!")

if __name__ == '__main__':
    schedule_commands()
