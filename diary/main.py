import os
import tempfile
import datetime
from sys import argv, exit
from subprocess import call
from securedata import securedata

EDITOR = os.environ.get('EDITOR', 'vim')
FILENAME = f"Archive/Diary Entries/{datetime.datetime.now().strftime('%Y %m %d %H:%M:%S')}.md"
NOTES_LOCAL = securedata.getItem('path_tasks_notes')
NOTES_CLOUD = securedata.getItem('path_cloud_notes')

with tempfile.NamedTemporaryFile(mode='w+', suffix=".tmp") as tf:

    if len(argv) == 1:
        tf.write('')
        tf.flush()
        call([EDITOR, tf.name])
        tf.seek(0)
        data = tf.read()
    else:
        print("Pulling...")
        os.system(f"rclone sync {NOTES_CLOUD} {NOTES_LOCAL}")
        print("Pulled.")
        data = ' '.join(argv[1:])

    if len(data) > 0:
        print("Saving...")
        securedata.writeFile(
            FILENAME, "notes", data)
        print(f"Saved to {securedata.getItem('path_tasks_notes')}/{FILENAME}.")
    else:
        print("No changes made.")
