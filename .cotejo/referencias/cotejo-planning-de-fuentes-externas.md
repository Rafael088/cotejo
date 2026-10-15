---
id: ref-p579
temas: [cotejo, planning, fuentes, ax, notion]
resumen: "Planning de cómo Cotejo se conecta a cualquier aplicativo (Notion y los que vengan) para traer proyectos y tareas, sin que el agente sepa cómo funciona la app de atrás."
---
# Cotejo - Planning de fuentes externas

# Cotejo — Planning de fuentes externas

Planning para que [[proyecto|Cotejo]] se conecte a cualquier aplicativo para obtener proyectos y tareas, sin que el agente necesite saber cómo funciona la app de detrás. El diseño sigue las prácticas de [[revision-ax-de-cotejo|Agent Experience (AX)]].

## Decisiones tomadas

| Pregunta | Decisión |
| --- | --- |
| Comando público | `cotejo` (con posible alias interno `tareas-obsidian`) |
| Mecanismo de fuentes externas | Comandos por `subprocess` |
| Primera fuente de prueba | Notion |
| Archivo de configuración | Un solo archivo: `~/.config/cotejo/config.json` |
| Estado en el vault | Planificación, sin tareas aún |

## Por qué subprocess

- Funciona igual en Windows y en cualquier distribución Linux.
- Cualquier lenguaje puede implementar un adaptador: Python, Node, Go, o el CLI oficial de la app.
- Cotejo no necesita conocer la app: solo invoca subcomandos estándar.
- El despliegue es simple: copiar el adaptador junto a Cotejo o dejarlo en el `PATH`.
- Es ligeramente más lento que una llamada interna, pero los verbos de agente no son de alta frecuencia; el costo sigue siendo bajo comparado con leer el vault entero.

## Arquitectura propuesta

```
agente → cotejo CLI → fuente.py → Registro de fuentes
                              ├── built-in: obsidian, markdown
                              └── externas: notion, linear, asana...
                                    ↓
                              comando subprocess (cotejo-notion, etc.)
```

## Configuración en un solo archivo

`~/.config/cotejo/config.json`:

```json
{
  "fuente": "notion",
  "fuentes": {
    "obsidian": {
      "tipo": "built-in",
      "vault": "/ruta/al/vault",
      "carpeta_proyectos": "01-Proyectos"
    },
    "notion": {
      "tipo": "externa",
      "comando": "cotejo-notion",
      "token_env": "NOTION_TOKEN",
      "database_id": "abc123..."
    }
  },
  "enrutador": {
    "motor": "agente",
    "modelos": []
  }
}
```

Ventaja AX: `cotejo doctor` lee un solo archivo y responde en una llamada.

## CLI de fuentes

| Comando | Qué hace |
| --- | --- |
| `cotejo doctor` | Diagnóstico general y de la fuente activa |
| `cotejo config init` | Crea `config.json` con valores por defecto y explicaciones |
| `cotejo config validate` | Valida JSON y coherencia sin tocar datos |
| `cotejo fuentes` | Lista built-ins y externas registradas + cuál está activa |
| `cotejo fuentes info <nombre>` | Muestra parámetros requeridos y ejemplo |
| `cotejo fuentes probar <nombre>` | Ejecuta `doctor` + `escanear` de prueba, sin escribir |
| `cotejo fuentes usar <nombre>` | Cambia la fuente activa |
| `cotejo fuentes agregar <nombre> --comando <cmd>` | Registra fuente externa |
| `cotejo fuentes quitar <nombre>` | La desregistra, no borra datos |
| `cotejo protocolo` | Imprime el protocolo canónico para agentes |

## Contrato de una fuente externa

Cada adaptador externo debe implementar estos subcomandos y devolver JSON con `"esquema": 1`.

### `doctor`

```json
{
  "esquema": 1,
  "ok": true,
  "mensaje": "Conectado a Notion"
}
```

### `protocolo`

```json
{
  "esquema": 1,
  "nombre": "notion",
  "lectura": true,
  "escritura": true,
  "verbos": ["escanear", "tomar", "entregar", "bloquear", "asignar"],
  "campos_tarea": ["id", "texto", "estado", "agente", "dificultad", "proyecto"],
  "estados": ["pendiente", "en-curso", "por-validar", "hecha"]
}
```

### `escanear`

Devuelve proyectos y tareas en la misma estructura que usa Cotejo hoy.

### `tomar`, `entregar`, `bloquear`, `asignar`

Reciben `id` y parámetros adicionales (`--agente`, `--evidencia`, `--motivo`). Devuelven la tarea como quedó.

## Notion como primera fuente de prueba

1. Crear un adaptador `cotejo-notion` que use la API oficial de Notion.
2. Mapear:
   - Base de datos de Notion → proyectos.
   - Páginas de la base de datos → tareas.
   - Propiedades de Notion → estado, agente, dificultad.
   - Checkbox "Done" → `hecha`.
3. Soportar escritura mediante actualización de propiedades.
4. Asegurar idempotencia: si la página ya está en el estado deseado, no se toca y se devuelve `"cambio": false`.

## Pasos de implementación

### Fase 1: CLI y config
- Renombrar/complementar el comando a `cotejo`.
- Crear `cotejo config init`, `cotejo config validate`, `cotejo doctor`.
- Crear `cotejo fuentes`, `cotejo fuentes info`, `cotejo fuentes probar`, `cotejo fuentes usar`.
- Agregar pruebas para cada nuevo verbo.

### Fase 2: Fuente externa por subprocess
- Extender `fuente.py` para soportar `tipo: "externa"`.
- Crear `tareas/fuentes/externa.py` como adaptador genérico.
- Implementar `cotejo fuentes agregar` y `cotejo fuentes quitar`.

### Fase 3: Adaptador de Notion
- Desarrollar `cotejo-notion` (en `extras/notion/` o similar).
- Documentar requisitos: token de integración, ID de base de datos.
- Probar `cotejo fuentes probar notion`.

### Fase 4: Skill y protocolo
- Actualizar `skills/cotejo/SKILL.md` con la sección de fuentes.
- Asegurar que `cotejo protocolo` devuelva el texto canónico.
- Actualizar pruebas para que vigilen que el protocolo no miente.

### Fase 5: README
- Añadir sección "Conectar Cotejo a otra app".
- Incluir template mínimo de adaptador externo.

## Qué no cambia

- No hay verbo para finalizar tareas.
- El agente sigue sin editar Markdown ni APIs a mano.
- Los errores siguen llevando `salida` y `reintentable`.
- `estado.json` y `bitacora.jsonl` mantienen su esquema.

## Estado de la implementación (2026-09-24)

Las cinco fases están hechas, en `master` (commit `744b777`, encima de la eliminación de CotejoList, `3fc52a2`) e **instaladas** el 2026-09-24. La config vive ya en `~/.config/cotejo/config.json`; Notion está registrada sin activar y probada contra la base «Cotejo — prueba». 414 pruebas en verde; `evaluar` sigue en 85,7 % y 0 abaratados.

- **Fase 1:** `cotejo doctor`, `cotejo fuentes [info|probar|usar|agregar|quitar]`, `cotejo config init|validar`. Config en `~/.config/cotejo/config.json`; la vieja se sigue leyendo y `config init` la migra y la renombra a `.migrado`.
- **Fase 2:** `tareas/fuentes/externa.py`, el adaptador genérico por subproceso.
- **Fase 3:** `extras/notion/cotejo_notion.py` (instalado como `cotejo-notion`), probado contra un Notion de mentira por HTTP. **Falta probarlo contra una base real** (tarea `cotejo-g9etjp`).
- **Fase 4:** `SKILL.md` usa `cotejo` y explica `doctor`; `cotejo protocolo` ya lo repartía.
- **Fase 5:** README, sección «Conectar Cotejo a otra app», con `extras/plantilla/cotejo_plantilla.py` como plantilla mínima.

### En qué se apartó del planning, y por qué

- **El adaptador no implementa `tomar`, `entregar`, `bloquear` ni `asignar`.** Implementa primitivas (`estado`, `agente`, `marcar`, `crear`), como la interfaz `Fuente`. Si cada adaptador tuviera su `entregar`, validaría la evidencia a su manera y la guardaría en la app de fuera en vez de en la bitácora. Cada escritura lleva `--esperado` y el adaptador contesta `cambiada` sin escribir si alguien tocó la tarea: la misma garantía que Obsidian.
- **`config validar`**, no `validate`: todos los verbos de Cotejo están en español.
- **`config` y `protocolo` ya existían** (del enrutador): `config` ganó `init` y `validar` sin cambiar lo que hacía a secas.
- **No hay fuente built-in `markdown`**: no existía y nada la pedía todavía.
- **Los textos del enrutador siguen diciendo `tareas-obsidian`** (que sigue funcionando), para no chocar con la rama `enrutador-mide-su-reparto`, que toca esos archivos (tarea `cotejo-bulou2`).
- **Notion:** una página es una tarea; el proyecto sale de la propiedad «Proyecto» (select, texto o relación), o es la base entera si no la hay. Los estados de fábrica de Notion (*Not started*, *In progress*, *Done*) se entienden sin configurar nada, pero hace falta una opción para «por validar»: `doctor` avisa.

Hecho: prueba contra Notion real (`cotejo-g9etjp`) e integración e instalación (`cotejo-wsvpvq`), las dos esperando comprobación. Pendiente: `cotejo-bulou2`.

### Cambiar de fuente (2026-09-24, `cd2d839`)

- `cotejo fuentes usar obsidian|notion` es todo: la app vigila la config y reabre la fuente sola; board y barra cambian sin reiniciar.
- El token de Notion se lee de `NOTION_TOKEN` o de `~/.config/cotejo/notion.token` (600), que es lo que ven el board y la barra.
- Skill `cotejo-fuentes` (instalada en Claude Code y Codex) para cambiar de fuente o conectar una app nueva sin cargar el protocolo entero.
- Fuente activa al cerrar: **Obsidian**. Notion queda registrada, con la base «Cotejo — prueba».

## Enlaces

- Proyecto: [[proyecto|Cotejo]]
- Planning de producción: [[cotejo-planning-para-produccion|Cotejo - Planning para Producción]]
- Revisión AX: [[revision-ax-de-cotejo|Revisión AX de Cotejo]]
