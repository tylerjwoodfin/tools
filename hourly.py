"""
a script that runs each hour on my machines to ensure system stability
"""

import subprocess
import socket
from datetime import datetime, timedelta
import tzlocal
import pytz
from cabinet import Cabinet, Mail

CAB = Cabinet()
MAIL = Mail()
HOSTNAME = socket.gethostname()


def check_timezone():
    """
    Checks the latest timezone from phone, if provided, and updates machine to match
    """

    def get_timezone_from_offset(offset_str):
        """
        Returns a timezone from a UTC offset string.
        Note: This function will pick one of the timezones that match the offset,
        which may not be the intended timezone.
        """
        try:
            # Convert offset string to timedelta
            offset_hours, offset_minutes = map(int, offset_str.split(":"))
            offset = timedelta(hours=offset_hours, minutes=offset_minutes)

            # Find a matching timezone
            for name in pytz.common_timezones:
                timezone = pytz.timezone(name)
                if datetime.now(timezone).utcoffset() == offset:
                    return timezone.zone
        except ValueError:
            # Handle invalid offset format
            print("Invalid timezone offset format.")
            return None

        # Handle case where no timezone matches the offset
        print(f"No timezone found for offset {offset_str}")
        return None

    timezone_file = CAB.get_file_as_array(
        "TIMEZONE", "/home/tyler/syncthing/cabinet/keys"
    )
    if timezone_file:
        timezone_data = timezone_file[0]

    timezone_data = timezone_file[0]
    new_timezone = get_timezone_from_offset(timezone_data)
    if new_timezone != str(tzlocal.get_localzone()):
        # update system time
        command = f"sudo timedatectl set-timezone {new_timezone}"

        try:
            old_time = subprocess.run(
                ["date"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout

            # Timezone change command
            subprocess.run(command, shell=True, check=True)

            current_time = subprocess.run(
                [f"{command} && date"],
                capture_output=True,
                text=True,
                shell=True,
                check=True,
            ).stdout.strip()

            msg = (
                f"The time on {HOSTNAME} has changed from {old_time} to {current_time}."
            )
            CAB.log(msg)
            MAIL.send(f"Updated Timezone to {new_timezone}", msg)
        except subprocess.CalledProcessError as e:
            CAB.log(f"Error executing the subprocess: {e}", level="error")
        except PermissionError as e:
            CAB.log(f"Permission denied: {e}", level="error")
        except Exception as e:
            # Catch any other unexpected exceptions
            CAB.log(f"An unexpected error occurred: {e}", level="error")
    else:
        CAB.log(f"System timezone is {new_timezone}. No change needed.")


if __name__ == "__main__":
    check_timezone()
