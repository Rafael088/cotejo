// El sistema del navegador, sin adivinar: macOS, Android y iOS no tienen paquete de Cotejo.
// Se puede llamar con cualquier objeto que tenga userAgentData, platform y userAgent (el
// prerender y el comprobador le pasan uno de mentira).
export function sistemaDe(nav) {
  const pistas = [
    nav?.userAgentData?.platform,
    nav?.platform,
    nav?.userAgent,
  ].filter(Boolean).join(' ')
  if (/win/i.test(pistas)) return 'windows'
  if (/android|iphone|ipad|ipod|mac/i.test(pistas)) return 'otro'
  if (/linux|x11/i.test(pistas)) return 'linux'
  return 'otro'
}
