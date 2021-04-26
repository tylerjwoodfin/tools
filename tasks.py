# ReadMe
# A tool for editing Tasks.txt in Dropbox; to be integrated with Raspberry Pilot

import os
import sys
import subprocess
import json
from datetime import datetime as date
import time

sys.path.insert(0, '/home/pi/Git/google-reminders-cli')
import secureData
from remind import tasks

helpText = f"""\nUsage: rp t <command>\n\n<command>:
	add <taskInfo>
	add <taskInfo> <line number>
	rm  <taskInfo>
	rm  <line number>
	ls
	pull
	config notes <notesDirectory>
	
	For help with a specific command: help <command>
	
Parameters:
	taskInfo: enter any task you want to complete. Enclose in quotes, e.g. rp t add 'take the trash out'
	notesDirectory: Currently {secureData.notesDir}. Setting is stored at {secureData.secureDir}/NotesDir.

Notes Directory:
	Tasks.txt and TasksGenerate.txt in {secureData.notesDir}. Change the directory by running rp t config notes <directory> or modifying {secureData.secureDir}/NotesDir.

TasksGenerate.txt:
	when generate() is run (from crontab or similar task scheduler; not intended to be run directly), matching tasks are added to Tasks.txt.
	See the provided TasksGenerate.txt file in ExampleFiles for examples.
	
	"""


today = date.today()

def __toLower(arr):
	for i in range(len(arr)):
		arr[i] = arr[i].lower()
	
	return arr

# generates tasks from the TasksGenerate.txt file in {notesDir}. Not intended to be run directly (try 'crontab -e')
def generate():
	tasksGeneratedTime = secureData.variable("tasksGenerated")
	tasksGeneratedTime = tasksGeneratedTime if tasksGeneratedTime != '' else 0
	timeSinceTasksGenerated = int(time.time()) - float(tasksGeneratedTime)
	epochDay = int(time.time()/60/60/24)
	epochWeek = int(time.time()/60/60/24/7)
	epochMonth = int(date.today().month)

	tokenSplitter = {
		"d": epochDay,
		"w": epochWeek,
		"m": epochMonth
	}

	if(timeSinceTasksGenerated < 43200):
		secureData.log("Generating tasks")
		dayOfMonthEnclosed = "[D{:02d}]".format(today.day)
		dayOfWeekEnclosed = f"[{today.strftime('%a').lower()}]"
		dateMMdashDDEnclosed = f"[{today.strftime('%m-%d')}]"
		for item in secureData.array("TasksGenerate.txt", "notes"):
			if(item.startswith(dayOfMonthEnclosed) or item.startswith(dayOfWeekEnclosed) or item.startswith(dateMMdashDDEnclosed)):
				secureData.appendUnique("Tasks.txt", item, "notes")
			elif(item.startswith("[") and ("%" in item) and ("]" in item)):
				splitType = item[1].lower() # d, w, m
				splitFactor = int(item.split("%")[1].split("]")[0])
				if(splitType == "d"):
					if(epochDay % splitFactor == 0):
						secureData.appendUnique("Tasks.txt", item, "notes")
				elif(splitType == "w"):
					if(date.today().strftime("%a") == 'Sun' and epochWeek % splitFactor == 0):
						secureData.appendUnique("Tasks.txt", item, "notes")
				elif(splitType == "m"):
					if(date.today().day == 1 and epochMonth % splitFactor == 0):
						secureData.appendUnique("Tasks.txt", item, "notes")

		secureData.write("tasksGenerated", str(time.time()))
		secureData.log("Generated tasks")
	else:
		print(f"Tasks have already been generated in the past 12 hours (most recently at {tasksGeneratedTime}).")


def add(s=None):
	if(s == "help"):
		return "Add something"
	if(len(sys.argv) < 3):
		print(rm("help"))
		return

	dayOfWeekEnclosed = f"[{today.strftime('%a').lower()}]"

	secureData.appendUnique("Tasks.txt", f"{dayOfWeekEnclosed} {sys.argv[2]}", "notes")
	print(f"Added {sys.argv[2]} to {secureData.notesDir}Tasks.txt")
	
def rm(s=None):
	if(s == "help"):
		return f"Pulls latest Tasks.txt in secureData.notesDir (currently {secureData.notesDir}), then removes the selected string or index in the file.\n\ne.g. 'rp t rm 3' removes the third line.\n\nUsage: rp t rm <string matching task title, or integer of a line to remove>"
	if(len(sys.argv) < 3):
		print(rm("help"))
		return

	# convert list and query to lowercase to avoid false negatives
	tasks = __toLower(secureData.array("Tasks.txt", "notes"))
	sys.argv[2] = sys.argv[2].lower()

	try:
		del tasks[int(sys.argv[2])-1]
		secureData.write("Tasks.txt", '\n'.join(tasks), "notes")
		print(f"Removed {sys.argv[2]}. New Tasks:\n")
		ls()
	except:
		for i, task in enumerate(tasks):
			if(sys.argv[2] == task or (task.startswith("[") and "] " in task and sys.argv[2] == task.split("] ")[1])):
				del tasks[i]
				secureData.write("Tasks.txt", '\n'.join(tasks), "notes")
				print(f"Removed {sys.argv[2]}. New Tasks:\n")
				ls()
				quit()
				
		print(f"'{sys.argv[2]}' isn't in {secureData.notesDir}Tasks.txt.\nHint: don't include brackets. Names must be an exact, case-insensitive match.")

def rename(s=None):
	if(s == "help"):
		return f"Pulls latest Tasks.txt in secureData.notesDir (currently {secureData.notesDir}), then renames the selected string or index in the file.\n\ne.g. 'rp t rename 3 'buy milk' renames the third line to 'buy milk'.\ne.g. 'rp t rename 'buy milk' 'buy water' renames all lines called 'buy milk' to 'buy water'.\n\nUsage: rp t rename <string matching task title, or integer of a line to remove> <replacement string>"
	if(len(sys.argv) < 4):
		print(rm("help"))
		return

	# convert list and query to lowercase to avoid false negatives
	tasks = __toLower(secureData.array("Tasks.txt", "notes"))
	sys.argv[2] = sys.argv[2].lower()
	dayOfWeekEnclosed = f"[{today.strftime('%a').lower()}]"

	try:
		tasks[int(sys.argv[2])-1] = f"{dayOfWeekEnclosed} {sys.argv[3]}"
		secureData.write("Tasks.txt", '\n'.join(tasks), "notes")
		print(f"Renamed {sys.argv[2]} to {sys.argv[3]}. New Tasks:\n")
		ls()
	except:
		for i, task in enumerate(tasks):
			if(sys.argv[2] == task or (task.startswith("[") and "] " in task and sys.argv[2] == task.split("] ")[1])):
				tasks[i] = f"{dayOfWeekEnclosed} {sys.argv[3]}"
				secureData.write("Tasks.txt", '\n'.join(tasks), "notes")
				print(f"Renamed {sys.argv[2]} to {sys.argv[3]}. New Tasks:\n")
				ls()
				quit()
				
		print(f"'{sys.argv[2]}' isn't in {secureData.notesDir}Tasks.txt.\nHint: don't include brackets. Names must be an exact, case-insensitive match.")

def ls(s=None):
	if(s == "help"):
		return f"Displays the latest Tasks.txt in secureData.notesDir (currently {secureData.notesDir}), formatted with line numbers\n\nUsage: rp t ls"
	
	os.system(f"rclone copyto Dropbox:Notes/Tasks.txt {secureData.notesDir}Tasks.txt; cat -n {secureData.notesDir}Tasks.txt")
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
		return f"Pull reminders from Google Calendar, delete them, and add them to Tasks.txt in secureData.notesDir (currently {secureData.notesDir})"
		
	print("Pulling from Google...")
	items = tasks()

	# for each reminder, write to Tasks.txt if not there already
	titlesToAdd = []
	for item in items:
		print(item)
		if(not item["done"]):
			titlesToAdd.append(item['title'])
			print(f"Moving {item['title']} to {secureData.notesDir}Tasks.txt")
		print(f"Deleting {item['title']}")
		print(subprocess.check_output(['/home/pi/Git/google-reminders-cli/remind.py', '-d', item['id']]))

	if(len(titlesToAdd) > 0):
		secureData.appendUnique("Tasks.txt", '\n'.join(titlesToAdd), "notes")

def config(s=None):
	if(s == "help"):
		return f"rp t config notes <dir>: Set your notes directory\ne.g. rp t config notes /home/pi/Dropbox/Notes"
	if(len(sys.argv) < 4):
		print(config("help"))
		return

	if(sys.argv[2].lower() == "notes"):
		newDir = sys.argv[3] if sys.argv[3][-1] == '/' else sys.argv[3] + '/'
		secureData.write("NotesDir", newDir)
		print(f"Tasks.txt and TasksGenerate.txt should now be stored in {newDir}.")
		
	
params = {
	"add": add,
	"rm": rm,
	"rename": rename,
	"ls": ls,
	"help": help,
	"pull": pull,
	"config": config,
	"generate": generate
}

if(len(sys.argv)) == 1:
	print(helpText)
	quit()
	
if __name__ == '__main__':
	func = params.get(sys.argv[1], lambda: print(helpText))
	func()
