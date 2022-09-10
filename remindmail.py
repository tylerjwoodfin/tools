# in order to use remindmail directly, this wrapper function is used.

import sys
from remind import remind
from securedata import securedata

if len(sys.argv) > 1:
    if sys.argv[1] == 'generate':
        securedata.log("Calling remind generate")
        remind.generate()
    elif sys.argv[1] == 'later':
        securedata.log("Calling remind later")
        remind.generateRemindersForLater()
