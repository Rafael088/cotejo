import Comando from './Comando.jsx'
import Icono from './Icono.jsx'
import { COMANDOS, RELEASES, VERSION } from '../config.js'

export default function Instalar() {
  return (
    <section className="seccion instalar" id="instalar" aria-labelledby="instalar-titulo">
      <div className="seccion__cabeza">
        <h2 id="instalar-titulo" className="titulo-2">Instálalo y pregúntale qué falta.</h2>
        <p className="parrafo">
          Instalar pide pegar un comando en una terminal; si no te manejas con ella, pídele a tu
          agente que lo corra por ti. Un comando por sistema. Baja la última versión de GitHub, comprueba su checksum, deja{' '}
          <code>cotejo</code> en tu PATH y crea el acceso en el menú. Volver a correrlo actualiza.
        </p>
      </div>

      <div className="instalar__sistemas">
        <div className="instalar__sistema">
          <h3 className="titulo-3">Linux</h3>
          <Comando texto={COMANDOS.linux} />
          <p className="parrafo parrafo--tenue">
            Cualquier distribución. En Arch y Omarchy hay paquete de pacman, y el botón de la barra
            se instala solo.
          </p>
        </div>
        <div className="instalar__sistema">
          <h3 className="titulo-3">Windows 10 y 11</h3>
          <Comando texto={COMANDOS.windows} prompt="PS>" />
          <p className="parrafo parrafo--tenue">
            En PowerShell, sin permisos de administrador. Se instala para tu usuario y se quita
            desde Configuración → Aplicaciones.
          </p>
        </div>
      </div>

      <div className="instalar__despues">
        <div className="instalar__paso">
          <span className="instalar__paso-texto">Después, una sola pregunta:</span>
          <Comando texto="cotejo doctor" />
          <span className="parrafo--tenue instalar__paso-pie">Te dice si funciona y, si no, qué hacer.</span>
        </div>
        <a className="enlace-flecha" href={RELEASES}>
          <Icono nombre="descargar" tam={18} /> Prefiero descargar el paquete
        </a>
      </div>

      <aside className="aviso-beta" aria-label="Aviso de beta">
        <p>
          <strong>Cotejo {VERSION} está en beta.</strong> Todavía puede fallar. Haz copia de tus proyectos
          antes de probarlo y, si algo se rompe, cuéntalo. Es gratis, no libre: la licencia es
          propietaria. Sin macOS por ahora.
        </p>
      </aside>
    </section>
  )
}
