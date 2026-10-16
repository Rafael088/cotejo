// Los textos de /comofunciona que no son marcado: los pasos de «No programo» y el ciclo de
// «Programo» con la salida de cada verbo.
//
// Las salidas son las de la CLI de verdad (cotejo 1.2.5 sobre un repo de prueba «mi-app»),
// recortadas a las claves que cuentan la historia: las claves y los valores son los que devuelve,
// no se inventan. Si un verbo cambia sus claves, esto se rehace corriendo el ciclo otra vez.
// ⟦…⟧ marca lo que la consola pinta en verde (lo que salió bien).

export const PASOS = [
  ['Pides.', 'Con tus palabras, a tu agente de siempre.'],
  ['Se planea.', 'Tu agente lo parte en tareas y las pone en el tablero.'],
  ['Te entrega.', 'Cada tarea vuelve con un resumen que entiendes.'],
  ['Decides.', 'La apruebas, o la devuelves con un motivo.'],
]

// Lo que dura cada escena antes de pasar a la siguiente; la última da más tiempo para decidir.
export const DURACION = [4200, 4200, 4200, 7000]

export const VERBOS = [
  {
    verbo: 'init',
    que: 'Deja .cotejo/ en tu repo, en la 0.1.0.',
    comando: 'cotejo init',
    salida: `{ "creado": ⟦true⟧,
  "creados": ["tareas.md", "proyecto.md", "decisiones/", "problemas/",
              "arquitectura/", "aprendizajes/", "bitacora/", "referencias/",
              "recursos/"],
  "version": { "version": "0.1.0", "hecho": "puesta" } }`,
  },
  {
    verbo: 'plan',
    que: 'Qué modelo hace cada tarea, y por qué. No escribe nada.',
    comando: 'cotejo plan --proyecto mi-app --solo-despachables',
    salida: `{ "despachables": 2, "sin_asignar": 1,
  "tareas": [
    { "id": "cotejo-5eeu8l", "texto": "Registro con correo",
      "modelo": "sonnet", "por": "asignacion" },
    { "id": "cotejo-4lm46f", "texto": "Correo de bienvenida",
      "modelo": "sonnet", "por": "defecto",
      "razon": "ninguna regla la reconoció, y ante la duda se escala: el defecto es Sonnet, no Haiku" }
  ] }`,
  },
  {
    verbo: 'despachar',
    que: 'Toma la tarea y abre un worktree con su rama.',
    comando: 'cotejo despachar cotejo-5eeu8l --motor agente',
    salida: `{ "tomada": ⟦true⟧,
  "worktree": { "rama": "cotejo/cotejo-5eeu8l", "creado": true },
  "salida": "Tarea de Cotejo cotejo-5eeu8l — proyecto mi-app.…" }`,
  },
  {
    verbo: 'entregar',
    que: 'Con evidencia y pruebas que Cotejo corre sin shell.',
    comando: `cotejo entregar cotejo-5eeu8l --evidencia "commit 75284ab" \\
    --resumen "Ya te puedes registrar con tu correo." --prueba "npm test"`,
    salida: `{ "tarea": { "estado": "por-validar" },
  "git": { "rama": "cotejo/cotejo-5eeu8l", "sin_commitear": false },
  "pruebas": [{ "comando": "npm test", "codigo": ⟦0⟧ }],
  "nota_para_el_agente": "Queda esperando que una persona la compruebe en CotejoBoard. Marcar [x] no es tuyo." }`,
  },
  {
    verbo: 'comprobar',
    que: 'Repite las pruebas. Aprobar es tuyo, en el board.',
    comando: 'cotejo comprobar cotejo-5eeu8l',
    salida: `{ "sigue_igual": ⟦true⟧,
  "pruebas": [{ "comando": "npm test", "antes": 0, "ahora": ⟦0⟧, "igual": true }] }`,
  },
  {
    verbo: 'release',
    que: 'Ensayo de notas; se niega si queda algo sin aprobar.',
    comando: 'cotejo release --proyecto mi-app --version 0.1.0',
    salida: `{ "error": "Quedan 1 tareas de la 0.1.0 sin aprobar: cotejo-7baiit (Página de inicio, pendiente)",
  "salida": "Que se aprueben en el board, o muévelas de versión; después, repite." }`,
  },
]

// El árbol que deja `cotejo init` (el mismo «creados» de arriba).
export const ARBOL = ['proyecto.md', 'tareas.md', 'decisiones/', 'arquitectura/', 'problemas/', 'aprendizajes/', 'bitacora/', 'referencias/', 'recursos/']
