; Shoot Sorter Windows installer (Inno Setup 6.5 or newer).
; Built by build_windows.ps1, which passes SourceDir, AppVersion, OutputDir and BuildInfo.
; Per-user install: no administrator rights, installs to %LOCALAPPDATA%\Programs\Shoot Sorter.
; Settings, models and history live in %APPDATA%\Shoot Sorter and are kept on uninstall
; unless the user chooses to delete them (or passes /PURGE=1 to a silent uninstall).

#ifndef SourceDir
  #error SourceDir must point at the staged build (packaging\build-win\stage)
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#ifndef BuildInfo
  #define BuildInfo ""
#endif

[Setup]
AppId={{8C1B3E52-6A4F-4F7B-9E0D-5D2B9C3A7F11}
AppName=Shoot Sorter
AppVersion={#AppVersion}
AppVerName=Shoot Sorter {#AppVersion}
AppComments=Keywords for Lightroom Classic XMP sidecars, on your own PC. Build {#BuildInfo}
AppPublisher=Shoot Sorter
AppPublisherURL=https://github.com/jaswalker24/shoot-sorter
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\Shoot Sorter
DefaultGroupName=Shoot Sorter
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename=ShootSorter-{#AppVersion}-Setup
SetupIconFile={#SourceDir}\ShootSorter.ico
UninstallDisplayIcon={app}\ShootSorter.ico
UninstallDisplayName=Shoot Sorter
LicenseFile={#SourceDir}\LICENSE
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=16
CloseApplications=no
RestartApplications=no
ChangesEnvironment=no

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startatlogin"; Description: "Start Shoot Sorter when I sign in"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\Shoot Sorter"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\runtime\tray.py"""; WorkingDir: "{app}"; IconFilename: "{app}\ShootSorter.ico"; Comment: "Shoot Sorter control panel"
Name: "{userdesktop}\Shoot Sorter"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\runtime\tray.py"""; WorkingDir: "{app}"; IconFilename: "{app}\ShootSorter.ico"; Tasks: desktopicon
Name: "{userstartup}\Shoot Sorter"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\runtime\tray.py"" --background"; WorkingDir: "{app}"; IconFilename: "{app}\ShootSorter.ico"; Tasks: startatlogin

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\runtime\tray.py"""; WorkingDir: "{app}"; Description: "Open Shoot Sorter now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{app}\python\python.exe"; Parameters: """{app}\runtime\tray.py"" --stop"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "StopShootSorter"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: files; Name: "{userstartup}\Shoot Sorter.lnk"

[Code]
procedure StopRunningCopy(AppDir: String);
var
  Rc: Integer;
begin
  if FileExists(AppDir + '\runtime\tray.py') and FileExists(AppDir + '\python\python.exe') then
    Exec(AppDir + '\python\python.exe', '"' + AppDir + '\runtime\tray.py" --stop', AppDir,
         SW_HIDE, ewWaitUntilTerminated, Rc);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  { Updating over a running copy: quit it first so its files can be replaced. }
  StopRunningCopy(ExpandConstant('{app}'));
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Purge: Boolean;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\Shoot Sorter');
    if not DirExists(DataDir) then
      Exit;
    Purge := ExpandConstant('{param:PURGE|0}') = '1';
    if (not Purge) and (not UninstallSilent) then
      Purge := MsgBox('Also delete your Shoot Sorter settings, downloaded models and history?' + #13#10#13#10 +
                      DataDir + #13#10#13#10 +
                      'Photos, Lightroom catalogues and XMP sidecars are never touched.',
                      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
    if Purge then
      DelTree(DataDir, True, True, True);
  end;
end;
