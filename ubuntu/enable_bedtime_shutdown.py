"""
enable_bedtime_shutdown

If I comment the automatic shutdown line out from my crontab, it should reappear on reboot.
This can be solved by calling this script upon reboot.

Shutdown in crontab is: 25 23 * * * root /usr/sbin/shutdown -h now
"""

import os
import fnmatch

# backup existing crontab
os.system("sudo cp /etc/crontab /etc/crontab_backup")

file_crontab_lines = []

# read crontab - done with manual close to avoid IO errors
file_crontab_read = open("/etc/crontab", "r", encoding="utf-8")
file_crontab_lines = file_crontab_read.read().splitlines()
for index, line in enumerate(file_crontab_lines):
    if fnmatch.fnmatch(line, "*/usr/sbin/shutdown*"):
        if line.startswith("#"):
            print("Uncommenting scheduled shutdown")
            file_crontab_lines[index] = line.replace("# ", "", 1)

file_crontab_read.close()

# write modified crontab
with open("/etc/crontab", "w", encoding="utf-8") as file_crontab:
    print('\n'.join(file_crontab_lines))
    file_crontab.write('\n'.join(file_crontab_lines))
