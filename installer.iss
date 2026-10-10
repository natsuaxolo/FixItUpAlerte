; Script Inno Setup - Fix It Up Alerte
; A compiler avec Inno Setup APRES avoir lance build.bat

[Setup]
AppName=Fix It Up Alerte
AppVersion=1.3
AppPublisher=Nathan
DefaultDirName={autopf}\FixItUpAlerte
DefaultGroupName=Fix It Up Alerte
OutputDir=installer_output
OutputBaseFilename=FixItUpAlerte_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\FixItUpAlerte.exe
WizardStyle=modern

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "dist\FixItUpAlerte\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
; Son d'alarme personnalise (optionnel) : mets un fichier alarme.wav ou alarme.mp3 dans le dossier du projet
Source: "alarme.*"; DestDir: "{app}"; Flags: skipifsourcedoesntexist

[Icons]
Name: "{group}\Fix It Up Alerte"; Filename: "{app}\FixItUpAlerte.exe"
Name: "{group}\Désinstaller Fix It Up Alerte"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Fix It Up Alerte"; Filename: "{app}\FixItUpAlerte.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FixItUpAlerte.exe"; Description: "Lancer Fix It Up Alerte"; Flags: nowait postinstall skipifsilent
