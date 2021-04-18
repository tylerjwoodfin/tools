# ReadMe
# A tool for editing Tasks.txt in Dropbox; to be integrated with Raspberry Pilot

import os
import sys
import subprocess
import json

sys.path.insert(0, '../google-reminders-cli')
from secureData import noteDir, writeUnique
from remind import tasks

helpText = """\nUsage: rp t <command>\n\n<command>:
	add <taskInfo>
	add <taskInfo> <line number>
	rm  <taskInfo>
	rm  <line number>
	ls
	pull
	config
	
	For help with a specific command: help <command>
	
Parameters:
	taskInfo: enter any task you want to complete.
	
	"""

def add(s=None):
	if(s == "help"):
		return "Add something"
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
		print(func("help"))
	else:
		print(sys.argv[2] + " is not a command.\n")
		print(helpText)

def pull(s=None):
	if(s == "help"):
		return f"Pull reminders from Google Calendar, delete them, and add them to Tasks.txt in secureData.noteDir (currently {noteDir})"
		
	print("Pulling from Google...")
	items = tasks()

	# for each reminder, write to Tasks.txt if not there already
	titlesToAdd = []
	for item in items:
		print(item)
		if(not item["done"]):
			titlesToAdd.append(item['title'])
			print(f"Moving {item['title']} to {noteDir}Tasks.txt")
		print(f"Deleting {item['title']}")
		print(subprocess.check_output(['../google-reminders-cli/remind.py', '-d', item['id']]))

	if(len(titlesToAdd) > 0):
		writeUnique("Tasks.txt", '\n'.join(titlesToAdd), "notes")
		
	
params = {
	"add": add,
	"rm": rm,
	"ls": ls,
	"config": config,
	"help": help,
	"pull": pull
}

if(len(sys.argv)) == 1:
	print(helpText)
	quit()
	
if __name__ == '__main__':
	func = params.get(sys.argv[1], lambda: print(helpText))
	func()
