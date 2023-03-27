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
        remindmail mail -s <subject> -b <body> -t <to_addr, comma-separated>
    """
    cab = Cabinet()
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['generate', 'later', 'mail'])
    parser.add_argument('-s', help='the subject of the email')
    parser.add_argument('-b', help='the body of the email')
    parser.add_argument('-t',
                        help='the comma-separated list of email addresses to send the email to')

    args = parser.parse_args()

    if args.command == 'generate':
        cab.log("Calling remind generate")
        remind.generate()
    elif args.command == 'later':
        cab.log("Calling remind later")
        remind.mail_reminders_for_later()
    elif args.command == 'mail':
        mail.send(subject=args.s, body=args.b,
                  to_addr=args.t.split(","))
    else:
        print(f"Invalid command: {args.command}", file=sys.stderr)


if __name__ == "__main__":
    remindmail()
