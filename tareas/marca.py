"""La geometría del logo de Cotejo: la C cortada y el check que la cierra.

Vive aquí, en el núcleo y sin GTK, porque la usan dos: `docs/marca/generar.py`, que dibuja con
ella todos los SVG de la marca, y el board (`tareas/app/`), que la anima al arrancar —la C se dibuja
y el check entra a cerrarla—. Con una copia en cada sitio, el día que se retoque el logo la
animación dibujaría el de antes.

Unidades de Sora (1000 por em, línea base en y = 0, hacia arriba en negativo). Qué significa
cada medida y por qué los cortes son como son está en `docs/marca/generar.py`.
"""

import math

# La C mide lo que una mayúscula de Sora y su trazo es el de la «o» de la palabra. El brazo del
# check sale por la boca de la C y su punta queda flotando sobre la «o».
LETRA = {"centro": (428, -366), "radio": 315, "grosor": 140, "abajo": 30, "aire": 34,
         "check": ((277, -357), (393, -240), (928, -816))}
# 24 px o menos (barra y favicon): el mismo dibujo con el trazo más grueso.
PEQUENA = dict(LETRA, grosor=185, aire=40, abajo=24)


def brazo(geo):
    """El brazo largo del check: su arranque (el vértice), su dirección y la normal que apunta
    hacia arriba a la izquierda, del lado donde queda la punta de arriba de la C."""
    (ax, ay), (bx, by) = geo["check"][1], geo["check"][2]
    largo = math.hypot(bx - ax, by - ay)
    d = ((bx - ax) / largo, (by - ay) / largo)
    return (ax, ay), d, (d[1], -d[0])


def corte(geo, lado, distancia, radio):
    """Dónde corta al círculo de `radio` la recta paralela al brazo, a `distancia` de su eje
    por el `lado` (+1 arriba, -1 abajo). De los dos cruces, el de la salida del check."""
    (ax, ay), d, n = brazo(geo)
    px, py = ax + n[0] * distancia * lado, ay + n[1] * distancia * lado
    cx, cy = geo["centro"]
    fx, fy = px - cx, py - cy
    b = fx * d[0] + fy * d[1]
    t = -b + math.sqrt(b * b - (fx * fx + fy * fy - radio * radio))
    return px + t * d[0], py + t * d[1]


def puntas(geo):
    """Las cuatro esquinas de la C y sus dos radios: `(fuera, dentro, f0, d0, f1, d1)`.

    `f0`/`d0` son la punta de abajo (exterior e interior), cortada en horizontal a
    `geo["abajo"]` grados; `f1`/`d1`, la de arriba, cortada por la paralela al brazo del check.
    La C va de la punta de abajo a la de arriba en el sentido de las agujas del reloj (en
    pantalla, con y hacia abajo).
    """
    r, medio = geo["radio"], geo["grosor"] / 2
    fuera, dentro = r + medio, r - medio
    cx, cy = geo["centro"]
    a = math.radians(geo["abajo"])
    f0 = (cx + fuera * math.cos(a), cy + fuera * math.sin(a))
    d0 = (cx + math.sqrt(dentro ** 2 - (f0[1] - cy) ** 2), f0[1])   # a la misma altura
    arriba = medio + geo["aire"]
    f1, d1 = corte(geo, +1, arriba, fuera), corte(geo, +1, arriba, dentro)
    return fuera, dentro, f0, d0, f1, d1


def angulo(geo, punto):
    """El ángulo de `punto` visto desde el centro de la C, en radianes (y hacia abajo)."""
    cx, cy = geo["centro"]
    return math.atan2(punto[1] - cy, punto[0] - cx)


def barrido(geo):
    """Desde qué ángulo y cuánto recorre la C, de la punta de abajo a la de arriba."""
    _, _, f0, _, f1, _ = puntas(geo)
    desde, hasta = angulo(geo, f0), angulo(geo, f1)
    while hasta <= desde:
        hasta += 2 * math.pi
    return desde, hasta - desde


def largo_del_check(geo):
    return sum(math.hypot(bx - ax, by - ay)
               for (ax, ay), (bx, by) in zip(geo["check"], geo["check"][1:]))


def caja(geo):
    """Lo que ocupa el símbolo: el círculo exterior de la C y el check con su grosor."""
    (cx, cy), fuera, medio = geo["centro"], geo["radio"] + geo["grosor"] / 2, geo["grosor"] / 2
    xs = [cx - fuera, cx + fuera] + [x + s * medio for x, _ in geo["check"] for s in (-1, 1)]
    ys = [cy - fuera, cy + fuera] + [y + s * medio for _, y in geo["check"] for s in (-1, 1)]
    return min(xs), min(ys), max(xs), max(ys)


# --- la animación de arranque del board ------------------------------------------------------
#
# Cuando el board se abre desde cero (el proceso no estaba en segundo plano), primero se ve la
# marca cargando: la C se dibuja desde su punta de abajo y el check entra a cerrarla. Después,
# el board. Entre las dos no pasan más de ARRANQUE_MS + FUNDIDO_MS (~800 ms): es lo que se le
# añade a abrir la ventana, y ya está construida debajo mientras tanto.

ARRANQUE_MS = 650   # la C y el check
FUNDIDO_MS = 150    # del logo al board
# Qué parte de la animación ocupa cada trazo (0 a 1): se solapan, para que el check llegue
# cuando la C está terminando de cerrarse y no después.
TRAMO_C = (0.0, 0.62)
TRAMO_CHECK = (0.45, 1.0)


def _salir_suave(x):
    return 1 - (1 - x) ** 3


def trazos(t):
    """Cuánto se ve de la C y del check (0 a 1 cada uno) en el instante `t` (0 a 1)."""
    def tramo(desde, hasta):
        return _salir_suave(min(1.0, max(0.0, (t - desde) / (hasta - desde))))
    return tramo(*TRAMO_C), tramo(*TRAMO_CHECK)
