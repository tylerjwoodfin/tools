# ReadMe
# Returns files from my SecureData folder

import os

fileDir = "/home/pi/Tools/SecureData/"

def variable(item):
    f = open(fileDir + item, "r")
    return f.read()

def array(item):
    f = open(fileDir + item, "r")
    return f.read().rstrip().split('\n')

def write(item, content):
    f = open(fileDir + item, "r")
    f.write(content)
    f.close
