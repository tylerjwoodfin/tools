import os
import tempfile
import datetime
from sys import argv, exit
from subprocess import call
from securedata import securedata

EDITOR = os.environ.get('EDITOR', 'vim')
PATH_DIARY = securedata.getItem("path", "diary")
PATH_NOTES_LOCAL = securedata.getItem('path', 'notes', 'local')
PATH_NOTES_CLOUD = securedata.getItem('path', 'notes', 'cloud')
FILENAME = f"{PATH_DIARY}/{datetime.datetime.now().strftime('%Y %m %d %H:%M:%S')}.md"

with tempfile.NamedTemporaryFile(mode='w+', suffix=".tmp") as tf:

    if len(argv) == 1:
        tf.write('')
        tf.flush()
        call([EDITOR, tf.name])
        tf.seek(0)
        data = tf.read()
    else:
        print("Pulling...")
        os.system(f"rclone sync {PATH_NOTES_CLOUD} {PATH_NOTES_LOCAL}")
        print("Pulled.")
        data = ' '.join(argv[1:])

    if len(data) > 0:
        print("Saving...")
        securedata.writeFile(
            FILENAME, "notes", data)
    else:
        print("No changes made.")
