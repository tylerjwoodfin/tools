"""
This tool is specific to the original developer and is used to publish to PyPi.
"""

import sys
import os
from datetime import datetime
from cabinet import Cabinet

def confirm_proceed():
    response = input("You may be in the wrong directory. Are you sure? Type 'yes' to continue: ")
    return response.strip().lower() == 'yes'

cab = Cabinet()

BUILD_OPTIONS = ['remindmail', 'cabinet']

# parse args
if len(sys.argv) < 2 or sys.argv[1] not in BUILD_OPTIONS:
    print(f"Invalid argument; please run `...build.py {BUILD_OPTIONS}`")
    sys.exit(1)

selected_option = sys.argv[1]
current_working_directory = os.getcwd()
path_remindmail = cab.get("path", "remindmail", "src") or os.path.join(os.path.expanduser('~'), 'git', 'remindmail')
path_cabinet = cab.get("path", "cabinet", "src") or os.path.join(os.path.expanduser('~'), 'git', 'cabinet')

# Confirmation check
if selected_option == 'remindmail' and 'remindmail' not in current_working_directory:
    if not confirm_proceed():
        sys.exit("Try again.")
elif selected_option == 'cabinet' and 'cabinet' not in current_working_directory:
    if not confirm_proceed():
        sys.exit("Try again.")

# Set PATH_SRC based on the selected option
if selected_option == 'remindmail':
    PATH_SRC = path_remindmail
else:
    PATH_SRC = path_cabinet

DEFAULT_CONFIG_FILE = f"{PATH_SRC}/setup.cfg"

CMD_PIPREQS = ""
if selected_option == 'remindmail':
    CMD_PIPREQS = "pipreqs --force --savepath requirements.md --mode no-pin;"

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

    os.system(f"cd {PATH_SRC}; {CMD_PIPREQS} python3 -m build")

    # push to PyPi
    os.system(f"cd {PATH_SRC}; python3 -m twine upload dist/* --verbose")

    print("\n\nFinished! Remember to commit any new changes.")


if __name__ == "__main__":
    main()
