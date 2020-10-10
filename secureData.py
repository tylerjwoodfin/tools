# ReadMe
# Returns files from my SecureData folder

import os

def variable(varname):
    f = open("/home/pi/Tools/SecureData/" + varname, "r")
    return f.read()

def array(varname):
    f = open("/home/pi/Tools/SecureData/" + varname, "r")
    return f.read().rstrip().split('\n')