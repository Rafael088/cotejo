"""El logo de Cotejo dibujado con cairo, sin pasar por el cargador de SVG de gdk-pixbuf.

`Gdk.Texture.new_from_bytes` con un SVG abre el cargador de pixbuf, y al cerrarlo GIO borra un
archivo temporal por gvfs/dbus (`g_file_delete` → `g_dbus_proxy_call_sync`). Si gvfsd no
contesta, el board se queda sin ventana y sin error. Aquí el SVG del logo (solo `M L H V Q A Z`
en absolutas, un `polyline` y rellenos/trazos lisos) se lee con la biblioteca estándar y se
pinta con cairo en una superficie en memoria: ni pixbuf, ni GIO de archivos, ni librsvg.

Va aparte del widget, como `dot_dibujo`: solo necesita pycairo.
"""

import math
import re
import xml.etree.ElementTree as ET

import cairo

_TOKEN = re.compile(r"[A-Za-z]|-?\d*\.?\d+(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "A": 7, "Z": 0}


def _rgb(hexa):
    hexa = hexa.lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _arco(cr, x0, y0, rx, ry, rot, grande, barrido, x, y):
    """Un arco de SVG (por sus extremos) como un arco de cairo."""
    if rx == 0 or ry == 0 or (x0 == x and y0 == y):
        cr.line_to(x, y)
        return
    fi = math.radians(rot)
    c, s = math.cos(fi), math.sin(fi)
    dx, dy = (x0 - x) / 2, (y0 - y) / 2
    x1, y1 = c * dx + s * dy, -s * dx + c * dy
    rx, ry = abs(rx), abs(ry)
    k = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if k > 1:
        rx, ry = rx * math.sqrt(k), ry * math.sqrt(k)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    f = math.sqrt(max(0.0, num / den)) * (-1 if grande == barrido else 1)
    cx1, cy1 = f * rx * y1 / ry, -f * ry * x1 / rx
    cx = c * cx1 - s * cy1 + (x0 + x) / 2
    cy = s * cx1 + c * cy1 + (y0 + y) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not barrido and dt > 0:
        dt -= 2 * math.pi
    elif barrido and dt < 0:
        dt += 2 * math.pi
    cr.save()
    cr.translate(cx, cy)
    cr.rotate(fi)
    cr.scale(rx, ry)
    if dt > 0:
        cr.arc(0, 0, 1, t1, t1 + dt)
    else:
        cr.arc_negative(0, 0, 1, t1, t1 + dt)
    cr.restore()


def trazar(cr, d):
    """Traza en `cr` el atributo `d` de un path (solo comandos absolutos M L H V Q A Z)."""
    fichas = _TOKEN.findall(d)
    i, cmd, x, y, inicio = 0, None, 0.0, 0.0, (0.0, 0.0)
    while i < len(fichas):
        if fichas[i].isalpha():
            cmd = fichas[i].upper() if fichas[i] in _ARGS else None
            if cmd is None:
                raise ValueError(f"comando de path no soportado: {fichas[i]}")
            i += 1
            if cmd == "Z":
                cr.close_path()
                x, y = inicio
                continue
        n = _ARGS[cmd]
        a = [float(v) for v in fichas[i:i + n]]
        i += n
        if cmd == "M":
            x, y = a
            inicio = (x, y)
            cr.move_to(x, y)
            cmd = "L"   # los pares siguientes de un M son líneas
        elif cmd == "L":
            x, y = a
            cr.line_to(x, y)
        elif cmd == "H":
            x = a[0]
            cr.line_to(x, y)
        elif cmd == "V":
            y = a[0]
            cr.line_to(x, y)
        elif cmd == "Q":
            qx, qy, x2, y2 = a
            cr.curve_to(x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y),
                        x2 + 2 / 3 * (qx - x2), y2 + 2 / 3 * (qy - y2), x2, y2)
            x, y = x2, y2
        elif cmd == "A":
            rx, ry, rot, grande, barrido, x2, y2 = a
            _arco(cr, x, y, rx, ry, rot, int(grande), int(barrido), x2, y2)
            x, y = x2, y2


def _trasladar(attr):
    m = re.match(r"translate\(\s*([-\d.]+)[\s,]+([-\d.]+)\s*\)", attr or "")
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)


def dibujar_logo(cr, svg):
    """Pinta el SVG del logo en `cr` con su viewBox ya mapeado al (0,0)-(ancho, alto) del lienzo."""
    raiz = ET.fromstring(svg)
    for el in raiz.iter():
        etiqueta = el.tag.rsplit("}", 1)[-1]
        if etiqueta not in ("path", "polyline"):
            continue
        cr.save()
        cr.translate(*_trasladar(el.get("transform")))
        cr.new_path()
        if etiqueta == "path":
            trazar(cr, el.get("d", ""))
        else:
            p = [float(v) for v in re.findall(r"-?\d*\.?\d+", el.get("points", ""))]
            cr.move_to(p[0], p[1])
            for j in range(2, len(p) - 1, 2):
                cr.line_to(p[j], p[j + 1])
        relleno, trazo = el.get("fill", "#000000"), el.get("stroke")
        if relleno != "none":
            cr.set_source_rgb(*_rgb(relleno))
            if trazo:
                cr.fill_preserve()
            else:
                cr.fill()
        if trazo:
            cr.set_source_rgb(*_rgb(trazo))
            cr.set_line_width(float(el.get("stroke-width", 1)))
            cr.set_line_cap({"round": cairo.LINE_CAP_ROUND, "square": cairo.LINE_CAP_SQUARE}
                            .get(el.get("stroke-linecap"), cairo.LINE_CAP_BUTT))
            cr.set_line_join({"round": cairo.LINE_JOIN_ROUND, "bevel": cairo.LINE_JOIN_BEVEL}
                             .get(el.get("stroke-linejoin"), cairo.LINE_JOIN_MITER))
            cr.stroke()
        cr.restore()


def rasterizar(svg, ancho):
    """El logo como `ImageSurface` ARGB32 de `ancho` px (el alto sale del viewBox)."""
    raiz = ET.fromstring(svg)
    x0, y0, w, h = (float(v) for v in raiz.get("viewBox").split())
    alto = max(1, round(ancho * h / w))
    superficie = cairo.ImageSurface(cairo.FORMAT_ARGB32, ancho, alto)
    cr = cairo.Context(superficie)
    cr.scale(ancho / w, alto / h)
    cr.translate(-x0, -y0)
    dibujar_logo(cr, svg)
    superficie.flush()
    return superficie
