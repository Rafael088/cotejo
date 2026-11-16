import Doc from '../../components/docs/Doc.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { enlace } from '../../enlace.js'

const secciones = [
  {
    id: 'archivo',
    titulo: 'El archivo de configuración',
    hijos: (
      <>
        <p>
          Todo va en un solo archivo, <code>~/.config/cotejo/config.json</code>: qué fuente se usa,
          los parámetros de cada una y los ajustes del enrutador.
        </p>
        <Codigo
          texto={'cotejo config init       # lo crea (o migra el de antes)\ncotejo config validar    # dice qué tiene mal, sin tocarlo'}
        />
        <p>
          <code>COTEJO_CONFIG=/ruta</code> apunta a otro en una sola invocación. El archivo de antes
          (<code>~/.config/tareas-obsidian/config.json</code>) se sigue leyendo mientras no exista el
          nuevo; <code>cotejo config init</code> lo pasa al formato nuevo y lo renombra a{' '}
          <code>config.json.migrado</code> en vez de borrarlo.
        </p>
        <Codigo titulo="Ejemplo" texto={'{ "fuente": "repo", "fuentes": { "repo": { "repos": ["/ruta/al/proyecto"] } } }'} />
        <p>
          Las fuentes y sus parámetros están en <a href={enlace('/docs/fuentes')}>Fuentes</a>.
        </p>
      </>
    ),
  },
  {
    id: 'rutas',
    titulo: 'Dónde guarda cosas',
    hijos: (
      <>
        <Tabla
          etiqueta="Rutas de configuración y estado"
          cabeza={['Sistema', 'Config (config.json, temas, token de Notion)', 'Estado (estado.json, bitácoras, ahorro.json, board.json)']}
          filas={[
            ['Linux', <><code>$XDG_CONFIG_HOME</code> o <code>~/.config</code></>, <><code>$XDG_STATE_HOME</code> o <code>~/.local/state</code>, en <code>tareas-obsidian/</code></>],
            ['Windows', <code key="a">%APPDATA%</code>, <code key="b">%LOCALAPPDATA%\cotejo\estado</code>],
          ]}
        />
        <p>
          <code>COTEJO_ESTADO=/ruta</code> apunta la carpeta de estado a otra en una sola invocación.
          En Linux sigue llamándose <code>tareas-obsidian</code> porque de ahí lee el widget de la
          barra.
        </p>
        <Tabla
          etiqueta="Archivos de estado"
          cabeza={['Archivo', 'Qué es']}
          filas={[
            [<code key="a">bitacora.jsonl</code>, 'Lo que pasó con cada tarea: una línea de JSON por operación, solo se agrega. En la tarea vive su estado; aquí, lo que pasó para llegar ahí.'],
            [<code key="b">despachos.jsonl</code>, 'Lo mismo para el reparto: a qué modelo fue cada tarea y cómo salió, y las que no se repartieron (cotejo despachos).'],
            [<code key="c">ahorro.json</code>, 'Los totales del medidor de ahorro.'],
            [<code key="d">estado.json</code>, 'El resumen que lee el widget de la barra. Lleva "esquema": 1; las claves se agregan, nunca se renombran ni se quitan.'],
            [<code key="e">board.json</code>, 'El proyecto elegido en el board.'],
          ]}
        />
      </>
    ),
  },
  {
    id: 'enrutador',
    titulo: 'El enrutador y el maestro',
    hijos: (
      <>
        <p>Los ajustes del enrutador van en el mismo archivo, bajo la clave <code>enrutador</code>:</p>
        <Codigo
          texto={'{\n  "enrutador": {\n    "motor": "agente",\n    "proyectos": { "Cotejo": "~/Documentos/ClaudeCode/cotejo" },\n    "modelos": [],\n    "reglas_extra": [],\n    "reglas_apagadas": []\n  }\n}'}
        />
        <Tabla
          etiqueta="Claves del enrutador"
          cabeza={['Clave', 'Qué es']}
          filas={[
            [<code key="a">proyectos</code>, 'En qué carpeta trabaja el agente para cada proyecto. Sin entrada, corre donde estés.'],
            [<code key="b">modelos</code>, <>Los modelos que añadiste, cada uno con <code>clave</code>, <code>modelo_id</code>, <code>cliente</code> y <code>nivel</code>. Se gestiona con <code>cotejo modelos agregar</code> y <code>quitar</code>.</>],
            [<code key="c">reglas_extra</code>, 'Reglas propias; ganan a las de fábrica.'],
            [<code key="d">reglas_apagadas</code>, <>Una regla de fábrica se apaga por su nombre (<code>cotejo config</code> las lista).</>],
            [<code key="e">capacidad</code>, <><code>mb_por_agente</code>, <code>reserva_mb</code>, <code>fraccion_swap</code>, <code>cpu_por_agente</code>, <code>maximo</code>.</>],
            [<code key="f">maestro</code>, <><code>modelos</code> (el modelo del maestro en cada cliente, p. ej. <code>{'{"claude": "opus"}'}</code>), <code>timeout_seg</code> (600) y <code>argumentos_extra.&lt;cliente&gt;</code>, que solo añade: los permisos van siempre.</>],
            [<code key="g">motores.headless.clientes.&lt;cliente&gt;</code>, <><code>comando</code> y <code>argumentos_extra</code> para lanzar un cliente que no es Claude.</>],
            [<code key="h">motores.headless.aislar</code>, <>(<code>true</code> por defecto) corre cada headless en su propio scope de systemd de usuario, con <code>memoria_max</code> (<code>"50%"</code> por defecto, o <code>"2G"</code>). <code>aislar: false</code> lo apaga.</>],
          ]}
        />
        <p>
          <code>COTEJO_MOTOR</code> fija el motor en una sola invocación.
        </p>
      </>
    ),
  },
  {
    id: 'variables',
    titulo: 'Variables de entorno',
    hijos: (
      <Tabla
        etiqueta="Variables de entorno"
        cabeza={['Variable', 'Para qué']}
        filas={[
          [<code key="a">COTEJO_CONFIG</code>, 'Otro archivo de configuración.'],
          [<code key="b">COTEJO_ESTADO</code>, 'Otra carpeta de estado.'],
          [<code key="c">COTEJO_VAULT</code>, 'Otro vault de Obsidian.'],
          [<code key="d">COTEJO_CARPETA_PROYECTOS</code>, 'Otra carpeta de proyectos dentro del vault.'],
          [<code key="e">COTEJO_CARPETAS_SUELTAS</code>, 'Carpetas sueltas, separadas por comas; vacía para apagarlas.'],
          [<code key="f">COTEJO_MOTOR</code>, 'El motor del enrutador.'],
        ]}
      />
    ),
  },
  {
    id: 'instalador',
    titulo: 'Opciones del instalador',
    hijos: (
      <>
        <p>
          Estas son las de <code>install.sh</code> en Linux. <code>./uninstall.sh</code> quita todo
          eso; la config se queda.
        </p>
        <Tabla
          etiqueta="Opciones de install.sh"
          cabeza={['Opción', 'Para qué']}
          filas={[
            [<code key="a">--sin-board</code>, 'Solo la CLI (un servidor, una máquina sin escritorio).'],
            [<code key="b">--sin-widget</code> , 'No tocar la barra de Omarchy.'],
            [<code key="c">--widget</code>, 'Instalar el widget aunque la barra aún no esté configurada.'],
            [<code key="d">--sin-agentes</code>, 'No escribir el protocolo en Claude Code, Codex, Gemini CLI ni opencode.'],
            [<code key="e">--prefijo /usr/local</code>, 'Para todo el sistema (con sudo).'],
          ]}
        />
        <Codigo
          texto={'curl -fsSL https://cotejo.dev/install.sh | sh -s -- --sin-board'}
          titulo="Pasar una opción al instalador"
        />
      </>
    ),
  },
  {
    id: 'barra',
    titulo: 'La barra de Omarchy y los temas',
    hijos: (
      <>
        <p>
          En Linux con Omarchy, el widget <code>cotejo.barra</code> se ajusta en{' '}
          <code>~/.config/omarchy/shell.json</code>:
        </p>
        <Codigo texto={'{ "id": "cotejo.barra", "mostrarPendientes": false, "intervaloSeg": 300, "colorAviso": "#16C98D" }'} />
        <p>
          <code>mostrarPendientes: true</code> enseña siempre el total (por defecto solo sale un
          número cuando algo espera tu comprobación). <code>intervaloSeg</code> es cada cuánto
          recalcula por su cuenta, como red de seguridad cuando la app no corre.
        </p>
        <p>
          El board trae dos temas, Oscuro y Claro, que se eligen con el botón ◐. Un tema propio es
          un archivo JSON de colores que se crea y se comprueba por la CLI: <code>cotejo temas</code>,{' '}
          <code>temas nuevo &lt;id&gt;</code>, <code>temas comprobar &lt;id&gt;</code> (mide el
          contraste) y <code>temas usar &lt;id&gt;</code>.
        </p>
        <Aviso>
          Esta sección es de Linux con Omarchy.
        </Aviso>
      </>
    ),
  },
]

export default function Configuracion() {
  return (
    <Doc
      ruta="/docs/configuracion"
      titulo="Configuración."
      bajada="Lo esencial: un solo archivo, dónde guarda cosas Cotejo y qué se puede ajustar."
      secciones={secciones}
    />
  )
}
