"""Si el pid anotado sigue siendo el del cliente, también en el instante del lanzamiento.

`systemd-run --scope` hace `execve` sobre sí mismo, pero no antes de volver del `fork`: entre
que `Popen` devuelve el pid y systemd-run termina su ida y vuelta por D-Bus, `/proc/<pid>/
cmdline` todavía dice «systemd-run … -- cliente». Ahí `procesos.vivo` comparaba ese argv con el
programa del cliente, no lo reconocía y el board enseñaba «Se cerró sin entregar» justo al
lanzar (cotejo-ovw2xt: pasó en la app de verdad con Codex, que siguió vivo y entregó).
"""

import os
import socket
import unittest
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import procesos
from tareas import lanzados, senal_vida

# Lo que deja `/proc/<pid>/cmdline` mientras systemd-run aún no ha hecho el exec: el envoltorio
# entero, con el cliente al final, detrás del `--`.
ENVOLTORIO = [
    "systemd-run", "--user", "--scope", "--quiet",
    "--unit=cotejo-headless-cotejo-ovw2xt-1234-abcd12ef",
    "-p", "MemoryMax=50%", "-p", "OOMPolicy=continue", "--",
    "codex", "exec", "--skip-git-repo-check", "haz la tarea",
]
CLIENTE = ["codex", "exec", "--skip-git-repo-check", "haz la tarea"]


def cmdline(*partes):
    return b"\0".join(p.encode() for p in partes) + b"\0"


class ElPidDelCliente(unittest.TestCase):
    def con_cmdline(self, *partes):
        return mock.patch.object(procesos.Path, "read_bytes", return_value=cmdline(*partes))

    def test_el_envoltorio_de_systemd_run_cuenta_como_el_cliente(self):
        with self.con_cmdline(*ENVOLTORIO):
            self.assertTrue(procesos.vivo(os.getpid(), "codex"))

    def test_el_envoltorio_no_hace_pasar_a_otro_programa(self):
        with self.con_cmdline(*ENVOLTORIO):
            self.assertFalse(procesos.vivo(os.getpid(), "claude"))

    def test_ya_hecho_el_exec_manda_el_argv_del_cliente(self):
        with self.con_cmdline(*CLIENTE):
            self.assertTrue(procesos.vivo(os.getpid(), "codex"))
            self.assertFalse(procesos.vivo(os.getpid(), "claude"))

    def test_un_systemd_run_que_no_es_de_un_cliente_no_cuenta(self):
        with self.con_cmdline("systemd-run", "--user", "--scope", "--", "sleep", "10"):
            self.assertFalse(procesos.vivo(os.getpid(), "codex"))


class LoQueVeElBoardAlLanzar(unittest.TestCase):
    """El registro tal cual queda al lanzar: `lanzados.estado` y la señal de vida de la ficha."""

    def setUp(self):
        self.registro = {"id": "cotejo-ovw2xt", "fase": lanzados.LANZADO,
                         "pid": os.getpid(), "programa": "codex",
                         "host": socket.gethostname(), "modelo": "gpt-5-codex",
                         "ts": 1_000_000, "log": "/no/existe.log"}

    def test_en_el_instante_del_lanzamiento_sigue_trabajando(self):
        with mock.patch.object(procesos.Path, "read_bytes",
                               return_value=cmdline(*ENVOLTORIO)):
            estado = lanzados.estado(self.registro)
            vivo = senal_vida.evaluar(self.registro, ahora=1_000_030)
        self.assertEqual(estado["estado"], lanzados.TRABAJANDO)
        self.assertEqual(vivo["nivel"], senal_vida.ACTIVO)
        self.assertEqual(vivo["titulo"], "Trabajando")
        self.assertFalse(vivo["retomar"])

    def test_solo_cuando_ya_no_esta_se_ofrece_retomar(self):
        with mock.patch.object(procesos, "vivo", return_value=False):
            estado = lanzados.estado(self.registro)
            vivo = senal_vida.evaluar(self.registro, ahora=1_000_030)
        self.assertEqual(estado["estado"], lanzados.MURIO)
        self.assertEqual(vivo["nivel"], senal_vida.MURIO)
        self.assertTrue(vivo["retomar"])