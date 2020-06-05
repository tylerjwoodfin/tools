# ReadMe
# Returns files from my SecureData folder

import os

def variable(varname):
	f = open("SecureData/" + varname, "r")
	return f.read()

def array(varname):
	f = open("SecureData/" + varname, "r")
	return f.read().split('\n')