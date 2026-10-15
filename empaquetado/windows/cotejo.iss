; El instalador de Cotejo para Windows (Inno Setup 6).
;
; No se compila a mano: lo hace construir.py, que primero arma la carpeta que este guion
; empaqueta y le pasa dónde está y qué versión es:
;
;   iscc /DOrigen=<construido\Cotejo> /DVersion=<version> /O<construido> cotejo.iss
;
; Instala para el usuario, sin pedir administrador: en %LOCALAPPDATA%\Programs\Cotejo, con el
; PATH del usuario (HKCU\Environment) y el menú Inicio del usuario. Es lo mismo que hace
; install.sh en Linux (~/.local), y por la misma razón: Cotejo es de quien lo usa.
;
; La config y el estado (%APPDATA%\cotejo, %LOCALAPPDATA%\cotejo\estado) no se tocan al
; desinstalar, como en Linux.

#ifndef Origen
  #error Falta /DOrigen: corre construir.py en vez de compilar este archivo a mano.
#endif
#ifndef Version
  #define Version "0"
#endif

[Setup]
; El AppId identifica la instalación entre versiones: no se cambia nunca.
AppId={{EA72ABDA-35CB-4BCC-AC9F-0B2E6FD479C1}
AppName=Cotejo
AppVersion={#Version}
AppVerName=Cotejo {#Version}
AppPublisher=Cotejo
AppPublisherURL=https://github.com/Rafael088/cotejo
DefaultDirName={autopf}\Cotejo
DefaultGroupName=Cotejo
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
CloseApplications=yes
OutputBaseFilename=Cotejo-{#Version}-windows-x64-instalador
SetupIconFile={#Origen}\cotejo.ico
UninstallDisplayIcon={app}\cotejo.ico
UninstallDisplayName=Cotejo
LicenseFile={#Origen}\app\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "path"; Description: "Añadir el comando cotejo al PATH (para ti y para tus agentes)"
Name: "agentes"; Description: "Avisar a los agentes instalados (Claude Code, opencode…) de que existe Cotejo"
Name: "escritorio"; Description: "Crear un acceso en el escritorio"; Flags: unchecked

[Files]
Source: "{#Origen}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Las tipografías del board (OFL), para el usuario. Si ya las tiene, se quedan las suyas.
Source: "{#Origen}\app\data\fonts\Sora[wght].ttf"; DestDir: "{autofonts}"; FontInstall: "Sora"; Flags: onlyifdoesntexist
Source: "{#Origen}\app\data\fonts\Inter[opsz,wght].ttf"; DestDir: "{autofonts}"; FontInstall: "Inter"; Flags: onlyifdoesntexist
Source: "{#Origen}\app\data\fonts\IBMPlexMono-Regular.ttf"; DestDir: "{autofonts}"; FontInstall: "IBM Plex Mono"; Flags: onlyifdoesntexist
Source: "{#Origen}\app\data\fonts\IBMPlexMono-Medium.ttf"; DestDir: "{autofonts}"; FontInstall: "IBM Plex Mono Medium"; Flags: onlyifdoesntexist

[Icons]
; AppUserModelID: el mismo que declara el proceso (tareas/app/comun.py). Con él Windows agrupa la
; ventana bajo este acceso, con su ícono y su nombre, y no bajo pythonw.exe.
Name: "{autoprograms}\Cotejo"; Filename: "{app}\bin\cotejoboard.exe"; IconFilename: "{app}\cotejo.ico"; AppUserModelID: "io.github.cotejoapp.Cotejo"; Comment: "Las tareas de tus proyectos, y el board para seguirlas"
Name: "{autodesktop}\Cotejo"; Filename: "{app}\bin\cotejoboard.exe"; IconFilename: "{app}\cotejo.ico"; AppUserModelID: "io.github.cotejoapp.Cotejo"; Tasks: escritorio

[Run]
; Lo que pacman hace al instalar gdk-pixbuf: registrar sus cargadores. La caché lleva rutas
; absolutas, así que se hace aquí, con la carpeta ya en su sitio. Sin ella no hay SVG.
Filename: "{app}\runtime\bin\gdk-pixbuf-query-loaders.exe"; Parameters: "--update-cache"; Flags: runhidden; StatusMsg: "Registrando los cargadores de imágenes…"
Filename: "{app}\interno\cotejo-agentes.exe"; Flags: runhidden; Tasks: agentes; StatusMsg: "Avisando a los agentes…"
Filename: "{app}\bin\cotejoboard.exe"; Description: "Abrir Cotejo"; Flags: postinstall nowait skipifsilent

[UninstallRun]
; Antes de borrar la carpeta, quitarle a los agentes el protocolo que apunta aquí.
Filename: "{app}\interno\cotejo-agentes.exe"; Parameters: "--desinstalar"; Flags: runhidden; RunOnceId: "QuitarAgentes"

[UninstallDelete]
; Lo que Python escribe mientras corre (__pycache__), que el desinstalador no conoce.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"

[Code]
const
  ClaveEntorno = 'Environment';

function CarpetaBin: string;
begin
  Result := ExpandConstant('{app}\bin');
end;

{ ¿Está `Carpeta` en la lista `Lista` (separada por ;), sin mirar mayúsculas? }
function EnLaLista(Lista, Carpeta: string): Boolean;
begin
  Result := Pos(';' + Uppercase(Carpeta) + ';', ';' + Uppercase(Lista) + ';') > 0;
end;

procedure AgregarAlPath;
var
  Actual: string;
begin
  if not RegQueryStringValue(HKCU, ClaveEntorno, 'Path', Actual) then
    Actual := '';
  if EnLaLista(Actual, CarpetaBin) then
    exit;
  if (Actual <> '') and (Copy(Actual, Length(Actual), 1) <> ';') then
    Actual := Actual + ';';
  RegWriteExpandStringValue(HKCU, ClaveEntorno, 'Path', Actual + CarpetaBin);
end;

procedure QuitarDelPath;
var
  Actual: string;
  Donde: Integer;
begin
  if not RegQueryStringValue(HKCU, ClaveEntorno, 'Path', Actual) then
    exit;
  Actual := ';' + Actual + ';';
  Donde := Pos(';' + Uppercase(CarpetaBin) + ';', Uppercase(Actual));
  if Donde = 0 then
    exit;
  Delete(Actual, Donde, Length(CarpetaBin) + 1);
  RegWriteExpandStringValue(HKCU, ClaveEntorno, 'Path', Copy(Actual, 2, Length(Actual) - 2));
end;

{ Cierra la app de Cotejo que esté corriendo, venga de donde venga: la de esta carpeta, una
  instalación anterior o un ZIP viejo descomprimido en cualquier sitio. La app es de instancia
  única, así que un proceso vivo de otra carpeta se quedaba con la orden del Cotejo recién
  instalado y, con su código, no abría el board (cotejo-ksypkc). CloseApplications solo mira
  lo que está en la carpeta de instalación.

  Se reconoce por el Python del runtime (…\runtime\bin\pythonw.exe) corriendo la app: el board
  o `-m tareas` sin verbo, --board o --fondo. Las llamadas de la CLI que hacen los agentes no se
  tocan: duran un instante y cortarlas podría dejar una escritura a medias. }
procedure CerrarCotejo;
var
  Codigo: Integer;
begin
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
       '-NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -match ''\\runtime\\bin\\pythonw?\.exe$'' -and $_.CommandLine -match ''-m tareas(\.board\b|\s*$|\s+--(board|fondo|gapplication))'' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"',
       '', SW_HIDE, ewWaitUntilTerminated, Codigo);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  CerrarCotejo;
  Result := '';
end;

function InitializeUninstall: Boolean;
begin
  CerrarCotejo;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('path') then
    AgregarAlPath;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    QuitarDelPath;
end;
