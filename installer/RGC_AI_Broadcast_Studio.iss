#define AppName "RGC AI Broadcast Studio"
#ifndef AppVersion
#define AppVersion "0.0.0"
#endif
#ifndef SourceDir
#define SourceDir "..\dist\windows_installer_source"
#endif
#ifndef OutputDir
#define OutputDir "..\dist"
#endif

[Setup]
AppId={{A35A3F15-2D5F-4C2E-A4E4-7602B58962A1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=RGC Motorsports
AppPublisherURL=https://www.realisticgamingcrew.com
AppSupportURL=https://www.realisticgamingcrew.com
DefaultDirName={localappdata}\RGC AI Broadcast Studio
DefaultGroupName=RGC AI Broadcast Studio
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=RGC-AI-Broadcast-Studio-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=RGC AI Broadcast Studio

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\RGC AI Broadcast Studio"; Filename: "{app}\launch_studio.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\RGC AI Broadcast Studio"; Filename: "{app}\launch_studio.bat"; WorkingDir: "{app}"

[Run]
Filename: "{app}\setup_windows.bat"; Description: "Install required Python packages"; Flags: postinstall waituntilterminated skipifsilent
Filename: "{app}\launch_studio.bat"; Description: "Launch RGC AI Broadcast Studio"; Flags: postinstall nowait skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.venv"
Type: filesandordirs; Name: "{app}\.runtime"
