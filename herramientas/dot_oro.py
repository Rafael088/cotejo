"""El oro del dot: los números y los fotogramas que el laboratorio da en instantes fijos.

El laboratorio (`docs/dot/avatar.html` + `avatar.css`) es la referencia de verdad del dot. Este
script lo abre en Chromium sin ventana, pausa todas sus animaciones con la Web Animations API
(`document.getAnimations()`, `currentTime`) y guarda en `pruebas/oro/dot/` lo que ve:

- `oro.json`: por cada muestra, la matriz de cada pieza en coordenadas del lienzo 200×200, el
  `d` de la boca, las opacidades, los desfases y trazos, y el filtro.
- un PNG por muestra y talla (250, 56 y 24 px, fondo transparente): `<id>_<talla>.png`.

Solo hace falta para regenerar el oro (las pruebas normales no necesitan Chromium):

    python3 herramientas/dot_oro.py            # regenera pruebas/oro/dot/
    python3 herramientas/dot_oro.py --comprobar   # regenera aparte y dice si sale lo mismo

Habla con Chromium por el protocolo DevTools sobre pipes (`--remote-debugging-pipe`), con la
biblioteca estándar y nada más. El binario sale de `CHROMIUM`, o de `chromium`, `chromium-browser`
y `google-chrome` en el PATH.

Qué se mide
-----------
Estados: `idle`, `trabaja`, `comprobar`, `celebra`, `falla` (`piensa` está fuera del port) y
`entrada` (el dot sube desde abajo: es `.entra` sobre `idle`).

Instantes fijos, en segundos desde que el estado se activa: 0, 0,3, 0,9, 1,6 y 2,4 (`tipo` =
`reposo`; en `entrada`, `tipo` = `entrada`). El estado se carga de cero con `?estado=<x>`, así
que no hay ninguna transición en marcha: es la pose de las animaciones de CSS y nada más.

Mitad de cada transición (`tipo` = `transicion`, con `desde`): el dot está en reposo en el
estado de origen con sus animaciones en t = 0, se cambia `data-estado` al de destino y se pausa
todo en la mitad de la duración de cada transición que arranca (la boca, el filtro, el giro del
mechón…). Cada duración distinta es un instante, así que todas las animaciones, transiciones
incluidas, van a la vez en ese tiempo desde el cambio. Se capturan de `idle` a cada estado y de
cada estado a `idle`. **Las transiciones las declara el estado de destino**: al volver a `idle`
se interpolan la boca, el filtro del cuerpo y la opacidad de los ojos, pero el giro y el
desplazamiento de los ojos, el del mundo y el del mechón saltan (el `idle` no los declara).

Formato de `oro.json`
---------------------
    {"formato": 1, "lienzo": 200, "tallas": [250, 56, 24], "instantes": [...],
     "muestras": [ <una por línea> ]}

Cada muestra:

    {"id": "falla@0.9",              # también es el prefijo del PNG: falla_t0900
     "estado": "falla", "tipo": "reposo|entrada|transicion", "t": 0.9,
     "desde": "idle",               # solo en las transiciones
     "propiedades": ["boca:d"],      # solo en las transiciones: qué transiciona
     "png": "falla_t0900",
     "piezas": {"mundo": {...}, ...}}

Cada pieza lleva `ctm`: `[a, b, c, d, e, f]`, la matriz de SVG que lleva el sistema de la pieza
al del lienzo de 200×200 (la de `getCTM()` dividida por px-por-unidad: ya incluye los `transform-origin`, las
`transform-box` y todos los ancestros, y no depende de la talla). Además, según la pieza:

    opacidad    opacity calculada de la pieza (la visible es el producto con sus ancestros)
    filtro      {"saturacion": s, "brillo": b} si es saturate()/brightness(); si no, el texto
                calculado de `filter` (el drop-shadow de la piel va aquí). Ausente si no hay
    trazo       {"dasharray": [..] | null, "dashoffset": n}   (en las unidades de pathLength)
    opacidad_trazo   stroke-opacity
    d           solo la boca: el `d` calculado, ya interpolado si hay transición
    transform   la `transform` calculada de la pieza, en matriz CSS (lo que anima avatar.css),
                solo si no es la identidad
    origen      el `transform-origin` calculado, en px (junto a `transform`)

Los números llevan 6 decimales: el ruido de coma flotante de Chromium no entra en el oro.

Lo que D2 debe respetar de CSS (descubierto al medirlo)
-------------------------------------------------------
- Una pieza con `transform-origin` y `transform` es `T(origen)·M·T(-origen)` y sus hijos heredan
  esa matriz: `ctm` de un hijo = `ctm` del padre · la suya propia.
- `transform-box: view-box` en todo el SVG: los orígenes en px (`100px 176px`) están en el
  lienzo, no en la caja de cada pieza. Solo las chispas usan `fill-box`/`center`.
- Los keyframes de un `animation-timing-function` van de tramo en tramo: la curva de un
  fotograma clave rige hasta el siguiente (`salto`), y el resto de las animaciones usan `ease`
  entre claves cuando no lo dicen. `ease-in-out` en `respira`/`mecer` va de tramo en tramo
  (de 0 a 50 % y de 50 % a 100 %), no de una vez.
- Las animaciones con `animation-delay` (halo h2, chispas 2 y 3) no existen antes de su
  desfase: ahí valen el valor de partida (`fill` ninguno), no el primer fotograma.
- Al cambiar de estado, la boca (`d`) transiciona 260 ms, y los demás tiempos dependen de la
  declaración del estado de destino (ver arriba).
"""

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REFERENCIA = RAIZ / "docs" / "dot" / "avatar.html"
DESTINO = RAIZ / "pruebas" / "oro" / "dot"

ESTADOS = ("idle", "trabaja", "comprobar", "celebra", "falla")   # `piensa` no se porta
INSTANTES = (0, 0.3, 0.9, 1.6, 2.4)
TALLAS = (250, 56, 24)
LIENZO = 200
FORMATO = 1

# Las piezas con transform o que cambian con el estado: nombre -> selector dentro del dot.
PIEZAS = {
    "mundo": ".mundo",
    "halo1": ".halo.h1",
    "halo2": ".halo.h2",
    "piel": ".piel",
    "pluma": ".pluma",
    "cuerpo": ".cuerpo",
    "ojos": ".ojos",
    "ojo_izq": ".ojos rect:nth-child(1)",
    "ojo_der": ".ojos rect:nth-child(2)",
    "felices": ".felices",
    "feliz_izq": ".felices path:nth-child(1)",
    "feliz_der": ".felices path:nth-child(2)",
    "boca": ".boca",
    "ideas": ".ideas",
    "idea1": ".ideas circle:nth-child(1)",
    "idea2": ".ideas circle:nth-child(2)",
    "idea3": ".ideas circle:nth-child(3)",
    "chispas": ".chispas",
    "chispa1": ".chispas path:nth-child(1)",
    "chispa2": ".chispas path:nth-child(2)",
    "chispa3": ".chispas path:nth-child(3)",
}

# Dónde se pone cada talla al capturar: una al lado de la otra, sin tocarse.
POSICION = {250: (0, 0), 56: (320, 0), 24: (420, 0)}
SELECTOR_TALLA = {250: "#dot", 56: ".dot-mini:not(.t24)", 24: ".dot-mini.t24"}

# Se inyecta una vez por página: deja solo los tres dots, sueltos y sobre fondo transparente.
PREPARAR = """
(() => {
  const estilo = document.createElement("style");
  estilo.textContent = `
    html, body { background: none !important; margin: 0 !important; padding: 0 !important; }
    body > :not(.dot-suelto):not(script):not(template):not(svg[width="0"]) { display: none !important; }
  `;
  document.head.appendChild(estilo);
  const posicion = %(posicion)s;
  const selectores = %(selectores)s;
  for (const talla of Object.keys(selectores)) {
    const el = document.querySelector(selectores[talla]);
    document.body.appendChild(el);
    el.classList.add("dot-suelto");
    el.style.cssText = `position: fixed; display: block; left: ${posicion[talla][0]}px; ` +
                       `top: ${posicion[talla][1]}px; width: ${talla}px; margin: 0;`;
    el.dataset.talla = talla;
  }
})()
"""

# Congela todo en t segundos y mide. Devuelve {talla: {pieza: {...}}} solo para la talla 250:
# la matriz del lienzo no depende de la talla y se comprueba en `medir_todo`.
CONGELAR = """
((t) => {
  for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
  return document.getAnimations().length;
})
"""

MEDIR = """
((piezas, talla) => {
  const raiz = document.querySelector(`.dot-suelto[data-talla="${talla}"]`);
  const escala = raiz.querySelector("svg").getBoundingClientRect().width / 200;   // px por unidad del lienzo
  const num = (v) => Math.round(v * 1e6) / 1e6 + 0;     // + 0 evita el -0
  const lista = (v) => v === "none" ? null : v.split(/[ ,]+/).map(parseFloat).map(num);
  const salida = {};
  for (const [nombre, selector] of Object.entries(piezas)) {
    const el = raiz.querySelector(selector);
    const cs = getComputedStyle(el);
    const m = el.getCTM();
    const p = { ctm: [m.a, m.b, m.c, m.d, m.e, m.f].map((v) => num(v / escala)), opacidad: num(parseFloat(cs.opacity)) };
    if (cs.transform !== "none") { p.transform = cs.transform.replace(/matrix\\(|\\)/g, "").split(", ").map(parseFloat).map(num); p.origen = cs.transformOrigin; }
    if (cs.filter !== "none") {
      const s = /^saturate\\(([-\\d.e]+)\\) brightness\\(([-\\d.e]+)\\)$/.exec(cs.filter);
      p.filtro = s ? { saturacion: num(parseFloat(s[1])), brillo: num(parseFloat(s[2])) } : cs.filter;
    }
    if (cs.strokeDasharray !== "none" || parseFloat(cs.strokeDashoffset) !== 0) {
      p.trazo = { dasharray: lista(cs.strokeDasharray), dashoffset: num(parseFloat(cs.strokeDashoffset)) };
    }
    if (cs.strokeOpacity !== "1" && el.closest("svg") && cs.stroke !== "none") p.opacidad_trazo = num(parseFloat(cs.strokeOpacity));
    if (nombre === "boca") p.d = cs.getPropertyValue("d");
    salida[nombre] = p;
  }
  return salida;
})
"""

# Tras cambiar de estado: qué transiciones arrancaron, con su duración en ms.
TRANSICIONES = """
(() => document.getAnimations()
  .filter((a) => a instanceof CSSTransition && a.effect.target.closest("#dot"))
  .map((a) => [a.effect.target.getAttribute("class").split(" ")[0], a.transitionProperty,
               a.effect.getTiming().duration]))()
"""

CAMBIAR = """
((estado) => { for (const el of document.querySelectorAll(".dot-suelto")) el.dataset.estado = estado;
               getComputedStyle(document.querySelector(".dot-suelto .boca")).d; })
"""

ENTRAR = """
(() => { for (const el of document.querySelectorAll(".dot-suelto")) el.classList.add("entra");
         getComputedStyle(document.querySelector(".dot-suelto .mundo")).transform; })()
"""


class Chromium:
    """Un Chromium sin ventana al que se le habla por DevTools sobre pipes (sin websocket)."""

    def __init__(self, binario):
        self.perfil = tempfile.mkdtemp(prefix="dot-oro-")
        a_hijo, escribe = os.pipe()     # lo que Chromium lee (fd 3)
        lee, de_hijo = os.pipe()        # lo que Chromium escribe (fd 4)

        def preparar():
            # dup2 sobre sí mismo no quita el cierre al exec: se pide la herencia a mano
            os.dup2(a_hijo, 3, inheritable=True)
            os.dup2(de_hijo, 4, inheritable=True)
            os.set_inheritable(3, True)
            os.set_inheritable(4, True)

        self.proc = subprocess.Popen(
            [binario, "--headless=new", "--remote-debugging-pipe", "--disable-gpu",
             "--no-sandbox", "--hide-scrollbars", "--force-color-profile=srgb",
             "--force-device-scale-factor=1", "--font-render-hinting=none",
             "--disable-lcd-text", "--no-first-run", "--disable-extensions",
             "--host-resolver-rules=MAP * ~NOTFOUND",   # sin red: no hay fuentes ni nada que baje
             f"--user-data-dir={self.perfil}", "about:blank"],
            close_fds=False, preexec_fn=preparar,   # preparar pone los pipes en 3 y 4
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(a_hijo)
        os.close(de_hijo)
        self.escribe = os.fdopen(escribe, "wb", buffering=0)
        self.lee = os.fdopen(lee, "rb", buffering=0)
        self.siguiente = 0
        self.resto = b""
        self.sesion = None
        destino = self.llamar("Target.createTarget", {"url": "about:blank"})["targetId"]
        self.sesion = self.llamar("Target.attachToTarget",
                                  {"targetId": destino, "flatten": True})["sessionId"]

    def _mensaje(self):
        while b"\0" not in self.resto:
            trozo = self.lee.read(65536)
            if not trozo:
                raise RuntimeError("Chromium se cerró antes de contestar")
            self.resto += trozo
        crudo, self.resto = self.resto.split(b"\0", 1)
        return json.loads(crudo)

    def llamar(self, metodo, params=None):
        self.siguiente += 1
        mensaje = {"id": self.siguiente, "method": metodo, "params": params or {}}
        if self.sesion and not metodo.startswith("Target."):
            mensaje["sessionId"] = self.sesion
        self.escribe.write(json.dumps(mensaje).encode() + b"\0")
        while True:
            respuesta = self._mensaje()
            if respuesta.get("id") == self.siguiente:
                if "error" in respuesta:
                    raise RuntimeError(f"{metodo}: {respuesta['error']}")
                return respuesta.get("result", {})

    def evaluar(self, expresion, *argumentos):
        """Evalúa una expresión (o una función con argumentos) y devuelve su valor JSON."""
        if argumentos:
            expresion = f"({expresion})(...{json.dumps(list(argumentos))})"
        r = self.llamar("Runtime.evaluate", {"expression": expresion, "returnByValue": True,
                                             "awaitPromise": True})
        if "exceptionDetails" in r:
            raise RuntimeError(f"JS: {r['exceptionDetails']}")
        return r["result"].get("value")

    def abrir(self, url):
        self.llamar("Page.enable")
        self.llamar("Page.navigate", {"url": url})
        for _ in range(200):
            if self.evaluar("document.readyState") == "complete":
                return
        raise RuntimeError("la página no terminó de cargar")

    def foto(self, talla):
        x, y = POSICION[talla]
        datos = self.llamar("Page.captureScreenshot", {
            "format": "png", "clip": {"x": x, "y": y, "width": talla, "height": talla, "scale": 1}})
        return base64.b64decode(datos["data"])

    def cerrar(self):
        try:
            self.llamar("Browser.close")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.perfil, ignore_errors=True)


def encontrar_chromium():
    for candidato in (os.environ.get("CHROMIUM"), "chromium", "chromium-browser", "google-chrome"):
        if candidato and shutil.which(candidato):
            return shutil.which(candidato)
    sys.exit("No encuentro Chromium: pon su ruta en CHROMIUM.")


def preparar_pagina(nav, estado):
    """Carga el laboratorio ya en `estado` (sin transición) y deja los tres dots sueltos."""
    nav.llamar("Emulation.setDeviceMetricsOverride",
               {"width": 600, "height": 300, "deviceScaleFactor": 1, "mobile": False})
    nav.llamar("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
    nav.abrir(REFERENCIA.as_uri() + f"?estado={estado}")
    nav.evaluar(PREPARAR % {"posicion": json.dumps(POSICION), "selectores": json.dumps(SELECTOR_TALLA)})


def muestrear(nav, t, fotos):
    """Congela todo en t segundos, mide y, si `fotos`, saca los tres PNG."""
    nav.evaluar(CONGELAR, t)
    if fotos:   # dos fotogramas para que el compositor asiente lo congelado antes de la foto
        nav.evaluar("new Promise((ok) => requestAnimationFrame(() => requestAnimationFrame(ok)))")
    piezas = nav.evaluar(MEDIR, PIEZAS, 250)
    # La matriz no depende de la talla: la de 56 y la de 24 tienen que salir igual.
    for talla in TALLAS[1:]:
        otra = nav.evaluar(MEDIR, PIEZAS, talla)
        for nombre, p in piezas.items():
            if max(abs(x - y) for x, y in zip(otra[nombre]["ctm"], p["ctm"])) > 2e-3:
                raise RuntimeError(f"la matriz de {nombre} cambia con la talla ({talla})")
    return piezas, ({talla: nav.foto(talla) for talla in TALLAS} if fotos else {})


def generar(binario):
    """Devuelve ({nombre de archivo: bytes}, texto del JSON)."""
    archivos, muestras = {}, []
    nav = Chromium(binario)

    def anotar(identificador, datos, piezas, imagenes):
        nombre, _, t = identificador.partition("@")
        png = f"{nombre}_t{round(float(t) * 1000):04d}"
        muestras.append({"id": identificador, **datos, "png": png, "piezas": piezas})
        for talla, datos_png in imagenes.items():
            archivos[f"{png}_{talla}.png"] = datos_png

    try:
        # Reposo: cada estado cargado de cero, y la entrada sobre idle.
        for estado in ESTADOS + ("entrada",):
            preparar_pagina(nav, "idle" if estado == "entrada" else estado)
            if estado == "entrada":
                nav.evaluar(ENTRAR)
            tiempos = list(INSTANTES) + ([0.38] if estado == "entrada" else [])
            for t in tiempos:
                piezas, imagenes = muestrear(nav, t, True)
                anotar(f"{estado}@{t:g}",
                       {"estado": estado, "tipo": "entrada" if estado == "entrada" else "reposo", "t": t},
                       piezas, imagenes)
        # Transiciones: de idle a cada estado y de cada estado a idle.
        for estado in ESTADOS[1:]:
            for origen, destino in (("idle", estado), (estado, "idle")):
                preparar_pagina(nav, origen)
                nav.evaluar(CONGELAR, 0)
                nav.evaluar(CAMBIAR, destino)
                trans = nav.evaluar(TRANSICIONES)
                if not trans:
                    continue
                for dur in sorted({d for _, _, d in trans}):
                    t = round(dur / 2000, 4)
                    props = sorted(f"{clase}:{p}"
                                   for clase, p, d in trans if d == dur)
                    piezas, imagenes = muestrear(nav, t, True)
                    anotar(f"{origen}-a-{destino}@{t:g}",
                           {"estado": destino, "tipo": "transicion", "desde": origen, "t": t,
                            "propiedades": props}, piezas, imagenes)
    finally:
        nav.cerrar()
    cabecera = {"formato": FORMATO, "lienzo": LIENZO, "tallas": list(TALLAS),
                "instantes": list(INSTANTES)}
    texto = json.dumps(cabecera)[:-1] + ',\n "muestras": [\n' + ",\n".join(
        json.dumps(m, ensure_ascii=False) for m in muestras) + "\n]}\n"
    return archivos, texto


def escribir(destino, archivos, texto):
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("*.png"):
        viejo.unlink()
    (destino / "oro.json").write_text(texto, encoding="utf-8")
    for nombre, datos in archivos.items():
        (destino / nombre).write_bytes(datos)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--comprobar", action="store_true",
                    help="regenera en una carpeta temporal y compara con el oro del repo")
    ap.add_argument("--destino", type=Path, default=DESTINO)
    args = ap.parse_args(argv)
    archivos, texto = generar(encontrar_chromium())
    if args.comprobar:
        distintos = []
        if (DESTINO / "oro.json").read_text(encoding="utf-8") != texto:
            distintos.append("oro.json")
        for nombre, datos in archivos.items():
            f = DESTINO / nombre
            if not f.exists() or f.read_bytes() != datos:
                distintos.append(nombre)
        sobran = {f.name for f in DESTINO.glob("*.png")} - set(archivos)
        distintos += sorted(sobran)
        print("igual que el oro del repo" if not distintos else
              f"{len(distintos)} archivos distintos: {', '.join(distintos[:10])}")
        return 1 if distintos else 0
    escribir(args.destino, archivos, texto)
    print(f"{len(archivos)} PNG y oro.json en {args.destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
