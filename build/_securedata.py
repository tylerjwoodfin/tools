from datetime import datetime
from securedata import securedata
import os
import sys
import os.path

DEFAULT_CONFIG_FILE = f'{securedata.getItem("path_securedata")}/setup.cfg' or f'{os.path.expanduser("~")}/securedata/setup.cfg'

def main():
    # bump version
    try:
      if os.path.isfile( DEFAULT_CONFIG_FILE ):
        with open(DEFAULT_CONFIG_FILE, 'r') as f:
            _f = f.read()
            originalVersionNumber = _f.split("version = ")[1].split("\n")[0]
            originalDate = '.'.join(originalVersionNumber.split(".")[:-1])
            newDate = datetime.now().strftime("%Y.%m.%d")

            newBuildNumber = 1 if originalDate != newDate else int(originalVersionNumber.split(".")[-1]) + 1
            newVersionNumber = f"""{datetime.now().strftime("%Y.%m.%d")}.{newBuildNumber}"""
            _f = _f.replace(originalVersionNumber,newVersionNumber)
        with open(DEFAULT_CONFIG_FILE, 'w') as f:
            f.write(_f)
            print(f"Bumped version to {newVersionNumber}")
      else:
        sys.exit(f"Cannot build; {DEFAULT_CONFIG_FILE} does not exist")
    except Exception as e:
        print(e)
        sys.exit("Could not parse setup.cfg to determine incremented version number")

    # delete `dist` directory
    try:
        os.system("rm -rf /home/pi/Git/securedata/dist")
    except Exception as e:
        print(f"Warning: {e}")

    # build
    print("Building... this will take a few minutes")
    os.system("cd /home/pi/Git/securedata; python3 -m build")

    # push to PyPi
    os.system("cd /home/pi/Git/securedata; python3 -m twine upload dist/*")

    print("Finished! Remember to commit any new changes.")

if __name__ == "__main__":
    main()

