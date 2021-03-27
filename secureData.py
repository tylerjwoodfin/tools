# ReadMe
# Returns files from my SecureData folder

fileDir = "/home/pi/Git/SecureData/"

def variable(item):
    # print("Opening " + fileDir + item)
    f = open(fileDir + item, "a+")
    f.seek(0,0)
    return f.read().rstrip().split('\n')[0]

def array(item):
    f = open(fileDir + item, "a+")
    f.seek(0,0)
    return f.read().rstrip().split('\n')

def write(item, content):
    f = open(fileDir + item, "w")
    f.write(content)
    f.close
