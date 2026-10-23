"""La pantalla Preparando en el board de verdad (v1.3.0, cotejo-hiifrz), de punta a punta.

Con GTK y pantalla (sin ellas se salta), sobre un vault de mentira y con una bitácora y un
registro de preparación escritos a mano: nunca se lanza un agente. Los cinco pasos salen con su
estado y su tiempo según el momento; con error se ven «Reintentar» y «Abrir en terminal» y llaman
a `preparar.reintentar` / `abrir_en_terminal` (simulados); al terminar aparece «Revisar el plan»;
y el temporizador solo existe mientras la pantalla se ve. La lógica sin GTK está en
`test_preparando.py`.
"""

import json
import os
import time
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import test_pestana_inicio as base

if base.HAY_GTK:
    from gi.repository import Gtk
    from tareas import bitacora, preparacion
    from tareas.app import preparando as pantalla


def botones(widget, acumulado=None):
    acumulado = [] if acumulado is None else acumulado
    if isinstance(widget, Gtk.Button):
        acumulado.append(widget)
    hijo = widget.get_first_child()
    while hijo is not None:
        botones(hijo, acumulado)
        hijo = hijo.get_next_sibling()
    return acumulado


@unittest.skipUnless(base.HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class Preparando(base.PestanaInicio):
    def setUp(self):
        super().setUp()
        raiz = Path(os.environ["COTEJO_ESTADO"])
        raiz.mkdir(parents=True, exist_ok=True)
        self.carpeta = str(raiz / "proyectos" / "turnos")
        os.makedirs(os.path.join(self.carpeta, ".cotejo"))
        self.bitacora = raiz / "bitacora.jsonl"
        self.bitacora.write_text("")
        for objetivo, atributo, valor in (
                (preparacion, "CARPETA", raiz / "preparaciones"),
                (bitacora, "ARCHIVO", self.bitacora)):
            p = mock.patch.object(objetivo, atributo, valor)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(preparacion, "_muerto", return_value=False)
        p.start()
        self.addCleanup(p.stop)
        self.ts = int(time.time()) - 75
        self.estado = {"id": "turnos-abc123", "proyecto": "turnos"}
        self.registrar(fase="lanzado")

    def registrar(self, **extra):
        preparacion.guardar({
            "id": "turnos-abc123", "proyecto": "turnos", "carpeta": self.carpeta,
            "cliente": "claude", "modelo": "", "prompt": "x", "comando": ["claude"],
            "intentos": 1, "log": "", "pid": 1, "programa": "claude", "ts": self.ts, **extra})

    def linea(self, operacion, antes, **extra):
        """Una línea de bitácora hecha `antes` segundos atrás."""
        with self.bitacora.open("a") as f:
            f.write(json.dumps({"cuando": int(time.time()) - antes, "operacion": operacion,
                                "proyecto": "turnos", "carpeta": self.carpeta, **extra}) + "\n")

    def abrir(self):
        b = self.board
        with mock.patch("enrutador.preparar.estado", return_value=self.estado):
            b.mostrar_preparando(self.estado)
        base.girar()
        return b, b.pantalla_preparando

    def pasos(self, p):
        return [(f[1].get_label(), f[0].get_label(), f[3].get_label()) for f in p.filas]

    def test_los_cinco_pasos_con_su_estado_y_su_tiempo(self):
        self.linea("init", 60, git_init=True)
        self.linea("editar", 30, tipo="proyecto", entrada="proyecto")
        b, p = self.abrir()
        self.assertEqual(b.pestana_actual(), "preparando")
        self.assertEqual(p.titulo.get_label(), "Preparando turnos")
        self.assertIn("1:1", p.reloj.get_label())          # ~1:15
        self.assertIn("2 a 4 minutos", p.reloj.get_label())
        pasos = self.pasos(p)
        self.assertEqual(len(pasos), 5)
        self.assertEqual([s for _t, s, _d in pasos], ["✓", "✓", "◐", "○", "○"])
        self.assertEqual(pasos[0][2], "15 s")
        self.assertEqual(pasos[1][2], "30 s")
        self.assertTrue(p.filas[0][2].get_label().startswith("Carpeta creada"))
        self.assertFalse(p.reintentar.get_visible() or p.en_terminal.get_visible()
                         or p.revisar.get_visible())
        # El registro desplegable lleva lo que se vio hacer al agente.
        buf = p.registro.get_buffer()
        self.assertIn("$ cotejo init", buf.get_text(buf.get_start_iter(), buf.get_end_iter(),
                                                    False))

    def test_con_error_salen_reintentar_y_abrir_en_terminal_y_los_llaman(self):
        self.linea("init", 60)
        self.registrar(fase="terminado", codigo=3, terminado_ts=int(time.time()) - 5)
        b, p = self.abrir()
        self.assertEqual(self.pasos(p)[1][1], "✕")
        self.assertTrue(p.reintentar.get_visible())
        self.assertTrue(p.en_terminal.get_visible())
        self.assertTrue(p.mensaje.get_visible())
        self.assertFalse(p.revisar.get_visible())
        with mock.patch("enrutador.preparar.reintentar") as reintentar:
            p.reintentar.emit("clicked")
        self.assertEqual(reintentar.call_args.args, ("turnos-abc123",))
        self.assertTrue(callable(reintentar.call_args.kwargs["al_terminar"]))
        with mock.patch("enrutador.preparar.abrir_en_terminal") as terminal:
            p.en_terminal.emit("clicked")
        terminal.assert_called_once_with("turnos-abc123")

    def test_otro_cotejo_de_otra_version_se_dice_en_llano(self):
        b, p = self.abrir()
        self.assertFalse(p.otro_cotejo.get_visible())
        self.registrar(fase="lanzado", otro_cotejo={"ruta": "/usr/bin/cotejo",
                                                     "version": "1.2.5", "esta": "1.3.0"})
        b.refrescar_preparando()
        self.assertTrue(p.otro_cotejo.get_visible())
        self.assertIn("otro Cotejo instalado (la versión 1.2.5)", p.otro_cotejo.get_label())
        self.assertFalse(p.mensaje.get_visible())  # es una nota, no un error

    def test_si_reintentar_no_puede_se_avisa(self):
        from enrutador import preparar
        self.registrar(fase="terminado", codigo=1)
        b, p = self.abrir()
        with mock.patch("enrutador.preparar.reintentar",
                        side_effect=preparar.NoSePuede("No encontré «claude»")), \
                mock.patch.object(b, "aviso") as aviso:
            p.reintentar.emit("clicked")
        aviso.assert_called_once_with("No encontré «claude»")

    def test_al_terminar_aparece_revisar_el_plan(self):
        b, p = self.abrir()
        self.assertFalse(p.revisar.get_visible())
        for i, v in enumerate(("init", "editar", "proponer", "anotar")):
            self.linea(v, 50 - i * 10, tipo="proyecto" if v == "editar" else "arquitectura",
                       entrada="x")
        self.linea("crear", 5, id="t1", nota="turnos/.cotejo/tareas.md")
        Path(self.carpeta, ".cotejo", "tareas.md").write_text("# T\n- [ ] Una #v0.1.0\n")
        self.registrar(fase="terminado", codigo=0, terminado_ts=int(time.time()) - 2)
        with mock.patch("enrutador.preparar.estado", return_value=self.estado):
            self.assertEqual(b.preparacion_terminada(self.estado), pantalla.GLib.SOURCE_REMOVE)
        self.assertEqual(p.titulo.get_label(), "turnos está listo")
        self.assertEqual([s for _t, s, _d in self.pasos(p)], ["✓"] * 5)
        self.assertTrue(p.revisar.get_visible())
        self.assertFalse(p.reintentar.get_visible())
        # «Revisar el plan» lleva a la pantalla del plan (m195bn) con el estado de esta.
        estado = dict(self.estado, carpeta=self.carpeta)
        with mock.patch("enrutador.preparar.estado", return_value=estado), \
                mock.patch.object(b, "abrir_proyecto") as abrir:
            p.revisar.emit("clicked")
        abrir.assert_not_called()
        self.assertEqual(b.pestana_actual(), "plan")
        self.assertEqual(b.plan_estado["id"], "turnos-abc123")

    def test_el_temporizador_existe_solo_con_la_pantalla_a_la_vista(self):
        b, p = self.abrir()
        self.assertTrue(p.get_mapped())
        self.assertTrue(p.hay_reloj())
        antes = p.refrescos
        base.girar(2500)
        self.assertGreater(p.refrescos, antes)          # el reloj avanza mientras se ve
        b.ver_pestana("inicio")
        base.girar(300)
        self.assertFalse(p.get_mapped())
        self.assertFalse(p.hay_reloj())
        quieto = p.refrescos
        base.girar(2500)
        self.assertEqual(p.refrescos, quieto)           # oculta, no refresca nada
        b.ver_pestana("preparando")
        base.girar(100)
        self.assertTrue(p.hay_reloj())

    def test_antes_de_lanzar_nada_no_hay_temporizador(self):
        self.assertFalse(self.board.pantalla_preparando.hay_reloj())

    def test_volver_al_inicio_no_para_al_agente(self):
        b, p = self.abrir()
        with mock.patch("enrutador.preparar.reintentar") as r, \
                mock.patch("enrutador.preparar.abrir_en_terminal") as t:
            p.boton_inicio.emit("clicked")
        self.assertEqual(b.pestana_actual(), "inicio")
        r.assert_not_called()
        t.assert_not_called()


if __name__ == "__main__":
    unittest.main()
