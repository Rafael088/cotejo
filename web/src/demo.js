// La demo de la portada sin React ni navegador: un estado (las cartas del tablero, las líneas de la
// terminal y la leyenda), las acciones que lo cambian (`aplicar`, un reductor puro) y el guion con
// sus tiempos. components/Demo.jsx lo corre con temporizadores; el prerender usa `FOTO`, el guion
// ya aplicado, para que sin JavaScript se lea la historia entera y no un tablero vacío.

export const COLUMNAS = [
  ['pendiente', 'Pendiente'],
  ['haciendola', 'Haciéndola'],
  ['comprobar', 'Para comprobar'],
  ['finalizada', 'Finalizada'],
]

// Lo que cabe en la terminal: las líneas viejas se van por arriba.
export const LINEAS_MAX = 13
const MOTIVO = 'falta el mensaje de error'

export const INICIAL = {
  cartas: [
    { id: 'a1', texto: 'Registro con correo', modelo: 'sonnet', col: 'pendiente', estado: 'normal' },
    { id: 'b2', texto: 'Correo de bienvenida', modelo: 'opus', col: 'pendiente', estado: 'normal' },
    { id: 'c3', texto: 'Comprar el dominio', modelo: 'persona', col: 'pendiente', estado: 'normal' },
    { id: 'd4', texto: 'Página de inicio', modelo: 'haiku', col: 'finalizada', estado: 'hecha' },
  ],
  lineas: [],
  siguiente: 0,
  paso: 1,
  leyenda: 'Le pides trabajo a tu agente.',
  fin: false,
}

const linea = (clase, texto) => ({ t: 'linea', clase, texto })
const decir = (paso, leyenda) => ({ t: 'decir', paso, leyenda })

// Mueve una carta al final de otra columna, cambiándole lo que diga `cambios`.
function mover(estado, id, col, cambios = {}) {
  const carta = estado.cartas.find((c) => c.id === id)
  if (!carta) return estado
  const resto = estado.cartas.filter((c) => c.id !== id)
  return { ...estado, cartas: [...resto, { ...carta, ...cambios, col }] }
}

export function aplicar(estado, accion) {
  switch (accion.t) {
    case 'reiniciar':
      return INICIAL
    case 'linea': {
      const nueva = { n: estado.siguiente, clase: accion.clase, texto: accion.texto, animar: !!accion.animar }
      return { ...estado, siguiente: estado.siguiente + 1, lineas: [...estado.lineas, nueva].slice(-LINEAS_MAX) }
    }
    case 'decir':
      return { ...estado, paso: accion.paso, leyenda: accion.leyenda }
    case 'mover':
      return mover(estado, accion.id, accion.col)
    case 'entregar':
      return mover(estado, accion.id, 'comprobar', { estado: 'entregada', ev: accion.ev, motivo: undefined })
    case 'devolver': {
      const fuera = mover(estado, accion.id, 'pendiente', { estado: 'devuelta', ev: undefined, motivo: MOTIVO })
      return [decir(3, 'Devuelta con su motivo. El agente vuelve a ella.'), linea('cmd', `cotejo despachar ${accion.id}`)].reduce(aplicar, fuera)
    }
    case 'aprobar': {
      const hecha = mover(estado, accion.id, 'finalizada', { estado: 'hecha', ev: undefined })
      const quedan = hecha.cartas.some((c) => c.col === 'comprobar' || c.col === 'haciendola' || c.estado === 'devuelta')
      return quedan
        ? aplicar(hecha, decir(4, 'Una menos. Revisa la otra.'))
        : { ...aplicar(hecha, decir(4, 'Hecho. Porque lo revisaste tú.')), fin: true }
    }
    default:
      return estado
  }
}

// Lo que teclea quien usa el agente; la terminal lo escribe a TECLA ms por carácter.
export const PEDIDO = 'hazme dos tareas de mi-app'
export const TECLA = 38
const T0 = 500 + PEDIDO.length * TECLA

// [ms desde que empieza, acciones]. Los tiempos son los del diseño aprobado.
export const GUION = [
  [500, [linea('yo', PEDIDO)]],
  [T0 + 350, [linea('cmd', 'cotejo plan --proyecto mi-app')]],
  [T0 + 900, [linea('sal', 'a1 → sonnet · b2 → opus'), linea('sal', 'c3 → persona (no se despacha)'), decir(2, 'Cotejo reparte cada tarea al modelo que le toca.')]],
  [T0 + 1700, [linea('cmd', 'cotejo despachar a1'), { t: 'mover', id: 'a1', col: 'haciendola' }]],
  [T0 + 2300, [linea('cmd', 'cotejo despachar b2'), { t: 'mover', id: 'b2', col: 'haciendola' }]],
  [T0 + 3900, [linea('cmd', 'cotejo entregar a1 --prueba "npm test"'), decir(3, 'El agente entrega con pruebas.')]],
  [T0 + 4500, [linea('ok', '12 pruebas · ok · por-validar'), { t: 'entregar', id: 'a1', ev: 'commit 3f2c1a · 12 pruebas ok' }]],
  [T0 + 5600, [linea('cmd', 'cotejo entregar b2 --prueba "npm test"')]],
  [T0 + 6200, [linea('ok', '4 pruebas · ok · por-validar'), { t: 'entregar', id: 'b2', ev: 'commit 1a4b9c · 4 pruebas ok' }]],
  [T0 + 6900, [linea('aviso', 'Listo. Te tocan dos por revisar.'), decir(4, 'Tu turno: apruébala o devuélvela.')]],
]

// Lo que pasa después de devolver una carta: el agente lee el motivo y la vuelve a entregar.
export const tras_devolver = (id) => [
  [900, [linea('sal', `lee el motivo: ${MOTIVO}`), { t: 'mover', id, col: 'haciendola' }]],
  [2600, [linea('cmd', `cotejo entregar ${id} --prueba "npm test"`)]],
  [3200, [linea('ok', '14 pruebas · ok · por-validar'), { t: 'entregar', id, ev: 'commit 8d41e0 · 14 pruebas ok' }, decir(3, 'Tu turno otra vez: revísala.')]],
]

// El guion entero ya aplicado: lo que sale en el HTML y lo que ve quien pide menos movimiento.
export const FOTO = GUION.flatMap(([, acciones]) => acciones).reduce(aplicar, INICIAL)
