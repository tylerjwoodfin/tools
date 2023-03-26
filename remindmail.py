"""
A wrapper script to call remindmail.
"""

import argparse
import sys
from remind import remind
from cabinet import Cabinet, mail

def remindmail():
    """
    A wrapper function for using the 'remind' module directly from the command line.

    Usage:
        remindmail generate
        remindmail later
        remindmail mail <subject> <body> <to_addr, comma-separated>
    """
    cab = Cabinet()
    parser = argparse.ArgumentParser(prog='remindmail')

    args = parser.parse_args()

    if args.command == 'generate':
        cab.log("Calling remind generate")
        remind.generate()
    elif args.command == 'later':
        cab.log("Calling remind later")
        remind.mail_reminders_for_later()
    elif args.command == 'mail':
        mail.send(subject=args.subject, body=args.body, to_addr=args.to_addr.split(","))
    else:
        print(f"Invalid command: {args.command}", file=sys.stderr)
