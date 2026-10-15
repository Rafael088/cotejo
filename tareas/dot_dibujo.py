"""El dot dibujado con cairo, sin GTK: `dibujar_dot(cr, pose, lado)` y el fotograma entero.

`tareas/dot.py` dice dónde está cada pieza en un instante (la `Pose`); este módulo la pinta. Va
aparte del widget (`tareas/dot_widget.py`) para que las pruebas y cualquier herramienta puedan
dibujar el dot solo con pycairo, en un Python sin PyGObject: es la misma regla de `marca.py` y
`dibujar_arranque`.

Qué hace cada pieza:

- `dibujar_dot` pinta las formas del SVG del laboratorio (`docs/dot/avatar.html`) en el mismo
  orden, con los mismos degradados, trazos discontinuos y opacidades de grupo. **No** pone ni el
  brillo de la piel ni el desaturado de `falla`: en el board los ponen los nodos de GSK
  (`push_shadow`, `push_color_matrix`), que los hacen en la GPU. Por eso se puede pedir una sola
  capa (`CAPAS`): el widget necesita la piel separada del resto para poner la sombra y el
  filtro donde los pone el navegador, y no sobre todo el dibujo.
- `componer` hace en software lo que el widget hace con GSK (capas, filtro, sombra y la
  opacidad del mundo) y devuelve una `ImageSurface`. Lo usan las pruebas de fotogramas para
  comparar con el oro de Chromium (`pruebas/oro/dot/`) sin pantalla.

Los colores del dot son fijos: no siguen el tema del board (decisión del 2026-10-10). Lo único
que cambia en modo claro es el alfa del brillo, y eso es cosa de la sombra.
"""

import math

import cairo

from . import dot

GEO = dot.GEOMETRIA
_K = 2 / 3   # una cuadrática de SVG como cúbica de cairo: los puntos de control a 2/3

# Las capas en que el widget parte el dibujo, de atrás adelante, con las piezas raíz de cada
# una. La piel (mechón + cuerpo) es la que lleva el brillo; cada mitad lleva su propio filtro
# porque en `falla` y al salir de ella el mechón y el cuerpo no se desaturan a la vez.
CAPAS = {
    "fondo": ("halo1", "halo2"),
    "pluma": ("pluma",),
    "cuerpo": ("cuerpo",),
    "frente": ("ideas", "chispas"),
}
PIEL = ("pluma", "cuerpo")

HIJOS = {p: tuple(h for h in dot.PIEZAS if dot.PADRE[h] == p) for p in dot.PIEZAS}


def _rgb(hexa):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))


TINTA = _rgb(GEO["color"]["tinta"])
SENAL = _rgb(GEO["color"]["senal"])
AMBAR = _rgb(GEO["color"]["ambar"])
_REMATE = {"butt": cairo.LINE_CAP_BUTT, "round": cairo.LINE_CAP_ROUND}


def _curva(cr, x, y, qx, qy, x2, y2):
    """`M x y Q qx qy x2 y2` en cairo, que solo tiene cúbicas."""
    cr.move_to(x, y)
    cr.curve_to(x + _K * (qx - x), y + _K * (qy - y), x2 + _K * (qx - x2), y2 + _K * (qy - y2), x2, y2)


LARGO_PLUMA = dot.LARGO_PLUMA

# --- las formas de cada pieza, en su propio sistema de coordenadas ----------------------------


def _halo(cr, pose, pieza):
    h = GEO["halo"]
    cr.arc(h["cx"], h["cy"], h["r"], 0, 2 * math.pi)   # como el <circle>: desde las 3, horario
    cr.set_line_width(h["grosor"])
    cr.set_line_cap(_REMATE[GEO["remates"]["halo"]])
    if not _guiones(cr, pose, pieza, 1.0, 2 * math.pi * h["r"]):
        cr.new_path()
        return
    cr.set_source_rgb(*SENAL)
    cr.stroke()


def _pluma(cr, pose, pieza):
    p = GEO["pluma"]
    cr.move_to(*p["puntos"][0])
    for punto in p["puntos"][1:]:
        cr.line_to(*punto)
    cr.set_line_width(p["grosor"])
    cr.set_line_cap(_REMATE[GEO["remates"]["pluma"]])
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    # `pathLength="1"`: los guiones vienen en fracciones del largo y aquí van en unidades.
    if not _guiones(cr, pose, pieza, LARGO_PLUMA / p["largo"], LARGO_PLUMA):
        cr.new_path()
        return
    g = GEO["degradado_pluma"]
    degradado = cairo.LinearGradient(0, g["y1"], 0, g["y2"])
    for desplazamiento, color in g["paradas"]:
        degradado.add_color_stop_rgb(desplazamiento, *_rgb(color))
    cr.set_source(degradado)
    cr.stroke()


def _cuerpo(cr, pose, pieza):
    c = GEO["cuerpo"]
    g = GEO["degradado_cuerpo"]
    # `objectBoundingBox`: el centro y el radio son fracciones de la caja del círculo.
    lado = 2 * c["r"]
    x0, y0 = c["cx"] - c["r"], c["cy"] - c["r"]
    cx, cy, r = x0 + g["cx"] * lado, y0 + g["cy"] * lado, g["r"] * lado
    degradado = cairo.RadialGradient(cx, cy, 0, cx, cy, r)
    for desplazamiento, color in g["paradas"]:
        degradado.add_color_stop_rgb(desplazamiento, *_rgb(color))
    cr.arc(c["cx"], c["cy"], c["r"], 0, 2 * math.pi)
    cr.set_source(degradado)
    cr.fill()


def _ojo(indice):
    def pintar(cr, pose, pieza):
        o = GEO["ojos"][indice]
        x, y, w, h, r = o["x"], o["y"], o["ancho"], o["alto"], o["radio"]
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgb(*TINTA)
        cr.fill()
    return pintar


def _feliz(indice):
    def pintar(cr, pose, pieza):
        f = GEO["felices"][indice]
        (x, y), (dx1, dy1, dx2, dy2) = f["m"], f["q"]
        _curva(cr, x, y, x + dx1, y + dy1, x + dx2, y + dy2)
        cr.set_line_width(GEO["grosor_felices"])
        cr.set_line_cap(_REMATE[GEO["remates"]["felices"]])
        cr.set_source_rgb(*TINTA)
        cr.stroke()
    return pintar


def _boca(cr, pose, pieza):
    _curva(cr, *pose.boca_absoluta())
    cr.set_line_width(GEO["grosor_boca"])
    cr.set_line_cap(_REMATE[GEO["remates"]["boca"]])
    cr.set_source_rgb(*TINTA)
    cr.stroke()


def _idea(indice):
    def pintar(cr, pose, pieza):
        x, y, r = GEO["ideas"][indice]
        cr.arc(x, y, r, 0, 2 * math.pi)
        cr.set_source_rgb(*AMBAR)
        cr.fill()
    return pintar


def _chispa(indice):
    def pintar(cr, pose, pieza):
        for (x0, y0), (x1, y1) in GEO["chispas"][indice]:
            cr.move_to(x0, y0)
            cr.line_to(x1, y1)
        cr.set_line_width(GEO["grosor_chispas"])
        cr.set_line_cap(_REMATE[GEO["remates"]["chispas"]])
        cr.set_source_rgb(*AMBAR)
        cr.stroke()
    return pintar


def _guiones(cr, pose, pieza, unidad, largo):
    """Pone `stroke-dasharray` y `stroke-dashoffset` de la pose en `cr` y dice si queda algo
    que pintar (ver `dot.guiones`)."""
    lista, desfase, visible = dot.guiones(pose, pieza, unidad, largo)
    if lista:
        cr.set_dash(lista, desfase)
    return visible


FORMAS = {
    "halo1": _halo, "halo2": _halo, "pluma": _pluma, "cuerpo": _cuerpo,
    "ojo_izq": _ojo(0), "ojo_der": _ojo(1), "feliz_izq": _feliz(0), "feliz_der": _feliz(1),
    "boca": _boca, "idea1": _idea(0), "idea2": _idea(1), "idea3": _idea(2),
    "chispa1": _chispa(0), "chispa2": _chispa(1), "chispa3": _chispa(2),
}

# --- el dibujo --------------------------------------------------------------------------------


opacidad_visible = dot.opacidad_visible


def capa_visible(pose, capa):
    """Si la capa tiene algo que pintar (sin contar la opacidad del mundo). El widget no
    apila nodos para capas vacías: en idle los anillos no existen."""
    return any(opacidad_visible(pose, raiz, "mundo") > 0 for raiz in CAPAS[capa])


def _pintar(cr, pose, pieza, base, escala):
    """Una pieza y sus hijos, en el orden del SVG. Una opacidad menor que 1 se aplica al grupo
    entero, como hace SVG: se pinta en una capa aparte y se compone con ese alfa (si no, donde
    dos hijos se tapan se verían a través, como en la entrada, con el mechón bajo el cuerpo)."""
    opacidad = pose.opacidad[pieza]
    if opacidad <= 0:
        return
    grupo = opacidad < 1
    if grupo:
        cr.push_group()
    forma = FORMAS.get(pieza)
    if forma:
        cr.save()
        cr.set_matrix(cairo.Matrix(*pose.ctm[pieza]).multiply(escala).multiply(base))
        forma(cr, pose, pieza)
        cr.restore()
    for hijo in HIJOS[pieza]:
        _pintar(cr, pose, hijo, base, escala)
    if grupo:
        cr.pop_group_to_source()
        cr.paint_with_alpha(opacidad)


def dibujar_dot(cr, pose, lado, capa=None):
    """Pinta `pose` en un cuadrado de `lado` × `lado` con la esquina en el origen actual de `cr`.

    El lienzo del laboratorio es de 200 × 200 y se escala a `lado`. Sin `capa`, el dibujo entero
    con la opacidad del mundo incluida (lo que da el SVG sin filtros). Con `capa` (una de
    `CAPAS`), solo esa parte y **sin** la opacidad del mundo, que la pone el widget sobre todas
    las capas juntas (`push_opacity`): si cada capa la llevara por su cuenta, en la entrada se
    vería el mechón a través del cuerpo.

    No pone ni el brillo ni el desaturado (ver el docstring del módulo).
    """
    base = cr.get_matrix()
    k = lado / dot.LIENZO
    escala = cairo.Matrix(k, 0, 0, k, 0, 0)
    if capa is None:
        _pintar(cr, pose, "mundo", base, escala)
        return
    for raiz in CAPAS[capa]:
        _pintar(cr, pose, raiz, base, escala)


# --- el filtro de `falla` ---------------------------------------------------------------------


matriz_filtro = dot.matriz_filtro


def matriz_graphene(saturacion, brillo):
    """Los 16 números para `Graphene.Matrix.init_from_float` y `push_color_matrix`.

    Graphene guarda por columnas y GSK multiplica el color como vector fila: lo que va es la
    transpuesta de `matriz_filtro`, con el alfa en la diagonal (lo midió D3).
    """
    m = matriz_filtro(saturacion, brillo)
    filas = [list(f) + [0.0] for f in m] + [[0.0, 0.0, 0.0, 1.0]]
    return [filas[i][j] for j in range(4) for i in range(4)]


def filtrar(superficie, saturacion, brillo):
    """Aplica `saturate·brightness` en software a una `ImageSurface` ARGB32, en su sitio.

    Es lo que hace `push_color_matrix` en el widget. La matriz es lineal y no toca el alfa, así
    que se puede aplicar a los colores premultiplicados tal cual están en memoria.
    """
    if (saturacion, brillo) == (1.0, 1.0):
        return
    superficie.flush()
    datos = superficie.get_data()
    m = matriz_filtro(saturacion, brillo)
    # En memoria, ARGB32 de cairo es B, G, R, A (entero de 32 bits en el orden de la máquina;
    # en las máquinas donde corre Cotejo, little-endian).
    (rr, rg, rb), (gr, gg, gb), (br, bg, bb) = m
    for i in range(0, len(datos), 4):
        a = datos[i + 3]
        if not a:
            continue
        b, g, r = datos[i], datos[i + 1], datos[i + 2]
        datos[i + 2] = min(a, max(0, round(rr * r + rg * g + rb * b)))
        datos[i + 1] = min(a, max(0, round(gr * r + gg * g + gb * b)))
        datos[i] = min(a, max(0, round(br * r + bg * g + bb * b)))
    superficie.mark_dirty()


# --- la sombra --------------------------------------------------------------------------------

# La desviación de la gaussiana del brillo, en px del widget. En `drop-shadow()` la longitud es
# la desviación misma (no la mitad, como en `box-shadow`), y en un elemento de SVG va en
# unidades del lienzo: a 250 px son 22 × 250 / 200 = 27,5 px. Calibrado contra el oro: entre
# 16 y 40 px, la diferencia media con los PNG de 250 px es mínima justo ahí
# (`pruebas/test_dot_dibujo.py`).
def sigma_sombra(lado):
    return GEO["sombra"]["radio"] * lado / dot.LIENZO


def _anchos_de_caja(sigma, n=3):
    """Tres desenfoques de caja seguidos que se parecen a una gaussiana de `sigma` (el método
    de los navegadores para `feGaussianBlur`): los anchos impares que da la varianza."""
    ideal = math.sqrt(12 * sigma * sigma / n + 1)
    bajo = int(ideal)
    if bajo % 2 == 0:
        bajo -= 1
    alto = bajo + 2
    m = round((12 * sigma * sigma - n * bajo * bajo - 4 * n * bajo - 3 * n) / (-4 * bajo - 4))
    return [bajo if i < m else alto for i in range(n)]


def _caja(superficie, ancho, horizontal):
    """Un desenfoque de caja de `ancho` px (impar) en una dirección, con cairo: la media de
    `ancho` copias desplazadas sumadas. Sobre una superficie de coma flotante no hay redondeo."""
    destino = cairo.ImageSurface(superficie.get_format(), superficie.get_width(), superficie.get_height())
    cr = cairo.Context(destino)
    cr.set_operator(cairo.OPERATOR_ADD)
    r = ancho // 2
    for d in range(-r, r + 1):
        cr.set_source_surface(superficie, d if horizontal else 0, 0 if horizontal else d)
        cr.paint_with_alpha(1 / ancho)
    return destino


def _formato_preciso():
    return getattr(cairo, "FORMAT_RGBA128F", cairo.FORMAT_ARGB32)


def desenfocar(superficie, sigma, reduccion=2):
    """Una copia desenfocada (gaussiana aproximada de `sigma` px) de `superficie`.

    Se hace a 1/`reduccion` de resolución, con margen para que lo que se sale del borde vuelva
    al desenfocar como en un plano infinito, y se devuelve a la talla con filtro bilineal: una
    gaussiana de 27 px no tiene detalle que se pierda así, y a la talla entera serían cuatro
    veces más píxeles en cada una de las decenas de pasadas.
    """
    ancho, alto = superficie.get_width(), superficie.get_height()
    s = sigma / reduccion
    anchos = _anchos_de_caja(s)
    margen = sum(a // 2 for a in anchos) + 2
    w = math.ceil(ancho / reduccion) + 2 * margen
    h = math.ceil(alto / reduccion) + 2 * margen
    trabajo = cairo.ImageSurface(_formato_preciso(), w, h)
    cr = cairo.Context(trabajo)
    cr.translate(margen, margen)
    cr.scale(1 / reduccion, 1 / reduccion)
    cr.set_source_surface(superficie, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)
    cr.paint()
    for a in anchos:
        trabajo = _caja(trabajo, a, True)
    for a in anchos:
        trabajo = _caja(trabajo, a, False)
    salida = cairo.ImageSurface(_formato_preciso(), ancho, alto)
    cr = cairo.Context(salida)
    cr.scale(reduccion, reduccion)
    cr.set_source_surface(trabajo, -margen, -margen)
    cr.get_source().set_filter(cairo.FILTER_BILINEAR)
    cr.paint()
    return salida


def color_sombra(claro=False):
    """El color del brillo como (r, g, b, a) de 0 a 1. En modo claro solo baja el alfa."""
    s = GEO["sombra"]
    return tuple(c / 255 for c in s["color"]) + (s["alfa_claro"] if claro else s["alfa"],)


# --- el fotograma entero en software ----------------------------------------------------------


def _capa(pose, lado, capa, formato):
    sup = cairo.ImageSurface(formato, lado, lado)
    dibujar_dot(cairo.Context(sup), pose, lado, capa)
    return sup


def componer(pose, lado, claro=False, sombra=None, sigma=None):
    """El fotograma de `pose` a `lado` px, en una `ImageSurface` ARGB32 transparente.

    Hace en software lo mismo que el widget con GSK: los anillos, la piel con el filtro de cada
    mitad y el brillo debajo, lo de delante, y todo con la opacidad del mundo. `sombra` es si
    va el brillo (por defecto, solo a 250 px, como en el laboratorio); `sigma`, su desviación
    en px (por defecto `sigma_sombra(lado)`).
    """
    if sombra is None:
        sombra = lado >= 250
    final = cairo.ImageSurface(cairo.FORMAT_ARGB32, lado, lado)
    mundo = pose.opacidad["mundo"]
    if mundo <= 0:
        return final
    cr = cairo.Context(final)
    if mundo < 1:
        cr.push_group()
    cr.set_source_surface(_capa(pose, lado, "fondo", cairo.FORMAT_ARGB32), 0, 0)
    cr.paint()
    piel = cairo.ImageSurface(cairo.FORMAT_ARGB32, lado, lado)
    cp = cairo.Context(piel)
    for mitad in PIEL:
        sup = _capa(pose, lado, mitad, cairo.FORMAT_ARGB32)
        if mitad in pose.filtro:
            filtrar(sup, *pose.filtro[mitad])
        cp.set_source_surface(sup, 0, 0)
        cp.paint()
    if sombra:
        # drop-shadow: el alfa de la piel, desenfocado y teñido, debajo de la piel.
        borroso = desenfocar(piel, sigma if sigma is not None else sigma_sombra(lado))
        cr.set_source_rgba(*color_sombra(claro))
        cr.mask_surface(borroso, 0, 0)
    cr.set_source_surface(piel, 0, 0)
    cr.paint()
    cr.set_source_surface(_capa(pose, lado, "frente", cairo.FORMAT_ARGB32), 0, 0)
    cr.paint()
    if mundo < 1:
        cr.pop_group_to_source()
        cr.paint_with_alpha(mundo)
    final.flush()
    return final
