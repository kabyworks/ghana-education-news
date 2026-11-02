' Start the refresh job minimized so it stays on the taskbar and does not cover the desktop.
Option Explicit
Dim shell, folder, script, command, code
Set shell = CreateObject("WScript.Shell")
folder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
script = folder & "\refresh.ps1"
command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & script & """"
' 7 = show minimized without activating the window
code = shell.Run(command, 7, True)
WScript.Quit code
