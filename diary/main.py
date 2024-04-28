"""
diary

in my terminal, `diary` is aliased to this script so I can easily create, edit,
and save a new diary entry (stored in my cloud provider as a markdown file)
"""
import os
import sys
import datetime
from cabinet import Cabinet

cab = Cabinet()

PATH_DIARY = cab.get("path", "diary") or ""
FILENAME = f"{PATH_DIARY}/{datetime.datetime.now().strftime('%Y-%m-%d_%H.%M.%S')}.md"

if not os.path.exists(PATH_DIARY):
    cab.log(f"'{PATH_DIARY}' does not exist. Set cabinet -> path -> diary.", level="error")
    sys.exit(0)

cab.edit_file(f"{FILENAME}")
