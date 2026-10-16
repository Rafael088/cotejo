// Íconos dibujados a mano, todos con el mismo trazo de 1.75 sobre una caja de 24.
const TRAZOS = {
  copiar: (
    <>
      <rect x="8.5" y="8.5" width="11" height="11" rx="2.5" />
      <path d="M15.5 5.5v-.5a2 2 0 0 0-2-2h-8a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h.5" />
    </>
  ),
  check: <path d="M5 12.5l4.5 4.5L19 7" />,
  flecha: <path d="M5 12h14m-6-6l6 6-6 6" />,
  repetir: <path d="M4 12a8 8 0 0 1 13.7-5.7L20 8.5M20 4v4.5h-4.5M20 12a8 8 0 0 1-13.7 5.7L4 15.5M4 20v-4.5h4.5" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  cerrar: <path d="M6 6l12 12M18 6L6 18" />,
}

export default function Icono({ nombre, tam = 18, className = '' }) {
  return (
    <svg
      className={`icono ${className}`}
      width={tam}
      height={tam}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {TRAZOS[nombre]}
    </svg>
  )
}
