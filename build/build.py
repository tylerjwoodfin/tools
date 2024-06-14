"""
this tool is specific to the original developer and is used to publish to pypi.
"""

import sys
import os
from datetime import datetime
from cabinet import Cabinet

class BuildTool:
    """
    A tool to build my most prominent projects
    """

    def __init__(self) -> None:
        self.cab = Cabinet()
        self.build_options = ['remindmail', 'cabinet', 'website']
        self.selected_option: str = ""
        self.current_working_directory: str = os.getcwd()
        self.path_remindmail: str = self.cab.get("path", "remindmail", "src") or \
            os.path.join(os.path.expanduser('~'), 'git', 'remindmail')
        self.path_cabinet: str = self.cab.get("path", "cabinet", "src") or \
            os.path.join(os.path.expanduser('~'), 'git', 'cabinet')
        self.path_src: str = ""
        self.default_config_file: str = ""
        self.cmd_pipreqs: str = ""

    def confirm_proceed(self) -> bool:
        """
        if the user is potentially in the wrong directory, have the user explicitly confirm.

        returns:
            bool: whether the user has typed 'yes'
        """
        response = input(
            "You may be in the wrong directory. Are you sure? Type 'yes' to continue: ")
        return response.strip().lower() == 'yes'

    def check_and_set_path(self) -> str:
        """
        checks if the user is in the correct directory and sets
        the path source based on the selected option.

        returns:
            str: the path source based on the selected option.
        """
        options = {
            'remindmail': self.path_remindmail,
            'cabinet': self.path_cabinet,
            'website': None
        }

        if self.selected_option in options:
            if self.selected_option in ['remindmail', 'cabinet'] \
                and self.selected_option not in self.current_working_directory:
                if not self.confirm_proceed():
                    sys.exit("Try again.")
            if self.selected_option == 'website':
                build_website = self.cab.get("cmd", "build_website") or ""
                if not build_website:
                    self.cab.log("cabinet cmd -> build_website not set.", level="error")
                    sys.exit()
                os.system(build_website)
                self.cab.log("Published - https://www.tyler.cloud")
                sys.exit()
            return options[self.selected_option]
        else:
            sys.exit("Invalid option selected.")

    def bump_version(self) -> None:
        """
        bump version of config file.
        """
        try:
            if os.path.isfile(self.default_config_file):
                with open(self.default_config_file, 'r', encoding="utf8") as file_config:
                    _file_config = file_config.read()
                    original_version_number = _file_config.split("version = ")[1].split("\n")[0]
                    original_date = '.'.join(original_version_number.split(".")[:-1])
                    new_date = datetime.now().strftime("%Y.%m.%d")

                    if original_date != new_date:
                        new_build_number = 1
                    else:
                        new_build_number = int(original_version_number.split(".")[-1]) + 1
                    new_version_number = f"{new_date}.{new_build_number}"
                    _file_config = _file_config.replace(original_version_number, new_version_number)
                with open(self.default_config_file, 'w', encoding="utf8") as file_config:
                    file_config.write(_file_config)
                    print(f"Bumped version to {new_version_number}")
            else:
                sys.exit(f"Cannot build; {self.default_config_file} does not exist")
        except IOError as error:
            print(error)
            sys.exit("Could not parse setup.cfg to determine incremented version number")

    def delete_dist_directory(self) -> None:
        """
        delete `dist` directory.
        """
        try:
            os.system(f"rm -rf {self.path_src}/dist")
        except IOError as error:
            print(f"Warning: {error}")

    def build_and_upload(self) -> None:
        """
        build and upload using twine.
        """
        print("Building... this will take a few minutes")

        os.system(f"cd {self.path_src}; {self.cmd_pipreqs} python3 -m build")

        # push to pypi
        os.system(f"cd {self.path_src}; python3 -m twine upload dist/* --verbose")

        print("\n\nFinished! Remember to commit any new changes.")

    def main(self) -> None:
        """
        main function to execute the build process.
        """
        # parse args
        if len(sys.argv) < 2 or sys.argv[1] not in self.build_options:
            print(f"Invalid argument; please run `...build.py {self.build_options}`")
            sys.exit(1)

        self.selected_option = sys.argv[1]
        self.path_src = self.check_and_set_path()
        self.default_config_file = f"{self.path_src}/setup.cfg"

        if self.selected_option == 'remindmail':
            self.cmd_pipreqs = "pipreqs --force --savepath requirements.md --mode no-pin;"

        self.bump_version()
        self.delete_dist_directory()
        self.build_and_upload()


if __name__ == "__main__":
    tool = BuildTool()
    tool.main()
