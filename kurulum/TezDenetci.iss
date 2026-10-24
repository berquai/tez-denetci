; Tez Denetçi kurulum betiği (Inno Setup 6). Doğrudan değil, paketle.py üzerinden derleyin.
#ifndef AppVer
  #define AppVer "1.3.0"
#endif
#define AppName "Tez Denetçi"

[Setup]
AppId={{D258601D-06B4-4274-BA03-061DFF3CD192}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=Berkay Çelik
AppCopyright=Copyright (C) 2026 Berkay Çelik
AppComments=Berkay Çelik tarafından akademik çalışmalara yardımcı olmak amacıyla tasarlanmıştır.
DefaultDirName={autopf}\TezDenetci
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\cikti
OutputBaseFilename=TezDenetci_{#AppVer}_Kurulum
SetupIconFile=..\tezdenetci\resources\tezdenetci.ico
UninstallDisplayIcon={app}\TezDenetci.exe
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE.txt
InfoBeforeFile=kurulum_bilgi.txt
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#AppVer}
VersionInfoCompany=Berkay Çelik
VersionInfoDescription={#AppName} kurulumu

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\TezDenetci\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\TezDenetci.exe"
Name: "{group}\Kullanım Kılavuzu"; Filename: "{app}\Kullanim_Kilavuzu.html"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\TezDenetci.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TezDenetci.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    if MsgBox('Tez Denetçi ayarları (seçili dosya yolları, pencere düzeni, tema, PDF kaymaları) da silinsin mi?' + #13#10#13#10 +
              'Programı yeniden kuracaksanız "Hayır" deyin. Tezinizin yanındaki çalışma durumu dosyası (.tezdenetci.json) ' +
              've belgeleriniz her iki durumda da silinmez.',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      RegDeleteKeyIncludingSubkeys(HKCU, 'Software\TezDenetci');
end;
