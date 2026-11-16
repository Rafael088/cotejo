// El índice de /docs, en un solo sitio y sin JSX: la barra lateral, el «Anterior / Siguiente» y la
// comprobación del prerender lo leen. Cada ruta tiene que existir también en rutas.js (con su
// título y su descripción para <head>) y en paginas.js (su componente).
export const GRUPOS = [
  {
    nombre: 'Empezar',
    paginas: [
      { ruta: '/docs', titulo: 'Qué es Cotejo' },
      { ruta: '/docs/primeros-pasos', titulo: 'Primeros pasos' },
    ],
  },
  {
    nombre: 'El board',
    paginas: [
      { ruta: '/docs/board', titulo: 'El board' },
      { ruta: '/docs/maestro', titulo: 'El maestro' },
    ],
  },
  {
    nombre: 'Agentes y modelos',
    paginas: [
      { ruta: '/docs/enrutador', titulo: 'El enrutador' },
      { ruta: '/docs/agentes', titulo: 'Agentes y modelos' },
    ],
  },
  {
    nombre: 'Contexto',
    paginas: [
      { ruta: '/docs/almacen', titulo: 'El almacén' },
      { ruta: '/docs/tokens', titulo: 'Ahorro de tokens' },
      { ruta: '/docs/fuentes', titulo: 'Fuentes' },
    ],
  },
  {
    nombre: 'Referencia',
    paginas: [
      { ruta: '/docs/cli', titulo: 'La CLI' },
      { ruta: '/docs/configuracion', titulo: 'Configuración' },
    ],
  },
]

export const PAGINAS_DOCS = GRUPOS.flatMap((g) => g.paginas)

// La página de antes y la de después de `ruta`, en el orden de la barra lateral.
export function vecinas(ruta) {
  const i = PAGINAS_DOCS.findIndex((p) => p.ruta === ruta)
  return { anterior: PAGINAS_DOCS[i - 1] ?? null, siguiente: PAGINAS_DOCS[i + 1] ?? null }
}
