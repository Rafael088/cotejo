"""La purga, probada contra árboles de mentira.

No corre contra el repo de verdad: el repo cambia todos los días y estas pruebas se
romperían por razones que no tienen nada que ver con la herramienta. Lo que se prueba es el
comportamiento —qué detecta, qué calla, qué no repite— con árboles temporales armados a
propósito. Correr la herramienta contra el repo real es un paso aparte, manual, que queda en
el informe de hallazgos.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ

from herramientas import purga


def config_minima(**extra):
    base = {
        "esquema": 1,
        "patrones": [
            {"id": "home_absoluto", "categoria": "ruta",
             "regex": r"/home/[A-Za-z0-9_.-]+",
             "motivo": "ruta absoluta de este equipo"},
            {"id": "nombre_rafael", "categoria": "identidad",
             "regex": r"(?i)\brafael\b", "motivo": "nombre de pila"},
            {"id": "id_reverso_github", "categoria": "identidad",
             "regex": r"io\.github\.[A-Za-z0-9_.-]+",
             "motivo": "app id con usuario de GitHub"},
            {"id": "token_notion", "categoria": "secreto",
             "regex": r"\b(?:secret_[A-Za-z0-9]{43}|ntn_[A-Za-z0-9]{20,60})\b",
             "motivo": "token de integración de Notion"},
        ],
        "marcas": ["atlas"],
        "directorios_prohibidos": [".git", "__pycache__"],
        "lista_blanca": [],
    }
    base.update(extra)
    return base


class ArbolTemporal:
    """Un directorio temporal que se limpia solo, con un helper para escribir archivos."""

    def __enter__(self):
        self._temporal = tempfile.TemporaryDirectory()
        self.raiz = Path(self._temporal.name)
        return self

    def __exit__(self, *exc):
        self._temporal.cleanup()

    def escribir(self, ruta_relativa, contenido):
        ruta = self.raiz / ruta_relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
        return ruta


class Deteccion(unittest.TestCase):
    def test_detecta_ruta_home_absoluta(self):
        with ArbolTemporal() as arbol:
            arbol.escribir("config.py", 'RUTA = "/home/alguien/algo"\n')
            resultado = purga.escanear_arbol(arbol.raiz, config_minima())
        self.assertFalse(resultado.limpio)
        patrones = {h.patron for h in resultado.hallazgos}
        self.assertIn("home_absoluto", patrones)

    def test_detecta_nombre_personal(self):
        with ArbolTemporal() as arbol:
            arbol.escribir("nota.md", "Esto lo escribió Rafael a mano.\n")
            resultado = purga.escanear_arbol(arbol.raiz, config_minima())
        self.assertEqual([h.patron for h in resultado.hallazgos], ["nombre_rafael"])

    def test_detecta_id_de_github(self):
        with ArbolTemporal() as arbol:
            arbol.escribir("app.py", 'APP_ID = "io.github.alguien.Loquesea"\n')
            resultado = purga.escanear_arbol(arbol.raiz, config_minima())
        self.assertEqual([h.patron for h in resultado.hallazgos], ["id_reverso_github"])

    def test_marca_es_configurable(self):
        """La lista de marcas se agrega en la config: acá con «atlas», y con una inventada
        para probar que no hace falta tocar el código para sumar una nueva."""
        with ArbolTemporal() as arbol:
            arbol.escribir("data/marca/x.svg", "<svg>Zorzal</svg>\n")
            config = config_minima(marcas=["atlas", "zorzal"])
            resultado = purga.escanear_arbol(arbol.raiz, config)
        self.assertEqual([h.patron for h in resultado.hallazgos], ["marca:zorzal"])

    def test_arbol_sin_coincidencias_queda_limpio(self):
        with ArbolTemporal() as arbol:
            arbol.escribir("app.py", "print('hola')\n")
            resultado = purga.escanear_arbol(arbol.raiz, config_minima())
        self.assertTrue(resultado.limpio)
        self.assertEqual(resultado.hallazgos, [])


class Secretos(unittest.TestCase):
    def test_detecta_token_de_notion_pero_no_lo_repite(self):
        token = "secret_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V"  # 43 tras el prefijo
        self.assertEqual(len(token), len("secret_") + 43)
        with ArbolTemporal() as arbol:
            arbol.escribir("config.json", f'{{"token": "{token}"}}\n')
            resultado = purga.escanear_arbol(arbol.raiz, config_minima())
        self.assertEqual(len(resultado.hallazgos), 1)
        hallazgo = resultado.hallazgos[0]
        self.assertEqual(hallazgo.patron, "token_notion")
        self.assertEqual(hallazgo.categoria, "secreto")
        self.assertIsNone(hallazgo.fragmento, "un hallazgo de secreto no debe cargar el valor")

    def test_la_salida_de_texto_no_repite_el_secreto(self):
        token = "ntn_" + ("x" * 40)
        with ArbolTemporal() as arbol:
            arbol.escribir("config.json", f'"{token}"\n')
            codigo, salida = self._correr_cli(arbol.raiz)
        self.assertEqual(codigo, 1)
        self.assertNotIn(token, salida)
        self.assertIn("token_notion", salida)

    def _correr_cli(self, raiz):
        config = raiz.parent / "config_minima.json"
        config.write_text(json.dumps(config_minima()), encoding="utf-8")
        proceso = subprocess.run(
            ["python3", str(RAIZ / "herramientas" / "purga.py"),
             "--raiz", str(raiz), "--config", str(config)],
            capture_output=True, text=True)
        return proceso.returncode, proceso.stdout


class DirectoriosProhibidos(unittest.TestCase):
    def test_no_desciende_pero_reporta_la_carpeta(self):
        with ArbolTemporal() as arbol:
            arbol.escribir("__pycache__/x.pyc", "Rafael, /home/alguien, secret_token\n")
            resultado = purga.escanear_arbol(arbol.raiz, config_minima())
        self.assertEqual(resultado.hallazgos, [], "no debería mirar el contenido")
        self.assertEqual(resultado.directorios_prohibidos, ["__pycache__"])
        self.assertFalse(resultado.limpio)

    def test_archivo_puntero_git_de_un_worktree_se_ignora(self):
        """`.git` como archivo (no carpeta) es de un worktree: plomería del checkout, no
        contenido del proyecto. No debe ni contarse como hallazgo ni como carpeta prohibida."""
        with ArbolTemporal() as arbol:
            arbol.escribir(".git", "gitdir: /home/alguien/otro-repo/.git/worktrees/x\n")
            resultado = purga.escanear_arbol(arbol.raiz, config_minima())
        self.assertTrue(resultado.limpio)

    def test_directorio_git_de_un_repo_normal_se_reporta(self):
        with ArbolTemporal() as arbol:
            (arbol.raiz / ".git").mkdir()
            (arbol.raiz / ".git" / "config").write_text("[core]\n", encoding="utf-8")
            resultado = purga.escanear_arbol(arbol.raiz, config_minima())
        self.assertEqual(resultado.directorios_prohibidos, [".git"])

    def test_worktrees_de_claude_no_desciende_pero_se_reporta(self):
        """`.claude/worktrees/` son los worktrees que arma la propia herramienta cuando varios
        agentes trabajan en paralelo: no viajan en ningún bundle. Se tratan igual que `.git` o
        `__pycache__` — se reportan como carpeta, no se mira su contenido — en vez de bajar y
        reportar cada archivo de cada worktree como si fuera del repo."""
        with ArbolTemporal() as arbol:
            arbol.escribir(".claude/worktrees/una-rama/nota.md", "Rafael, /home/alguien\n")
            config = config_minima(
                directorios_prohibidos=[".git", "__pycache__", "worktrees"])
            resultado = purga.escanear_arbol(arbol.raiz, config)
        self.assertEqual(resultado.hallazgos, [], "no debería mirar el contenido")
        self.assertEqual(resultado.directorios_prohibidos, [".claude/worktrees"])


class ListaBlanca(unittest.TestCase):
    def test_una_excepcion_exime_el_hallazgo_pero_queda_registrada(self):
        with ArbolTemporal() as arbol:
            arbol.escribir("fixtures/sucio.txt", "Rafael\n")
            config = config_minima(lista_blanca=[
                {"ruta": "fixtures/*", "patron": "*", "motivo": "fixture de prueba, a propósito"}])
            resultado = purga.escanear_arbol(arbol.raiz, config)
        self.assertEqual(resultado.hallazgos, [])
        self.assertEqual(len(resultado.exentos), 1)
        self.assertEqual(resultado.exentos[0].patron, "nombre_rafael")

    def test_la_excepcion_es_por_patron_no_a_ciegas(self):
        """Una lista blanca que solo exime un patrón no debe eximir los demás en la misma ruta."""
        with ArbolTemporal() as arbol:
            arbol.escribir("fixtures/sucio.txt", "Rafael vive en /home/alguien\n")
            config = config_minima(lista_blanca=[
                {"ruta": "fixtures/*", "patron": "nombre_rafael", "motivo": "solo el nombre"}])
            resultado = purga.escanear_arbol(arbol.raiz, config)
        self.assertEqual([h.patron for h in resultado.hallazgos], ["home_absoluto"])
        self.assertEqual([h.patron for h in resultado.exentos], ["nombre_rafael"])


class Config(unittest.TestCase):
    def test_falta_una_clave_obligatoria_es_un_error_claro(self):
        with ArbolTemporal() as arbol:
            ruta = arbol.escribir("config.json", json.dumps({"patrones": []}))
            with self.assertRaises(SystemExit):
                purga.cargar_config(ruta)

    def test_la_config_de_fabrica_es_valida_y_tiene_las_claves(self):
        config = purga.cargar_config(purga.CONFIG_POR_DEFECTO)
        for clave in ("patrones", "marcas", "directorios_prohibidos", "lista_blanca"):
            self.assertIn(clave, config)
        self.assertTrue(config["marcas"], "la lista de marcas existe para poder editarse, "
                                          "pero además tiene que traer algo de fábrica")

    def test_la_config_de_fabrica_no_se_queja_de_si_misma(self):
        """El propio archivo de config nombra a Rafael y a las marcas dentro de sus motivos y
        ejemplos: por eso está en su propia lista blanca. Si alguien la borra, esta prueba
        avisa antes de que la herramienta se reporte a sí misma como hallazgo.

        Se copia a un árbol temporal en vez de escanear el repo real: la ruta relativa
        (`herramientas/purga_config.json`) tiene que ser la misma que ve un escaneo desde la
        raíz del repo, que es como está escrita la lista blanca."""
        config = purga.cargar_config(purga.CONFIG_POR_DEFECTO)
        with ArbolTemporal() as arbol:
            arbol.escribir("herramientas/purga_config.json",
                           purga.CONFIG_POR_DEFECTO.read_text(encoding="utf-8"))
            resultado = purga.escanear_arbol(arbol.raiz, config)
        propios = [h for h in resultado.hallazgos if h.archivo == "herramientas/purga_config.json"]
        self.assertEqual(propios, [])


class CLI(unittest.TestCase):
    def test_codigo_de_salida_1_con_hallazgos_y_0_sin_ellos(self):
        with ArbolTemporal() as arbol:
            config = arbol.raiz.parent / "config.json"
            config.write_text(json.dumps(config_minima()), encoding="utf-8")

            sucio = arbol.raiz / "sucio"
            sucio.mkdir()
            (sucio / "nota.md").write_text("Rafael\n", encoding="utf-8")
            self.assertEqual(purga.main(["--raiz", str(sucio), "--config", str(config)]), 1)

            limpio = arbol.raiz / "limpio"
            limpio.mkdir()
            (limpio / "nota.md").write_text("nada que ver\n", encoding="utf-8")
            self.assertEqual(purga.main(["--raiz", str(limpio), "--config", str(config)]), 0)


class Historial(unittest.TestCase):
    def test_encuentra_un_secreto_en_un_commit_viejo_sin_repetirlo(self):
        token = "secret_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V"
        with ArbolTemporal() as arbol:
            repo = arbol.raiz
            self._git(repo, "init", "-q")
            self._git(repo, "config", "user.email", "prueba@example.com")
            self._git(repo, "config", "user.name", "Prueba")
            (repo / "config.json").write_text(f'{{"token": "{token}"}}\n', encoding="utf-8")
            self._git(repo, "add", "config.json")
            self._git(repo, "commit", "-q", "-m", "commit con el secreto, luego revertido")
            (repo / "config.json").write_text('{"token": "borrado"}\n', encoding="utf-8")
            self._git(repo, "add", "config.json")
            self._git(repo, "commit", "-q", "-m", "se borra, pero sigue en el historial")

            hallazgos = purga.escanear_historial(repo, config_minima())

        # Aparece en el commit que lo agrega y en el que lo borra —el diff del segundo commit
        # muestra la línea vieja como contexto de la resta—, y eso es lo correcto: los dos
        # commits tienen el secreto en su patch, aunque el archivo de hoy ya esté limpio.
        self.assertEqual(len(hallazgos), 2)
        self.assertTrue(all(h["patron"] == "token_notion" for h in hallazgos))
        self.assertTrue(all(h["categoria"] == "secreto" for h in hallazgos))
        self.assertEqual(len({h["commit"] for h in hallazgos}), 2, "cada commit una sola vez")
        for hallazgo in hallazgos:
            self.assertNotIn("valor", hallazgo)
            self.assertNotIn(token, json.dumps(hallazgo))

    def test_sin_secretos_en_el_historial_devuelve_vacio(self):
        with ArbolTemporal() as arbol:
            repo = arbol.raiz
            self._git(repo, "init", "-q")
            self._git(repo, "config", "user.email", "prueba@example.com")
            self._git(repo, "config", "user.name", "Prueba")
            (repo / "a.txt").write_text("nada de nada\n", encoding="utf-8")
            self._git(repo, "add", "a.txt")
            self._git(repo, "commit", "-q", "-m", "commit limpio")

            self.assertEqual(purga.escanear_historial(repo, config_minima()), [])

    @staticmethod
    def _git(repo, *args):
        subprocess.run(["git", "-C", str(repo), *args], check=True,
                       capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
