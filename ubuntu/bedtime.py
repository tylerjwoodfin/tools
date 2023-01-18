"""
About:
Sometimes I find myself spending too much time on my desktop.
I set this to run each evening at 10PM to hopefully convince myself to go
to bed at an appropriate hour.

Dependencies for Crontab:
xvfb

Dependencies for Python:
tkinter (sudo apt-get install python3-tk)

Example Crontab:
0 22 * * * cd /home/tyler/git/tools/ubuntu && XAUTHORITY=/home/tyler/.Xauthority DISPLAY=:0 python3 bedtime.py
"""

#!/usr/bin/env python
import tkinter as tk
import time
import os
import sys
from tkinter.ttk import Label


def _disable_event():
    pass

class App:
    """
    contains the description of the fullscreen, blocking window and text that is displayed
    """

    def __init__(self, master, message) -> None:

        # Instantiating master i.e toplevel Widget
        self.master = master
        self.text = tk.StringVar()

        # block alt-tab
        print(os.system("GSETTINGS_BACKEND=dconf /usr/bin/gsettings set org.gnome.desktop.wm.keybindings switch-applications \"[]\""))

        # Creating first Label i.e with default font-size
        self.title = Label(
            self.master, textvariable=self.text, font=("Arial", 25))
        self.title.pack(pady=20, expand=True)

        self.timeremaining = 200

        while self.timeremaining > 0:
            self.text.set((f"{message}\nThis message will remain for "
                           f"{self.timeremaining}"
                           f" more {'second' if self.timeremaining == 1 else 'seconds'}."))
            root.update()
            self.timeremaining -= 1
            time.sleep(1)

def restore():
    """
    destroy modal and restore alt-tab
    """
    print(os.system(CMD_ALT_TAB))

if __name__ == "__main__":
    CMD_ALT_TAB = "GSETTINGS_BACKEND=dconf /usr/bin/gsettings set org.gnome.desktop.wm.keybindings" \
        " switch-applications \"['<Alt>Tab']\""

    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.protocol("WM_DELETE_WINDOW", _disable_event)
    root.title("Get Ready for Bed")
    root.after(200000, restore)
    root.after(200000, root.destroy)

    # initialize
    if len(sys.argv) > 1:
        MESSAGE = sys.argv[1]
    else:
        MESSAGE = "Please get ready for bed.\nYour bedtime is 11:30 tonight."
        "\nMelatonin is a good idea."

    app = App(root, MESSAGE)
    root.mainloop()
