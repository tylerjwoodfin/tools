import tkinter as tk
from tkinter.ttk import Label, Style
import time

"""
About

Sometimes I find myself spending too much time on my desktop; I set this to run each evening at 10PM to
hopefully convince myself to go to bed at an appropriate hour.
"""


def disable_event():
    pass


class App:
    def __init__(self, master) -> None:

        # Instantiating master i.e toplevel Widget
        self.master = master
        self.text = tk.StringVar()

        # Creating first Label i.e with default font-size
        self.title = Label(
            self.master, textvariable=self.text, font=("Arial", 25))
        self.title.pack(pady=20, expand=True)

        self.timeremaining = 200

        while(self.timeremaining > 0):
            self.text.set(
                f"Please get ready for bed.\nYour bedtime is 11:30 tonight.\nThis message will remain for {self.timeremaining} more {'second' if self.timeremaining == 1 else 'seconds'}.")
            root.update()
            self.timeremaining -= 1
            time.sleep(1)


if __name__ == "__main__":
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.protocol("WM_DELETE_WINDOW", disable_event)
    root.title("Get Ready for Bed")
    root.after(200000, root.destroy)

    # initialize
    app = App(root)
    root.mainloop()
