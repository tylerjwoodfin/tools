# ReadMe
# Emails my day-to-day tasks file to me to keep me in check

import os
import secureData # to return sensitive data from protected folder

filePath = secureData.variable("nextCloudRootDirectory") + "/Notes/Tasks.txt"

f = open(filePath, 'r')

os.system("echo \"" + "Hi Tyler,\n\nPlease review the following tasks:\n\n" + f.read() + "\" | mail -s \"Your Daily Task Update\" " + secureData.variable("email"))
