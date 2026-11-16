import Doc from '../../components/docs/Doc.jsx'
import Comando from '../../components/Comando.jsx'
import { Aviso, Codigo, Tabla } from '../../components/docs/bloques.jsx'
import { COMANDOS, RELEASES } from '../../config.js'
import { enlace } from '../../enlace.js'

const secciones = [
  {
    id: 'que-es',
    titulo: 'Qué es Cotejo',
    hijos: (
      <>
        <p>
          Cotejo es el tablero de control para tu vibe coding. Tus agentes escriben el código;
          Cotejo ordena el proyecto y verifica lo que entregan. No escribe código por ti.
        </p>
        <ul>
          <li>
            Cada proyecto guarda su contexto, sus decisiones y su arquitectura en una carpeta{' '}
            <code>.cotejo/</code> dentro de su propio repo. Cualquier agente la consulta barato
            (<a href={enlace('/docs/almacen')}>el almacén</a>).
          </li>
          <li>
            Cada tarea va al modelo adecuado: <a href={enlace('/docs/enrutador')}>el enrutador</a>{' '}
            decide a quién le toca y por qué.
          </li>
          <li>
            Nada se da por hecho sin evidencia y sin tu revisión: el agente entrega con pruebas, y
            marcar una tarea como hecha es siempre cosa tuya, en CotejoBoard.
          </li>
        </ul>
        <p>
          Se usa con Claude Code, Codex, OpenCode, Gemini CLI, Antigravity CLI o cualquier agente
          que hable MCP. Es gratis, en Windows y Linux.
        </p>
        <Aviso tipo="ojo">
          Cotejo es software en fase beta: todavía puede tener fallos o comportarse de forma
          inesperada, y se ofrece «tal cual», sin garantías. Haz copia de tu segundo cerebro antes
          de probarlo y, si algo falla, cuéntalo en un{' '}
          <a href="https://github.com/Rafael088/cotejo/issues">issue</a>.
        </Aviso>
      </>
    ),
  },
  {
    id: 'instalar',
    titulo: 'Instalar',
    hijos: (
      <>
        <h3>Linux</h3>
        <p>
          Una línea, sin <code>sudo</code> y sin clonar nada. Baja la última versión, comprueba su
          SHA-256 y la instala. Repetirlo actualiza.
        </p>
        <Comando texto={COMANDOS.linux} prompt="$" />
        <p>
          La CLI necesita solo <code>python3</code>; CotejoBoard, además, <code>python-gobject</code>,{' '}
          <code>python-cairo</code>, <code>gtk4</code> y <code>libadwaita</code>. Sin las
          dependencias del board instala solo la CLI y dice qué falta.
        </p>
        <p>
          En Arch y Omarchy puedes usar el paquete de la{' '}
          <a href={RELEASES}>última release</a>: <code>sudo pacman -U cotejo-*.pkg.tar.zst</code>.
          Para otras distribuciones hay un <code>.tar.gz</code> con su <code>./install.sh</code>.
        </p>
        <h3>Windows</h3>
        <p>
          Windows 10 y 11 de 64 bits. Descarga el instalador <code>.exe</code> de la{' '}
          <a href={RELEASES}>última release</a>, doble clic y siguiente. No pide administrador:
          instala Cotejo para tu usuario, lo pone en el menú Inicio y añade el comando{' '}
          <code>cotejo</code> al PATH, para ti y para tus agentes. O, en PowerShell:
        </p>
        <Comando texto={COMANDOS.windows} prompt="PS>" />
        <h3>Comprobar la instalación</h3>
        <Codigo texto={'cotejo --version\ncotejo doctor'} />
        <p>
          <code>cotejo doctor</code> dice si algo no funciona y qué hacer. Cada release trae su{' '}
          <code>SHA256SUMS</code> para comprobar la descarga a mano. Si ya tenías una versión,
          instala la nueva encima: tus tareas viven en tu repo o en tu vault, y el instalador no las
          toca.
        </p>
      </>
    ),
  },
  {
    id: 'ciclo',
    titulo: 'El ciclo, de init a release',
    hijos: (
      <>
        <p>Seis verbos cuentan el trabajo de un proyecto. Ninguno marca una tarea como hecha.</p>
        <Tabla
          etiqueta="El ciclo de Cotejo"
          cabeza={['Verbo', 'Qué pasa']}
          filas={[
            [<code key="a">cotejo init</code>, <>Deja <code>.cotejo/</code> en tu repo, en la 0.1.0.</>],
            [<code key="b">cotejo plan</code>, 'Qué modelo hace cada tarea, y por qué. No escribe nada.'],
            [<code key="c">cotejo despachar</code>, 'Toma la tarea y abre un worktree con su rama.'],
            [<code key="d">cotejo entregar</code>, 'Con evidencia y pruebas que Cotejo corre sin shell.'],
            [<code key="e">cotejo comprobar</code>, 'Repite las pruebas. Aprobar es tuyo, en el board.'],
            [<code key="f">cotejo release</code>, 'Ensayo de notas; se niega si queda algo sin aprobar.'],
          ]}
        />
        <p>
          Entre <code>entregar</code> y <code>comprobar</code> está la persona: la tarea espera en
          «Para comprobar» hasta que la apruebas o la devuelves con un motivo. Hecha es cuando
          alguien la revisó.
        </p>
      </>
    ),
  },
  {
    id: 'seguir',
    titulo: 'Por dónde seguir',
    hijos: (
      <ul>
        <li>
          <a href={enlace('/docs/primeros-pasos')}>Primeros pasos</a>: tu primer proyecto, de la
          instalación a la primera tarea comprobada.
        </li>
        <li>
          <a href={enlace('/docs/board')}>El board</a>: las cuatro columnas y cómo se revisa una
          entrega.
        </li>
        <li>
          <a href={enlace('/docs/cli')}>La CLI</a>: todos los verbos, una línea cada uno.
        </li>
      </ul>
    ),
  },
]

export default function Introduccion() {
  return (
    <Doc
      ruta="/docs"
      titulo="Documentación de Cotejo."
      bajada="Qué es, cómo se instala y cómo se usa. Tus agentes entregan; tú compruebas."
      secciones={secciones}
    />
  )
}
