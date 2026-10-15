"""Dibuja los iconos de CotejoBoard y los deja como relleno, no como trazo.

Por qué existe este archivo en vez de 30 SVG escritos a mano: GTK, al cargar un icono
simbólico, le fuerza el `fill` a la letra `color` del CSS y **descarta el `stroke`**. Un
icono dibujado con trazo —que es como se piensa y como lo pide el diseño (24 px, grosor
1,75, puntas redondas)— le llega a GTK como un polígono relleno: una palomita se convierte
en un triángulo macizo. Comprobado con tres variantes antes de escribir esto.

La salida, en cambio, tiene que seguir recoloreándose sola: el diseño pinta el mismo icono
de plata, de verde o de ámbar según dónde esté, y eso solo lo da el CSS. Así que aquí los
iconos se declaran con trazos —que es como se editan— y se emiten con el trazo ya
convertido en contorno relleno, que es lo único que GTK respeta.

Para volver a generarlos después de tocar un icono:

    python3 data/iconos/generar.py

Las figuras se unen por regla «nonzero»: todas van en el mismo sentido y se suman, salvo
las que llevan `hueco=True`, que van al revés y restan —así se cala una palomita dentro de
un disco—. Las puntas redondas son un círculo en cada extremo, que además redondea las
uniones sin tener que calcular el inglete.
"""

import math
from pathlib import Path

GROSOR = 1.75          # el que pide el diseño
R = GROSOR / 2         # media anchura del trazo
DESTINO = Path(__file__).resolve().parent / "hicolor" / "scalable" / "actions"
TOLERANCIA = 0.02      # flecha máxima al aplanar una curva, en unidades del lienzo de 24


def _lados(radio):
    """Cuántos segmentos necesita un círculo de este radio para verse redondo."""
    if radio <= 0:
        return 3
    # Flecha de un polígono regular: r(1 - cos(pi/n)). Se despeja n y se acota.
    paso = math.acos(max(-1.0, 1 - TOLERANCIA / radio))
    return max(8, min(96, math.ceil(math.pi / paso)))


def _area(puntos):
    total = 0.0
    for (x1, y1), (x2, y2) in zip(puntos, puntos[1:] + puntos[:1]):
        total += x1 * y2 - x2 * y1
    return total / 2


def _camino(puntos, hueco=False):
    """Un polígono cerrado, orientado para sumar (o para restar, si es hueco)."""
    if len(puntos) < 3:
        return ""
    if (_area(puntos) > 0) == bool(hueco):
        puntos = list(reversed(puntos))
    partes = [f"M{puntos[0][0]:.3f} {puntos[0][1]:.3f}"]
    partes += [f"L{x:.3f} {y:.3f}" for x, y in puntos[1:]]
    return "".join(partes) + "Z"


def _circulo(centro, radio, hueco=False):
    cx, cy = centro
    n = _lados(radio)
    puntos = [(cx + radio * math.cos(2 * math.pi * i / n),
               cy + radio * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return _camino(puntos, hueco)


def _arco_puntos(centro, radio, desde, hasta):
    cx, cy = centro
    n = max(2, _lados(radio) * abs(hasta - desde) // 360 + 2)
    return [(cx + radio * math.cos(math.radians(desde + (hasta - desde) * i / n)),
             cy + radio * math.sin(math.radians(desde + (hasta - desde) * i / n)))
            for i in range(int(n) + 1)]


# --- figuras que se declaran en los iconos -----------------------------------

def linea(p1, p2, hueco=False):
    """Un segmento de trazo con las dos puntas redondas."""
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    largo = math.hypot(dx, dy)
    if largo < 1e-9:
        return [_circulo(p1, R, hueco)]
    nx, ny = -dy / largo * R, dx / largo * R
    cuerpo = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
    return [_camino(cuerpo, hueco), _circulo(p1, R, hueco), _circulo(p2, R, hueco)]


def polilinea(puntos, hueco=False):
    caminos = []
    for p1, p2 in zip(puntos, puntos[1:]):
        caminos += linea(p1, p2, hueco)
    return caminos


def disco(centro, radio, hueco=False):
    return [_circulo(centro, radio, hueco)]


def anillo(centro, radio):
    """Un círculo dibujado con trazo: relleno por fuera, hueco por dentro."""
    return [_circulo(centro, radio + R), _circulo(centro, radio - R, hueco=True)]


def arco(centro, radio, desde, hasta):
    """Un trozo de circunferencia con trazo, con las puntas redondas."""
    fuera = _arco_puntos(centro, radio + R, desde, hasta)
    dentro = _arco_puntos(centro, radio - R, desde, hasta)
    cx, cy = centro
    extremos = [(cx + radio * math.cos(math.radians(a)), cy + radio * math.sin(math.radians(a)))
                for a in (desde, hasta)]
    return [_camino(fuera + list(reversed(dentro)))] + [_circulo(p, R) for p in extremos]


def rect(x, y, ancho, alto, radio=0):
    """Un rectángulo de esquinas redondeadas, dibujado con trazo."""
    def contorno(r_esq, desfase):
        e = max(0.01, r_esq)
        centros = [(x + ancho - e, y + alto - e, 0, 90), (x + e, y + alto - e, 90, 180),
                   (x + e, y + e, 180, 270), (x + ancho - e, y + e, 270, 360)]
        puntos = []
        for cx, cy, a0, a1 in centros:
            puntos += _arco_puntos((cx, cy), max(0.01, e + desfase), a0, a1)
        return puntos
    return [_camino(contorno(radio, R)), _camino(contorno(radio, -R), hueco=True)]


def barra(x, abajo, alto):
    """Una barra vertical de señal, con las puntas redondas."""
    return linea((x, abajo), (x, abajo - alto))


def trazo_solido(puntos, grosor=GROSOR, hueco=False):
    """Un trazo como un único polígono, con las uniones en inglete y las puntas rectas.

    `linea()` monta cada trazo con tres piezas que se pisan (el cuerpo y un círculo por
    punta). Sumando da igual, pero restando no: dos piezas negativas encima de un relleno
    dejan -1, que para la regla «nonzero» sigue siendo relleno, y el hueco aparece a
    medio calar. Lo que se cala tiene que ser una sola pieza que no se pise, y eso es esto.
    """
    h = grosor / 2
    normales, direcciones = [], []
    for (x1, y1), (x2, y2) in zip(puntos, puntos[1:]):
        largo = math.hypot(x2 - x1, y2 - y1) or 1.0
        d = ((x2 - x1) / largo, (y2 - y1) / largo)
        direcciones.append(d)
        normales.append((-d[1], d[0]))

    def borde(signo):
        lado = [(puntos[0][0] + signo * normales[0][0] * h,
                 puntos[0][1] + signo * normales[0][1] * h)]
        for i in range(1, len(puntos) - 1):
            n1, n2 = normales[i - 1], normales[i]
            coseno = n1[0] * n2[0] + n1[1] * n2[1]
            if 1 + coseno < 1e-6:          # giro de 180°: no hay inglete posible
                lado.append((puntos[i][0] + signo * n1[0] * h, puntos[i][1] + signo * n1[1] * h))
                continue
            factor = h / (1 + coseno)
            lado.append((puntos[i][0] + signo * (n1[0] + n2[0]) * factor,
                         puntos[i][1] + signo * (n1[1] + n2[1]) * factor))
        lado.append((puntos[-1][0] + signo * normales[-1][0] * h,
                     puntos[-1][1] + signo * normales[-1][1] * h))
        return lado

    return [_camino(borde(1) + list(reversed(borde(-1))), hueco)]


def punta(p, angulo, largo=3.4, apertura=38):
    """La cabeza de una flecha: dos barbas que salen del vértice hacia atrás."""
    caminos = []
    for lado in (+1, -1):
        a = math.radians(angulo + 180 - lado * apertura)
        caminos += linea(p, (p[0] + largo * math.cos(a), p[1] + largo * math.sin(a)))
    return caminos


def estrella(centro, puntas, r_ext, r_int, giro=-90):
    cx, cy = centro
    pasos = puntas * 2
    puntos = []
    for i in range(pasos):
        r = r_ext if i % 2 == 0 else r_int
        a = math.radians(giro + 360 * i / pasos)
        puntos.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return [_camino(puntos)]


def semidisco(centro, radio, desde, hasta):
    return [_camino(_arco_puntos(centro, radio, desde, hasta) + [centro])]


# --- los 30 iconos -----------------------------------------------------------
# Lienzo de 24×24. El dibujo se queda entre 3 y 21 para que nada toque el borde.

def _iconos():
    return {
        # Recargar gira como el reloj y deshacer al revés: son el mismo arco en espejo,
        # que es lo que los deja distinguirse de un vistazo estando uno al lado del otro.
        "recargar": arco((12, 12), 6.3, -40, 240) + punta((8.85, 6.54), -30),
        "mas": disco((12, 6.2), 1.55) + disco((12, 12), 1.55) + disco((12, 17.8), 1.55),
        "buscar": anillo((10.6, 10.6), 5.1) + linea((14.4, 14.4), (19, 19)),
        # Embudo: la barra ancha de arriba es todo, y se va angostando hasta el tallo de
        # abajo, que es lo que queda tras filtrar.
        "filtro": (linea((4.6, 6.2), (19.4, 6.2)) + linea((4.6, 6.2), (12, 13.6))
                   + linea((19.4, 6.2), (12, 13.6)) + barra(12, 18.8, 5.2)),
        "tablero": (rect(3.5, 5, 17, 14, 2.5) + linea((9.2, 5), (9.2, 19))
                    + linea((14.8, 5), (14.8, 19))),
        "lateral": rect(3.5, 5, 17, 14, 2.5) + linea((9.6, 5), (9.6, 19)),
        # Dos flechas que caen sobre una línea: contraer es juntar, no cruzar.
        "contraer": (linea((4.4, 12), (19.6, 12))
                     + polilinea([(8.4, 5.6), (12, 9.2), (15.6, 5.6)])
                     + polilinea([(8.4, 18.4), (12, 14.8), (15.6, 18.4)])),
        "cerrar": linea((7.2, 7.2), (16.8, 16.8)) + linea((16.8, 7.2), (7.2, 16.8)),
        "flecha-izquierda": linea((19, 12), (5.6, 12)) + punta((5.6, 12), 180),
        "flecha-derecha": linea((5, 12), (18.4, 12)) + punta((18.4, 12), 0),
        # Chispa: lo que marca que detrás de la tarea hay un modelo y no una persona.
        "agente": estrella((12, 12), 4, 7.8, 3.7),
        "persona": anillo((12, 8.9), 2.9) + arco((12, 19.6), 5.7, 200, 340),
        # Nadie la tiene: el mismo círculo de una persona, pero sin cerrar.
        "sin-agente": (arco((12, 12), 6.3, -75, 15) + arco((12, 12), 6.3, 45, 135)
                       + arco((12, 12), 6.3, 165, 255)),
        "dificultad-facil": barra(7.2, 17.6, 4.2),
        "dificultad-medio": barra(7.2, 17.6, 4.2) + barra(12, 17.6, 7.6),
        "dificultad-dificil": (barra(7.2, 17.6, 4.2) + barra(12, 17.6, 7.6)
                               + barra(16.8, 17.6, 11)),
        "estado-pendiente": anillo((12, 12), 6.4),
        "estado-en-curso": anillo((12, 12), 6.4) + disco((12, 12), 3.1),
        "estado-por-validar": (anillo((12, 12), 6.4)
                               + polilinea([(8.8, 12.2), (11, 14.4), (15.3, 9.4)])),
        # Finalizada es el único icono macizo: la palomita va calada dentro del disco.
        "estado-hecha": (disco((12, 12), 7.4)
                         + trazo_solido([(8.5, 12.2), (10.9, 14.7), (15.5, 9.2)], hueco=True)),
        "evidencia": (rect(5, 3.4, 14, 17.2, 2.2)
                      + polilinea([(8.6, 12.4), (11, 14.8), (15.4, 9.6)])),
        "devuelta": (polilinea([(17.5, 7.4), (17.5, 13.6), (7.6, 13.6)])
                     + punta((7.6, 13.6), 180)),
        "abrir": (rect(3.6, 8, 11.6, 11.6, 2.2) + linea((13, 11), (19.4, 4.6))
                  + punta((19.4, 4.6), -45)),
        "deshacer": arco((12, 12), 6.3, 220, -60) + punta((15.15, 6.54), -150),
        "teclado": (rect(2.8, 6.8, 18.4, 10.4, 2.2) + disco((6.6, 11), 0.95)
                    + disco((9.7, 11), 0.95) + disco((12.8, 11), 0.95)
                    + disco((15.9, 11), 0.95) + linea((8.4, 14.3), (15.6, 14.3))),
        # Medio disco lleno: el mismo círculo cambia de mitad al cambiar de tema.
        "tema": anillo((12, 12), 6.4) + semidisco((12, 12), 5.6, -90, 90),
        # Aviso: lo que está roto, no lo que está vacío. Triángulo y no círculo para que no
        # se confunda con los cuatro estados, que son todos redondos; va siempre en ámbar.
        "aviso": (polilinea([(12, 4.4), (20.2, 18.9), (3.8, 18.9), (12, 4.4)])
                  + linea((12, 9.8), (12, 13.4)) + disco((12, 16.1), 1.05)),
        # Bandeja vacía: es lo que se ve cuando una columna no tiene nada.
        "vacio": (rect(3.5, 5.5, 17, 13, 2.5)
                  + polilinea([(3.5, 14), (8.8, 14), (10.2, 16.3), (13.8, 16.3),
                               (15.2, 14), (20.5, 14)])),
    }


PLANTILLA = ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
             'viewBox="0 0 24 24"><path d="{d}"/></svg>\n')


def escribir():
    DESTINO.mkdir(parents=True, exist_ok=True)
    iconos = _iconos()
    for nombre, caminos in iconos.items():
        d = "".join(c for c in caminos if c)
        (DESTINO / f"cotejo-{nombre}-symbolic.svg").write_text(PLANTILLA.format(d=d))
    return sorted(iconos)


if __name__ == "__main__":
    nombres = escribir()
    print(f"{len(nombres)} iconos en {DESTINO}")
