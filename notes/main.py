"""
Notes

Edits a file in the notes folder based on argv[1]; can create file if it doesn't exist
"""

from sys import argv
from os import listdir
from securedata import securedata

# print(securedata.editFile(argv[1],  ))
PATH_FILE_TO_EDIT = securedata.getItem("path", "notes", "local")

if securedata.editFile(f"{PATH_FILE_TO_EDIT}/{argv[1]}.md", sync=True) == -1:

    print('\nAVAILABLE FILES:')
    print('\n'.join(listdir(PATH_FILE_TO_EDIT)))
    print('\n')

    if input(f"Do you want to create {argv[1]}.md?\n\n").startswith("y"):
        securedata.editFile(
            f"{PATH_FILE_TO_EDIT}/{argv[1]}.md", sync=True, createIfNotExist=True)
