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
from securedata import securedata, mail

TODAY = datetime.date.today()
DAY_EPOCH = int(int(time.time())/60/60/24)
WORKOUT_FILE = '<br>'.join(securedata.getFileAsArray(
    "workout.md", "notes")).split("## ")[(TODAY.weekday()) + 1].split("<br>")

WORKOUT_MSG = '<br>'.join(WORKOUT_FILE[1:])
WORKOUT_TYPE = WORKOUT_FILE[0]

securedata.log("Checking workout")

if TODAY.weekday() == 5:
    # ignore no-obligation Saturdays
    securedata.log("Saturday - no workout to be sent")
    sys.exit(0)

message = f"Hi Tyler,\n\nHere's your {WORKOUT_TYPE} workout for today: {WORKOUT_MSG}"

mail.send(f"{WORKOUT_TYPE} for {TODAY}", message)
