; Script do Inno Setup - Instalador do AutomacaoPrecos
; Como usar:
;   1. Instale o Inno Setup (https://jrsoftware.org/isinfo.php)
;   2. Coloque este arquivo na mesma pasta onde fica a pasta "dist\"
;      (ou seja, na raiz do projeto, junto do projeto_automacao.py)
;   3. Abra este arquivo com o Inno Setup Compiler e aperte F9 (Compile)
;   4. O instalador final aparece em Output\SetupAutomacaoPrecos.exe

#define MyAppName "Automacao Precos - Mercado Livre"
#define MyAppVersion "1.0"
#define MyAppExeName "AutomacaoPrecos.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
; Pasta padrao de instalacao: C:\Program Files\Automacao Precos - Mercado Livre
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Gera o instalador dentro da pasta Output
OutputDir=Output
OutputBaseFilename=SetupAutomacaoPrecos
Compression=lzma
SolidCompression=yes
; Nao precisa ser admin para instalar (instala so pro usuario atual)
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Area de Trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
; Copia o executavel gerado pelo PyInstaller
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Copia o README junto, se existir
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Oferece abrir o programa logo apos a instalacao
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName} agora"; Flags: nowait postinstall skipifsilent
