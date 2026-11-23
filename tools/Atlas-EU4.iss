; Build with ISCC /DPayloadDir=<unpacked Asystent-EU4> /O<output directory> Atlas-EU4.iss
#ifndef PayloadDir
  #error Pass the absolute path of the unpacked portable application in PayloadDir.
#endif

[Setup]
AppId={{0ED26FD5-8E48-4667-BE9C-9739C6411A28}
AppName=Atlas EU4
AppVersion=0.1.0
AppPublisher=Aniolowie-Gabriela
AppPublisherURL=https://github.com/Aniolowie-Gabriela/Super-Joint-Engineering-Project
DefaultDirName={localappdata}\Programs\Atlas EU4
DefaultGroupName=Atlas EU4
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
OutputBaseFilename=Atlas-EU4-Setup-x64
Compression=lzma2/fast
SolidCompression=yes

[Languages]
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Atlas EU4"; Filename: "{app}\python\python.exe"; Parameters: "-B -X utf8 ""{app}\app\portable_launcher.py"""; WorkingDir: "{app}"
Name: "{group}\Przygotuj model"; Filename: "{app}\Przygotuj-model.cmd"; WorkingDir: "{app}"
Name: "{group}\Przygotuj wyszukiwanie"; Filename: "{app}\Przygotuj-wyszukiwanie.cmd"; WorkingDir: "{app}"

[Run]
Filename: "{app}\python\python.exe"; Parameters: "-B -X utf8 ""{app}\app\portable_launcher.py"""; WorkingDir: "{app}"; Description: "Uruchom Atlas EU4"; Flags: nowait postinstall skipifsilent
