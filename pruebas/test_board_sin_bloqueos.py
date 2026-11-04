"""El board no se traba mientras lanza y mientras un agente trabaja (cotejo-72a7di).

En Windows, soltar una carta en Haciendo paraba el bucle de GTK ~10 s («Cotejo no responde»):
el despacho (`cotejo` para tomarla, varios `git` para el worktree, el cliente) corría en el
hilo principal. Ahora corre en el hilo de despachos (`tareas/app/segundo_plano.py`). Aquí, con
GTK de verdad y un repo con `.cotejo/tareas.md` como fuente:

- con `git` lento a propósito (cada llamada tarda 0,3 s), la carta se ve en Haciendo al soltarla,
  el bucle no pasa nunca más de 200 ms sin latir y ningún `git` corre en el hilo principal;
- con un agente falso que escribe en `.cotejo/` cada medio segundo (y el board refrescando por
  cada escritura), el bucle tampoco pasa de 200 ms;
- dos sueltas seguidas de la misma carta lanzan un solo agente, y un fallo del despacho llega a
  la persona como aviso y la carta vuelve a Pendiente.

Sin GTK, sin pantalla o sin git, se salta. La app usa el id `io.github.cotejoapp.CotejoPrueba…`
de `test_pestana_inicio`: no abre el board de la persona.
"""

import json
import os
import shutil
import sys
import threading
import time
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

import test_pestana_inicio as base
from test_despacho_board import FALSO, FOTO_CON_HUECO, git

if base.HAY_GTK:
    from gi.repository import GLib, Gtk
    from enrutador import bitacora as despachos, capacidad, despacho_board
    from tareas import bitacora, estado, lanzados, preparacion, worktrees
    from tareas.app import segundo_plano
    from tareas.app.piezas import TareaArrastrada

HAY_GIT = shutil.which("git") is not None
TOPE_MS = 200
GIT_LENTO_S = 0.3
TAREAS = ("# Faro\n\n"
          "- [ ] Arreglar el parseo de los tags #agente/sonnet ^cotejo-con\n"
          "- [ ] Firmar el contrato con el abogado #agente/persona ^cotejo-hum\n")


class Latido:
    """Cada 10 ms el bucle de GLib apunta la hora; `peor_ms` es el hueco más largo entre dos."""

    def __init__(self):
        self.ultimo = None
        self.peor_ms = 0.0
        self.fuente = GLib.timeout_add(10, self._latir)

    def _latir(self):
        ahora = time.monotonic()
        if self.ultimo is not None:
            self.peor_ms = max(self.peor_ms, (ahora - self.ultimo) * 1000)
        self.ultimo = ahora
        return GLib.SOURCE_CONTINUE

    def empezar(self):
        self.ultimo, self.peor_ms = time.monotonic(), 0.0

    def parar(self):
        GLib.source_remove(self.fuente)


@unittest.skipUnless(base.HAY_GTK and HAY_GIT, "sin GTK, sin pantalla o sin git")
class BoardSinBloqueos(base.PestanaInicio):
    con_vault = False

    def entorno_extra(self, raiz):
        self.repo = raiz / "Faro"
        (self.repo / ".cotejo").mkdir(parents=True)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "LEEME").write_text("hola\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        # Después del commit: el worktree no la lleva, como un `.cotejo` sin versionar.
        self.tareas = self.repo / ".cotejo" / "tareas.md"
        self.tareas.write_text(TAREAS, encoding="utf-8")
        self.escrito = self.repo / ".cotejo" / "agente-falso.log"
        (raiz / "config.json").write_text(json.dumps({"enrutador": {
            "proyectos": {"Faro": str(self.repo)},
            "motores": {"headless": {"comando": [sys.executable, FALSO], "aislar": False}}}}),
            encoding="utf-8")
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
        self.addCleanup(despacho_board.esperar_vigilantes)
        self.addCleanup(lambda: [despacho_board.detener(i) for i in lanzados.todos()])
        self.addCleanup(self.esperar, lambda: segundo_plano.en_marcha() == 0, 15000)
        return {"COTEJO_REPOS": str(self.repo), "COTEJO_MOTOR": "agente",
                "FALSO_ESPERA": "30", "FALSO_ESCRIBIR": str(self.escrito),
                "FALSO_ESCRIBIR_CADA": "0.5"}

    def setUp(self):
        super().setUp()
        self.board.ver_pestana("tablero")
        self.avisos = []
        parche = mock.patch.object(type(self.board), "aviso",
                                   lambda _b, t, *a, **k: self.avisos.append(t))
        parche.start()
        self.addCleanup(parche.stop)
        self.latido = Latido()
        self.addCleanup(self.latido.parar)

    # --- ayudas -----------------------------------------------------------------------------

    def fila(self, palabra, columna):
        lista = self.board.columnas[columna][0]
        for fila in self.board.cartas(lista):
            if fila.tarea is not None and palabra in fila.tarea.texto:
                return fila
        return None

    def soltar(self, palabra):
        fila = self.fila(palabra, "pendiente")
        self.assertIsNotNone(fila, f"no hay carta «{palabra}» en Pendiente")
        return self.board.al_soltar(None, TareaArrastrada(fila.proyecto, fila.tarea), 0, 0,
                                    "en-curso", Gtk.Box())

    def esperar(self, condicion, ms=15000):
        return base.girar_hasta(condicion, ms / 1000)

    def linea(self, marca):
        return next(l for l in self.tareas.read_text(encoding="utf-8").splitlines() if marca in l)

    # --- las pruebas ------------------------------------------------------------------------

    def test_con_git_lento_soltar_no_bloquea_y_git_no_corre_en_el_hilo_principal(self):
        original = worktrees._git
        hilos = []

        def git_lento(*args, **kwargs):
            hilos.append(threading.current_thread() is threading.main_thread())
            time.sleep(GIT_LENTO_S)
            return original(*args, **kwargs)

        with mock.patch.object(worktrees, "_git", git_lento):
            base.girar(100)
            self.latido.empezar()
            antes = time.monotonic()
            self.assertTrue(self.soltar("parseo"))
            soltar_ms = (time.monotonic() - antes) * 1000
            # Al instante: ya se ve en Haciendo, con «Lanzando…», aunque la nota no lo diga aún.
            carta = self.fila("parseo", "en-curso")
            self.assertIsNotNone(carta)
            self.assertIn("Lanzando…", base.textos(carta))
            self.assertIsNone(self.fila("parseo", "pendiente"))
            self.assertTrue(self.esperar(lambda: segundo_plano.en_marcha() == 0))
            base.girar(300)
            peor = self.latido.peor_ms
        self.assertLess(soltar_ms, TOPE_MS)
        self.assertGreaterEqual(len(hilos), 3, "el despacho no pasó por git")
        self.assertFalse(any(hilos), "algún git corrió en el hilo principal")
        # Con lo que tardó git (≥ 3 × 0,3 s) el bucle se habría parado ≥ 900 ms; no pasa de 200.
        self.assertLess(peor, TOPE_MS, f"el bucle se paró {peor:.0f} ms")
        registro = lanzados.leer("cotejo-con")
        self.assertIsInstance(registro["pid"], int)
        self.assertIn("#en-curso", self.linea("^cotejo-con"))
        self.assertIsNotNone(self.fila("parseo", "en-curso"))
        self.assertNotIn("Lanzando…", base.textos(self.fila("parseo", "en-curso")))
        self.assertTrue(any("sonnet empezó" in a for a in self.avisos), self.avisos)

    def test_con_un_agente_escribiendo_en_cotejo_el_bucle_no_se_bloquea(self):
        self.assertTrue(self.soltar("parseo"))
        self.assertTrue(self.esperar(lambda: segundo_plano.en_marcha() == 0))
        self.assertTrue(self.esperar(self.escrito.exists))
        refrescos = []
        original = self.app.refrescar

        def contar():
            refrescos.append(time.monotonic())
            return original()

        with mock.patch.object(self.app, "refrescar", contar):
            self.latido.empezar()
            base.girar(3000)
            peor = self.latido.peor_ms
        escritas = len(self.escrito.read_text(encoding="utf-8").splitlines())
        self.assertGreaterEqual(escritas, 4, "el agente falso no escribió en .cotejo")
        self.assertGreaterEqual(len(refrescos), 2, "el board no refrescó por lo que escribió")
        self.assertLess(peor, TOPE_MS, f"el bucle se paró {peor:.0f} ms")

    def test_dos_sueltas_seguidas_lanzan_un_solo_agente(self):
        self.assertTrue(self.soltar("parseo"))
        # La segunda, mientras la primera sigue en marcha: la carta ya está en Haciendo y
        # moverla otra vez solo dice que espere.
        carta = self.fila("parseo", "en-curso")
        self.board.mover(carta.proyecto, carta.tarea, "en-curso")
        self.board.lanzar_al_mover(carta.proyecto, carta.tarea)
        self.assertTrue(self.esperar(lambda: segundo_plano.en_marcha() == 0))
        base.girar(200)
        self.assertTrue(any("Todavía la estoy lanzando" in a for a in self.avisos), self.avisos)
        self.assertEqual(sum("empezó a trabajar" in a for a in self.avisos), 1, self.avisos)
        self.assertEqual(lanzados.leer("cotejo-con")["lanzamientos"], 1)

    def test_si_el_despacho_falla_se_dice_y_la_carta_vuelve_a_pendiente(self):
        with mock.patch.object(despacho_board, "lanzar",
                               side_effect=despacho_board.NoSePuede("el repo no tiene commits")):
            self.assertTrue(self.soltar("parseo"))
            self.assertTrue(self.esperar(lambda: segundo_plano.en_marcha() == 0))
            base.girar(100)
        self.assertTrue(any("No la lancé: el repo no tiene commits" in a for a in self.avisos),
                        self.avisos)
        self.assertIsNotNone(self.fila("parseo", "pendiente"))
        self.assertIsNone(self.fila("parseo", "en-curso"))
        self.assertNotIn("#en-curso", self.linea("^cotejo-con"))

    def test_una_tarea_de_persona_se_mueve_como_siempre(self):
        self.assertTrue(self.soltar("contrato"))
        self.assertTrue(self.esperar(lambda: segundo_plano.en_marcha() == 0))
        base.girar(100)
        self.assertIn("#en-curso", self.linea("^cotejo-hum"))
        self.assertIsNone(lanzados.leer("cotejo-hum"))
        self.assertIsNotNone(self.fila("contrato", "en-curso"))


class UnaFotoDeLosClientes(unittest.TestCase):
    """En Windows cada `shutil.which` recorre el PATH con PATHEXT; un refresco del board
    preguntaba ~11 veces por cada cliente. Dentro de `una_foto` se mira una vez por ejecutable,
    y fuera de ella se mira siempre (la CLI y las pruebas que cambian el PATH no notan nada)."""

    def test_dentro_de_la_foto_cada_ejecutable_se_busca_una_vez(self):
        from enrutador import clientes
        with mock.patch("enrutador.clientes.shutil.which", return_value="/x") as which:
            with clientes.una_foto():
                for _ in range(5):
                    clientes.instalados()
                with clientes.una_foto():          # anidada: la misma foto
                    clientes.instalados()
            self.assertEqual(which.call_count, len(clientes.CLIENTES))
            clientes.instalados()
            self.assertEqual(which.call_count, 2 * len(clientes.CLIENTES))

    def test_la_foto_es_del_hilo_que_la_abre(self):
        from enrutador import clientes
        visto = []
        with mock.patch("enrutador.clientes.shutil.which", return_value=None) as which:
            with clientes.una_foto():
                clientes.instalados()
                hilo = threading.Thread(target=lambda: visto.append(clientes.instalados()))
                hilo.start()
                hilo.join()
                clientes.instalados()
        self.assertEqual(visto, [[]])
        self.assertEqual(which.call_count, 2 * len(clientes.CLIENTES))


if __name__ == "__main__":
    unittest.main()
