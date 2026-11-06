#!/usr/bin/env bash
# Probar una rama de Cotejo en la máquina Windows de verdad, desde Linux.
#
#   herramientas/probar_windows.sh [opciones]
#
# Copia lo commiteado de la rama (git archive) a %TEMP%\cotejo-prueba\<rama>\codigo en el
# Windows (por ssh; PowerShell es su shell), sin tocar la instalación de la persona, y:
#
#   1. corre la suite (`python -m unittest discover -v -s pruebas`) con el Python del runtime
#      instalado (%LOCALAPPDATA%\Programs\Cotejo\runtime: trae GTK 4 y libadwaita) y el entorno
#      del lanzador, en la sesión de escritorio (en la de ssh las pruebas del board no pueden
#      crear su ventana y el proceso muere); sus ventanas salen y se van en esa pantalla;
#   2. corre el humo del board (`herramientas/humo_windows.py`) en la sesión de escritorio, con
#      una tarea programada interactiva (lo mismo que `schtasks /it`): abre el board de la rama,
#      lanza un agente falso, cuenta conhost.exe y ventanas de terminal, mide si la ventana deja
#      de responder, la cierra y lista lo que queda vivo. Deja humo.json.
#
# Lo que vuelve (suite.log, humo.json, board.log, volcados/) queda en --salida y el JSON se
# imprime entero al final, con una línea de resumen. Al terminar se borra la carpeta del
# Windows (salvo --conservar) y no queda ningún proceso del humo: lo que el humo no cierre, lo
# cierra este script por su línea de comandos.
#
# Opciones:
#   --host H            el ssh de la máquina Windows (win)
#   --rama REF          qué copiar (HEAD); con --sucio, también lo no commiteado de lo seguido
#   --solo suite|humo   solo una de las dos partes
#   --patron P          -p de unittest para la suite (p. ej. test_escala.py)
#   --espera S          segundos que el agente falso se queda trabajando (8)
#   --volcar-ms N       el board vuelca sus hilos (faulthandler) si su bucle pasa N ms sin latir
#   --faulthandler-s S  además, faulthandler.dump_traceback_later(S, repeat=True)
#   --perfil            perfilar (cProfile) los refrescos del board: volcados/perfil.txt
#   --maestro           el humo le escribe al maestro desde la barra (un turno con el falso,
#                       que corre cmd /c y git) en vez de mover la carta
#   --cerrar-trabajando parar|dejar
#                       cerrar el board con el agente aún trabajando (detrás de un cmd /c, como
#                       uno de npm) y contestar eso a «pararlos o dejarlos»; usa --espera 60
#   --compilar          compilar la copia (compileall) antes: como una instalación que ya
#                       arrancó una vez y tiene su __pycache__; sin esto, el primer import de
#                       cada módulo se compila en el momento y cuenta en lo que se mide
#   --tope-suite S      segundos máximos de la suite (1800)
#   --salida DIR        dónde dejar lo que vuelve (/tmp/probar-windows/<rama>)
#   --conservar         no borrar la copia en el Windows
#   --en-seco           decir qué haría, sin conectarse
#
# Sale con 0 si todo lo pedido corrió y la suite pasó; 1 si la suite falló; 2 si la suite no
# terminó, el humo no pudo medir o algo de la conexión falló. Que el humo dé terminales > 0 o bloqueos no es un
# fallo del script: es lo que mide.
set -euo pipefail

HOST=win
REF=HEAD
SUCIO=0
SOLO=todo
PATRON=""
ESPERA=8
VOLCAR_MS=0
FH_S=0
PERFIL=0
CERRAR=""
MAESTRO=""
COMPILAR=0
TOPE_SUITE=1800
SALIDA=""
CONSERVAR=0
EN_SECO=0

uso() { sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
    case "$1" in
        --host) HOST=$2; shift ;;
        --rama) REF=$2; shift ;;
        --sucio) SUCIO=1 ;;
        --solo) SOLO=$2; shift ;;
        --patron) PATRON=$2; shift ;;
        --espera) ESPERA=$2; shift ;;
        --volcar-ms) VOLCAR_MS=$2; shift ;;
        --faulthandler-s) FH_S=$2; shift ;;
        --perfil) PERFIL=1 ;;
        --cerrar-trabajando) CERRAR=$2; shift ;;
        --maestro) MAESTRO=" --maestro" ;;
        --compilar) COMPILAR=1 ;;
        --tope-suite) TOPE_SUITE=$2; shift ;;
        --salida) SALIDA=$2; shift ;;
        --conservar) CONSERVAR=1 ;;
        --en-seco) EN_SECO=1 ;;
        -h|--help) uso; exit 0 ;;
        *) echo "opción desconocida: $1 (mira --help)" >&2; exit 2 ;;
    esac
    shift
done
case "$SOLO" in todo|suite|humo) ;; *) echo "--solo es suite o humo" >&2; exit 2 ;; esac
case "$CERRAR" in ""|parar|dejar) ;; *) echo "--cerrar-trabajando es parar o dejar" >&2; exit 2 ;; esac
for numero in "$ESPERA" "$VOLCAR_MS" "$FH_S" "$TOPE_SUITE"; do
    [[ "$numero" =~ ^[0-9]+([.][0-9]+)?$ ]] || { echo "no es un número: $numero" >&2; exit 2; }
done
[[ "$PATRON" =~ ^[A-Za-z0-9_.*?-]*$ ]] || { echo "--patron solo lleva letras, _ . * ? -" >&2; exit 2; }

REPO=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
if [ "$REF" = HEAD ]; then
    RAMA=$(git -C "$REPO" rev-parse --abbrev-ref HEAD)
else
    RAMA=$REF
fi
NOMBRE=$(printf '%s' "$RAMA" | tr -c 'A-Za-z0-9._-' '-')
SALIDA=${SALIDA:-/tmp/probar-windows/$NOMBRE}
TAREA_PROGRAMADA="CotejoPruebaHumo-$NOMBRE"

# Lo que se dice al Windows: rutas armadas allí, con su %TEMP% y su %LOCALAPPDATA%.
CABECERA='$ProgressPreference = "SilentlyContinue"
$ErrorActionPreference = "Stop"
$base = Join-Path $env:TEMP "cotejo-prueba\'"$NOMBRE"'"
$codigo = Join-Path $base "codigo"
$inst = Join-Path $env:LOCALAPPDATA "Programs\Cotejo"
$py = Join-Path $inst "runtime\bin\python.exe"
$pyw = Join-Path $inst "runtime\bin\pythonw.exe"
'

# Un script de PowerShell, entero, por ssh: va codificado para no pelear con las comillas.
remoto() {
    local codificado
    codificado=$(printf '%s%s' "$CABECERA" "$1" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)
    ssh -o LogLevel=ERROR -o BatchMode=yes "$HOST" \
        "powershell -NoProfile -NonInteractive -OutputFormat Text -EncodedCommand $codificado; exit \$LASTEXITCODE"
}

if [ "$EN_SECO" = 1 ]; then
    echo "rama: $RAMA ($REF$( [ "$SUCIO" = 1 ] && echo ', con lo no commiteado'))"
    echo "host: $HOST · carpeta: %TEMP%\\cotejo-prueba\\$NOMBRE · salida: $SALIDA"
    [ "$SOLO" != humo ] && echo "suite: tarea interactiva $TAREA_PROGRAMADA: runtime\\bin\\python.exe -m unittest discover -v -s pruebas${PATRON:+ -p $PATRON} (tope ${TOPE_SUITE}s)"
    [ "$SOLO" != suite ] && echo "humo: tarea interactiva $TAREA_PROGRAMADA: pythonw humo_windows.py vigilar --espera $ESPERA --volcar-ms $VOLCAR_MS --faulthandler-s $FH_S --perfil $PERFIL${CERRAR:+ --cerrar-trabajando $CERRAR}$MAESTRO"
    exit 0
fi

mkdir -p "$SALIDA"
TAR=$(mktemp --suffix=.tar)
trap 'rm -f "$TAR"' EXIT

ARBOL=$REF
if [ "$SUCIO" = 1 ]; then
    ARBOL=$(git -C "$REPO" stash create)
    ARBOL=${ARBOL:-$REF}
fi
git -C "$REPO" archive --format=tar -o "$TAR" "$ARBOL"

echo "→ copiando $RAMA a $HOST"
TEMP_WIN=$(remoto 'Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $codigo | Out-Null
if (-not (Test-Path $py)) { Write-Output "FALTA $py"; exit 9 }
Write-Output $base' | tr -d '\r')
case "$TEMP_WIN" in *FALTA*) echo "$TEMP_WIN: ¿está Cotejo instalado en $HOST?" >&2; exit 2 ;; esac
BASE_SCP=$(printf '%s' "$TEMP_WIN" | tr '\\' '/')
scp -q -o LogLevel=ERROR -o BatchMode=yes "$TAR" "$HOST:$BASE_SCP/rama.tar"
remoto 'tar -xf (Join-Path $base "rama.tar") -C $codigo; Remove-Item (Join-Path $base "rama.tar")'
if [ "$COMPILAR" = 1 ]; then
    echo "→ compilando la copia (compileall)"
    remoto '& $py -m compileall -q $codigo | Out-Null'
fi

traer() {   # traer <ruta relativa a la base> <destino>: lo que falte no es un error
    scp -q -r -o LogLevel=ERROR -o BatchMode=yes "$HOST:$BASE_SCP/$1" "$2" 2>/dev/null || true
}

limpiar_windows() {
    remoto 'try { Unregister-ScheduledTask -TaskName "'"$TAREA_PROGRAMADA"'" -Confirm:$false -ErrorAction SilentlyContinue } catch {}
$quedan = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($base) -and $_.ProcessId -ne $PID })
foreach ($p in $quedan) { Write-Output ("cerrando lo que quedó: " + $p.Name + " " + $p.ProcessId); Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
if ("'"$CONSERVAR"'" -ne "1") { Start-Sleep 1; Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue }' || true
}
trap 'rm -f "$TAR"; limpiar_windows' EXIT

# Corre `pythonw humo_windows.py <modo> ...` en la sesión de escritorio con una tarea programada
# interactiva (LogonType Interactive: lo mismo que `schtasks /it`) y espera a que deje <archivo>.
#   en_escritorio <modo> '<resto de argumentos, en PowerShell>' <archivo bajo la base> <tope s>
en_escritorio() {
    remoto 'if (-not (Get-Process explorer -ErrorAction SilentlyContinue)) { Write-Output "nadie tiene sesión de escritorio abierta"; exit 9 }
$listo = Join-Path $base "'"$3"'"
$argumentos = "`"" + (Join-Path $codigo "herramientas\humo_windows.py") + "`" '"$1"' --instalacion `"" + $inst + "`" --codigo `"" + $codigo + "`" " + '"$2"'
$accion = New-ScheduledTaskAction -Execute $pyw -Argument $argumentos -WorkingDirectory $base
$quien = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
$ajustes = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Seconds '"$4"') -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "'"$TAREA_PROGRAMADA"'" -Action $accion -Principal $quien -Settings $ajustes -Force | Out-Null
Start-ScheduledTask -TaskName "'"$TAREA_PROGRAMADA"'"
$limite = (Get-Date).AddSeconds('"$4"' + 15)
while (-not (Test-Path $listo) -and (Get-Date) -lt $limite) { Start-Sleep -Milliseconds 500 }
Stop-ScheduledTask -TaskName "'"$TAREA_PROGRAMADA"'" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "'"$TAREA_PROGRAMADA"'" -Confirm:$false
if (-not (Test-Path $listo)) { Write-Output "no apareció '"$3"' a tiempo"; exit 9 }'
}

CODIGO_SUITE=0
if [ "$SOLO" != humo ]; then
    echo "→ suite en el escritorio de $HOST (runtime de Cotejo${PATRON:+, -p $PATRON}; salen y se van ventanas del board)"
    set +e
    en_escritorio suite '"--salida `"" + $base + "`" --tope '"$TOPE_SUITE"''"${PATRON:+ --patron $PATRON}"'"' suite.json "$TOPE_SUITE"
    CODIGO_REMOTO=$?
    set -e
    traer suite.log "$SALIDA/suite.log"
    traer suite.json "$SALIDA/suite.json"
    echo "   (suite.log completo en $SALIDA/suite.log)"
    python3 "$REPO/herramientas/humo_windows.py" resumen-suite "$SALIDA/suite.log" \
        "$SALIDA/suite.json" 2>&1 | sed 's/^/   /' || true
    if [ "$CODIGO_REMOTO" != 0 ] || [ ! -s "$SALIDA/suite.json" ]; then
        CODIGO_SUITE=2
        echo "   la suite no terminó (código $CODIGO_REMOTO)"
    else
        CODIGO_SUITE=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['codigo'])" "$SALIDA/suite.json")
        echo "   suite: código $CODIGO_SUITE ($(cat "$SALIDA/suite.json"))"
    fi
fi

CODIGO_HUMO=0
if [ "$SOLO" != suite ]; then
    TOPE_HUMO=$(python3 -c "print(int(float('$ESPERA')) + 240)")
    echo "→ humo del board en el escritorio de $HOST (hasta ${TOPE_HUMO}s)"
    set +e
    en_escritorio vigilar '"--carpeta `"" + (Join-Path $base "humo") + "`" --salida `"" + (Join-Path $base "humo.json") + "`" --espera '"$ESPERA"' --volcar-ms '"$VOLCAR_MS"' --faulthandler-s '"$FH_S"' --perfil '"$PERFIL"''"${CERRAR:+ --cerrar-trabajando $CERRAR}$MAESTRO"'"' humo.json "$TOPE_HUMO"
    CODIGO_HUMO=$?
    set -e
    rm -rf "$SALIDA/volcados"
    traer humo.json "$SALIDA/humo.json"
    traer humo/board.log "$SALIDA/board.log"
    traer humo/volcados "$SALIDA/volcados"
    traer humo/estado/lanzados "$SALIDA/lanzados"
    if [ -s "$SALIDA/humo.json" ]; then
        cat "$SALIDA/humo.json"
        echo
        set +e
        python3 "$REPO/herramientas/humo_windows.py" resumen "$SALIDA/humo.json"
        [ $? -eq 0 ] || CODIGO_HUMO=2
        set -e
    else
        CODIGO_HUMO=2
        echo "   el humo no devolvió humo.json (mira $SALIDA/board.log)" >&2
    fi
    [ "$CODIGO_HUMO" = 0 ] || CODIGO_HUMO=2
fi

if [ "$CODIGO_HUMO" != 0 ]; then exit 2; fi
if [ "$CODIGO_SUITE" = 2 ]; then exit 2; fi
if [ "$CODIGO_SUITE" != 0 ]; then exit 1; fi
exit 0
