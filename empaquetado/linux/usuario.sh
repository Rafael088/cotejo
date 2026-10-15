#!/bin/sh
# Lo que Cotejo pone en el usuario que lo va a usar, y que un paquete del sistema no puede poner
# por él porque vive en su $HOME: el protocolo en los agentes que tenga instalados, el widget de
# la barra de Omarchy y la mudanza de la config vieja (~/.config/foco).
#
# install.sh lo corre solo en una instalación de usuario. Con un paquete (/usr), cada usuario
# lo corre una vez: sh /usr/share/tareas-obsidian/linux/usuario.sh
# Nunca pide sudo ni lo necesita. Se puede repetir: deja lo mismo.
set -eu

LINUX=$(cd "$(dirname "$0")" && pwd)
DESTINO=$(dirname "$LINUX")
BIN=
WIDGET=auto
AGENTES=1
QUITAR=0

uso() {
  cat <<USO
Uso: $0 [--bin DIR] [--widget | --sin-widget] [--sin-agentes] [--quitar]

  --bin DIR      dónde están los comandos de Cotejo (por defecto, junto a esta instalación)
  --widget       instala el widget de la barra aunque Omarchy aún no esté configurado
  --sin-widget   no toca la barra de Omarchy
  --sin-agentes  no escribe el protocolo en Claude Code, Codex, Gemini CLI ni opencode
  --quitar       quita lo que puso este script (la config se conserva)
USO
}

while [ $# -gt 0 ]; do
  case $1 in
    --bin) BIN=${2:?--bin necesita una carpeta}; shift ;;
    --widget) WIDGET=si ;;
    --sin-widget) WIDGET=no ;;
    --sin-agentes) AGENTES=0 ;;
    --quitar) QUITAR=1 ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; uso >&2; exit 2 ;;
  esac
  shift
done

[ -d "$DESTINO/tareas" ] || {
  echo "Este script se corre desde una instalación de Cotejo, no desde el repositorio." >&2
  exit 1
}
# <destino> es <prefijo>/share/tareas-obsidian, y los comandos están en <prefijo>/bin.
[ -n "$BIN" ] || BIN=$(cd "$DESTINO/../../bin" 2>/dev/null && pwd) || BIN=

# Lo que se puso y con qué opciones, en <estado>/usuario.json: el board lo lee al arrancar para
# correr este script solo si falta o es de otra versión, con las mismas opciones; doctor, para
# decir qué falta (tareas/usuario.py).
anotar() {  # anotar <json>
  (cd "$DESTINO" && python3 -c '
import json, sys
from tareas import __version__, usuario
datos = {"version": __version__, **json.loads(sys.argv[1])}
usuario.archivo().parent.mkdir(parents=True, exist_ok=True)
usuario.archivo().write_text(json.dumps(datos) + "\n", encoding="utf-8")
' "$1") || echo "No pude anotar lo puesto en la carpeta de estado (el board lo repetirá)." >&2
}

if [ "$QUITAR" = 1 ]; then
  [ "$AGENTES" = 1 ] && (cd "$DESTINO" && python3 -m tareas.skill --desinstalar) | sed 's/^/Agentes — /'
  [ "$WIDGET" = no ] || python3 "$LINUX/widget.py" quitar
  anotar '{"quitado": true}'
  exit 0
fi

# La config se llamaba ~/.config/foco. Se mueve (no se copia: dos carpetas vivas son dos
# configs) y la ruta vieja queda como enlace, para lo que la tenga escrita.
CONFIG=$(cd "$DESTINO" && python3 -c 'from tareas import rutas; print(rutas.config_base())')
if [ -d "$CONFIG/foco" ] && [ ! -L "$CONFIG/foco" ] && [ ! -e "$CONFIG/cotejo" ]; then
  mv "$CONFIG/foco" "$CONFIG/cotejo"
  ln -s cotejo "$CONFIG/foco"
  echo "Config movida a $CONFIG/cotejo ($CONFIG/foco queda como enlace)."
fi

# Que los agentes instalados se enteren de que existe. Solo toca a los que ya están en este
# usuario, y en un archivo ajeno escribe entre marcas y con copia .bak.
[ "$AGENTES" = 1 ] && (cd "$DESTINO" && python3 -m tareas.skill) | sed 's/^/Agentes — /'

case $WIDGET in
  no) ;;
  *)
    if [ ! -x "$BIN/tareas-obsidian" ]; then
      echo "No encuentro $BIN/tareas-obsidian: el widget no se instala (usa --bin)." >&2
    elif [ "$WIDGET" = si ]; then
      python3 "$LINUX/widget.py" poner --lanzador "$BIN/tareas-obsidian" --forzar
    else
      python3 "$LINUX/widget.py" poner --lanzador "$BIN/tareas-obsidian"
    fi ;;
esac

[ "$AGENTES" = 1 ] && AGENTES_JSON=true || AGENTES_JSON=false
anotar "{\"widget\": \"$WIDGET\", \"agentes\": $AGENTES_JSON}"
