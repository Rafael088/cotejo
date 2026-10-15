---
id: pro-tjn3
fecha: 2026-10-06
temas: [windows, git, rutas-largas, importar]
estado: resuelto
solucion: importar_obsidian.git_init (compartido con importar_notion) se niega con un mensaje claro si la raíz pasa de 247 caracteres en Windows, y pasa core.longpaths=true para los archivos de .git/. probar_almacen.py deja la raíz en 240 y lo largo dentro (bitácora 271, recurso 294). Confirmado en Windows 11 en la segunda prueba (commit 2d6be87, F1b cotejo-8lo2ke).
---
# En Windows, git no puede crear la raíz de un repo en una ruta de más de ~248 caracteres

Síntoma: probar_almacen.py y `importar obsidian --aplicar` con un destino de 310+ caracteres salían con exit 128. Sin core.longpaths: «cannot mkdir … Filename too long». Con core.longpaths=true: crea la carpeta pero «cannot chdir». Pasa aunque LongPathsEnabled=1. Causa: git init hace chdir dentro de la raíz, y chdir/CreateDirectory en Windows se quedan en MAX_PATH − 12 aunque el sistema acepte rutas largas. Los archivos largos dentro de un repo de raíz corta sí funcionan (probar_despachar, 368 caracteres). Visto en la prueba a mano de F1 del 2026-10-06.
