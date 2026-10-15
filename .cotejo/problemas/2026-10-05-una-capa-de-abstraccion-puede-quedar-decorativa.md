---
id: pro-nzwz
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: pruebas/test_fuente.py enchufa una fuente que vive en memoria —sin notas, sin tags, sin rutas— y corre contra ella los mismos verbos que usa un agente, comprobando además que la carpeta del vault queda vacía. Si alguien vuelve a colar una suposición sobre Obsidian en cli.py, estado.py o el modelo, se pone roja. De paso es el ejemplo más corto de qué hay que escribir para añadir un segundo cerebro
---
# Una capa de abstracción puede quedar decorativa

Una capa de abstracción puede quedar decorativa: seguir funcionando solo porque por dentro todo sigue siendo Markdown

**Causa:** Las 160 pruebas de entonces corrían todas contra el vault de mentira, así que no distinguían entre «funciona» y «funciona porque la fuente sigue siendo Obsidian»

**Solución:** pruebas/test_fuente.py enchufa una fuente que vive en memoria —sin notas, sin tags, sin rutas— y corre contra ella los mismos verbos que usa un agente, comprobando además que la carpeta del vault queda vacía. Si alguien vuelve a colar una suposición sobre Obsidian en cli.py, estado.py o el modelo, se pone roja. De paso es el ejemplo más corto de qué hay que escribir para añadir un segundo cerebro
