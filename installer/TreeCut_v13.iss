#ifndef SourceRoot
  #define SourceRoot "G:\TreeCut_v13_release_candidate"
#endif
#ifndef OutputDir
  #define OutputDir "G:\TreeCut_build\installer"
#endif

[Setup]
AppId={{4A21D2E8-9D91-4F87-82AA-05B6DA74BEE9}
AppName=树剪 TreeCut
AppVersion=13.0.0
AppVerName=树剪 TreeCut 13.0.0 CPU 离线版
AppPublisher=TreeCut
DefaultDirName={code:GetPortableDefaultDir}
DefaultGroupName=树剪 TreeCut
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=TreeCut_v13_CPU_Setup
Compression=none
SolidCompression=no
DiskSpanning=yes
DiskSliceSize=2100000000
WizardStyle=modern
SetupLogging=yes
UninstallDisplayName=树剪 TreeCut 13.0.0 CPU 离线版
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=13.0.0.0
VersionInfoDescription=TreeCut v13 CPU Offline Installer

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "runtime_data\*,tests\*"

[Dirs]
Name: "{app}\runtime_data"
Name: "{app}\runtime_data\cache"
Name: "{app}\runtime_data\temp"
Name: "{app}\runtime_data\logs"
Name: "{app}\runtime_data\database"
Name: "{app}\runtime_data\materials"
Name: "{app}\runtime_data\output"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式（快捷方式通常位于 Windows 用户目录）"; Flags: unchecked
Name: "startmenuicons"; Description: "创建开始菜单快捷方式（快捷方式通常位于 Windows 用户目录）"; Flags: unchecked

[Icons]
Name: "{autodesktop}\树剪 TreeCut"; Filename: "{app}\启动树剪v13.cmd"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{group}\树剪 TreeCut"; Filename: "{app}\启动树剪v13.cmd"; WorkingDir: "{app}"; Tasks: startmenuicons
Name: "{group}\检查树剪安装"; Filename: "{app}\检查树剪安装.cmd"; WorkingDir: "{app}"; Tasks: startmenuicons
Name: "{group}\卸载树剪 TreeCut"; Filename: "{uninstallexe}"; Tasks: startmenuicons

[Run]
Filename: "{app}\启动树剪v13.cmd"; Description: "启动树剪 TreeCut"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent

[Code]
function GetPortableDefaultDir(Param: String): String;
var
  SourceDrive: String;
begin
  SourceDrive := ExtractFileDrive(ExpandConstant('{src}'));
  if CompareText(SourceDrive, 'C:') = 0 then
    SourceDrive := 'D:';
  Result := SourceDrive + '\TreeCut_v13';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  TargetDrive: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    TargetDrive := ExtractFileDrive(WizardDirValue);
    if CompareText(TargetDrive, 'C:') = 0 then
    begin
      MsgBox('树剪的程序、模型、缓存和运行数据均不得放在 C 盘。请选择 D、E、F、G 等其他磁盘。', mbError, MB_OK);
      Result := False;
    end;
  end;
end;
