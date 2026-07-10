$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $projectRoot "launch_studio.bat"

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Could not find launch_studio.bat next to this script."
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "RGC AI Broadcast Studio.lnk"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcher
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = "Open RGC AI Broadcast Studio"
$shortcut.Save()

Write-Host "Created desktop shortcut:"
Write-Host $shortcutPath
Write-Host ""
Write-Host "You can now double-click RGC AI Broadcast Studio from your desktop."
