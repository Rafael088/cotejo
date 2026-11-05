"""El maestro en el board: la barra del pie y la conversación que sube encima (cotejo-9ybn1a).

Dos partes, las dos con GTK (sin él, o sin pantalla, se saltan):

- La barra con un Board falso, sin ventana: lo escrito viaja al maestro, Enter y el botón hacen
  lo mismo, el desplegable solo elige el agente y lo recuerda, y nunca se abre una terminal.
- De punta a punta en el board de verdad, con el cliente falso (`cliente_falso.py`) en lugar de
  un agente: escribir «apunta…» lanza un turno sin interfaz, la conversación sube con lo que
  dijo la persona y la respuesta, la tarea que apuntó sale en el tablero, y si propone repartir,
  el botón «Repartir» las pasa a Haciendo por `mover`, solo las que una persona asignó.
"""

import json
import os
import sys
import types
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from enrutador import clientes

import test_pestana_inicio as base

try:
    from tareas import app
    from gi.repository import Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False

FALSO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cliente_falso.py")


def _nunca_una_terminal(*_a, **_k):
    raise AssertionError("el maestro no puede abrir una terminal")


def board_falso(seleccion="Uno"):
    falso = types.SimpleNamespace(seleccion=seleccion, avisos=[], definiciones=[],
                                  fuente=types.SimpleNamespace(problema=None))
    falso.aviso = lambda texto, segundos=4: falso.avisos.append(texto)
    for metodo in ("barra_maestro", "al_ejecutar_maestro", "hablar_al_maestro", "poner_maestro",
                   "menu_maestro", "cliente_del_maestro", "elegir_cliente_maestro",
                   "modelo_del_maestro", "definiciones_maestro", "elegir_modelo_maestro",
                   "crear_conversacion", "montar_conversacion", "ver_conversacion",
                   "cerrar_conversacion", "poner_en_su_sitio", "ajustar_conversacion",
                   "pintar_conversacion", "proyecto_del_maestro", "parar_reloj_maestro",
                   "tic_maestro", "maestro_contesto", "parar_maestro", "olvidar_maestro",
                   "repartir_del_maestro"):
        setattr(falso, metodo, types.MethodType(getattr(app.Board, metodo), falso))
    falso.panel = falso.crear_conversacion()
    falso.barra = falso.barra_maestro()
    return falso


def botones_de(widget):
    """Todos los `Gtk.Button` de un widget, aunque estén dentro de su scroll (el menú del
    maestro lo lleva: con los modelos registrados la lista crece)."""
    salida = []
    if isinstance(widget, Gtk.Button):
        salida.append(widget)
    hijo = widget.get_first_child()
    while hijo is not None:
        salida += botones_de(hijo)
        hijo = hijo.get_next_sibling()
    return salida


def etiquetas_de(widget):
    """Todos los `Gtk.Label` de un widget, aunque estén dentro de su scroll."""
    salida = []
    if isinstance(widget, Gtk.Label):
        salida.append(widget.get_label())
    hijo = widget.get_first_child()
    while hijo is not None:
        salida += etiquetas_de(hijo)
        hijo = hijo.get_next_sibling()
    return salida


def texto_de_boton(boton):
    etiquetas = []
    pendientes = [boton.get_first_child()]
    while pendientes:
        hijo = pendientes.pop()
        while hijo is not None:
            if isinstance(hijo, Gtk.Label):
                etiquetas.append(hijo.get_label())
            if hijo.get_first_child() is not None:
                pendientes.append(hijo.get_first_child())
            hijo = hijo.get_next_sibling()
    return " ".join(etiquetas)


def hablado(proyecto="Uno"):
    return {"proyecto": proyecto, "titulo": "Claude Code", "asignadas": [], "lanzado": True}


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir la barra")
class BarraMaestro(unittest.TestCase):
    def setUp(self):
        guardado = {}
        for nombre, valor in (("cargar_board", lambda: dict(guardado)),
                              ("guardar_board", lambda **c: guardado.update(c))):
            parche = mock.patch.object(app.comun, nombre, valor)
            parche.start()
            self.addCleanup(parche.stop)
        self.guardado = guardado
        for parche in (mock.patch("enrutador.clientes.instalados",
                                  return_value=["claude", "codex"]),
                       mock.patch("enrutador.modelos_vivos.utilizables",
                                  return_value=["claude", "codex"]),
                       mock.patch("enrutador.motores.terminal.abrir", _nunca_una_terminal),
                       mock.patch("enrutador.conversacion.leer",
                                  return_value={"proyecto": "Uno", "turnos": []})):
            parche.start()
            self.addCleanup(parche.stop)

    def test_un_solo_boton_para_enviar(self):
        falso = board_falso()
        botones = []
        hijo = falso.boton_maestro.get_parent().get_first_child()
        while hijo is not None:
            if isinstance(hijo, (Gtk.Button, Gtk.MenuButton)) or hasattr(hijo, "get_dropdown_tooltip"):
                botones.append(hijo)
            hijo = hijo.get_next_sibling()
        self.assertEqual(botones, [falso.boton_maestro])

    def test_enter_le_habla_al_maestro_y_sube_la_conversacion(self):
        falso = board_falso()
        falso.entrada_maestro.set_text("  apunta que falta   el login ")
        with mock.patch("enrutador.verbos.hablar_maestro", return_value=hablado()) as hablar:
            falso.entrada_maestro.emit("activate")
        self.assertEqual(hablar.call_args.args, ("Uno", "apunta que falta el login", "claude"))
        self.assertIn("al_terminar", hablar.call_args.kwargs)
        self.assertEqual(falso.entrada_maestro.get_text(), "")
        self.assertTrue(falso.panel_maestro.get_visible())

    def test_el_boton_dice_que_envia_cuando_hay_texto(self):
        falso = board_falso()
        falso.poner_maestro()
        self.assertEqual(falso.boton_maestro.get_label(), "Conversación")
        # Sin texto, contorno; con texto, relleno (la clase la pinta el CSS).
        self.assertFalse(falso.boton_maestro.has_css_class("con-texto"))
        falso.entrada_maestro.set_text("qué falta")
        self.assertEqual(falso.boton_maestro.get_label(), "Enviar")
        self.assertTrue(falso.boton_maestro.has_css_class("con-texto"))
        falso.entrada_maestro.set_text("   ")
        self.assertFalse(falso.boton_maestro.has_css_class("con-texto"))

    def test_sin_texto_el_boton_ensena_y_oculta_la_conversacion(self):
        falso = board_falso()
        with mock.patch("enrutador.verbos.hablar_maestro") as hablar:
            falso.al_ejecutar_maestro()
            self.assertTrue(falso.panel_maestro.get_visible())
            falso.al_ejecutar_maestro()
            self.assertFalse(falso.panel_maestro.get_visible())
        hablar.assert_not_called()

    def test_cerrar_la_conversacion_no_para_al_maestro(self):
        """Cerrar solo oculta el panel: el turno sigue y su respuesta se guarda."""
        falso = board_falso()
        falso.ver_conversacion()
        with mock.patch("enrutador.conversacion.parar") as parar:
            falso.cerrar_conversacion()
        parar.assert_not_called()
        self.assertFalse(falso.panel_maestro.get_visible())

    def test_minimizar_deja_la_cabecera_y_no_corta_al_maestro(self):
        falso = board_falso()
        falso.ver_conversacion()
        panel = falso.panel_maestro
        with mock.patch("enrutador.conversacion.parar") as parar:
            panel.boton_minimizar.emit("clicked")
        parar.assert_not_called()
        self.assertTrue(panel.minimizado)
        self.assertFalse(panel.scroll.get_visible())      # los mensajes se esconden
        self.assertTrue(panel.titulo.get_visible())       # la cabecera se queda
        panel.boton_minimizar.emit("clicked")
        self.assertFalse(panel.minimizado)
        self.assertTrue(panel.scroll.get_visible())

    def test_el_boton_restaura_la_conversacion_minimizada_antes_de_cerrarla(self):
        falso = board_falso()
        falso.ver_conversacion()
        falso.panel_maestro.minimizar()
        falso.al_ejecutar_maestro()                       # sin texto: no cierra a la primera
        self.assertTrue(falso.panel_maestro.get_visible())
        self.assertFalse(falso.panel_maestro.minimizado)
        falso.al_ejecutar_maestro()                       # ya entera: ahora sí la cierra
        self.assertFalse(falso.panel_maestro.get_visible())

    def test_el_panel_se_mueve_y_no_se_sale_del_tablero(self):
        falso = board_falso()
        panel = falso.panel_maestro
        self.assertFalse(panel.movido)
        panel.mover_a(40, 30)
        self.assertEqual((panel.get_margin_start(), panel.get_margin_top()), (40, 30))
        self.assertTrue(panel.movido)                     # movido a mano: deja de recentrarse
        panel.mover_a(-100, -100)
        self.assertEqual((panel.get_margin_start(), panel.get_margin_top()), (0, 0))

    def test_si_el_maestro_se_niega_lo_escrito_se_queda(self):
        from tareas.cli import ErrorCLI
        falso = board_falso()
        falso.entrada_maestro.set_text("solo la web")
        with mock.patch("enrutador.verbos.hablar_maestro",
                        side_effect=ErrorCLI("Todavía está contestando", "Espera")):
            falso.al_ejecutar_maestro()
        self.assertEqual(falso.entrada_maestro.get_text(), "solo la web")
        self.assertTrue(falso.avisos)

    def test_elegir_otro_modelo_solo_elige_y_lo_recuerda(self):
        falso = board_falso()
        falso.menu_maestro(falso.boton_maestro)
        caja = falso.boton_maestro.get_popover().get_child()
        opciones = botones_de(caja)
        # Los modelos del catálogo, no solo los agentes: Claude trae sus tres alias y Codex sus
        # cuatro de fábrica con nombre exacto (cotejo-ef3xzj).
        self.assertEqual([texto_de_boton(b) for b in opciones],
                         ["opus", "sonnet", "haiku", "gpt-5.6-luna", "gpt-5.6-terra",
                          "gpt-5.6-sol", "gpt-5.6-sol-alto"])
        elegido = next(b for b in opciones if texto_de_boton(b) == "gpt-5.6-sol")
        with mock.patch("enrutador.verbos.hablar_maestro") as hablar:
            elegido.emit("clicked")
        hablar.assert_not_called()
        self.assertEqual(self.guardado["cliente_maestro"], "codex")
        self.assertEqual(self.guardado["modelo_maestro"], "gpt-5.6-sol")
        falso.entrada_maestro.set_text("hola")
        self.assertIn("Codex", falso.boton_maestro.get_tooltip_text())
        with mock.patch("enrutador.verbos.hablar_maestro", return_value=hablado()) as hablar:
            falso.al_ejecutar_maestro()
        self.assertEqual(hablar.call_args.args, ("Uno", "hola", "codex"))
        self.assertEqual(hablar.call_args.kwargs["modelo"], "gpt-5.6-sol")

    def test_el_menu_agrupa_por_cliente_y_solo_los_instalados(self):
        falso = board_falso()
        falso.definiciones = [
            {"clave": "astra", "modelo_id": "gpt-6-astra", "cliente": "codex", "nivel": "n3"},
            {"clave": "kimi", "modelo_id": "opencode-go/kimi", "cliente": "opencode",
             "nivel": "n2"}]
        falso.menu_maestro(falso.boton_maestro)
        caja = falso.boton_maestro.get_popover().get_child()
        textos = etiquetas_de(caja)
        # Los títulos de grupo: Claude y Codex (instalados), sin OpenCode.
        self.assertIn("Claude Code", textos)
        self.assertIn("Codex", textos)
        self.assertNotIn("OpenCode", textos)
        self.assertIn("astra", [texto_de_boton(b) for b in botones_de(caja)])
        self.assertNotIn("kimi", [texto_de_boton(b) for b in botones_de(caja)])
        # Y elegir un modelo concreto lo recuerda y lo manda.
        astra = next(b for b in botones_de(caja) if "astra" in texto_de_boton(b))
        astra.emit("clicked")
        self.assertEqual(self.guardado["modelo_maestro"], "astra")
        falso.entrada_maestro.set_text("hola")
        with mock.patch("enrutador.verbos.hablar_maestro", return_value=hablado()) as hablar:
            falso.al_ejecutar_maestro()
        self.assertEqual(hablar.call_args.kwargs["modelo"], "astra")
        self.assertIn("astra", falso.boton_maestro.get_tooltip_text())

    def test_con_todos_los_proyectos_la_barra_no_se_usa(self):
        falso = board_falso(seleccion=app.comun.TODOS)
        falso.poner_maestro()
        for control in (falso.boton_maestro, falso.entrada_maestro):
            self.assertFalse(control.get_sensitive())

    def test_sin_clientes_avisa(self):
        falso = board_falso()
        falso.entrada_maestro.set_text("hola")
        with mock.patch("enrutador.modelos_vivos.utilizables", return_value=[]), \
                mock.patch("enrutador.modelos_vivos.aviso_sin_listos",
                           return_value=clientes.SIN_AGENTE_TEXTO), \
                mock.patch("enrutador.verbos.hablar_maestro") as hablar:
            falso.al_ejecutar_maestro()
        hablar.assert_not_called()
        self.assertEqual(falso.avisos, [clientes.SIN_AGENTE_TEXTO])


TAREAS = ("- [ ] Arreglar el parseo #agente/sonnet ^cotejo-asig\n"
          "- [ ] Mejorar el mensaje de error ^cotejo-sinm\n")


@unittest.skipUnless(base.HAY_GTK, "sin GTK o sin pantalla")
class ConversacionEnElBoard(base.PestanaInicio):
    def entorno_extra(self, raiz):
        nota = raiz / "vault" / "01-Proyectos" / "Faro.md"
        nota.write_text(f"---\ntipo: proyecto\n---\n\n# Faro\n\n{TAREAS}", encoding="utf-8")
        self.nota = nota
        (raiz / "config.json").write_text(json.dumps({"enrutador": {"motores": {"headless": {
            "comando": [sys.executable, FALSO], "aislar": False}}}}), encoding="utf-8")
        from tareas import preparacion
        for parche in (mock.patch.object(preparacion, "CARPETA", raiz / "estado" / "prep"),
                       mock.patch("enrutador.motores.terminal.abrir", _nunca_una_terminal),
                       mock.patch("enrutador.clientes.shutil.which",
                                  side_effect=lambda n, **_k: None
                                  if n in ("codex", "opencode", "gemini", "agy")
                                  else "/usr/bin/" + os.path.basename(n)),
                       # El maestro solo habla con un agente listo: el falso tiene sesión,
                       # haya o no en la máquina (en el CI no hay).
                       mock.patch("enrutador.modelos_vivos.sesion", return_value=True)):
            parche.start()
            self.addCleanup(parche.stop)
        return {"COTEJO_MOTOR": "agente", "FALSO_PROYECTO": "Faro"}

    def elegir_faro(self):
        self.board.ver_pestana("tablero")
        self.board.al_elegir_chip(self.board.botones_chip["Faro"])
        base.girar(60)

    def turnos(self):
        from enrutador import conversacion
        return conversacion.leer("Faro")["turnos"]

    def hablar(self, texto, **entorno):
        with mock.patch.dict(os.environ, entorno):
            self.board.entrada_maestro.set_text(texto)
            self.board.entrada_maestro.emit("activate")
            self.assertTrue(self.board.panel_maestro.get_visible())
            ok = base.girar_hasta(lambda: len(self.turnos()) >= 2
                                  and self.board.panel_maestro.boton_parar is None, tope=15)
        self.assertTrue(ok, self.turnos())
        base.girar(100)

    def test_apuntar_una_tarea_desde_la_conversacion(self):
        self.elegir_faro()
        self.hablar("apunta que falta el login", FALSO_CREAR="Hacer el login",
                    FALSO_RESPUESTA="Apunté «Hacer el login».")
        todo = base.textos(self.board.panel_maestro)
        self.assertIn("apunta que falta el login", todo)
        self.assertIn("Apunté «Hacer el login».", todo)
        self.assertIn("Hacer el login", self.nota.read_text(encoding="utf-8"))
        # El tablero ya la enseña: se refrescó al volver el turno.
        tareas = [t.texto for p in self.board.app.proyectos if p.nombre == "Faro"
                  for t in p.tareas]
        self.assertTrue(any("Hacer el login" in t for t in tareas), tareas)

    def test_repartir_pasa_a_haciendo_solo_lo_asignado(self):
        self.elegir_faro()
        self.hablar("reparte lo asignado",
                    FALSO_RESPUESTA="Va esta.\nREPARTIR: cotejo-asig cotejo-sinm")
        botones = self.board.panel_maestro.botones_repartir
        self.assertEqual(len(botones), 1)
        self.assertEqual(botones[0].get_label(), "Repartir 1 tarea")
        self.assertFalse(any("REPARTIR" in t for t in base.textos(self.board.panel_maestro)))
        movidas = []
        with mock.patch.object(type(self.board), "mover",
                               lambda _b, proyecto, tarea, destino: movidas.append(
                                   (proyecto.nombre, tarea.id, destino))):
            botones[0].emit("clicked")
        self.assertEqual(movidas, [("Faro", "cotejo-asig", "en-curso")])
        # El botón no vuelve a salir para repartirlas otra vez.
        self.assertTrue(self.turnos()[-1].get("repartido"))
        self.assertFalse(self.board.panel_maestro.botones_repartir[0].get_sensitive())

    # --- el panel flotante (cotejo-w8vteb) ----------------------------------------------------

    def abrir_conversacion(self):
        self.elegir_faro()
        self.board.ver_conversacion()
        base.girar(120)
        self.maquetar()
        return self.board.panel_maestro

    def maquetar(self, ancho=1920, alto=1080):
        """Maqueta el board a mano, como una ventana maximizada. Sin esto las cajas dependen
        de que el compositor mande fotogramas, y a una ventana en un espacio que no se ve
        (el 6 de las pruebas) no se los manda: el panel se quedaba sin colocar."""
        for _vuelta in range(3):
            self.board.measure(Gtk.Orientation.HORIZONTAL, -1)
            self.board.allocate(ancho, alto, -1, None)
            base.girar(30)

    @staticmethod
    def caja(widget, dentro):
        ok, r = widget.compute_bounds(dentro)
        return (r.get_x(), r.get_y(), r.get_width(), r.get_height()) if ok else None

    def test_el_panel_flota_en_el_overlay_y_no_mueve_las_columnas(self):
        self.elegir_faro()
        columna = self.board.columnas["pendiente"][0]
        self.maquetar()
        antes = self.caja(columna, self.board.encima)
        panel = self.abrir_conversacion()
        self.assertIs(panel.get_parent(), self.board.encima)
        self.assertTrue(panel.get_visible())
        # Enseñarlo no empuja ni redimensiona: la columna está exactamente donde estaba.
        self.assertEqual(self.caja(columna, self.board.encima), antes)
        caja = self.caja(panel, self.board.encima)
        self.assertIsNotNone(caja)
        self.assertGreaterEqual(caja[0], 0)
        self.assertGreaterEqual(caja[1], 0)
        self.assertLessEqual(caja[0] + caja[2], self.board.encima.get_width())
        self.assertLessEqual(caja[1] + caja[3], self.board.encima.get_height())

    def test_el_panel_se_arrastra_dentro_del_tablero(self):
        panel = self.abrir_conversacion()
        panel.mover_a(20, 30)
        self.maquetar()
        caja = self.caja(panel, self.board.encima)
        self.assertEqual((round(caja[0]), round(caja[1])), (20, 30))
        self.assertTrue(panel.movido)
        # Fuera del tablero no: se queda pegado al borde.
        panel.mover_a(-500, -500)
        self.maquetar()
        caja = self.caja(panel, self.board.encima)
        self.assertEqual((round(caja[0]), round(caja[1])), (0, 0))

    def test_minimizar_deja_solo_la_cabecera(self):
        panel = self.abrir_conversacion()
        panel.boton_minimizar.emit("clicked")
        base.girar(60)
        self.assertTrue(panel.minimizado)
        self.assertFalse(panel.scroll.get_visible())
        self.assertTrue(panel.titulo.get_visible())
        # El maestro sigue disponible: la barra del pie no se toca.
        self.assertTrue(self.board.barra_del_maestro.get_visible())
        panel.boton_minimizar.emit("clicked")
        self.assertTrue(panel.scroll.get_visible())

    # --- dónde cae (cotejo-5ejs0y) -------------------------------------------------------------

    def hueco_sobre_el_pie(self, panel):
        """Píxeles entre el borde de abajo del panel y el de arriba del pie (negativo: lo tapa)."""
        caja, pie = self.caja(panel, self.board.encima), self.caja(self.board.pie,
                                                                   self.board.encima)
        return pie[1] - (caja[1] + caja[3])

    def test_al_abrir_queda_encima_del_pie_y_no_en_el_centro(self):
        from tareas.app.comun import ESPACIADO_LG
        from tareas.app.escala import px
        panel = self.abrir_conversacion()
        hueco = self.hueco_sobre_el_pie(panel)
        self.assertGreaterEqual(hueco, 0)                 # no tapa el campo del maestro
        self.assertLessEqual(hueco, px(ESPACIADO_LG) + 2)  # pero está pegado a él
        caja = self.caja(panel, self.board.encima)
        centro_x = caja[0] + caja[2] / 2
        self.assertAlmostEqual(centro_x, self.board.encima.get_width() / 2, delta=2)
        # Con mensajes crece hacia arriba, sin despegarse del pie.
        self.hablar("¿cómo va?", FALSO_RESPUESTA="Todo en orden.\n" * 6)
        self.maquetar()
        self.assertGreater(self.caja(panel, self.board.encima)[3], caja[3])
        self.assertLessEqual(self.hueco_sobre_el_pie(panel), px(ESPACIADO_LG) + 2)
        self.assertGreaterEqual(self.hueco_sobre_el_pie(panel), 0)

    def test_minimizado_la_cabecera_queda_junto_al_pie(self):
        from tareas.app.comun import ESPACIADO_LG
        from tareas.app.escala import px
        self.elegir_faro()
        self.hablar("¿cómo va?", FALSO_RESPUESTA="Todo en orden.\n" * 6)
        panel = self.board.panel_maestro
        self.maquetar()
        entero = self.caja(panel, self.board.encima)
        panel.boton_minimizar.emit("clicked")
        self.maquetar()
        chico = self.caja(panel, self.board.encima)
        self.assertLess(chico[3], entero[3])              # solo la cabecera
        self.assertGreater(chico[1], entero[1])           # bajó: no se queda a media altura
        hueco = self.hueco_sobre_el_pie(panel)
        self.assertGreaterEqual(hueco, 0)
        self.assertLessEqual(hueco, px(ESPACIADO_LG) + 2)
        panel.boton_minimizar.emit("clicked")             # restaurar: vuelve a crecer hacia arriba
        self.maquetar()
        self.assertEqual(self.caja(panel, self.board.encima), entero)

    def test_arrastrado_se_queda_donde_lo_dejaron_aunque_se_minimice(self):
        panel = self.abrir_conversacion()
        x, y = panel.posicion()
        panel.mover_a(x - 30, y - 200)
        self.maquetar()
        donde = self.caja(panel, self.board.encima)[:2]
        panel.boton_minimizar.emit("clicked")
        self.maquetar()
        self.assertEqual(self.caja(panel, self.board.encima)[:2], donde)
        panel.boton_minimizar.emit("clicked")
        self.maquetar()
        self.assertEqual(self.caja(panel, self.board.encima)[:2], donde)
        # Cerrar y volver a abrir respeta el sitio elegido.
        self.board.cerrar_conversacion()
        self.board.ver_conversacion()
        self.maquetar()
        self.assertEqual(self.caja(panel, self.board.encima)[:2], donde)

    def test_cerrar_y_volver_a_abrir_el_panel_no_pierde_la_conversacion(self):
        self.elegir_faro()
        self.hablar("¿cómo va?", FALSO_RESPUESTA="Todo en orden.")
        self.board.cerrar_conversacion()
        self.assertFalse(self.board.panel_maestro.get_visible())
        self.board.ver_conversacion()
        base.girar(60)
        self.assertTrue(self.board.panel_maestro.get_visible())
        todo = base.textos(self.board.panel_maestro)
        self.assertIn("¿cómo va?", todo)
        self.assertIn("Todo en orden.", todo)

    def test_cerrar_mientras_contesta_no_corta_el_turno(self):
        self.elegir_faro()
        freno = self.nota.with_name("freno-maestro")
        with mock.patch.dict(os.environ, {"FALSO_ESPERA_HASTA": str(freno),
                                          "FALSO_RESPUESTA": "Sigo aquí."}):
            self.board.entrada_maestro.set_text("¿cómo va?")
            self.board.entrada_maestro.emit("activate")
            self.assertTrue(self.board.panel_maestro.get_visible())
            with mock.patch("enrutador.conversacion.parar") as parar:
                self.board.cerrar_conversacion()
            parar.assert_not_called()
            self.assertFalse(self.board.panel_maestro.get_visible())
            # El maestro sigue trabajando aunque su panel esté cerrado.
            from enrutador import conversacion
            self.assertTrue(conversacion.leer("Faro").get("en_curso"))
            freno.write_text("", encoding="utf-8")
            ok = base.girar_hasta(lambda: len(self.turnos()) >= 2, tope=15)
        self.assertTrue(ok, self.turnos())
        # Al volver a abrirlo, la respuesta está esperando.
        self.board.ver_conversacion()
        base.girar(60)
        self.assertIn("Sigo aquí.", base.textos(self.board.panel_maestro))


if __name__ == "__main__":
    unittest.main()
