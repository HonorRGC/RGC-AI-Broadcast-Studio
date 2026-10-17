Option Explicit

Dim shell, fileSystem, projectRoot, pythonwPath, launcherPath, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

projectRoot = fileSystem.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = fileSystem.BuildPath(projectRoot, ".venv\Scripts\pythonw.exe")
launcherPath = fileSystem.BuildPath(projectRoot, "studio_launcher.py")

If Not fileSystem.FileExists(pythonwPath) Then
    MsgBox "RGC AI Broadcast Studio is not set up yet." & vbCrLf & vbCrLf & _
        "Run setup_windows.bat first.", vbExclamation, "RGC AI Broadcast Studio"
    WScript.Quit 1
End If

If Not fileSystem.FileExists(launcherPath) Then
    MsgBox "studio_launcher.py could not be found.", vbCritical, "RGC AI Broadcast Studio"
    WScript.Quit 1
End If

command = Chr(34) & pythonwPath & Chr(34) & " " & Chr(34) & launcherPath & Chr(34)
shell.CurrentDirectory = projectRoot
shell.Run command, 0, False
