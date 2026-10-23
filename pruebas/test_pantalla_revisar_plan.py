"""La pantalla «Revisar el plan» en el board de verdad (v1.3.0, cotejo-m195bn), de punta a punta.

Con GTK y pantalla (sin ellas se salta), sobre un proyecto de prueba en un tmp con su `.cotejo/`
(objetivo, dos decisiones propuestas, tareas n0 y no-n0). Nunca se lanza un agente:
`preparar.rehacer` se simula. Se ve el objetivo y el siguiente paso; Aceptar deja la decisión
aceptada en el almacén; Cambiar exige motivo, la deja rechazada y relanza con ese motivo
volviendo a Preparando; la tarea n0 sale como «tú»; y «Empezar la 0.1.0» asigna como `plan`
y abre el proyecto. La lógica sin GTK está en `test_revisar_plan.py`.
"""

import os
import time
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import test_pestana_inicio as base
from test_revisar_plan import PROYECTO, TAREAS

if base.HAY_GTK:
    from tareas import almacen, bitacora, preparacion
    from tareas.app import revisar_plan as pantalla


@unittest.skipUnless(base.HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class RevisarPlan(base.PestanaInicio):
    def setUp(self):
        super().setUp()
        raiz = Path(os.environ["COTEJO_ESTADO"])
        raiz.mkdir(parents=True, exist_ok=True)
        self.carpeta = raiz / "proyectos" / "turnos"
        (self.carpeta / ".git").mkdir(parents=True)
        (self.carpeta / ".cotejo").mkdir()
        (self.carpeta / ".cotejo" / "tareas.md").write_text(TAREAS, encoding="utf-8")
        self.alm = almacen.Almacen(self.carpeta)
        self.alm.crear("proyecto", "turnos", PROYECTO)
        self.d1 = self.alm.crear("decision", "Web que se abre en el celular", "Sin tienda.")
        self.d2 = self.alm.crear("decision", "Los turnos en una hoja de Google", "Se ven.")
        for objetivo, atributo, valor in ((preparacion, "CARPETA", raiz / "preparaciones"),
                                          (bitacora, "ARCHIVO", raiz / "bitacora.jsonl")):
            p = mock.patch.object(objetivo, atributo, valor)
            p.start()
            self.addCleanup(p.stop)
        for nombre in ("enrutador.preparar.avisar_a_la_barra",):
            p = mock.patch(nombre)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(preparacion, "_muerto", return_value=False)
        p.start()
        self.addCleanup(p.stop)
        self.estado = {"id": "turnos-abc123", "proyecto": "turnos", "carpeta": str(self.carpeta),
                       "cliente": "claude"}
        # El campo del motivo toma el foco; si la ventana se destruye con él, Wayland puede
        # mandar el evento de foco a un widget que ya no existe. Se suelta antes de cerrar.
        self.addCleanup(self.soltar_foco)
        preparacion.guardar({**self.estado, "modelo": "", "prompt": "x", "comando": ["claude"],
                             "intentos": 1, "log": "", "fase": "terminado", "codigo": 0,
                             "pid": 1, "programa": "claude", "ts": int(time.time()) - 100,
                             "terminado_ts": int(time.time()) - 5})

    def soltar_foco(self):
        self.board.set_focus(None)
        base.girar()

    def abrir(self):
        self.board.revisar_plan(self.estado)
        base.girar()
        return self.board, self.board.pantalla_plan

    def fila(self, p, entrada):
        return next(f for f in p.filas_decision if f.datos["id"] == entrada.id)

    def test_enseña_objetivo_siguiente_paso_decisiones_y_tareas(self):
        b, p = self.abrir()
        self.assertEqual(b.pestana_actual(), pantalla.PLAN)
        self.assertEqual(p.objetivo.get_label(), "Que los clientes reserven su turno solos.")
        self.assertEqual(p.siguiente.get_label(),
                         "Siguiente paso: La pantalla de horarios libres.")
        self.assertEqual(p.cabecera_decisiones.get_label(), "2 decisiones esperan tu visto bueno")
        self.assertIn("2 por aceptar", base.textos(p.cuenta))
        self.assertEqual(len(p.filas_decision), 2)
        self.assertTrue(all(f.aceptar.get_visible() for f in p.filas_decision))
        # La n0 sale como «tú»; las demás, para un agente.
        quien = {t["id"]: base.textos(chip)[0] for _f, chip, t in p.filas_tarea}
        self.assertEqual(quien["cotejo-bbb222"], "tú")
        self.assertEqual(quien["cotejo-aaa111"], "agente")
        self.assertNotIn("cotejo-ddd444", quien)          # la de la 0.2.0 no es de este plan
        tu = next(c for _f, c, t in p.filas_tarea if t["id"] == "cotejo-bbb222")
        self.assertTrue(tu.has_css_class("chip-tu"))

    def test_aceptar_la_deja_aceptada_en_el_almacen(self):
        b, p = self.abrir()
        self.fila(p, self.d1).aceptar.emit("clicked")
        base.girar()
        self.assertEqual(self.alm.leer(self.d1.id).estado, "aceptada")
        self.assertEqual(self.alm.leer(self.d2.id).estado, "propuesta")
        self.assertEqual(p.cabecera_decisiones.get_label(), "1 decisión espera tu visto bueno")
        self.assertIsNone(self.fila(p, self.d1).aceptar)   # ya no tiene botones
        self.assertIn("Aceptada", base.textos(self.fila(p, self.d1)))

    def test_cambiar_exige_motivo_la_rechaza_y_relanza_con_el_motivo(self):
        b, p = self.abrir()
        f = self.fila(p, self.d2)
        self.assertFalse(f.caja_motivo.get_visible())
        f.cambiar.emit("clicked")
        self.assertTrue(f.caja_motivo.get_visible())
        self.assertFalse(f.enviar.get_sensitive())      # vacío no se puede enviar
        with mock.patch("enrutador.preparar.rehacer") as rehacer:
            f.motivo.emit("activate")
            rehacer.assert_not_called()
            self.assertEqual(self.alm.leer(self.d2.id).estado, "propuesta")
            f.motivo.set_text("Prefiero una base de datos")
            self.assertTrue(f.enviar.get_sensitive())
            rehacer.return_value = dict(self.estado)
            with mock.patch("enrutador.preparar.estado", return_value=self.estado):
                f.enviar.emit("clicked")
        entrada = self.alm.leer(self.d2.id)
        self.assertEqual(entrada.estado, "rechazada")
        self.assertEqual(entrada.datos["motivo"], "Prefiero una base de datos")
        ident, prompt = rehacer.call_args.args
        self.assertEqual(ident, "turnos-abc123")
        self.assertIn("| Prefiero una base de datos", prompt)
        self.assertEqual(rehacer.call_args.kwargs["motivo"], "Prefiero una base de datos")
        self.assertTrue(callable(rehacer.call_args.kwargs["al_terminar"]))
        self.assertEqual(b.pestana_actual(), "preparando")

    def test_si_no_se_puede_relanzar_avisa_y_se_queda(self):
        from enrutador import preparar
        b, p = self.abrir()
        f = self.fila(p, self.d1)
        f.cambiar.emit("clicked")
        f.motivo.set_text("No")
        with mock.patch("enrutador.preparar.rehacer",
                        side_effect=preparar.NoSePuede("No encontré «claude»")), \
                mock.patch.object(b, "aviso") as aviso:
            f.enviar.emit("clicked")
        self.assertIn("No encontré «claude»", aviso.call_args.args[0])
        self.assertEqual(b.pestana_actual(), pantalla.PLAN)
        self.assertIn("Rechazada", base.textos(self.fila(p, self.d1)))

    def test_empezar_asigna_como_plan_y_abre_el_proyecto(self):
        b, p = self.abrir()
        with mock.patch("enrutador.motores.fondo.lanzar") as lanzar, \
                mock.patch.object(b, "abrir_proyecto") as abrir:
            p.empezar.emit("clicked")
        lanzar.assert_not_called()
        abrir.assert_called_once_with("turnos")
        texto = (self.carpeta / ".cotejo" / "tareas.md").read_text(encoding="utf-8")
        self.assertIn("libres #v0.1.0 #agente/sonnet ^cotejo-aaa111", texto)
        self.assertIn("#dificil #agente/opus ^cotejo-ccc333", texto)
        self.assertIn("#agente/persona ^cotejo-bbb222", texto)
        self.assertEqual(preparacion.leer("turnos-abc123")["fase"], preparacion.VISTO)

    def test_volver_al_inicio(self):
        b, p = self.abrir()
        p.boton_inicio.emit("clicked")
        self.assertEqual(b.pestana_actual(), "inicio")


if __name__ == "__main__":
    unittest.main()
