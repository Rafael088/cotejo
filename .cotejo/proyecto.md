---
id: proyecto
---
# Cotejo

> [!abstract] En una frase
> El tablero de control para hacer vibe coding profesional: tus agentes escriben el código, y Cotejo organiza el proyecto y verifica lo que entregan.

## 🎯 Objetivo
- **Qué es:** el tablero de control para hacer vibe coding profesional. Tus agentes escriben el código; Cotejo organiza el proyecto y verifica lo que entregan.
- **Para qué sirve:** que cualquier persona, programe o no, construya software con IA de forma estructurada y que pueda crecer. Cada proyecto guarda su contexto, sus decisiones y su arquitectura, cada tarea va al modelo adecuado y nada se da por hecho sin evidencia y sin tu revisión.
- **Cómo se usa:** con cualquier agente de terminal (Claude Code, Codex, Gemini CLI, opencode) o cualquier agente que hable MCP. Gratis en Windows y Linux.
- **Frase de marca:** «Tus agentes entregan. Tú compruebas.»

*Matiz: Cotejo no escribe el código; por eso «tablero de control» en lugar de «app para vibe coding». La voz de la marca no promete productividad.*

## 🧱 Stack y arquitectura
| Capa | Tecnología | Notas |
| --- | --- | --- |
| Interfaz | Python + GTK4 + libadwaita | Todo ya venía instalado en el sistema; sin dependencias extra |
| Botón | Widget QML en la barra de Omarchy | Plugin `cotejo.barra` en `barra/`, se instala en `~/.config/omarchy/plugins`. Abre y cierra la ventana; avisa en Verde Señal cuando hay tareas `#por-validar` |
| Datos | Una **fuente** intercambiable | `tareas/modelo.py` (qué es una tarea), `tareas/fuente.py` (la interfaz) y `tareas/fuentes/obsidian.py` (notas, tags, marcas y escritura verificada). `tareas/estado.py` deja el resumen en `estado.json` para la barra |
| Infra / Deploy | `install.sh` en `~/.local` | Autostart y regla de ventana flotante en `~/.config/hypr/autostart.lua` |

- Código: este repo (instala con `./install.sh`, quita con `./uninstall.sh`)
- Comando: `cotejo` (alias viejos: `tareas-obsidian`, `foco`) abre o cierra la ventana (lo que hace el botón de la barra); `--fondo` deja el proceso listo sin abrirla; `--estado` imprime el resumen en JSON sin cargar GTK
- Config: `~/.config/cotejo/config.json` (fuente activa, parámetros por fuente, catálogo de modelos). El widget se ajusta en `~/.config/omarchy/shell.json` (`mostrarPendientes`, `intervaloSeg`, `colorAviso`)
- Proyectos abiertos recordados en `~/.local/state/tareas-obsidian/expandidos.json`

## 🗺️ Hoja de ruta
Decidida el 2026-10-02: Cotejo pasa a ser la herramienta para gestionar de punta a punta los proyectos hechos con IA, empezando por los desarrolladores que hacen vibe coding. Detalle en [[cotejo-planning-v1-2|Cotejo - Planning v1.2]].

| Versión | Qué trae |
| --- | --- |
| **1.1** | Fuente repo con `.cotejo/tareas.md`, `init`, MCP, evidencia estructurada, `comprobar`, worktree por despacho, `importar plan` ([[cotejo-planning-v1-1|Cotejo - Planning v1.1]]) |
| **1.2** | Almacén `.cotejo/` en cada repo (decisiones, arquitectura, problemas, aprendizajes, bitácora, referencias, recursos), verbos `contexto`/`buscar`/`leer` y de escritura, importadores de Obsidian y Notion ([[cotejo-planning-v1-2|Cotejo - Planning v1.2]]) |
| **1.3** | Soporte: un reporte entra como tarea y el enrutador la asigna |
| **2.0** | Grafo y vault visual en la app; Obsidian deja de hacer falta |
| Después | Del inicio al plan (crear proyecto, brief, arquitectura) y el lanzamiento como control con evidencia |

## 🔗 Enlaces
- Repo: https://github.com/Rafael088/cotejo (código, releases y web)
- Demo: 
- Relacionados: Segundo Cerebro · [[cotejo-enrutador|Enrutador]] · Marca anterior · Apps para agentes
- Revisión AX (qué falta para producción y para que la maneje un agente): [[revision-ax-de-cotejo|Revisión AX de Cotejo]]
- Planning para producción: [[cotejo-planning-para-produccion|Cotejo - Planning para Producción]]
- Lanzamiento v1.0 (fases y fechas hasta el 14 de octubre): [[cotejo-lanzamiento-v1-0|Cotejo - Lanzamiento v1.0]]
- Planning v1.1 (fuente repo, MCP, revisión con evidencia y worktrees, importar planes): [[cotejo-planning-v1-1|Cotejo - Planning v1.1]]
- Planning v1.2 (almacén .cotejo/ en cada repo, verbos de contexto, importadores de Obsidian y Notion) y hoja de ruta hasta la 2.0: [[cotejo-planning-v1-2|Cotejo - Planning v1.2]]

## ⏭️ Siguiente paso
> [!tip] Dónde retomar — 2026-10-08
> **La 1.2.0, 1.2.1 y 1.2.2 están publicadas** (la 1.2.2: filtro de fechas en Finalizada y `cotejo limpiar`). Ahora: **1.2.3 «Memoria que no miente y arranque barato»**. Ya mergeado: frescura en `contexto`, decisiones importadas aparte, aviso en `entregar`. Faltan: perfil MCP núcleo, descripciones de tool más cortas, skill corta y README. Después: decidir si el dot del laboratorio entra al board GTK; las interfaces nuevas del board (CotejoBoard 7.3.2: home con grafo, banda de proyectos, barra del Maestro); y en paralelo la 1.2.4 (`cotejo version`, `cotejo release`) y la 1.2.5 (buscar por relevancia). Planning: la nota «Cotejo - Arreglos v1.2» del vault.

**Lo que no se toca sin decisión consciente:**

- La CLI **no tiene ni tendrá** verbo para finalizar una tarea. Hay una prueba (`test_no_hay_ningun_verbo_para_finalizar_una_tarea`) cuyo único trabajo es ponerse roja si alguien lo añade: hoy vigila seis verbos.
- **Ninguna suposición sobre Obsidian fuera de `tareas/fuentes/`.** `pruebas/test_fuente.py` corre los verbos contra una fuente en memoria; si una nota o un tag se cuelan en la CLI, en el resumen o en el modelo, se pone roja.
- **El estado vive donde vive la tarea; el texto libre, en `bitacora.jsonl`.** Por eso la nota sigue siendo legible en Obsidian y el vault sigue siendo la única fuente de en qué columna está cada cosa.
- **Entregar exige evidencia; devolver y bloquear exigen motivo.** Si revisar cuesta lo mismo que hacer, la columna no sirve; y una tarea que vuelve a Pendiente sin explicación la toma el siguiente para estrellarse contra lo mismo.
- `estado.json` es un contrato con el widget de la barra, y las claves `"nota"` del JSON de la CLI y de la bitácora también: se agregan claves, no se renombran ni se quitan, aunque el nombre se quede viejo.
- Todo lo que escriba en el vault pasa por la fuente Obsidian, que verifica que la línea siga igual y reemplaza atómico. Editar el Markdown por fuera se salta eso.

**Si van a trabajar dos agentes a la vez:** rama propia cada uno (`git switch -c <lo-suyo>`) o worktrees separados, y solo uno corre `./install.sh` y reinicia el proceso de fondo. El 2026-09-17 un `git add -A` en el árbol compartido se llevó el trabajo sin commitear del otro agente, firmado con el nombre equivocado y en la rama equivocada. Desde el 2026-09-18 el repo tiene su propia identidad de git (`user.name` y `user.email` locales), así que al menos el nombre ya no se puede equivocar.

