"""La constelación de proyectos de la pestaña Inicio (v1.3.0), sin GTK: geometría y dibujo.

Cada proyecto es un **núcleo** y sus piezas de arquitectura (`tareas/arquitectura.py`, por
`conocimiento.piezas_del_repo`) son puntos a su alrededor, unidos al núcleo por una línea y
pintados por estado. Es el mapa del proyecto en pequeño: lo que se ve es el producto que se
está construyendo, no las notas.

Los colores salen del tema del board (los tokens de `tareas/temas.py`), no de una tabla propia,
y el verde (`senal`) es **solo** para lo que espera comprobación, como en todo Cotejo:

- `hecho`: punto relleno del color del texto.
- `en-curso`: anillo del color del texto, más grueso.
- `por-comprobar`: punto verde, un poco más grande.
- `falta`: anillo tenue y discontinuo.

Va aparte del widget (`tareas/app/constelacion.py`) por la misma regla que el dot
(`dot_dibujo.py`): se dibuja con cualquier contexto de cairo y se prueba sin pantalla. No
importa ni GTK ni cairo; solo llama métodos del `cr` que le pasan.

La animación es una deriva lenta de cada punto alrededor de su núcleo (`posicion(…, t)`); con
`quieto=True` (las animaciones del sistema apagadas) la pose es fija y nadie pide fotogramas.
"""

import math
from dataclasses import dataclass, field

from .arquitectura import ESTADOS
from .temas import color

POR_FILA = 4              # núcleos por fila como mucho, como las tarjetas del Inicio
ANCHO_CELDA_MIN = 200     # por debajo, menos núcleos por fila
ANCHO_CELDA_PLENO = 240   # a partir de aquí, la constelación a escala 1
ALTO_FILA = 170           # alto de cada fila de núcleos, con su nombre debajo (v1.3.1: era
                          # 240, y una fila sola dejaba 300 px casi vacíos en el Inicio)
CENTRO_Y = 0.44           # dónde cae el núcleo dentro de su fila (fracción del alto)
ALTO_NOMBRE = 0.90        # dónde va el nombre (fracción del alto de la fila)
RADIO_NUCLEO = 13
RADIO_BASE = 44           # el anillo más cercano de piezas
SALTO_ANILLO = 13         # cuánto se aleja cada anillo
ANILLOS = 3
APLASTADO = 0.8           # las órbitas son elipses, más anchas que altas
DERIVA = 0.06             # radianes que se mece cada punto
PERIODO_DERIVA = 2.6      # segundos (la fase avanza t / PERIODO)

# Cómo se pinta cada estado: con qué token se rellena y se traza, cuánto mide y si va
# discontinuo. `None` de relleno es «el fondo de la constelación» (un anillo hueco).
ESTILOS = {
    "hecho": {"relleno": "texto", "trazo": "texto", "radio": 5, "grosor": 1.5, "discontinuo": False},
    "en-curso": {"relleno": None, "trazo": "texto", "radio": 5, "grosor": 2.0, "discontinuo": False},
    "por-comprobar": {"relleno": "senal", "trazo": "senal", "radio": 6, "grosor": 1.5,
                      "discontinuo": False},
    "falta": {"relleno": None, "trazo": "tenue", "radio": 5, "grosor": 1.5, "discontinuo": True},
}
FONDO = "columna"         # el fondo de la caja de la constelación (lo pone el CSS)
LINEA = "borde"           # las líneas del núcleo a cada pieza
NUCLEO = "texto"
NUCLEO_VACIO = "tenue"    # un proyecto sin arquitectura todavía

NOMBRES = {
    "hecho": "Hecho",
    "en-curso": "En curso",
    "por-comprobar": "Espera que lo compruebes",
    "falta": "Falta",
}

ESTADOS_LEYENDA = ("hecho", "en-curso", "por-comprobar", "falta")

assert set(ESTILOS) == set(ESTADOS) == set(NOMBRES)


@dataclass
class Punto:
    """Una pieza alrededor de su núcleo, en coordenadas polares relativas a él."""

    estado: str
    angulo: float
    radio: float
    fase: float


@dataclass
class Nucleo:
    """Un proyecto en la constelación: su centro, su celda (para tocarlo) y sus piezas."""

    nombre: str
    x: float
    y: float
    escala: float
    celda: tuple                      # (x, y, ancho, alto)
    puntos: list = field(default_factory=list)

    @property
    def con_arquitectura(self):
        return bool(self.puntos)


def estilo(estado):
    """El estilo de un estado; uno que no se conoce se pinta como `falta`, nunca en verde."""
    return ESTILOS.get(estado, ESTILOS["falta"])


def columnas_para(n, ancho):
    """Cuántos núcleos van por fila con `n` proyectos en `ancho` px."""
    if n <= 0:
        return 1
    caben = max(1, int(ancho // ANCHO_CELDA_MIN))
    return max(1, min(n, POR_FILA, caben))


def alto_para(n, ancho):
    """El alto que pide la constelación de `n` proyectos a `ancho` px."""
    if n <= 0:
        return 0
    return math.ceil(n / columnas_para(n, ancho)) * ALTO_FILA


def puntos_de(estados, indice=0):
    """Los puntos de un núcleo: repartidos en círculo, en tres anillos, con una fase propia
    para que no se mezan todos a la vez. `indice` gira el reparto de cada proyecto para que
    dos constelaciones vecinas no se vean calcadas."""
    n = len(estados)
    puntos = []
    for k, estado in enumerate(estados):
        angulo = (k / n) * 2 * math.pi + indice
        radio = RADIO_BASE + ((k * 37) % ANILLOS) * SALTO_ANILLO
        puntos.append(Punto(estado, angulo, radio, k * 0.7 + indice))
    return puntos


def disponer(proyectos, ancho):
    """Los núcleos de `proyectos` (cualquier cosa con `nombre` y `estados`, como las
    `resumen_inicio.Tarjeta`) dentro de `ancho` px, en filas de `columnas_para` núcleos.

    Una fila incompleta va centrada. La escala baja si la celda es estrecha, para que las
    órbitas de dos vecinos no se monten.
    """
    proyectos = list(proyectos)
    n = len(proyectos)
    if not n or ancho <= 0:
        return []
    columnas = columnas_para(n, ancho)
    celda = ancho / columnas
    escala = min(1.0, celda / ANCHO_CELDA_PLENO)
    nucleos = []
    for i, proyecto in enumerate(proyectos):
        fila, columna = divmod(i, columnas)
        en_esta_fila = min(columnas, n - fila * columnas)
        sangria = (ancho - en_esta_fila * celda) / 2
        x0, y0 = sangria + columna * celda, fila * ALTO_FILA
        # Un vaivén leve en altura, como en el prototipo: en fila recta parece una tabla.
        vaiven = (-1 if i % 2 else 1) * 8 * escala
        nucleos.append(Nucleo(
            nombre=proyecto.nombre,
            x=x0 + celda / 2,
            y=y0 + ALTO_FILA * CENTRO_Y + vaiven,
            escala=escala,
            celda=(x0, y0, celda, ALTO_FILA),
            puntos=puntos_de(list(getattr(proyecto, "estados", []) or []), i),
        ))
    return nucleos


def posicion(nucleo, punto, t=0.0, quieto=True):
    """(x, y) de `punto` en el instante `t` (segundos). Quieto, siempre la misma."""
    angulo = punto.angulo
    if not quieto:
        angulo += math.sin(t / PERIODO_DERIVA + punto.fase) * DERIVA
    radio = punto.radio * nucleo.escala
    return (nucleo.x + math.cos(angulo) * radio,
            nucleo.y + math.sin(angulo) * radio * APLASTADO)


def nucleo_en(nucleos, x, y):
    """El núcleo cuya celda contiene (x, y), o None: tocar la celda abre el proyecto."""
    for nucleo in nucleos:
        cx, cy, ancho, alto = nucleo.celda
        if cx <= x < cx + ancho and cy <= y < cy + alto:
            return nucleo
    return None


def rgba(colores, token):
    """(r, g, b, a) en 0-1 de un token del tema; gris si el tema no lo trae o no se entiende."""
    valor = color((colores or {}).get(token)) if colores else None
    r, g, b, a = valor or (128, 128, 128, 1.0)
    return r / 255, g / 255, b / 255, a


def _fuente(cr, colores, token):
    cr.set_source_rgba(*rgba(colores, token))


def dibujar_punto(cr, x, y, estado, colores, escala=1.0):
    """Un punto de pieza en (x, y) con el estilo de su estado. Lo usan la constelación y su
    leyenda, para que la leyenda no pueda decir otra cosa que el dibujo."""
    e = estilo(estado)
    radio = e["radio"] * max(escala, 0.6)
    cr.new_path()
    cr.arc(x, y, radio, 0, 2 * math.pi)
    _fuente(cr, colores, e["relleno"] or FONDO)
    cr.fill_preserve()
    cr.set_line_width(e["grosor"])
    cr.set_dash([2, 2] if e["discontinuo"] else [])
    _fuente(cr, colores, e["trazo"])
    cr.stroke()
    cr.set_dash([])


def dibujar(cr, nucleos, colores, t=0.0, quieto=True):
    """Pinta la constelación en `cr`: primero las líneas, después las piezas, encima los
    núcleos. Los nombres no: los pone el widget con Pango, que sabe de la tipografía del
    board. Devuelve cuántas piezas pintó (las pruebas lo miran)."""
    pintadas = 0
    cr.set_line_width(1)
    _fuente(cr, colores, LINEA)
    for nucleo in nucleos:
        for punto in nucleo.puntos:
            x, y = posicion(nucleo, punto, t, quieto)
            cr.move_to(nucleo.x, nucleo.y)
            cr.line_to(x, y)
    cr.stroke()
    for nucleo in nucleos:
        for punto in nucleo.puntos:
            dibujar_punto(cr, *posicion(nucleo, punto, t, quieto), punto.estado, colores,
                          nucleo.escala)
            pintadas += 1
    for nucleo in nucleos:
        cr.new_path()
        radio = RADIO_NUCLEO * max(nucleo.escala, 0.6)
        cr.arc(nucleo.x, nucleo.y, radio, 0, 2 * math.pi)
        if nucleo.con_arquitectura:
            _fuente(cr, colores, NUCLEO)
            cr.fill()
        else:
            # Sin arquitectura todavía: el núcleo hueco, para no fingir que hay algo dentro.
            _fuente(cr, colores, FONDO)
            cr.fill_preserve()
            cr.set_line_width(1.5)
            cr.set_dash([3, 3])
            _fuente(cr, colores, NUCLEO_VACIO)
            cr.stroke()
            cr.set_dash([])
    return pintadas


def descripcion(proyectos):
    """Lo que dice el lector de pantalla de la constelación entera."""
    proyectos = list(proyectos)
    if not proyectos:
        return "Mapa de tus proyectos: todavía no hay ninguno"
    partes = []
    for p in proyectos:
        estados = list(getattr(p, "estados", []) or [])
        if not estados:
            partes.append(f"{p.nombre}, sin arquitectura todavía")
            continue
        hechas = estados.count("hecho")
        texto = f"{p.nombre}, {hechas} de {len(estados)} piezas hechas"
        esperan = estados.count("por-comprobar")
        if esperan:
            texto += f", {esperan} esperan que las compruebes"
        partes.append(texto)
    return "Mapa de tus proyectos: " + "; ".join(partes)
