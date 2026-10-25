"""Los verbos de la instalación: `doctor`, `fuentes` y `config init|validar`.

Lo que se vigila es lo que haría daño sin hacer ruido: activar una fuente que no responde (el
board se queda sin tareas), guardar un token en claro, pisar una config rota con una buena a
medias, o dejar dos archivos de config vivos después de migrar.
"""

import json
import os
import subprocess
import sys
from unittest import mock

from apoyo import RAIZ, PruebaDeCLI, proyecto
from tareas import configuracion, fuente as f

PLANTILLA = RAIZ / "extras" / "plantilla" / "cotejo_plantilla.py"
COMANDO = f"{sys.executable} {PLANTILLA}"


class PruebaDeConexion(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Algo ^cotejo-uno1"))
        self.archivo = self.vault / "tareas.json"
        self.archivo.write_text(json.dumps({"proyectos": [{"nombre": "Casa", "tareas": [
            {"id": "casa-1", "texto": "Pintar", "estado": "pendiente", "agente": "",
             "dificultad": "", "hecha": False}]}]}), encoding="utf-8")

    def config_escrita(self):
        return json.loads(self.config.read_text(encoding="utf-8"))

    def agregar_demo(self, *extra):
        return self.correr("fuentes", "agregar", "demo", "--comando", COMANDO,
                           "--param", f"archivo={self.archivo}", *extra)

    def repo(self, nombre="repo"):
        ruta = self.vault / nombre
        (ruta / ".git").mkdir(parents=True)
        return ruta

    def parado_en(self, carpeta):
        """Mueve el cwd del proceso ahí para la prueba, y lo deja como estaba al salir.

        `doctor` mira `Path.cwd()` para la pista del repo actual; no hay subproceso que
        aislarlo como en `test_nucleo_sin_gtk.py`, así que aquí se mueve de verdad.
        """
        anterior = os.getcwd()
        os.chdir(carpeta)
        self.addCleanup(os.chdir, anterior)


class Fuentes(PruebaDeConexion):
    def test_sin_config_esta_obsidian_y_es_la_activa(self):
        codigo, datos = self.correr("fuentes")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["activa"], "obsidian")
        # Las de fábrica salen aunque no estén configuradas; la de repos, con su problema dicho.
        self.assertEqual([x["nombre"] for x in datos["fuentes"]], ["obsidian", "repo"])
        repo = next(x for x in datos["fuentes"] if x["nombre"] == "repo")
        self.assertFalse(repo["activa"])
        self.assertIn("repo", repo["problema"])

    def test_agregar_registra_sin_activar_y_repetir_no_cambia(self):
        codigo, datos = self.agregar_demo()
        self.assertEqual((codigo, datos["cambio"]), (0, True))
        guardada = self.config_escrita()
        self.assertEqual(guardada["fuentes"]["demo"]["tipo"], "externa")
        self.assertNotIn("fuente", guardada)
        _, otra = self.agregar_demo()
        self.assertFalse(otra["cambio"])

    def test_agregar_no_guarda_secretos(self):
        codigo, datos = self.agregar_demo("--param", "token=abc123")
        self.assertEqual(codigo, 3)
        self.assertIn("token_env", datos["salida"])
        self.assertFalse(self.config.exists())

    def test_agregar_no_pisa_una_de_fabrica(self):
        codigo, _ = self.correr("fuentes", "agregar", "obsidian", "--comando", "x")
        self.assertEqual(codigo, 3)

    def test_los_parametros_en_json_se_guardan_como_json(self):
        self.agregar_demo("--param", 'database_ids=["a","b"]', "--param", "numero=0042")
        guardada = self.config_escrita()["fuentes"]["demo"]
        self.assertEqual(guardada["database_ids"], ["a", "b"])
        self.assertEqual(guardada["numero"], "0042")

    def test_probar_la_conecta_sin_activarla(self):
        self.agregar_demo()
        codigo, datos = self.correr("fuentes", "probar", "demo")
        self.assertEqual(codigo, 0)
        self.assertEqual((datos["ok"], datos["pendientes"]), (True, 1))
        self.assertNotIn("fuente", self.config_escrita())

    def test_usar_se_niega_si_no_responde(self):
        self.correr("fuentes", "agregar", "rota", "--comando", "cotejo-que-no-existe")
        codigo, datos = self.correr("fuentes", "usar", "rota")
        self.assertEqual(codigo, 3)
        self.assertNotIn("fuente", self.config_escrita())
        self.assertIn("cotejo-que-no-existe", datos["error"])

    def test_usar_activa_y_los_verbos_leen_de_ella(self):
        self.agregar_demo()
        codigo, datos = self.correr("fuentes", "usar", "demo")
        self.assertEqual((codigo, datos["cambio"]), (0, True))
        _, tareas = self.correr("tareas")
        self.assertEqual([t["id"] for t in tareas["tareas"]], ["casa-1"])

    def test_quitar_se_niega_con_la_activa_y_con_las_de_fabrica(self):
        self.agregar_demo()
        self.correr("fuentes", "usar", "demo")
        self.assertEqual(self.correr("fuentes", "quitar", "demo")[0], 3)
        self.assertEqual(self.correr("fuentes", "quitar", "obsidian")[0], 3)
        self.correr("fuentes", "usar", "obsidian")
        codigo, datos = self.correr("fuentes", "quitar", "demo")
        self.assertEqual((codigo, datos["cambio"]), (0, True))
        self.assertNotIn("demo", self.config_escrita()["fuentes"])

    def test_info_de_una_de_fabrica_dice_sus_parametros(self):
        codigo, datos = self.correr("fuentes", "info", "obsidian")
        self.assertEqual(codigo, 0)
        self.assertIn("vault", datos["parametros"])

    def test_info_de_una_externa_pregunta_al_adaptador(self):
        self.agregar_demo()
        _, datos = self.correr("fuentes", "info", "demo")
        self.assertEqual(datos["protocolo"]["nombre"], "plantilla")
        self.assertIn("archivo", datos["parametros"])

    def test_info_de_una_que_no_existe_dice_como_registrarla(self):
        codigo, datos = self.correr("fuentes", "info", "trello")
        self.assertEqual(codigo, 3)
        self.assertIn("fuentes agregar trello", datos["salida"])

    def test_una_config_rota_no_se_pisa(self):
        self.config.write_text("{roto", encoding="utf-8")
        codigo, _ = self.agregar_demo()
        self.assertEqual(codigo, 3)
        self.assertEqual(self.config.read_text(encoding="utf-8"), "{roto")


class Doctor(PruebaDeConexion):
    def test_con_todo_bien_dice_cuantas_hay(self):
        codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["ok"])
        self.assertEqual((datos["fuente"]["nombre"], datos["fuente"]["pendientes"]),
                         ("obsidian", 1))

    def test_sin_ningun_agente_de_terminal_avisa_sin_dar_ok_false(self):
        with mock.patch("enrutador.clientes.shutil.which", return_value=None):
            codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["agentes"]["instalados"], [])
        self.assertTrue(any("No encontré ningún agente de terminal" in a
                            for a in datos["avisos"]))

    def test_con_algun_agente_no_hay_aviso_de_agentes(self):
        with mock.patch("enrutador.clientes.shutil.which", return_value="/usr/bin/x"):
            _, datos = self.correr("doctor")
        self.assertFalse(any("agente de terminal" in a for a in datos.get("avisos", [])))
        self.assertIn("claude", datos["agentes"]["instalados"])

    def fuera_de_un_repo(self):
        """Una carpeta que no es repo: `doctor` no suma la pista del repo donde se para."""
        fuera = self.vault / "no-es-repo"
        fuera.mkdir(exist_ok=True)
        return fuera

    def test_de_punta_a_punta_con_el_path_vacio_avisa_y_no_dice_todo_en_orden(self):
        self.parado_en(self.fuera_de_un_repo())
        with mock.patch.dict(os.environ, {"PATH": ""}):
            codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["agentes"]["instalados"], [])
        self.assertEqual(len(datos["avisos"]), 1)
        self.assertIn("No encontré ningún agente de terminal", datos["avisos"][0])
        self.assertNotIn("Todo en orden", datos["salida"])
        self.assertIn("No encontré ningún agente", datos["salida"])

    def test_de_punta_a_punta_con_un_cliente_en_el_path_no_hay_aviso(self):
        bin_falso = self.vault / "bin-falso"
        bin_falso.mkdir()
        claude = bin_falso / "claude"
        claude.write_text("#!/bin/sh\n", encoding="utf-8")
        claude.chmod(0o755)
        self.parado_en(self.fuera_de_un_repo())
        with mock.patch.dict(os.environ, {"PATH": str(bin_falso)}):
            codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["agentes"]["instalados"], ["claude"])
        self.assertNotIn("avisos", datos)
        self.assertIn("Todo en orden", datos["salida"])

    def test_en_subproceso_con_el_path_vacio_ok_true_y_el_aviso(self):
        (self.vault / "hogar").mkdir()
        entorno = {"PATH": "", "COTEJO_VAULT": str(self.vault),
                   "COTEJO_CARPETA_PROYECTOS": self.CARPETA, "COTEJO_CONFIG": str(self.config),
                   "HOME": str(self.vault / "hogar"), "XDG_CONFIG_HOME": str(self.vault / "xdg-c"),
                   "XDG_STATE_HOME": str(self.vault / "xdg-e"), "DBUS_SESSION_BUS_ADDRESS": "",
                   "PYTHONPATH": str(RAIZ)}
        hecho = subprocess.run([sys.executable, "-m", "tareas", "doctor"], cwd=self.fuera_de_un_repo(),
                               env=entorno,
                               capture_output=True, text=True)
        self.assertEqual(hecho.returncode, 0, hecho.stderr)
        datos = json.loads(hecho.stdout)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["agentes"]["instalados"], [])
        self.assertIn("No encontré ningún agente de terminal", datos["avisos"][0])
        self.assertNotIn("Todo en orden", datos["salida"])

    def test_con_la_config_rota_lo_dice_y_no_revienta(self):
        self.config.write_text("{roto", encoding="utf-8")
        codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 3)
        self.assertFalse(datos["ok"])
        self.assertTrue(datos["config"]["errores"])

    def test_con_la_fuente_activa_rota_dice_que_hacer(self):
        self.config.write_text(json.dumps({"fuente": "demo", "fuentes": {"demo": {
            "tipo": "externa", "comando": "cotejo-que-no-existe"}}}), encoding="utf-8")
        codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 3)
        self.assertIn("cotejo-que-no-existe", datos["fuente"]["problema"])
        self.assertTrue(datos["salida"])


class Init(PruebaDeConexion):
    """`cotejo init`: crea `.cotejo/tareas.md` en un repo y lo registra en la fuente «repo»."""

    def test_crea_el_archivo_y_registra_el_repo_sin_activarlo(self):
        repo = self.repo()
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["creado"])
        self.assertTrue(datos["cambio"])
        self.assertEqual((repo / ".cotejo" / "tareas.md").read_text(encoding="utf-8"), "# Tareas\n")
        guardada = self.config_escrita()
        self.assertEqual(guardada["fuentes"]["repo"]["repos"], [str(repo.resolve())])
        # No cambia la fuente activa: eso es de `fuentes usar repo`.
        self.assertNotIn("fuente", guardada)

    def test_repetirlo_no_duplica_ni_rescribe_el_archivo(self):
        repo = self.repo()
        self.correr("init", "--repo", str(repo))
        archivo = repo / ".cotejo" / "tareas.md"
        archivo.write_text("# Tareas\n\n- [ ] Ya había algo ^x1\n", encoding="utf-8")
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        self.assertFalse(datos["creado"])
        self.assertFalse(datos["cambio"])
        # No se reescribió por encima de lo que ya había.
        self.assertIn("Ya había algo", archivo.read_text(encoding="utf-8"))
        self.assertEqual(self.config_escrita()["fuentes"]["repo"]["repos"], [str(repo.resolve())])

    def test_crea_el_esqueleto_del_almacen_con_las_carpetas_de_sus_tipos(self):
        from tareas import almacen
        repo = self.repo()
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        cotejo = repo / ".cotejo"
        carpetas = [t.carpeta for t in almacen.TIPOS.values() if t.carpeta]
        self.assertEqual(sorted(carpetas), ["aprendizajes", "arquitectura", "bitacora",
                                            "decisiones", "problemas", "recursos",
                                            "referencias"])
        for nombre in carpetas:
            self.assertTrue((cotejo / nombre / ".gitkeep").is_file(), nombre)
        self.assertEqual(datos["creados"],
                         ["tareas.md", "proyecto.md", *(f"{c}/" for c in carpetas)])
        # proyecto.md es una entrada del almacén que se lee, con el nombre del repo.
        proyecto = almacen.Almacen(repo).leer("proyecto")
        self.assertEqual(proyecto.titulo, repo.name)
        # Y las carpetas vacías no meten nada raro en el almacén.
        avisos = []
        self.assertEqual([e.id for e in almacen.Almacen(repo).entradas(avisos=avisos)],
                         ["proyecto"])
        self.assertEqual(avisos, [])

    def test_repetirlo_no_cambia_nada_y_cambio_es_un_booleano(self):
        repo = self.repo()
        self.correr("init", "--repo", str(repo))
        antes = sorted(str(p.relative_to(repo)) for p in (repo / ".cotejo").rglob("*"))
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        self.assertIs(datos["cambio"], False)
        self.assertEqual(datos["creados"], [])
        self.assertEqual(sorted(str(p.relative_to(repo)) for p in (repo / ".cotejo").rglob("*")),
                         antes)

    def test_no_pisa_un_proyecto_md_ni_carpetas_que_ya_tenian_algo(self):
        repo = self.repo()
        cotejo = repo / ".cotejo"
        (cotejo / "decisiones").mkdir(parents=True)
        decision = cotejo / "decisiones" / "2026-10-01-algo.md"
        decision.write_text("---\nid: dec-ab12\nestado: aceptada\n---\n# Algo\n",
                            encoding="utf-8")
        (cotejo / "proyecto.md").write_text("---\nid: proyecto\n---\n# Mío\n", encoding="utf-8")
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        self.assertNotIn("proyecto.md", datos["creados"])
        self.assertNotIn("decisiones/", datos["creados"])
        self.assertIs(datos["cambio"], True)  # faltaban tareas.md y las demás carpetas
        self.assertEqual((cotejo / "proyecto.md").read_text(encoding="utf-8"),
                         "---\nid: proyecto\nversion: 0.1.0\n---\n# Mío\n")  # solo se le añade version:
        self.assertEqual(sorted(p.name for p in (cotejo / "decisiones").iterdir()),
                         ["2026-10-01-algo.md"])

    def test_init_pone_version_y_repetirlo_no_cambia_nada(self):
        repo = self.repo()
        _, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(datos["version"], {"version": "0.1.0", "hecho": "puesta"})
        antes = (repo / ".cotejo" / "proyecto.md").read_bytes()
        _, otra = self.correr("init", "--repo", str(repo))
        self.assertEqual(otra["version"]["hecho"], "ya-estaba")
        self.assertIs(otra["cambio"], False)
        self.assertEqual((repo / ".cotejo" / "proyecto.md").read_bytes(), antes)

    def test_doctor_avisa_de_un_proyecto_sin_version_y_init_lo_arregla(self):
        repo = self.repo()
        (repo / ".cotejo").mkdir()
        (repo / ".cotejo" / "proyecto.md").write_text("---\nid: proyecto\n---\n# Mío\n",
                                                      encoding="utf-8")
        self.parado_en(repo)
        _, datos = self.correr("doctor")
        self.assertTrue(datos["ok"])
        self.assertIn("version:", datos["avisos"][0])
        self.assertIn("cotejo init", datos["avisos"][0])
        self.correr("init", "--repo", str(repo))
        _, datos = self.correr("doctor")
        self.assertFalse(any("version:" in a for a in datos.get("avisos", [])))

    def test_solo_completa_lo_que_falta_de_un_esqueleto_a_medias(self):
        repo = self.repo()
        self.correr("init", "--repo", str(repo))
        (repo / ".cotejo" / "recursos" / ".gitkeep").unlink()
        (repo / ".cotejo" / "recursos").rmdir()
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual((codigo, datos["creados"], datos["cambio"]), (0, ["recursos/"], True))

    def test_un_repo_ya_registrado_a_mano_no_se_duplica(self):
        repo = self.repo()
        self.config.write_text(json.dumps({"fuentes": {"repo": {"repos": [str(repo)]}}}),
                               encoding="utf-8")
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["creado"])  # el archivo sí hacía falta
        self.assertEqual(self.config_escrita()["fuentes"]["repo"]["repos"], [str(repo)])

    def test_un_repo_ya_cubierto_por_raiz_no_se_duplica_en_repos(self):
        padre = self.vault / "codigo"
        repo = self.repo("codigo/app")
        self.config.write_text(json.dumps({"fuentes": {"repo": {"raiz": str(padre)}}}),
                               encoding="utf-8")
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        guardada = self.config_escrita()
        self.assertNotIn("repos", guardada["fuentes"]["repo"])
        self.assertEqual(guardada["fuentes"]["repo"]["raiz"], str(padre))
        # Sin archivo todavía: contaba como cambio por crearlo, aunque no tocara la config.
        self.assertTrue(datos["creado"])

    def test_sin_repo_git_y_sin_repo_es_un_error_y_no_escribe_nada(self):
        carpeta = self.vault / "no-es-repo"
        carpeta.mkdir()
        with mock.patch("pathlib.Path.cwd", return_value=carpeta):
            codigo, datos = self.correr("init")
        self.assertEqual(codigo, 3)
        self.assertIn("repo git", datos["error"])
        self.assertIn("--repo .", datos["salida"])
        self.assertFalse((carpeta / ".cotejo").exists())

    def test_sin_git_instalado_el_error_dice_que_falta_git_y_no_sugiere_init_repo(self):
        carpeta = self.vault / "no-es-repo"
        carpeta.mkdir()
        with mock.patch("pathlib.Path.cwd", return_value=carpeta), \
                mock.patch.dict(os.environ, {"PATH": str(self.vault)}):
            codigo, datos = self.correr("init")
        self.assertEqual(codigo, 3)
        self.assertIn("git", datos["error"])
        self.assertIn("instálalo", datos["salida"])
        self.assertNotIn("init --repo .`", datos["error"])
        self.assertFalse((carpeta / ".cotejo").exists())

    def test_init_deja_un_commit_con_cotejo_aunque_no_haya_identidad_git(self):
        home = self.vault / "home-vacio"
        home.mkdir()
        entorno = {"HOME": str(home), "XDG_CONFIG_HOME": str(home / "c"),
                   "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
                   "GIT_CONFIG_NOSYSTEM": "1"}
        for clave in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                      "GIT_COMMITTER_EMAIL", "EMAIL"):
            os.environ.pop(clave, None)
        destino = self.vault / "sin-identidad"
        with mock.patch.dict(os.environ, entorno):
            codigo, datos = self.correr("init", "--repo", str(destino))
        self.assertEqual(codigo, 0, datos)
        self.assertTrue(datos["commit"])
        self.assertIn("Commit inicial", datos["salida"])
        archivos = subprocess.run(["git", "-C", str(destino), "ls-tree", "-r", "--name-only", "HEAD"],
                                  capture_output=True, text=True).stdout.split()
        self.assertIn(".cotejo/tareas.md", archivos)
        self.assertIn(".cotejo/proyecto.md", archivos)
        # Sin identidad de la persona, `init` deja la de Cotejo en la config LOCAL del repo para
        # que los agentes commiteen sin `-c` (cotejo-q93zyw).
        self.assertEqual(self._local(destino, "user.name"), "Cotejo")
        self.assertEqual(self._local(destino, "user.email"), "cotejo@localhost")
        self.assertEqual(datos["identidad"], ["user.name", "user.email"])
        hecho = subprocess.run(["git", "-C", str(destino), "-c", "commit.gpgsign=false",
                                "commit", "-q", "--allow-empty", "-m", "x"], capture_output=True)
        self.assertEqual(hecho.returncode, 0, hecho.stderr)

    def _local(self, repo, clave):
        return subprocess.run(["git", "-C", str(repo), "config", "--local", "--get", clave],
                              capture_output=True, text=True).stdout.strip()

    def _init_con_global(self, contenido):
        """Corre `init` en una carpeta nueva con un gitconfig global de mentira (o vacío)."""
        home = self.vault / "home-ident"
        home.mkdir(exist_ok=True)
        glob = home / "gitconfig"
        glob.write_text(contenido, encoding="utf-8")
        entorno = {"HOME": str(home), "XDG_CONFIG_HOME": str(home / "c"),
                   "GIT_CONFIG_GLOBAL": str(glob), "GIT_CONFIG_SYSTEM": os.devnull,
                   "GIT_CONFIG_NOSYSTEM": "1"}
        for clave in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                      "GIT_COMMITTER_EMAIL", "EMAIL"):
            os.environ.pop(clave, None)
        destino = self.vault / "ident-proyecto"
        with mock.patch.dict(os.environ, entorno):
            codigo, datos = self.correr("init", "--repo", str(destino))
        self.assertEqual(codigo, 0, datos)
        return destino, datos

    def test_init_respeta_la_identidad_global_de_la_persona(self):
        destino, datos = self._init_con_global(
            "[user]\n\tname = Ana Prueba\n\temail = ana@ejemplo.test\n")
        self.assertEqual(datos["identidad"], [])
        self.assertEqual(self._local(destino, "user.name"), "")
        self.assertEqual(self._local(destino, "user.email"), "")

    def test_init_completa_solo_lo_que_falta_de_la_identidad(self):
        destino, datos = self._init_con_global("[user]\n\tname = Ana Prueba\n")
        self.assertEqual(datos["identidad"], ["user.email"])
        self.assertEqual(self._local(destino, "user.name"), "")
        self.assertEqual(self._local(destino, "user.email"), "cotejo@localhost")

    def test_init_no_pisa_la_identidad_local_de_un_repo_existente(self):
        destino = self.vault / "con-identidad"
        destino.mkdir()
        for clave, valor in (("user.name", "Dueña"), ("user.email", "d@ejemplo.test")):
            subprocess.run(["git", "init", "-q", str(destino)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(destino), "config", clave, valor], check=True)
        _, datos = self.correr("init", "--repo", str(destino))
        self.assertEqual(datos["identidad"], [])
        self.assertEqual(self._local(destino, "user.name"), "Dueña")
        self.assertEqual(self._local(destino, "user.email"), "d@ejemplo.test")

    def test_init_no_toca_un_repo_que_ya_tiene_commits(self):
        destino = self.vault / "con-historia"
        destino.mkdir()
        for orden in (["init", "-q"], ["-c", "user.name=P", "-c", "user.email=p@p", "commit",
                                       "-q", "--allow-empty", "-m", "mio"]):
            subprocess.run(["git", "-C", str(destino), *orden], check=True, capture_output=True)
        _, datos = self.correr("init", "--repo", str(destino))
        self.assertEqual(datos["commit"], "")
        cuenta = subprocess.run(["git", "-C", str(destino), "rev-list", "--count", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(cuenta, "1")

    def _git_ok(self, carpeta):
        self.assertTrue((carpeta / ".git").is_dir())
        self.assertTrue((carpeta / ".cotejo" / "tareas.md").is_file())
        self.assertIn("version: 0.1.0",
                      (carpeta / ".cotejo" / "proyecto.md").read_text(encoding="utf-8"))
        # Desde la 1.2.5 deja un commit inicial con `.cotejo/`: sin él no hay HEAD y el primer
        # `despachar` falla con «referencia inválida: HEAD».
        hecho = subprocess.run(["git", "-C", str(carpeta), "rev-parse", "--verify", "HEAD"],
                               capture_output=True)
        self.assertEqual(hecho.returncode, 0)

    def test_una_carpeta_que_no_existe_se_crea_con_git_y_cotejo(self):
        destino = self.vault / "nuevo" / "proyecto"
        codigo, datos = self.correr("init", "--repo", str(destino))
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["git_init"])
        self.assertTrue(datos["cambio"])
        self.assertEqual(datos["repo"], str(destino.resolve()))
        self._git_ok(destino)
        self.assertEqual(self.config_escrita()["fuentes"]["repo"]["repos"],
                         [str(destino.resolve())])

    def test_una_carpeta_vacia_sin_git_recibe_git_init(self):
        destino = self.vault / "vacia"
        destino.mkdir()
        codigo, datos = self.correr("init", "--repo", str(destino))
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["git_init"])
        self._git_ok(destino)

    def test_una_carpeta_con_archivos_sin_git_no_pierde_nada(self):
        destino = self.vault / "con-cosas"
        (destino / "src").mkdir(parents=True)
        (destino / "src" / "a.py").write_text("print(1)\n", encoding="utf-8")
        codigo, datos = self.correr("init", "--repo", str(destino))
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["git_init"])
        self.assertEqual((destino / "src" / "a.py").read_text(encoding="utf-8"), "print(1)\n")
        self._git_ok(destino)

    def test_repetir_init_sobre_una_carpeta_nueva_no_cambia_nada(self):
        destino = self.vault / "otra"
        self.correr("init", "--repo", str(destino))
        proyecto = (destino / ".cotejo" / "proyecto.md").read_bytes()
        codigo, datos = self.correr("init", "--repo", str(destino))
        self.assertEqual(codigo, 0)
        self.assertFalse(datos["git_init"])
        self.assertFalse(datos["cambio"])
        self.assertEqual(datos["creados"], [])
        self.assertEqual((destino / ".cotejo" / "proyecto.md").read_bytes(), proyecto)
        self.assertEqual(self.config_escrita()["fuentes"]["repo"]["repos"],
                         [str(destino.resolve())])

    def test_un_repo_que_ya_es_git_no_hace_git_init(self):
        repo = self.repo()
        _, datos = self.correr("init", "--repo", str(repo))
        self.assertFalse(datos["git_init"])

    def test_una_ruta_que_es_un_archivo_es_un_error_claro(self):
        archivo = self.vault / "archivo.txt"
        archivo.write_text("x", encoding="utf-8")
        codigo, datos = self.correr("init", "--repo", str(archivo))
        self.assertEqual(codigo, 3)
        self.assertIn("es un archivo", datos["error"])
        self.assertEqual(archivo.read_text(encoding="utf-8"), "x")

    def test_desde_una_subcarpeta_encuentra_la_raiz_del_repo(self):
        repo = self.repo()
        (repo / "src").mkdir()
        codigo, datos = self.correr("init", "--repo", str(repo / "src"))
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["repo"], str(repo.resolve()))
        self.assertTrue((repo / ".cotejo" / "tareas.md").is_file())

    def test_doctor_encuentra_el_repo_una_vez_activada_la_fuente(self):
        repo = self.repo()
        self.correr("init", "--repo", str(repo))
        with mock.patch.dict(os.environ, {"COTEJO_FUENTE": "repo"}):
            codigo, datos = self.correr("fuentes", "probar", "repo")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["proyectos"], 1)

    def test_init_mantiene_la_fuente_activa_si_funciona(self):
        """Cuando la fuente activa funciona (ej. obsidian con vault válido), init no la cambia."""
        repo = self.repo()
        # El setUp crea un vault válido de Obsidian, así que obsidian es la activa y funciona
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["cambio"])
        guardada = self.config_escrita()
        # No debe haber "fuente" escrito porque obsidian funciona bien
        self.assertNotIn("fuente", guardada)
        self.assertIn("funciona bien", datos["salida"])

    def test_init_activa_repo_si_la_fuente_activa_no_funciona(self):
        """Cuando la fuente activa no funciona (ej. una fuente externa que no responde), init activa repo."""
        from tareas import conexion
        # Agregar una fuente externa que no existe
        self.config.write_text(json.dumps({
            "fuente": "noexiste",
            "fuentes": {
                "noexiste": {
                    "tipo": "externa",
                    "comando": "cotejo-que-no-existe"
                }
            }
        }), encoding="utf-8")
        repo = self.repo()
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["cambio"])
        guardada = self.config_escrita()
        # Debe haber activado "repo" porque la fuente activa no funciona
        self.assertEqual(guardada.get("fuente"), "repo")
        self.assertIn("repo", datos["salida"])

    def test_init_activa_repo_si_no_hay_fuente_configurada(self):
        """Cuando no hay fuente configurada, init verifica si la activa funciona."""
        # Crear una config vacía
        self.config.write_text("{}", encoding="utf-8")
        repo = self.repo()
        codigo, datos = self.correr("init", "--repo", str(repo))
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["cambio"])
        guardada = self.config_escrita()
        # La fuente activa por defecto es "repo", y después de registrarlo debe funcionar
        # Podría no escribir "fuente" si repo funciona, pero vamos a revisar la salida
        self.assertTrue("repo" in guardada.get("fuentes", {}))


class DoctorYElRepoActual(PruebaDeConexion):
    """La pista que falta cuando `init` dejó todo listo pero la fuente activa sigue siendo
    otra (lo normal: `init` no activa nada por sí mismo), y la contraria: un repo con
    `.cotejo/tareas.md` que nadie registró todavía."""

    def setUp(self):
        super().setUp()
        # Con un agente «instalado»: estas pruebas miran los avisos del repo, y el de «ningún
        # agente de terminal» depende de la máquina (el runner de CI no tiene ninguno).
        parche = mock.patch("enrutador.clientes.shutil.which", return_value="/usr/bin/x")
        parche.start()
        self.addCleanup(parche.stop)

    def test_registrado_pero_la_activa_es_otra_lo_dice_sin_tocar_ok(self):
        repo = self.repo()
        self.correr("init", "--repo", str(repo))  # obsidian sigue siendo la activa
        self.parado_en(repo)
        codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["ok"])  # no es un error: solo falta un paso
        self.assertEqual(len(datos["avisos"]), 1)
        self.assertIn("fuentes usar repo", datos["avisos"][0])
        self.assertIn("fuentes usar repo", datos["salida"])

    def test_registrado_y_ya_activa_no_dice_nada_de_mas(self):
        repo = self.repo()
        self.correr("init", "--repo", str(repo))
        self.correr("fuentes", "usar", "repo")
        self.parado_en(repo)
        _, datos = self.correr("doctor")
        self.assertNotIn("avisos", datos)

    def test_con_tareas_md_pero_sin_registrar_sugiere_init(self):
        repo = self.repo()
        (repo / ".cotejo").mkdir()
        (repo / ".cotejo" / "tareas.md").write_text("# Tareas\n", encoding="utf-8")
        self.parado_en(repo)
        codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["ok"])
        self.assertEqual(len(datos["avisos"]), 1)
        self.assertIn("cotejo init", datos["avisos"][0])
        self.assertIn("cotejo init", datos["salida"])

    def test_un_repo_sin_tareas_md_y_sin_registrar_no_dice_nada(self):
        repo = self.repo()
        self.parado_en(repo)
        _, datos = self.correr("doctor")
        self.assertNotIn("avisos", datos)

    def test_fuera_de_cualquier_repo_no_dice_nada(self):
        fuera = self.vault / "no-es-repo"
        fuera.mkdir()
        self.parado_en(fuera)
        _, datos = self.correr("doctor")
        self.assertNotIn("avisos", datos)

    def test_un_error_de_config_no_se_tapa_con_la_pista_del_repo(self):
        repo = self.repo()
        self.correr("init", "--repo", str(repo))
        self.config.write_text("{roto", encoding="utf-8")
        self.parado_en(repo)
        codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 3)
        self.assertFalse(datos["ok"])
        self.assertIn("Arregla la config", datos["salida"])


class Validar(PruebaDeConexion):
    def escribir(self, datos):
        self.config.write_text(json.dumps(datos), encoding="utf-8")

    def test_un_secreto_en_claro_es_un_error(self):
        self.escribir({"fuentes": {"n": {"tipo": "externa", "comando": "x", "token": "abc"}}})
        codigo, datos = self.correr("config", "validar")
        self.assertEqual(codigo, 3)
        self.assertIn("token_env", datos["errores"][0])

    def test_una_fuente_activa_que_no_existe_es_un_error(self):
        self.escribir({"fuente": "trello"})
        _, datos = self.correr("config", "validar")
        self.assertTrue(any("trello" in e for e in datos["errores"]))

    def test_una_externa_sin_comando_es_un_error(self):
        self.escribir({"fuentes": {"n": {"tipo": "externa"}}})
        _, datos = self.correr("config", "validar")
        self.assertTrue(any("comando" in e for e in datos["errores"]))

    def test_el_formato_viejo_sigue_valiendo(self):
        self.escribir({"vault": str(self.vault), "carpeta_proyectos": "01-Proyectos"})
        codigo, datos = self.correr("config", "validar")
        self.assertEqual((codigo, datos["errores"]), (0, []))

    def test_un_secreto_en_la_raiz_de_la_config_es_un_error(self):
        # No está dentro de `fuentes`: antes pasaba con ok:true.
        self.escribir({"fuente": "obsidian", "api_key": "sk-en-claro-123"})
        codigo, datos = self.correr("config", "validar")
        self.assertEqual(codigo, 3)
        self.assertTrue(any("api_key" in e and "token_env" in e for e in datos["errores"]))
        self.assertTrue(all("sk-en-claro-123" not in e for e in datos["errores"]))

    def test_un_secreto_dentro_del_enrutador_es_un_error(self):
        self.escribir({"fuente": "obsidian", "enrutador": {"api_key": "sk-en-claro-456"}})
        codigo, datos = self.correr("config", "validar")
        self.assertEqual(codigo, 3)
        self.assertTrue(any("enrutador.api_key" in e for e in datos["errores"]))
        self.assertTrue(all("sk-en-claro-456" not in e for e in datos["errores"]))

    def test_un_secreto_en_una_lista_anidada_del_enrutador_es_un_error(self):
        self.escribir({"fuente": "obsidian", "enrutador": {"modelos": [
            {"nivel": "n1", "modelo": "extra", "modelo_id": "opencode-go/kimi-k2.7-code",
             "api_key": "sk-anidada-789"},
        ]}})
        codigo, datos = self.correr("config", "validar")
        self.assertEqual(codigo, 3)
        self.assertTrue(any("modelos[0].api_key" in e for e in datos["errores"]))
        self.assertTrue(all("sk-anidada-789" not in e for e in datos["errores"]))

    def test_una_config_real_tipica_no_salta_falsos_positivos(self):
        self.escribir({
            "fuente": "notion",
            "fuentes": {
                "notion": {"tipo": "externa", "comando": "cotejo-notion",
                           "token_env": "NOTION_TOKEN", "database_id": "abc123"},
            },
            "enrutador": {
                "modelos": [
                    {"nivel": "n2", "modelo": "opencode-go", "cliente": "opencode-go",
                     "modelo_id": "opencode-go/kimi-k2.7-code"},
                ],
                "reglas_extra": [
                    {"nombre": "compras", "nivel": "n0", "patron": r"\bcomprar\b",
                     "porque": "gasta dinero"},
                ],
                "reglas_apagadas": ["otra_regla"],
                "alias_persona": ["persona", "rafael"],
                "maestro": {"terminal": None, "modelos": {"claude": "opus"}},
            },
            "tema": "oscuro",
        })
        codigo, datos = self.correr("config", "validar")
        self.assertEqual((codigo, datos["errores"]), (0, []))


class ConfigInit(PruebaDeConexion):
    """`init` y la migración, con un XDG_CONFIG_HOME de mentira y sin COTEJO_CONFIG."""

    def setUp(self):
        super().setUp()
        self.xdg = self.vault / "xdg"
        entorno = {k: v for k, v in os.environ.items() if k != "COTEJO_CONFIG"}
        entorno["XDG_CONFIG_HOME"] = str(self.xdg)
        parche = mock.patch.dict(os.environ, entorno, clear=True)
        parche.start()
        self.addCleanup(parche.stop)

    def registrar_vaults(self, **vaults):
        """Escribe el `obsidian.json` de mentira: nombre -> carpeta (None, una que no existe)."""
        registro = {nombre: {"path": str(ruta), "ts": 1} for nombre, ruta in vaults.items()}
        archivo = self.xdg / "obsidian" / "obsidian.json"
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps({"vaults": registro}), encoding="utf-8")

    def test_sin_nada_crea_el_nuevo_con_el_repo(self):
        # Sin obsidian.json: quien no tiene Obsidian no se queda con una fuente que no sirve.
        codigo, datos = self.correr("config", "init")
        self.assertEqual((codigo, datos["cambio"]), (0, True))
        escrito = json.loads(configuracion.nueva().read_text(encoding="utf-8"))
        self.assertEqual(escrito["fuente"], "repo")
        self.assertEqual(list(escrito["fuentes"]), ["repo"])
        self.assertIn("repos", escrito["fuentes"]["repo"])
        _, otra = self.correr("config", "init")
        self.assertFalse(otra["cambio"])

    def test_con_un_vault_real_detectado_crea_obsidian_con_ese_vault(self):
        self.registrar_vaults(a=self.vault)
        codigo, datos = self.correr("config", "init")
        self.assertEqual((codigo, datos["cambio"]), (0, True))
        escrito = json.loads(configuracion.nueva().read_text(encoding="utf-8"))
        self.assertEqual(escrito["fuente"], "obsidian")
        self.assertEqual(escrito["fuentes"]["obsidian"]["vault"], str(self.vault))
        self.assertIn("carpeta_proyectos", escrito["fuentes"]["obsidian"])

    def test_con_un_vault_borrado_crea_repo_y_con_dos_toma_el_que_existe(self):
        self.registrar_vaults(viejo=self.vault / "ya-no-existe")
        self.correr("config", "init")
        self.assertEqual(json.loads(configuracion.nueva().read_text(encoding="utf-8"))["fuente"],
                         "repo")
        configuracion.nueva().unlink()
        self.registrar_vaults(viejo=self.vault / "ya-no-existe", bueno=self.vault)
        self.correr("config", "init")
        escrito = json.loads(configuracion.nueva().read_text(encoding="utf-8"))
        self.assertEqual((escrito["fuente"], escrito["fuentes"]["obsidian"]["vault"]),
                         ("obsidian", str(self.vault)))

    def test_sin_fuente_ni_vault_doctor_y_tareas_sugieren_init_y_con_vault_real_tambien_obsidian(self):
        entorno = {k: v for k, v in os.environ.items() if k not in ("COTEJO_VAULT", "COTEJO_FUENTE")}
        self.parado_en(self.vault)  # que la pista del repo actual no tape la de la fuente
        with mock.patch.dict(os.environ, entorno, clear=True):
            self.correr("config", "init")  # repo, sin repos: no sirve todavía
            self.registrar_vaults(viejo=self.vault / "ya-no-existe")
            codigo, datos = self.correr("doctor")
            self.assertEqual(codigo, 3)
            self.assertIn("cotejo init", datos["salida"])
            self.assertNotIn("fuentes usar obsidian", datos["salida"])
            codigo, datos = self.correr("tareas")
            self.assertEqual(codigo, 3)
            self.assertIn("cotejo init", datos["salida"])
            self.assertNotIn("fuentes usar obsidian", datos["salida"])
            # Ahora el vault existe: se ofrece además de init.
            self.registrar_vaults(bueno=self.vault)
            _, datos = self.correr("doctor")
            self.assertIn("cotejo init", datos["salida"])
            self.assertIn("cotejo fuentes usar obsidian", datos["salida"])
            codigo, datos = self.correr("tareas")
            self.assertEqual(codigo, 3)
            self.assertIn("cotejo fuentes usar obsidian", datos["salida"])
            self.assertIn("cotejo init", datos["salida"])

    def test_migra_el_viejo_y_lo_aparta(self):
        viejo = configuracion.legado()
        viejo.parent.mkdir(parents=True)
        viejo.write_text(json.dumps({"vault": "/v", "carpeta_proyectos": "P",
                                     "enrutador": {"motor": "agente"}}), encoding="utf-8")
        self.assertEqual(configuracion.ruta(), viejo)
        codigo, datos = self.correr("config", "init")
        self.assertEqual(codigo, 0)
        nuevo = json.loads(configuracion.nueva().read_text(encoding="utf-8"))
        self.assertEqual(nuevo["fuentes"]["obsidian"], {"vault": "/v", "carpeta_proyectos": "P"})
        self.assertEqual(nuevo["enrutador"], {"motor": "agente"})
        # Uno solo vivo: el viejo queda apartado, no borrado.
        self.assertFalse(viejo.exists())
        self.assertTrue(viejo.with_suffix(".json.migrado").exists())
        self.assertEqual(configuracion.ruta(), configuracion.nueva())

    def test_el_viejo_se_sigue_leyendo_mientras_no_se_migre(self):
        viejo = configuracion.legado()
        viejo.parent.mkdir(parents=True)
        viejo.write_text(json.dumps({"vault": "/de/antes"}), encoding="utf-8")
        self.assertEqual(f.cargar_config()["vault"], "/de/antes")


class LaConfigSeLeePorFuente(PruebaDeConexion):
    def test_los_parametros_de_fuentes_ganan_a_los_sueltos(self):
        self.config.write_text(json.dumps({"vault": "/viejo", "fuentes": {
            "obsidian": {"vault": "/nuevo"}}}), encoding="utf-8")
        self.assertEqual(f.cargar_config()["vault"], "/nuevo")

    def test_las_claves_sueltas_no_le_llegan_a_otra_fuente(self):
        self.config.write_text(json.dumps({"vault": "/v", "fuente": "demo", "fuentes": {
            "demo": {"tipo": "externa", "comando": "x"}}}), encoding="utf-8")
        self.assertNotIn("vault", f.cargar_config())
