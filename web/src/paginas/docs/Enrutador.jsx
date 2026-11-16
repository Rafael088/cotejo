import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { TAREAS_MEDIDAS } from '../../config.js'
import { enlace } from '../../enlace.js'

const secciones = [
  {
    id: 'niveles',
    titulo: 'Niveles',
    hijos: (
      <>
        <p>
          Cotejo resuelve qué hay que hacer; el enrutador resuelve quién lo hace: los modelos
          configurados y una persona.
        </p>
        <Tabla
          etiqueta="Niveles del enrutador"
          cabeza={['Nivel', 'Quién', 'Para qué']}
          filas={[
            ['n0', <strong key="a">Una persona</strong>, 'Comprar, firmar, llamar a alguien, abrir una cuenta, tocar algo físico, decidir por gusto'],
            ['n1', <code key="b">claude-haiku-5-5</code>, 'Trabajo mecánico y acotado'],
            ['n2', <code key="c">claude-sonnet-5-5</code>, 'El trabajo normal de código. Es el defecto'],
            ['n3', <code key="d">claude-opus-5-5</code>, 'Arquitectura, contratos, lo que cruza varios archivos'],
          ]}
        />
        <p>
          <code>cotejo modelos</code> lista el catálogo de niveles y modelos registrados.
        </p>
      </>
    ),
  },
  {
    id: 'veto',
    titulo: 'El veto humano',
    hijos: (
      <>
        <p>
          Al medir tareas reales apareció lo más útil del enrutador: {TAREAS_MEDIDAS.persona} de
          las {TAREAS_MEDIDAS.total} tareas pendientes no eran para ningún modelo («Comprar el
          dominio», «Que un abogado revise los textos»). Un enrutador que solo elige entre modelos
          las manda todas a uno, y el modelo las intenta y las entrega a medias: una entrega falsa
          que alguien tiene que revisar y devolver.
        </p>
        <Aviso tipo="ojo">
          Por eso <code>humano</code> es un destino de primera clase, con su veto, y no hay bandera
          para forzarlo.
        </Aviso>
      </>
    ),
  },
  {
    id: 'orden',
    titulo: 'Orden de decisión',
    hijos: (
      <>
        <p>De lo más explícito a lo más adivinado. Cada escalón dice por qué ganó.</p>
        <Tabla
          etiqueta="Orden de decisión"
          cabeza={['#', 'Escalón', 'Qué significa']}
          filas={[
            ['1', <code key="a">--modelo</code>, 'Una persona lo está pidiendo ahora mismo (confianza alta)'],
            ['2', 'Asignación', <>Ya estaba escrito en la nota (<code>#agente/opus</code>) (confianza alta)</>],
            ['3', 'Veto humano', 'Nadie lo asignó y el texto dice que no es para un modelo'],
            ['4', 'Dificultad', <>Una persona etiquetó el tamaño (<code>#facil</code>, <code>#medio</code>, <code>#dificil</code>)</>],
            ['5', 'Reglas', 'Expresiones regulares sobre el texto, gratis'],
            ['6', 'Defecto', 'Sonnet'],
          ]}
        />
        <p>
          Dos decisiones sostienen ese orden. El veto va antes que la dificultad: <code>#facil</code>{' '}
          no dice «que lo haga un modelo», dice «es corto». Y ante la duda se escala, nunca se
          abarata: un ruteo caro equivocado cuesta unos centavos; uno barato equivocado arruina la
          tarea y hay que rehacerla.
        </p>
        <p>
          Las reglas proponen, no autorizan: si nadie asignó el modelo, <code>despachar</code> se
          niega con código <code>6</code> y enseña la propuesta; la respuesta se escribe en la nota
          con <code>asignar</code>. <code>--auto</code> es la excepción explícita.{' '}
          <code>cotejo evaluar</code> mide las reglas contra tareas reales etiquetadas a mano.
        </p>
      </>
    ),
  },
  {
    id: 'despachar',
    titulo: 'despachar',
    hijos: (
      <>
        <p>
          Toma la tarea a nombre de su modelo. Si es de un repo de git, le crea por defecto su
          propio worktree, fuera del repo, con una rama <code>cotejo/&lt;id&gt;</code>: ahí trabaja
          y commitea el agente, y de ahí saca <code>entregar</code> la evidencia, sin que dos tareas
          del mismo repo se pisen.
        </p>
        <Codigo
          texto={'cotejo plan --proyecto Cotejo --solo-despachables   # qué modelo recibiría cada pendiente\ncotejo decidir --tarea <id>                       # a quién le toca esa, y por qué\ncotejo despachar <id>                             # tomarla a nombre de ese modelo\ncotejo worktrees [--limpiar]                      # dónde quedó cada uno; con --limpiar, retira los que sobran'}
        />
        <p>
          <code>--sin-aislar</code> (o <code>enrutador.worktrees.aislar: false</code>) desactiva el
          worktree, para una tarea que no toca código. <code>--limpiar</code> nunca borra una rama ni
          algo sin commitear.
        </p>
        <h3>Motores</h3>
        <Tabla
          etiqueta="Motores de despachar"
          cabeza={['Motor', 'Qué hace']}
          filas={[
            [<code key="a">agente</code>, 'El de por defecto. No lanza nada: toma la tarea y te devuelve el encargo para que lo hagas tú o se lo pases a un subagente con ese modelo.'],
            [<code key="b">sesion</code>, <>Abre una instancia de verdad (<code>claude --bg --model</code>), que se dirige con <code>claude attach</code>. Solo sabe abrir Claude Code y lo dice antes de tomar nada.</>],
            [<code key="c">headless</code>, 'Para lo desatendido, y hay que pedirlo. Lanza el cliente que ejecuta el modelo según el catálogo.'],
          ]}
        />
        <p>
          Si el cliente no está instalado, <code>despachar</code> se niega sin tomar la tarea, en
          vez de dejarla en Haciéndola a nombre de un modelo que nunca empezó. Con qué cliente corre
          cada modelo está en <a href={enlace('/docs/agentes')}>Agentes y modelos</a>.
        </p>
      </>
    ),
  },
  {
    id: 'revisar',
    titulo: 'revisar',
    hijos: (
      <>
        <p>
          <code>plan</code> dice qué hay por repartir; <code>revisar</code> dice si repartirlo
          sirvió. Cruza la bitácora de despachos con dónde está hoy cada tarea.
        </p>
        <Codigo texto="cotejo revisar --dias 3     # lo que lleva 3 días tomado y nadie movió" />
        <Tabla
          etiqueta="Lo que dice revisar"
          cabeza={['Clave', 'Qué es']}
          filas={[
            [<code key="a">colgada</code>, 'Se tomó, nadie la entregó ni la devolvió, y ya lleva días. En el board, una colgada y una que alguien hace ahora mismo son la misma carta.'],
            [<code key="b">devuelta</code>, 'Volvió a Pendiente, y viene con el motivo: el dato que dice si el ruteo se equivocó.'],
            [<code key="c">perdida</code>, 'El id dejó de resolver porque alguien editó la nota, o la tarea sigue en curso pero el proceso headless que la hacía ya no existe (un OOM, un reinicio).'],
            [<code key="d">en_curso_sin_despacho</code>, 'Tareas que alguien puso en curso sin pasar por aquí. No es un error, pero es la diferencia entre «reparte el trabajo» y «reparte parte del trabajo».'],
          ]}
        />
        <p>
          El resumen trae también <code>rechazos</code>: cuántas veces el enrutador se negó a
          repartir, por veto humano o por falta de modelo. Es la cifra que cuenta cuántas entregas
          falsas se evitaron.
        </p>
        <Aviso>
          Lo que el enrutador no hace es entregar. Reparte trabajo; quien lo hizo dice qué hizo con{' '}
          <code>entregar</code>, y quien lo comprueba es una persona.
        </Aviso>
      </>
    ),
  },
  {
    id: 'capacidad',
    titulo: 'capacidad',
    hijos: (
      <>
        <p>
          Antes de repartir varias tareas en paralelo, <code>capacidad</code> dice cuántas caben
          ahora en la máquina donde corre, para no llevarla al OOM.
        </p>
        <Codigo texto="cotejo capacidad --proyecto Cotejo   # caben, qué lo limita, y cuáles ahora y cuáles esperar" />
        <p>
          Mide al preguntar: memoria disponible, la parte del swap libre que cuenta, CPUs y carga, y
          los agentes que ya están en marcha. Divide lo que queda, menos una reserva, entre lo que
          cuesta un agente. Ese costo es un supuesto (1500 MB) que los agentes en marcha solo pueden
          subir, así que medirlo nunca reparte de más. Se cambia en <code>enrutador.capacidad</code>{' '}
          (<code>mb_por_agente</code>, <code>reserva_mb</code>, <code>fraccion_swap</code>,{' '}
          <code>cpu_por_agente</code>, <code>maximo</code>). No escribe nada.
        </p>
      </>
    ),
  },
]

export default function Enrutador() {
  return (
    <Doc
      ruta="/docs/enrutador"
      titulo="El enrutador."
      bajada="Decide a quién le toca cada tarea, y por qué. Cuando no es para ningún modelo, dice que es para ti."
      secciones={secciones}
    />
  )
}
