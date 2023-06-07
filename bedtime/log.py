"""
Logs the latest bedtime or wakeup time (triggered via PHP call to server from phone)
"""
import csv
import datetime
import os
import sys
from cabinet import Cabinet, Mail

MAIL = Mail()
CAB = Cabinet()


def remove_empty_lines(file_path):
    """
    Removes any empty lines from the file provided
    :param file_path: the full path of the file
    """
    with open(file_path, 'r', newline='', encoding='utf-8') as file:
        lines = [line for line in file if line.strip()]

    # Rewrite the file with the non-empty lines
    with open(file_path, 'w', newline='', encoding='utf-8') as file:
        file.writelines(lines)


# Set the path to the log file
LOG_FILE = '/home/tyler/syncthing/log/log_bedtime.csv'

BEDTIME_EXISTS_TODAY = False
WAKEUP_EXISTS_TODAY = False

# Check if the log file exists, and create it if it doesn't
if not os.path.isfile(LOG_FILE):
    with open(LOG_FILE, 'w', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['event', 'date', 'time'])

# Get the current date and time
now = datetime.datetime.now()
date_str = now.strftime('%Y-%m-%d')
time_str = now.strftime('%H:%M')

# If the time is between midnight and 4AM, use yesterday's date instead
if now.hour < 4:
    yesterday = now - datetime.timedelta(days=1)
    date_str = yesterday.strftime('%Y-%m-%d')

# Check if there is already a "bedtime" or "wakeup" entry for today's date

remove_empty_lines(LOG_FILE)

with open(LOG_FILE, 'r', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    rows = list(reader)

    for i, row in enumerate(rows):
        if row[0] == 'bedtime' and row[1] == date_str:
            # Update the existing "bedtime" row with the current time
            rows[i] = ['bedtime', date_str, time_str]
            BEDTIME_EXISTS_TODAY = True
        elif row[0] == 'wakeup' and row[1] == date_str:
            # Check if the "wakeup" row already exists for today's date
            WAKEUP_EXISTS_TODAY = True

if sys.argv[1] == 'bedtime':
    # Check if there is already a "bedtime" entry for today's date
    if not BEDTIME_EXISTS_TODAY:
        # Append a new "bedtime" row with the current date and time
        with open(LOG_FILE, 'a', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['bedtime', date_str, time_str])
    else:
        # Update the existing "bedtime" row with the current time
        with open(LOG_FILE, 'w', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)
elif sys.argv[1] == 'wakeup' and now.hour >= 4:
    # Check if the "wakeup" row already exists for today's date
    if not WAKEUP_EXISTS_TODAY:
        # Append a new "wakeup" row with the current date and time
        with open(LOG_FILE, 'a', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['wakeup', date_str, time_str])

        # If last night's bedtime was later than 2AM, send an email to donate $23
        with open(LOG_FILE, 'r', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            BEDTIME = None
            for row in reversed(list(reader)):
                if row[0] == 'bedtime':
                    BEDTIME = datetime.datetime.strptime(
                        row[2], '%H:%M').time()
                    break

            # 24-hour format as a string, i.e. "1:30"
            bedtime_limit = CAB.get('bedtime', 'limit')
            bedtime_limit_amount = CAB.get('bedtime', 'limit_amount') or 23

            if bedtime_limit:
                bedtime_limit = datetime.datetime.strptime(
                    bedtime_limit, '%H:%M').time()

                if BEDTIME and (bedtime_limit <= BEDTIME <= datetime.time(6, 0)):
                    MAIL.send(f"Late Bedtime: ${bedtime_limit_amount} to Charity",
                              f"Your bedtime last night was {BEDTIME.strftime('%H:%M')} \
                                        - please get to bed at a more reasonable time.")
