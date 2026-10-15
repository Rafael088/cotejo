import { useEffect, useReducer } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Marca } from './Logo.jsx'
import Icono from './Icono.jsx'

// CotejoBoard dibujado en HTML para el fondo del hero. Las tareas son de ejemplo.
const COLUMNAS = [
  { id: 'pendiente', nombre: 'Pendiente' },
  { id: 'haciendola', nombre: 'Haciéndola' },
  { id: 'comprobar', nombre: 'Para comprobar' },
  { id: 'finalizada', nombre: 'Finalizada' },
]

const PROYECTOS = [
  { nombre: 'Web de Cotejo', pendientes: 9, esperando: 2, activo: true },
  { nombre: 'Canal de YouTube', pendientes: 6 },
  { nombre: 'Tienda', pendientes: 12, esperando: 1 },
  { nombre: 'Tesis', pendientes: 4 },
  { nombre: 'Inbox', pendientes: 3 },
]

const POOL = [
  'Escribir la sección de preguntas frecuentes',
  'Medir el peso de las fuentes y servirlas en woff2',
  'Revisar el contraste del modo claro',
  'Añadir el enlace de donaciones al pie',
  'Probar la instalación en una máquina limpia',
  'Grabar el clip del board para el directo',
]

const AGENTES = ['opus', 'sonnet', 'haiku', 'kimi']
const DIF = ['facil', 'medio', 'dificil']

let siguienteId = 100
const carta = (texto, columna, extra = {}) => ({ id: siguienteId++, texto, columna, ...extra })

const INICIAL = [
  carta('Comprar el dominio y apuntarlo a GitHub Pages', 'pendiente', { dif: 'facil', agente: 'persona' }),
  carta('Servir install.sh e install.ps1 desde el dominio', 'pendiente', { dif: 'medio' }),
  carta('Escribir el texto de la sección de fuentes', 'pendiente', { dif: 'facil' }),
  carta('Componente del comando con botón de copiar', 'haciendola', { agente: 'sonnet', dif: 'facil' }),
  carta('Animación de la órbita de apps compatibles', 'haciendola', { agente: 'opus', dif: 'medio' }),
  carta('Favicon y apple-touch-icon desde el kit de marca', 'comprobar', { agente: 'haiku', dif: 'facil', evidencia: 'commit 3f2c1a0 · public/favicon.svg' }),
  carta('Pestañas Linux / Windows en el hero', 'comprobar', { agente: 'sonnet', dif: 'facil', evidencia: 'commit 8d41e2b · 4 pruebas OK' }),
  carta('Metadatos para compartir el enlace', 'finalizada', { agente: 'haiku', dif: 'facil' }),
  carta('Tokens de color del tema oscuro', 'finalizada', { agente: 'opus', dif: 'medio' }),
]

const PASOS = ['tomar', 'entregar', 'comprobar']

function reducir({ cartas, paso, pool }) {
  const tipo = PASOS[paso % PASOS.length]
  let nuevas = [...cartas]
  let nuevoPool = pool
  const mover = (desde, hacia, extra = {}) => {
    const i = nuevas.findIndex((c) => c.columna === desde)
    if (i < 0) return
    const [c] = nuevas.splice(i, 1)
    nuevas.push({ ...c, ...extra, columna: hacia })
  }
  if (tipo === 'tomar') {
    mover('pendiente', 'haciendola', { agente: AGENTES[paso % AGENTES.length] })
  } else if (tipo === 'entregar') {
    mover('haciendola', 'comprobar', { evidencia: `commit ${(0x1a2b3c + paso * 7919).toString(16).slice(0, 7)} · pruebas OK` })
  } else {
    mover('comprobar', 'finalizada')
    // Lo más viejo de Finalizada se va, y entra trabajo nuevo a Pendiente.
    const fin = nuevas.filter((c) => c.columna === 'finalizada')
    if (fin.length > 3) {
      nuevas = nuevas.filter((c) => c.id !== fin[0].id)
      nuevas.push(carta(nuevoPool[0], 'pendiente', { dif: DIF[paso % DIF.length] }))
      nuevoPool = [...nuevoPool.slice(1), nuevoPool[0]]
    }
  }
  return { cartas: nuevas, paso: paso + 1, pool: nuevoPool }
}

function Carta({ c }) {
  const espera = c.columna === 'comprobar'
  return (
    <motion.div
      className={`t-carta ${espera ? 't-carta--espera' : ''} ${c.columna === 'finalizada' ? 't-carta--hecha' : ''}`}
      initial={{ opacity: 0, height: 0, y: -8 }}
      animate={{ opacity: 1, height: 'auto', y: 0 }}
      exit={{ opacity: 0, height: 0, y: 8 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="t-carta__cuerpo">
        <div className="t-carta__fila">
          <span className="t-carta__texto">{c.texto}</span>
          <Icono nombre="mas" tam={14} className="t-carta__menu" />
        </div>
        {espera && c.evidencia && <span className="t-carta__evidencia">{c.evidencia}</span>}
        <div className="t-carta__chips">
          {c.agente && <span className="t-chip t-chip--borde">{c.agente}</span>}
          {c.dif && <span className="t-chip">#{c.dif}</span>}
        </div>
      </div>
    </motion.div>
  )
}

export default function Tablero() {
  const reducido = useReducedMotion()
  const [estado, avanzar] = useReducer(reducir, { cartas: INICIAL, paso: 0, pool: POOL })

  useEffect(() => {
    if (reducido) return
    const t = setInterval(avanzar, 2400)
    return () => clearInterval(t)
  }, [reducido])

  const esperando = estado.cartas.filter((c) => c.columna === 'comprobar').length

  return (
    <div className="tablero">
      <div className="tablero__cabecera">
        <Marca tam={22} />
        <div className="tablero__titulo">
          <span className="tablero__nombre">CotejoBoard</span>
          <span className="tablero__aviso">{esperando} esperando que las compruebes · Web de Cotejo</span>
        </div>
        <span className="tablero__buscar"><Icono nombre="buscar" tam={14} /> Buscar tareas <kbd>Ctrl F</kbd></span>
      </div>
      <div className="tablero__cuerpo">
        <aside className="tablero__lateral">
          <span className="tablero__rotulo">PROYECTOS</span>
          {PROYECTOS.map((p) => (
            <div key={p.nombre} className={`tablero__proyecto ${p.activo ? 'es-activo' : ''}`}>
              <span>{p.nombre}</span>
              {p.esperando ? <span className="tablero__pastilla">{p.activo ? esperando : p.esperando}</span> : null}
              <span className="tablero__conteo">{p.pendientes}</span>
            </div>
          ))}
          <div className="tablero__ahorro">
            <span>~192.000 tokens ahorrados</span>
            <span>19,7× menos que leer las notas</span>
          </div>
        </aside>
        <div className="tablero__columnas">
          {COLUMNAS.map((col) => {
            const cartas = estado.cartas.filter((c) => c.columna === col.id)
            return (
              <div key={col.id} className={`t-columna t-columna--${col.id}`}>
                <div className="t-columna__cabeza">
                  <span className="t-columna__nombre">{col.nombre}</span>
                  <span className="t-columna__cuenta">{cartas.length}</span>
                </div>
                <div className="t-columna__cartas">
                  <AnimatePresence initial={false}>
                    {cartas.map((c) => <Carta key={c.id} c={c} />)}
                  </AnimatePresence>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
