"""Mover a Haciendo lanza el agente, en el board de verdad (v1.3.0, cotejo-7xsjb8).

De punta a punta con GTK y pantalla (sin ellas se salta), sobre un vault de mentira con un repo
de verdad para el worktree y el cliente falso (`cliente_falso.py`) en lugar de un agente: nunca
se lanza uno de verdad, y la máquina no se mide (foto de `capacidad` inventada). Arrastrar una
tarea con modelo la lanza y el registro guarda pid y log; sin modelo se pregunta y, al elegir, se
asigna y se lanza; n0 no se lanza; sin hueco no se lanza y queda en espera con el motivo; y la
ficha de una tarea en Haciendo enseña las líneas nuevas del log al llegar, con un temporizador
que existe solo mientras la ficha se ve. La lógica sin GTK está en `test_despacho_board.py`.
"""

import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import test_pestana_inicio as base
from test_despacho_board import FALSO, FOTO_CON_HUECO, git
from test_despacho_board import esperar as esperar_hilo

if base.HAY_GTK:
    from gi.repository import Gtk
    from enrutador import bitacora as despachos, capacidad, despacho_board
    from tareas import bitacora, estado, lanzados, preparacion, retomar, worktrees
    from tareas.app.piezas import TareaArrastrada

HAY_GIT = shutil.which("git") is not None

TAREAS = ("- [ ] Arreglar el parseo de los tags #agente/sonnet ^cotejo-con\n"
          "- [ ] Mejorar el mensaje de error del parser ^cotejo-sin\n"
          "- [ ] Firmar el contrato con el abogado #agente/persona ^cotejo-hum\n")


@unittest.skipUnless(base.HAY_GTK and HAY_GIT, "sin GTK, sin pantalla o sin git")
class LanzarDesdeElBoard(base.PestanaInicio):
    def entorno_extra(self, raiz):
        nota = raiz / "vault" / "01-Proyectos" / "Faro.md"
        nota.write_text(f"---\ntipo: proyecto\n---\n\n# Faro\n\n{TAREAS}", encoding="utf-8")
        self.nota = nota
        self.repo = raiz / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "LEEME").write_text("hola\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.config = raiz / "config.json"
        self.configurar()
        self.argv_falso = raiz / "argv.json"
        estado_dir = raiz / "estado"
        for objetivo, atributo, valor in (
                (bitacora, "ARCHIVO", estado_dir / "bitacora.jsonl"),
                (despachos, "ARCHIVO", estado_dir / "despachos.jsonl"),
                (estado, "ARCHIVO", estado_dir / "estado.json"),
                (worktrees, "REGISTRO", estado_dir / "worktrees"),
                (worktrees, "BASE", raiz / "wt"),
                (preparacion, "CARPETA", estado_dir / "preparaciones")):
            parche = mock.patch.object(objetivo, atributo, valor)
            parche.start()
            self.addCleanup(parche.stop)
        parche = mock.patch.object(capacidad, "leer", return_value=dict(FOTO_CON_HUECO))
        parche.start()
        self.addCleanup(parche.stop)
        # Ningún cliente falso se queda vivo al terminar la prueba.
        self.addCleanup(lambda: [despacho_board.detener(i) for i in lanzados.todos()])
        return {"FALSO_ARGV": str(self.argv_falso), "COTEJO_MOTOR": "agente"}

    def configurar(self, **extra):
        ajustes = {"proyectos": {"Faro": str(self.repo)},
                   "motores": {"headless": {"comando": [sys.executable, FALSO],
                                            "aislar": False}}}
        ajustes.update(extra)
        self.config.write_text(json.dumps({"enrutador": ajustes}), encoding="utf-8")

    # --- ayudas -----------------------------------------------------------------------------

    def fila(self, palabra, columna=None):
        for clave in ([columna] if columna else self.board.columnas):
            lista, _cuenta, _scroll = self.board.columnas[clave]
            for fila in self.board.cartas(lista):
                if palabra in fila.tarea.texto:
                    return fila
        raise AssertionError(f"no hay carta con «{palabra}»")

    def arrastrar(self, palabra, destino="en-curso"):
        """Lo que hace soltar la carta sobre la columna."""
        fila = self.fila(palabra, "pendiente")
        hecho = self.board.al_soltar(None, TareaArrastrada(fila.proyecto, fila.tarea), 0, 0,
                                     destino, Gtk.Box())
        self.assertTrue(hecho)
        base.girar(100)
        return fila

    def linea(self, marca):
        return next(l for l in self.nota.read_text(encoding="utf-8").splitlines() if marca in l)

    def esperar(self, condicion, ms=8000):
        limite = 0
        while not condicion() and limite < ms:
            base.girar(50)
            limite += 50
        return condicion()

    # --- las pruebas ------------------------------------------------------------------------

    def test_arrastrar_una_tarea_con_modelo_la_lanza_y_el_registro_guarda_pid_y_log(self):
        self.board.ver_pestana("tablero")
        avisos = []
        with mock.patch.object(type(self.board), "aviso", lambda _b, t: avisos.append(t)), \
                mock.patch.dict(os.environ, {"FALSO_ESPERA": "1"}):
            self.arrastrar("parseo")
            self.assertIn("#en-curso #agente/sonnet", self.linea("^cotejo-con"))
            registro = lanzados.leer("cotejo-con")
            self.assertIsInstance(registro["pid"], int)
            self.assertTrue(registro["log"])
            self.assertEqual(registro["modelo"], "sonnet")
            self.assertTrue(any("sonnet empezó" in a for a in avisos), avisos)
            # Cuando vuelve, se anota y el board avisa. El falso no entrega: vuelve a Pendiente
            # (cotejo-o253bs).
            self.assertTrue(self.esperar(
                lambda: ((lanzados.leer("cotejo-con") or {}).get("fin") or {}).get("como")
                == lanzados.FIN_SIN_ENTREGAR))
            self.assertTrue(self.esperar(lambda: any("terminó" in a for a in avisos)), avisos)
        self.assertTrue(Path(registro["log"]).read_text().strip())
        self.assertEqual(self.fila("parseo").tarea.columna, "pendiente")

    def test_sin_modelo_pregunta_con_la_propuesta_y_al_elegir_asigna_y_lanza(self):
        self.board.ver_pestana("tablero")
        self.arrastrar("mensaje de error")
        dialogo = self.board.pregunta_modelo
        self.assertIsNotNone(dialogo)
        propuesta = dialogo.modelos[0]
        self.assertIn(f"Propongo {propuesta} porque", dialogo.get_body())
        self.assertNotIn("persona", dialogo.modelos)
        # Nada se tomó ni se lanzó mientras pregunta.
        self.assertTrue(self.linea("^cotejo-sin").startswith("- [ ] Mejorar"))
        self.assertNotIn("#en-curso", self.linea("^cotejo-sin"))
        self.assertIsNone(lanzados.leer("cotejo-sin"))
        # Elige otro de la lista: se asigna (en la nota) y se lanza con ese.
        elegido = dialogo.modelos[1]
        dialogo.desplegable.set_selected(1)
        fila = self.fila("mensaje de error", "pendiente")
        dialogo.force_close()
        # Que siga trabajando mientras se mira: si vuelve sin entregar, vuelve a Pendiente.
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            self.board.al_responder_modelo(dialogo, "lanzar", fila.proyecto, fila.tarea)
        base.girar(100)
        self.assertIn(f"#en-curso #agente/{elegido}", self.linea("^cotejo-sin"))
        self.assertEqual(lanzados.leer("cotejo-sin")["modelo"], elegido)
        asignaciones = [json.loads(l) for l in bitacora.ARCHIVO.read_text().splitlines()
                        if '"asignar"' in l]
        self.assertEqual(asignaciones[-1]["a"], elegido)

    def test_la_hago_yo_la_asigna_a_la_persona_sin_lanzar(self):
        self.board.ver_pestana("tablero")
        self.arrastrar("mensaje de error")
        dialogo = self.board.pregunta_modelo
        fila = self.fila("mensaje de error", "pendiente")
        dialogo.force_close()
        self.board.al_responder_modelo(dialogo, "yo", fila.proyecto, fila.tarea)
        base.girar(100)
        self.assertIn("#en-curso", self.linea("^cotejo-sin"))
        self.assertIn("#agente/persona", self.linea("^cotejo-sin"))
        self.assertIsNone(lanzados.leer("cotejo-sin"))
        self.assertFalse(self.argv_falso.exists())

    def test_n0_no_se_lanza(self):
        self.board.ver_pestana("tablero")
        self.arrastrar("contrato")
        # Se mueve, como siempre que una persona toma la suya, pero sin agente.
        self.assertIn("#en-curso", self.linea("^cotejo-hum"))
        self.assertIsNone(lanzados.leer("cotejo-hum"))
        self.assertFalse(self.argv_falso.exists())
        self.assertIsNone(self.board.dialogo_detalle(
            self.fila("contrato").proyecto, self.fila("contrato").tarea).en_vivo)

    def test_sin_hueco_no_se_lanza_y_queda_en_espera_con_el_motivo(self):
        self.board.ver_pestana("tablero")
        self.configurar(capacidad={"mb_por_agente": 10 ** 9})
        self.arrastrar("parseo")
        # Sigue en Pendiente, sin tomar ni lanzar.
        self.assertTrue(self.linea("^cotejo-con").startswith("- [ ] Arreglar"))
        self.assertNotIn("#en-curso", self.linea("^cotejo-con"))
        self.assertFalse(self.argv_falso.exists())
        # Su carta lleva «En espera», con el motivo de tooltip; su ficha, el motivo entero.
        fila = self.fila("parseo", "pendiente")
        self.assertIn("En espera", base.textos(fila))
        motivo = lanzados.en_espera()["cotejo-con"]
        self.assertIn("memoria", motivo)
        ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
        self.assertIn("EN ESPERA", base.textos(ficha.get_child()))
        self.assertIn(motivo, base.textos(ficha.get_child()))

    def test_quitar_de_la_espera_borra_el_chip_y_volver_a_arrastrar_la_lanza_como_nueva(self):
        self.board.ver_pestana("tablero")
        with mock.patch.object(type(self.board), "aviso", lambda _b, _t: None):
            self.configurar(capacidad={"mb_por_agente": 10 ** 9})
            self.arrastrar("parseo")
            fila = self.fila("parseo", "pendiente")
            self.assertIn("En espera", base.textos(fila))
            antes = self.linea("^cotejo-con")
            # Desde el menú de la carta.
            self.board.al_quitar_de_espera(fila.proyecto, fila.tarea)
            base.girar(100)
            self.assertIsNone(lanzados.leer("cotejo-con"))
            self.assertEqual(lanzados.en_espera(), {})
            fila = self.fila("parseo", "pendiente")
            self.assertNotIn("En espera", base.textos(fila))
            ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
            self.assertNotIn("EN ESPERA", base.textos(ficha.get_child()))
            # La tarea y su modelo siguen igual en la fuente; nada se lanzó.
            self.assertEqual(self.linea("^cotejo-con"), antes)
            self.assertFalse(self.argv_falso.exists())
            # Desde la ficha: otra espera y el botón de la ficha.
            self.arrastrar("parseo")
            fila = self.fila("parseo", "pendiente")
            ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
            self.assertIn("Quitar de la espera", base.textos(ficha.get_child()))
            boton = self.buscar_boton(ficha.get_child(), "Quitar de la espera")
            boton.emit("clicked")
            base.girar(100)
            self.assertEqual(lanzados.en_espera(), {})
            self.assertNotIn("En espera", base.textos(self.fila("parseo", "pendiente")))
            # Con hueco otra vez, arrastrarla la lanza como nueva.
            self.configurar()
            with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
                self.arrastrar("parseo")
                self.assertTrue(self.esperar(self.argv_falso.exists))
                registro = lanzados.leer("cotejo-con")
                self.assertIsInstance(registro["pid"], int)
                self.assertNotEqual(registro["fase"], lanzados.EN_ESPERA)
                self.assertIn("#en-curso", self.linea("^cotejo-con"))

    def test_lanzar_de_todos_modos_desde_la_ficha_la_lanza_sin_mirar_la_capacidad(self):
        self.board.ver_pestana("tablero")
        with mock.patch.object(type(self.board), "aviso", lambda _b, _t: None):
            self.configurar(capacidad={"mb_por_agente": 10 ** 9})
            self.arrastrar("parseo")
            fila = self.fila("parseo", "pendiente")
            ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
            self.assertTrue(any("Cierra algo" in t for t in base.textos(ficha.get_child())))
            boton = self.buscar_boton(ficha.get_child(), "Lanzar de todos modos")
            self.assertIsNotNone(boton)
            with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
                boton.emit("clicked")
                self.assertTrue(self.esperar(self.argv_falso.exists))
            self.assertIn("#en-curso", self.linea("^cotejo-con"))
            self.assertEqual(lanzados.en_espera(), {})

    @staticmethod
    def buscar_boton(widget, texto):
        if isinstance(widget, Gtk.Button) and widget.get_label() == texto:
            return widget
        hijo = widget.get_first_child()
        while hijo is not None:
            hallado = LanzarDesdeElBoard.buscar_boton(hijo, texto)
            if hallado is not None:
                return hallado
            hijo = hijo.get_next_sibling()
        return None

    def test_la_ficha_en_haciendo_ve_el_log_en_vivo_con_reloj_solo_mientras_se_ve(self):
        self.board.ver_pestana("tablero")
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            self.arrastrar("parseo")
        registro = lanzados.leer("cotejo-con")
        self.assertTrue(self.esperar(lambda: "Voy a mirar" in Path(registro["log"]).read_text()))
        fila = self.fila("parseo", "en-curso")
        ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
        vivo = ficha.en_vivo
        self.assertIsNotNone(vivo)
        self.assertFalse(vivo.hay_reloj())          # todavía no se ve
        self.assertIn("sonnet está trabajando en ella", vivo.situacion.get_label())
        # La señal de vida (cotejo-21y2ah): visible, con cuánto lleva y el último movimiento.
        self.assertTrue(vivo.vida.get_visible())
        self.assertEqual(vivo.vida_titulo.get_label(), "Trabajando")
        self.assertIn("último movimiento hace", vivo.vida_detalle.get_label())
        self.assertFalse(vivo.vida_retomar.get_visible())
        # Qué está haciendo, de la última herramienta del log (el cliente falso usa Bash).
        self.assertEqual(vivo.vida_ayuda.get_label(), "Corriendo: git status")
        ficha.present(self.board)
        self.assertTrue(self.esperar(vivo.hay_reloj, 2000))
        self.assertIn("Voy a mirar el repo.", vivo.texto())
        self.assertIn("→ Bash: git status", vivo.texto())
        # Una línea nueva del agente aparece al llegar, sin cerrar ni abrir nada.
        with open(registro["log"], "a", encoding="utf-8") as log:
            log.write(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Ya corrí las pruebas."}]}}) + "\n")
        antes = vivo.refrescos
        self.assertTrue(self.esperar(lambda: "Ya corrí las pruebas." in vivo.texto(), 3000))
        self.assertGreater(vivo.refrescos, antes)
        # Cerrada la ficha, el temporizador deja de existir.
        ficha.force_close()
        self.assertTrue(self.esperar(lambda: not vivo.hay_reloj(), 2000))
        quieto = vivo.refrescos
        base.girar(1300)
        self.assertEqual(vivo.refrescos, quieto)

    def test_agente_cerrado_sin_entregar_ofrece_retomar_y_lanza_otro(self):
        """cotejo-21y2ah: si el proceso murió, la ficha lo dice como un hecho y «Retomar» la
        deja pausada y lanza un agente nuevo en el mismo worktree, sin arrastrar nada."""
        self.board.ver_pestana("tablero")
        with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            self.arrastrar("parseo")
            registro = lanzados.leer("cotejo-con")
            primero = registro["pid"]
            self.assertTrue(self.esperar(lambda: "git status" in Path(registro["log"]).read_text()))
            fila = self.fila("parseo", "en-curso")
            with mock.patch.object(lanzados, "_muerto", return_value=True):
                ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
                vivo = ficha.en_vivo
                self.assertEqual(vivo.vida_titulo.get_label(), "Se cerró sin entregar")
                self.assertTrue(vivo.vida_retomar.get_visible())
                self.argv_falso.unlink()
                vivo.vida_retomar.emit("clicked")
            base.girar(200)
            nuevo = lanzados.leer("cotejo-con")
            self.assertNotEqual(nuevo["pid"], primero)
            self.assertIn("#en-curso #agente/sonnet", self.linea("^cotejo-con"))
            self.assertEqual(nuevo["worktree"]["ruta"], registro["worktree"]["ruta"])
            self.assertTrue(self.esperar(lambda: self.argv_falso.exists()))
            self.assertTrue(esperar_hilo(lambda: not _vive(primero)), "el agente viejo sigue vivo")

    def test_devolver_a_pendiente_pausa_y_volver_a_haciendo_retoma(self):
        """cotejo-z7ma7r de punta a punta: pausar conserva worktree, rama y modelo; retomar
        lanza otro agente en el mismo worktree con la nota, y la ficha dice que retoma."""
        self.board.ver_pestana("tablero")
        avisos = []
        with mock.patch.object(type(self.board), "aviso", lambda _b, t: avisos.append(t)), \
                mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            self.arrastrar("parseo")
            registro = lanzados.leer("cotejo-con")
            primero = registro["pid"]
            self.assertTrue(self.esperar(lambda: "git status" in Path(registro["log"]).read_text()))
            ruta = Path(registro["worktree"]["ruta"])

            # Haciendo → Pendiente, a mano: se para el agente; worktree, rama y modelo siguen.
            fila = self.fila("parseo", "en-curso")
            self.board.mover(fila.proyecto, fila.tarea, "pendiente")
            base.girar(100)
            self.assertNotIn("#en-curso", self.linea("^cotejo-con"))
            self.assertIn("#agente/sonnet", self.linea("^cotejo-con"))
            self.assertEqual(lanzados.leer("cotejo-con")["fase"], lanzados.DETENIDO)
            self.assertTrue(esperar_hilo(lambda: not _vive(primero)), "el agente sigue vivo")
            self.assertTrue(ruta.is_dir())
            self.assertIsNotNone(worktrees.de_tarea("cotejo-con"))
            self.assertIn("cotejo/cotejo-con", git(self.repo, "branch", "--list"))
            self.assertTrue(any(a.startswith("Pausé a sonnet") for a in avisos), avisos)
            # Su ficha en Pendiente dice que está pausada.
            fila = self.fila("parseo", "pendiente")
            ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
            self.assertIsNotNone(ficha.pausada)
            self.assertIn("PAUSADA", base.textos(ficha.get_child()))
            self.assertIn("cotejo/cotejo-con", " ".join(base.textos(ficha.get_child())))

            # Lo que dejó: un commit y un archivo sin commitear.
            (ruta / "hecho.txt").write_text("listo\n")
            git(ruta, "add", "hecho.txt")
            git(ruta, "commit", "-q", "-m", "Primera mitad del arreglo")
            (ruta / "a-medias.txt").write_text("falta\n")
            self.argv_falso.unlink()

            # Pendiente → Haciendo: un agente nuevo en el mismo worktree, con la nota.
            self.arrastrar("parseo")
            self.assertIn("#en-curso #agente/sonnet", self.linea("^cotejo-con"))
            registro = lanzados.leer("cotejo-con")
            self.assertNotEqual(registro["pid"], primero)
            self.assertEqual(registro["worktree"]["ruta"], str(ruta))
            self.assertTrue(self.esperar(lambda: self.argv_falso.exists()
                                         and self.argv_falso.read_text().endswith("}")))
            lanzado = json.loads(self.argv_falso.read_text())
            self.assertEqual(Path(lanzado["cwd"]).resolve(), ruta.resolve())
            prompt = lanzado["argv"][-1]
            for dicho in ("cotejo entregar cotejo-con", retomar.TITULO,
                          "Primera mitad del arreglo", "?? a-medias.txt",
                          "> Voy a mirar el repo."):
                self.assertIn(dicho, prompt)

            # La ficha en Haciendo dice que es una reanudación.
            fila = self.fila("parseo", "en-curso")
            ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
            vivo = ficha.en_vivo
            self.assertIn("sonnet está retomándola", vivo.situacion.get_label())
            self.assertTrue(vivo.reanudacion.get_visible())
            self.assertIn("Es una reanudación (vez 2)", vivo.reanudacion.get_label())
            self.assertIn("1 commit y 1 cambio sin commitear", vivo.reanudacion.get_label())

    # --- el fin y el rechazo (cotejo-o253bs) --------------------------------------------------

    def fin_de(self, marca):
        return ((lanzados.leer(marca) or {}).get("fin") or {}).get("como")

    def entregada(self, avisos):
        """Arrastra «parseo» con un agente que entrega, y espera a verla en Para comprobar."""
        with mock.patch.dict(os.environ, {"FALSO_ENTREGAR": "cotejo-con"}):
            self.arrastrar("parseo")
        self.assertTrue(self.esperar(lambda: self.fin_de("cotejo-con") == lanzados.FIN_ENTREGO,
                                     30000), "el agente no entregó")
        self.assertTrue(self.esperar(lambda: any("entregó" in a for a in avisos)), avisos)
        self.app.refrescar()
        return self.fila("parseo", "por-validar")

    def test_el_que_entrega_queda_en_para_comprobar_con_sus_mensajes(self):
        self.board.ver_pestana("tablero")
        avisos = []
        with mock.patch.object(type(self.board), "aviso", lambda _b, t: avisos.append(t)):
            fila = self.entregada(avisos)
        self.assertIn("#por-validar", self.linea("^cotejo-con"))
        # Su revisión y su ficha guardan lo que dijo.
        revision = self.board.ver_revision(fila.proyecto, fila.tarea)
        self.assertIsNotNone(revision.en_vivo)
        self.assertIn("Entregué (código 0).", revision.en_vivo.texto())
        self.assertIn("entregó", revision.en_vivo.situacion.get_label())
        revision.force_close()
        ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
        self.assertIn("Voy a mirar el repo.", ficha.en_vivo.texto())

    def test_el_que_termina_sin_entregar_vuelve_a_pendiente_pausado_con_el_motivo(self):
        self.board.ver_pestana("tablero")
        avisos = []
        with mock.patch.object(type(self.board), "aviso", lambda _b, t: avisos.append(t)):
            self.arrastrar("parseo")
            self.assertTrue(self.esperar(
                lambda: self.fin_de("cotejo-con") == lanzados.FIN_SIN_ENTREGAR))
            self.assertTrue(self.esperar(lambda: any("terminó sin entregar" in a
                                                     for a in avisos)), avisos)
        fila = self.fila("parseo", "pendiente")
        self.assertIn("#agente/sonnet", self.linea("^cotejo-con"))
        ficha = self.board.dialogo_detalle(fila.proyecto, fila.tarea)
        dicho = " ".join(base.textos(ficha.get_child()))
        self.assertIn("PAUSADA", dicho)
        self.assertIn("el agente terminó sin entregar", dicho)
        self.assertIn("«Voy a mirar el repo.»", dicho)          # el motivo, con sus mensajes
        self.assertTrue(Path(lanzados.leer("cotejo-con")["worktree"]["ruta"]).is_dir())

    def test_el_que_murio_con_el_board_cerrado_se_recoge_al_refrescar(self):
        self.board.ver_pestana("tablero")
        procesos = []
        with mock.patch.object(despacho_board, "vigilar",
                               lambda proceso, *a, **k: procesos.append(proceso)), \
                mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
            self.arrastrar("parseo")
        procesos[0].kill()
        procesos[0].wait()
        self.app.refrescar()
        base.girar(100)
        self.assertEqual(self.fila("parseo").tarea.columna, "pendiente")
        self.assertEqual(self.fin_de("cotejo-con"), lanzados.FIN_SIN_ENTREGAR)

    def test_devolver_de_para_comprobar_a_haciendo_lanza_otro_con_lo_que_se_pidio(self):
        self.board.ver_pestana("tablero")
        avisos = []
        with mock.patch.object(type(self.board), "aviso", lambda _b, t: avisos.append(t)):
            fila = self.entregada(avisos)
            primero = lanzados.leer("cotejo-con")
            self.argv_falso.unlink()
            entrada = Gtk.Entry(text="Falta el caso del archivo vacío.")
            with mock.patch.dict(os.environ, {"FALSO_ESPERA": "30"}):
                self.board.al_responder_motivo(None, "devolver", entrada, fila.proyecto,
                                               fila.tarea, "en-curso")
            base.girar(100)
            self.assertTrue(any("la retoma con lo que pediste cambiar" in a for a in avisos),
                            avisos)
        self.assertIn("#en-curso", self.linea("^cotejo-con"))
        self.assertIn("#agente/sonnet", self.linea("^cotejo-con"))
        rechazo = [json.loads(l) for l in bitacora.ARCHIVO.read_text().splitlines()
                   if '"rechazar"' in l][-1]
        self.assertEqual(rechazo["motivo"], "Falta el caso del archivo vacío.")
        registro = lanzados.leer("cotejo-con")
        self.assertNotEqual(registro["pid"], primero["pid"])
        self.assertEqual(registro["worktree"]["ruta"], primero["worktree"]["ruta"])
        self.assertTrue(self.esperar(lambda: self.argv_falso.exists()
                                     and self.argv_falso.read_text().endswith("}")))
        lanzado = json.loads(self.argv_falso.read_text())
        self.assertEqual(Path(lanzado["cwd"]).resolve(),
                         Path(primero["worktree"]["ruta"]).resolve())
        prompt = lanzado["argv"][-1]
        for dicho in ("cotejo entregar cotejo-con", retomar.TITULO_RECHAZO,
                      "Falta el caso del archivo vacío.", "Resumen: Arreglé el parseo."):
            self.assertIn(dicho, prompt)
        # Su ficha en Haciendo dice que retoma tras el rechazo.
        fila = self.fila("parseo", "en-curso")
        vivo = self.board.dialogo_detalle(fila.proyecto, fila.tarea).en_vivo
        self.assertIn("Se la devolvieron desde Para comprobar", vivo.reanudacion.get_label())

    def test_devolver_lo_que_no_lanzo_el_board_retira_el_worktree_como_siempre(self):
        self.board.ver_pestana("tablero")
        self.arrastrar("contrato")                 # n0: se mueve sin lanzar
        fila = self.fila("contrato", "en-curso")
        self.assertFalse(self.board.es_pausable(fila.tarea))
        self.board.mover(fila.proyecto, fila.tarea, "pendiente")
        base.girar(100)
        self.assertIsNone(lanzados.leer("cotejo-hum"))
        ficha = self.board.dialogo_detalle(*(lambda f: (f.proyecto, f.tarea))(
            self.fila("contrato", "pendiente")))
        self.assertIsNone(ficha.pausada)


def _vive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


if __name__ == "__main__":
    unittest.main()
