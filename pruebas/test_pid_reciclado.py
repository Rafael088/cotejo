"""Parar a un agente en Windows no mata a otro programa que heredó su pid (cotejo-hrnx1m).

En Windows `procesos.vivo` solo miraba si el pid existía, y `terminar` le hacía
`taskkill /PID <pid> /T /F`: con el pid ya reciclado, cerraba el árbol entero de otro programa
(el humo cerró así el Chrome del dueño el 04-nov). Ahora se mira el ejecutable del pid y la hora
de nacimiento anotada al lanzar, y el árbol se recorre a mano exigiendo que cada hijo naciera
después de su padre.

Sin Windows a mano: se simula con `sys.platform = "win32"` y una tabla de procesos falsa en lugar
de kernel32 (`_ApiWindows`), con los mismos tres verbos (`info`, `foto`, `matar`).
"""

import socket
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import procesos


class WindowsFalso:
    """Una tabla {pid: (ppid, imagen, nacio)} con lo que se paró."""

    def __init__(self, tabla):
        self.tabla = dict(tabla)
        self.parados = []

    def info(self, pid):
        if pid not in self.tabla:
            return None
        _, imagen, nacio = self.tabla[pid]
        return {"vivo": True, "creado": nacio, "imagen": imagen}

    def foto(self):
        return [(pid, ppid) for pid, (ppid, _, _) in self.tabla.items()]

    def matar(self, pid, nacio):
        if pid not in self.tabla or self.tabla[pid][2] != nacio:
            return False
        self.parados.append(pid)
        del self.tabla[pid]
        return True


CMD = r"C:\Windows\System32\cmd.exe"
OPENCODE = r"C:\Users\rafa\AppData\Roaming\npm\node_modules\opencode\bin\opencode.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROGRAMA = r"C:\Users\rafa\AppData\Roaming\npm\opencode.cmd"

# Un registro anterior: `cmd.exe /c opencode.cmd` (pid 100, nació en 5000) → opencode.exe.
AGENTE = {100: (4, CMD, 5000), 101: (100, OPENCODE, 5001), 102: (101, OPENCODE, 5002)}
# Chrome, con el pid 100 ya reciclado tras morir el agente.
CHROME_RECICLADO = {100: (4, CHROME, 9000), 300: (100, CHROME, 9001), 301: (100, CHROME, 9002)}


class EnWindows(unittest.TestCase):
    def windows(self, tabla):
        falso = WindowsFalso(tabla)
        for parche in (mock.patch.object(procesos.sys, "platform", "win32"),
                       mock.patch.object(procesos, "_API", falso)):
            parche.start()
            self.addCleanup(parche.stop)
        return falso


class UnPidReciclado(EnWindows):
    def test_otro_programa_con_el_pid_no_se_para(self):
        win = self.windows(CHROME_RECICLADO)
        self.assertFalse(procesos.terminar(100, PROGRAMA, 5000))
        self.assertEqual(win.parados, [])

    def test_sin_hora_anotada_basta_el_nombre_para_no_pararlo(self):
        win = self.windows(CHROME_RECICLADO)
        self.assertFalse(procesos.terminar(100, PROGRAMA))
        self.assertEqual(win.parados, [])

    def test_el_mismo_programa_nacido_en_otro_momento_no_se_para(self):
        # La persona abrió su propio `cmd` y le tocó el pid del agente muerto.
        win = self.windows({100: (4, CMD, 7000), 200: (100, CMD, 7001)})
        self.assertFalse(procesos.terminar(100, PROGRAMA, 5000))
        self.assertEqual(win.parados, [])

    def test_un_pid_reciclado_cuenta_como_muerto(self):
        self.windows(CHROME_RECICLADO)
        self.assertFalse(procesos.vivo(100, PROGRAMA, 5000))
        self.assertFalse(procesos.vivo(100, "opencode"))
        linea = {"fase": "lanzado", "pid": 100, "programa": PROGRAMA, "nacio": 5000,
                 "host": socket.gethostname()}
        self.assertTrue(procesos.anotado_muerto(linea))

    def test_sin_poder_leer_el_ejecutable_vive_pero_no_se_para(self):
        win = self.windows({100: (4, None, 5000)})
        self.assertTrue(procesos.vivo(100, PROGRAMA))
        self.assertFalse(procesos.terminar(100, PROGRAMA))
        self.assertEqual(win.parados, [])


class ElArbolDelAgente(EnWindows):
    def test_parar_al_agente_para_su_arbol(self):
        win = self.windows(AGENTE)
        self.assertTrue(procesos.vivo(100, PROGRAMA, 5000))
        self.assertTrue(procesos.terminar(100, PROGRAMA, 5000))
        self.assertEqual(win.parados, [100, 101, 102])   # la raíz primero

    def test_un_registro_viejo_sin_hora_tambien_se_para(self):
        win = self.windows(AGENTE)
        self.assertTrue(procesos.terminar(100, PROGRAMA))
        self.assertEqual(sorted(win.parados), [100, 101, 102])

    def test_lo_que_dice_colgar_del_agente_pero_nacio_antes_no_se_toca(self):
        # Un Chrome cuyo padre muerto tenía el pid 101: su ppid sigue diciendo 101, aunque
        # nació mucho antes que el opencode que tiene ahora ese pid.
        win = self.windows({**AGENTE, 300: (101, CHROME, 1000), 301: (300, CHROME, 1001)})
        self.assertTrue(procesos.terminar(100, PROGRAMA, 5000))
        self.assertEqual(win.parados, [100, 101, 102])
        self.assertIn(300, win.tabla)
        self.assertIn(301, win.tabla)

    def test_un_hijo_del_que_no_se_sabe_cuando_nacio_no_se_toca(self):
        win = self.windows({**AGENTE, 103: (100, OPENCODE, None)})
        self.assertTrue(procesos.terminar(100, PROGRAMA, 5000))
        self.assertNotIn(103, win.parados)

    def test_lanzado_por_su_nombre_sin_extension(self):
        win = self.windows(AGENTE)
        self.assertTrue(procesos.terminar(100, "opencode", 5000))
        self.assertEqual(len(win.parados), 3)

    def test_el_shim_nuevo_anota_directamente_el_pid_del_exe(self):
        directo = {101: (4, OPENCODE, 5001), 102: (101, OPENCODE, 5002)}
        win = self.windows(directo)
        self.assertTrue(procesos.vivo(101, "opencode", 5001))
        self.assertTrue(procesos.terminar(101, "opencode", 5001))
        self.assertEqual(win.parados, [101, 102])


class ElNombreDelEjecutable(unittest.TestCase):
    def test_casos(self):
        casos = [
            (OPENCODE, "opencode", True),
            (OPENCODE, r"C:\npm\opencode.exe", True),
            (CMD, PROGRAMA, True),            # un .cmd lo corre cmd.exe
            (CMD, "opencode", True),          # sin extensión puede ser un .cmd
            (CMD, "cmd", True),
            (CMD, r"C:\x\opencode.exe", False),
            (CHROME, PROGRAMA, False),
            (CHROME, "opencode", False),
            (r"C:\Python\python.exe", r"C:\Python\python.exe", True),
            (r"C:\Python\PYTHON.EXE", "python", True),
        ]
        for imagen, programa, esperado in casos:
            self.assertEqual(procesos.es_su_imagen(imagen, programa), esperado,
                             (imagen, programa))


class EnLinux(unittest.TestCase):
    """La hora de nacimiento también vale aquí (`starttime` de `/proc/<pid>/stat`)."""

    def test_el_propio_proceso_tiene_hora_y_sigue_siendo_el(self):
        import os
        nacio = procesos.nacimiento(os.getpid())
        if nacio is None:
            self.skipTest("sin /proc")
        self.assertTrue(procesos.vivo(os.getpid(), "", nacio))
        self.assertFalse(procesos.vivo(os.getpid(), "", nacio + 1))
        self.assertFalse(procesos.terminar(os.getpid(), "", nacio + 1))

    def test_un_pid_que_no_existe_no_tiene_hora(self):
        self.assertIsNone(procesos.nacimiento(0))
        self.assertIsNone(procesos.nacimiento("x"))


class LoQueSeAnotaAlLanzar(unittest.TestCase):
    """La hora de nacimiento se anota con el pid y llega hasta `terminar` al parar."""

    def setUp(self):
        import os
        import tempfile
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        parche = mock.patch.dict(os.environ, {"COTEJO_ESTADO": temporal.name})
        parche.start()
        self.addCleanup(parche.stop)

    def test_lanzados_anota_la_hora_y_detener_la_pasa(self):
        from enrutador import despacho_board
        from tareas import lanzados
        registro = {"id": "cotejo-uno"}
        with mock.patch.object(procesos, "nacimiento", return_value=5000):
            lanzados.anotar_lanzado(registro, 100, PROGRAMA)
        self.assertEqual(lanzados.leer("cotejo-uno")["nacio"], 5000)
        with mock.patch.object(procesos, "terminar") as terminar:
            despacho_board.detener("cotejo-uno", "prueba")
        terminar.assert_called_once_with(100, PROGRAMA, 5000)


if __name__ == "__main__":
    unittest.main()
