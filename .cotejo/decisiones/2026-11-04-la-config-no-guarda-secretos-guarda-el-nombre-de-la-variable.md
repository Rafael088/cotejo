---
id: dec-791y
fecha: 2026-11-04
temas: [seguridad, config]
estado: propuesta
autor: agente
---
# La config no guarda secretos: guarda el nombre de la variable de entorno

La config guarda token_env (el nombre de la variable), nunca el valor; fuentes agregar y config validar se niegan con cualquier clave que parezca un token. Generaliza dec-yrvu (el token de Notion) a cualquier fuente.

**Por qué:** la config se copia, se comparte y la leen los agentes.

Sale de «Lo que no se cambia sin decisión consciente» del CLAUDE.md (texto completo en ref-62y4); se propone al acortarlo en cotejo-d9cbol porque no había decisión vigente que la recogiera.
