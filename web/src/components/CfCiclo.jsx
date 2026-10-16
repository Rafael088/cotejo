import { useState } from 'react'
import { ARBOL, VERBOS } from '../comofunciona.js'

// /comofunciona · Programo: los seis verbos del ciclo con su salida real (src/comofunciona.js),
// el árbol de .cotejo/ y lo que no se cierra sin una persona.

// Las claves en tenue y lo marcado con ⟦…⟧ en verde; el resto, tal cual. Sin innerHTML.
function pintar(texto) {
  return texto.split(/(⟦[^⟧]*⟧|"[^"\n]+"(?=:))/).map((trozo, i) => {
    if (trozo.startsWith('⟦'))
      return (
        <span key={i} className="cf-consola__ok">
          {trozo.slice(1, -1)}
        </span>
      )
    if (i % 2)
      return (
        <span key={i} className="cf-consola__k">
          {trozo}
        </span>
      )
    return trozo
  })
}

function Salida({ comando, salida }) {
  return (
    <>
      <span className="cf-consola__p">$</span> <span className="cf-consola__cmd">{comando}</span>
      {'\n'}
      {pintar(salida)}
      {'\n'}
    </>
  )
}

export default function CfCiclo() {
  const [sel, setSel] = useState(0)
  const v = VERBOS[sel]

  return (
    <>
      <div className="cf-ciclo">
        <div className="cf-verbos" role="tablist" aria-label="El ciclo">
          {VERBOS.map((otro, i) => (
            <button
              key={otro.verbo}
              className="cf-verbo"
              role="tab"
              type="button"
              aria-selected={i === sel}
              onClick={() => setSel(i)}
            >
              <span className="cf-verbo__c">{otro.verbo}</span>
              <span className="cf-verbo__d">{otro.que}</span>
            </button>
          ))}
        </div>
        <div className="cf-consola">
          <div className="cf-consola__barra">
            <span>terminal</span>
            <span>salida abreviada</span>
          </div>
          <pre aria-live="polite" key={sel}>
            <Salida comando={v.comando} salida={v.salida} />
          </pre>
        </div>
      </div>

      <div className="cf-dos">
        <div className="cf-panel">
          <h3 className="titulo-3">El proyecto vive en tu repo.</h3>
          <p className="parrafo parrafo--tenue">Un archivo por entrada. Viaja con el código.</p>
          <pre className="cf-arbol">
            <span className="cf-arbol__d">mi-app/</span>
            {'\n└─ '}
            <span className="cf-arbol__d">.cotejo/</span>
            {ARBOL.map((a, i) => `\n   ${i === ARBOL.length - 1 ? '└─' : '├─'} ${a}`).join('')}
          </pre>
        </div>
        <div className="cf-panel">
          <h3 className="titulo-3">Nada se cierra sin ti.</h3>
          <p className="parrafo parrafo--tenue">
            No existe un verbo para finalizar. Las decisiones que propone un agente se aceptan en el board. Las tareas
            de persona no se despachan.
          </p>
          <div className="demo-chips">
            <span className="cf-chip">JSON en todos los verbos</span>
            <span className="cf-chip">errores con el siguiente paso</span>
            <span className="cf-chip">MCP</span>
          </div>
        </div>
      </div>
    </>
  )
}
