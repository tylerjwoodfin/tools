"""
Sends a workout description based on a workout markdown file; scheduled in crontab
"""

import sys
import time
import datetime
from securedata import securedata, mail

TODAY = datetime.date.today()
DAY_EPOCH = int(int(time.time())/60/60/24)
WORKOUT_FILE = '<br>'.join(securedata.getFileAsArray(
    "workout.md", "notes")).split("### ")

securedata.log("Checking workout")

if TODAY.weekday() == 5:
    # ignore no-obligation Saturdays
    securedata.log("Saturday - no workout to be sent")
    sys.exit(0)

message = f"Hi Tyler,\n\nHere's your workout for {WORKOUT_FILE[(TODAY.weekday()) + 1]}"

mail.send(f"Your Workout, {TODAY}", message)
