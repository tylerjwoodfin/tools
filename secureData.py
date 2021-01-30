# ReadMe
# Returns files from my SecureData folder

import os

fileDir = os.path.dirname(os.path.realpath('__file__'))

def variable(item):
    f = open(os.path.join(fileDir, "Tools/SecureData/" + item), "r")
    return f.read()

def array(item):
    f = open(os.path.join(fileDir, "Tools/SecureData/" + item), "r")
    return f.read().rstrip().split('\n')

def write(item, content):
    f = open(os.path.join(fileDir, "Tools/SecureData/" + item), "w")
    f.write(content)
    f.close
