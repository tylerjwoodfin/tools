import os
import time
from securedata import securedata, mail
import datetime
from sys import exit

TODAY = datetime.date.today()
DAY_EPOCH = int(int(time.time())/60/60/24)
WORKOUT_FILE_PATH = os.path.dirname(os.path.realpath(__file__))
WORKOUT_FILE = '<br>'.join(securedata.getFileAsArray(
    "README.md", WORKOUT_FILE_PATH)).split("### ")
WORKOUT_FILE_LEN = len(WORKOUT_FILE) - 1

if TODAY.weekday() == 5:
    # ignore no-obligation Saturdays
    exit(0)

message = f"Hi Tyler,\n\nhere's your workout for {WORKOUT_FILE[(DAY_EPOCH % WORKOUT_FILE_LEN) + 1]}"

if (DAY_EPOCH % WORKOUT_FILE_LEN) % 2 == 0:
    message += f"\nIf you have a training session today, this is <b>in addition to</b> that."
else:
    message += f"\nIf you have a training session today, you can ignore this."

mail.send(f"Your Workout, {TODAY}", message)
