# ReadMe
# A function to test whether my phone is on my network (192.168.1.109)
#!/usr/bin/env python3
import subprocess
from subprocess import DEVNULL, STDOUT, check_call, os

pingCode = subprocess.Popen(["ping","-c","1","192.168.1.109"], stdout=DEVNULL, stderr=subprocess.STDOUT)
pingCode.communicate()[0]
print("Phone Connected: " + str(1-pingCode.returncode))
