"""El candado del maestro (v1.3.1, cotejo-va7lgn): puede todo menos aprobar, y eso lo hace cumplir
Cotejo, no el prompt.

De punta a punta con el cliente falso (`cliente_falso.py`, `FALSO_COMANDOS`) haciendo lo que
haría un maestro con shell que se salta la regla: poner una `[x]` a mano en la nota, aceptar una
decisión cambiando su archivo, meter la rama de una tarea en `main`. Al cerrar el turno la tarea
sigue sin aprobar, la decisión vuelve a propuesta, el merge se avisa sin deshacer, y la respuesta
que ve la persona lo dice. Un turno que no toca nada no lleva aviso, y lo que aprueba la persona
en el board durante el turno no se deshace.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador, proyecto

from enrutador import candado, conversacion, verbos
from enrutador.motores import terminal
from tareas import almacen, preparacion

FALSO = str(Path(__file__).with_name("cliente_falso.py"))


def _reemplazar(ruta, viejo, nuevo):
    """El argv de un «sed» en Python: lo que correría un maestro con shell."""
    codigo = ("import sys, pathlib; p = pathlib.Path(sys.argv[1]); "
              "p.write_text(p.read_text(encoding='utf-8').replace(sys.argv[2], sys.argv[3]), "
              "encoding='utf-8')")
    return [sys.executable, "-c", codigo, str(ruta), viejo, nuevo]


def _git(carpeta, *args):
    return subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@t", "-C",
                           str(carpeta), *args], check=True, capture_output=True, text=True)


class Candado(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.estado = Path(temporal.name) / "estado"
        self.repo = Path(temporal.name) / "uno"
        self.repo.mkdir()
        for parche in (mock.patch.dict(os.environ, {"COTEJO_ESTADO": str(self.estado)}),
                       mock.patch.object(preparacion, "CARPETA",
                                         self.estado / "preparaciones"),
                       mock.patch.object(terminal, "abrir", mock.Mock(side_effect=AssertionError)),
                       mock.patch("enrutador.clientes.shutil.which",
                                  return_value="/usr/bin/x"),
                       mock.patch("enrutador.modelos_vivos.sesion", return_value=True)):
            parche.start()
            self.addCleanup(parche.stop)
        self.escribir_config({
            "proyectos": {"Uno": str(self.repo)},
            "motores": {"headless": {"comando": [sys.executable, FALSO], "aislar": False}}})
        self.nota = self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo #agente/sonnet #por-validar ^cotejo-asig",
            "- [ ] Rediseñar la capa Fuente #medio ^cotejo-prop",
            "- [x] Lo que ya estaba hecho ^cotejo-hech",
        ))
        self.alm = almacen.Almacen(self.repo)
        self.alm.base.mkdir()
        self.vieja = self.alm.crear("decision", "La regla de antes", "Así era.")
        self.vieja = self.alm.poner_estado(self.vieja.id, self.vieja.version, "aceptada")
        self.nueva = self.alm.crear("decision", "La regla nueva", "Así será.",
                                    reemplaza=self.vieja.id)

    def hablar(self, comandos=(), respuesta="Hecho."):
        with mock.patch.dict(os.environ, {"FALSO_COMANDOS": json.dumps(list(comandos)),
                                          "FALSO_RESPUESTA": respuesta}):
            return self.correr("maestro", "--proyecto", "Uno", "--pedido", "apruébalo todo",
                               "--cliente", "claude")

    def aceptar_a_mano(self):
        """Lo que haría `decision.aceptar` sin pasar por él: los dos archivos, a mano."""
        return [_reemplazar(self.alm.base / self.nueva.ruta, "estado: propuesta",
                            "estado: aceptada\naceptada_el: 2026-11-06"),
                _reemplazar(self.alm.base / self.vieja.ruta, "estado: aceptada",
                            f"estado: reemplazada\nreemplazada_por: {self.nueva.id}")]

    def tarea(self, ident):
        _, tareas = self.tareas_de("Uno")
        return next(t for t in tareas if t.id == ident)

    # --- de punta a punta ---------------------------------------------------------------------

    def test_lo_que_aprueba_el_maestro_se_deshace_y_se_dice(self):
        codigo, datos = self.hablar([
            _reemplazar(self.nota, "- [ ] Arreglar el parseo #agente/sonnet #por-validar",
                        "- [x] Arreglar el parseo #agente/sonnet"),
            *self.aceptar_a_mano()], respuesta="Listo: la di por buena y acepté la decisión.")
        self.assertEqual(codigo, verbos.OK, datos)
        # La tarea vuelve a donde estaba: Para comprobar, sin [x].
        tarea = self.tarea("cotejo-asig")
        self.assertFalse(tarea.hecha)
        self.assertEqual(tarea.estado, "por-validar")
        self.assertIn("- [ ] Arreglar el parseo", self.leer_nota("Uno.md"))
        # Lo que ya estaba hecho antes del turno no se toca.
        self.assertTrue(self.tarea("cotejo-hech").hecha)
        # La decisión vuelve a propuesta, sin fecha de aceptación, y la vieja sigue aceptada.
        nueva, vieja = self.alm.leer(self.nueva.id), self.alm.leer(self.vieja.id)
        self.assertEqual(nueva.estado, "propuesta")
        self.assertNotIn("aceptada_el", nueva.datos)
        self.assertEqual(vieja.estado, "aceptada")
        self.assertNotIn("reemplazada_por", vieja.datos)
        # La persona lo ve en la respuesta del maestro.
        self.assertTrue(datos["respuesta"].startswith("Listo: la di por buena"))
        self.assertIn("Intenté dar por hecha «Arreglar el parseo» (cotejo-asig); Cotejo lo "
                      "deshizo: aprobar es tuyo, en el board.", datos["respuesta"])
        self.assertIn(f"Intenté aceptar {self.nueva.id}", datos["respuesta"])
        self.assertEqual(conversacion.leer("Uno")["turnos"][-1]["texto"], datos["respuesta"])
        # Y en la bitácora de Cotejo, por su API.
        candados = [o for o in self.operaciones() if o["operacion"] == candado.DESHACER]
        self.assertEqual({o.get("id") or o.get("entrada") for o in candados},
                         {"cotejo-asig", self.nueva.id})

    def test_un_turno_que_no_toca_nada_no_lleva_aviso(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.hablar(respuesta="Faltan dos tareas.")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertEqual(datos["respuesta"], "Faltan dos tareas.")
        self.assertNotIn("candado", conversacion.leer("Uno")["turnos"][-1])
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertNotIn(candado.DESHACER, [o["operacion"] for o in self.operaciones()])

    def test_por_integrar_tambien_es_aprobar(self):
        _, datos = self.hablar([_reemplazar(self.nota, "#por-validar", "#por-integrar")])
        self.assertEqual(self.tarea("cotejo-asig").estado, "por-validar")
        self.assertIn("cotejo-asig", datos["respuesta"])

    def test_el_merge_a_main_se_avisa_sin_deshacer_git(self):
        _git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("a\n", encoding="utf-8")
        _git(self.repo, "add", "a.txt")
        _git(self.repo, "commit", "-q", "-m", "inicio")
        _git(self.repo, "checkout", "-q", "-b", "cotejo/cotejo-asig")
        (self.repo / "b.txt").write_text("b\n", encoding="utf-8")
        _git(self.repo, "add", "b.txt")
        _git(self.repo, "commit", "-q", "-m", "el arreglo")
        _git(self.repo, "checkout", "-q", "main")
        merge = ["git", "-c", "user.name=M", "-c", "user.email=m@m", "-C", str(self.repo),
                 "merge", "-q", "--no-ff", "--no-edit", "cotejo/cotejo-asig"]
        _, datos = self.hablar([merge])
        self.assertIn("Metí la rama cotejo/cotejo-asig en main", datos["respuesta"])
        # Git queda como lo dejó: el merge sigue ahí.
        self.assertTrue((self.repo / "b.txt").exists())
        self.assertEqual(_git(self.repo, "log", "-1", "--format=%s").stdout.strip(),
                         "Merge branch 'cotejo/cotejo-asig'")

    # --- sin lanzar nada ------------------------------------------------------------------------

    def test_lo_que_aprueba_la_persona_durante_el_turno_se_queda(self):
        foto = candado.foto("Uno", str(self.repo))
        tarea = self.tarea("cotejo-asig")
        candado.lo_aprueba_la_persona(tarea.id)    # el board, mientras el maestro contesta
        self.fuente.marcar(tarea, hecha=True)
        self.assertEqual(candado.revisar(foto), "")
        self.assertTrue(self.tarea("cotejo-asig").hecha)

    def test_una_tarea_creada_ya_hecha_tambien_se_deshace(self):
        foto = candado.foto("Uno", str(self.repo))
        with open(self.nota, "a", encoding="utf-8") as archivo:
            archivo.write("- [x] Una que nació aprobada ^cotejo-nuev\n")
        aviso = candado.revisar(foto)
        self.assertIn("cotejo-nuev", aviso)
        self.assertFalse(self.tarea("cotejo-nuev").hecha)

    def test_sin_foto_no_hay_nada_que_revisar(self):
        self.assertEqual(candado.revisar(None), "")
        self.assertEqual(candado.revisar({}), "")

    def test_parar_el_turno_tambien_pasa_por_el_candado(self):
        foto = candado.foto("Uno", str(self.repo))
        conversacion._guardar({"proyecto": "Uno", "turnos": [{"quien": "persona", "texto": "x"}],
                               "en_curso": {"pid": 999999999, "programa": "claude",
                                            "cliente": "claude", "foto": foto,
                                            "out": str(self.estado / "nada.out")}})
        self.fuente.marcar(self.tarea("cotejo-prop"), hecha=True)
        # El proceso ya no está: `leer` cierra el turno, y el candado va con él.
        turno = conversacion.leer("Uno")["turnos"][-1]
        self.assertIn("cotejo-prop", turno["texto"])
        self.assertFalse(self.tarea("cotejo-prop").hecha)


class DeshacerEstado(PruebaDeEnrutador):
    """`Almacen.deshacer_estado`: la única vuelta atrás, solo de lo que hace aceptar."""

    def setUp(self):
        super().setUp()
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.alm = almacen.Almacen(temporal.name)
        self.alm.base.mkdir()

    def test_solo_deshace_aceptar(self):
        entrada = self.alm.crear("decision", "Una", "Texto.")
        with self.assertRaises(almacen.NoSeEdita):     # propuesta → propuesta no es deshacer
            self.alm.deshacer_estado(entrada.id, entrada.version, "propuesta")
        rechazada = self.alm.poner_estado(entrada.id, entrada.version, "rechazada")
        with self.assertRaises(almacen.NoSeEdita):
            self.alm.deshacer_estado(rechazada.id, rechazada.version, "propuesta")
        problema = self.alm.crear("problema", "Un fallo", "Pasa.")
        with self.assertRaises(almacen.NoSeEdita):
            self.alm.deshacer_estado(problema.id, problema.version, "abierto")

    def test_verifica_la_version(self):
        entrada = self.alm.crear("decision", "Una", "Texto.")
        aceptada = self.alm.poner_estado(entrada.id, entrada.version, "aceptada",
                                         campos={"aceptada_el": "2026-11-06"})
        with self.assertRaises(almacen.EntradaCambiada):
            self.alm.deshacer_estado(aceptada.id, entrada.version, "propuesta")
        vuelta = self.alm.deshacer_estado(aceptada.id, aceptada.version, "propuesta",
                                          quitar=("aceptada_el",))
        self.assertEqual(vuelta.estado, "propuesta")
        self.assertNotIn("aceptada_el", vuelta.datos)
        self.assertEqual(vuelta.cuerpo, aceptada.cuerpo)


if __name__ == "__main__":
    import unittest
    unittest.main()
