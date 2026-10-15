"""Dibuja el logo de Cotejo y deja cada versión donde la usa quien la usa.

El logo es la palabra: «Cotejo», con una C que se cierra con un check como primera letra y
«otejo» en Sora SemiBold detrás. La C, en el color del texto, es el trabajo que trae el agente;
el check, en Verde Hecho, es lo que pone la persona. El brazo largo del check sale por la boca
de la C y flota sobre la «o». Esa misma C, sola, es el ícono, el favicon y la barra: el nombre
y el símbolo son una sola pieza.

Todo sale de una sola geometría (`LETRA`, en unidades de Sora) y de la palabra ya convertida a
curvas (`PALABRA`): en la web o en el equipo de quien imprima no hace falta tener la fuente.
Si se cambia la geometría, se vuelve a correr:

    python3 docs/marca/generar.py

Los detalles, que se ven de cerca y no estorban de lejos:

- La C tiene el mismo trazo que las letras de Sora, así que se lee como letra y no como
  un ícono pegado a la palabra.
- La C va cortada a escuadra y el check con puntas redondas: la máquina y la mano.
- La punta de arriba de la C la corta una recta paralela al brazo del check, a `aire` de su
  borde: la boca es una ranura hecha a la medida del check, y a 16 px no se funden.
- La punta de abajo va cortada en horizontal, como las de la «c» de Sora.
- El verde es solo el check: la única marca de color de todo el logo.

La versión engrosada (`PEQUENA`) es para 24 px o menos, y repite los mismos cortes.

Además genera los SVG estáticos del dot (`docs/marca/dot/<estado>-<talla>.svg`, D6): uno por
estado con la pose en t = 0, a 56 y a 24 px. Salen de `tareas/dot.py` (`dot.pose`), no del
laboratorio, así que son los mismos números que pinta el board. Ver `dot_svg`.

Para sacar `PALABRA` de nuevo (otra fuente u otro peso) hace falta fontTools, que no es
dependencia de Cotejo: `palabra()` explica cómo.
"""

import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
WEB = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
# La geometría vive en el núcleo porque el board la anima al arrancar (`tareas/marca.py`).
from tareas import dot  # noqa: E402
from tareas.marca import LETRA, PEQUENA, caja as _caja, puntas  # noqa: E402

# Colores de la marca (docs: nota «Cotejo - Identidad pública», paleta P1).
VERDE = "#16C98D"          # Verde Hecho: el check sobre fondo oscuro (8,8:1 sobre el negro)
VERDE_CLARO = "#0E9F6E"    # el check sobre fondo claro: #16C98D da 2,15:1 sobre blanco y un
                           # gráfico pide 3:1; este da 3,39:1 sobre blanco y 5,58:1 sobre negro
NEGRO = "#101114"
BLANCO = "#FFFFFF"

# La C con el check es la primera letra de la palabra, y la palabra se dibuja en unidades de
# Sora (1000 por em, línea base en y = 0, hacia arriba en negativo), así que la geometría
# también: la C mide lo que una mayúscula de Sora (de -751 a 19, altura de mayúscula 730 más
# el sobrante de las letras redondas) y su trazo es el de la «o» de la palabra. El brazo del
# check sale por la boca de la C y su punta queda flotando sobre la «o», sin tocarla. Se
# define en `tareas/marca.py` (`LETRA`, y `PEQUENA` para 24 px o menos).
SEPARACION = 70   # de la punta de abajo de la C a la «o»: la de Sora entre la C y la o

# «cotejo» en Sora SemiBold (wght 600, interletraje -0,01 em), en unidades de la fuente
# (1000 por em), con la línea base en y = 0 y hacia arriba en negativo. Altura x: 534.
PALABRA = "M319.5 19Q249 19 197.2 -4.8Q145.5 -28.5 111.2 -68.8Q77 -109 60 -159Q43 -209 43 -261V-280Q43 -334.5 60.5 -385Q78 -435.5 112.8 -475.2Q147.5 -515 199 -538.5Q250.5 -562 318.5 -562Q390 -562 445.8 -534.5Q501.5 -507 535 -458Q568.5 -409 572.5 -344H437.5Q432.5 -385.5 402.2 -413.8Q372 -442 318.5 -442Q272.5 -442 242.2 -420Q212 -398 197 -359.5Q182 -321 182 -270.5Q182 -222.5 196.2 -183.8Q210.5 -145 241 -123Q271.5 -101 319.5 -101Q356 -101 382 -114Q408 -127 423.5 -149.8Q439 -172.5 442.5 -202H577.5Q574 -135.5 539.5 -86Q505 -36.5 448.2 -8.8Q391.5 19 319.5 19ZM939.5 19Q868 19 813 -4Q758 -27 720 -66.2Q682 -105.5 662.5 -155.5Q643 -205.5 643 -260V-281Q643 -336.5 663.2 -387.2Q683.5 -438 722 -477.2Q760.5 -516.5 815.5 -539.2Q870.5 -562 939.5 -562Q1009 -562 1063.8 -539.2Q1118.5 -516.5 1157 -477.2Q1195.5 -438 1215.8 -387.2Q1236 -336.5 1236 -281V-260Q1236 -205.5 1216.5 -155.5Q1197 -105.5 1159 -66.2Q1121 -27 1066 -4Q1011 19 939.5 19ZM939.5 -100Q990.5 -100 1025.5 -122.2Q1060.5 -144.5 1078.8 -183.2Q1097 -222 1097 -270.5Q1097 -320.5 1078.2 -359.2Q1059.5 -398 1024.2 -420.5Q989 -443 939.5 -443Q890.5 -443 855 -420.5Q819.5 -398 800.8 -359.2Q782 -320.5 782 -270.5Q782 -222 800.2 -183.2Q818.5 -144.5 853.8 -122.2Q889 -100 939.5 -100ZM1583.5 7Q1508.5 7 1460 -12.5Q1411.5 -32 1387.8 -78.2Q1364 -124.5 1364 -203.5L1364.5 -696H1494.5L1494 -195Q1494 -155 1515.5 -133.5Q1537 -112 1577 -112H1662V7ZM1278 -441V-543H1662V-441ZM2012 19Q1942 19 1889.5 -5Q1837 -29 1802.5 -69.2Q1768 -109.5 1750.5 -159.5Q1733 -209.5 1733 -262V-281Q1733 -335 1750.5 -385.2Q1768 -435.5 1802.2 -475.2Q1836.5 -515 1887.8 -538.5Q1939 -562 2006 -562Q2094 -562 2153.2 -523.2Q2212.5 -484.5 2242.8 -422.2Q2273 -360 2273 -288V-237.5H1792V-322.5H2185.5L2143 -281Q2143 -333 2127.8 -370Q2112.5 -407 2082.2 -427Q2052 -447 2006 -447Q1959.5 -447 1927.5 -425.8Q1895.5 -404.5 1879.2 -365.2Q1863 -326 1863 -271Q1863 -219.5 1878.8 -180Q1894.5 -140.5 1927.5 -118.2Q1960.5 -96 2012 -96Q2062.5 -96 2094.5 -116.5Q2126.5 -137 2135.5 -166.5H2263.5Q2252 -111 2217.8 -69Q2183.5 -27 2131.2 -4Q2079 19 2012 19ZM2302 205V86H2344Q2381 86 2400.8 66Q2420.5 46 2420.5 9.5V-543H2554.5V1.5Q2554.5 76.5 2531.8 121Q2509 165.5 2460.8 185.2Q2412.5 205 2335 205ZM2341.5 -439V-543H2554.5V-439ZM2466 -612Q2425.5 -612 2406 -633.2Q2386.5 -654.5 2386.5 -687.5Q2386.5 -720.5 2406 -741.8Q2425.5 -763 2466 -763Q2507 -763 2526.2 -741.8Q2545.5 -720.5 2545.5 -687.5Q2545.5 -654.5 2526.2 -633.2Q2507 -612 2466 -612ZM2961.5 19Q2890 19 2835 -4Q2780 -27 2742 -66.2Q2704 -105.5 2684.5 -155.5Q2665 -205.5 2665 -260V-281Q2665 -336.5 2685.2 -387.2Q2705.5 -438 2744 -477.2Q2782.5 -516.5 2837.5 -539.2Q2892.5 -562 2961.5 -562Q3031 -562 3085.8 -539.2Q3140.5 -516.5 3179 -477.2Q3217.5 -438 3237.8 -387.2Q3258 -336.5 3258 -281V-260Q3258 -205.5 3238.5 -155.5Q3219 -105.5 3181 -66.2Q3143 -27 3088 -4Q3033 19 2961.5 19ZM2961.5 -100Q3012.5 -100 3047.5 -122.2Q3082.5 -144.5 3100.8 -183.2Q3119 -222 3119 -270.5Q3119 -320.5 3100.2 -359.2Q3081.5 -398 3046.2 -420.5Q3011 -443 2961.5 -443Q2912.5 -443 2877 -420.5Q2841.5 -398 2822.8 -359.2Q2804 -320.5 2804 -270.5Q2804 -222 2822.2 -183.2Q2840.5 -144.5 2875.8 -122.2Q2911 -100 2961.5 -100Z"
PALABRA_CAJA = (43, -763, 3258, 205)   # x e y mínimas, x e y máximas (la t arriba, la j abajo)
ALTURA_X = 534


def _punto(geo, angulo):
    (cx, cy), r = geo["centro"], geo["radio"]
    return cx + r * math.cos(math.radians(angulo)), cy + r * math.sin(math.radians(angulo))


def _distancia_al_check(geo, p):
    """Distancia del punto p al eje del check (la polilínea, sin su grosor)."""
    mejor = math.inf
    for (ax, ay), (bx, by) in zip(geo["check"], geo["check"][1:]):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
        mejor = min(mejor, math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy))
    return mejor


def c_cortada(geo):
    """La C como forma rellena, con las puntas cortadas en recto y no redondas.

    La punta de arriba la corta una recta paralela al brazo largo del check, a medio grosor
    más `geo["aire"]` de su eje: la boca de la C es una ranura hecha a la medida del check. La de
    abajo va cortada en horizontal a `geo["abajo"]` grados, como las puntas de la «c» de Sora
    en la palabra, y deja la letra abierta: si las dos fueran paralelas al check, la C se
    cerraría hasta ser el «check en un círculo» de cualquier lista de tareas.

    La C, cortada a escuadra, es el trabajo de la máquina; el check, con sus puntas redondas,
    es el gesto de la persona.
    """
    fuera, dentro, f0, d0, f1, d1 = puntas(geo)
    n = lambda p: f"{p[0]:.2f} {p[1]:.2f}"
    return (f"M{n(f0)}A{fuera} {fuera} 0 1 1 {n(f1)}L{n(d1)}"
            f"A{dentro} {dentro} 0 1 0 {n(d0)}Z")


def simbolo(geo, tinta, verde):
    """El símbolo como grupo SVG: la C en `tinta` y el check en `verde`."""
    check = " ".join(f"{x},{y}" for x, y in geo["check"])
    return (f'<g><path d="{c_cortada(geo)}" fill="{tinta}"/>'
            f'<polyline points="{check}" fill="none" stroke="{verde}" '
            f'stroke-width="{geo["grosor"]}" stroke-linecap="round" stroke-linejoin="round"/></g>')


def svg(ancho, alto, cuerpo, titulo, comentario=""):
    nota = f"\n  <!-- {comentario} -->" if comentario else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho} {alto}" '
            f'width="{ancho}" height="{alto}" role="img" aria-label="Cotejo">\n'
            f'  <title>{titulo}</title>{nota}\n  {cuerpo}\n</svg>\n')


def encajado(geo, tinta, verde, lado=100, margen=4):
    """El símbolo centrado en un cuadrado de `lado`, con `margen` a cada lado."""
    x0, y0, x1, y1 = _caja(geo)
    util = lado - 2 * margen
    s = util / max(x1 - x0, y1 - y0)
    tx = margen + (util - (x1 - x0) * s) / 2 - x0 * s
    ty = margen + (util - (y1 - y0) * s) / 2 - y0 * s
    return f'<g transform="translate({tx:.2f} {ty:.2f}) scale({s:.5f})">{simbolo(geo, tinta, verde)}</g>'


def _otejo():
    """«otejo»: la palabra sin su «c», que es el primer trozo del path."""
    return "".join(re.findall(r"M[^M]*", PALABRA)[1:])


def palabra_logo(tinta, verde, ancho, margen=40):
    """El logo: «Cotejo», con la C del símbolo como primera letra y «otejo» en Sora detrás.

    En una tinta (`verde` igual a `tinta`) el check va del mismo color que la palabra.
    """
    (cx, _), fuera = LETRA["centro"], LETRA["radio"] + LETRA["grosor"] / 2
    x_o = cx + fuera * math.cos(math.radians(LETRA["abajo"])) + SEPARACION
    desplaza = x_o - 643                     # 643: donde empieza la «o» en `PALABRA`
    x0, y0, _, _ = _caja(LETRA)
    x1, y1 = PALABRA_CAJA[2] + desplaza, PALABRA_CAJA[3]
    vb = (x0 - margen, y0 - margen, x1 - x0 + 2 * margen, y1 - y0 + 2 * margen)
    alto = round(ancho * vb[3] / vb[2])
    cuerpo = (simbolo(LETRA, tinta, verde) +
              f'<path transform="translate({desplaza:.1f} 0)" fill="{tinta}" d="{_otejo()}"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{" ".join(f"{v:.0f}" for v in vb)}" '
            f'width="{ancho}" height="{alto}" role="img" aria-label="Cotejo">\n'
            f'  <title>Cotejo</title>\n'
            f'  <!-- La palabra va en curvas (Sora SemiBold): no necesita la fuente instalada. -->\n'
            f'  {cuerpo}\n</svg>\n')


def icono_app(geo=LETRA, lado=100):
    """El ícono del menú: la C con el check sobre una placa negra, que se ve igual sobre
    cualquier fondo de escritorio o de barra de tareas."""
    cuerpo = (f'<rect width="100" height="100" rx="22" fill="{NEGRO}"/>' +
              encajado(geo, BLANCO, VERDE, margen=18))
    return svg(100, 100, cuerpo, "Cotejo — tus agentes entregan, tú compruebas").replace(
        'width="100" height="100" role', f'width="{lado}" height="{lado}" role')


def _plano(geo, tinta, verde, lado, titulo, comentario=""):
    return svg(100, 100, encajado(geo, tinta, verde), titulo, comentario).replace(
        'width="100" height="100" role', f'width="{lado}" height="{lado}" role')


SALIDAS = {
    # La cabecera del board: `tareas/app/piezas.py` cambia BLANCO por el texto del tema y VERDE
    # por su señal, así que el mismo archivo sirve en el tema oscuro, en el claro y en los del usuario.
    # Va a 264 de ancho, cuatro veces lo que ocupa en la cabecera: GTK lo rasteriza a su tamaño
    # natural y luego lo reduce, así que en una pantalla de escala 2 sigue nítido.
    RAIZ / "data/marca/cotejo-logo.svg": lambda: palabra_logo(BLANCO, VERDE, 264),
    RAIZ / "data/io.github.cotejoapp.Cotejo.svg": icono_app,
    # La barra de Omarchy tiñe el símbolo de un solo color: va en blanco y engrosado, porque
    # se ve a 14 px.
    RAIZ / "barra/cotejo.barra/cotejo-simbolo.svg": lambda: _plano(
        PEQUENA, BLANCO, BLANCO, 100, "Cotejo",
        "Un solo tono: el widget lo tiñe con el color que toque (barra, aviso o error)."),
    # El kit de la página web. No lo instala nadie: solo vive en el repo.
    WEB / "logo-full.svg": lambda: palabra_logo(NEGRO, VERDE_CLARO, 320),
    WEB / "logo-full-oscuro.svg": lambda: palabra_logo(BLANCO, VERDE, 320),
    WEB / "logo-wordmark.svg": lambda: palabra_logo(NEGRO, VERDE_CLARO, 180),
    WEB / "logo-white.svg": lambda: palabra_logo(BLANCO, BLANCO, 320),
    WEB / "logo-black.svg": lambda: palabra_logo(NEGRO, NEGRO, 320),
    WEB / "logo-mark.svg": lambda: _plano(LETRA, NEGRO, VERDE_CLARO, 64, "Cotejo",
                                          "La C de la palabra, sola, sobre fondo claro."),
    WEB / "logo-mark-oscuro.svg": lambda: _plano(LETRA, BLANCO, VERDE, 64, "Cotejo",
                                                 "La C de la palabra, sola, sobre fondo oscuro."),
    WEB / "logo-icon.svg": lambda: icono_app(LETRA, 512),
    WEB / "favicon.svg": lambda: icono_app(PEQUENA, 16),
}

# --- el dot, quieto (D6) -------------------------------------------------------------------------

DOT_TALLAS = (56, 24)
DOT_DIR = WEB / "dot"


def _n(v):
    """Un número con cuatro decimales como mucho y sin ceros de sobra: la salida no depende del
    redondeo de cada máquina ni trae «-0»."""
    texto = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "") else texto


def _matriz(ctm):
    return "matrix(" + " ".join(_n(v) for v in ctm) + ")"


def _horneado(hexa, filtro):
    """Un color con el `saturate·brightness` de la pieza aplicado, como #rrggbb.

    El desaturado de `falla` se hornea en los colores en vez de poner un `feColorMatrix`: da el
    mismo resultado (la matriz es lineal y los degradados interpolan en sRGB, igual que el
    filtro de CSS) y se pinta igual en librsvg, GTK y los navegadores, que no coinciden en el
    espacio de color de los filtros SVG.
    """
    rgb = [int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    if filtro:
        m = dot.matriz_filtro(*filtro)
        rgb = [sum(f * c for f, c in zip(fila, rgb)) for fila in m]
    return "#" + "".join(f"{round(min(1.0, max(0.0, c)) * 255):02x}" for c in rgb)


def _degradados(pose):
    geo = dot.GEOMETRIA
    gc, gp = geo["degradado_cuerpo"], geo["degradado_pluma"]
    fc, fp = pose.filtro.get("cuerpo"), pose.filtro.get("pluma")
    paradas = lambda g, f: "".join(
        f'<stop offset="{_n(o)}" stop-color="{_horneado(c, f)}"/>' for o, c in g["paradas"])
    return (f'<defs><radialGradient id="g-dot" cx="{_n(gc["cx"])}" cy="{_n(gc["cy"])}" '
            f'r="{_n(gc["r"])}">{paradas(gc, fc)}</radialGradient>'
            f'<linearGradient id="g-pluma" gradientUnits="userSpaceOnUse" x1="0" y1="{gp["y1"]}" '
            f'x2="0" y2="{gp["y2"]}">{paradas(gp, fp)}</linearGradient></defs>')


def _forma(pose, pieza):
    """El elemento SVG de una pieza (sin su transform ni su opacidad), o None si es un grupo."""
    geo, color = dot.GEOMETRIA, dot.GEOMETRIA["color"]
    rem = geo["remates"]
    tinta = _horneado(color["tinta"], pose.filtro.get("cuerpo"))
    if pieza in ("halo1", "halo2"):
        h = geo["halo"]
        guiones, desfase, visible = dot.guiones(pose, pieza, 1.0, 2 * math.pi * h["r"])
        if not visible:
            return None
        trazo = f' stroke-dasharray="{" ".join(_n(g) for g in guiones)}"' if guiones else ""
        trazo += f' stroke-dashoffset="{_n(desfase)}"' if guiones and desfase else ""
        return (f'<circle cx="{h["cx"]}" cy="{h["cy"]}" r="{h["r"]}" fill="none" '
                f'stroke="{color["senal"]}" stroke-width="{h["grosor"]}" '
                f'stroke-linecap="{rem["halo"]}"{trazo}/>')
    if pieza == "pluma":
        p = geo["pluma"]
        guiones, desfase, visible = dot.guiones(pose, pieza, dot.LARGO_PLUMA / p["largo"],
                                                dot.LARGO_PLUMA)
        if not visible:
            return None
        trazo = f' stroke-dasharray="{" ".join(_n(g) for g in guiones)}"' if guiones else ""
        trazo += f' stroke-dashoffset="{_n(desfase)}"' if guiones and desfase else ""
        puntos = " ".join(f"{x},{y}" for x, y in p["puntos"])
        return (f'<polyline points="{puntos}" fill="none" stroke="url(#g-pluma)" '
                f'stroke-width="{p["grosor"]}" stroke-linecap="{rem["pluma"]}" '
                f'stroke-linejoin="{geo["union_pluma"]}"{trazo}/>')
    if pieza == "cuerpo":
        c = geo["cuerpo"]
        return f'<circle cx="{c["cx"]}" cy="{c["cy"]}" r="{c["r"]}" fill="url(#g-dot)"/>'
    if pieza in ("ojo_izq", "ojo_der"):
        o = geo["ojos"][pieza == "ojo_der"]
        return (f'<rect x="{o["x"]}" y="{o["y"]}" width="{o["ancho"]}" height="{o["alto"]}" '
                f'rx="{o["radio"]}" fill="{tinta}"/>')
    if pieza in ("feliz_izq", "feliz_der"):
        f = geo["felices"][pieza == "feliz_der"]
        (x, y), (dx1, dy1, dx2, dy2) = f["m"], f["q"]
        return (f'<path d="M{x} {y}q{dx1} {dy1} {dx2} {dy2}" fill="none" stroke="{tinta}" '
                f'stroke-width="{geo["grosor_felices"]}" stroke-linecap="{rem["felices"]}"/>')
    if pieza == "boca":
        x, y, qx, qy, x2, y2 = (_n(v) for v in pose.boca_absoluta())
        return (f'<path d="M{x} {y}Q{qx} {qy} {x2} {y2}" fill="none" stroke="{tinta}" '
                f'stroke-width="{geo["grosor_boca"]}" stroke-linecap="{rem["boca"]}"/>')
    if pieza.startswith("idea") and pieza[-1].isdigit():
        x, y, r = geo["ideas"][int(pieza[-1]) - 1]
        return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color["ambar"]}"/>'
    if pieza.startswith("chispa") and pieza[-1].isdigit():
        segmentos = geo["chispas"][int(pieza[-1]) - 1]
        d = "".join(f"M{x0} {y0}L{x1} {y1}" for (x0, y0), (x1, y1) in segmentos)
        return (f'<path d="{d}" fill="none" stroke="{color["ambar"]}" '
                f'stroke-width="{geo["grosor_chispas"]}" stroke-linecap="{rem["chispas"]}"/>')
    return None


def dot_svg(estado, talla):
    """El SVG del dot en `estado` con la pose en t = 0, a `talla` px (viewBox de 200 × 200).

    Es la misma plantilla del laboratorio (`docs/dot/avatar.html`) pero plana: cada forma lleva
    su `matrix(...)`, la `getCTM()` que da `dot.pose`, en vez de grupos anidados con CSS, que
    librsvg no entiende. La opacidad de cada pieza es el producto con la de sus antepasados:
    solo es válido mientras ningún grupo con opacidad intermedia tenga dos hijos que se tapen
    (en t = 0 las únicas intermedias son los anillos, que son hojas); si no, se niega a dibujar.
    Sin brillo (a estas tallas no hay sombra) y con los colores fijos: el desaturado de `falla`
    va horneado (`_horneado`).
    """
    pose = dot.pose(estado, 0)
    for pieza in dot.PIEZAS:
        if 0 < pose.opacidad[pieza] < 1 and any(dot.PADRE[h] == pieza for h in dot.PIEZAS):
            raise ValueError(f"{estado}: {pieza} tiene opacidad parcial y tiene hijos")
    cuerpo = []
    for pieza in dot.PIEZAS:
        forma = _forma(pose, pieza)
        if forma is None:
            continue
        o = dot.opacidad_visible(pose, pieza)
        if o <= 0:
            continue
        ctm = pose.ctm[pieza]
        extra = "" if ctm == (1, 0, 0, 1, 0, 0) else f' transform="{_matriz(ctm)}"'
        extra += f' opacity="{_n(o)}"' if o < 1 else ""
        cuerpo.append(forma[:-2] + extra + "/>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dot.LIENZO} {dot.LIENZO}" '
            f'width="{talla}" height="{talla}" role="img" aria-label="dot de Cotejo: {estado}">\n'
            f'  <title>dot · {estado}</title>\n'
            f'  <!-- Pose en t = 0 de tareas/dot.py: no se edita a mano, sale de generar.py. -->\n'
            f'  {_degradados(pose)}\n  ' + "\n  ".join(cuerpo) + "\n</svg>\n")


for _estado in dot.ESTADOS:
    for _talla in DOT_TALLAS:
        SALIDAS[DOT_DIR / f"{_estado}-{_talla}.svg"] = (
            lambda e=_estado, t=_talla: dot_svg(e, t))


# Los PNG de la web salen de los SVG de arriba si hay con qué rasterizar (librsvg).
PNG = {
    "logo-icon-512.png": ("logo-icon.svg", 512), "logo-icon-192.png": ("logo-icon.svg", 192),
    "apple-touch-icon.png": ("logo-icon.svg", 180),
    "logo-full.png": ("logo-full.svg", 1200), "logo-full-oscuro.png": ("logo-full-oscuro.svg", 1200),
}


def palabra():
    """Imprime `PALABRA` y su caja con otra fuente o peso. Necesita fontTools:

        python3 -m venv /tmp/ft && /tmp/ft/bin/pip install fonttools
        /tmp/ft/bin/python -c "import generar; generar.palabra()"
    """
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    fuente = instantiateVariableFont(TTFont(RAIZ / "data/fonts/Sora[wght].ttf"), {"wght": 600})
    glifos, mapa = fuente.getGlyphSet(), fuente.getBestCmap()
    corto = lambda v: f"{v:.1f}".rstrip("0").rstrip(".")
    pluma, caja, x = SVGPathPen(glifos, ntos=corto), BoundsPen(glifos), 0
    for letra in "cotejo":
        glifo = glifos[mapa[ord(letra)]]
        for p in (pluma, caja):
            glifo.draw(TransformPen(p, (1, 0, 0, -1, x, 0)))
        x += glifo.width - 10
    print(caja.bounds, fuente["OS/2"].sxHeight)
    print(pluma.getCommands())


def main():
    for ruta, hacer in SALIDAS.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(hacer())
        print(ruta.relative_to(RAIZ))
    if not shutil.which("rsvg-convert"):
        print("Sin rsvg-convert (paquete librsvg): los PNG no se regeneraron.")
        return
    for png, (fuente, ancho) in PNG.items():
        subprocess.run(["rsvg-convert", "-w", str(ancho), "-o", str(WEB / png), str(WEB / fuente)],
                       check=True)
        print((WEB / png).relative_to(RAIZ))


if __name__ == "__main__":
    main()
