# ReadMe
# Returns files from my SecureData folder (and other folders as needed)
# Dependencies: rclone

from pathlib import Path
import os, datetime

secureDir = "/home/pi/Git/SecureData/"

# don't modify notesDir here- modify by changing {secureDir}/NotesDir
notesDir = "/home/pi/Dropbox/Notes"
directory = __file__

# prepares files for other functions
def __initialize(item, path, action="a+"):
    if(path == "notes"):
        path = notesDir
    if not os.path.exists(path):
        os.makedirs(path)
    if not os.path.exists(path + item):
        f = open(path + item, 'w')
        f.write('')
        f.close()

    if(path == notesDir):
        # pull from Dropbox
        os.system("rclone copyto Dropbox:Notes/{} {}".format(item, path + item))
    return open(path + item, action)

# reads the first line of a file
def variable(item, path=secureDir):
    f = __initialize(item, path)
    f.seek(0,0)
    try:
        return f.read().rstrip().splitlines()[0]
    except:
        return ''

# override default notes directory
notesDir = variable("NotesDir") if len(variable("NotesDir")) > 0 else notesDir
if(notesDir[-1] != "/"):
    notesDir += "/"

# returns the file as an array
def array(item, path=secureDir):
    f = __initialize(item, path)
    f.seek(0,0)
    return f.read().rstrip().splitlines()

# returns the file as a string without splitting
def file(item, path=secureDir):
    f = __initialize(item, path)
    f.seek(0,0)
    return f.read().rstrip()

# writes a file, replacing the contents entirely
def write(item, content, path=secureDir):
    f = __initialize(item, path, "w")
    f.write(content)
    f.close()

    # Push to Dropbox
    if(path == notesDir or path == "notes"):
        path = notesDir
        os.system("rclone copyto {} Dropbox:Notes/{}".format(path + item, item))

# appends a file where duplicate lines in 'content' will be removed
def appendUnique(item, content, path=secureDir):
    content = file(item, path) + '\n' + content
    if(content[0] == '\n'):
        content = content[1:]
    lines = content.splitlines()
    lines = list(dict.fromkeys(lines))
    content = '\n'.join(lines)
    print(content)
    write(item, content, path)

# appends to a daily Log file, sent and reset at the end of each day
def log(content):
    appendUnique("dailyLog", f"{datetime.datetime.now().strftime('%H:%M:%S')}: {content}")