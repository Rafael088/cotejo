"""Parar a un agente para también lo que él lanzó: el nieto muere (cotejo-qtegjk).

Antes un agente de npm en Windows era `cmd.exe /c opencode.cmd` → `opencode.exe`: el board
anotaba el pid del `cmd`, y parar solo ese dejaba vivo al `opencode.exe` que hacía el trabajo.
Aquí se lanza de verdad un hijo (como lanza el board a un agente: `start_new_session`, por
`subproceso`) que a su vez lanza un nieto, se para el hijo con `procesos.terminar` y se comprueba
que el nieto ya no está. En Linux lo hace el grupo de procesos; en Windows, el árbol recorrido
a mano por
`procesos._terminar_arbol_windows` (cotejo-hrnx1m; corre igual allí, con
`herramientas/probar_windows.sh --solo suite --patron test_parar_arbol.py`).
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import procesos, subproceso
from tareas import lanzados

# El hijo: lanza al nieto, deja su pid en un archivo y se queda esperando.
HIJO = """
import subprocess, sys, time
nieto = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
with open(sys.argv[1] + ".tmp", "w") as f:
    f.write(str(nieto.pid))
import os
os.replace(sys.argv[1] + ".tmp", sys.argv[1])
time.sleep(120)
"""


def muerto(pid):
    """Ya no está, o es un zombi esperando que lo recojan (en Linux, tras morir su padre)."""
    if not procesos.vivo(pid):
        return True
    try:
        estado = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return estado in ("Z", "X")


def esperar(condicion, tope=15):
    limite = time.monotonic() + tope
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.05)
    return condicion()


class PararElArbol(unittest.TestCase):
    def test_parar_al_agente_mata_tambien_a_su_nieto(self):
        carpeta = Path(tempfile.mkdtemp())
        archivo = carpeta / "nieto.pid"
        hijo = subproceso.Popen([sys.executable, "-c", HIJO, str(archivo)],
                                stdin=subproceso.DEVNULL, stdout=subproceso.DEVNULL,
                                stderr=subproceso.DEVNULL, start_new_session=True)
        nieto = None

        def limpiar():
            for pid in (hijo.pid, nieto):
                if pid and not muerto(pid):
                    try:
                        os.kill(pid, 9)
                    except OSError:
                        pass
            try:
                hijo.wait(5)
            except subproceso.TimeoutExpired:
                pass
            for f in carpeta.iterdir():
                f.unlink()
            carpeta.rmdir()

        self.addCleanup(limpiar)
        self.assertTrue(esperar(archivo.exists), "el hijo no lanzó al nieto")
        nieto = int(archivo.read_text())
        self.assertTrue(procesos.vivo(nieto))

        self.assertTrue(procesos.terminar(hijo.pid, sys.executable))
        hijo.wait(15)
        self.assertTrue(esperar(lambda: muerto(nieto)), "el nieto siguió vivo")

    def test_un_pid_que_ya_no_esta_no_se_para(self):
        hijo = subproceso.Popen([sys.executable, "-c", "pass"])
        hijo.wait(15)
        self.assertFalse(procesos.terminar(hijo.pid, sys.executable))


class SinTemporalesSobrantes(unittest.TestCase):
    """`estado/lanzados` se quedaba con un `.json.tmp` a medias al cerrar el board en Windows
    con un agente trabajando: el reemplazo fallaba (el destino estaba abierto) o el proceso
    murió entre escribir y reemplazar."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        parche = mock.patch.dict(os.environ, {"COTEJO_ESTADO": temporal.name})
        parche.start()
        self.addCleanup(parche.stop)
        self.carpeta = lanzados.carpeta()

    def sobrantes(self):
        return sorted(p.name for p in self.carpeta.iterdir() if p.name.endswith(".tmp"))

    def test_guardar_no_deja_temporales(self):
        for vez in range(3):
            lanzados.guardar({"id": "cotejo-uno", "fase": lanzados.LANZADO, "vez": vez})
        self.assertEqual(lanzados.leer("cotejo-uno")["vez"], 2)
        self.assertEqual(self.sobrantes(), [])

    def test_si_el_destino_sigue_ocupado_se_reintenta(self):
        reemplazar, fallos = os.replace, []

        def ocupado(origen, destino):
            if len(fallos) < 3:
                fallos.append(destino)
                raise PermissionError(32, "lo usa otro proceso")
            reemplazar(origen, destino)

        with mock.patch.object(lanzados.os, "replace", ocupado), \
                mock.patch.object(lanzados, "PAUSA_REINTENTO_S", 0):
            lanzados.guardar({"id": "cotejo-uno", "fase": lanzados.LANZADO})
        self.assertEqual(len(fallos), 3)
        self.assertEqual(lanzados.leer("cotejo-uno")["fase"], lanzados.LANZADO)
        self.assertEqual(self.sobrantes(), [])

    def test_si_no_se_pudo_se_borra_el_temporal(self):
        with mock.patch.object(lanzados.os, "replace",
                               side_effect=PermissionError(32, "lo usa otro proceso")), \
                mock.patch.object(lanzados, "PAUSA_REINTENTO_S", 0):
            with self.assertRaises(PermissionError):
                lanzados.guardar({"id": "cotejo-uno", "fase": lanzados.LANZADO})
        self.assertEqual(self.sobrantes(), [])

    def test_los_temporales_viejos_de_un_corte_se_limpian_al_leer(self):
        self.carpeta.mkdir(parents=True)
        viejo = self.carpeta / ".cotejo-uno.json.tmp"
        viejo.write_text('{"id": "cotejo-u', encoding="utf-8")
        hace_rato = time.time() - lanzados.TEMPORAL_VIEJO_S - 5
        os.utime(viejo, (hace_rato, hace_rato))
        reciente = self.carpeta / ".cotejo-dos.json.abc.tmp"
        reciente.write_text("{", encoding="utf-8")
        self.assertEqual(lanzados.todos(), {})
        self.assertEqual(self.sobrantes(), [reciente.name])


if __name__ == "__main__":
    unittest.main()
