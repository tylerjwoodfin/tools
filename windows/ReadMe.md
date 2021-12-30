# Overview
I have three displays at home: my two primary 1440p monitors, and my 1080p TV. My desktop is attached to all of them at once, and most of the time, I prefer this setup for things like watching TV and dragging windows across at home.

However, I often remotely connect to my desktop through other one-monitor desktops or my phone. In these situations, I prefer only having one monitor. 

Rather than go through the Windows display settings each time, I've made these scripts, then set the icons in this folder as their icon, then dragged them to the Windows 10 taskbar.

This means that I can switch between two displays and one display by just clicking the icons on the taskbar.

# Dependencies
- Windows
- Autohotkey

# Setup

## enableGrayscale
- Refer to https://active-directory-wp.com/docs/Usage/How_to_add_a_cron_job_on_Windows/Scheduled_tasks_and_cron_jobs_on_Windows/
    - Add a scheduled task with the Action: `"C:\Program Files\AutoHotkey\AutoHotkey.exe" <path to enableGrayscale.ahk>`

# Supplemental Info
dc2.exe (short for Display Changer II) is provided free for personal use by 12Noon. https://12noon.com/?page_id=641