# ReadMe
# Deprecated and no longer in used; used to check nearby apartments in my apartment complex
# Dependency: requests
# pip install requests

import requests, datetime, json, time, os, secureData

now = datetime.datetime.now() 	# current dae, aka now
weeks = 12 			# how many weeks out to check
available_units = []		# stores available units
email = ""			# email body

print "Checking for available apartments. This should take about 30 seconds."
for floorplan_count in range(3303586,3303599):
	print "Checking floorplan %i of 13" %(floorplan_count - 3303586 + 1)
	
	for week in range(weeks):
		date = datetime.datetime.now() + datetime.timedelta(days=(7*week))
		date = date.strftime("%Y-%m-%d")
		url = "http://leasing.realpage.com/RP.Leasing.AppService.WebHost/ApartmentList/v1?FloorplanId=%s&MoveInDate=%s&PmcId=1049405&SiteId=3671867&BpmId=OLL.Shopping.Search.Apartment&BpmSequence=2&LogSequence=17&ClientSessionID=c0ec99e0-7252-128b-affe-da8ca15bf8ab&format=json" %(floorplan_count,date)
		response = requests.get(url).content
		response = (json.loads(response))
		if len(response["Units"]) > 0:
			for i in range(len(response["Units"])):
                
				print "Found: %s " %response["Units"][i]

				if (response["Units"][i]["UnitNumber"] not in available_units) and (response["Units"][i]["UnitNumber"][0] == "5") and (response["Units"][i]["UnitNumber"] != "548"):
					email += "%s (%s square feet) is available on %s\n" %(response["Units"][i]["UnitNumber"], response["Units"][i]["Squarefeet"], response["Units"][i]["AvailableDateString"])
					available_units.append(response["Units"][i]["UnitNumber"])

					

# finish by sending an email
if (len(available_units) > 0):
	os.system("echo \"" + email + "\" | mail -s \"Azul Availability\" " + secureData.variables("email"))
else:
	os.system("echo \"" + "No 5th floor units were found today." + "\" | mail -s \"Azul Availability\" " + secureData.variables("email"))
