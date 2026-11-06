"""Lo que enseña la pantalla Preparando, sin GTK (tareas/preparando.py): de una bitácora de prueba
en distintos momentos a los cinco pasos con su estado y su tiempo, el reloj, el error con sus
acciones y «Revisar el plan». Sin agente de verdad: se escribe el registro de la preparación y la
bitácora a mano."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from tareas import inicio, preparacion, preparando

T0 = 1_000_000


def hora(s):
    return T0 + s


class Vistas(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.carpeta = str(self.base / "turnos")
        os.makedirs(os.path.join(self.carpeta, ".cotejo"))
        self.bitacora = self.base / "bitacora.jsonl"
        self.bitacora.write_text("")
        for objetivo, valor in ((preparacion, "CARPETA"),):
            p = mock.patch.object(objetivo, valor, self.base / "preparaciones")
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(preparacion, "_muerto", return_value=False)
        p.start()
        self.addCleanup(p.stop)
        self.registro = preparacion.guardar({
            "id": "turnos-abc123", "proyecto": "turnos", "carpeta": self.carpeta,
            "cliente": "claude", "modelo": "", "prompt": "x", "comando": ["claude"],
            "intentos": 1, "log": str(self.base / "salida.log"), "fase": "lanzado",
            "pid": 1, "programa": "claude", "ts": T0})
        self.seguimiento = preparando.Preparando("turnos-abc123", str(self.bitacora))

    def linea(self, operacion, s, **extra):
        base = {"cuando": hora(s), "operacion": operacion, "proyecto": "turnos",
                "carpeta": self.carpeta, **extra}
        with self.bitacora.open("a") as f:
            f.write(json.dumps(base) + "\n")

    def tarea(self, s, ident):
        with self.bitacora.open("a") as f:
            f.write(json.dumps({"cuando": hora(s), "operacion": "crear", "id": ident,
                                "proyecto": "turnos", "texto": "algo",
                                "nota": "turnos/.cotejo/tareas.md"}) + "\n")

    def ver(self, s):
        return self.seguimiento.refrescar(ahora=hora(s))

    def estados(self, v):
        return [p["estado"] for p in v.pasos]

    def test_los_cinco_pasos_salen_con_los_titulos_de_inicio(self):
        v = self.ver(5)
        self.assertEqual([p["titulo"] for p in v.pasos], [p.titulo for p in inicio.PASOS])
        self.assertEqual(self.estados(v), ["en curso", "pendiente", "pendiente", "pendiente",
                                           "pendiente"])
        self.assertEqual(v.titulo, "Preparando turnos")
        self.assertIn("0:05", v.reloj)
        self.assertIn("2 a 4 minutos", v.reloj)

    def test_el_avance_en_distintos_momentos(self):
        self.linea("init", 12, git_init=True)
        self.linea("editar", 40, tipo="proyecto", entrada="proyecto")
        v = self.ver(75)
        self.assertEqual(self.estados(v), ["hecho", "hecho", "en curso", "pendiente", "pendiente"])
        self.assertEqual([p["tiempo"] for p in v.pasos][:3], ["12 s", "28 s", "35 s"])
        self.assertEqual(v.pasos[0]["simbolo"], "✓")
        self.assertEqual(v.pasos[2]["simbolo"], "◐")
        self.assertEqual(v.pasos[3]["simbolo"], "○")
        self.assertIn("1:15", v.reloj)
        self.linea("proponer", 80, entrada="dec-a")
        self.linea("anotar", 95, tipo="arquitectura", piezas=4)
        v = self.ver(100)
        self.assertEqual(self.estados(v), ["hecho", "hecho", "hecho", "hecho", "en curso"])
        self.assertEqual(v.pasos[3]["tiempo"], "15 s")
        self.assertIn("1 decisión propuesta", v.pasos[2]["detalle"])
        self.assertFalse(v.puede_revisar)
        self.assertEqual(v.acciones, ())

    def test_al_terminar_aparece_revisar_el_plan(self):
        for s, v in ((10, "init"), (30, "editar"), (50, "proponer"), (70, "anotar")):
            self.linea(v, s, tipo="proyecto" if v == "editar" else "arquitectura",
                       entrada="d1")
        self.tarea(100, "t1")
        Path(self.carpeta, ".cotejo", "tareas.md").write_text("# T\n- [ ] Primera #v0.1.0\n")
        preparacion.anotar_terminado("turnos-abc123", 0)
        reg = preparacion.leer("turnos-abc123")
        reg["terminado_ts"] = hora(135)
        preparacion.guardar(reg)
        v = self.ver(500)
        self.assertEqual(v.situacion, preparacion.LISTO)
        self.assertEqual(self.estados(v), ["hecho"] * 5)
        self.assertTrue(v.puede_revisar)
        self.assertEqual(v.titulo, "turnos está listo")
        self.assertEqual(v.reloj, "Listo en 2:15")
        self.assertEqual(v.acciones, ())

    def test_con_error_salen_reintentar_y_abrir_en_terminal(self):
        self.linea("init", 12)
        preparacion.anotar_terminado("turnos-abc123", 3)
        v = self.ver(60)
        self.assertEqual(v.situacion, preparacion.FALLO)
        self.assertEqual(self.estados(v), ["hecho", "fallo", "pendiente", "pendiente", "pendiente"])
        self.assertEqual(v.pasos[1]["simbolo"], "✕")
        self.assertEqual(v.acciones, ("reintentar", "abrir_en_terminal"))
        self.assertIn("código 3", v.mensaje)
        self.assertFalse(v.puede_revisar)

    def test_colgado_ofrece_lo_mismo(self):
        self.linea("init", 12)
        os.utime(os.path.join(self.carpeta, ".cotejo"), (T0, T0))   # nada se movió desde T0
        v = self.ver(60 * 30)
        self.assertEqual(v.situacion, preparacion.COLGADO)
        self.assertEqual(v.acciones, ("reintentar", "abrir_en_terminal"))
        self.assertEqual(self.estados(v)[1], "fallo")
        self.assertIn("sin escribir", v.mensaje)

    def test_en_terminal_explica_donde_sigue(self):
        self.linea("init", 12)
        preparacion.cambiar_fase("turnos-abc123", preparacion.EN_TERMINAL)
        v = self.ver(90)
        self.assertEqual(v.situacion, preparacion.EN_TERMINAL)
        self.assertEqual(v.acciones, ())
        self.assertIn("terminal", v.mensaje)
        self.assertEqual(self.estados(v)[:2], ["hecho", "en curso"])

    def entero(self, tareas=5):
        """El resultado completo en la carpeta, como lo deja el agente, sin bitácora."""
        c = Path(self.carpeta, ".cotejo")
        (c / "proyecto.md").write_text("---\nid: proyecto\n---\n# turnos\n\n## Objetivo\nX\n")
        for sub, nombre in (("decisiones", "2026-11-03-stack.md"), ("arquitectura", "a.md")):
            (c / sub).mkdir(exist_ok=True)
            (c / sub / nombre).write_text("---\nid: x\n---\n# x\n")
        (c / "tareas.md").write_text("# T\n" + "".join(f"- [ ] T{i}: x #v0.1.0\n"
                                                         for i in range(tareas)))

    def test_lo_que_existe_en_la_carpeta(self):
        self.assertEqual(preparacion.lo_que_existe(self.carpeta), {})
        Path(self.carpeta, ".cotejo", "proyecto.md").write_text("---\nid: proyecto\n---\n# turnos\n")
        self.assertEqual(preparacion.lo_que_existe(self.carpeta), {"init": 1})
        self.entero(tareas=3)
        self.assertEqual(preparacion.lo_que_existe(self.carpeta),
                         {"init": 1, "editar": 1, "proponer": 1, "anotar": 1, "crear": 3})

    def test_los_pasos_se_mueven_por_lo_que_ya_hay_aunque_la_bitacora_calle(self):
        self.linea("init", 12)
        self.entero()
        v = self.ver(60)
        self.assertEqual(self.estados(v)[:4], ["hecho"] * 4)
        self.assertEqual(v.pasos[4]["detalle"], "5 tareas creadas")

    def test_entero_y_quieto_es_listo_aunque_el_proceso_no_salga(self):
        self.entero()
        quieto = T0 + 600
        for raiz, carpetas, archivos in os.walk(Path(self.carpeta, ".cotejo")):
            for n in [raiz] + [os.path.join(raiz, a) for a in archivos]:
                os.utime(n, (T0 + 300, T0 + 300))
        registro = preparacion.leer("turnos-abc123")
        con_gracia = mock.patch.object(preparacion, "segundos_de_gracia", return_value=120)
        with con_gracia:
            self.assertFalse(preparacion.resultado_completo(registro, ahora=T0 + 400))
            self.assertTrue(preparacion.resultado_completo(registro, ahora=quieto))
            e = preparacion.estado(registro, ahora=quieto, minutos=60)
        self.assertEqual(e["estado"], preparacion.LISTO)
        self.assertFalse(e["puede_cancelar"])
        # Lo de antes del lanzamiento no basta: un reintento sobre un proyecto ya hecho.
        registro["ts"] = T0 + 500
        with con_gracia:
            self.assertFalse(preparacion.resultado_completo(registro, ahora=quieto))
        # Al rehacer una decisión lo que tiene que moverse es `decisiones/`.
        registro.update(ts=T0 + 200, rehacer={"motivo": "otra"})
        with con_gracia:
            self.assertTrue(preparacion.resultado_completo(registro, ahora=quieto))
        os.utime(Path(self.carpeta, ".cotejo", "decisiones", "2026-11-03-stack.md"), (T0, T0))
        os.utime(Path(self.carpeta, ".cotejo", "decisiones"), (T0, T0))
        with con_gracia:
            self.assertFalse(preparacion.resultado_completo(registro, ahora=quieto))

    def test_a_medias_no_es_listo(self):
        self.entero()
        os.remove(Path(self.carpeta, ".cotejo", "arquitectura", "a.md"))
        with mock.patch.object(preparacion, "segundos_de_gracia", return_value=0):
            self.assertFalse(preparacion.resultado_completo(preparacion.leer("turnos-abc123"),
                                                            ahora=T0 + 10 ** 6))

    def test_mientras_prepara_se_puede_cancelar(self):
        self.assertTrue(self.ver(5).puede_cancelar)
        preparacion.anotar_terminado("turnos-abc123", 3)
        self.assertFalse(self.ver(60).puede_cancelar)

    def test_cancelada_dice_que_lo_hecho_sigue_y_ofrece_reintentar(self):
        self.linea("init", 12)
        preparacion.anotar_cancelado("turnos-abc123")
        v = self.ver(60)
        self.assertEqual(v.situacion, preparacion.CANCELADO)
        self.assertEqual(v.eyebrow, "Cancelada")
        self.assertFalse(v.puede_cancelar)
        self.assertEqual(v.acciones, ("reintentar", "abrir_en_terminal"))
        self.assertIn("sigue ahí", v.mensaje)
        self.assertNotIn(preparacion.CANCELADO, preparacion.PARA_LA_BARRA)

    def test_un_reintento_empieza_a_contar_de_nuevo(self):
        self.linea("init", 12)
        self.assertEqual(self.estados(self.ver(30))[0], "hecho")
        reg = preparacion.leer("turnos-abc123")
        reg["ts"] = hora(200)
        preparacion.guardar(reg)
        self.assertEqual(self.estados(self.ver(210))[0], "en curso")

    def test_el_registro_enseña_la_bitacora_y_la_salida(self):
        self.linea("init", 12)
        Path(self.base, "salida.log").write_text("hola desde el agente")
        reg = self.ver(20).registro
        self.assertIn("$ cotejo init turnos", reg)
        self.assertIn("hola desde el agente", reg)

    def test_preparacion_que_no_existe(self):
        v = preparando.Preparando("nada-000000", str(self.bitacora)).refrescar()
        self.assertEqual(v.situacion, preparacion.FALLO)

    def test_formatos_de_tiempo(self):
        self.assertEqual([preparando.tiempo(s) for s in (0, 5, 135, 3723)],
                         ["0:00", "0:05", "2:15", "1:02:03"])
        self.assertEqual([preparando.duracion(s) for s in (None, 12, 60, 65)],
                         ["", "12 s", "1 min", "1 min 5 s"])


if __name__ == "__main__":
    unittest.main()
