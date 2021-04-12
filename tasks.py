# ReadMe
# A tool for editing Tasks.txt in Dropbox; to be integrated with Raspberry Pilot

import os, sys

helpText = """\nUsage: v t <command>\n\n<command>:
	add <taskInfo>
	add <taskInfo> <line number>
	rm  <taskInfo>
	rm  <line number>
	ls
	config
	help <command>
	
Parameters:
	taskInfo: enter any task you want to complete.
	
	"""

def add(s=None):
	if(s == "help"):
		print("Add something")
	print("Adding things")
	
def rm(s=None):
	print("Removing things")
	
def ls(s=None):
	print("Listing things")
	
def config(s=None):
	print("Configuring things")
	
def help():
	func = params.get(sys.argv[2])
	if(hasattr(func, '__name__')):
		func("help")
	else:
		print(sys.argv[2] + " is not a command.\n")
		print(helpText)
	
params = {
	"add": add,
	"rm": rm,
	"ls": ls,
	"config": config,
	"help": help
}

if(len(sys.argv)) == 1:
	print(helpText)
	quit()
	
func = params.get(sys.argv[1], lambda: print("Invalid"))
func()
