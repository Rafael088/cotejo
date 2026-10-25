"""El mapa del proyecto en el board de verdad (v1.3.0, cotejo-p86sa9), de punta a punta.

Con GTK y pantalla (sin ellas se salta). La fuente activa es la de repos, con un proyecto de
prueba en un tmp (`test_mapa.proyecto_de_prueba`: piezas en las cuatro capas, estados variados
y tareas enlazadas). Se llega al mapa desde la tarjeta del Inicio, desde un núcleo de la
constelación y desde «Revisar el plan» (con la carpeta, como un proyecto recién preparado);
el mapa agrupa por capa con el estado correcto, la ficha enseña frase, tareas y tecnología, y
«Ver el tablero» lleva al tablero de ese proyecto. Nunca se lanza un agente.
"""

import os
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import test_pestana_inicio as base
from test_mapa import proyecto_de_prueba

if base.HAY_GTK:
    from tareas import constelacion as c
    from tareas.app import mapa as pantalla


@unittest.skipUnless(base.HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class MapaDelProyecto(base.PestanaInicio):
    con_vault = False

    def entorno_extra(self, raiz):
        self.carpeta = proyecto_de_prueba(raiz / "repos")
        return {"COTEJO_REPOS": str(self.carpeta)}

    def mapa(self):
        return self.board.pantalla_mapa

    def comprobar_mapa(self):
        b, p = self.board, self.mapa()
        self.assertEqual(b.pestana_actual(), pantalla.MAPA)
        self.assertFalse(b.banda_proyectos.get_visible())
        self.assertEqual(p.titulo.get_label(), "Cómo está hecho barberia")
        self.assertEqual(p.avance.get_label(), "2 de 7 piezas")
        capas = {}
        hijo = p.capas.get_first_child()
        while hijo is not None:
            todo = base.textos(hijo)
            capas[todo[0]] = todo[2:]
            hijo = hijo.get_next_sibling()
        self.assertEqual(capas, {
            "Qué ve la gente": ["Horarios libres", "Formulario de reserva", "Mis turnos del día"],
            "Qué hace": ["Calcular huecos", "Avisar"],
            "Qué guarda": ["Turnos"],
            "Con qué se conecta": ["Hoja de Google"],
        })
        estados = {i: pz["estado"] for i, pz in ((i, p.mapa.pieza(i)) for i in p.botones_pieza)}
        self.assertEqual(estados["horarios-libres"], "por-comprobar")
        self.assertEqual(estados["formulario-de-reserva"], "en-curso")
        self.assertEqual(estados["calcular-huecos"], "hecho")
        self.assertEqual(estados["avisar"], "falta")
        # La leyenda es la de la constelación, con sus cuatro nombres.
        todo = base.textos(p)
        for nombre in c.NOMBRES.values():
            self.assertIn(nombre, todo)

    def test_los_avisos_van_plegados_en_si_programas(self):
        b, p = self.board, self.mapa()
        b.abrir_proyecto("barberia")
        base.girar()
        pintado = pantalla.m.armar("barberia", [], avisos=[
            "Este repo todavía no tiene .cotejo/",
            {"nota": ".cotejo/arquitectura/x.md", "motivo": "pieza 1: la capa «x» no es válida"}])
        p.pintar(pintado)
        base.girar()
        self.assertTrue(p.avisos_plegable.get_visible())
        self.assertEqual(p.avisos_plegable.get_label(), "Si programas")
        self.assertFalse(p.avisos_plegable.get_expanded())
        # Fuera del plegable no hay ni rastro técnico.
        visibles = [t for t in base.textos(p) if t not in base.textos(p.avisos)]
        for tecnico in ("cotejo/", ".md", "capa", "pieza 1"):
            self.assertFalse(any(tecnico in t for t in visibles), tecnico)
        p.pintar(pantalla.m.armar("barberia", []))
        self.assertFalse(p.avisos_plegable.get_visible())

    def test_desde_la_tarjeta_del_inicio(self):
        b = self.board
        self.assertEqual(b.pestana_actual(), "inicio")
        tarjeta = next(t for t in _hijos_boton(b.inicio_tarjetas)
                       if "barberia" in base.textos(t))
        tarjeta.emit("clicked")
        base.girar()
        self.comprobar_mapa()

    def test_desde_un_nucleo_de_la_constelacion(self):
        b = self.board
        self.assertIsNotNone(b.constelacion)
        nucleos = c.disponer(b.constelacion.proyectos, 800)
        x0, y0, ancho, alto = nucleos[0].celda
        with mock.patch.object(b.constelacion, "get_width", return_value=800):
            b.constelacion._al_soltar(None, 1, x0 + ancho / 2, y0 + alto / 2)
        base.girar()
        self.comprobar_mapa()

    def test_la_ficha_enseña_frase_tareas_y_tecnologia(self):
        b, p = self.board, self.mapa()
        b.abrir_proyecto("barberia")
        base.girar()
        # Al abrir, la ficha de lo que espera comprobación.
        self.assertEqual(p.ficha_nombre.get_label(), "Horarios libres")
        self.assertTrue(p.botones_pieza["horarios-libres"].get_active())
        p.botones_pieza["hoja-de-google"].emit("clicked")
        base.girar()
        self.assertFalse(p.botones_pieza["horarios-libres"].get_active())
        self.assertTrue(p.botones_pieza["hoja-de-google"].get_active())
        self.assertEqual(p.ficha_capa.get_label(), "CON QUÉ SE CONECTA")
        self.assertEqual(p.ficha_frase.get_label(), "Donde viven los turnos")
        self.assertEqual(p.ficha_tecnologia.get_label(), "Si programas: Sheets API")
        self.assertEqual(base.textos(p.ficha_tareas),
                         ["Guardar la reserva en la hoja", "Para comprobar"])
        estado = p.ficha_chips.get_first_child()
        self.assertEqual(base.textos(estado), ["Espera que lo compruebes"])
        self.assertTrue(estado.has_css_class("verde"))
        # Una pieza hecha no va en verde; una sin tareas lo dice.
        p.botones_pieza["calcular-huecos"].emit("clicked")
        self.assertFalse(p.ficha_chips.get_first_child().has_css_class("verde"))
        self.assertEqual(base.textos(p.ficha_tareas), ["Calcular huecos", "Finalizada"])
        p.botones_pieza["avisar"].emit("clicked")
        self.assertEqual(base.textos(p.ficha_tareas), ["Ninguna tarea la cubre todavía."])
        self.assertEqual(p.ficha_tecnologia.get_label(), "Si programas: todavía sin elegir")

    def test_del_mapa_al_tablero_del_proyecto_y_de_vuelta_al_inicio(self):
        b, p = self.board, self.mapa()
        b.abrir_proyecto("barberia")
        base.girar()
        p.boton_tablero.emit("clicked")
        base.girar()
        self.assertEqual(b.pestana_actual(), "tablero")
        self.assertEqual(b.seleccion, "barberia")
        self.assertTrue(b.banda_proyectos.get_visible())
        b.abrir_proyecto("barberia")
        base.girar()
        p.boton_inicio.emit("clicked")
        self.assertEqual(b.pestana_actual(), "inicio")

    def test_desde_el_plan_con_la_carpeta(self):
        b = self.board
        estado = {"id": "barberia-abc123", "proyecto": "barberia", "carpeta": str(self.carpeta)}
        with mock.patch("tareas.revisar_plan.leer") as leer:
            leer.return_value = mock.Mock(proyecto="barberia", objetivo="", siguiente_paso="",
                                          cabecera_decisiones="", por_aceptar=0, decisiones=[],
                                          tareas=[], avisos=[])
            b.revisar_plan(estado)
        base.girar()
        b.pantalla_plan.ver_mapa.emit("clicked")
        base.girar()
        self.comprobar_mapa()
        self.assertEqual(b.mapa_proyecto, ("barberia", str(self.carpeta)))
        # «Empezar la 0.1.0» termina también en el mapa.
        with mock.patch("tareas.revisar_plan.empezar", return_value=[]):
            b.empezar_version()
        base.girar()
        self.comprobar_mapa()

    def test_un_proyecto_que_no_esta_en_la_fuente_activa_se_lee_de_su_carpeta(self):
        # Como uno recién preparado: el mapa se pinta con lo de la carpeta, y el tablero avisa.
        b, p = self.board, self.mapa()
        b.abrir_proyecto("otro-nombre", str(self.carpeta))
        base.girar()
        self.assertEqual(p.avance.get_label(), "2 de 7 piezas")
        self.assertEqual(p.mapa.pieza("horarios-libres")["estado"], "por-comprobar")
        with mock.patch.object(b, "aviso") as aviso:
            p.boton_tablero.emit("clicked")
        self.assertIn("otro-nombre", aviso.call_args.args[0])
        self.assertEqual(b.pestana_actual(), pantalla.MAPA)

    def test_se_repinta_al_refrescar_si_se_ve(self):
        b, p = self.board, self.mapa()
        b.abrir_proyecto("barberia")
        base.girar()
        tareas = self.carpeta / ".cotejo" / "tareas.md"
        tareas.write_text(tareas.read_text(encoding="utf-8").replace(
            "Tu vista del día #v0.1.0", "Tu vista del día #v0.1.0 #en-curso"), encoding="utf-8")
        self.app.refrescar()
        base.girar(200)
        self.assertEqual(p.mapa.pieza("mis-turnos-del-dia")["estado"], "en-curso")


def _hijos_boton(flowbox):
    hijo = flowbox.get_first_child()
    while hijo is not None:
        tarjeta = hijo.get_child()
        # La tarjeta de un proyecto es su botón con «Ver mi app» debajo (cotejo-vn4qd2).
        yield (tarjeta.get_first_child() if hasattr(tarjeta, "botones_app") else tarjeta)
        hijo = hijo.get_next_sibling()


if __name__ == "__main__":
    unittest.main()
