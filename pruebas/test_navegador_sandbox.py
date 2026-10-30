"""Un navegador sin interfaz dentro del sandbox del agente (cotejo-xrmr3h, `enrutador/navegador.py`).

La prueba de verdad arranca el navegador en bubblewrap con las mismas reglas que pone el sandbox
de Claude Code (`sandbox.ajustes_claude`): la raíz de solo lectura, escribir solo en la carpeta
de trabajo y en su `TMPDIR`, sin red propia, sin espacios de nombres de usuario y el filtro
seccomp que niega `socket(AF_UNIX)` —el que tumbaba a Chromium—, y comprueba que sale un PNG de
una página local, por `file://` y por un `http.server` en `localhost` arrancado en el mismo
comando. Antes comprueba que la jaula muerde (no deja crear un socket de Unix ni escribir fuera),
para que un verde no salga de una jaula floja. Se salta sin bwrap, sin firefox o fuera de x86-64
y aarch64.
"""

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from enrutador import armado, navegador, sandbox  # noqa: E402

BWRAP = shutil.which("bwrap")
FIREFOX = shutil.which("firefox")


def bwrap_arranca():
    """Que bwrap esté no basta: en el runner de GitHub el kernel no deja crear namespaces."""
    try:
        return subprocess.run([BWRAP, "--ro-bind", "/", "/", "true"], capture_output=True,
                              timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

# Lo justo de seccomp: (arquitectura de audit, número de `socket`).
ARQUITECTURAS = {"x86_64": (0xC000003E, 41), "aarch64": (0xC00000B7, 198)}
AF_UNIX, EPERM = 1, 1


def filtro_sin_sockets_unix(maquina=None):
    """El programa BPF (para `bwrap --seccomp`) que niega `socket(AF_UNIX, ...)` con EPERM, como
    el de Claude Code; `socketpair` sigue valiendo. None en otra arquitectura."""
    datos = ARQUITECTURAS.get(maquina or os.uname().machine)
    if not datos:
        return None
    arch, nr_socket = datos
    ld, jeq, ret = 0x20, 0x15, 0x06
    permitir, negar = 0x7FFF0000, 0x00050000 | EPERM
    instrucciones = [
        (ld, 0, 0, 4),                 # arch
        (jeq, 1, 0, arch),
        (ret, 0, 0, permitir),
        (ld, 0, 0, 0),                 # número de llamada
        (jeq, 0, 3, nr_socket),
        (ld, 0, 0, 16),                # args[0] (familia), 32 bits bajos
        (jeq, 0, 1, AF_UNIX),
        (ret, 0, 0, negar),
        (ret, 0, 0, permitir),
    ]
    return b"".join(struct.pack("=HBBI", *i) for i in instrucciones)


def bwrap_como_claude(ajustes, tmpdir, fd_seccomp):
    """El argv de bubblewrap con las reglas de `ajustes` (la clave `sandbox` de
    `ajustes_claude`) como las aplica Claude Code en Linux: todo de solo lectura menos
    `allowWrite`, su `TMPDIR` y un `/dev` y `/proc` propios; sin red, sin capacidades, sin
    espacios de nombres de usuario anidados y con el filtro de sockets de Unix."""
    caja = ajustes["sandbox"]
    argv = [BWRAP, "--new-session", "--die-with-parent", "--ro-bind", "/", "/"]
    for ruta in caja["filesystem"]["allowWrite"]:
        argv += ["--bind", ruta, ruta]
    for ruta in caja["filesystem"]["denyWrite"]:
        if os.path.exists(ruta):
            argv += ["--ro-bind", ruta, ruta]
    argv += ["--bind", tmpdir, tmpdir, "--setenv", "TMPDIR", tmpdir,
             "--setenv", "SANDBOX_RUNTIME", "1",
             "--dev", "/dev", "--proc", "/proc",
             "--unshare-net", "--unshare-pid", "--unshare-user", "--disable-userns",
             "--cap-drop", "ALL", "--seccomp", str(fd_seccomp)]
    return argv


@unittest.skipUnless(BWRAP and FIREFOX and filtro_sin_sockets_unix() and bwrap_arranca(),
                     "sin bwrap, sin firefox, en una arquitectura sin filtro o sin namespaces")
class NavegadorEnElSandbox(unittest.TestCase):

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="cotejo-xrmr3h-"))
        self.trabajo = self.base / "trabajo"
        self.tmp = self.base / "tmp"
        self.fuera = self.base / "fuera"
        for carpeta in (self.trabajo, self.tmp, self.fuera):
            carpeta.mkdir()
        (self.trabajo / "pagina.html").write_text(
            "<html><body style='background:#c33'><h1>Cotejo</h1></body></html>",
            encoding="utf-8")
        self.ajustes = sandbox.ajustes_claude([str(self.trabajo)], [], ["github.com"])

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def encerrar(self, script, espera=150):
        """Corre `script` (bash) en la jaula, desde la carpeta de trabajo."""
        lectura, escritura = os.pipe()
        os.write(escritura, filtro_sin_sockets_unix())
        os.close(escritura)
        try:
            argv = bwrap_como_claude(self.ajustes, str(self.tmp), lectura)
            argv += ["--chdir", str(self.trabajo), "--", "/bin/bash", "-c", script]
            return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                  text=True, timeout=espera, pass_fds=(lectura,),
                                  env={**os.environ, "PYTHONPATH": str(RAIZ)})
        finally:
            os.close(lectura)

    def test_la_jaula_muerde(self):
        hecho = self.encerrar(textwrap.dedent(f"""
            python3 -c 'import socket; socket.socket(socket.AF_UNIX)' 2>/dev/null \\
                && echo socket-unix-abierto
            python3 -c 'import socket; socket.socketpair()' && echo socketpair-ok
            touch {self.fuera}/x 2>/dev/null && echo escribe-fuera
            touch ./dentro && echo escribe-dentro
        """))
        self.assertIn("socketpair-ok", hecho.stdout)
        self.assertIn("escribe-dentro", hecho.stdout)
        self.assertNotIn("socket-unix-abierto", hecho.stdout)
        self.assertNotIn("escribe-fuera", hecho.stdout)
        self.assertFalse((self.fuera / "x").exists())

    def test_captura_de_una_pagina_por_file_y_por_localhost(self):
        hecho = self.encerrar(textwrap.dedent(f"""
            python3 -m enrutador.navegador pagina.html file.png --ancho 400 --alto 300
            python3 -m http.server 8765 --bind 127.0.0.1 >/dev/null 2>&1 &
            servidor=$!
            sleep 1
            python3 -m enrutador.navegador http://localhost:8765/pagina.html local.png \\
                --ancho 400 --alto 300
            kill $servidor
        """))
        for nombre in ("file.png", "local.png"):
            with self.subTest(nombre):
                png = self.trabajo / nombre
                self.assertTrue(navegador.es_png(png), hecho.stdout + hecho.stderr)
                self.assertEqual(struct.unpack(">II", png.read_bytes()[16:24]), (400, 300))
        # El perfil fue al TMPDIR del sandbox y se borró; fuera no escribió nada.
        self.assertEqual(list(self.tmp.iterdir()), [])
        self.assertEqual(list(self.fuera.iterdir()), [])


class Eleccion(unittest.TestCase):

    def which(self, *hay):
        return lambda nombre: f"/usr/bin/{nombre}" if nombre in hay else None

    def test_dentro_del_sandbox_solo_firefox(self):
        entorno = {"SANDBOX_RUNTIME": "1"}
        self.assertEqual(navegador.elegir(entorno, self.which("firefox", "chromium"))[0],
                         "firefox")
        tipo, _, motivo = navegador.elegir(entorno, self.which("chromium"))
        self.assertIsNone(tipo)
        self.assertIn("socket de Unix", motivo)
        self.assertIsNone(navegador.elegir({"COTEJO_SANDBOX": "1"}, self.which("chromium"))[0])

    def test_al_agente_no_se_le_promete_chromium(self):
        # El encargo y la nota se arman fuera del sandbox; con solo Chromium, el agente
        # encerrado no podría sacar capturas: ni se le piden ni se le da el comando.
        self.assertFalse(navegador.disponible_para_el_agente(self.which("chromium")))
        self.assertTrue(navegador.disponible_para_el_agente(self.which("firefox")))
        with mock.patch.object(navegador, "disponible_para_el_agente", return_value=False):
            self.assertEqual(armado.nota_sandbox(), armado.NOTA_SIN_NAVEGADOR)

    def test_fuera_vale_chromium(self):
        self.assertEqual(navegador.elegir({}, self.which("chromium"))[:2],
                         ("chromium", "/usr/bin/chromium"))
        self.assertIsNone(navegador.elegir({}, self.which())[0])

    def test_argv_y_url(self):
        argv = navegador.argv_captura("firefox", "/f", "file:///p.html", "/w/c.png", "/t/p")
        self.assertEqual(argv[:5], ["/f", "--headless", "--no-remote", "--profile", "/t/p"])
        self.assertIn("--window-size=1280,800", argv)
        chromium = navegador.argv_captura("chromium", "/c", "u", "/w/c.png", "/t/p", 10, 20)
        self.assertIn("--user-data-dir=/t/p", chromium)
        self.assertNotIn("--no-sandbox", chromium)   # fuera del sandbox conserva el suyo
        self.assertEqual(navegador.a_url("http://localhost:1/"), "http://localhost:1/")
        self.assertTrue(navegador.a_url("/x/p.html").startswith("file:///"))

    def test_sin_navegador_no_lanza_nada(self):
        with mock.patch.object(navegador.subprocess, "Popen") as popen:
            hecho = navegador.capturar("p.html", "/nunca/c.png", which=lambda _: None,
                                       entorno={})
        self.assertFalse(hecho["ok"])
        popen.assert_not_called()

    def test_la_nota_del_sandbox_dice_como_ver_una_pagina(self):
        self.assertIn("firefox --headless", armado.NOTA_SANDBOX)
        # Lo que solo vale dentro del repo de Cotejo no va al encargo (cotejo-v40nc1).
        self.assertNotIn("enrutador.navegador", armado.NOTA_SANDBOX)

    def test_el_sandbox_no_abre_sockets_de_unix_ni_escritura_nueva(self):
        caja = sandbox.ajustes_claude(["/w"])["sandbox"]
        self.assertNotIn("allowAllUnixSockets", caja.get("network", {}))
        self.assertNotIn("allowUnixSockets", caja.get("network", {}))
        self.assertEqual(caja["filesystem"]["allowWrite"], ["/w"])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(os.environ.get("COTEJO_PRUEBA_CLAUDE") == "1"
                     and shutil.which("claude") and FIREFOX,
                     "prueba con Claude y Firefox de verdad: COTEJO_PRUEBA_CLAUDE=1")
class LaEntregaNoDependeDelSandbox(unittest.TestCase):
    """Dentro del sandbox **real** de Claude, el agente solo pide las capturas; el board las
    saca fuera (cotejo-v40nc1). La prueba emulada de arriba no reproduce el fallo de Firefox
    155 (clone EPERM, WebRender y dconf de solo lectura): esta corre un `claude -p` de verdad
    con las mismas reglas del armado y se salta si no se pide con `COTEJO_PRUEBA_CLAUDE=1`."""

    def setUp(self):
        if not sandbox.disponible()[0]:
            self.skipTest("esta máquina no tiene el sandbox de Claude (bwrap/socat)")
        base = Path(tempfile.mkdtemp(prefix="cotejo-v40nc1-"))
        self.addCleanup(shutil.rmtree, base, True)
        self.base = base
        self.vault = base / "vault"
        self.notas = self.vault / "01-Proyectos"
        self.estado = base / "estado"
        self.config_dir = base / "config"
        for carpeta in (self.notas, self.estado, self.config_dir):
            carpeta.mkdir(parents=True)
        (self.notas / "Uno.md").write_text(
            "---\ntipo: proyecto\n---\n\n## Tareas\n\n"
            "- [ ] Haciéndola #en-curso #agente/haiku\n", encoding="utf-8")
        (self.vault / "pagina.html").write_text(
            "<html><body style='background:#2a7'><h1>Cotejo</h1></body></html>",
            encoding="utf-8")
        self.config = self.config_dir / "config.json"
        self.config.write_text(json.dumps({
            "fuente": "obsidian",
            "fuentes": {"obsidian": {"vault": str(self.vault),
                                     "carpeta_proyectos": "01-Proyectos"}}},
            ensure_ascii=False), encoding="utf-8")
        self.entorno = {
            **os.environ,
            "PYTHONPATH": str(RAIZ),
            "COTEJO_CONFIG": str(self.config),
            "COTEJO_VAULT": str(self.vault),
            "COTEJO_CARPETA_PROYECTOS": "01-Proyectos",
            "COTEJO_ESTADO": str(self.estado),
        }
        codigo, texto = self.correr_cli("tareas", "--proyecto", "Uno")
        self.assertEqual(codigo, 0, texto)
        self.id = json.loads(texto)["tareas"][0]["id"]

    def correr_cli(self, *argumentos):
        hecho = subprocess.run([sys.executable, "-m", "tareas", *argumentos],
                               cwd=self.vault, env=self.entorno, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=120)
        return hecho.returncode, hecho.stdout.strip() or hecho.stderr.strip()

    def lanzar(self):
        from enrutador import clientes, config as cfg
        cliente = clientes.de("claude")
        carpetas = [str(self.vault), str(self.estado), str(self.config_dir)]
        ramas = armado.ramas_protegidas(str(self.vault))
        ajustes = sandbox.ajustes_claude(carpetas, [], [])
        prompt = (f"Corre una sola vez, exactamente, esta orden con Bash y dime su código de "
                  f"salida y si el JSON dice \"cambio\": true. No arranques ningún navegador, "
                  f"no edites archivos y no hagas nada más:\n\n"
                  f"python3 -m tareas entregar {self.id} --evidencia \"capturas pedidas desde "
                  f"el sandbox\" --captura-desde pagina.html --repo {self.vault}")
        argv = armado.comando(cfg.cargar(self.config_dir / "enrutador.json"), cliente,
                              "haiku", None, prompt, carpetas, ramas, sandbox=ajustes)
        return subprocess.run(argv, cwd=self.vault, stdin=subprocess.DEVNULL, timeout=300,
                              env={**armado.entorno(cliente, carpetas, ramas,
                                                    {"activo": True, "entorno": {}}),
                                   **self.entorno, "PWD": str(self.vault)},
                              capture_output=True, text=True)

    def test_el_agente_entrega_sin_png_y_el_board_las_saca_fuera(self):
        from tareas import bitacora
        archivo = self.estado / "bitacora.jsonl"
        with mock.patch.object(bitacora, "ARCHIVO", archivo), \
                mock.patch.object(navegador, "_carpeta_de_la_entrega",
                                  return_value=self.vault):
            hecho = self.lanzar()
            self.assertEqual(hecho.returncode, 0, hecho.stderr[-3000:])
            entrega = [a for a in bitacora._anotaciones()
                       if a.get("operacion") == "entregar"][-1]
            # El agente no produjo ningún PNG: dejó la petición y entregó igual.
            self.assertEqual(entrega["capturas_solicitadas"], ["pagina.html"])
            self.assertNotIn("capturas", entrega)
            self.assertEqual(len(bitacora.pendientes_de_captura()), 1)
            # Fuera del sandbox sí se sacan, y quedan unidas a la misma entrega.
            resultados = navegador.capturar_pendientes()
            self.assertEqual(len(resultados), 1)
            self.assertEqual(resultados[0]["capturas_avisos"], [])
            self.assertEqual([c["tipo"] for c in resultados[0]["capturas"]],
                             ["movil", "escritorio"])
            self.assertEqual(bitacora.pendientes_de_captura(), [])
            self.assertEqual(len(bitacora.ultima_entrega(entrega["id"])["capturas"]), 2)
