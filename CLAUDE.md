# Cotejo — para quien trabaje aquí

Lo mínimo para tocar este repo. El resto vive en `.cotejo/` y se pide barato:
`cotejo contexto` (<1k tokens), `cotejo buscar --texto X`, `cotejo leer <id>`.
Este archivo no pasa de 8 KB (`pruebas/test_claude_md_corto.py`): lo nuevo va a `.cotejo/`
con `cotejo anotar` o `cotejo proponer decision`, y aquí solo su id.

## Cómo probar

- **El Cotejo instalado es el release publicado, no este repo.** Aquí no se corre
  `./install.sh`. El código del checkout (repo o worktree) se prueba con `cotejo-dev`
  (`herramientas/cotejo_dev.py`): config, estado y worktrees propios en
  `~/.local/state/cotejo-dev`, vault de prueba (Faro y Horizonte) y board con otro APP_ID.
  `COTEJO_VAULT=/ruta cotejo-dev …` apunta a otro vault. Detalle en ref-98dq.
- Pruebas: las de lo que tocas, `python3 -m unittest discover pruebas -p test_x.py`. La suite entera
  (`python3 -m unittest discover pruebas`) una vez, al final, antes de entregar. Las que
  necesitan pantalla se saltan sin ella.
- Si tocas reglas del enrutador: `python3 -m tareas evaluar` y `abaratados` sigue en 0.
- `git status --short` antes de empezar: si no está limpio, averigua por qué.
- Ver un arreglo del board antes del release: `cotejo-dev --board`. El board publicado vive
  en `--fondo` y cerrar la ventana no recarga el código; se reinicia por su pid, nunca con
  `pkill -f` (apr-7v20).

## Reglas duras

Texto completo y la prueba que vigila cada una: ref-62y4.

- La CLI no tiene verbo para finalizar ni para crear proyectos; `[x]` es de una persona en
  el board (dec-5fj1, dec-p5k8, dec-49kj, dec-hgq7).
- Todo lo que se escribe en el vault pasa por `fuentes/obsidian.py`, verificado y atómico;
  nada de `sed` ni edición a mano del Markdown de tareas (dec-v9vf, dec-ceht).
- Ninguna suposición sobre Obsidian fuera de su fuente: `#en-curso` o `.md` fuera de
  `fuentes/` es un error (dec-gymf, dec-r6u2).
- `estado.json` es un contrato: claves que se agregan, nunca se renombran ni quitan (dec-j012).
- El texto libre (evidencia, motivos) va a la bitácora, no a la línea de la tarea (dec-c3cw).
- Entregar exige evidencia; bloquear y devolver, motivo (dec-prwn, dec-m3lp, dec-1x7s).
- El medidor de ahorro mide, no estima; en plata, nunca en verde (dec-vqhc).
- El núcleo no importa GTK: solo `tareas/app/` y el widget del dot (dec-pxtt).
- Ninguna ruta de config o estado a mano: salen de `tareas/rutas.py` (dec-vps5).
- El CSS del board no lleva colores: todo es un token `var(--k-…)` de los temas (dec-x652).
- Ningún módulo de `tareas/` o `enrutador/` pasa de 800 líneas; si se pasa, se parte (dec-owvb).
- El estado de interfaz vive fuera del vault (dec-8am7).
- Un adaptador externo implementa primitivas, no verbos, y escribe con `--esperado` (dec-h1bx).
- La config no guarda secretos (dec-791y, dec-yrvu); un solo archivo de config vivo (dec-k9sg).
- Cambiar de fuente no exige reiniciar (dec-l2x5); una fuente que no contesta es un problema,
  no una lista vacía (dec-bhh5).
- Ningún verbo etiqueta ni publica (dec-mcm0, dec-hjd0).
- El enrutador no entrega ni finaliza, y toma por `cli.tomar_para` (dec-0r9e).
- Gastar lo decide una persona: el nivel humano no se despacha, sin `--forzar`; sin modelo
  puesto, se pregunta (dec-7aqz).
- Solo tres cosas lanzan un agente sin interfaz, todas pedidas en el board (dec-1wh6); el
  maestro es una conversación que puede todo menos aprobar, y `enrutador/candado.py` deshace
  lo que apruebe (dec-qnug, reemplaza a dec-ku4d).
- Ante la duda se escala, nunca se abarata; las etiquetas del set de evaluación no se editan
  (dec-714y, dec-1qkk).
- Toda decisión de `despachar` deja línea, también las negativas (dec-xeke).
- El protocolo del agente se escribe una vez, en `skills/cotejo/SKILL.md` (dec-l4c2).
- Dos agentes a la vez: rama o worktree propio cada uno, `git status` y `git branch` antes de
  commitear, y nunca `git add -A` en un árbol compartido (apr-38jf).

dec-pxtt, dec-vps5, dec-owvb, dec-8am7, dec-791y, dec-bhh5, dec-mcm0, dec-prwn, dec-0r9e,
dec-7aqz, dec-1wh6, dec-qnug, dec-714y y dec-xeke están **propuestas**: aceptarlas es de una
persona.

## Índice

- Arquitectura y piezas: arq-lfay. Detalle por módulo, en referencias con tema `arquitectura`:
  - ref-98dq · Cotejo publicado, `cotejo-dev` y nombres heredados de Foco
  - ref-tvaz · Fuentes, config e `init`
  - ref-h6ka · Enrutador, clientes de agentes, modelos y MCP
  - ref-k6ew · Worktrees, almacén `.cotejo` y arquitectura dibujable
  - ref-ss7l · Inicio, equipo, constelación, mapa y «Ver mi app»
  - ref-rvpe · Importador, vista de revisión y preparación en segundo plano
  - ref-l5zo · Mover a Haciendo lanza el agente: despacho, pausa, fin y rechazo
  - ref-imu9 · El maestro como conversación y «Revisar el plan»
- La mudanza del enrutador a este repo: apr-d34h.
- Bugs conocidos: `cotejo buscar --tipo problema`. Si uno vuelve, se marca recurrente y se
  busca por qué volvió (ejemplo: pro-hoss, el menú de los 3 puntos).
- Estado del día y siguiente paso: `cotejo contexto`. Informe AX con costos medidos: vault,
  `01-Proyectos/Revisión AX de Cotejo.md`.
