"""La pestaña Inicio en el board de verdad (v1.3.0): abre antes que el tablero.

Prueba de humo con GTK y pantalla (sin ellas se salta), sobre un vault de mentira: el board
abre en Inicio con el titular y una tarjeta por proyecto; «Nuevo proyecto» de momento avisa;
una tarjeta lleva al mapa y de ahí al tablero con su proyecto elegido; y sin de dónde leer
abre en «Revisar el equipo» (el primer arranque), que pasa al Inicio. La lógica de lo que se enseña se prueba sin
GTK en `test_resumen_inicio.py`.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

try:
    from tareas import app, entrevista, inicio  # antes que gi.repository: pide las versiones de GTK 4
    from tareas.app import pestana_inicio
    from gi.repository import Gio, GLib, Gtk
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def girar(ms=60):
    contexto = GLib.MainContext.default()
    limite = GLib.get_monotonic_time() + ms * 1000
    while GLib.get_monotonic_time() < limite:
        contexto.iteration(False)


def textos(widget, acumulado=None):
    acumulado = [] if acumulado is None else acumulado
    if isinstance(widget, Gtk.Label) and widget.get_label():
        acumulado.append(widget.get_label())
    hijo = widget.get_first_child()
    while hijo is not None:
        textos(hijo, acumulado)
        hijo = hijo.get_next_sibling()
    return acumulado


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se arma el board")
class PestanaInicio(unittest.TestCase):
    apps = 0
    con_vault = True

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        raiz = Path(temporal.name)
        entorno = {"COTEJO_CONFIG": str(raiz / "config.json"), "COTEJO_ESTADO": str(raiz / "estado")}
        if self.con_vault:
            (raiz / "vault" / "01-Proyectos").mkdir(parents=True)
            for nombre, lineas in (("Faro", "- [ ] Uno\n- [ ] Dos #por-validar\n"),
                                   ("Horizonte", "- [ ] Tres\n")):
                (raiz / "vault" / "01-Proyectos" / f"{nombre}.md").write_text(
                    f"---\ntipo: proyecto\n---\n\n# {nombre}\n\n{lineas}", encoding="utf-8")
            entorno["COTEJO_VAULT"] = str(raiz / "vault")
        else:
            entorno["COTEJO_FUENTE"] = "repo"   # una fuente de repos sin ninguno: primer arranque
        entorno.update(self.entorno_extra(raiz))
        parche = mock.patch.dict(os.environ)
        parche.start()
        self.addCleanup(parche.stop)
        for var in ("COTEJO_REPOS", "COTEJO_RAIZ_REPOS", "COTEJO_FUENTE", "COTEJO_VAULT"):
            os.environ.pop(var, None)
        os.environ.update(entorno)
        parche = mock.patch.object(app.App, "poner_lo_del_usuario", return_value=None)
        parche.start()
        self.addCleanup(parche.stop)

        ajustes = Gtk.Settings.get_default()
        antes = ajustes.get_property("gtk-enable-animations")
        ajustes.set_property("gtk-enable-animations", False)
        self.addCleanup(ajustes.set_property, "gtk-enable-animations", antes)

        from tareas.app import escala
        self.factor_antes = escala.FACTOR
        self.app = app.App()
        PestanaInicio.apps += 1
        self.app.set_application_id(f"io.github.cotejoapp.CotejoPruebaInicio{os.getpid()}n{self.apps}")
        self.app.set_flags(self.app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
        self.app.register(None)
        self.addCleanup(self.cerrar)
        self.app.desde_cero = False
        self.app.abrir_board()
        self.board = self.app.board
        girar()

    def entorno_extra(self, raiz):
        """Lo que una subclase añade al entorno antes de abrir el board (p. ej. sus repos)."""
        return {}

    def cerrar(self):
        for monitor in self.app.monitores:
            monitor.cancel()
        if self.app.board is not None:
            self.app.board.destroy()
        self.app.release()
        # Lo que la App deja en el proceso y no en su ventana: su CSS en la pantalla, el DPI de
        # la letra y el factor de escala. Sin quitarlos, las pruebas que corren después (las
        # que miden un widget suelto, como `test_columnas_fijas`) medían con el tema y la letra
        # del board y no con los suyos (cotejo-9ybn1a).
        from gi.repository import Gdk
        from tareas.app import escala
        if self.app.proveedor is not None and Gdk.Display.get_default() is not None:
            Gtk.StyleContext.remove_provider_for_display(Gdk.Display.get_default(),
                                                         self.app.proveedor)
        if self.app.dpi_de_letra is not None and Gtk.Settings.get_default() is not None:
            Gtk.Settings.get_default().props.gtk_xft_dpi = self.app.dpi_de_letra
        escala.FACTOR = self.factor_antes


class ConProyectos(PestanaInicio):
    def test_abre_en_inicio_con_el_resumen_y_una_tarjeta_por_proyecto(self):
        b = self.board
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)
        self.assertTrue(b.botones_pestana[pestana_inicio.INICIO].get_active())
        self.assertFalse(b.banda_proyectos.get_visible())
        self.assertFalse(b.buscador.get_visible())
        todo = textos(b.pestanas.get_child_by_name(pestana_inicio.INICIO))
        self.assertIn("Tienes 2 proyectos y 1 entrega por comprobar", todo)
        self.assertIn("1 por comprobar", todo)
        self.assertIn("sin arquitectura todavía", todo)
        self.assertIn("Empezar un proyecto", todo)
        # Faro (con una entrega por comprobar) primero; «Nuevo proyecto» al final.
        nombres = [t for t in todo if t in ("Faro", "Horizonte")]
        self.assertEqual(nombres, ["Faro", "Horizonte"])
        # La constelación sale con los dos proyectos (sin arquitectura: dos núcleos huecos).
        self.assertTrue(b.area_constelacion.get_visible())
        self.assertEqual([p.nombre for p in b.constelacion.proyectos], ["Faro", "Horizonte"])
        b.poner_constelacion(None)
        self.assertFalse(b.area_constelacion.get_visible())

    def test_nuevo_proyecto_abre_la_entrevista(self):
        b = self.board
        with mock.patch("enrutador.clientes.instalados", return_value=["claude"]):
            b.nuevo_proyecto()
        self.assertEqual(b.pestana_actual(), "entrevista")
        todo = textos(b.pestanas.get_child_by_name("entrevista"))
        for pregunta in ("1. ¿Qué quieres construir?", "2. ¿Quién la va a usar?",
                         "3. ¿Qué tiene que hacer la primera versión?",
                         "4. ¿Dónde la van a usar?", "5. ¿Qué más necesita?",
                         "6. ¿Qué dejamos para después? (opcional)"):
            self.assertIn(pregunta, todo)
        # Los ejemplos van en gris: vacía, no se puede preparar el proyecto de ejemplo.
        self.assertEqual(b.ent_que_es.get_text(), "")
        self.assertEqual(b.ent_que_es.get_placeholder_text(), entrevista.EJEMPLOS["que_es"])
        self.assertTrue(b.ent_que_hace_ejemplo.get_visible())
        self.assertFalse(b.ent_preparar.get_sensitive())
        b.ent_que_hace.get_buffer().set_text("Ver citas")
        self.assertFalse(b.ent_que_hace_ejemplo.get_visible())
        self.assertEqual(b.ent_ver.get_label(), "Ver lo que se le enviará a tu agente")
        self.assertEqual(b.agente_elegido(), "claude")
        self.assertEqual(b.ent_agente_pista.get_label(), "detectado")
        b.cancelar_entrevista()
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)

    def abrir_entrevista(self, agentes=("claude",)):
        with mock.patch("enrutador.clientes.instalados", return_value=list(agentes)):
            self.board.nuevo_proyecto()
        # Llega vacía (los ejemplos son solo el texto en gris): se rellena con ellos.
        b, ej = self.board, entrevista.EJEMPLOS
        b.ent_que_es.set_text(ej["que_es"])
        b.ent_para_quien.set_text(ej["para_quien"])
        b.ent_que_hace.get_buffer().set_text(ej["que_hace"])
        b.ent_fuera.set_text(ej["fuera"])
        return b

    def test_el_formulario_arma_las_respuestas(self):
        b = self.abrir_entrevista()
        b.ent_que_es.set_text("Una agenda de citas")
        b.ent_para_quien.set_text("Mi equipo")
        b.ent_que_hace.get_buffer().set_text("Ver citas\nCrear citas")
        b.ent_donde["En el computador, como programa"].set_active(True)
        b.ent_donde["En el celular"].set_active(False)
        b.ent_necesita["Cobrar pagos"].set_active(True)
        b.ent_fuera.set_text("")
        b.ent_carpeta.set_text("/tmp/agenda-citas")
        r = b.respuestas_entrevista()
        self.assertEqual(r, inicio.Respuestas(
            que_es="Una agenda de citas", para_quien="Mi equipo",
            que_hace="Ver citas\nCrear citas", carpeta="/tmp/agenda-citas",
            donde_se_usa="En el navegador, En el computador, como programa",
            necesita="Guardar datos, Cobrar pagos, Enviar avisos (WhatsApp, correo)", fuera=""))

    def test_la_carpeta_sigue_a_la_pregunta_uno_hasta_que_se_toca(self):
        b = self.abrir_entrevista()
        b.ent_que_es.set_text("Una tienda de velas")
        self.assertTrue(b.ent_carpeta.get_text().endswith("/Proyectos/tienda-velas"))
        b.ent_carpeta.set_text("/tmp/mia")
        b.ent_que_es.set_text("Otra cosa distinta")
        self.assertEqual(b.ent_carpeta.get_text(), "/tmp/mia")

    def test_ver_lo_que_se_enviara_es_exactamente_armar(self):
        b = self.abrir_entrevista()
        b.ent_que_es.set_text("Un blog de recetas")
        b.ent_carpeta.set_text("/tmp/blog-recetas")
        esperado = inicio.armar(b.respuestas_entrevista())
        self.assertEqual(b._texto_de(b.ent_prompt), esperado)
        self.assertIn("Un blog de recetas", esperado)
        # Y se actualiza al cambiar una respuesta.
        b.ent_fuera.set_text("Nada de pagos")
        self.assertEqual(b._texto_de(b.ent_prompt), inicio.armar(b.respuestas_entrevista()))
        self.assertIn("Nada de pagos", b._texto_de(b.ent_prompt))

    def test_con_campos_vacios_no_se_puede_preparar(self):
        b = self.abrir_entrevista()
        for vacio in ("ent_que_es", "ent_carpeta"):
            b.ent_que_es.set_text("Algo")
            b.ent_carpeta.set_text("/tmp/algo")
            self.assertTrue(b.ent_preparar.get_sensitive())
            getattr(b, vacio).set_text("")
            self.assertFalse(b.ent_preparar.get_sensitive(), vacio)
            self.assertTrue(b.ent_error.get_visible())
        b.ent_carpeta.set_text("/tmp/algo")
        b.ent_que_hace.get_buffer().set_text("")
        self.assertFalse(b.ent_preparar.get_sensitive())
        with mock.patch("enrutador.preparar.lanzar") as lanzar:
            self.assertIsNone(b.preparar_proyecto())
        lanzar.assert_not_called()

    def test_el_boton_inicio_sale_de_la_entrevista(self):
        b = self.abrir_entrevista()
        self.assertTrue(b.botones_pestana["inicio"].get_active())
        b.botones_pestana["inicio"].emit("clicked")
        self.assertEqual(b.pestana_actual(), "inicio")

    def test_sin_agente_instalado_no_se_puede_preparar(self):
        b = self.abrir_entrevista(agentes=())
        self.assertIsNone(b.agente_elegido())
        self.assertFalse(b.ent_preparar.get_sensitive())
        self.assertIn("ningún agente", b.ent_agente_pista.get_label())

    def test_preparar_lanza_con_la_carpeta_y_el_agente_elegidos(self):
        b = self.abrir_entrevista(agentes=("claude", "codex"))
        b.ent_agente.set_selected(1)
        b.ent_carpeta.set_text("/tmp/mi-proyecto")
        estado = {"id": "mi-proyecto-abc123", "proyecto": "mi-proyecto"}
        with mock.patch("enrutador.preparar.lanzar", return_value=estado) as lanzar, \
                mock.patch.object(b, "mostrar_preparando") as gancho:
            self.assertEqual(b.preparar_proyecto(), estado)
        (r,), nombrados = lanzar.call_args
        self.assertEqual(r.carpeta, "/tmp/mi-proyecto")
        self.assertEqual(r, inicio.validar(b.respuestas_entrevista()))
        self.assertEqual(nombrados["cliente"], "codex")
        gancho.assert_called_once_with(estado)
        # El aviso de fin se entrega en el hilo de la interfaz, a preparacion_terminada.
        with mock.patch.object(b, "preparacion_terminada") as fin, \
                mock.patch("tareas.app.entrevista.GLib.idle_add") as idle:
            with mock.patch("enrutador.preparar.lanzar", return_value=estado) as lanzar:
                b.preparar_proyecto()
            lanzar.call_args.kwargs["al_terminar"]({"id": "x"})
        idle.assert_called_once_with(fin, {"id": "x"})

    def test_el_formulario_elige_el_modelo_exacto_del_catalogo(self):
        b = self.abrir_entrevista(agentes=("claude", "codex"))
        modelos = lambda d: [d.get_model().get_string(i)                # noqa: E731
                             for i in range(d.get_model().get_n_items())]
        # Sin tocar nada, el equivalente a n2 de cada agente.
        self.assertEqual(b.modelo_elegido(), "sonnet")
        self.assertEqual(modelos(b.ent_modelo), ["opus", "sonnet", "haiku"])
        b.ent_agente.set_selected(1)   # Codex
        self.assertEqual(b.modelo_elegido(), "gpt-5.6-sol")
        self.assertEqual(modelos(b.ent_modelo),
                         ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6-sol-alto"])
        b.ent_modelo.set_selected(
            [m.modelo for m in b.ent_modelos].index("gpt-5.6-sol-alto"))
        self.assertEqual(b.modelo_elegido(), "gpt-5.6-sol-alto")
        b.ent_carpeta.set_text("/tmp/mi-proyecto")
        estado = {"id": "mi-proyecto-abc123", "proyecto": "mi-proyecto"}
        with mock.patch("enrutador.preparar.lanzar", return_value=estado) as lanzar, \
                mock.patch.object(b, "mostrar_preparando"):
            b.preparar_proyecto()
        self.assertEqual(lanzar.call_args.kwargs["cliente"], "codex")
        self.assertEqual(lanzar.call_args.kwargs["modelo"], "gpt-5.6-sol-alto")

    def test_el_formulario_ensena_los_modelos_registrados_de_su_agente(self):
        b = self.abrir_entrevista(agentes=("codex",))
        b.definiciones = [{"clave": "astra", "modelo_id": "gpt-6-astra", "cliente": "codex",
                           "nivel": "n3"}]
        b.llenar_modelos()
        modelos = [b.ent_modelo.get_model().get_string(i)
                   for i in range(b.ent_modelo.get_model().get_n_items())]
        self.assertIn("astra", modelos)
        b.ent_modelo.set_selected([m.modelo for m in b.ent_modelos].index("astra"))
        self.assertEqual(b.modelo_elegido(), "astra")

    def test_si_no_se_puede_lanzar_se_avisa_y_se_queda(self):
        from enrutador import preparar
        b = self.abrir_entrevista()
        with mock.patch("enrutador.preparar.lanzar",
                        side_effect=preparar.NoSePuede("No encontré «claude»")), \
                mock.patch.object(b, "aviso") as aviso:
            self.assertIsNone(b.preparar_proyecto())
        aviso.assert_called_once_with("No encontré «claude»")
        self.assertEqual(b.pestana_actual(), "entrevista")

    def test_una_tarjeta_lleva_al_mapa_y_de_ahi_al_tablero_con_su_proyecto(self):
        b = self.board
        b.abrir_proyecto("Horizonte")
        girar()
        self.assertEqual(b.pestana_actual(), "mapa")   # sin arquitectura: el mapa lo dice
        self.assertTrue(b.pantalla_mapa.vacio.get_visible())
        b.pantalla_mapa.boton_tablero.emit("clicked")
        girar()
        self.assertEqual(b.pestana_actual(), pestana_inicio.TABLERO)
        self.assertEqual(b.seleccion, "Horizonte")
        self.assertTrue(b.banda_proyectos.get_visible())
        self.assertTrue(b.buscador.get_visible())
        # Y el selector de la cabecera vuelve a Inicio.
        b.botones_pestana[pestana_inicio.INICIO].set_active(True)
        girar()
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)

    def test_agentes_lleva_a_revisar_el_equipo_despues_del_primer_arranque(self):
        b = self.board
        with mock.patch("enrutador.clientes.instalados", return_value=[]), \
                mock.patch("tareas.instalar_agentes.sumar_al_path", return_value=[]), \
                mock.patch("tareas.instalar_agentes.instalado", return_value=False):
            b.inicio_agentes.emit("clicked")
        self.assertEqual(b.pestana_actual(), "equipo")
        self.assertEqual(b.equipo_ceja.get_label(), "Tus agentes")
        b.equipo_seguir.emit("clicked")
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)

    def test_anadir_modelo_lleva_a_revisar_el_equipo(self):
        b = self.board
        with mock.patch.object(b, "listar_en_fondo"):
            dialogo = b.abrir_anadir_modelo()
        self.assertIn("Instálalo o conéctalo", dialogo.ir_al_equipo.get_label())
        with mock.patch("enrutador.clientes.instalados", return_value=[]), \
                mock.patch("tareas.instalar_agentes.sumar_al_path", return_value=[]), \
                mock.patch("tareas.instalar_agentes.instalado", return_value=False):
            dialogo.ir_al_equipo.emit("clicked")
        girar()
        self.assertEqual(b.pestana_actual(), "equipo")
        self.assertIsNone(b.dialogo_modelo)

    def test_buscar_lleva_al_tablero(self):
        self.app.buscar()
        self.assertEqual(self.board.pestana_actual(), pestana_inicio.TABLERO)


def girar_hasta(condicion, tope=10.0):
    limite = GLib.get_monotonic_time() + int(tope * 1e6)
    contexto = GLib.MainContext.default()
    while GLib.get_monotonic_time() < limite:
        if condicion():
            return True
        contexto.iteration(False)
    return condicion()


class SinFuente(PestanaInicio):
    """Sin de dónde leer: «Revisar el equipo». HOME y PATH son de mentira (cotejo-2j6un7): ni
    los agentes ni las sesiones de esta máquina cuentan, y lo que se «instala» es un script
    falso que escribe un CLI falso en `~/.local/bin` de esa casa."""
    con_vault = False

    def entorno_extra(self, raiz):
        import shutil
        self.casa = raiz / "casa"
        self.bin = raiz / "bin"
        sistema = raiz / "sistema"
        for carpeta in (self.casa, self.bin, sistema):
            carpeta.mkdir()
        for nombre in ("sh", "bash", "mkdir", "chmod", "sleep", "cat", "git"):
            real = shutil.which(nombre)
            if real:
                (sistema / nombre).symlink_to(real)
        # Si git puede empujar depende de /etc/gitconfig de la máquina (en el CI no hay helper):
        # aquí siempre puede, salvo en las pruebas que digan otra cosa.
        parche = mock.patch("tareas.equipo.puede_empujar", return_value="helper")
        parche.start()
        self.addCleanup(parche.stop)
        return {"HOME": str(self.casa), "XDG_DATA_HOME": str(self.casa / ".local" / "share"),
                "PATH": f"{self.bin}{os.pathsep}{sistema}", "ANTHROPIC_API_KEY": "",
                "CLAUDE_CODE_OAUTH_TOKEN": "", "OPENAI_API_KEY": "", "CODEX_HOME": "",
                "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "GOOGLE_GENAI_USE_VERTEXAI": "",
                # Aquí los CLIs son de mentira: sí se les pregunta.
                "COTEJO_NO_PREGUNTAR_CLI": ""}

    def revisar(self, agentes, git=True, sin_sesion=(), empuja="helper"):
        with mock.patch("enrutador.clientes.instalados", return_value=list(agentes)), \
                mock.patch("enrutador.modelos_vivos.sesion", lambda n, **_: n not in sin_sesion), \
                mock.patch("enrutador.modelos_vivos.en_cache", return_value=["modelo"]), \
                mock.patch("tareas.equipo.hay_git", return_value=git), \
                mock.patch("tareas.equipo.puede_empujar", return_value=empuja):
            return self.board.revisar_equipo()

    def con_instalador(self, texto):
        from tareas import instalar_agentes

        def falso(url, destino, tope=None):
            destino.write_text(texto, encoding="utf-8")
        parche = mock.patch.object(instalar_agentes, "descargar", side_effect=falso)
        parche.start()
        self.addCleanup(parche.stop)

    def progreso(self, clave):
        etiqueta = self.board.equipo_progreso[clave]
        return etiqueta.get_label() if etiqueta.get_visible() else ""

    def filas(self):
        """{titulo: estado} de lo que pinta la pantalla."""
        resultado = {}
        fila = self.board.equipo_filas.get_first_child()
        while fila is not None:
            t = textos(fila)
            resultado[t[0]] = t[1]
            fila = fila.get_next_sibling()
        return resultado

    def test_la_primera_vez_abre_revisar_el_equipo_y_no_el_primer_arranque_viejo(self):
        b = self.board
        self.assertIsNotNone(b.fuente.problema)
        self.assertEqual(b.pestana_actual(), "equipo")
        todo = " | ".join(textos(b.pestanas.get_child_by_name("equipo")))
        self.assertIn("Antes de empezar, Cotejo revisa tu equipo", todo)
        self.assertNotIn("Pídele a tu agente", todo)
        self.assertNotIn("cotejo init --repo", todo)
        self.assertFalse(b.banda_proyectos.get_visible())

    def test_marca_cada_uno_con_todo_ninguno_o_algunos(self):
        b = self.board
        self.revisar(["claude", "opencode", "codex", "gemini"], git=True)
        filas = self.filas()
        self.assertEqual(filas.pop("Antigravity CLI"), "No instalado")   # cotejo-r4yg0n
        self.assertEqual(set(filas.values()), {"Listo"})
        self.assertEqual(set(b.equipo_enlaces), {"antigravity"})
        self.assertEqual(b.equipo_titular.get_label(), "Todo listo: tienes 4 agentes")

        self.revisar(["antigravity"], git=True, sin_sesion={"antigravity"})
        self.assertEqual(self.filas()["Antigravity CLI"], "Instalado")   # su sesión no se ve
        self.assertEqual(b.equipo_titular.get_label(),
                         "Todo listo para empezar con Antigravity CLI")

        self.revisar([], git=False)
        self.assertEqual(set(self.filas().values()), {"No instalado"})
        self.assertEqual(set(b.equipo_enlaces),
                         {"claude", "opencode", "codex", "gemini", "antigravity", "git"})
        self.assertEqual(b.equipo_titular.get_label(), "Te falta un agente de IA")

        self.revisar(["gemini"], git=True)
        filas = self.filas()
        self.assertEqual(filas["Gemini CLI"], "Listo")
        self.assertEqual(filas["Claude Code"], "No instalado")
        self.assertEqual(filas["git (para guardar versiones)"], "Listo")
        self.assertNotIn("gemini", b.equipo_enlaces)
        self.assertNotIn("git", b.equipo_enlaces)

    def test_el_enlace_de_uno_que_falta_abre_su_pagina_oficial_y_no_instala(self):
        from tareas import equipo as logica
        b = self.board
        self.revisar(["claude"], git=False)
        with mock.patch.object(b, "abrir_pagina") as abrir, \
                mock.patch("subprocess.run") as correr, mock.patch("subprocess.Popen") as popen:
            b.equipo_enlaces["git"].emit("clicked")
            b.equipo_enlaces["codex"].emit("clicked")
        self.assertEqual([c.args[0] for c in abrir.call_args_list],
                         [logica.PAGINAS["git"], logica.PAGINAS["codex"]])
        correr.assert_not_called()
        popen.assert_not_called()

    def test_git_sin_credenciales_ofrece_conectar_y_no_dice_listo(self):
        # cotejo-vz6v3c: git instalado pero sin con qué empujar pediría contraseña al guardar.
        b = self.board
        self.revisar(["claude"], git=True, empuja=None)
        self.assertEqual(self.filas()["git (para guardar versiones)"], "Falta conectar")
        self.assertNotIn("Todo listo", b.equipo_titular.get_label())
        self.assertIn("git", b.equipo_sesion)
        from tareas import instalar_agentes
        with mock.patch.object(instalar_agentes, "terminal", return_value=["mi-terminal"]), \
                mock.patch("shutil.which", return_value="/usr/bin/gh"), \
                mock.patch("tareas.equipo.gh_con_sesion", return_value=False), \
                mock.patch("enrutador.motores.terminal.abrir") as abrir, \
                mock.patch("tareas.equipo.hay_git", return_value=True), \
                mock.patch("tareas.equipo.puede_empujar", return_value=None):
            b.equipo_sesion["git"].emit("clicked")
        abrir.assert_called_once_with(["mi-terminal", "/usr/bin/gh", "auth", "login"])
        self.assertIn("gh auth login", self.progreso("git"))

        with mock.patch.object(b, "abrir_pagina") as pagina, \
                mock.patch.object(instalar_agentes, "conectar_git",
                                  return_value=instalar_agentes.Apertura("sin_gh", "")):
            b.conectar_git()
        pagina.assert_called_once_with("https://cli.github.com/")
        self.assertIn("GitHub CLI", self.progreso("git"))

        self.revisar(["claude"], git=True, empuja="helper")
        self.assertEqual(self.filas()["git (para guardar versiones)"], "Listo")
        self.assertNotIn("git", b.equipo_sesion)

    def test_abrir_pagina_usa_el_lanzador_del_sistema(self):
        with mock.patch("tareas.app.equipo.Gio.AppInfo.launch_default_for_uri") as lanzar:
            self.board.abrir_pagina("https://ejemplo.org/x")
        lanzar.assert_called_once_with("https://ejemplo.org/x", None)

    def test_revisar_otra_vez_vuelve_a_detectar(self):
        b = self.board
        self.revisar([], git=True)
        self.assertEqual(self.filas()["Claude Code"], "No instalado")
        with mock.patch("enrutador.clientes.instalados", return_value=["claude"]), \
                mock.patch("enrutador.modelos_vivos.sesion", return_value=True), \
                mock.patch("enrutador.modelos_vivos.en_cache", return_value=["sonnet"]), \
                mock.patch("tareas.equipo.hay_git", return_value=True), \
                mock.patch("tareas.equipo.puede_empujar", return_value="ssh"):
            b.equipo_revisar.emit("clicked")
        self.assertEqual(self.filas()["Claude Code"], "Listo")
        self.assertEqual(b.equipo_titular.get_label(), "Todo listo para empezar con Claude Code")
        self.assertNotIn("claude", b.equipo_enlaces)

    def test_seguir_al_inicio_pasa_a_la_pestana_inicio(self):
        b = self.board
        b.equipo_seguir.emit("clicked")
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)
        self.assertTrue(b.botones_pestana[pestana_inicio.INICIO].get_active())

    def test_sin_ningun_agente_ofrece_instalar_y_recomienda_uno(self):
        b = self.board
        b.revisar_equipo()
        filas = self.filas()
        filas.pop("git (para guardar versiones)")
        self.assertEqual(set(filas.values()), {"No instalado"})
        self.assertEqual(set(b.equipo_instalar), {"claude", "codex", "opencode", "antigravity"})
        self.assertIn("gemini", b.equipo_enlaces)          # Gemini CLI y git, solo enlace
        self.assertEqual(b.equipo_sesion, {})
        todo = " | ".join(textos(b.pestanas.get_child_by_name("equipo")))
        self.assertIn("Si no sabes cuál elegir, empieza por este.", todo)
        self.assertIn("Solo con licencia de empresa", todo)
        self.assertIn("Primer arranque", todo)
        self.assertEqual(b.equipo_titular.get_label(), "Te falta un agente de IA")

    def test_instalar_corre_el_oficial_y_ensena_el_progreso(self):
        b = self.board
        b.revisar_equipo()
        self.con_instalador(
            "echo 'Bajando Claude Code'\nsleep 0.4\n"
            "mkdir -p \"$HOME/.local/bin\"\n"
            "printf '#!/bin/sh\\n' > \"$HOME/.local/bin/claude\"\n"
            "chmod +x \"$HOME/.local/bin/claude\"\necho 'Instalación completa'\n")
        with mock.patch.object(b, "abrir_pagina") as abrir:
            b.equipo_instalar["claude"].emit("clicked")
        abrir.assert_not_called()
        self.assertTrue(girar_hasta(lambda: "Bajando Claude Code" in self.progreso("claude")))
        self.assertIn("claude", b.equipo_cancelar)                  # mientras corre, Cancelar
        self.assertFalse(b.equipo_instalar["codex"].get_sensitive())  # uno a la vez
        trabajo = b.equipo_trabajos["claude"]
        self.assertTrue(girar_hasta(lambda: not trabajo.corriendo and
                                    "quedó instalado" in self.progreso("claude")))
        self.assertEqual(self.filas()["Claude Code"], "Falta iniciar sesión")
        self.assertIn("claude", b.equipo_sesion)
        self.assertTrue(b.equipo_instalar["codex"].get_sensitive())

    def test_cancelar_un_instalador(self):
        b = self.board
        b.revisar_equipo()
        self.con_instalador("echo empiezo\nsleep 30\n")
        b.equipo_instalar["opencode"].emit("clicked")
        self.assertTrue(girar_hasta(lambda: "empiezo" in self.progreso("opencode")))
        b.equipo_cancelar["opencode"].emit("clicked")
        self.assertTrue(girar_hasta(lambda: "Cancelado" in self.progreso("opencode")))
        self.assertEqual(self.filas()["OpenCode"], "No instalado")
        self.assertIn("opencode", b.equipo_instalar)

    def test_iniciar_sesion_abre_el_login_oficial_y_el_sondeo_nota_que_quedo(self):
        from tareas import instalar_agentes
        b = self.board
        claude = self.bin / "claude"
        claude.write_text("#!/bin/sh\n", encoding="utf-8")
        claude.chmod(0o755)
        b.revisar_equipo()
        self.assertEqual(self.filas()["Claude Code"], "Falta iniciar sesión")
        self.assertEqual(b.equipo_titular.get_label(), "Te falta iniciar sesión en Claude Code")
        with mock.patch.object(instalar_agentes, "terminal", return_value=["mi-terminal"]), \
                mock.patch("enrutador.motores.terminal.abrir") as abrir:
            b.equipo_sesion["claude"].emit("clicked")
        abrir.assert_called_once_with(["mi-terminal", str(claude), "auth", "login"])
        self.assertIn("claude auth login", self.progreso("claude"))
        self.assertEqual(self.filas()["Claude Code"], "Falta iniciar sesión")
        (self.casa / ".claude").mkdir()
        (self.casa / ".claude" / ".credentials.json").write_text("{}", encoding="utf-8")
        self.assertTrue(b.sondear_equipo())                 # detecta en un hilo
        self.assertTrue(girar_hasta(lambda: self.filas()["Claude Code"] == "Listo"))
        self.assertIn("Claude Code está listo.", self.progreso("claude"))
        self.assertNotIn("claude", b.equipo_sesion)

    def test_sin_terminal_ensena_el_comando_para_copiar(self):
        from tareas import instalar_agentes
        b = self.board
        opencode = self.bin / "opencode"
        opencode.write_text("#!/bin/sh\n", encoding="utf-8")
        opencode.chmod(0o755)
        b.revisar_equipo()
        with mock.patch.object(instalar_agentes, "terminal", return_value=None):
            b.equipo_sesion["opencode"].emit("clicked")
        self.assertIn("escribe: opencode auth login", self.progreso("opencode"))

    def test_el_sondeo_pregunta_al_cli_por_el_llavero_en_un_hilo(self):
        """Codex con la sesión en el llavero: sin archivo, `codex login status` dice que sí."""
        import threading
        from enrutador import modelos_vivos
        modelos_vivos.olvidar_estados()
        self.addCleanup(modelos_vivos.olvidar_estados)
        codex = self.bin / "codex"
        codex.write_text("#!/bin/sh\necho 'Logged in using ChatGPT'\n", encoding="utf-8")
        codex.chmod(0o755)
        b = self.board
        b.revisar_equipo()                                  # al pintar no se pregunta
        self.assertEqual(self.filas()["Codex"], "Falta iniciar sesión")
        hilos = []
        real = threading.Thread
        with mock.patch("tareas.app.equipo.threading.Thread",
                        side_effect=lambda *a, **k: hilos.append(1) or real(*a, **k)):
            b.sondear_equipo()
        self.assertEqual(hilos, [1])
        self.assertTrue(girar_hasta(lambda: self.filas()["Codex"] == "Listo"))

    def test_antigravity_instalado_dice_instalado_y_se_abre(self):
        from tareas import instalar_agentes
        b = self.board
        agy = self.bin / "agy"
        agy.write_text("#!/bin/sh\n", encoding="utf-8")
        agy.chmod(0o755)
        b.revisar_equipo()
        self.assertEqual(self.filas()["Antigravity CLI"], "Instalado")
        with mock.patch.object(instalar_agentes, "terminal", return_value=["mi-terminal"]), \
                mock.patch("enrutador.motores.terminal.abrir") as abrir:
            b.equipo_sesion["antigravity"].emit("clicked")
        abrir.assert_called_once_with(["mi-terminal", str(agy)])
        self.assertIn("entra con tu cuenta", self.progreso("antigravity"))

    def test_el_sondeo_se_apaga_al_salir_de_la_pantalla(self):
        b = self.board
        self.assertTrue(b.equipo_sondeo)
        self.assertTrue(b.sondear_equipo())
        b.ver_pestana(pestana_inicio.INICIO)
        self.assertFalse(b.sondear_equipo())
        self.assertEqual(b.equipo_sondeo, 0)

    def test_el_tablero_sin_proyectos_manda_al_inicio(self):
        b = self.board
        b.ver_pestana(pestana_inicio.TABLERO)
        self.assertEqual(b.pestana_actual(), pestana_inicio.TABLERO)
        self.assertIn("Todavía no hay proyectos", textos(b.pestanas.get_child_by_name("tablero")))


class FuenteRota(PestanaInicio):
    con_vault = False

    def entorno_extra(self, raiz):
        return {"COTEJO_REPOS": str(raiz / "no-existe")}

    def test_una_fuente_rota_sigue_abriendo_en_el_tablero(self):
        self.assertIsNotNone(self.board.fuente.problema)
        self.assertEqual(self.board.pestana_actual(), pestana_inicio.TABLERO)


class UnRepoQueFalta(PestanaInicio):
    """Un repo de la lista que ya no existe no tumba el Inicio: sale el bueno y el aviso en llano."""
    con_vault = False

    def entorno_extra(self, raiz):
        bueno = raiz / "bueno"
        (bueno / ".git").mkdir(parents=True)
        (bueno / ".cotejo").mkdir()
        (bueno / ".cotejo" / "tareas.md").write_text("# Tareas\n\n- [ ] Una ^b1\n", encoding="utf-8")
        self.perdido = raiz / "perdido"
        return {"COTEJO_REPOS": os.pathsep.join([str(self.perdido), str(bueno)])}

    def test_inicio_enseña_el_proyecto_y_el_aviso_con_como_arreglarlo(self):
        b = self.board
        self.assertIsNone(b.fuente.problema)
        self.assertEqual(b.pestana_actual(), pestana_inicio.INICIO)
        todo = textos(b.pestanas.get_child_by_name(pestana_inicio.INICIO))
        # Con una tarea sin terminar no se dice «todo al día» (v1.3.1).
        self.assertIn("Tienes 1 proyecto y 1 tarea por hacer", todo)
        self.assertNotIn("todo al día", todo)
        self.assertNotIn("Todavía no tienes proyectos", todo)
        self.assertTrue(b.inicio_aviso.get_visible())
        self.assertIn("1 repo de tu lista ya no existe", " ".join(todo))
        detalle = b.inicio_aviso_detalle.get_label()
        self.assertIn(str(self.perdido), detalle)
        self.assertIn("quítalo", detalle)


if __name__ == "__main__":
    unittest.main()
