// El href de una ruta con la base de Vite (/ con dominio, /cotejo/ sin él). Son enlaces de
// verdad, a otra página prerenderizada: navegan sin JavaScript. Vive aparte de paginas.js
// (que importa todas las páginas) para que las páginas de /docs puedan usarlo al cargarse.
export const enlace = (ruta) => `${import.meta.env.BASE_URL}${ruta.slice(1)}`
