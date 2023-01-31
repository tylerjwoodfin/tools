"""
in order to use remindmail directly, this wrapper function is used.
"""
import sys
from remind import remind
from securedata import securedata, mail

if len(sys.argv) > 1:
    if sys.argv[1] == 'generate':
        securedata.log("Calling remind generate")
        remind.generate()
    if sys.argv[1] == 'later':
        securedata.log("Calling remind later")
        remind.generate_reminders_for_later()
    if sys.argv[1] == 'mail':
        if len(sys.argv) < 5:
            print("Usage: remind mail <subject> <body> <to_addr, comma-separated>")
        else:
            mail.send(subject=sys.argv[2], body=sys.argv[3], to_addr=sys.argv[4].split(","))
    else:
        print(f"Invalid command: {sys.argv[1]}")
