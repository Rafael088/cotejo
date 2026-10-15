#!/bin/sh
# Publica la web en GitHub Pages: construye y empuja dist/ a la rama gh-pages de este mismo
# repo (Rafael088/cotejo).
#
#   sh publicar.sh                  # https://cotejo.dev/ (base en la raíz y CNAME)
#   DOMINIO= sh publicar.sh         # solo si se pide: sin dominio, base /cotejo/ y sin CNAME
#                                   # (¡tumba cotejo.dev: gh-pages pierde el CNAME!)
set -eu

REPO="https://github.com/Rafael088/cotejo.git"
cd "$(dirname "$0")"

DOMINIO="${DOMINIO-cotejo.dev}"
if [ -n "$DOMINIO" ]; then BASE=/; else BASE=/cotejo/; fi
BASE="$BASE" npm run build

touch dist/.nojekyll
[ -n "$DOMINIO" ] && printf '%s\n' "$DOMINIO" > dist/CNAME

COMMIT=$(git rev-parse --short HEAD)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp -R dist/. "$TMP"
cd "$TMP"
git init -q -b gh-pages
git add -A
# Identidad fija: la global de git es la de una persona y este commit va a un repo público.
git -c user.name=Cotejo -c user.email=noreply@cotejo.dev \
    commit -q -m "Web desde $COMMIT"
git push -q -f "$REPO" gh-pages
echo "Publicado: gh-pages de $REPO (base $BASE)"
