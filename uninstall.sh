#!/bin/sh
# Desinstala Cotejo. Sin opciones, la instalación de usuario; con --prefijo, la del sistema
# (la misma que se le pasó a install.sh). La configuración se conserva siempre.
set -eu
APP_ID=io.github.cotejoapp.Cotejo
PREFIJO=

while [ $# -gt 0 ]; do
  case $1 in
    --prefijo) PREFIJO=${2:?--prefijo necesita una carpeta}; shift ;;
    -h|--help) echo "Uso: $0 [--prefijo DIR]"; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -n "$PREFIJO" ]; then
  DATA=$PREFIJO/share
  BIN=$PREFIJO/bin
else
  DATA=${XDG_DATA_HOME:-$HOME/.local/share}
  BIN=$HOME/.local/bin
fi
DESTINO=$DATA/tareas-obsidian

# Antes de borrar el destino, quitarle a los agentes el protocolo que apunta aquí, y el widget
# de la barra. En una del sistema eso es de cada usuario: usuario.sh --quitar.
if [ -z "$PREFIJO" ]; then
  if [ -f "$DESTINO/linux/usuario.sh" ]; then
    sh "$DESTINO/linux/usuario.sh" --quitar || true
  else
    # Una instalación de antes de usuario.sh.
    (cd "$DESTINO" 2>/dev/null && python3 -m tareas.skill --desinstalar) || true
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/cotejo.barra" \
           "${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/rafael.foco"
  fi
fi

rm -rf "$DESTINO" "$DATA/fonts/tareas-obsidian"
for nombre in tareas-obsidian cotejo cotejoboard foco cotejo-notion foco-notion; do
  rm -f "$BIN/$nombre"
done
rm -f "$DATA/applications/$APP_ID.desktop" "$DATA/icons/hicolor/scalable/apps/$APP_ID.svg"
update-desktop-database "$DATA/applications" 2>/dev/null || true
echo "Cotejo desinstalado. La configuración en ~/.config/cotejo (o ~/.config/tareas-obsidian) se conserva."
