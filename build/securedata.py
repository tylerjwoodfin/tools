from datetime import datetime
import os
import sys
import os.path

# README
# Builds my SecureData package; see https://pypi.org/project/securedata
# see https://betterscientificsoftware.github.io/python-for-hpc/tutorials/python-pypi-packaging/ for specific instructions

DEFAULT_CONFIG_FILE="~/securedata/setup.cfg"

def main():
    # bump version
    try:
      if os.path.isfile( DEFAULT_CONFIG_FILE ):
        # if default config file exists then read one.
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
        #sys.exit("[%s] does not exist!" % DEFAULT_CONFIG_FILE)
        print("[%s] does not exist!" % DEFAULT_CONFIG_FILE)
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

if __name__ == "__main__":
    main()

