# ReadMe
# A tool for editing Tasks.txt in Dropbox; to be integrated with Raspberry Pilot

import os
import sys
import subprocess
import json

sys.path.insert(0, '../google-reminders-cli')
from secureData import notesDir, secureDir, write, writeUnique, array, directory
from remind import tasks

helpText = f"""\nUsage: rp t <command>\n\n<command>:
	add <taskInfo>
	add <taskInfo> <line number>
	rm  <taskInfo>
	rm  <line number>
	ls
	pull
	config notes <directory>
	
	For help with a specific command: help <command>
	
Parameters:
	taskInfo: enter any task you want to complete.

Notes Directory:
	Tasks.txt in {notesDir}. Change the directory by modifying {secureDir}/NotesDir.
	
	"""

def __toLower(arr):
	for i in range(len(arr)):
		arr[i] = arr[i].lower()
	
	return arr

def add(s=None):
	if(s == "help"):
		return "Add something"
	print("Adding things")
	
def rm(s=None):
	if(s == "help"):
		return f"Pulls latest Tasks.txt in secureData.notesDir (currently {notesDir}), then removes the selected string or index in the file.\n\ne.g. 'rp t rm 3' removes the third line.\n\nUsage: rp t rm <string matching task title, or integer of a line to remove>"
	if(len(sys.argv) == 2):
		print(rm("help"))
		return

	# convert list and query to lowercase to avoid false negatives
	tasks = __toLower(array("Tasks.txt", "notes"))
	sys.argv[2] = sys.argv[2].lower()

	try:
		del tasks[int(sys.argv[2])-1]
		write("Tasks.txt", '\n'.join(tasks), "notes")
		print(f"Removed {sys.argv[2]}. New Tasks:\n")
		ls()
	except:
		if(sys.argv[2] in tasks):
			tasks.remove(sys.argv[2])
			write("Tasks.txt", '\n'.join(tasks), "notes")
			print(f"Removed {sys.argv[2]}. New Tasks:\n")
			ls()
		else:
			print(f"'{sys.argv[2]}' isn't in {notesDir}Tasks.txt.")

def ls(s=None):
	if(s == "help"):
		return "Displays the latest Tasks.txt in secureData.notesDir (currently {notesDir}), as well as line numbers\n\nUsage: rp t ls"
	
	os.system(f"cat -n {notesDir}Tasks.txt")
	print("\n")
	
def help():
	if(len(sys.argv) > 2):
		func = params.get(sys.argv[2])
		if(hasattr(func, '__name__')):
			print(func("help"))
	else:
		print(helpText)

def pull(s=None):
	if(s == "help"):
		return f"Pull reminders from Google Calendar, delete them, and add them to Tasks.txt in secureData.notesDir (currently {notesDir})"
		
	print("Pulling from Google...")
	items = tasks()

	# for each reminder, write to Tasks.txt if not there already
	titlesToAdd = []
	for item in items:
		print(item)
		if(not item["done"]):
			titlesToAdd.append(item['title'])
			print(f"Moving {item['title']} to {notesDir}Tasks.txt")
		print(f"Deleting {item['title']}")
		print(subprocess.check_output(['../google-reminders-cli/remind.py', '-d', item['id']]))

	if(len(titlesToAdd) > 0):
		writeUnique("Tasks.txt", '\n'.join(titlesToAdd), "notes")

def config(s=None):
	if(s == "help"):
		return f"rp t config notes <dir>: Set your notes directory\ne.g. rp t config notes /home/pi/Dropbox/Notes"
	if(len(sys.argv) < 4):
		print(config("help"))
		return

	if(sys.argv[2].lower() == "notes"):
		newDir = sys.argv[3] if sys.argv[-1] == '/' else sys.argv[3] + '/'
		write("NotesDir", newDir)
		print(f"Tasks will now be stored in {newDir}Tasks.txt.")
		
	
params = {
	"add": add,
	"rm": rm,
	"ls": ls,
	"help": help,
	"pull": pull,
	"config": config
}

if(len(sys.argv)) == 1:
	print(helpText)
	quit()
	
if __name__ == '__main__':
	func = params.get(sys.argv[1], lambda: print(helpText))
	func()
