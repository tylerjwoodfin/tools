import sys
import json
import datetime

sys.path.insert(0, '/home/pi/Git/SecureData')
import secureData

# ReadMe
# Imports meal data from a JSON file and generates a shopping list and schedules meals for each day.
# Designed to be used with SecureData.

def generate():
	meals = json.loads(secureData.file("mealExample.json", "/home/pi/Git/Tools/ExampleFiles"))
	ingredients = []
	plannedMeals = []

	# iterate through each meal set and write to file

	key_index = -1
	for key in meals.keys():
		key_index += 1
		for i in range(7):
			day_w = (datetime.datetime.today() + datetime.timedelta(days=i+1)).strftime("%A")
			if(key_index == 0):
				print(day_w)
				plannedMeals.append({day_w: [{}, {}, {}]})
			mod_i = i % len(meals[key])
			if i < 7:
				plannedMeals[i][day_w][key_index] = {key: (meals[key][mod_i])}
				# print(f"{day_w}: {meals[key][mod_i]}")
				for ingredient in meals[key][mod_i]["ingredients"]:
					ingredients.append(ingredient)

	print("\n\n\n")
	print(plannedMeals)
	ingredients = list(dict.fromkeys(ingredients))
	# print(ingredients)
	# add ingredients

	secureData.write("WeeklyMeals.json", json.dumps(plannedMeals), "notes")
	secureData.appendUnique("Shopping.txt", '\n'.join(ingredients), "notes")

if(__name__ == "__main__"):
	generate()