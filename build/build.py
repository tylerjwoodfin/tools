from datetime import datetime
from securedata import securedata
import sys
import os.path


"""
This tool is specific to the original developer and is used to publish to PyPi.
"""

BUILD_OPTIONS = ['securedata', 'remindmail']

# parse args
if len(sys.argv) < 2 or sys.argv[1] not in BUILD_OPTIONS:
    print(f"Invalid argument; please run `...build.py {BUILD_OPTIONS}`")


PATH_SRC_SECUREDATA = securedata.getItem("path", "securedata", "src")
PATH_SRC_REMINDMAIL = securedata.getItem("path", "remindmail", "src")
DEFAULT_CONFIG_FILE_SECUREDATA = f'{PATH_SRC_SECUREDATA}/setup.cfg' or f'{os.path.expanduser("~")}/securedata/setup.cfg'
DEFAULT_CONFIG_FILE_REMINDMAIL = f'{PATH_SRC_REMINDMAIL}/setup.cfg' or f'{os.path.expanduser("~")}/remindmail/setup.cfg'

PATH_SRC = PATH_SRC_REMINDMAIL if sys.argv[1] == 'remindmail' else PATH_SRC_SECUREDATA
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_FILE_REMINDMAIL if sys.argv[
    1] == 'remindmail' else DEFAULT_CONFIG_FILE_SECUREDATA


def main():
    # bump version
    try:
        if os.path.isfile(DEFAULT_CONFIG_FILE):
            with open(DEFAULT_CONFIG_FILE, 'r') as f:
                _f = f.read()
                originalVersionNumber = _f.split(
                    "version = ")[1].split("\n")[0]
                originalDate = '.'.join(originalVersionNumber.split(".")[:-1])
                newDate = datetime.now().strftime("%Y.%m.%d")

                newBuildNumber = 1 if originalDate != newDate else int(
                    originalVersionNumber.split(".")[-1]) + 1
                newVersionNumber = f"""{datetime.now().strftime("%Y.%m.%d")}.{newBuildNumber}"""
                _f = _f.replace(originalVersionNumber, newVersionNumber)
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
        os.system(f"rm -rf {PATH_SRC}/dist")
    except Exception as e:
        print(f"Warning: {e}")

    # build
    print("Building... this will take a few minutes")
    os.system(f"cd {PATH_SRC}; python3 -m build")

    # push to PyPi
    os.system(f"cd {PATH_SRC}; python3 -m twine upload dist/*")

    print("\n\nFinished! Remember to commit any new changes.")


if __name__ == "__main__":
    main()
