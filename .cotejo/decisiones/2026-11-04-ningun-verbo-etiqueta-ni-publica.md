---
id: dec-mcm0
fecha: 2026-11-04
temas: [release, seguridad]
estado: propuesta
autor: agente
---
# Ningún verbo etiqueta ni publica

El verbo release devuelve el comando git tag para la persona y nunca lo ejecuta; ningún módulo de tareas/ o enrutador/ corre git tag, git push ni gh release. Complementa dec-hjd0 (release.yml solo deja borrador).

**Por qué:** etiquetar y publicar son decisiones de una persona, no de quien reparte o ejecuta trabajo.

**Lo vigila:** pruebas/test_contrato_publicar.py.

Sale de «Lo que no se cambia sin decisión consciente» del CLAUDE.md (texto completo en ref-62y4); se propone al acortarlo en cotejo-d9cbol porque no había decisión vigente que la recogiera.
