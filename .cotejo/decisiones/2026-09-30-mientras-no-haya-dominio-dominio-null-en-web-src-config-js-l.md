---
id: dec-cjfp
fecha: 2026-09-30
temas: []
estado: aceptada
autor: importado
---
# Mientras no haya dominio (DOMINIO = null en web/src/config.js), los comandos de la web…

Mientras no haya dominio (DOMINIO = null en web/src/config.js), los comandos de la web bajan el tar.gz y el instalador de la release en GitHub

**Por qué:** Publicar curl https://cotejo.app/install.sh \| sh mandaría a la gente a ejecutar un script de un dominio que no es nuestro

**Descartado:** Publicar con cotejo.app de relleno; no publicar hasta tener dominio
