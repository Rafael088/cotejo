#!/bin/sh
# Arma en dist/ lo que se publica para Linux:
#
#   cotejo-<versión>-linux.tar.gz   se descomprime y se instala con su ./install.sh
#   arch/cotejo-<versión>-1-any.pkg.tar.zst   con --arch, el paquete de pacman (Arch, Omarchy)
#
# Sale de HEAD con `git archive`, no del árbol de trabajo: lo que no está en un commit no se
# publica, tampoco el trabajo a medias de otro. La versión es `tareas.__version__` tal como está
# en HEAD (la misma que dicen `cotejo --version` y construir.py de Windows) salvo que se dé
# COTEJO_VERSION; DIST cambia la carpeta de salida. `--version` solo la imprime. No instala nada.
# Con --arch, makepkg no construye dentro de DIST ni del repo: usa una carpeta temporal bajo
# /tmp (ver más abajo) para que el .BUILDINFO del paquete no quede con la ruta de este equipo ni
# el usuario que lo compiló; a DIST solo llega el .pkg ya terminado.
set -eu

RAIZ=$(cd "$(dirname "$0")/../.." && pwd)
ARCH=0
SOLO_VERSION=0
case ${1:-} in
  --arch) ARCH=1 ;;
  --version) SOLO_VERSION=1 ;;
  "") ;;
  *) echo "Uso: $0 [--arch | --version]" >&2; exit 2 ;;
esac

VERSION=${COTEJO_VERSION:-$(git -C "$RAIZ" show HEAD:tareas/__init__.py \
  | sed -n 's/^__version__ = "\(.*\)"$/\1/p')}
[ -n "$VERSION" ] || { echo "No encontré __version__ en tareas/__init__.py de HEAD" >&2; exit 2; }
case $VERSION in *[!A-Za-z0-9._+]*) echo "Versión no válida para un paquete: $VERSION" >&2; exit 2 ;; esac
[ "$SOLO_VERSION" = 0 ] || { echo "$VERSION"; exit 0; }
DIST=${DIST:-$RAIZ/dist}
NOMBRE=cotejo-$VERSION
TARBALL=$DIST/$NOMBRE-linux.tar.gz
mkdir -p "$DIST"

# Solo lo que install.sh copia, y lo que acompaña a una publicación.
git -C "$RAIZ" archive --format=tar.gz --prefix="$NOMBRE/" -o "$TARBALL" HEAD -- \
  install.sh uninstall.sh README.md LICENSE THIRD-PARTY-NOTICES \
  tareas enrutador skills extras barra empaquetado/linux \
  data/marca data/iconos data/temas data/fonts \
  data/io.github.cotejoapp.Cotejo.desktop data/io.github.cotejoapp.Cotejo.svg
echo "$TARBALL"

[ "$ARCH" = 1 ] || exit 0
command -v makepkg >/dev/null || { echo "Falta makepkg: --arch se construye en Arch" >&2; exit 1; }
SUMA=$(sha256sum "$TARBALL" | cut -d' ' -f1)

# makepkg construye en el directorio desde donde se lanza (startdir) y lo deja grabado, tal
# cual, en el .BUILDINFO del paquete (builddir y startdir). Si ese directorio fuera dentro del
# repo (bajo $DIST), el .pkg terminaría llevando la ruta de este equipo y de quien lo compiló.
# Por eso se construye en una carpeta temporal neutra bajo /tmp —única por `mktemp`, no fija ni
# con el usuario en el nombre— y de ahí solo se copia el .pkg ya hecho a dist/; la temporal se
# borra siempre al salir, falle o no la construcción.
BUILD=$(mktemp -d /tmp/cotejo-arch.XXXXXX)
trap 'rm -rf "$BUILD"' EXIT
sed -e "s/@VERSION@/$VERSION/" -e "s/@SHA256@/$SUMA/" "$RAIZ/empaquetado/linux/PKGBUILD" > "$BUILD/PKGBUILD"
cp "$RAIZ/empaquetado/linux/cotejo.install" "$TARBALL" "$BUILD/"
# --nodeps: construirlo no necesita las dependencias, solo instalarlo.
(cd "$BUILD" && makepkg --force --nodeps --cleanbuild >&2)
rm -rf "$DIST/arch"
mkdir -p "$DIST/arch"
cp "$BUILD/"*.pkg.tar.* "$DIST/arch/"
ls "$DIST/arch/"*.pkg.tar.*
