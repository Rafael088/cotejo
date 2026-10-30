// Todo lo que cambia cuando se publique de verdad vive aquí.

// Dominio propio (GitHub Pages con HTTPS forzado). install.sh e install.ps1 viven en
// web/public/ y se sirven en la raíz: https://cotejo.dev/install.sh. publicar.sh escribe el
// CNAME en gh-pages; sin él, el dominio se cae.
const DOMINIO = 'cotejo.dev'
export const CONTACTO = 'soporte@cotejo.dev'
const SERVIDOR = DOMINIO

// La pone vite.config.js desde tareas.__version__: no se escribe a mano.
export const VERSION = __COTEJO_VERSION__

export const COMANDOS = {
  // web/public/install.sh: baja la última release, comprueba su SHA-256 e instala; repetirlo
  // actualiza.
  linux: `curl -fsSL https://${SERVIDOR}/install.sh | sh`,
  // web/public/install.ps1: baja el instalador de la última release, comprueba su SHA-256 y
  // lo corre en silencio; repetirlo actualiza.
  windows: `irm https://${SERVIDOR}/install.ps1 | iex`,
}

// Repo público de releases.
export const RELEASES = 'https://github.com/Rafael088/cotejo/releases/latest'

// Los paquetes que la web ofrece según el sistema. El AppImage y el instalador .exe se publican
// como assets de cada release; mientras la 1.3 no tenga esos assets, el botón lleva a la página
// de releases, que es donde estarán: aquí no se escribe el nombre de un archivo que no existe.
export const DESCARGAS = {
  linux: { sistema: 'Linux', paquete: 'AppImage', href: RELEASES },
  windows: { sistema: 'Windows', paquete: 'Instalador .exe', href: RELEASES },
}
export const LICENCIA = 'https://github.com/Rafael088/cotejo/blob/main/LICENSE'
export const DONAR = 'https://link.mercadopago.com.co/cotejo'

// Medición real de `cotejo ahorro` en la máquina del autor (README, «El medidor de ahorro»).
export const AHORRO = {
  lecturas: 4,
  devuelto: 37098,
  leido: 730071,
  razon: 19.7,
  tokensAhorrados: 192492,
}

// Estimación documentada para una consulta: las pendientes de un proyecto contra la nota entera.
export const CONSULTA = { nota: 4700, cli: 480 }
