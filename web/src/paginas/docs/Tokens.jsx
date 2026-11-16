import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { AHORRO, CONSULTA } from '../../config.js'

// Todas las cifras salen de config.js (CONSULTA y AHORRO): aquí no se escribe ninguna a mano.
const miles = (n) => Math.round(n).toLocaleString('de-DE')
const aprox = (n) => `~${miles(n)}`
const decimal = (n) => n.toLocaleString('de-DE', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const porcentaje = (n) => `${((n / CONSULTA.nota) * 100).toFixed(1)}%`

const secciones = [
  {
    id: 'consulta',
    titulo: 'Una consulta, comparada',
    hijos: (
      <>
        <p>
          Para saber qué falta, el agente no necesita leer la nota entera del proyecto. Cotejo le
          responde solo eso. Con las pendientes de un proyecto, la estimación es {aprox(CONSULTA.cli)}{' '}
          tokens contra {aprox(CONSULTA.nota)} de la nota entera.
        </p>
        <div
          className="tk-escala"
          role="img"
          aria-label={`Tokens por consulta: la nota entera, unos ${miles(CONSULTA.nota)}; cotejo tareas, unos ${miles(CONSULTA.cli)}`}
        >
          <div className="tk-escala__fila">
            <span className="tk-escala__nombre">La nota entera</span>
            <div className="tk-escala__barra" style={{ width: porcentaje(CONSULTA.nota) }} />
            <span className="tk-escala__cifra">{aprox(CONSULTA.nota)}</span>
          </div>
          <div className="tk-escala__fila">
            <span className="tk-escala__nombre">cotejo tareas</span>
            <div className="tk-escala__barra tk-escala__barra--cli" style={{ width: porcentaje(CONSULTA.cli) }} />
            <span className="tk-escala__cifra">{aprox(CONSULTA.cli)}</span>
          </div>
        </div>
        <p>
          Con las 101 tareas de un vault entero, son ~7.300 contra ~36.600. Hay tres tamaños para
          pedir, y conviene usar el más chico que sirva:
        </p>
        <Tabla
          etiqueta="Tamaños de consulta"
          cabeza={['Verbo', 'Para qué', 'Coste']}
          filas={[
            [<code key="a">cotejo estado</code>, 'Los conteos de siempre', '~80 tokens'],
            [<code key="b">cotejo tareas</code>, 'Cuáles faltan, con filtros', 'según el filtro'],
            ['La nota entera', 'Solo si hace falta de verdad el contexto', 'la más cara'],
          ]}
        />
      </>
    ),
  },
  {
    id: 'medidor',
    titulo: 'El medidor: cotejo ahorro',
    hijos: (
      <>
        <p>
          Una app que se justifica con un ahorro debería poder enseñarlo medido. Las dos mitades del
          número se miden: lo que costó es el tamaño de lo que la CLI devolvió (exactamente lo que
          el agente se lleva al contexto), y lo que habría costado es el tamaño de las notas que la
          fuente tuvo que leer para contestar.
        </p>
        <Codigo
          texto={'cotejo ahorro\n{"esquema": 1, "lecturas": 4, "devuelto": 37098, "leido": 730071,\n "razon": 19.7, "tokens_devueltos": 10305, "tokens_ahorrados": 192492,\n "caracteres_por_token": 3.6, "supuesto": "Lo medido son los caracteres que devolvió la CLI…"}'}
        />
        <Tabla
          etiqueta="Medición real en la máquina del autor"
          cabeza={['Dato', 'Valor']}
          filas={[
            ['Razón', <strong key="a">{decimal(AHORRO.razon)}×</strong>],
            ['Lecturas', miles(AHORRO.lecturas)],
            ['Caracteres leídos', miles(AHORRO.leido)],
            ['Caracteres devueltos', miles(AHORRO.devuelto)],
            ['Tokens ahorrados', `~${miles(Math.round(AHORRO.tokensAhorrados / 1000) * 1000)}`],
          ]}
        />
        <Aviso tipo="ojo">
          El supuesto: que sin Cotejo el agente habría leído las notas enteras. Es lo único que no
          se mide, así que viaja dentro del dato, en la clave <code>supuesto</code>, y sale escrito
          debajo del número en el board. Esa medición es de la máquina del autor; mídela en tu
          proyecto con <code>cotejo ahorro</code>.
        </Aviso>
        <p>
          Se cuenta en caracteres, que es lo que hay sin volver a tocar nada. Los tokens salen de
          dividir por una constante declarada, que viaja en la respuesta (
          <code>caracteres_por_token</code>). La <code>razon</code> no depende de ese divisor y es
          la cifra más defendible.
        </p>
      </>
    ),
  },
  {
    id: 'honesto',
    titulo: 'Cómo se mantiene honesto',
    hijos: (
      <>
        <ul>
          <li>
            <strong>Vive en su propio archivo</strong> (<code>ahorro.json</code>, en la carpeta de
            estado), con los totales acumulados y los de los últimos 30 días, y no en la bitácora:
            una línea por lectura encarecería justo el camino que el medidor dice abaratar.
          </li>
          <li>
            <strong>Contar no cuesta.</strong> Nada del medidor abre una nota: se le pregunta a la
            fuente cuánto pesaba lo que ya leyó.
          </li>
          <li>
            <strong>Puede dar menos de uno.</strong> Con notas chicas, el JSON que las describe pesa
            más que ellas, y entonces el board dice «Tokens de más». Un medidor que solo sabe
            felicitar es un cartel.
          </li>
          <li>
            <strong>Solo cuenta <code>tareas</code></strong>, el camino por el que un agente se
            entera.
          </li>
        </ul>
        <p>
          Una limitación conocida: <code>escanear</code> lee el vault entero aunque se pida{' '}
          <code>--proyecto</code>, así que con ese filtro la mitad cara cuenta notas que la
          respuesta no necesitaba, y el número sale inflado.
        </p>
        <p>
          En CotejoBoard sale bajo el tablero, en dos líneas en mono y plata: el total de tokens
          ahorrados y el supuesto. Sin ninguna lectura contada, el pie no sale.
        </p>
      </>
    ),
  },
]

export default function Tokens() {
  return (
    <Doc
      ruta="/docs/tokens"
      titulo="Ahorro de tokens."
      bajada={`Tu agente lee ${miles(CONSULTA.cli)} tokens, no ${miles(CONSULTA.nota)}: medido, y con su supuesto a la vista.`}
      secciones={secciones}
    />
  )
}
