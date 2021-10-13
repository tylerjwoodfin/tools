# ReadMe
This enables you to associate a "default editor" for files with no extensions. Microsoft really doesn't make this easy!

# Source
https://superuser.com/questions/13653/how-to-set-the-default-program-for-opening-files-without-an-extension-in-windows

# Steps
- Open cmd.exe as an administrator
	- assoc .="No Extension"
	- ftype "No Extension"="C:\path\to\my editor.exe" "%1"
- In Regedit: `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.`
	- Add a new key called UserChoice inside .
	- In UserChoice, create a new String value called Progid. Set its value to `No Extension`.

Changes should immediately take effect.


