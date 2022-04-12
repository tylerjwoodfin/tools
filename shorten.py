import random
import string
import securedata
from os import system
from sys import argv, exit

"""
Used by tyler.cloud to provide a faster URL shortener

If this is stored in a web server, one could add this to their .bashrc for rapid URL shortening:
alias shorten="ssh -oHostKeyAlgorithms=+ssh-dss -p {portNumber} {username}@{server} 'python3 {path}/tools/shorten.py"
"""


def getUrl():
    return ''.join(random.choices(string.ascii_lowercase +
                                  string.ascii_uppercase + string.digits, k=5))


if len(argv) < 2:
    print("Error- missing url; usage: `shorten url`")
    exit(-1)
with open('~/www/.htaccess', 'a') as f:
    directory = getUrl()
    f.write(
        f"\n\nRewriteCond %{{REQUEST_URI}} ^/u/{directory}.*\nRewriteRule (.*) {argv[1]}")
    print(f"https://tyler.cloud/u/{directory}")
    exit(1)
