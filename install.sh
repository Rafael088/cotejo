#!/bin/sh
# Instala Cotejo en Linux. Sin opciones, en el usuario actual y sin sudo: el programa en
# ~/.local/share/tareas-obsidian, los comandos en ~/.local/bin, la entrada del menú, el
# protocolo en los agentes y, si hay Omarchy, el widget de la barra.
#
# Con --prefijo (/usr, /usr/local) instala para todo el sistema, y con --destdir además lo deja
# en una carpeta de empaquetado (así lo usa empaquetado/linux/PKGBUILD). En esos dos casos no
# toca ningún $HOME: lo de cada usuario lo pone <destino>/linux/usuario.sh.
set -eu

ORIGEN=$(cd "$(dirname "$0")" && pwd)
APP_ID=io.github.cotejoapp.Cotejo
PREFIJO=
DESTDIR=
BOARD=1
WIDGET=
AGENTES=1

uso() {
  cat <<USO
Uso: $0 [--prefijo DIR] [--destdir DIR] [--sin-board] [--widget | --sin-widget] [--sin-agentes]

  --prefijo DIR  instala en DIR/bin y DIR/share (p. ej. /usr/local) en vez de en el usuario
  --destdir DIR  escribe todo bajo DIR, como si DIR fuera la raíz (para empaquetar)
  --sin-board    solo la CLI: sin CotejoBoard, sin PyGObject/GTK, sin menú ni widget
  --widget       instala el widget de Omarchy aunque la barra aún no esté configurada
  --sin-widget   no toca la barra de Omarchy
  --sin-agentes  no escribe el protocolo en los agentes del usuario
USO
}

while [ $# -gt 0 ]; do
  case $1 in
    --prefijo) PREFIJO=${2:?--prefijo necesita una carpeta}; shift ;;
    --destdir) DESTDIR=${2:?--destdir necesita una carpeta}; shift ;;
    --sin-board) BOARD=0 ;;
    --widget) WIDGET=--widget ;;
    --sin-widget) WIDGET=--sin-widget ;;
    --sin-agentes) AGENTES=0 ;;
    -h|--help) uso; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; uso >&2; exit 2 ;;
  esac
  shift
done

if [ -n "$PREFIJO" ]; then
  case $PREFIJO in /*) ;; *) echo "--prefijo tiene que ser una ruta absoluta" >&2; exit 2 ;; esac
  DATA=$PREFIJO/share
  BIN=$PREFIJO/bin
else
  [ -z "$DESTDIR" ] || { echo "--destdir va con --prefijo" >&2; exit 2; }
  DATA=${XDG_DATA_HOME:-$HOME/.local/share}
  BIN=$HOME/.local/bin
fi
DESTINO=$DATA/tareas-obsidian
# Lo que se escribe va bajo $DESTDIR; lo que queda escrito dentro de los archivos, no.
R=$DESTDIR
# Solo una instalación de usuario, en esta máquina, toca el $HOME de quien la corre.
DE_USUARIO=0
[ -n "$PREFIJO" ] || DE_USUARIO=1

if [ -z "$DESTDIR" ]; then
  command -v python3 >/dev/null || { echo "Falta python3" >&2; exit 1; }
  if [ "$BOARD" = 1 ]; then
    python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1'); import cairo" 2>/dev/null || {
      echo "Faltan dependencias del board: instala python-gobject, python-cairo, gtk4 y libadwaita" >&2
      echo "(o instala solo la CLI con --sin-board)" >&2
      exit 1
    }
  fi
fi

rm -rf "$R$DESTINO"
mkdir -p "$R$DESTINO/data" "$R$DESTINO/linux" "$R$BIN"
cp -r "$ORIGEN/tareas" "$ORIGEN/enrutador" "$ORIGEN/skills" "$ORIGEN/extras" "$R$DESTINO/"
cp -r "$ORIGEN/data/marca" "$ORIGEN/data/iconos" "$ORIGEN/data/temas" "$R$DESTINO/data/"
cp "$ORIGEN/empaquetado/linux/usuario.sh" "$ORIGEN/empaquetado/linux/widget.py" "$R$DESTINO/linux/"
chmod +x "$R$DESTINO/linux/usuario.sh"
[ "$BOARD" = 0 ] || cp -r "$ORIGEN/barra" "$R$DESTINO/"
find "$R$DESTINO" -name __pycache__ -type d -exec rm -rf {} +

# Los comandos. Son Python y ponen la instalación delante en sys.path: así no dependen de la
# carpeta desde donde se llamen (un `tareas/` en el directorio actual no la suplanta) y las
# rutas relativas de los argumentos siguen siendo del que llama.
lanzador() {
  cat > "$R$BIN/$1" <<LANZADOR
#!/usr/bin/env python3
# Cotejo instalado en $DESTINO. Lo escribe install.sh: se rehace al reinstalar.
import sys
sys.path.insert(0, "$DESTINO")
from $2 import main
sys.exit(main())
LANZADOR
  chmod +x "$R$BIN/$1"
}
# `cotejo` es el nombre público; `tareas-obsidian` se queda para lo que ya lo llama (el .desktop,
# la barra, skills viejas), y `foco` para lo que se escribió cuando el producto se llamaba así.
# Los tres son el mismo programa. Sin board, los tres son la CLI a secas.
if [ "$BOARD" = 1 ]; then
  PUERTA=tareas.__main__
  lanzador cotejoboard tareas.board
else
  PUERTA=tareas.cli
  rm -f "$R$BIN/cotejoboard"
fi
for nombre in tareas-obsidian cotejo foco; do
  lanzador "$nombre" "$PUERTA"
done

# Los adaptadores de fuentes externas, con el nombre que `fuentes info <nombre>` busca en el
# PATH (cotejo-<nombre>). No se activan solos: se registran con `cotejo fuentes agregar`.
cat > "$R$BIN/cotejo-notion" <<ADAPTADOR
#!/bin/sh
exec python3 "$DESTINO/extras/notion/cotejo_notion.py" "\$@"
ADAPTADOR
chmod +x "$R$BIN/cotejo-notion"
# Una config escrita antes del cambio de nombre dice "comando": "foco-notion".
cp "$R$BIN/cotejo-notion" "$R$BIN/foco-notion"

if [ "$BOARD" = 1 ]; then
  mkdir -p "$R$DATA/applications" "$R$DATA/icons/hicolor/scalable/apps" "$R$DATA/fonts/tareas-obsidian"
  # Tipografías (Sora, Inter, IBM Plex Mono; licencia OFL).
  cp "$ORIGEN"/data/fonts/* "$R$DATA/fonts/tareas-obsidian/"
  # Ruta absoluta en Exec: ~/.local/bin puede no estar en el PATH del lanzador.
  sed "s|^Exec=tareas-obsidian|Exec=$BIN/tareas-obsidian|" "$ORIGEN/data/$APP_ID.desktop" > "$R$DATA/applications/$APP_ID.desktop"
  cp "$ORIGEN/data/$APP_ID.svg" "$R$DATA/icons/hicolor/scalable/apps/"
fi

if [ -z "$DESTDIR" ]; then
  # El lanzador y el ícono con el id de antes, que si no aparecerían dos veces en el menú.
  rm -f "$DATA/applications/io.github.rafael088.TareasObsidian.desktop" \
        "$DATA/icons/hicolor/scalable/apps/io.github.rafael088.TareasObsidian.svg"
  if [ "$BOARD" = 1 ]; then
    fc-cache -f "$DATA/fonts/tareas-obsidian" >/dev/null 2>&1 || true
    update-desktop-database "$DATA/applications" 2>/dev/null || true
    gtk-update-icon-cache -q -t "$DATA/icons/hicolor" 2>/dev/null || true
  fi
fi

if [ "$DE_USUARIO" = 1 ]; then
  set -- --bin "$BIN"
  [ "$AGENTES" = 1 ] || set -- "$@" --sin-agentes
  # Sin board no hay nada que abrir desde la barra.
  if [ "$BOARD" = 0 ]; then set -- "$@" --sin-widget; elif [ -n "$WIDGET" ]; then set -- "$@" "$WIDGET"; fi
  sh "$DESTINO/linux/usuario.sh" "$@"
  if [ "$BOARD" = 1 ]; then
    echo "Instalado. Ábrelo con el botón de la barra, desde el menú (Cotejo) o con: cotejo --board"
  else
    echo "Instalada la CLI de Cotejo (sin board)."
  fi
  echo "Para repartir trabajo: cotejo plan --proyecto <nombre>"
  echo "Para saber si todo funciona: cotejo doctor"
else
  echo "Instalado en $R$DESTINO (comandos en $R$BIN)."
  echo "Cada usuario, para el protocolo de sus agentes y el widget de Omarchy: sh $DESTINO/linux/usuario.sh"
fi
