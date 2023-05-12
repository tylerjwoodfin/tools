"""
Logs the latest bedtime (triggered via PHP call to server from phone)
"""
import csv
import datetime
import os
import sys

# Set the path to the log file
LOG_FILE = '/home/tyler/syncthing/log/log_bedtime.csv'

BEDTIME_EXISTS_TODAY = False

# Check if the log file exists, and create it if it doesn't
if not os.path.isfile(LOG_FILE):
    with open(LOG_FILE, 'w', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['bedtime', 'date', 'time'])

# Get the current date and time
now = datetime.datetime.now()
date_str = now.strftime('%Y-%m-%d')
time_str = now.strftime('%H:%M')

# If the time is between midnight and 4AM, use yesterday's date instead
if now.hour < 4:
    yesterday = now - datetime.timedelta(days=1)
    date_str = yesterday.strftime('%Y-%m-%d')

# Check if there is already a "bedtime" entry for today's date
with open(LOG_FILE, 'r', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    rows = list(reader)
    for i, row in enumerate(rows):
        if row[0] == 'bedtime' and row[1] == date_str:
            # Update the existing row with the current time
            rows[i] = ['bedtime', date_str, time_str]
            BEDTIME_EXISTS_TODAY = True
            break

if not BEDTIME_EXISTS_TODAY:
    # Append a new row with the current date and time
    with open(LOG_FILE, 'a', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([sys.argv[1], date_str, time_str])

# Write all rows to file
with open(LOG_FILE, 'w', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerows(rows)
