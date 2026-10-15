---
id: pro-0ujw
fecha: 2026-10-05
temas: []
estado: resuelto
solucion: Apuntar COTEJO_CONFIG a una ruta inexistente dentro de la prueba; PruebaDeCLI ya aísla COTEJO_CONFIG para todas las demás
---
# test_por_defecto_es_obsidian falló al activar Notion en la máquina

test_por_defecto_es_obsidian falló al activar Notion en la máquina

**Causa:** La prueba leía la config real del usuario en vez de una aislada

**Solución:** Apuntar COTEJO_CONFIG a una ruta inexistente dentro de la prueba; PruebaDeCLI ya aísla COTEJO_CONFIG para todas las demás
