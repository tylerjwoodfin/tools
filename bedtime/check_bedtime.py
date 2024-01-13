"""
Check Bedtime

If my bedtime is later than allowed through cab -> bedtime -> limit, then send an email to myself.
If my bedtime is earlier than the limit, 
    receive a refund of 50% of the penalty for the same time difference.
"""

import csv
import datetime
from cabinet import Cabinet, Mail

MAIL = Mail()
CAB = Cabinet()

# Set the path to the log file
LOG_FILE = "/home/tyler/syncthing/log/log_bedtime.csv"


def calculate_time_difference(time1, time2):
    """
    Calculate the time difference in minutes between actual bedtime and limit.
    """
    return (
        datetime.datetime.combine(datetime.date.today(), time1)
        - datetime.datetime.combine(datetime.date.today(), time2)
    ).seconds / 60


with open(LOG_FILE, "r", encoding="utf-8") as csvfile:
    reader = csv.reader(csvfile)

    # read bedtime
    BEDTIME = None
    for row in reversed(list(reader)):
        if row[0] == "bedtime":
            BEDTIME = datetime.datetime.strptime(row[2], "%H:%M").time()
            break

    bedtime_limit_obj = CAB.get("bedtime", "limit")
    bedtime_limit = bedtime_limit_obj.max_bedtime
    max_penalty = bedtime_limit_obj.max_penalty
    charity_balance = bedtime_limit_obj.charity_balance

    if bedtime_limit:
        bedtime_limit = datetime.datetime.strptime(bedtime_limit, "%H:%M").time()

        if BEDTIME:
            if bedtime_limit <= BEDTIME <= datetime.time(6, 0):
                # Late bedtime penalty
                delta_minutes = calculate_time_difference(BEDTIME, bedtime_limit)
                penalty_amount = min(int(delta_minutes), max_penalty)
                charity_balance += penalty_amount
                MAIL.send(
                    f"Late Bedtime: ${penalty_amount} to Charity",
                    f"Your bedtime last night was {BEDTIME.strftime('%H:%M')}. \
                                Please get to bed at a more reasonable time.",
                )
            elif BEDTIME < bedtime_limit:
                # Early bedtime refund
                delta_minutes = calculate_time_difference(bedtime_limit, BEDTIME)

                # 50% refund, limit to 50% of max penalty
                refund_amount = min(int(delta_minutes / 2), (max_penalty / 2))

                charity_balance -= refund_amount
                MAIL_SUBJ = f"Early Bedtime: ${refund_amount} Refund"

                if charity_balance < 0:
                    MAIL_SUBJ = "Early Bedtime: 50% Off Pushups for Today"

                MAIL.send(
                    MAIL_SUBJ,
                    f"Thank you for going to bed early at {BEDTIME.strftime('%H:%M')}. \
                                Your balance is ${charity_balance}.",
                )

            CAB.log(f"Found bedtime last night: {BEDTIME}", level="info")
            CAB.put("bedtime", "limit", "charity_balance", max(charity_balance, 0))
