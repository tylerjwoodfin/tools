"""
Check Bedtime

If my bedtime is later than allowed through
cabinet -> bedtime -> limit, then send an email to myself
"""

import csv
import datetime
from cabinet import Cabinet, Mail

MAIL = Mail()
CAB = Cabinet()

# Set the path to the log file
LOG_FILE = "/home/tyler/syncthing/log/log_bedtime.csv"

with open(LOG_FILE, "r", encoding="utf-8") as csvfile:
    reader = csv.reader(csvfile)

    BEDTIME = None
    for row in reversed(list(reader)):
        if row[0] == "bedtime":
            BEDTIME = datetime.datetime.strptime(row[2], "%H:%M").time()
            break

    # 24-hour format as a string, i.e. "1:30"
    bedtime_limit = CAB.get("bedtime", "limit")
    bedtime_limit_amount = CAB.get("bedtime", "limit_amount") or 23

    if bedtime_limit:
        bedtime_limit = datetime.datetime.strptime(bedtime_limit, "%H:%M").time()

        if BEDTIME and (bedtime_limit <= BEDTIME <= datetime.time(6, 0)):
            MAIL.send(
                f"Late Bedtime: ${bedtime_limit_amount} to Charity",
                f"Your bedtime last night was {BEDTIME.strftime('%H:%M')} \
                                - please get to bed at a more reasonable time.",
            )
        else:
            CAB.log(f"Found bedtime last night: {BEDTIME}", level="info")
