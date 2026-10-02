#!/bin/sh
# Instala (o actualiza) Cotejo en Linux desde su última versión en GitHub Releases:
#
#   curl -fsSL https://rafael088.github.io/cotejo/install.sh | sh
#   curl -fsSL https://rafael088.github.io/cotejo/install.sh | sh -s -- --sin-board
#
# Baja el cotejo-<versión>-linux.tar.gz de la release y su SHA256SUMS, comprueba la suma (si no
# coincide, no instala nada) y corre el install.sh que trae dentro: para tu usuario y sin sudo,
# con `cotejo` en ~/.local/bin, la entrada del menú y el aviso a tus agentes. Volver a correrlo
# actualiza a la última versión; la configuración se conserva.
#
# Si no están las dependencias del board (python-gobject, gtk4, libadwaita), instala solo la
# CLI y te dice qué instalar para tener el board. Las opciones que no son de aquí pasan tal cual
# al install.sh del paquete (--sin-agentes, --sin-widget...).
#
#   COTEJO_VERSION=1.0.0       instala esa versión en vez de la última
#   COTEJO_DESCARGAS=<url>     de dónde bajar (por defecto, las releases de Rafael088/cotejo)
#
# Todo va dentro de main(), que se llama en la última línea: si la descarga de este script se
# corta a medias, `sh` no llega a ejecutar nada.
set -eu

REPO=https://github.com/Rafael088/cotejo

di() { printf 'Cotejo: %s\n' "$*"; }
falla() { printf 'Cotejo: %s\n' "$*" >&2; exit 1; }

bajar() {  # bajar <url> <archivo>
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 2 -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else
    falla "hace falta curl o wget para descargar"
  fi
}

ultima_version() {
  # La redirección de /releases/latest dice la etiqueta sin pasar por la API (que limita las
  # peticiones sin token).
  if command -v curl >/dev/null 2>&1; then
    destino=$(curl -fsSLI -o /dev/null -w '%{url_effective}' "$REPO/releases/latest")
  else
    destino=$(wget -q -S --spider --max-redirect=5 "$REPO/releases/latest" 2>&1 \
              | sed -n 's/^ *[Ll]ocation: *//p' | tail -1 | tr -d '\r')
  fi
  case $destino in
    */tag/v*) printf '%s\n' "${destino##*/tag/v}" ;;
    *) falla "no encontré la última versión en $REPO/releases (¿sin conexión?)" ;;
  esac
}

suma_de() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    falla "hace falta sha256sum (coreutils) para comprobar la descarga"
  fi
}

instalada() {  # la que dejó este instalador (la de usuario), si hay
  [ -x "$HOME/.local/bin/cotejo" ] || return 0
  "$HOME/.local/bin/cotejo" --version 2>/dev/null | sed -n 's/^cotejo //p' | head -1
}

hay_board() {
  python3 -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')" \
    >/dev/null 2>&1
}

paquetes_del_board() {
  if command -v pacman >/dev/null 2>&1; then echo "sudo pacman -S python-gobject gtk4 libadwaita"
  elif command -v apt-get >/dev/null 2>&1; then echo "sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"
  elif command -v dnf >/dev/null 2>&1; then echo "sudo dnf install python3-gobject gtk4 libadwaita"
  elif command -v zypper >/dev/null 2>&1; then echo "sudo zypper install python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1"
  else echo "instala python-gobject, gtk4 y libadwaita con el gestor de paquetes de tu sistema"
  fi
}

main() {
  [ "$(uname -s)" = Linux ] || falla "este instalador es para Linux. En Windows: irm https://rafael088.github.io/cotejo/install.ps1 | iex"
  maquina=$(uname -m)
  case $maquina in
    x86_64|amd64|aarch64|arm64|armv7l|riscv64|ppc64le|i686) ;;
    *) di "arquitectura $maquina: Cotejo es Python y debería funcionar, pero no está probado ahí." ;;
  esac
  command -v python3 >/dev/null 2>&1 || falla "falta python3: instálalo y vuelve a correr esto"
  command -v tar >/dev/null 2>&1 || falla "falta tar"

  version=${COTEJO_VERSION:-$(ultima_version)}
  case $version in *[!A-Za-z0-9._+-]*|'') falla "versión no válida: $version" ;; esac
  descargas=${COTEJO_DESCARGAS:-$REPO/releases/download/v$version}
  antes=$(instalada || true)
  if [ -n "$antes" ] && [ "$antes" = "$version" ]; then
    di "ya tienes la $version; la reinstalo por si le falta algo."
  elif [ -n "$antes" ]; then
    di "actualizando de la $antes a la $version ($maquina)."
  else
    di "instalando la $version ($maquina)."
  fi

  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT INT TERM
  paquete=cotejo-$version-linux.tar.gz
  bajar "$descargas/$paquete" "$tmp/$paquete" || falla "no pude bajar $descargas/$paquete"
  bajar "$descargas/SHA256SUMS" "$tmp/SHA256SUMS" || falla "no pude bajar $descargas/SHA256SUMS"
  esperada=$(awk -v f="$paquete" '$2 == f || $2 == "*" f { print $1 }' "$tmp/SHA256SUMS")
  [ -n "$esperada" ] || falla "SHA256SUMS no trae la suma de $paquete: no instalo nada"
  [ "$(suma_de "$tmp/$paquete")" = "$esperada" ] || \
    falla "la suma SHA-256 de $paquete no coincide con SHA256SUMS: no instalo nada"
  di "descarga comprobada (SHA-256 $esperada)."

  tar -xzf "$tmp/$paquete" -C "$tmp"
  [ -f "$tmp/cotejo-$version/install.sh" ] || falla "el paquete no trae install.sh"

  sin_board=0
  for opcion in "$@"; do [ "$opcion" = --sin-board ] && sin_board=1; done
  if [ "$sin_board" = 0 ] && ! hay_board; then
    di "no encuentro las dependencias del board: instalo solo la CLI."
    di "para el board: $(paquetes_del_board), y vuelve a correr este comando."
    set -- "$@" --sin-board
  fi
  sh "$tmp/cotejo-$version/install.sh" "$@"

  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) di "~/.local/bin no está en tu PATH: añádelo (export PATH=\"\$HOME/.local/bin:\$PATH\" en tu ~/.profile) y abre una terminal nueva." ;;
  esac
  if [ -x /usr/bin/cotejo ] && command -v pacman >/dev/null 2>&1 && pacman -Qq cotejo >/dev/null 2>&1; then
    di "también tienes el paquete de pacman (/usr/bin/cotejo): gana el que esté antes en el PATH. Si sobra uno, quita el paquete con sudo pacman -R cotejo."
  fi
  di "listo. Para saber qué falta configurar: cotejo doctor"
}

main "$@"
