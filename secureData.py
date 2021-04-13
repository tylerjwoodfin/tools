# ReadMe
# Returns files from my SecureData folder (and other folders as needed)
# Dependencies: rclone

import os, time

secure = "/home/pi/Git/SecureData/"
noteDir = "/home/pi/Dropbox/Notes/"

# prepares files for other functions
def __initialize(item, path, action="a+"):
    if(path == "notes"):
        path = noteDir
    if not os.path.exists(path):
        os.makedirs(path)

    # pull from Dropbox
    if(path == noteDir):
        os.system("rclone copyto Dropbox:Notes/{} {}".format(item, path + item))
    return open(path + item, action)

# reads the first line of a file
def variable(item, path=secure):
    f = __initialize(item, path)
    f.seek(0,0)
    return f.read().rstrip().split('\n')[0]

# returns the file as an array
def array(item, path=secure):
    f = __initialize(item, path)
    f.seek(0,0)
    return f.read().rstrip().split('\n')

# returns the file as a string without splitting
def file(item, path=secure):
    f = __initialize(item, path)
    f.seek(0,0)
    return f.read().rstrip()

# writes a file
def write(item, content, path=secure):
    f = __initialize(item, path, "w")
    f.write(content)
    f.close()

    # Push to Dropbox
    if(path == noteDir or path == "notes"):
        path = noteDir
        os.system("rclone copyto {} Dropbox:Notes/{}".format(path + item, item))