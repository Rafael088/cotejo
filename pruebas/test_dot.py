"""El núcleo del dot (cotejo-18bc08): `tareas/dot.py` contra los números de Chromium.

Sin GTK ni cairo. Recorre todas las muestras de `pruebas/oro/dot/oro.json` (reposo, entrada y
mitad de cada transición) y compara la matriz de cada pieza, la boca, las opacidades, los trazos
y el filtro con tolerancia 0,001 en unidades del lienzo. Lo que queda por debajo es ruido del
propio oro: Skia calcula las matrices en float32 (~1e-5) y Chromium escribe el `d` calculado con
seis cifras significativas (`135.972`, hasta 5e-4).
"""

import json
import math
import os
import re
import subprocess
import sys
import unittest

import apoyo  # noqa: F401  (pone la raíz del proyecto en el path)

from tareas import dot

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORO = os.path.join(RAIZ, "pruebas", "oro", "dot", "oro.json")
TOLERANCIA = 1e-3


def cargar_oro():
    with open(ORO, encoding="utf-8") as f:
        return json.load(f)


def pose_de(muestra):
    """La pose que corresponde a una muestra del oro, como la midió `herramientas/dot_oro.py`:
    en las transiciones, el dot estaba en el estado de origen con sus animaciones en t = 0 y
    todo (animaciones nuevas y transiciones) corre `t` segundos desde el cambio."""
    if muestra["tipo"] == "transicion":
        return dot.pose(muestra["estado"], muestra["t"], desde=dot.pose(muestra["desde"], 0))
    return dot.pose(muestra["estado"], muestra["t"])


def diferencias(muestra, p):
    """[(error, qué)] de una muestra: un error de 1 es que algo está y no debería (o al revés)."""
    errores = []
    for nombre, g in muestra["piezas"].items():
        errores.append((max(abs(a - b) for a, b in zip(p.ctm[nombre], g["ctm"])), f"{nombre}.ctm"))
        errores.append((abs(p.opacidad[nombre] - g["opacidad"]), f"{nombre}.opacidad"))
        oro_trazo, trazo = g.get("trazo"), p.trazo.get(nombre)
        if (oro_trazo is None) != (trazo is None):
            errores.append((1, f"{nombre}.trazo {trazo} ≠ {oro_trazo}"))
        elif oro_trazo:
            guiones, oro_guiones = trazo[0], oro_trazo["dasharray"]
            if (guiones is None) != (oro_guiones is None) or (
                    guiones and list(guiones) != [float(x) for x in oro_guiones]):
                errores.append((1, f"{nombre}.dasharray {guiones} ≠ {oro_guiones}"))
            errores.append((abs(trazo[1] - oro_trazo["dashoffset"]), f"{nombre}.dashoffset"))
        oro_filtro, filtro = g.get("filtro"), p.filtro.get(nombre)
        if isinstance(oro_filtro, str):      # el brillo de la piel: va aparte
            continue
        if (oro_filtro is None) != (filtro is None):
            errores.append((1, f"{nombre}.filtro {filtro} ≠ {oro_filtro}"))
        elif oro_filtro:
            errores.append((max(abs(filtro[0] - oro_filtro["saturacion"]),
                                abs(filtro[1] - oro_filtro["brillo"])), f"{nombre}.filtro"))
        if nombre == "boca":
            numeros = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", g["d"])]
            errores.append((max(abs(a - b) for a, b in zip(p.boca_absoluta(), numeros)), "boca.d"))
    return errores


class ContraElOro(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oro = cargar_oro()

    def test_todas_las_muestras_igual_que_chromium(self):
        peor = (0, "")
        for m in self.oro["muestras"]:
            p = pose_de(m)
            for error, que in diferencias(m, p):
                peor = max(peor, (error, f"{m['id']} {que}"))
                with self.subTest(muestra=m["id"], que=que):
                    self.assertLessEqual(error, TOLERANCIA)
        self.assertLessEqual(peor[0], TOLERANCIA, peor[1])

    def test_estan_todos_los_tipos_de_muestra(self):
        tipos = {m["tipo"] for m in self.oro["muestras"]}
        self.assertEqual(tipos, {"reposo", "entrada", "transicion"})
        self.assertEqual(len([m for m in self.oro["muestras"] if m["tipo"] == "transicion"]), 12)

    def test_cada_muestra_tiene_las_mismas_piezas_que_la_pose(self):
        for m in self.oro["muestras"]:
            self.assertEqual(set(m["piezas"]), set(dot.PIEZAS), m["id"])

    def test_el_brillo_de_la_piel_es_el_de_la_geometria(self):
        s = dot.GEOMETRIA["sombra"]
        r, g, b = s["color"]
        esperado = f"drop-shadow(rgba({r}, {g}, {b}, {s['alfa']}) 0px 0px {s['radio']}px)"
        for m in self.oro["muestras"]:
            self.assertEqual(m["piezas"]["piel"]["filtro"], esperado, m["id"])

    def test_los_origenes_son_los_del_navegador(self):
        """`origen` del oro va en px del lienzo, salvo las chispas (fill-box: px de su caja)."""
        m = next(x for x in self.oro["muestras"] if x["id"] == "celebra@0.9")
        for nombre, (ox, oy) in dot.ORIGEN.items():
            pieza = m["piezas"][nombre]
            if "origen" not in pieza:
                continue
            x, y = (float(v.rstrip("px")) for v in pieza["origen"].split())
            if nombre.startswith("chispa"):
                caja = dot.GEOMETRIA["chispas"][int(nombre[-1]) - 1]
                x += min(px for s in caja for px, _ in s)
                y += min(py for s in caja for _, py in s)
            self.assertAlmostEqual(x, ox, msg=nombre)
            self.assertAlmostEqual(y, oy, msg=nombre)


def bisectar(c, x):
    """Referencia lenta: y(t) con t de una bisección de 200 pasos sobre x(t)."""
    x1, y1, x2, y2 = c.puntos

    def coord(p1, p2, t):
        return 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3

    bajo, alto = 0.0, 1.0
    for _ in range(200):
        medio = (bajo + alto) / 2
        if coord(x1, x2, medio) < x:
            bajo = medio
        else:
            alto = medio
    return coord(y1, y2, (bajo + alto) / 2)


class Bezier(unittest.TestCase):
    CURVAS = ("ease", "ease-in", "ease-out", "ease-in-out", "cubic-bezier(0.3, 0, 0.2, 1)",
              "cubic-bezier(0.3, 1.35, 0.5, 1)", "cubic-bezier(0.5, 0, 0.8, 0.6)",
              "cubic-bezier(0.33, 0, 0.15, 1)")

    def test_valores_conocidos(self):
        self.assertAlmostEqual(dot.curva("ease")(0.5), 0.8024033877399112, places=6)
        self.assertAlmostEqual(dot.curva("ease-in-out")(0.5), 0.5, places=9)
        self.assertAlmostEqual(dot.curva("ease-in")(0.5), 0.3153568, places=6)
        self.assertAlmostEqual(dot.curva("ease-out")(0.5), 0.6846432, places=6)
        self.assertIsNone(dot.curva("linear"))
        self.assertEqual(dot.aplicar(dot.curva("linear"), 0.37), 0.37)

    def test_extremos(self):
        for nombre in self.CURVAS:
            c = dot.curva(nombre)
            self.assertAlmostEqual(c(0), 0, places=9, msg=nombre)
            self.assertAlmostEqual(c(1), 1, places=9, msg=nombre)

    def test_igual_que_una_biseccion_lenta(self):
        for nombre in self.CURVAS:
            c = dot.curva(nombre)
            for i in range(1, 400):
                x = i / 400
                self.assertAlmostEqual(c(x), bisectar(c, x), places=6, msg=f"{nombre} en {x}")

    def test_ease_in_out_es_simetrica(self):
        c = dot.curva("ease-in-out")
        for i in range(21):
            x = i / 20
            self.assertAlmostEqual(c(x) + c(1 - x), 1, places=7)

    def test_la_entrada_se_pasa_y_vuelve(self):
        c = dot.curva(dot.ENTRADA.curva)
        self.assertGreater(max(c(i / 100) for i in range(101)), 1.04)

    def test_fuera_de_rango_extrapola_con_la_pendiente(self):
        c = dot.bezier(0.25, 0.1, 0.25, 1)
        self.assertAlmostEqual(c(-0.5), -0.5 * 0.1 / 0.25)
        self.assertAlmostEqual(c(1.5), 1.0)

    def test_curva_desconocida(self):
        with self.assertRaises(ValueError):
            dot.curva("steps(4)")

    def test_viaje(self):
        self.assertEqual(dot.VIAJE.duracion, 0.9)
        self.assertEqual(dot.VIAJE.curva.puntos, (0.33, 0, 0.15, 1))
        self.assertEqual(dot.viaje(0), 0)
        self.assertAlmostEqual(dot.viaje(0.9), 1)
        self.assertEqual(dot.viaje(5), 1)
        self.assertAlmostEqual(dot.viaje(0.45), bisectar(dot.VIAJE.curva, 0.5), places=6)


class Matrices(unittest.TestCase):
    def cerca(self, m, n, places=9):
        for a, b in zip(m, n):
            self.assertAlmostEqual(a, b, places=places)

    def test_descomponer_y_recomponer_es_la_identidad(self):
        for funciones in ("rotate(30deg) scale(1.2, 0.7)", "translate(5px, -3px) rotate(-100deg)",
                          "scale(-1, 1)", "rotate(10deg) scale(2, 1) rotate(20deg)", "none"):
            m = dot.matriz_de(dot.leer_transform(funciones))
            self.cerca(dot.recomponer(*dot.descomponer(m)), m)

    def test_funciones_iguales_se_interpolan_una_a_una(self):
        """Un giro de 0 a 360° pasa por 180° (como matriz se quedaría quieto)."""
        lista = dot.interpolar_transform((), dot.leer_transform("rotate(360deg)"), 0.5)
        self.assertEqual(lista, (("rotate", 180.0),))

    def test_funciones_distintas_se_interpolan_como_matriz(self):
        lista = dot.interpolar_transform(dot.leer_transform("translate(4px, 0)"),
                                         dot.leer_transform("scaleY(0.1)"), 0.5)
        self.assertEqual(lista[0][0], "matrix")
        self.cerca(dot.matriz_de(lista), (1, 0, 0, 0.55, 2, 0))

    def test_prefijo_comun_y_resto_como_matriz(self):
        lista = dot.interpolar_transform(dot.leer_transform("rotate(10deg) scale(2)"),
                                         dot.leer_transform("rotate(30deg) translate(4px, 0)"), 0.5)
        self.assertEqual(lista[0], ("rotate", 20.0))
        self.assertEqual(lista[1][0], "matrix")

    def test_el_origen_va_en_el_lienzo(self):
        m = dot.sobre_origen(dot.matriz_de(dot.leer_transform("scale(2)")), (100, 176))
        self.cerca(m, (2, 0, 0, 2, -100, -176))


class Pose(unittest.TestCase):
    def test_tiene_las_21_piezas(self):
        p = dot.pose("idle", 0)
        self.assertEqual(len(dot.PIEZAS), 21)
        for campo in (p.ctm, p.opacidad):
            self.assertEqual(set(campo), set(dot.PIEZAS))
        self.assertEqual(len(p.boca), 6)

    def test_piensa_no_se_porta(self):
        self.assertNotIn("piensa", dot.ESTADOS)
        with self.assertRaises(ValueError):
            dot.pose("piensa", 0)

    def test_la_entrada_acaba_en_idle(self):
        for t in (0.76, 1.3, 4.0):
            a, b = dot.pose("entrada", t), dot.pose("idle", t)
            for pieza in dot.PIEZAS:
                for x, y in zip(a.ctm[pieza], b.ctm[pieza]):
                    self.assertAlmostEqual(x, y, places=9)
                self.assertEqual(a.opacidad[pieza], b.opacidad[pieza])

    def test_el_cambio_no_salta_en_lo_que_transiciona(self):
        """En el instante del cambio, lo que transiciona sigue donde estaba."""
        for origen in dot.ESTADOS:
            for destino in dot.ESTADOS:
                if origen == destino:
                    continue
                antes = dot.pose(origen, 1.1)
                despues = dot.pose(destino, 0, desde=antes)
                with self.subTest(origen=origen, destino=destino):
                    for x, y in zip(antes.boca, despues.boca):
                        self.assertAlmostEqual(x, y, places=9)
                    self.assertTrue(despues.transiciones)

    def test_lo_que_venia_de_un_keyframes_salta(self):
        """De idle a falla los ojos y el mechón saltan aunque falla declare su transición."""
        p = dot.pose("falla", 0.05, desde=dot.pose("idle", 1.0))
        self.assertNotIn(("ojos", "transform"), p.transiciones)
        self.assertNotIn(("pluma", "transform"), p.transiciones)
        self.assertIn(("mundo", "transform"), p.transiciones)

    def test_lo_que_venia_quieto_transiciona(self):
        """De comprobar (ojos quietos en scale(1.14)) a falla, los ojos sí transicionan 400 ms."""
        antes = dot.pose("comprobar", 1.0)
        p = dot.pose("falla", 0.2, desde=antes)
        self.assertIn(("ojos", "transform"), p.transiciones)
        fija = dot.pose("falla", 0.2)
        self.assertNotAlmostEqual(p.ctm["ojos"][3], fija.ctm["ojos"][3], places=3)
        self.assertAlmostEqual(dot.pose("falla", 0.45, desde=antes).ctm["ojos"][3],
                               dot.pose("falla", 0.45).ctm["ojos"][3], places=9)

    def test_las_animaciones_que_siguen_no_vuelven_a_empezar(self):
        """`respira` sigue en el cuerpo de idle a falla: su reloj continúa, no empieza en 0."""
        p = dot.pose("falla", 0.5, desde=dot.pose("idle", 1.0))
        self.assertEqual(p.relojes["cuerpo"], ("respira", 1.5))
        q = dot.pose("trabaja", 0.5, desde=dot.pose("idle", 1.0))
        self.assertEqual(q.relojes["ojos"], ("oficio", 0.5))

    def test_encadenar_mantiene_la_transicion_en_marcha(self):
        """Volver al mismo destino a mitad de transición no la reinicia."""
        a = dot.pose("falla", 0.1, desde=dot.pose("idle", 0))
        b = dot.pose("falla", 0.1, desde=a)
        c = dot.pose("falla", 0.2, desde=dot.pose("idle", 0))
        self.assertAlmostEqual(b.ctm["mundo"][5], c.ctm["mundo"][5], places=9)

    def test_darse_la_vuelta_acorta_la_transicion(self):
        """De idle a falla y, a mitad, de vuelta a idle: el filtro vuelve en menos de 400 ms."""
        ida = dot.pose("falla", 0.1, desde=dot.pose("idle", 0))
        vuelta = dot.pose("idle", 0, desde=ida)
        tr = vuelta.transiciones[("cuerpo", "filter")]
        self.assertLess(tr.duracion, 0.4)
        self.assertGreater(tr.duracion, 0)
        self.assertNotIn(("cuerpo", "filter"), dot.pose("idle", tr.duracion + 0.01, desde=ida).filtro)

    def test_una_transicion_que_el_destino_no_declara_se_corta(self):
        ida = dot.pose("falla", 0.1, desde=dot.pose("idle", 0))
        p = dot.pose("trabaja", 0, desde=ida)
        self.assertNotIn(("mundo", "transform"), p.transiciones)

    def test_movimiento_reducido(self):
        p = dot.pose("trabaja", 0.7, quieto=True)
        self.assertEqual(p.opacidad["halo1"], dot.QUIETO_HALO)
        self.assertEqual(p.relojes, {})
        self.assertEqual(p.ctm["halo1"], dot.IDENTIDAD)
        self.assertEqual(p.ctm["cuerpo"], dot.IDENTIDAD)
        q = dot.pose("celebra", 0.1, desde=dot.pose("idle", 0, quieto=True), quieto=True)
        self.assertEqual(set(q.transiciones) - {(k, "opacity") for k in dot.PIEZAS}, set())
        self.assertGreater(q.opacidad["ojos"], 0)


class SinGtk(unittest.TestCase):
    def test_se_importa_sin_gi_ni_cairo(self):
        """El núcleo se usa donde no hay GTK (generador de SVG, CI): no puede importarlo."""
        codigo = (
            "import sys\n"
            "class Bloqueo:\n"
            "    def find_spec(self, nombre, ruta=None, objetivo=None):\n"
            "        if nombre.split('.')[0] in ('gi', 'cairo'):\n"
            "            raise ImportError('bloqueado: ' + nombre)\n"
            "sys.meta_path.insert(0, Bloqueo())\n"
            "from tareas import dot\n"
            "print(round(dot.pose('celebra', 0.3).ctm['mundo'][5], 3))\n"
        )
        r = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "-17.667")


if __name__ == "__main__":
    unittest.main()
