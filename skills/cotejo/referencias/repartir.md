# Repartir tareas: el maestro, la capacidad y los motores

## Caso B — «hazme dos tareas del proyecto X»

Tú eres el maestro: no haces las tareas, las repartes. Cada una va a **su propio sitio, con su
propio modelo**, y varias avanzan a la vez.

1. `cotejo plan --proyecto <nombre> --solo-despachables --limite <n>`.
2. Si alguna viene con `asignado: false`, pregunta por **todas ellas en una sola vez**, con la
   propuesta de cada una delante, y escribe las respuestas con `cotejo asignar`. Preguntar una
   vez por tarea es la forma de que nadie quiera usar esto.
3. **Si sabes algo que la tarea no dice, ponlo en `--nota`.** Qué parte ya está hecha, qué repo
   no hay que tocar, qué cambió desde el enunciado. Va dentro del encargo, aparte del texto.
4. **Asegúrate de que cada proyecto tenga carpeta en `enrutador.proyectos`** (abajo). Si falta,
   el headless se abrirá donde esté el proceso padre.
5. **Pregunta cuántos caben antes de lanzar varios a la vez** (cada sesión o headless es un
   proceso con su memoria; varios juntos pueden llevar la máquina al OOM):

   ```sh
   cotejo capacidad --proyecto <nombre>
   ```

   Mide memoria, swap, CPU, carga y los agentes en marcha y devuelve `caben`, qué lo limita y
   `ahora`/`esperar` con las tareas asignadas. Lanza solo las de `ahora`; las otras, cuando
   termine alguna, volviendo a preguntar. Con `caben: 0` no lances nada.
6. Reparte. Dos maneras, según quién tenga que poder mirar el trabajo:

   **Instancias de verdad** (sesiones completas, abribles, que siguen vivas si cierras):

   ```sh
   cotejo despachar <id> --motor sesion
   ```

   Abre el cliente en la carpeta del proyecto y devuelve el identificador (`claude attach <id>`
   para Claude). **No mires sus logs para saber cómo va**: el canal es Cotejo, y al terminar
   aparece en «Para comprobar» de CotejoBoard con su evidencia.

   **Subagentes** (dentro de esta sesión):

   ```sh
   cotejo despachar <id> --motor agente
   ```

   Toma la tarea y devuelve el encargo en `salida`; lánzalo como subagente **con el modelo de
   la decisión**. Vuelven a ti cuando acaban.
7. Cuenta qué repartiste y a quién. Si alguna se quedó sin repartir, di por qué.

## Y al día siguiente: ¿sirvió?

```sh
cotejo revisar --dias 2
```

Cruza lo repartido con dónde está hoy cada tarea. Mira `colgada` (se tomó y nadie la entregó ni
la devolvió), `devuelta` (volvió a Pendiente, con motivo) y `perdida` en curso (el headless murió
sin volver). Para retomar un proyecto empieza por aquí y no por `plan`: repartir otra vez lo que
se colgó es la forma más cara de no avanzar. `cotejo worktrees` dice dónde quedó cada worktree.

## Dónde trabaja el agente: el directorio del proyecto

Antes de lanzar con `--motor headless` o `--motor sesion`, el cliente se abre en la carpeta que
Cotejo le diga. Sin configuración hereda la de donde corrió `cotejo`, que puede ser la
instalación (`~/.local/share/tareas-obsidian`) en vez del repo; si el cliente se niega a leer
fuera de su carpeta, la tarea falla antes de empezar.

**Configura la carpeta** en `~/.config/cotejo/config.json`, bajo `enrutador.proyectos`:

```json
{ "enrutador": { "proyectos": { "<nombre-del-proyecto>": "/ruta/al/repo" } } }
```

No pongas la ruta de la máquina del autor: pregunta o deduce dónde está el repo en esta sesión.
`cotejo config validar` dice si el JSON está bien; `cotejo despachar <id> --simular` enseña el
directorio que usaría sin tomar la tarea.

## Modelos configurables

Consulta con `cotejo modelos` antes de asignar. Si el cliente tiene un modelo que no aparece,
regístralo con una clave corta. No guardes credenciales: `modelo-id` solo identifica el modelo y
`cliente` dice qué integración lo ejecuta. Usa el identificador real del cliente; si no lo sabes,
pregunta antes de inventarlo.

```sh
cotejo modelos agregar --clave <clave-corta> --nombre "Nombre legible" \
  --modelo-id <id-del-cliente> --cliente <claude|opencode|codex|gemini|antigravity> --nivel n2
```

Después, `cotejo asignar <id> <clave>`. Cotejo no lanza clientes externos por su cuenta; el
motor `agente` devuelve el encargo al cliente que está trabajando.

## Si hay un plan.md (o un PRD) para convertir en tareas

```sh
cotejo importar plan <plan.md> --proyecto <nombre>              # ensayo: no toca nada
cotejo importar plan <plan.md> --proyecto <nombre> --aplicar    # las crea de verdad
```

Lee las casillas `- [ ]` y, si no hay, los encabezados de paso (`## Paso N`, `### Tarea N`);
propone dificultad y modelo igual que `decidir`. **Es un ensayo por defecto**: enséñaselo a quien
te lo encargó antes de `--aplicar`. Repetirlo no duplica (`"creada": false`).

Para crear una tarea suelta: `cotejo crear "texto" --proyecto <nombre>` (con `--dificultad
facil|medio|dificil` si se sabe).
