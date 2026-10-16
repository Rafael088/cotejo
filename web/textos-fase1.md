# Textos de la web · Fase 1

Borrador para maquetar. Voz de `web/PRODUCT.md`: español, tuteo, frases cortas, verbos fijos, sin promesas de productividad. Solo lo que trae la versión publicada (1.2.5). Cada bloque indica su rol: titular, subtítulo, pasos, notas.

## Fase 1 A · Secciones por público

Orden en la página: primero «Si no programas», después «Si programas». Un selector o dos anclas arriba de ambas: «No programo» / «Programo».

---

### Sección 1 · Si no programas

**Etiqueta de sección:** Si no programas

**Titular:** Tu agente construye. Tú decides si está bien.

**Subtítulo:** Cotejo no tiene una pantalla aparte para ti ni escribe el código. Trabajas con tu agente de siempre; Cotejo guarda el proyecto en orden y cada entrega llega con un resumen en lenguaje llano para que la revises.

#### Qué necesitas

- Un agente de terminal (Claude Code, Codex, Gemini CLI u opencode) o cualquier agente que hable MCP.
- Un ordenador con Linux o con Windows 10/11.
- Cotejo, que es gratis.
- Unos minutos para revisar lo que el agente te entregue. Esa parte es tuya y no se delega.

#### Cómo empiezas

1. **Instala Cotejo.** Instalar pide pegar un comando en una terminal. Si no te sientes cómodo, pídeselo a tu agente: «instálame Cotejo» y pásale el comando de esta página. (Bloque «comando»: el de Linux y el de Windows, con botón de copiar, como en el hero.)
2. **Dile a tu agente que arranque el proyecto.** Escribe «empiezo un proyecto» o «prepara este repo para trabajar con Cotejo». El agente prepara la carpeta, te hace cinco preguntas en un solo mensaje (cada una con una respuesta por defecto que solo confirmas o corriges) y deja escrito el objetivo, el siguiente paso y entre 3 y 8 tareas para la primera versión.
3. **Acepta lo que importa.** Las decisiones que condicionan el proyecto (por ejemplo, qué tecnología usar) llegan como propuestas. Nada se da por vigente hasta que tú las aceptas en CotejoBoard.

#### Tu día a día

1. **Pídele trabajo.** «Hazme dos tareas del proyecto.» El agente reparte cada tarea al modelo que le toca y te cuenta a quién y por qué.
2. **Espera a que entregue.** Cada entrega aparece en la columna «Para comprobar» de CotejoBoard, con su evidencia.
3. **Lee el resumen.** Dice qué cambió visto desde fuera y cómo probarlo tú mismo, sin nombres de archivos ni jerga.
4. **Pruébalo y decide.** Si está bien, la apruebas. Si no, la devuelves con un motivo y el agente vuelve a ella.

Cierre en una línea: **Hecho es cuando alguien lo revisó. Ese alguien eres tú.**

#### Notas

- Quien aprueba eres tú: el agente no puede marcar una tarea como hecha. No existe un verbo para eso, a propósito.
- Cotejo no escribe código por ti. Lo hace tu agente; Cotejo organiza y verifica.
- Hay tareas que no son de un modelo sino tuyas (comprar un dominio, firmar, abrir una cuenta). Salen marcadas como de una persona y no se despachan.
- CotejoBoard es el tablero donde revisas; no es un asistente para crear proyectos. El proyecto lo arranca tu agente.
- Cotejo 1.2 es beta: puede fallar. Si algo falla, `cotejo doctor` dice qué hacer, y puedes contarlo en un issue.

**Llamada a la acción:** Instala Cotejo (ancla al bloque de instalación).

---

### Sección 2 · Si programas

**Etiqueta de sección:** Si programas

**Titular:** Del repo vacío a la versión etiquetada, con evidencia en cada paso.

**Subtítulo:** El contexto, las decisiones y la arquitectura viven en `.cotejo/`, dentro de tu repo, un archivo por entrada. Tus agentes escriben el código; Cotejo reparte, recoge pruebas repetibles y deja la última palabra a una persona.

#### Pasos

1. **`cotejo init`**
   Dentro del repo (o con `--repo <carpeta>`, que la crea y le hace `git init`). Deja `.cotejo/` con `tareas.md`, `proyecto.md` y una carpeta por tipo de conocimiento; la versión queda en 0.1.0. Es idempotente: repetirlo no pisa nada.

2. **`cotejo plan`**
   `cotejo plan --proyecto mi-app --solo-despachables` muestra por cada pendiente qué modelo la recibiría y por qué. No escribe nada. Si una tarea no tiene modelo asignado, se pregunta; `cotejo asignar <id> <modelo>` guarda la respuesta. Con un `plan.md` ya hecho, `cotejo importar plan` lo convierte en tareas (ensayo por defecto).

3. **`cotejo despachar`**
   `cotejo despachar <id>` toma la tarea y devuelve el encargo. Si la tarea está en un repo de git, crea un worktree con la rama `cotejo/<id>`: el agente trabaja y hace commit ahí. Puede ir como subagente (`--motor agente`) o como sesión aparte (`--motor sesion`). Las tareas de una persona (n0) no se despachan, sin excepción. `cotejo capacidad` dice cuántas caben a la vez en tu máquina.

4. **`cotejo entregar`, con evidencia**
   El agente entrega desde su carpeta con archivos, commit y `--prueba`, un comando suelto por prueba que Cotejo corre sin shell. Siempre con `--resumen`: qué cambió visto desde fuera y cómo probarlo, sin jerga. Si se atasca, `cotejo bloquear <id> --motivo "..."` la devuelve a Pendiente en vez de dejarla a medias.

5. **`cotejo comprobar`**
   `cotejo comprobar <id>` vuelve a correr las pruebas de la entrega y no escribe nada. En CotejoBoard revisas el diff y el resumen, y aprobar es cosa tuya.

6. **`cotejo release`**
   `cotejo release --proyecto mi-app --version 1.3.0` es un ensayo: enseña las notas que saldrían (tareas aprobadas, decisiones aceptadas, problemas resueltos) y se niega, nombrándolas, si queda alguna tarea de esa versión sin aprobar. Con `--aplicar` escribe `.cotejo/releases/v1.3.0.md`. Etiquetar y publicar lo haces tú.

#### Notas

- Un agente se entera barato: `cotejo contexto` devuelve objetivo, tareas, decisiones vigentes y temas en menos de mil tokens. `cotejo ahorro` enseña lo que costó enterarse y su supuesto (ver el medidor).
- Una decisión propuesta por un agente (`proponer decision`) se acepta solo desde CotejoBoard.
- Si ya tienes el proyecto en Obsidian o Notion, `cotejo importar` lo trae entero a `.cotejo/` (ensayo primero, `--aplicar` después).
- Todos los verbos devuelven JSON y los errores dicen cuál es el siguiente paso.

**Llamada a la acción:** Instala Cotejo y corre `cotejo init` (ancla al bloque de instalación).

---

## Afirmaciones y de dónde salen

| Afirmación | Respaldo |
| --- | --- |
| Quien no programa entra por su agente y revisa un resumen en lenguaje llano; no hay interfaz propia | `dec-22dl`; `web/PRODUCT.md` (Users) |
| Instalar pide pegar un comando o pedírselo al agente | `web/PRODUCT.md` (Users); `web/src/config.js` (COMANDOS) |
| Funciona con Claude Code, Codex, Gemini CLI, opencode o cualquier agente MCP; gratis; Linux y Windows 10/11 | `README.md` (intro); `web/PRODUCT.md` (Capabilities) |
| El agente arranca el proyecto con cinco preguntas en un mensaje y deja objetivo, siguiente paso, decisiones propuestas, arquitectura y 3 a 8 tareas | `cotejo protocolo --completo` (referencias/inicio.md); `README.md` paso 3 |
| Las decisiones propuestas solo se aceptan en CotejoBoard | `cotejo protocolo --completo` (almacén e inicio) |
| El agente reparte cada tarea al modelo adecuado y dice por qué | `cotejo plan --help`; `cotejo despachar --help`; protocolo (destinos y reparto) |
| Las tareas n0 son de una persona y no se despachan | protocolo (Reglas duras) |
| La entrega aparece en «Para comprobar» con evidencia y resumen sin jerga | `cotejo entregar --help`; protocolo (referencias/entrega.md) |
| El agente no puede finalizar; aprobar es de la persona | protocolo (Reglas duras); `web/PRODUCT.md` (Positioning) |
| `init` deja `.cotejo/` en 0.1.0 y es idempotente | `cotejo init --help`; `README.md` paso 2 |
| `despachar` crea worktree con rama `cotejo/<id>`; motores agente y sesión | `cotejo despachar --help`; protocolo (ciclo y repartir) |
| `--prueba` corre sin shell, un comando por prueba; `bloquear` devuelve a Pendiente | `cotejo entregar --help`; protocolo (ciclo) |
| `comprobar` repite las pruebas y no escribe | `cotejo comprobar --help`; `README.md` (Para agentes) |
| `release` es ensayo, se niega con tareas sin aprobar, `--aplicar` escribe `.cotejo/releases/vX.Y.Z.md`; etiquetar es de la persona | `cotejo release --help`; protocolo (referencias/versiones.md) |
| `contexto` cabe en menos de mil tokens | protocolo (almacén) |
| `importar` trae un proyecto de Obsidian o Notion, con ensayo por defecto | `web/PRODUCT.md` (Operating Context); protocolo (inicio) |
| Cotejo 1.2 es beta y se ofrece sin garantías | `README.md` (aviso de beta) |
