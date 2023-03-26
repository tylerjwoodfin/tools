"""
diary

in my terminal, `diary` is aliased to this script so I can easily create, edit,
and save a new diary entry (stored in my cloud provider as a markdown file)
"""
import os
import tempfile
import datetime
from subprocess import call
from cabinet import Cabinet

cab = Cabinet()

EDITOR = os.environ.get('EDITOR', 'vim')
PATH_DIARY = cab.get("path", "diary")
PATH_NOTES = cab.get('path', 'notes')
FILENAME = f"{PATH_DIARY}/{datetime.datetime.now().strftime('%Y %m %d %H.%M.%S')}.md"

with tempfile.NamedTemporaryFile(mode='w+', suffix=".tmp") as tf:

    tf.write('')
    tf.flush()
    call([EDITOR, tf.name])
    tf.seek(0)
    DATA = tf.read()

    if len(DATA) > 0:
        cab.write_file(
            FILENAME, "notes", DATA)
        print("Saved.")
    else:
        print("No changes made.")
