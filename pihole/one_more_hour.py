#!/usr/bin/env python3
"""
This script allows me one hour of unblocking my "distraction list"
in Pihole. After 1 hour, it reintroduces the block.
"""

import subprocess
import time
from datetime import datetime, timedelta
from cabinet import Cabinet
from apscheduler.schedulers.background import BackgroundScheduler

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
    Schedule commands using APScheduler. This sets up two commands:
    one to execute immediately and another to execute one hour later.
    """
    # Create a scheduler in the background
    scheduler = BackgroundScheduler()

    # Schedule the first command to run immediately
    scheduler.add_job(execute_command,
                      args=["bash /home/tyler/git/tools/pihole/downtime.sh allow afternoon"],
                      trigger='date')

    # Schedule the second command to run 1 hour later
    scheduler.add_job(execute_command,
                      args=["bash -m /home/tyler/git/tools/pihole/downtime.sh block afternoon"],
                      trigger='date', run_date=datetime.now() + timedelta(hours=1))

    # Log Times Used
    cabinet.put("pihole", "times_unblocked", times_used + 1) # type: ignore
    cabinet.update_cache()

    print(f"Fine, unblocking, but you've used this {times_used} times before.")
    print("Sleep is important!")

    # Start the scheduler
    scheduler.start()

    # Keep the script running to allow jobs to execute
    try:
        while True:
            time.sleep(2)
    except (KeyboardInterrupt, SystemExit):
        # Shutdown the scheduler when exiting the app
        cabinet.log("Re-blocking")
        execute_command("bash /home/tyler/git/tools/pihole/downtime.sh block afternoon")
        scheduler.shutdown()

if __name__ == '__main__':
    schedule_commands()
