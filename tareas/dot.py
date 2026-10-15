"""El dot de Cotejo sin GTK: su geometría, sus animaciones y la pose de cada instante.

El laboratorio (`docs/dot/avatar.html` + `avatar.css`) es la referencia de verdad. Este módulo
lo traduce a datos y a una función: `pose(estado, t, desde)` dice dónde está cada pieza, qué boca
pone, qué se ve y con qué color en el instante `t`, igual que el navegador. Vive aquí, sin GTK ni
cairo, por la misma regla que `marca.py`: una sola copia que usan el widget del board
(`dibujar_dot`, D4), el generador de SVG (D6) y las pruebas (`pruebas/test_dot.py`, que la
comparan con los números de Chromium de `pruebas/oro/dot/oro.json`).

Lo que hay que respetar del navegador para que salga igual (medido en el oro, D1):

- Las piezas se anidan como en el SVG (mundo › piel › cuerpo › ojos…) y cada una es
  `T(origen)·M·T(−origen)` sobre la de su padre. `transform-box: view-box`: los orígenes están en
  el lienzo de 200 × 200, salvo las chispas, que giran sobre el centro de su propia caja.
- La curva de un fotograma clave rige el tramo hasta el siguiente; sin decir nada es la de la
  animación, aplicada **de tramo en tramo** (un `ease-in-out` de 0 a 50 % y otro de 50 a 100 %).
- Dos listas de transformaciones con las mismas funciones se interpolan función a función (el
  giro de `orbita` da la vuelta entera); si no coinciden, el resto se interpola como matrices
  descompuestas (`mirar`: de `translate` a `scaleY`).
- Una animación con retraso no existe antes de él: vale el estilo del estado, no su primer
  fotograma.
- Al cambiar de estado, las transiciones las declara el estado de destino. Una propiedad que
  venía de un `@keyframes` salta aunque el destino declare transición; las que venían quietas
  (o a medio transicionar) se interpolan desde donde estaban.
"""

import functools
import math
import re
from collections import namedtuple

LIENZO = 200

# --- la geometría -----------------------------------------------------------------------------
#
# Los números del brief, en el lienzo de 200 × 200 (el `viewBox` de la plantilla del
# laboratorio). Lo que no se mueve nunca está aquí; lo que cambia con el estado (la boca, las
# opacidades, los trazos) está en ESTILO.

GEOMETRIA = {
    "lienzo": LIENZO,
    "color": {"tinta": "#08120e", "senal": "#16c98d", "ambar": "#f0c987"},
    # El material del cuerpo: un degradado radial (en la caja del círculo) de menta a verde.
    "degradado_cuerpo": {"cx": 0.38, "cy": 0.3, "r": 0.95,
                         "paradas": ((0, "#7ef0c4"), (0.55, "#16c98d"), (1, "#0c7d58"))},
    # El del mechón, vertical y en coordenadas del lienzo: punta menta, base verde señal.
    "degradado_pluma": {"y1": 16, "y2": 56, "paradas": ((0, "#7ef0c4"), (1, "#16c98d"))},
    "cuerpo": {"cx": 100, "cy": 112, "r": 64},
    # Los anillos de `trabaja` y `comprobar`: solo trazo, del color señal.
    "halo": {"cx": 100, "cy": 112, "r": 78, "grosor": 3},
    # El mechón es el check del logo: `pathLength="1"`, así que sus trazos van de 0 a 1.
    "pluma": {"puntos": ((86, 34), (104, 54), (132, 18)), "grosor": 10, "largo": 1},
    # Ojos de píldora, girados −8° sobre su centro (el `transform` del atributo del SVG).
    "ojos": ({"x": 74.5, "y": 89, "ancho": 11, "alto": 26, "radio": 5.5, "giro": (-8, 80, 102)},
             {"x": 114.5, "y": 89, "ancho": 11, "alto": 26, "radio": 5.5, "giro": (-8, 120, 102)}),
    # Los ojos de `celebra`: dos arcos `M x y q 7 −10 14 0`.
    "felices": ({"m": (73, 104), "q": (7, -10, 14, 0)}, {"m": (113, 104), "q": (7, -10, 14, 0)}),
    "grosor_felices": 6,
    "grosor_boca": 6.5,
    # Los puntos ámbar de `piensa` (fuera del port, pero el SVG los tiene: siempre invisibles).
    "ideas": ((150, 44, 5), (164, 32, 6), (180, 18, 7)),
    # Las chispas de `celebra`: dos segmentos cada una, en ámbar.
    "chispas": ((((36, 50), (36, 66)), ((28, 58), (44, 58))),
                (((168, 64), (168, 76)), ((162, 70), (174, 70))),
                (((150, 22), (150, 34)), ((144, 28), (156, 28)))),
    "grosor_chispas": 4,
    # El brillo de la piel (`drop-shadow(0 0 22px var(--halo))`), solo a la talla grande.
    "sombra": {"color": (22, 201, 141), "alfa": 0.35, "alfa_claro": 0.18, "radio": 22},
    # Las puntas de los trazos (`stroke-linecap` de avatar.css): redondas en todo menos en los
    # anillos, que van con la de SVG por defecto. El mechón además dobla redondo
    # (`stroke-linejoin: round`); los demás trazos son una sola curva y no tienen esquinas.
    "remates": {"halo": "butt", "pluma": "round", "felices": "round", "boca": "round",
                "chispas": "round"},
    "union_pluma": "round",
}

# Las piezas, en el orden del SVG, con su padre. Son las 21 que mide el oro.
PADRE = {
    "mundo": None,
    "halo1": "mundo", "halo2": "mundo",
    "piel": "mundo",
    "pluma": "piel",
    "cuerpo": "piel",
    "ojos": "cuerpo", "ojo_izq": "ojos", "ojo_der": "ojos",
    "felices": "cuerpo", "feliz_izq": "felices", "feliz_der": "felices",
    "boca": "cuerpo",
    "ideas": "mundo", "idea1": "ideas", "idea2": "ideas", "idea3": "ideas",
    "chispas": "mundo", "chispa1": "chispas", "chispa2": "chispas", "chispa3": "chispas",
}
PIEZAS = tuple(PADRE)


def _centro_de_caja(segmentos):
    """El centro de la caja de relleno (sin el trazo) de unos segmentos: `transform-box: fill-box`."""
    xs = [x for s in segmentos for x, _ in s]
    ys = [y for s in segmentos for _, y in s]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


# Los `transform-origin` de avatar.css, en el lienzo. Las chispas giran sobre su propio centro.
ORIGEN = {
    "mundo": (100, 176), "halo1": (100, 112), "halo2": (100, 112),
    "cuerpo": (100, 176), "ojos": (100, 104), "pluma": (104, 54),
    **{f"chispa{i + 1}": _centro_de_caja(s) for i, s in enumerate(GEOMETRIA["chispas"])},
}

# --- el estilo de cada estado -----------------------------------------------------------------
#
# Lo que avatar.css deja quieto en cada estado, antes de las animaciones: es el valor de partida
# de las transiciones y el de los fotogramas 0 % y 100 % que un `@keyframes` no escribe. Los
# valores van como en el CSS (`transform` y `d` en texto) y se leen una vez al importar.

ESTILO_BASE = {
    ("mundo", "transform"): "none", ("mundo", "opacity"): 1,
    ("halo1", "opacity"): 0, ("halo2", "opacity"): 0,
    ("halo1", "transform"): "none", ("halo2", "transform"): "none",
    ("halo1", "stroke-dasharray"): None, ("halo1", "stroke-dashoffset"): 0,
    ("halo2", "stroke-dasharray"): None, ("halo2", "stroke-dashoffset"): 0,
    ("pluma", "transform"): "none", ("pluma", "filter"): None,
    ("pluma", "stroke-dasharray"): None, ("pluma", "stroke-dashoffset"): 0,
    ("cuerpo", "transform"): "none", ("cuerpo", "filter"): None,
    ("ojos", "transform"): "none", ("ojos", "opacity"): 1,
    ("felices", "opacity"): 0,
    ("boca", "d"): "M88 128q12 8 24 0",
    ("ideas", "opacity"): 0, ("chispas", "opacity"): 0,
    ("chispa1", "transform"): "none", ("chispa2", "transform"): "none",
    ("chispa3", "transform"): "none",
    ("chispa1", "opacity"): 1, ("chispa2", "opacity"): 1, ("chispa3", "opacity"): 1,
}

ESTILO = {
    "idle": {},
    "trabaja": {
        ("halo1", "opacity"): 0.7, ("halo1", "stroke-dasharray"): "64 426",
        ("boca", "d"): "M90 131q10 0 20 0",
    },
    "comprobar": {
        ("halo1", "opacity"): 0.8, ("halo2", "opacity"): 0.8,
        ("ojos", "transform"): "scale(1.14)",
        ("boca", "d"): "M93 130q7 9 14 0",
    },
    "celebra": {
        ("ojos", "opacity"): 0, ("felices", "opacity"): 1,
        ("boca", "d"): "M82 124q18 20 36 0",
        ("chispas", "opacity"): 1,
        ("pluma", "stroke-dasharray"): "1",
    },
    "falla": {
        ("cuerpo", "filter"): "saturate(0.4) brightness(0.82)",
        ("mundo", "transform"): "translateY(6px)",
        ("ojos", "transform"): "translate(-2px, 8px) scaleY(0.85)",
        ("boca", "d"): "M88 138q12 -9 24 0",
        ("pluma", "transform"): "rotate(58deg)",
        ("pluma", "filter"): "saturate(0.4) brightness(0.82)",
    },
}
ESTADOS = tuple(ESTILO)          # `piensa` se queda en el laboratorio: no se porta
ENTRADA_ESTADO = "entrada"       # la entrada es `idle` con la pista `entrar` en el mundo

# --- las animaciones --------------------------------------------------------------------------
#
# Cada `@keyframes` de avatar.css, tal cual: (porcentajes, {propiedad: valor}, curva). La curva
# de un fotograma rige el tramo hasta el siguiente; `None` es la de la animación.

KEYFRAMES = {
    "respira": ((50, {"transform": "scale(1.022)"}, None),),
    "mirar": (
        ((0, 36), {"transform": "translate(0, 0)"}, None),
        ((44, 58), {"transform": "translate(5px, 0)"}, None),
        ((66, 80), {"transform": "translate(-5px, 1px)"}, None),
        (88, {"transform": "translate(0, 0)"}, None),
        (91, {"transform": "scaleY(0.1)"}, None),
        ((94, 100), {"transform": "scaleY(1)"}, None),
    ),
    "mecer": ((50, {"transform": "rotate(-5deg)"}, None),),
    "orbita": ((100, {"transform": "rotate(360deg)"}, None),),
    "oficio": (
        ((0, 92, 100), {"transform": "translateY(2px) scaleY(0.72)"}, None),
        (96, {"transform": "translateY(2px) scaleY(0.1)"}, None),
    ),
    "tecleo": ((50, {"transform": "translateY(-1.5px)"}, None),),
    "tic": (
        ((0, 100), {"transform": "rotate(4deg)"}, None),
        (50, {"transform": "rotate(-4deg)"}, None),
    ),
    "latido": (
        (0, {"transform": "scale(0.86)", "opacity": 0.8}, None),
        (100, {"transform": "scale(1.18)", "opacity": 0}, None),
    ),
    "asomarse": (
        ((0, 100), {"transform": "rotate(4deg) translateX(3px)"}, None),
        (50, {"transform": "rotate(6deg) translateX(5px)"}, None),
    ),
    "erguir": (
        ((0, 100), {"transform": "rotate(-10deg) scale(1.06)"}, None),
        (50, {"transform": "rotate(-16deg) scale(1.1)"}, None),
    ),
    "salto": (
        (0, {"transform": "translateY(0) scale(1, 1)"}, "cubic-bezier(0.3, 0, 0.6, 1)"),
        (6, {"transform": "translateY(2px) scale(1.05, 0.95)"}, "cubic-bezier(0.2, 0.6, 0.4, 1)"),
        (20, {"transform": "translateY(-18px) scale(0.98, 1.03)"}, "cubic-bezier(0.5, 0, 0.8, 0.6)"),
        (32, {"transform": "translateY(0) scale(1.04, 0.96)"}, "cubic-bezier(0.2, 0.6, 0.4, 1)"),
        ((40, 100), {"transform": "translateY(0) scale(1, 1)"}, None),
    ),
    "chispa": (
        ((0, 14), {"transform": "scale(0)", "opacity": 0}, None),
        (22, {"transform": "scale(1.15)", "opacity": 1}, None),
        (30, {"transform": "scale(1)"}, None),
        (55, {"opacity": 1}, None),
        ((70, 100), {"transform": "scale(0.6)", "opacity": 0}, None),
    ),
    "firmar": (
        ((0, 12), {"stroke-dashoffset": 1}, None),
        ((30, 100), {"stroke-dashoffset": 0}, None),
    ),
    "entrar": (
        (0, {"transform": "translateY(46px) scale(0.55)", "opacity": 0}, None),
        (40, {"opacity": 1}, None),
        (100, {"transform": "none", "opacity": 1}, None),
    ),
}

# Qué anima cada pieza en cada estado: la declaración `animation` de avatar.css. Como en CSS, la
# de un estado sustituye entera a la de la base para esa pieza (`None` es `animation: none`).
Pista = namedtuple("Pista", "animacion duracion curva retraso repite", defaults=(0, True))

PISTAS_BASE = {
    "cuerpo": Pista("respira", 3.6, "ease-in-out"),
    "ojos": Pista("mirar", 7, "ease-in-out"),
    "pluma": Pista("mecer", 3.6, "ease-in-out"),
}
PISTAS = {
    "idle": {},
    "trabaja": {
        "halo1": Pista("orbita", 1.4, "linear"),
        "ojos": Pista("oficio", 2.8, "ease"),
        "mundo": Pista("tecleo", 0.9, "ease-in-out"),
        "pluma": Pista("tic", 0.9, "ease-in-out"),
    },
    "comprobar": {
        "halo1": Pista("latido", 1.6, "ease-out"),
        "halo2": Pista("latido", 1.6, "ease-out", 0.8),
        "ojos": None,
        "cuerpo": Pista("asomarse", 1.6, "ease-in-out"),
        "pluma": Pista("erguir", 1.6, "ease-in-out"),
    },
    "celebra": {
        "mundo": Pista("salto", 2.4, "ease"),
        "ojos": None,
        "chispa1": Pista("chispa", 2.4, "ease"),
        "chispa2": Pista("chispa", 2.4, "ease", 0.08),
        "chispa3": Pista("chispa", 2.4, "ease", 0.16),
        "pluma": Pista("firmar", 2.4, "ease"),
    },
    "falla": {
        "cuerpo": Pista("respira", 5.2, "ease-in-out"),
        "ojos": None,
        "pluma": None,
    },
}

# La entrada (`.entra .mundo`): el dot sube desde abajo y queda en idle. Una sola vez y con
# `fill: both`, así que antes de empezar vale el 0 % y al acabar se queda en el 100 %.
ENTRADA = Pista("entrar", 0.76, "cubic-bezier(0.3, 1.35, 0.5, 1)", 0, False)

# --- las transiciones -------------------------------------------------------------------------
#
# Qué propiedades se interpolan al **entrar** en cada estado y en cuánto: las declara el estado
# de destino (`transition` de avatar.css). Como el `transition` de CSS, el de un estado sustituye
# entero al de la base para esa pieza: en `comprobar` los ojos transicionan el giro y ya no la
# opacidad.

SUAVE = "cubic-bezier(0.3, 0, 0.2, 1)"
TRANSICIONES_BASE = {
    "cuerpo": {"filter": (0.4, "ease")},
    "ojos": {"opacity": (0.16, "ease")},
    "felices": {"opacity": (0.16, "ease")},
    "boca": {"d": (0.26, SUAVE)},
}
TRANSICIONES = {
    "idle": {},
    "trabaja": {},
    "comprobar": {"ojos": {"transform": (0.2, SUAVE)}},
    "celebra": {},
    "falla": {
        "mundo": {"transform": (0.4, SUAVE)},
        "ojos": {"transform": (0.4, SUAVE)},
        "pluma": {"transform": (0.6, SUAVE)},
    },
}

# Con movimiento reducido (`prefers-reduced-motion` en el laboratorio, `gtk-enable-animations`
# en el board): ninguna animación, solo un fundido de 200 ms en las opacidades, y el anillo de
# `trabaja` y `comprobar` se queda a media luz.
QUIETO_TRANSICION = (0.2, "ease")
QUIETO_HALO = 0.6

# --- las curvas -------------------------------------------------------------------------------


class Bezier:
    """Una `cubic-bezier(x1, y1, x2, y2)` de CSS, resuelta como el `UnitBezier` de Chromium.

    Para un x se busca el t de la curva con unas pocas iteraciones de Newton y, si no converge,
    por bisección; luego se evalúa y(t). Fuera de [0, 1] se extrapola con la pendiente de los
    extremos, como el navegador. Es el detalle que más se pierde al portar a mano: `ease` no es
    lineal, y es la curva por defecto de cada tramo.
    """

    EPSILON = 1e-7
    NEWTON = 4

    def __init__(self, x1, y1, x2, y2):
        self.puntos = (x1, y1, x2, y2)
        self.cx = 3 * x1
        self.bx = 3 * (x2 - x1) - self.cx
        self.ax = 1 - self.cx - self.bx
        self.cy = 3 * y1
        self.by = 3 * (y2 - y1) - self.cy
        self.ay = 1 - self.cy - self.by
        # Las pendientes de los extremos, para extrapolar fuera de [0, 1].
        if x1 > 0:
            self.pendiente_inicio = y1 / x1
        elif y1 == 0 and x2 > 0:
            self.pendiente_inicio = y2 / x2
        elif y1 == 0 and y2 == 0:
            self.pendiente_inicio = 1
        else:
            self.pendiente_inicio = 0
        if x2 < 1:
            self.pendiente_fin = (y2 - 1) / (x2 - 1)
        elif y2 == 1 and x1 < 1:
            self.pendiente_fin = (y1 - 1) / (x1 - 1)
        elif y2 == 1 and y1 == 1:
            self.pendiente_fin = 1
        else:
            self.pendiente_fin = 0

    def _x(self, t):
        return ((self.ax * t + self.bx) * t + self.cx) * t

    def _y(self, t):
        return ((self.ay * t + self.by) * t + self.cy) * t

    def _dx(self, t):
        return (3 * self.ax * t + 2 * self.bx) * t + self.cx

    def resolver_t(self, x):
        """El t de la curva cuya x es `x` (0 ≤ x ≤ 1)."""
        t = x
        for _ in range(self.NEWTON):
            error = self._x(t) - x
            if abs(error) < self.EPSILON:
                return t
            pendiente = self._dx(t)
            if abs(pendiente) < 1e-6:
                break
            t -= error / pendiente
        if 0 <= t <= 1 and abs(self._x(t) - x) < self.EPSILON:
            return t
        bajo, alto, t = 0.0, 1.0, x
        while bajo < alto:
            actual = self._x(t)
            if abs(actual - x) < self.EPSILON:
                return t
            if x > actual:
                bajo = t
            else:
                alto = t
            t = (alto + bajo) / 2
            if alto - bajo < 1e-15:
                break
        return t

    def __call__(self, x):
        if x < 0:
            return self.pendiente_inicio * x
        if x > 1:
            return 1 + self.pendiente_fin * (x - 1)
        return self._y(self.resolver_t(x))

    def __repr__(self):
        return "cubic-bezier({}, {}, {}, {})".format(*self.puntos)


def bezier(x1, y1, x2, y2):
    """La función de tiempo `cubic-bezier(x1, y1, x2, y2)`: un invocable de [0, 1] en ℝ."""
    return Bezier(x1, y1, x2, y2)


CURVAS = {
    "linear": None,
    "ease": bezier(0.25, 0.1, 0.25, 1),
    "ease-in": bezier(0.42, 0, 1, 1),
    "ease-out": bezier(0, 0, 0.58, 1),
    "ease-in-out": bezier(0.42, 0, 0.58, 1),
}


def curva(texto):
    """La función de tiempo de un texto de CSS (`ease`, `cubic-bezier(…)`…). `linear` es None."""
    if texto in CURVAS:
        return CURVAS[texto]
    m = re.fullmatch(r"cubic-bezier\(([^)]*)\)", texto.strip())
    if not m:
        raise ValueError(f"curva desconocida: {texto}")
    CURVAS[texto] = bezier(*(float(n) for n in m.group(1).split(",")))
    return CURVAS[texto]


def aplicar(c, x):
    return x if c is None else c(x)


# El viaje del dot entre cartas: el token `--t-avatar` del prototipo. El board GTK no tiene ese
# token y `Adw.TimedAnimation` no acepta curvas propias, así que la curva la pone este módulo.
Viaje = namedtuple("Viaje", "duracion curva")
VIAJE = Viaje(0.9, bezier(0.33, 0, 0.15, 1))


def viaje(t):
    """Cuánto del viaje lleva hecho el dot (0 a 1) a los `t` segundos de salir."""
    return VIAJE.curva(min(1.0, max(0.0, t / VIAJE.duracion)))


# --- las matrices -----------------------------------------------------------------------------
#
# Matrices afines de SVG: (a, b, c, d, e, f) es [[a c e], [b d f], [0 0 1]].

IDENTIDAD = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def multiplicar(m, n):
    """m · n: primero n y luego m, como en una lista de transformaciones de CSS."""
    a, b, c, d, e, f = m
    p, q, r, s, t, u = n
    return (a * p + c * q, b * p + d * q, a * r + c * s, b * r + d * s,
            a * t + c * u + e, b * t + d * u + f)


def trasladar(x, y):
    return (1.0, 0.0, 0.0, 1.0, x, y)


def girar(grados, cx=0, cy=0):
    r = math.radians(grados)
    m = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0.0, 0.0)
    if cx or cy:
        return multiplicar(multiplicar(trasladar(cx, cy), m), trasladar(-cx, -cy))
    return m


def escalar(sx, sy):
    return (sx, 0.0, 0.0, sy, 0.0, 0.0)


def sobre_origen(m, origen):
    """`T(origen)·m·T(−origen)`: así aplica CSS el `transform-origin`."""
    if not origen:
        return m
    ox, oy = origen
    return multiplicar(multiplicar(trasladar(ox, oy), m), trasladar(-ox, -oy))


# --- los valores de CSS -----------------------------------------------------------------------
#
# Una transformación es una tupla de funciones: ("translate", x, y), ("scale", sx, sy) o
# ("rotate", grados). translateX/translateY y scaleX/scaleY se guardan como su primitiva, que es
# lo que el navegador hace al interpolarlas: no cambia el resultado y simplifica emparejarlas.

_FUNCION = re.compile(r"(\w+)\(([^)]*)\)")


def leer_transform(texto):
    if texto in (None, "none"):
        return ()
    funciones = []
    for nombre, args in _FUNCION.findall(texto):
        n = [float(re.sub(r"(px|deg)$", "", a.strip())) for a in re.split(r"[,\s]+", args.strip()) if a]
        if nombre == "translate":
            funciones.append(("translate", n[0], n[1] if len(n) > 1 else 0.0))
        elif nombre == "translateX":
            funciones.append(("translate", n[0], 0.0))
        elif nombre == "translateY":
            funciones.append(("translate", 0.0, n[0]))
        elif nombre == "scale":
            funciones.append(("scale", n[0], n[1] if len(n) > 1 else n[0]))
        elif nombre == "scaleX":
            funciones.append(("scale", n[0], 1.0))
        elif nombre == "scaleY":
            funciones.append(("scale", 1.0, n[0]))
        elif nombre == "rotate":
            funciones.append(("rotate", n[0]))
        else:
            raise ValueError(f"función de transform no soportada: {nombre}")
    return tuple(funciones)


def leer_boca(texto):
    """Los seis números de `M x y q dx1 dy1 dx2 dy2`: la boca es siempre una curva así."""
    m = re.fullmatch(r"M\s*([-\d.]+)[\s,]+([-\d.]+)\s*q\s*([-\d.]+)[\s,]+([-\d.]+)[\s,]+"
                     r"([-\d.]+)[\s,]+([-\d.]+)", texto.strip())
    if not m:
        raise ValueError(f"boca no soportada: {texto}")
    return tuple(float(n) for n in m.groups())


def leer_filtro(texto):
    """`saturate(s) brightness(b)` como (s, b); `None` es sin filtro."""
    if texto in (None, "none"):
        return None
    m = re.fullmatch(r"saturate\(([-\d.]+)\)\s+brightness\(([-\d.]+)\)", texto.strip())
    if not m:
        raise ValueError(f"filtro no soportado: {texto}")
    return float(m.group(1)), float(m.group(2))


def leer(propiedad, valor):
    if propiedad == "transform":
        return leer_transform(valor)
    if propiedad == "d":
        return leer_boca(valor)
    if propiedad == "filter":
        return leer_filtro(valor)
    if propiedad == "stroke-dasharray":
        return None if valor is None else tuple(float(n) for n in str(valor).split())
    return float(valor)


def matriz_de(funciones):
    """La matriz de una lista de funciones, de izquierda a derecha como en CSS."""
    m = IDENTIDAD
    for f in funciones:
        if f[0] == "matrix":
            m = multiplicar(m, tuple(f[1:]))
        elif f[0] == "translate":
            m = multiplicar(m, trasladar(f[1], f[2]))
        elif f[0] == "scale":
            m = multiplicar(m, escalar(f[1], f[2]))
        else:
            m = multiplicar(m, girar(f[1]))
    return m


def _lerp(a, b, p):
    return a + (b - a) * p


_NEUTRA = {"translate": ("translate", 0.0, 0.0), "scale": ("scale", 1.0, 1.0),
           "rotate": ("rotate", 0.0), "matrix": ("matrix",) + IDENTIDAD}


def descomponer(m):
    """Una matriz 2D en traslación, escala, sesgo y giro, como `DecomposeTransform` de Chromium.

    Es la descomposición del navegador restringida al plano: escala en x, sesgo, escala en y
    (ortogonalizando) y el giro que queda. El navegador interpola el giro con cuaterniones; en
    el plano eso es interpolar el ángulo, y es lo que se hace aquí. Con determinante negativo
    (un reflejo) el navegador sale del plano; aquí se niega el eje x, que recompone la misma
    matriz. El dot no tiene reflejos, así que no cambia nada medible.
    """
    a, b, c, d, e, f = m
    sx = math.hypot(a, b)
    r0 = (a / sx, b / sx) if sx else (0.0, 0.0)
    sesgo = r0[0] * c + r0[1] * d
    r1 = (c - sesgo * r0[0], d - sesgo * r0[1])
    sy = math.hypot(*r1)
    r1 = (r1[0] / sy, r1[1] / sy) if sy else (0.0, 0.0)
    if sy:
        sesgo /= sy
    if r0[0] * r1[1] - r0[1] * r1[0] < 0:   # un reflejo (en el dot no hay): se niega el eje x
        sx, sesgo, r0 = -sx, -sesgo, (-r0[0], -r0[1])
    return (e, f), (sx, sy), sesgo, math.atan2(r0[1], r0[0])


def recomponer(traslado, escala, sesgo, angulo):
    """traslación · giro · sesgo · escala: la inversa de `descomponer`."""
    m = trasladar(*traslado)
    m = multiplicar(m, girar(math.degrees(angulo)))
    m = multiplicar(m, (1.0, 0.0, sesgo, 1.0, 0.0, 0.0))
    return multiplicar(m, escalar(*escala))


def interpolar_matrices(m, n, p):
    (t0, e0, s0, a0), (t1, e1, s1, a1) = descomponer(m), descomponer(n)
    return recomponer((_lerp(t0[0], t1[0], p), _lerp(t0[1], t1[1], p)),
                      (_lerp(e0[0], e1[0], p), _lerp(e0[1], e1[1], p)),
                      _lerp(s0, s1, p), _lerp(a0, a1, p))


def interpolar_transform(desde, hasta, p):
    """Interpola dos listas de transformaciones como el navegador y devuelve otra lista.

    `none` hace de lista de identidades del mismo tipo que la otra. Las funciones que coinciden
    al principio de las dos listas se interpolan una a una (un giro de 0 a 360° da la vuelta
    entera); lo que queda desde la primera que no coincide se interpola como matriz
    descompuesta y sale como una función `matrix`. Es lo que guarda el navegador como valor
    calculado, y lo que hay que tener a mano si otra transición sale de aquí.
    """
    if not desde:
        desde = tuple(_NEUTRA[f[0]] for f in hasta)
    if not hasta:
        hasta = tuple(_NEUTRA[f[0]] for f in desde)
    comun = 0
    while comun < min(len(desde), len(hasta)) and desde[comun][0] == hasta[comun][0]:
        comun += 1
    salida = []
    for f, g in zip(desde[:comun], hasta[:comun]):
        if f[0] == "matrix":
            salida.append(("matrix",) + interpolar_matrices(f[1:], g[1:], p))
        else:
            salida.append((f[0],) + tuple(_lerp(x, y, p) for x, y in zip(f[1:], g[1:])))
    if comun < max(len(desde), len(hasta)):
        salida.append(("matrix",) + interpolar_matrices(matriz_de(desde[comun:]),
                                                        matriz_de(hasta[comun:]), p))
    return tuple(salida)


def interpolar(propiedad, desde, hasta, p):
    """El valor de `propiedad` a la fracción `p` (ya con la curva aplicada) entre dos valores."""
    if propiedad == "transform":
        return interpolar_transform(desde, hasta, p)
    if propiedad == "filter":
        a, b = desde or (1.0, 1.0), hasta or (1.0, 1.0)
        return (max(0.0, _lerp(a[0], b[0], p)), max(0.0, _lerp(a[1], b[1], p)))
    if propiedad == "d":
        return tuple(_lerp(x, y, p) for x, y in zip(desde, hasta))
    if propiedad == "stroke-dasharray":   # no se interpola: cambia a mitad, como un discreto
        return hasta if p >= 0.5 else desde
    return _lerp(desde, hasta, p)


# --- las pistas compiladas --------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _claves(nombre, propiedad, base, texto_curva):
    """Los fotogramas de `propiedad` en el `@keyframes` `nombre`: [(offset, valor, curva)].

    Si el 0 % o el 100 % no la escriben, vale el estilo del estado (`base`) con la curva de la
    animación, que es lo que hace CSS con los fotogramas implícitos. Se calcula una vez por
    combinación: la pose se pide a cada fotograma.
    """
    curva_animacion = curva(texto_curva)
    claves = []
    for porcentajes, valores, c in KEYFRAMES[nombre]:
        if propiedad not in valores:
            continue
        for pct in porcentajes if isinstance(porcentajes, tuple) else (porcentajes,):
            claves.append((pct / 100, leer(propiedad, valores[propiedad]),
                           curva(c) if c else curva_animacion))
    claves.sort(key=lambda k: k[0])
    if not claves or claves[0][0] > 0:
        claves.insert(0, (0.0, base, curva_animacion))
    if claves[-1][0] < 1:
        claves.append((1.0, base, curva_animacion))
    return tuple(claves)


@functools.lru_cache(maxsize=None)
def _propiedades(nombre):
    return frozenset(p for _, valores, _ in KEYFRAMES[nombre] for p in valores)


def _valor_en(claves, propiedad, progreso):
    """El valor de una propiedad animada al `progreso` (0 a 1) de la iteración."""
    if progreso >= claves[-1][0]:
        return claves[-1][1]
    for (o0, v0, c), (o1, v1, _) in zip(claves, claves[1:]):
        if o0 <= progreso < o1:
            local = (progreso - o0) / (o1 - o0)
            return interpolar(propiedad, v0, v1, aplicar(c, local))
    return claves[0][1]


def _progreso(pista, reloj):
    """El progreso de la iteración en curso a los `reloj` segundos de empezar la animación, o
    None si todavía no existe (antes de su retraso, sin `fill`)."""
    activo = reloj - pista.retraso
    if pista.repite:
        if activo < 0:
            return None
        return (activo % pista.duracion) / pista.duracion
    # La entrada: una sola vez, con `fill: both`.
    return min(1.0, max(0.0, activo / pista.duracion))


def _estilo(estado):
    valores = {k: leer(k[1], v) for k, v in ESTILO_BASE.items()}
    valores.update({k: leer(k[1], v) for k, v in ESTILO[estado].items()})
    return valores


def _pistas(estado):
    pistas = dict(PISTAS_BASE)
    pistas.update(PISTAS[estado])
    return {pieza: p for pieza, p in pistas.items() if p is not None}


def _transiciones(estado):
    declaradas = dict(TRANSICIONES_BASE)
    declaradas.update(TRANSICIONES[estado])
    return {(pieza, prop): (dur, curva(c))
            for pieza, props in declaradas.items() for prop, (dur, c) in props.items()}


ESTILOS = {e: _estilo(e) for e in ESTADOS}
_TRANS = {e: _transiciones(e) for e in ESTADOS}
_QUIETO_TRANS = {(pieza, "opacity"): (QUIETO_TRANSICION[0], curva(QUIETO_TRANSICION[1]))
                 for pieza, prop in ESTILO_BASE if prop == "opacity"}

# --- la pose ----------------------------------------------------------------------------------

Transicion = namedtuple("Transicion", "desde hasta transcurrido duracion curva inicio_inverso factor")
"""Una transición en marcha: de `desde` a `hasta` en `duracion` segundos con `curva`, y lleva
`transcurrido`. `inicio_inverso` y `factor` son los de la especificación (el acortamiento cuando
una transición se da la vuelta a medias)."""


class Pose:
    """Todo lo que hace falta para dibujar el dot en un instante, sin saber nada de CSS.

    - `ctm[pieza]`: la matriz (a, b, c, d, e, f) que lleva el sistema de la pieza al lienzo de
      200 × 200, con sus antepasados y su origen incluidos. Es la de `getCTM()`.
    - `boca`: los seis números de la boca, `M x y q dx1 dy1 dx2 dy2` (en el sistema de la boca).
    - `opacidad[pieza]`: la opacidad propia de cada pieza (la visible es el producto con la de
      sus antepasados, como en SVG: un grupo se pinta en una capa con su opacidad).
    - `trazo[pieza]`: (dasharray, dashoffset) de las piezas con trazo discontinuo o desplazado;
      el resto no aparece. Van en las unidades de `pathLength` (el mechón mide 1).
    - `filtro[pieza]`: (saturación, brillo) de las piezas con filtro; el resto no aparece.

    Además guarda lo que necesita el siguiente cambio de estado (`estado`, `t`, `valores`, las
    `transiciones` en marcha, los `relojes` de las animaciones y qué propiedades estaban
    `animadas`): por eso se pasa entera como `desde`.
    """

    __slots__ = ("estado", "t", "ctm", "boca", "opacidad", "trazo", "filtro",
                 "valores", "transiciones", "relojes", "animadas", "quieto")

    def boca_absoluta(self):
        """La boca como `M x y Q x1 y1 x2 y2` en absolutas (lo que da el `d` calculado)."""
        x, y, dx1, dy1, dx2, dy2 = self.boca
        return (x, y, x + dx1, y + dy1, x + dx2, y + dy2)

    def __repr__(self):
        return f"Pose({self.estado!r}, t={self.t:g})"


def _iguales(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(a, tuple) and isinstance(b, tuple):
        if len(a) != len(b):
            return False
        return all(_iguales(x, y) for x, y in zip(a, b))
    if isinstance(a, str) or isinstance(b, str):
        return a == b
    return abs(a - b) < 1e-9


def _comparable(propiedad, valor):
    """Para decidir si dos valores son el mismo: las transformaciones, como matriz."""
    return matriz_de(valor) if propiedad == "transform" else valor


def _valor_transicion(tr, ahora):
    """(fracción del tiempo hecha, fracción de la curva) de una transición a los `ahora` s."""
    hecho = 1.0 if tr.duracion <= 0 else min(1.0, max(0.0, ahora / tr.duracion))
    return hecho, aplicar(tr.curva, hecho)


def pose(estado, t, desde=None, quieto=False):
    """La pose del dot a los `t` segundos de entrar en `estado`.

    `estado` es uno de ESTADOS o `"entrada"` (idle con la pista de la entrada en el mundo).
    `desde` es la Pose del estado anterior en el instante del cambio (o None si el dot aparece
    ya en `estado`, como al cargar el laboratorio con `?estado=`). Con ella, como en el
    laboratorio:

    - las animaciones que siguen siendo las mismas en la misma pieza (`respira` en el cuerpo)
      siguen su reloj; las nuevas empiezan en t = 0;
    - las propiedades que el estado nuevo declara en `transition` se interpolan desde su valor
      del cambio, salvo si venían de una animación, que saltan;
    - las transiciones que estaban a medias siguen, se dan la vuelta (acortadas como dice la
      especificación) o se cortan si el estado nuevo no las declara.

    `quieto` es el movimiento reducido: sin animaciones y solo con fundidos de opacidad.
    """
    entrada = estado == ENTRADA_ESTADO
    base_estado = "idle" if entrada else estado
    if base_estado not in ESTILOS:
        raise ValueError(f"estado desconocido: {estado} (están {', '.join(ESTADOS)} y entrada)")
    estilo = dict(ESTILOS[base_estado])
    if quieto and base_estado in ("trabaja", "comprobar"):
        estilo[("halo1", "opacity")] = QUIETO_HALO
    valores = dict(estilo)

    # 1. Las animaciones de CSS.
    pistas = {} if quieto else _pistas(base_estado)
    if entrada and not quieto:
        pistas["mundo"] = ENTRADA
    relojes, animadas = {}, set()
    for pieza, pista in pistas.items():
        reloj = t
        if desde is not None and pieza in desde.relojes and desde.relojes[pieza][0] == pista.animacion:
            reloj = desde.relojes[pieza][1] + t
        relojes[pieza] = (pista.animacion, reloj)
        progreso = _progreso(pista, reloj)
        for prop in _propiedades(pista.animacion):
            animadas.add((pieza, prop))
            if progreso is None:
                continue
            claves = _claves(pista.animacion, prop, estilo[(pieza, prop)], pista.curva)
            valores[(pieza, prop)] = _valor_en(claves, prop, progreso)

    # 2. Las transiciones del cambio de estado.
    transiciones = {}
    if desde is not None:
        declaradas = _QUIETO_TRANS if quieto else _TRANS[base_estado]
        for clave, (dur, c) in declaradas.items():
            if clave in animadas:      # una animación manda sobre su propiedad
                continue
            hasta = estilo[clave]
            corriendo = desde.transiciones.get(clave)
            if clave in desde.animadas:          # venía de un @keyframes: salta
                continue
            antes = desde.valores[clave]
            if corriendo and _iguales(_comparable(clave[1], corriendo.hasta), _comparable(clave[1], hasta)):
                transiciones[clave] = corriendo._replace(transcurrido=corriendo.transcurrido + t)
                continue
            if _iguales(_comparable(clave[1], antes), _comparable(clave[1], hasta)):
                continue
            inicio_inverso, factor, duracion = antes, 1.0, dur
            if corriendo and _iguales(_comparable(clave[1], corriendo.inicio_inverso),
                                      _comparable(clave[1], hasta)):
                _, salida = _valor_transicion(corriendo, corriendo.transcurrido)
                factor = min(1.0, max(0.0, abs(salida * corriendo.factor + 1 - corriendo.factor)))
                duracion = dur * factor
                inicio_inverso = corriendo.hasta
            transiciones[clave] = Transicion(antes, hasta, t, duracion, c, inicio_inverso, factor)
    for clave, tr in list(transiciones.items()):
        hecho, salida = _valor_transicion(tr, tr.transcurrido)
        if hecho >= 1:
            del transiciones[clave]
            continue
        valores[clave] = interpolar(clave[1], tr.desde, tr.hasta, salida)

    # 3. La pose: matrices encadenadas, opacidades, trazos y filtros.
    p = Pose()
    p.estado, p.t, p.quieto = estado, t, quieto
    p.valores, p.transiciones, p.relojes, p.animadas = valores, transiciones, relojes, animadas
    p.ctm, p.opacidad, p.trazo, p.filtro = {}, {}, {}, {}
    for pieza in PIEZAS:
        padre = PADRE[pieza]
        propia = IDENTIDAD
        if (pieza, "transform") in valores:
            propia = sobre_origen(matriz_de(valores[(pieza, "transform")]), ORIGEN.get(pieza))
        elif pieza in _GIRO_OJO:
            propia = _GIRO_OJO[pieza]
        p.ctm[pieza] = multiplicar(p.ctm[padre], propia) if padre else propia
        p.opacidad[pieza] = min(1.0, max(0.0, valores.get((pieza, "opacity"), 1.0)))
        guiones = valores.get((pieza, "stroke-dasharray"))
        desfase = valores.get((pieza, "stroke-dashoffset"), 0.0)
        if guiones is not None or desfase != 0:
            p.trazo[pieza] = (guiones, desfase)
        filtro = valores.get((pieza, "filter"))
        if filtro is not None:
            p.filtro[pieza] = filtro
    p.boca = valores[("boca", "d")]
    return p


# Los ojos de píldora llevan su giro en el SVG (`transform="rotate(-8 80 102)"`), fijo.
_GIRO_OJO = {nombre: girar(*ojo["giro"])
             for nombre, ojo in zip(("ojo_izq", "ojo_der"), GEOMETRIA["ojos"])}


# --- lo que comparten quienes dibujan la pose (cairo en D4, SVG en D6) -------------------------

def _largo_pluma():
    puntos = GEOMETRIA["pluma"]["puntos"]
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(puntos, puntos[1:]))


LARGO_PLUMA = _largo_pluma()


def opacidad_visible(pose, pieza, hasta=None):
    """La opacidad con la que se ve una pieza: el producto con la de sus antepasados (sin
    contar `hasta` ni los de más arriba, que los pone quien llama)."""
    o = 1.0
    while pieza is not None and pieza != hasta:
        o *= pose.opacidad[pieza]
        pieza = PADRE[pieza]
    return o


def guiones(pose, pieza, unidad, largo):
    """El `stroke-dasharray` y el `stroke-dashoffset` de la pose en unidades del trazo, como
    `(lista, desfase, visible)`; `lista` es None si la pieza no tiene guiones.

    `unidad` pasa de las fracciones de `pathLength` a unidades del lienzo (`largo` es lo que mide
    el trazo en ellas). `visible` dice si queda algo a la vista: cuando el trazo entero cae en un
    hueco salvo un guion de largo cero justo en el final (el mechón de `celebra` al empezar a
    firmarse, con el desfase en 1), cairo y librsvg pintan ese guion como un punto con sus
    puntas redondas y Chromium no pinta nada. Por eso se mide lo que queda y, si es nada, no se
    traza.
    """
    lista, desfase = pose.trazo.get(pieza, (None, 0.0))
    if not lista:
        return None, 0.0, True
    lista = [g * unidad for g in lista]
    if len(lista) % 2:          # como en SVG: una lista impar se repite para hacerla par
        lista = lista * 2
    ciclo = sum(lista)
    if ciclo <= 0:
        return None, 0.0, True
    # Lo que se ve: los tramos «on» del patrón, empezando en el desfase, dentro de [0, largo).
    pos, visible, i = -((desfase * unidad) % ciclo), 0.0, 0
    while pos < largo:
        if i % 2 == 0:
            visible += max(0.0, min(largo, pos + lista[i % len(lista)]) - max(0.0, pos))
        pos += lista[i % len(lista)]
        i += 1
    return lista, desfase * unidad, visible > 1e-9


def matriz_filtro(saturacion, brillo):
    """La matriz 3 × 3 de `saturate(s) brightness(b)` de la especificación de filtros (en filas,
    para aplicar a un color columna). El alfa pasa tal cual y no hay desplazamiento."""
    s = saturacion
    lr, lg, lb = 0.2126, 0.7152, 0.0722
    filas = ((lr + (1 - lr) * s, lg - lg * s, lb - lb * s),
             (lr - lr * s, lg + (1 - lg) * s, lb - lb * s),
             (lr - lr * s, lg - lg * s, lb + (1 - lb) * s))
    return tuple(tuple(v * brillo for v in fila) for fila in filas)
