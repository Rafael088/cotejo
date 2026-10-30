"""«Ver mi app» sin GTK (v1.3.0, cotejo-vn4qd2).

- La sección «## Cómo se abre» de la arquitectura: se lee, se valida (sin shell, sin sudo, sin
  salir de la carpeta), sobrevive a volver a anotar la arquitectura, y `anotar`/`editar` se
  niegan sin escribir si está mal.
- Sin anotación, la deducción prudente (`package.json` con `dev`/`start`, `index.html`) y, si
  no, la frase en llano.
- El ciclo de vida con procesos de verdad (solo Python, que está en CI): el servidor estático
  propio, un comando anotado con su dirección, uno que dice la dirección en su salida, la
  reutilización, parar (con sus hijos), el que no arranca, el que tarda y el que no existe.
  Nunca se abre un navegador: `Servidores.abrir` solo devuelve qué abrir.
"""

import contextlib
import io
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from tareas import almacen, cli, como_se_abre as c, inicio, servidor_app as s
from enrutador import encargo

PY = shlex.quote(sys.executable)
ANOTADA = """Una tienda.

## Cómo se abre

- comando: npm run dev
- URL: http://localhost:5173
- Qué esperar: la página de pedidos, vacía la primera vez
"""


class Seccion(unittest.TestCase):
    def test_lee_comando_url_y_que_esperar(self):
        como, errores = c.analizar(ANOTADA)
        self.assertEqual(errores, [])
        self.assertEqual((como.comando, como.url, como.que_esperar),
                         ("npm run dev", "http://localhost:5173",
                          "la página de pedidos, vacía la primera vez"))
        self.assertEqual(como.tipo, "servidor")
        self.assertEqual(como.argv(), ["npm", "run", "dev"])

    def test_sin_seccion_no_hay_nada_ni_error(self):
        self.assertEqual(c.analizar("Solo texto.\n\n## Piezas\n"), (None, []))

    def test_tipos(self):
        self.assertEqual(c.ComoSeAbre(comando="python3 app.py").tipo, "programa")
        self.assertEqual(c.ComoSeAbre(url="https://mi.app").tipo, "enlace")
        self.assertEqual(c.ComoSeAbre(url="web/index.html").tipo, "pagina")
        self.assertEqual(c.ComoSeAbre(url="dist/informe.pdf").tipo, "archivo")

    def test_la_seccion_acaba_en_el_siguiente_titulo(self):
        como, errores = c.analizar("## Cómo se abre\n\n- url: index.html\n\n## Piezas\n\n| a |\n")
        self.assertEqual(errores, [])
        self.assertEqual(como.url, "index.html")

    def test_lo_peligroso_o_raro_es_error(self):
        for linea, pista in (("- comando: sudo npm start", "sudo"),
                             ("- comando: cd web && npm run dev", "sin shell"),
                             ("- comando: npm run dev | tee log", "sin shell"),
                             ("- comando: echo $(rm -rf x)", "sin shell"),
                             ("- carpeta: ../otro\n- comando: npm start", "relativa"),
                             ("- url: /etc/passwd", "relativa"),
                             ("- qué esperar: algo", "necesita"),
                             ("- abrir con: firefox", "no es una línea"),
                             ("- comando: npm 'sin cerrar", "no se entiende")):
            with self.subTest(linea=linea):
                como, errores = c.analizar(f"## Cómo se abre\n\n{linea}\n")
                self.assertIsNone(como)
                self.assertTrue(any(pista in e for e in errores), errores)

    def test_volver_a_anotar_no_borra_como_se_abre(self):
        nuevo = c.con_seccion_previa("Otra versión.\n\n## Piezas\n", ANOTADA)
        self.assertIn("- comando: npm run dev", nuevo)
        self.assertTrue(nuevo.startswith("Otra versión."))
        # Si el texto nuevo trae la suya, manda la nueva.
        propio = "## Cómo se abre\n\n- url: index.html\n"
        self.assertEqual(c.con_seccion_previa(propio, ANOTADA), propio)

    def test_el_formato_se_pide_al_preparar_y_en_cada_encargo(self):
        self.assertIn("## Cómo se abre", c.FORMATO)
        for clave in ("comando:", "url:", "qué esperar:"):
            self.assertIn(clave, c.FORMATO)
        r = inicio.Respuestas(que_es="Una agenda", que_hace="Reservar", carpeta="/tmp/x")
        self.assertIn(c.FORMATO, inicio.armar(r))
        texto = encargo.armar({"id": "cotejo-abc123", "proyecto": "P", "texto": "Algo"},
                              _Decision(), worktree=None)
        self.assertIn(c.FORMATO, texto)
        self.assertIn("cotejo editar <arq-id>", texto)


class _Decision:
    razon = "sí"

    class nivel:
        modelo = "sonnet"


class Deducir(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.carpeta = Path(temporal.name)

    def test_package_json_con_dev_y_luego_start(self):
        (self.carpeta / "package.json").write_text(json.dumps({"scripts": {"start": "x"}}))
        self.assertEqual(c.deducir(self.carpeta).comando, "npm run start")
        (self.carpeta / "package.json").write_text(json.dumps({"scripts": {"dev": "v", "start": "x"}}))
        como = c.deducir(self.carpeta)
        self.assertEqual((como.comando, como.origen, como.tipo), ("npm run dev", "deducido", "programa"))

    def test_index_html_estatico(self):
        (self.carpeta / "index.html").write_text("<h1>hola</h1>")
        self.assertEqual(c.deducir(self.carpeta).tipo, "pagina")

    def test_package_json_roto_o_sin_scripts_no_inventa(self):
        (self.carpeta / "package.json").write_text("{roto")
        self.assertIsNone(c.deducir(self.carpeta))

    def test_sin_nada_lo_dice_en_llano(self):
        plan = c.plan_de(self.carpeta)
        self.assertFalse(plan.ok)
        self.assertEqual(plan.motivo, c.SIN_ANOTAR)
        self.assertIn("No sé cómo abrir tu app todavía", plan.motivo)
        self.assertFalse(c.plan_de(self.carpeta / "no-existe").ok)

    def test_lo_anotado_gana_a_lo_deducido(self):
        (self.carpeta / "index.html").write_text("x")
        (self.carpeta / "package.json").write_text(json.dumps({"scripts": {"dev": "v"}}))
        alm = almacen.Almacen(self.carpeta)
        alm.crear("arquitectura", "Arquitectura", ANOTADA)
        plan = c.plan_de(self.carpeta)
        self.assertTrue(plan.ok)
        self.assertEqual((plan.como.comando, plan.como.origen), ("npm run dev", "arquitectura"))

    def test_lo_anotado_sin_codigo_dice_que_no_hay_app_todavia(self):
        # Un proyecto recién creado anota `npm run dev` pero aún no tiene package.json:
        # «Ver mi app» no debe correrlo (enseñaría el ENOENT de npm), sino esperar.
        almacen.Almacen(self.carpeta).crear("arquitectura", "Arquitectura", ANOTADA)
        plan = c.plan_de(self.carpeta)
        self.assertFalse(plan.ok)
        self.assertTrue(plan.sin_app)
        self.assertEqual(plan.motivo, c.SIN_APP)
        self.assertIn("primera pantalla", plan.motivo)

    def test_falta_la_app(self):
        self.assertTrue(c.falta_la_app(self.carpeta, c.ComoSeAbre(comando="npm run dev")))
        self.assertTrue(c.falta_la_app(self.carpeta, c.ComoSeAbre(comando="yarn dev")))
        (self.carpeta / "package.json").write_text("{}")
        self.assertFalse(c.falta_la_app(self.carpeta, c.ComoSeAbre(comando="npm run dev")))
        self.assertTrue(c.falta_la_app(self.carpeta, c.ComoSeAbre(url="index.html")))
        (self.carpeta / "index.html").write_text("x")
        self.assertFalse(c.falta_la_app(self.carpeta, c.ComoSeAbre(url="index.html")))
        # Un comando que no es un gestor de Node no se bloquea por miedo: lo dice el arranque.
        self.assertFalse(c.falta_la_app(self.carpeta, c.ComoSeAbre(comando="python3 app.py")))
        self.assertFalse(c.falta_la_app(self.carpeta, c.ComoSeAbre(url="https://mi.app")))

    def test_lo_anotado_mal_se_dice_y_no_se_deduce(self):
        (self.carpeta / "index.html").write_text("x")
        almacen.Almacen(self.carpeta).crear(
            "arquitectura", "A", "## Cómo se abre\n\n- comando: sudo make run\n")
        plan = c.plan_de(self.carpeta)
        self.assertFalse(plan.ok)
        self.assertIn("Pídele a un agente que la corrija", plan.motivo)


class Verbos(unittest.TestCase):
    """`anotar` y `editar` validan la sección; volver a anotar la conserva."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "tienda"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / ".cotejo" / "arquitectura").mkdir(parents=True)
        (self.repo / ".cotejo" / "tareas.md").write_text("# Tareas\n", encoding="utf-8")

    def correr(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            codigo = cli.main([*args, "--repo", str(self.repo)])
        salida = buf.getvalue().strip()
        return codigo, (json.loads(salida) if salida else None)

    def test_anotar_se_niega_con_un_comando_con_sudo(self):
        codigo, datos = self.correr("anotar", "arquitectura", "--titulo", "A", "--texto",
                                    "## Cómo se abre\n\n- comando: sudo npm start\n")
        self.assertNotEqual(codigo, 0)
        self.assertIn("sudo", datos["error"])
        self.assertEqual(list((self.repo / ".cotejo" / "arquitectura").glob("*.md")), [])

    def test_anotar_otra_vez_con_piezas_conserva_como_se_abre(self):
        codigo, datos = self.correr("anotar", "arquitectura", "--titulo", "A", "--texto", ANOTADA)
        self.assertEqual(codigo, 0, datos)
        codigo, datos = self.correr("anotar", "arquitectura", "--titulo", "A", "--texto", "Nueva.",
                                    "--pieza", "ve|Pantalla|Lo que se ve||")
        self.assertEqual(codigo, 0, datos)
        self.assertTrue(datos.get("actualizada"))
        como, errores = c.de_la_arquitectura(self.repo)
        self.assertEqual((como.comando, errores), ("npm run dev", []))

    def test_editar_valida_la_seccion(self):
        _, datos = self.correr("anotar", "arquitectura", "--titulo", "A", "--texto", ANOTADA)
        _, leida = self.correr("leer", datos["id"])
        codigo, error = self.correr("editar", datos["id"], "--version", leida["version"],
                                    "--texto", ANOTADA.replace("npm run dev", "npm run dev && x"))
        self.assertNotEqual(codigo, 0)
        self.assertIn("sin shell", error["error"])


class CicloDeVida(unittest.TestCase):
    """Procesos de verdad (Python y su http.server), en puertos libres de 127.0.0.1."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.carpeta = Path(temporal.name) / "app"
        self.carpeta.mkdir()
        (self.carpeta / "index.html").write_text("<h1>Mi app</h1>", encoding="utf-8")
        self.servidores = s.Servidores(carpeta_logs=Path(temporal.name) / "logs",
                                       tope_servidor=15, tope_programa=2)
        self.addCleanup(self.servidores.parar_todos)

    def plan(self, **campos):
        return c.Plan(como=c.ComoSeAbre(**campos), carpeta=str(self.carpeta))

    def leer(self, url):
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.read().decode()

    def test_pagina_estatica_con_el_servidor_de_cotejo_reutilizar_y_parar(self):
        r = self.servidores.abrir("tienda", self.plan(url="index.html", que_esperar="un titular"))
        self.assertTrue(r.ok, r.texto)
        self.assertTrue(r.abrir.startswith("http://127.0.0.1:"))
        self.assertIn("Deberías ver: un titular", r.texto)
        self.assertIn("Mi app", self.leer(r.abrir))
        proceso = self.servidores.corriendo["tienda"].proceso
        # Otra vez: el mismo proceso, no otro.
        otra = self.servidores.abrir("tienda", self.plan(url="index.html"))
        self.assertIn("ya estaba abierta", otra.texto)
        self.assertEqual(otra.abrir, r.abrir)
        self.assertIs(self.servidores.corriendo["tienda"].proceso, proceso)
        self.assertTrue(self.servidores.parar("tienda"))
        self.assertIsNotNone(proceso.poll())
        self.assertFalse(s.responde(r.abrir))
        self.assertFalse(self.servidores.vivo("tienda"))

    def test_la_pagina_estatica_no_ensena_lo_oculto(self):
        # La carpeta del proyecto lleva .git y .cotejo: el servidor de Cotejo no los sirve,
        # ni con la ruta escapada, ni lista carpetas.
        (self.carpeta / ".git").mkdir()
        (self.carpeta / ".git" / "config").write_text("[remote]", encoding="utf-8")
        (self.carpeta / ".env").write_text("CLAVE=1", encoding="utf-8")
        (self.carpeta / "img").mkdir()
        r = self.servidores.abrir("tienda", self.plan(url="index.html"))
        self.assertTrue(r.ok, r.texto)
        base = r.abrir.rsplit("/", 1)[0]
        self.assertIn("Mi app", self.leer(r.abrir))
        for ruta in ("/.git/config", "/%2Egit/config", "/img/../.env", "/.env", "/img/"):
            with self.subTest(ruta=ruta), self.assertRaises(urllib.error.HTTPError) as error:
                self.leer(base + ruta)
            self.assertEqual(error.exception.code, 404)

    def test_comando_anotado_con_su_direccion(self):
        puerto = s.puerto_libre()
        url = f"http://127.0.0.1:{puerto}/"
        r = self.servidores.abrir("tienda", self.plan(
            comando=f"{PY} -m http.server {puerto} --bind 127.0.0.1", url=url))
        self.assertTrue(r.ok, r.texto)
        self.assertEqual(r.abrir, url)
        self.assertTrue(r.corriendo)
        self.assertIn("index.html", self.leer(url) + "index.html")
        self.servidores.parar_todos()
        self.assertFalse(s.responde(url))

    def test_la_direccion_sale_de_lo_que_dice_la_app(self):
        puerto = s.puerto_libre()
        guion = self.carpeta / "servir.py"
        guion.write_text(
            "import http.server, sys\n"
            f"print('  Local:   \\x1b[36mhttp://localhost:{puerto}/\\x1b[0m', flush=True)\n"
            f"http.server.HTTPServer(('127.0.0.1', {puerto}), "
            "http.server.SimpleHTTPRequestHandler).serve_forever()\n")
        r = self.servidores.abrir("tienda", self.plan(comando=f"{PY} servir.py"))
        self.assertTrue(r.ok, r.texto)
        self.assertEqual(r.abrir, f"http://localhost:{puerto}/")

    def test_parar_se_lleva_a_los_hijos(self):
        puerto = s.puerto_libre()
        url = f"http://127.0.0.1:{puerto}/"
        # Un padre que lanza el servidor como hijo, como hace `npm run dev`.
        hijo = f"import subprocess, sys; subprocess.run([sys.executable, '-m', 'http.server', '{puerto}', '--bind', '127.0.0.1'])"
        r = self.servidores.abrir("tienda", self.plan(comando=f"{PY} -c {shlex.quote(hijo)}", url=url))
        self.assertTrue(r.ok, r.texto)
        self.servidores.parar("tienda")
        self.assertFalse(s.responde(url))

    def test_si_no_arranca_el_error_crudo_va_al_registro_no_a_la_frase(self):
        r = self.servidores.abrir("tienda", self.plan(
            comando=f"{PY} -c \"import sys; print('falta node_modules'); sys.exit(3)\"",
            url=f"http://127.0.0.1:{s.puerto_libre()}/"))
        self.assertFalse(r.ok)
        self.assertIn("Tu app no arrancó", r.texto)
        # El error en crudo no se enseña: la frase queda en llano y el detalle va al registro,
        # que el board abre con «Ver lo que dijo».
        self.assertNotIn("falta node_modules", r.texto)
        self.assertTrue(Path(r.log).is_file())
        self.assertIn("falta node_modules", Path(r.log).read_text(encoding="utf-8"))
        self.assertFalse(self.servidores.vivo("tienda"))

    def test_si_tarda_demasiado_se_para_y_se_dice(self):
        self.servidores.tope_servidor = 1
        r = self.servidores.abrir("tienda", self.plan(
            comando=f"{PY} -c \"import time; time.sleep(30)\"",
            url=f"http://127.0.0.1:{s.puerto_libre()}/"))
        self.assertFalse(r.ok)
        self.assertIn("tardó más de 1 segundos", r.texto)
        self.assertEqual(self.servidores.corriendo, {})

    def test_un_programa_sin_direccion_queda_abierto(self):
        r = self.servidores.abrir("tienda", self.plan(
            comando=f"{PY} -c \"import time; time.sleep(30)\"", que_esperar="una ventana"))
        self.assertTrue(r.ok, r.texto)
        self.assertTrue(r.corriendo)
        self.assertEqual(r.abrir, "")
        self.assertIn("Tu app está abierta", r.texto)

    def test_un_programa_que_no_existe(self):
        r = self.servidores.abrir("tienda", self.plan(comando="programa-que-no-existe-xyz run"))
        self.assertFalse(r.ok)
        self.assertIn("No encuentro «programa-que-no-existe-xyz»", r.texto)
        self.assertEqual(self.servidores.corriendo, {})

    def test_enlace_y_archivo_no_arrancan_nada(self):
        r = self.servidores.abrir("tienda", self.plan(url="https://mi.app", que_esperar="x"))
        self.assertEqual((r.ok, r.abrir), (True, "https://mi.app"))
        (self.carpeta / "informe.pdf").write_bytes(b"%PDF")
        r = self.servidores.abrir("tienda", self.plan(url="informe.pdf"))
        self.assertEqual(r.abrir, str(self.carpeta / "informe.pdf"))
        r = self.servidores.abrir("tienda", self.plan(url="falta.pdf"))
        self.assertFalse(r.ok)
        self.assertEqual(self.servidores.corriendo, {})

    def test_url_del_log(self):
        self.assertEqual(s.url_del_log("  ➜  Local:   \x1b[1mhttp://localhost:5173/\x1b[0m\n"),
                         "http://localhost:5173/")
        self.assertEqual(s.url_del_log("ready on http://0.0.0.0:3000."), "http://127.0.0.1:3000")
        self.assertEqual(s.url_del_log("nada"), "")


if __name__ == "__main__":
    unittest.main()
