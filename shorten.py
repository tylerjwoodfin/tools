"""
Used by tyler.cloud to provide a faster URL shortener

If this is stored in a web server, one could store this in cabinet -> shorten_ssh:
"ssh -oHostKeyAlgorithms=+ssh-dss -p {portNumber} {username}@{server} "
"""

import sys
import random
import string
from os import system
from cabinet import cabinet


def get_url():
    """
    generates a random string of 5 characters
    """
    return ''.join(random.choices(string.ascii_lowercase +
                                  string.ascii_uppercase + string.digits, k=5))


if len(sys.argv) < 2:
    print("Error- missing url; usage: `shorten url`")
    sys.exit(-1)

if not sys.argv[1].startswith('http'):
    print("Error- make sure to provide the complete URL.")
    sys.exit(-1)

DIRECTORY = get_url()
system((f"""{cabinet.get('shorten_ssh')} "echo '\nRewriteCond"""
        f""" %{{REQUEST_URI}} ^/u/{DIRECTORY}.*\nRewriteRule (.*)"""
        f""" {sys.argv[1]}' >> www/.htaccess" """))
print(f"https://tyler.cloud/u/{DIRECTORY}")
