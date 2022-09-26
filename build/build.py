"""
This tool is specific to the original developer and is used to publish to PyPi.
"""

import sys
import os.path
from datetime import datetime
from securedata import securedata

BUILD_OPTIONS = ['securedata', 'remindmail']

# parse args
if len(sys.argv) < 2 or sys.argv[1] not in BUILD_OPTIONS:
    print(f"Invalid argument; please run `...build.py {BUILD_OPTIONS}`")
    sys.exit(1)


PATH_SRC_SECUREDATA = securedata.getItem("path", "securedata", "src")
PATH_SRC_REMINDMAIL = securedata.getItem("path", "remindmail", "src")
DEFAULT_CONFIG_FILE_SECUREDATA = f'{PATH_SRC_SECUREDATA}/setup.cfg' or \
    f'{os.path.expanduser("~")}/securedata/setup.cfg'
DEFAULT_CONFIG_FILE_REMINDMAIL = f'{PATH_SRC_REMINDMAIL}/setup.cfg' or \
    f'{os.path.expanduser("~")}/remindmail/setup.cfg'

PATH_SRC = PATH_SRC_REMINDMAIL if sys.argv[1] == 'remindmail' else PATH_SRC_SECUREDATA
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_FILE_REMINDMAIL if sys.argv[
    1] == 'remindmail' else DEFAULT_CONFIG_FILE_SECUREDATA


def main():
    """
    Bump version of config file, then build and upload using twine
    """

    # bump version to YYYY.MM.DD.n
    try:
        if os.path.isfile(DEFAULT_CONFIG_FILE):
            with open(DEFAULT_CONFIG_FILE, 'r', encoding="utf8") as file_config:
                _file_config = file_config.read()
                original_version_number = _file_config.split(
                    "version = ")[1].split("\n")[0]
                original_date = '.'.join(
                    original_version_number.split(".")[:-1])
                new_date = datetime.now().strftime("%Y.%m.%d")

                new_build_number = 1 if original_date != new_date else int(
                    original_version_number.split(".")[-1]) + 1
                new_version_number = f"""{datetime.now().strftime("%Y.%m.%d")}.{new_build_number}"""
                _file_config = _file_config.replace(
                    original_version_number, new_version_number)
            with open(DEFAULT_CONFIG_FILE, 'w', encoding="utf8") as file_config:
                file_config.write(_file_config)
                print(f"Bumped version to {new_version_number}")
        else:
            sys.exit(f"Cannot build; {DEFAULT_CONFIG_FILE} does not exist")
    except IOError as error:
        print(error)
        sys.exit("Could not parse setup.cfg to determine incremented version number")

    # delete `dist` directory
    try:
        os.system(f"rm -rf {PATH_SRC}/dist")
    except IOError as error:
        print(f"Warning: {error}")

    # build
    print("Building... this will take a few minutes")
    os.system(f"cd {PATH_SRC}; python3 -m build")

    # push to PyPi
    os.system(f"cd {PATH_SRC}; python3 -m twine upload dist/*")

    print("\n\nFinished! Remember to commit any new changes.")


if __name__ == "__main__":
    main()
