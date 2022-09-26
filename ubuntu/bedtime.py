"""
About:
Sometimes I find myself spending too much time on my desktop.
I set this to run each evening at 10PM to hopefully convince myself to go
to bed at an appropriate hour.

Dependencies for Crontab:
xvfb

Example Crontab:
0 22 * * * cd /home/tyler/git/tools/ubuntu && XAUTHORITY=/home/tyler/.Xauthority
DISPLAY=:0 python3 bedtime.py
"""

#!/usr/bin/env python
import tkinter as tk
import time
from tkinter.ttk import Label


def _disable_event():
    pass


class App:
    """
    contains the description of the fullscreen, blocking window and text that is displayed
    """

    def __init__(self, master) -> None:

        # Instantiating master i.e toplevel Widget
        self.master = master
        self.text = tk.StringVar()

        # Creating first Label i.e with default font-size
        self.title = Label(
            self.master, textvariable=self.text, font=("Arial", 25))
        self.title.pack(pady=20, expand=True)

        self.timeremaining = 200

        while self.timeremaining > 0:
            self.text.set((f"Please get ready for bed.\nYour bedtime is 11:30 tonight."
                           f"\nMelatonin is a good idea.\nThis message will remain for "
                           f" {self.timeremaining}"
                           f" more {'second' if self.timeremaining == 1 else 'seconds'}."))
            root.update()
            self.timeremaining -= 1
            time.sleep(1)


if __name__ == "__main__":
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.protocol("WM_DELETE_WINDOW", _disable_event)
    root.title("Get Ready for Bed")
    root.after(200000, root.destroy)

    # initialize
    app = App(root)
    root.mainloop()
