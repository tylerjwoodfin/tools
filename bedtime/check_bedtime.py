"""
Check Bedtime

If my bedtime is later than allowed through cab -> bedtime -> limit, then send an email to myself.
If my bedtime is earlier than the limit, 
    receive a refund of 50% of the penalty for the same time difference.
"""

import csv
import sys
import datetime
from cabinet import Cabinet, Mail

MAIL = Mail()
CAB = Cabinet()

# Set the path to the log file
LOG_FILE = "/home/tyler/syncthing/log/log_bedtime.csv"


def calculate_time_difference(actual_bedtime, limit_bedtime):
    """
    Calculate whether the actual bedtime is later than the bedtime limit and the time difference.

    This function takes into account the possibility of crossing midnight.
    If the actual bedtime is past midnight and the bedtime limit is before midnight (or vice versa),
    it correctly calculates the time difference.

    :param actual_bedtime: Actual time of going to bed.
    :param limit_bedtime: Bedtime limit set by the user.
    :return: Tuple (is_bedtime_late, time_difference)
             is_bedtime_late: A boolean indicating if the actual bedtime is later than the limit.
             time_difference: The time difference in minutes.
    """

    # Convert to datetime objects on the same day for comparison
    datetime_bedtime = datetime.datetime.combine(datetime.date.today(), actual_bedtime)
    datetime_limit = datetime.datetime.combine(datetime.date.today(), limit_bedtime)

    # Adjust for crossing midnight
    if actual_bedtime.hour >= 20 and limit_bedtime.hour <= 4:
        datetime_limit += datetime.timedelta(days=1)
        is_bedtime_late = False
    elif actual_bedtime.hour <= 4 and limit_bedtime.hour >= 20:
        datetime_bedtime += datetime.timedelta(days=1)
        is_bedtime_late = True
    else:
        is_bedtime_late = actual_bedtime > limit_bedtime

    # Calculate time difference in minutes
    # Using total_seconds() for accurate difference calculation, then converting to minutes
    time_difference = abs((datetime_bedtime - datetime_limit).total_seconds() / 60)

    return is_bedtime_late, time_difference


with open(LOG_FILE, "r", encoding="utf-8") as csvfile:
    reader = csv.reader(csvfile)

    # read bedtime
    BEDTIME = None
    for row in reversed(list(reader)):
        if row[0] == "bedtime":
            BEDTIME = datetime.datetime.strptime(row[2], "%H:%M").time()
            CAB.log(f"Found bedtime in CSV: {BEDTIME}")
            break

    bedtime_limit_obj = CAB.get("bedtime", "limit", return_type=dict)

    CAB.log(f"Bedtime Info: {bedtime_limit_obj}")

    if not bedtime_limit_obj:
        CAB.log("Bedtime data not found", level="error")
        sys.exit()

    bedtime_limit = bedtime_limit_obj["max_bedtime"]
    max_penalty = bedtime_limit_obj["max_penalty"]
    charity_balance = bedtime_limit_obj["charity_balance"]

    if bedtime_limit:
        bedtime_limit = datetime.datetime.strptime(bedtime_limit, "%H:%M").time()

        if BEDTIME:
            bedtime_time_difference = calculate_time_difference(BEDTIME, bedtime_limit)
            CAB.log(
                f"Bedtime Time Difference (is_late, diff): {bedtime_time_difference}"
            )

            if bedtime_time_difference[0]:
                # late
                penalty_amount = min(int(bedtime_time_difference[1]), max_penalty)
                charity_balance += penalty_amount
                msg = (
                    f"Your bedtime last night was {BEDTIME.strftime('%H:%M')}. "
                    f"Please get to bed at a reasonable time. Your balance is {charity_balance}"
                )
                MAIL.send(f"Late Bedtime: ${penalty_amount} to Charity", msg)
            else:
                # early or on time
                CAB.log("Early Bedtime")

                # 50% refund, limit to 50% of max penalty
                refund_amount = min(
                    int(bedtime_time_difference[1] / 2), (max_penalty / 2)
                )
                charity_balance -= refund_amount
                MAIL_SUBJ = f"Early Bedtime: ${refund_amount} Refund"

                if charity_balance < 0:
                    MAIL_SUBJ = "Early Bedtime: 50% Off Pushups for Today"

                MAIL.send(
                    MAIL_SUBJ,
                    f"Thank you for going to bed early at {BEDTIME.strftime('%H:%M')}! \
                                Your balance is ${charity_balance}.",
                )

            CAB.log(
                f"Processed bedtime last night: {BEDTIME} vs. limit of {bedtime_limit}",
                level="info",
            )
            CAB.put("bedtime", "limit", "charity_balance", max(charity_balance, 0))
        else:
            CAB.log(
                f"No BEDTIME found. Bedtime Info: {bedtime_limit_obj}", level="error"
            )
