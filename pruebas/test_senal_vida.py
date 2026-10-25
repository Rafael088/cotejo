"""La señal de vida del agente (cotejo-21y2ah): umbrales, textos, qué está haciendo según su
log y la fuente del último movimiento. Sin GTK. Un agente vivo nunca es «colgado»."""

import json
import os
import tempfile
import unittest
from unittest import mock

import apoyo  # noqa: F401

from tareas import lanzados, senal_vida as sv

AHORA = 10_000.0
RAIZ = "/trabajo/wt/cotejo-x"


def registro(**extra):
    base = {"id": "cotejo-x", "fase": lanzados.LANZADO, "pid": 1, "modelo": "sonnet",
            "ts": int(AHORA - 300)}
    base.update(extra)
    return base


def vivo():
    return mock.patch.object(lanzados, "_muerto", return_value=False)


def herramienta(nombre, **entrada):
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": nombre, "input": entrada}]}})


def texto(dice):
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": dice}]}})


def resultado():
    return json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "content": "ok"}]}})


# Un log de ejemplo de `claude -p --output-format stream-json --verbose`.
LOG = "\n".join([
    json.dumps({"type": "system", "subtype": "init", "model": "claude-sonnet"}),
    texto("Voy a mirar el repo."),
    herramienta("Read", file_path=f"{RAIZ}/tareas/app/detalle.py"),
    resultado(),
    herramienta("Edit", file_path=f"{RAIZ}/tareas/app/lanzar.py", old_string="a", new_string="b"),
    resultado(),
]) + "\n"


class Niveles(unittest.TestCase):
    def test_umbrales_solo_activo_y_pensando(self):
        self.assertEqual(sv.nivel(0), sv.ACTIVO)
        self.assertEqual(sv.nivel(119), sv.ACTIVO)
        self.assertEqual(sv.nivel(120), sv.PENSANDO)
        self.assertEqual(sv.nivel(100_000), sv.PENSANDO)      # jamás «colgado»

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
        self.assertFalse(s["retomar"])
        self.assertEqual(s["titulo"], "Trabajando")
        self.assertEqual(s["detalle"], "Lleva 5 min · último movimiento hace 30 s")

    def test_mucho_sin_escribir_dice_pensando_sin_alarma(self):
        with vivo():
            s = sv.evaluar(registro(), AHORA, movimiento=AHORA - 3000)
        self.assertEqual(s["nivel"], sv.PENSANDO)
        self.assertEqual(s["titulo"], "Pensando…")
        self.assertTrue(s["animar"])
        self.assertFalse(s["retomar"])
        self.assertNotIn("colgado", json.dumps(s, ensure_ascii=False).lower())

    def test_proceso_muerto_es_un_hecho_y_ofrece_retomar(self):
        with mock.patch.object(lanzados, "_muerto", return_value=True):
            s = sv.evaluar(registro(), AHORA, movimiento=AHORA - 2)
        self.assertEqual(s["nivel"], sv.MURIO)
        self.assertEqual(s["titulo"], "Se cerró sin entregar")
        self.assertTrue(s["retomar"])
        self.assertFalse(s["animar"])

    def test_sin_senal_cuando_no_esta_trabajando(self):
        for fase in (lanzados.TERMINADO, lanzados.DETENIDO, lanzados.EN_ESPERA):
            self.assertIsNone(sv.evaluar(registro(fase=fase), AHORA, movimiento=AHORA))
        self.assertIsNone(sv.evaluar(None))

    def test_sin_log_cuenta_desde_el_lanzamiento(self):
        with vivo():
            s = sv.evaluar(registro(log="/no/existe.log"), AHORA)
        self.assertEqual(s["silencio"], 300)
        self.assertEqual(s["hace"], "")


class QueHace(unittest.TestCase):
    def descripcion(self, *lineas):
        return sv.descripcion_de("\n".join(lineas).splitlines()[-1], RAIZ)

    def test_herramientas_en_llano(self):
        casos = [
            (herramienta("Edit", file_path=f"{RAIZ}/tareas/app/lanzar.py"),
             "Editando tareas/app/lanzar.py"),
            (herramienta("Write", file_path=f"{RAIZ}/pruebas/nuevo.py"),
             "Escribiendo pruebas/nuevo.py"),
            (herramienta("Read", file_path=f"{RAIZ}/tareas/app/detalle.py"),
             "Leyendo tareas/app/detalle.py"),
            (herramienta("Read", file_path="/otro/sitio/ajeno.md"), "Leyendo ajeno.md"),
            (herramienta("Grep", pattern="x"), "Buscando en el código"),
            (herramienta("WebSearch", query="x"), "Buscando en la web"),
            (herramienta("Bash", command="python3 -m unittest discover pruebas"),
             "Corriendo: python3 -m unittest discover pruebas"),
            (texto("Listo, ya está."), "Escribiendo su respuesta"),
            (herramienta("Cosa"), "Usando Cosa"),
        ]
        for linea, esperado in casos:
            self.assertEqual(sv.descripcion_de(linea, RAIZ), esperado)

    def test_comando_recortado_y_sin_rutas_personales(self):
        casa = os.path.expanduser("~")
        dice = sv.descripcion_de(herramienta(
            "Bash", command=f"cd {RAIZ} && cat {casa}/secreto.txt " + "x" * 200), RAIZ)
        self.assertLessEqual(len(dice), len("Corriendo: ") + sv.RECORTE_COMANDO)
        self.assertNotIn(RAIZ, dice)
        self.assertNotIn(casa + "/", dice)
        self.assertTrue(dice.endswith("…"))

    def test_lo_que_no_es_un_paso_suyo_no_describe(self):
        for linea in (resultado(), "texto suelto de otro cliente", "", "{roto",
                      json.dumps({"type": "result", "result": "fin"})):
            self.assertIsNone(sv.descripcion_de(linea, RAIZ))

    def test_del_log_toma_la_ultima_herramienta(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "a.log")
            with open(log, "w") as f:
                f.write(LOG)
            r = registro(log=log, worktree={"ruta": RAIZ})
            self.assertEqual(sv.que_hace(r), "Editando tareas/app/lanzar.py")

    def test_solo_lee_la_cola_y_cachea_por_mtime(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "a.log")
            relleno = texto("x" * 200) + "\n"
            with open(log, "w") as f:
                f.write(herramienta("Read", file_path=f"{RAIZ}/viejo.py") + "\n")
                f.write(relleno * (sv.COLA // 150))
            r = registro(log=log, worktree={"ruta": RAIZ})
            self.assertEqual(sv.que_hace(r), "Escribiendo su respuesta")   # lo viejo no se lee
            with mock.patch("builtins.open", side_effect=AssertionError("releyó")):
                self.assertEqual(sv.que_hace(r), "Escribiendo su respuesta")  # caché
            with open(log, "a") as f:
                f.write(herramienta("Grep", pattern="x") + "\n")
            self.assertEqual(sv.que_hace(r), "Buscando en el código")

    def test_cliente_sin_stream_json_no_describe(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "b.log")
            with open(log, "w") as f:
                f.write("Leyendo archivos...\nEjecutando pruebas\n")
            self.assertEqual(sv.que_hace(registro(log=log)), "")
        self.assertEqual(sv.que_hace(registro()), "")


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
