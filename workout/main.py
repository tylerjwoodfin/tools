"""
Sends a workout description based on a workout markdown file; scheduled in crontab

Format:

## DAYW
### Type

- instruction 1
- instruction 2

## DAYW + 1
...
"""

import sys
import time
import datetime
from cabinet import Cabinet, Mail

cab = Cabinet()
mail = Mail()

TODAY = datetime.date.today()
DAY_EPOCH = int(int(time.time())/60/60/24)
WORKOUT_FILE = cab.get_file_as_array(
    "workout.md", "notes") or ""
WORKOUT_FILE_FORMATTED = '<br>'.join(WORKOUT_FILE)
WORKOUT_TODAY = list(filter(None, WORKOUT_FILE_FORMATTED.split(
    "<br>## ")[(TODAY.weekday())+2].split("<br>")))

WORKOUT_MSG = '<br>'.join(WORKOUT_TODAY[2:])
WORKOUT_TYPE = WORKOUT_TODAY[1].replace("### ", "")

cab.log("Checking workout")

if TODAY.weekday() == 5:
    # ignore no-obligation Saturdays
    cab.log("Saturday - no workout to be sent")
    sys.exit(0)

message = f"Hi Tyler,<br><br>Here's your {WORKOUT_TYPE} workout for today:<br><br>{WORKOUT_MSG}"

mail.send(f"{WORKOUT_TYPE} for {TODAY}", message)
