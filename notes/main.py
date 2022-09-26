"""
Notes

Edits a file in the notes folder based on argv[1]; can create file if it doesn't exist
"""

import sys
from os import listdir
from securedata import securedata

if len(sys.argv) < 2:
    print("Usage: `notes {filename in securedata notes folder}`")
    sys.exit(-1)
elif sys.argv[1].endswith('.md'):
    sys.argv[1] = sys.argv[1].split(".md", maxsplit=1)[0]

PATH_FILE_TO_EDIT = securedata.getItem("path", "notes", "local")

if securedata.editFile(f"{PATH_FILE_TO_EDIT}/{sys.argv[1]}.md", sync=True) == -1:

    print('\nAVAILABLE FILES:')
    print('\n'.join(listdir(PATH_FILE_TO_EDIT)))
    print('\n')

    if input(f"Do you want to create {sys.argv[1]}.md?\n\n").startswith("y"):
        securedata.editFile(
            f"{PATH_FILE_TO_EDIT}/{sys.argv[1]}.md", sync=True, createIfNotExist=True)
