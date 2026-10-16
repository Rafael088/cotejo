import { useState, useRef, useEffect } from 'react'

async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto)
    return true
  } catch {
    // Sin permiso de portapapeles (http, iframes): el método viejo.
    const area = document.createElement('textarea')
    area.value = texto
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    let ok = false
    try {
      ok = document.execCommand('copy')
    } catch {
      ok = false
    }
    area.remove()
    return ok
  }
}

// Copiar al portapapeles con su estado: listo | copiado | error. `copiado` dura ~2,2 s. Si nada
// funciona, deja seleccionado el texto del nodo `ref` para que la persona lo copie con Ctrl+C.
// Lo usan Comando (la línea de terminal) y Frase (lo que se le dice al agente).
export default function useCopiar(texto, ref) {
  const [estado, setEstado] = useState('listo')
  const reloj = useRef()
  useEffect(() => () => clearTimeout(reloj.current), [])

  async function alCopiar() {
    const ok = await copiar(texto)
    if (!ok && ref?.current) {
      const r = document.createRange()
      r.selectNodeContents(ref.current)
      const s = getSelection()
      s.removeAllRanges()
      s.addRange(r)
    }
    setEstado(ok ? 'copiado' : 'error')
    clearTimeout(reloj.current)
    reloj.current = setTimeout(() => setEstado('listo'), 2200)
  }
  return { estado, alCopiar }
}
