import random
import string
from securedata import securedata
from os import system
from sys import argv, exit

"""
Used by tyler.cloud to provide a faster URL shortener

If this is stored in a web server, one could store this in securedata -> shorten_ssh:
"ssh -oHostKeyAlgorithms=+ssh-dss -p {portNumber} {username}@{server} "
"""


def getUrl():
    return ''.join(random.choices(string.ascii_lowercase +
                                  string.ascii_uppercase + string.digits, k=5))


if len(argv) < 2:
    print("Error- missing url; usage: `shorten url`")
    exit(-1)

if not argv[1].startswith('http'):
    print("Error- make sure to provide the complete URL.")
    exit(-1)

directory = getUrl()
system(
    f"""{securedata.getItem('shorten_ssh')} "echo '\nRewriteCond %{{REQUEST_URI}} ^/u/{directory}.*\nRewriteRule (.*) {argv[1]}' >> www/.htaccess" """)
print(f"https://tyler.cloud/u/{directory}")
