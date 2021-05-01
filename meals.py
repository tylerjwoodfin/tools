import sys
import json
import datetime
import yaml

sys.path.insert(0, '/home/pi/Git/SecureData')
import secureData

# ReadMe
# Imports meal data from a JSON file and generates a shopping list and schedules meals for each day.
# Designed to be used with SecureData.
# Dependencies: pip3 install pyyaml

def generate():
	meals = json.loads(secureData.file("mealExample.json", "/home/pi/Git/Tools/ExampleFiles"))
	ingredients = []
	plannedMeals = []

	# iterate through each meal set and write to file

	key_index = -1
	for key in meals.keys():
		key_index += 1
		for i in range(7):
			day_w = (datetime.datetime(2021, 4, 29) + datetime.timedelta(days=i+1)).strftime("%A") # start the list for Friday. Change date to modify
			if(key_index == 0):
				plannedMeals.append({day_w: [{}, {}, {}]})
			mod_i = i % len(meals[key])
			if i < 7:
				plannedMeals[i][day_w][key_index] = {key: (meals[key][mod_i])}
				for ingredient in meals[key][mod_i]["ingredients"]:
					ingredients.append(ingredient)

	print("Generated.")
	ingredients = list(dict.fromkeys(ingredients))

	secureData.write("WeeklyMeals.json", json.dumps(plannedMeals), "notes")
	secureData.appendUnique("Shopping.txt", '\n'.join(ingredients), "notes")
	print(f"Meals have been saved to {secureData.notesDir}WeeklyMeals.json.")
	print(f"Ingredients from WeeklyMeals.json have been added to {secureData.notesDir}Shopping.txt.")
	secureData.log("Generated meals, shopping list, and WeeklyMeals.json")
	ls(plannedMeals)

def ls(mealsFile=json.loads(secureData.file("WeeklyMeals.json", "notes"))):	
	toWrite=""
	for day in range(7):
		toWrite += f"{list(mealsFile[day].keys())[0]}:\n"
		for mealType in range(0,3):
			meals = list(mealsFile[day].values())[0]
			toWrite += f"    {list(meals[mealType].values())[0]['name']}\n"
	
	secureData.write("MealsList.txt", toWrite, "notes")
	print(f"A simplified meal list (without the ingredients) is available at {secureData.notesDir}MealsList.txt.")
	secureData.log("Generated MealsList.txt")

if(__name__ == "__main__"):
	if(sys.argv[1] == 'ls'):
		ls()
	if(sys.argv[1] == 'generate'):
		generate()