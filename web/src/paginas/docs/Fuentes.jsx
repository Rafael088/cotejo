import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { enlace } from '../../enlace.js'

const secciones = [
  {
    id: 'repo',
    titulo: 'El repo, por defecto',
    hijos: (
      <>
        <p>
          Todo lo que Cotejo hace con una tarea pasa por una fuente: listarla, tomarla, entregarla,
          marcarla. La que se usa si no dices otra cosa es el repo: sin vault ni adaptador, un repo de
          git es un proyecto, y sus tareas viven en <code>&lt;repo&gt;/.cotejo/tareas.md</code>, una
          línea cada una:
        </p>
        <Codigo texto="- [ ] texto #medio #agente/x ^cotejo-id" copiar={false} />
        <Codigo texto={'cd /ruta/al/repo\ncotejo init               # crea el esqueleto .cotejo/ y registra el repo\ncotejo fuentes usar repo   # la activa, si init no lo hizo'} />
        <p>
          <code>init</code> activa «repo» solo si la fuente activa no funciona, y deja en paz la que
          sí. Qué repos cuentan lo dice la config de la fuente: una lista (<code>repos</code>) o una
          carpeta (<code>raiz</code>) cuyos hijos directos tengan <code>.cotejo/tareas.md</code>.
        </p>
        <Codigo titulo="config.json" texto={'{ "fuente": "repo", "fuentes": { "repo": { "repos": ["/ruta/a/uno", "/ruta/a/otro"], "raiz": "/ruta/con/varios" } } }'} />
        <p>Funciona igual en Linux y en Windows.</p>
      </>
    ),
  },
  {
    id: 'importar',
    titulo: 'Traer un proyecto que ya existe',
    hijos: (
      <>
        <p>
          Obsidian y Notion no son el sitio donde se trabaja a diario: son la puerta de entrada.
          Traen un proyecto entero a su <code>.cotejo/</code>, y desde ahí se trabaja con el repo.
        </p>
        <Codigo
          texto={'cotejo importar obsidian Cotejo --detalle        # qué saldría de la nota; es un ensayo\ncotejo importar notion Cotejo --destino <carpeta>    # igual, desde una base de Notion\n    [--aplicar]                                      # con esto, se crean de verdad'}
        />
        <Tabla
          etiqueta="Qué hace cada importación"
          cabeza={['Verbo', 'Qué hace']}
          filas={[
            [
              <code key="a">importar obsidian</code>,
              'Localiza la nota del proyecto, sus subnotas y los adjuntos que enlazan, y reparte cada sección a su tipo: decisiones y problemas, aprendizajes, bitácora, tareas, y objetivo y stack a proyecto.md. Lo que no encaja sale en sin_clasificar, con su motivo.',
            ],
            [
              <code key="b">importar notion</code>,
              'Más modesto: trae las tareas por el adaptador que ya tengas registrado y cada página de la base como una referencia con resumen pendiente.',
            ],
            [
              <code key="c">importar plan</code>,
              'Convierte un plan.md en tareas, desde sus casillas o sus encabezados de paso, y propone dificultad y modelo igual que decidir.',
            ],
          ]}
        />
        <p>
          Todas son un ensayo por defecto: nunca escriben sin <code>--aplicar</code>. Con{' '}
          <code>--aplicar</code>, importar obsidian escribe en el <code>.cotejo/</code> del repo (y
          le hace <code>git init</code> si <code>--destino</code> no era un repo): las decisiones
          como aceptadas con <code>autor: importado</code>, los adjuntos copiados a{' '}
          <code>recursos/</code>, y crea la tarea «Revisar lo importado». No hace commit y no toca la
          nota del vault. Repetirlo no duplica nada, y se niega sin escribir si el repo ya tiene
          otras tareas.
        </p>
        <Aviso>
          Quitar el proyecto de <code>migrados</code> de la fuente obsidian lo deshace.{' '}
          <code>importar notion</code> no marca el proyecto como migrado: mientras no cambies de
          fuente, el mismo proyecto puede estar en Notion y en su <code>.cotejo/</code>.
        </Aviso>
      </>
    ),
  },
  {
    id: 'obsidian',
    titulo: 'Obsidian',
    hijos: (
      <>
        <p>
          Viene incluida. Quien ya usaba Obsidian sigue en Obsidian al actualizar, y las tareas
          viven en las notas del vault.
        </p>
        <Codigo titulo="config.json" texto={'{ "fuente": "obsidian", "fuentes": { "obsidian": { "vault": "/ruta/al/vault", "carpeta_proyectos": "01-Proyectos" } } }'} />
        <p>
          Con la fuente obsidian activa, los proyectos de <code>migrados</code> se leen de su repo y
          todos los demás siguen leyéndose de las notas, los dos a la vez y bajo el mismo{' '}
          <code>--proyecto</code>. Cada proyecto cuenta una sola vez, del lado que diga{' '}
          <code>migrados</code>. Las carpetas sueltas (Inbox, Diario) vienen apagadas; se encienden
          con <code>carpetas_sueltas</code>.
        </p>
      </>
    ),
  },
  {
    id: 'notion',
    titulo: 'Notion',
    hijos: (
      <>
        <p>
          Es el primer adaptador, y se instala como <code>cotejo-notion</code>. Cada página de la
          base es una tarea.
        </p>
        <Codigo
          texto={'export NOTION_TOKEN=secret_...          # el de una integración interna\ncotejo fuentes info notion\ncotejo fuentes agregar notion --comando cotejo-notion --param database_id=<los 32 caracteres de la URL>\ncotejo fuentes probar notion         # la conecta y la lee; no escribe ni la activa\ncotejo fuentes usar notion           # la activa, solo si probar pasa\ncotejo doctor'}
        />
        <p>
          La base hay que compartirla con la integración (… → Conexiones), o Notion contesta que no
          existe. El proyecto sale de una propiedad «Proyecto» o, sin ella, es la base entera; el
          estado, de «Estado»; también se leen «Agente», «Dificultad» y el checkbox «Done».
        </p>
        <Aviso tipo="ojo">
          El token nunca va en la config. Se lee de la variable que diga <code>token_env</code> (por
          defecto <code>NOTION_TOKEN</code>) o del archivo <code>~/.config/cotejo/notion.token</code>,
          con permisos 600. <code>fuentes agregar</code> y <code>config validar</code> se niegan a
          guardar algo que parezca un secreto.
        </Aviso>
        <p>
          Con Notion el board no se recarga solo al editar allí: <code>Ctrl+R</code>, y la barra por
          su cuenta cada pocos minutos.
        </p>
      </>
    ),
  },
  {
    id: 'cambiar',
    titulo: 'Cambiar de fuente',
    hijos: (
      <>
        <p>
          Cambiar de fuente es un comando. La app vigila la config y reabre la fuente sola, así que
          el board y la barra cambian sin reiniciar nada.
        </p>
        <Tabla
          etiqueta="Verbos de fuentes"
          cabeza={['Verbo', 'Qué hace']}
          filas={[
            [<code key="a">cotejo fuentes</code>, 'Las que hay, cuál está activa y qué les falta, sin conectarse a nada.'],
            [<code key="b">cotejo fuentes info &lt;nombre&gt;</code>, 'Qué parámetros pide y cómo se registra.'],
            [<code key="c">cotejo fuentes probar &lt;nombre&gt;</code>, 'La conecta y la lee. No escribe nada.'],
            [<code key="d">cotejo fuentes usar &lt;nombre&gt;</code>, 'La activa. Se niega si probar no pasa.'],
            [<code key="e">cotejo fuentes agregar &lt;nombre&gt; --comando &lt;cmd&gt; --param k=v</code>, 'Registra un adaptador. No lo activa.'],
            [<code key="f">cotejo fuentes quitar &lt;nombre&gt;</code>, 'Lo desregistra. No borra nada en la app de fuera.'],
          ]}
        />
      </>
    ),
  },
  {
    id: 'adaptadores',
    titulo: 'Conectar otra app',
    hijos: (
      <>
        <p>
          Hoy hay un adaptador hecho, el de Notion. Cualquier otra app se conecta escribiendo uno:
          un programa aparte al que Cotejo le habla por subproceso y en JSON, en cualquier lenguaje.
          Se parte de <code>extras/plantilla/cotejo_plantilla.py</code>, el contrato entero en unas
          200 líneas. Hay que escribir cuatro métodos: <code>escanear</code>, <code>marcar</code>,{' '}
          <code>poner_estado</code> y <code>poner_agente</code>. <code>crear</code> es opcional.
        </p>
        <Tabla
          etiqueta="Contrato de un adaptador"
          cabeza={['Subcomando', 'Contesta']}
          filas={[
            [<code key="a">doctor</code>, <><code>{'{"ok": true, "mensaje": "..."}'}</code>; con <code>ok: false</code> y <code>salida</code> si algo falla</>],
            [<code key="b">protocolo</code>, 'Qué sabe hacer y qué parámetros pide'],
            [<code key="c">escanear [--hechas]</code>, 'Los proyectos con sus tareas, más avisos y leido'],
            [<code key="d">estado &lt;ref&gt; &lt;nuevo&gt; --esperado JSON</code>, 'cambio y la tarea como quedó'],
            [<code key="e">agente &lt;ref&gt; &lt;quien&gt; --esperado JSON</code>, 'Igual; quien vacío la deja sin dueño'],
            [<code key="f">marcar &lt;ref&gt; --hecha|--pendiente --esperado JSON</code>, 'Igual. Solo lo usa el board: finalizar es de una persona'],
            [<code key="g">crear --proyecto N --texto T</code>, 'La tarea nueva; contestar no-implementado es válido'],
          ]}
        />
        <p>
          Todo en JSON con <code>"esquema": 1</code>. Los errores salen con código distinto de 0 y{' '}
          <code>{'{"error", "tipo", "salida", "reintentable"}'}</code>; <code>tipo: "cambiada"</code>{' '}
          es la que importa: la tarea ya no está como dice <code>--esperado</code>, así que no se
          escribe. Al adaptador se le piden primitivas, no los verbos de trabajo: que entregar exija
          evidencia y bloquear exija motivo sigue siendo de Cotejo. La skill{' '}
          <code>cotejo-fuentes</code> (se instala junto a la de Cotejo) le enseña a tu agente a cambiar de
          fuente y a conectar una app nueva; el resto de sus skills están en{' '}
          <a href={enlace('/docs/agentes')}>Agentes y modelos</a>.
        </p>
      </>
    ),
  },
]

export default function Fuentes() {
  return (
    <Doc
      ruta="/docs/fuentes"
      titulo="Fuentes."
      bajada="Las tareas viven por defecto en tu repo. Obsidian y Notion sirven para traer un proyecto que ya existe."
      secciones={secciones}
    />
  )
}
