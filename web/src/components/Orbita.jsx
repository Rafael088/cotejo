import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { siObsidian, siNotion } from '../iconos-apps.js'
import { Marca } from './Logo.jsx'

// Repo, Obsidian (importar) y Notion (importar) funcionan hoy. El puesto que queda vacío está así a propósito:
// se llena escribiendo un adaptador, y no se pinta el logo de ninguna app que no funcione.
const FUENTES = [
  {
    id: 'repo',
    nombre: 'Tu repo',
    estado: 'Por defecto — sin vault ni cuentas',
    texto: 'Un repo de git es un proyecto: su contexto, decisiones, arquitectura y tareas viven en la carpeta .cotejo/, en Markdown, junto al código. Lo crea cotejo init, o tu agente por ti.',
    orden: 'cotejo init',
  },
  {
    id: 'obsidian',
    nombre: 'Obsidian',
    estado: 'Para importar un proyecto que ya tienes',
    icono: siObsidian,
    texto: 'Si ya llevas un proyecto en un vault, lo traes a su .cotejo/ de una vez. Antes de escribir comprueba que la línea siga como la leyó: no pisa lo que escribiste tú.',
    orden: 'cotejo importar obsidian',
  },
  {
    id: 'notion',
    nombre: 'Notion',
    estado: 'Para importar, con el adaptador cotejo-notion',
    icono: siNotion,
    texto: 'Cada página de una base es una tarea. Traes la base entera a tu repo; el token nunca va en la config.',
    orden: 'cotejo importar notion',
  },
  {
    id: 'tu-app',
    nombre: 'Tu app',
    estado: 'Escribe su adaptador',
    texto: 'Logseq, Todoist, Linear o lo que uses: un programa aparte, en cualquier lenguaje, que Cotejo llama por subproceso y en JSON. La plantilla trae el contrato entero en 200 líneas.',
    orden: 'cotejo fuentes agregar mi-app --comando cotejo-mi-app',
  },
]

const AGENTES = ['Claude Code', 'Codex', 'Gemini CLI', 'opencode']

// Puestos del anillo de fuentes: repo, Obsidian, Notion y un vacío.
const ANILLO = [
  { id: 'repo', angulo: -90 },
  { id: 'obsidian', angulo: 30 },
  { id: 'notion', angulo: 150 },
  { id: 'tu-app', angulo: 210, vacio: true },
]

const pos = (angulo, radio) => {
  const r = (angulo * Math.PI) / 180
  return { left: `${50 + radio * Math.cos(r)}%`, top: `${50 + radio * Math.sin(r)}%` }
}

function Logo({ icono, tam = 26 }) {
  return (
    <svg viewBox="0 0 24 24" width={tam} height={tam} aria-hidden="true">
      <path d={icono.path} fill="currentColor" />
    </svg>
  )
}

export default function Orbita() {
  const [elegida, setElegida] = useState('repo')
  const fuente = FUENTES.find((f) => f.id === elegida)
  const giro = { duration: 90, ease: 'linear', repeat: Infinity }

  return (
    <section className="seccion orbita" id="fuentes" aria-labelledby="orbita-titulo">
      <div className="orbita__grid">
        <div className="orbita__escenario">
          <div className="orbita__anillo orbita__anillo--fuera" aria-hidden="true" />
          <div className="orbita__anillo orbita__anillo--dentro" aria-hidden="true" />

          {/* Anillo de fuera: los agentes, que le hablan a Cotejo. Gira al revés. */}
          <motion.div className="orbita__giro orbita__giro--agentes" animate={{ rotate: -360 }} transition={giro} aria-hidden="true">
            {AGENTES.map((a, i) => (
              <div key={a} className="orbita__puesto" style={pos(i * 90 + 45, 47)}>
                <motion.span className="orbita__agente" animate={{ rotate: 360 }} transition={giro}>
                  {a}
                </motion.span>
              </div>
            ))}
          </motion.div>

          {/* Anillo de dentro: las fuentes de donde lee. */}
          <motion.div className="orbita__giro" animate={{ rotate: 360 }} transition={giro}>
            <svg className="orbita__radios" viewBox="0 0 100 100" aria-hidden="true">
              {ANILLO.map((p) => {
                const r = (p.angulo * Math.PI) / 180
                return (
                  <line
                    key={p.clave || p.id}
                    x1="50" y1="50"
                    x2={50 + 31 * Math.cos(r)} y2={50 + 31 * Math.sin(r)}
                    className={`orbita__radio ${!p.vacio && p.id === elegida ? 'es-activo' : ''} ${p.vacio ? 'orbita__radio--vacio' : ''}`}
                  />
                )
              })}
            </svg>
            {ANILLO.map((p) => {
              const f = FUENTES.find((x) => x.id === p.id)
              const activo = p.id === elegida && (!p.vacio || !p.clave)
              return (
                <div key={p.clave || p.id} className="orbita__puesto" style={pos(p.angulo, 31)}>
                  <motion.button
                    type="button"
                    className={`orbita__nodo ${p.vacio ? 'orbita__nodo--vacio' : ''} ${activo ? 'es-activo' : ''}`}
                    animate={{ rotate: -360 }}
                    transition={giro}
                    onClick={() => setElegida(p.id)}
                    onMouseEnter={() => setElegida(p.id)}
                    onFocus={() => setElegida(p.id)}
                    aria-pressed={activo}
                    aria-label={f.nombre}
                    tabIndex={p.clave ? -1 : 0}
                  >
                    {f.icono ? <Logo icono={f.icono} /> : <span className="orbita__vacio">{p.vacio ? 'tu app' : 'git'}</span>}
                  </motion.button>
                </div>
              )
            })}
          </motion.div>

          <div className="orbita__centro">
            <Marca tam={64} />
          </div>
        </div>

        <div className="orbita__texto">
          <h2 id="orbita-titulo" className="titulo-2">Empieza en un repo. Trae lo que ya tienes.</h2>
          <p className="parrafo">
            Cada proyecto vive en su propio repo, dentro de .cotejo/, y tus agentes le hablan a
            Cotejo. Si ya tenías el proyecto en Obsidian o en Notion, lo importas; después
            trabajas en el repo.
          </p>

          <div className="orbita__fuentes" role="tablist" aria-label="Fuentes">
            {FUENTES.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={f.id === elegida}
                className="orbita__fuente"
                onClick={() => setElegida(f.id)}
              >
                {f.nombre}
              </button>
            ))}
          </div>

          <div className="orbita__ficha" role="tabpanel" aria-live="polite">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={fuente.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              >
                <p className="orbita__estado">{fuente.estado}</p>
                <p className="parrafo">{fuente.texto}</p>
                {fuente.orden && <code className="orbita__orden">{fuente.orden}</code>}
              </motion.div>
            </AnimatePresence>
          </div>

          <p className="orbita__agentes-texto">
            Y del otro lado, tus agentes: el instalador les escribe el protocolo a{' '}
            <strong>Claude Code</strong>, <strong>Codex</strong>, <strong>Gemini CLI</strong> y{' '}
            <strong>opencode</strong> para que sepan usar Cotejo desde la primera sesión.
          </p>
        </div>
      </div>
    </section>
  )
}
