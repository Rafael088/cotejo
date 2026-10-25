"""La señal de vida del agente (cotejo-21y2ah): umbrales, textos y la fuente del último
movimiento. Sin GTK."""

import os
import tempfile
import unittest
from unittest import mock

import apoyo  # noqa: F401

from tareas import lanzados, senal_vida as sv

AHORA = 10_000.0


def registro(**extra):
    base = {"id": "cotejo-x", "fase": lanzados.LANZADO, "pid": 1, "modelo": "sonnet",
            "ts": int(AHORA - 300)}
    base.update(extra)
    return base


def vivo():
    return mock.patch.object(lanzados, "_muerto", return_value=False)


class Niveles(unittest.TestCase):
    def test_umbrales(self):
        self.assertEqual(sv.nivel(0), sv.ACTIVO)
        self.assertEqual(sv.nivel(119), sv.ACTIVO)
        self.assertEqual(sv.nivel(120), sv.PENSANDO)
        self.assertEqual(sv.nivel(599), sv.PENSANDO)
        self.assertEqual(sv.nivel(600), sv.COLGADO)
        self.assertEqual(sv.nivel(5, vivo=False), sv.COLGADO)

    def test_duracion(self):
        self.assertEqual(sv.duracion(45), "45 s")
        self.assertEqual(sv.duracion(180), "3 min")
        self.assertEqual(sv.duracion(3900), "1 h 05 min")
        self.assertEqual(sv.duracion(-3), "0 s")


class Evaluar(unittest.TestCase):
    def test_trabajando(self):
        with vivo():
            s = sv.evaluar(registro(), AHORA, movimiento=AHORA - 30)
        self.assertEqual(s["nivel"], sv.ACTIVO)
        self.assertTrue(s["animar"])
        self.assertEqual(s["titulo"], "Trabajando")
        self.assertIn("Lleva 5 min", s["detalle"])
        self.assertIn("hace 30 s", s["detalle"])
        self.assertEqual(s["ayuda"], "")

    def test_pensando(self):
        with vivo():
            s = sv.evaluar(registro(), AHORA, movimiento=AHORA - 300)
        self.assertEqual(s["nivel"], sv.PENSANDO)
        self.assertTrue(s["animar"])
        self.assertIn("pensando", s["titulo"])

    def test_colgado_por_silencio_dice_que_hacer(self):
        with vivo():
            s = sv.evaluar(registro(), AHORA, movimiento=AHORA - 700)
        self.assertEqual(s["nivel"], sv.COLGADO)
        self.assertFalse(s["animar"])
        self.assertIn("Pendiente", s["ayuda"])

    def test_proceso_muerto_es_colgado_aunque_acabe_de_escribir(self):
        with mock.patch.object(lanzados, "_muerto", return_value=True):
            s = sv.evaluar(registro(), AHORA, movimiento=AHORA - 2)
        self.assertEqual(s["nivel"], sv.COLGADO)
        self.assertFalse(s["animar"])
        self.assertIn("ya no existe", s["titulo"])
        self.assertIn("retomarla", s["ayuda"])

    def test_sin_senal_cuando_no_esta_trabajando(self):
        for fase in (lanzados.TERMINADO, lanzados.DETENIDO, lanzados.EN_ESPERA):
            self.assertIsNone(sv.evaluar(registro(fase=fase), AHORA, movimiento=AHORA))
        self.assertIsNone(sv.evaluar(None))

    def test_sin_log_cuenta_desde_el_lanzamiento(self):
        with vivo():
            s = sv.evaluar(registro(log="/no/existe.log"), AHORA)
        self.assertEqual(s["silencio"], 300)
        self.assertEqual(s["nivel"], sv.PENSANDO)


class UltimoMovimiento(unittest.TestCase):
    def test_sale_del_mtime_del_log(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "a.log")
            open(log, "w").close()
            os.utime(log, (1234, 1234))
            self.assertEqual(sv.ultimo_movimiento({"log": log, "ts": 5}), 1234)

    def test_sin_log_usa_ts_y_sin_nada_none(self):
        self.assertEqual(sv.ultimo_movimiento({"ts": 77}), 77.0)
        self.assertIsNone(sv.ultimo_movimiento({}))


if __name__ == "__main__":
    unittest.main()
