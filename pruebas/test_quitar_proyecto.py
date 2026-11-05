"""Quitar un proyecto solo cambia una configuracion falsa; nunca borra carpetas."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401
from tareas import fuente, proyectos
from tareas.fuentes.repo import Repo


class QuitarProyecto(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.config = self.raiz / "config.json"
        self.entorno = mock.patch.dict(os.environ, {
            "COTEJO_CONFIG": str(self.config),
            "COTEJO_CONFIG_VEDADA": "",
        })
        self.entorno.start()
        self.addCleanup(self.entorno.stop)
        os.environ.pop("COTEJO_REPOS", None)
        os.environ.pop("COTEJO_FUENTE", None)
        os.environ.pop("COTEJO_VAULT", None)

    def escribir(self, datos):
        self.config.write_text(json.dumps(datos), encoding="utf-8")

    def leer(self):
        return json.loads(self.config.read_text(encoding="utf-8"))

    def test_quita_un_repo_sin_tocar_su_carpeta(self):
        uno = self.raiz / "uno"
        dos = self.raiz / "dos"
        uno.mkdir()
        dos.mkdir()
        (uno / "dato.txt").write_text("sigue aqui", encoding="utf-8")
        self.escribir({"fuente": "repo", "tema": "claro", "fuentes": {"repo": {
            "repos": [str(uno), str(dos)], "raiz": ""}}})

        proyectos.quitar("uno", uno)

        self.assertEqual(self.leer()["fuentes"]["repo"]["repos"], [str(dos)])
        self.assertEqual((uno / "dato.txt").read_text(encoding="utf-8"), "sigue aqui")
        self.assertEqual(self.leer()["tema"], "claro")

    def test_quita_la_ruta_ausente_que_produce_el_aviso(self):
        perdida = self.raiz / "ya-no-esta"
        self.escribir({"fuente": "repo", "fuentes": {"repo": {
            "repos": [str(perdida)]}}})

        proyectos.quitar(carpeta=perdida)

        self.assertEqual(self.leer()["fuentes"]["repo"]["repos"], [])

    def test_quita_un_migrado_por_nombre_y_deja_los_demas(self):
        uno = self.raiz / "repo-uno"
        dos = self.raiz / "repo-dos"
        self.escribir({"fuente": "obsidian", "fuentes": {"obsidian": {
            "vault": "/vault", "migrados": {"Uno": str(uno), "Dos": str(dos)}}}})

        proyectos.quitar("uno", uno)

        params = self.leer()["fuentes"]["obsidian"]
        self.assertEqual(params["migrados"], {"Dos": str(dos)})
        self.assertEqual(params["ocultos"], ["uno"])
        self.assertEqual(params["vault"], "/vault")

    def test_no_finge_quitar_una_lista_dada_por_el_entorno(self):
        repo = self.raiz / "repo"
        self.escribir({"fuente": "repo", "fuentes": {"repo": {"repos": [str(repo)]}}})
        os.environ["COTEJO_REPOS"] = str(repo)

        with self.assertRaisesRegex(proyectos.ProyectoNoRegistrado, "COTEJO_REPOS"):
            proyectos.quitar("repo", repo)
        self.assertEqual(self.leer()["fuentes"]["repo"]["repos"], [str(repo)])

    def test_un_repo_descubierto_por_raiz_se_oculta_sin_borrar_su_carpeta(self):
        repo = self.raiz / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / ".cotejo").mkdir()
        (repo / ".cotejo" / "tareas.md").write_text("# Tareas\n", encoding="utf-8")
        self.escribir({"fuente": "repo", "fuentes": {"repo": {
            "repos": [], "raiz": str(self.raiz)}}})

        proyectos.quitar("repo", repo)

        params = self.leer()["fuentes"]["repo"]
        self.assertEqual(params["ocultos"], [str(repo)])
        self.assertTrue(repo.is_dir())
        self.assertEqual(Repo(params).escanear(), [])

    def test_un_repo_explicito_dentro_de_raiz_no_reaparece_por_la_raiz(self):
        repo = self.raiz / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / ".cotejo").mkdir()
        (repo / ".cotejo" / "tareas.md").write_text("# Tareas\n", encoding="utf-8")
        self.escribir({"fuente": "repo", "fuentes": {"repo": {
            "repos": [str(repo)], "raiz": str(self.raiz)}}})

        proyectos.quitar("repo", repo)

        params = self.leer()["fuentes"]["repo"]
        self.assertEqual(params["repos"], [])
        self.assertEqual(params["ocultos"], [str(repo)])
        self.assertEqual(Repo(params).escanear(), [])

    def test_un_migrado_no_reaparece_desde_su_nota_de_obsidian(self):
        vault = self.raiz / "vault"
        proyectos_vault = vault / "01-Proyectos"
        proyectos_vault.mkdir(parents=True)
        (proyectos_vault / "Uno.md").write_text(
            "---\ntipo: proyecto\n---\n\n- [ ] Antigua\n", encoding="utf-8")
        repo = self.raiz / "repo-uno"
        self.escribir({"fuente": "obsidian", "fuentes": {"obsidian": {
            "vault": str(vault), "carpeta_proyectos": "01-Proyectos",
            "migrados": {"Uno": str(repo)}}}})

        proyectos.quitar("Uno", repo)

        activa = fuente.abrir(fuente.cargar_config())
        self.assertEqual(activa.escanear(), [])

    def test_la_carpeta_solo_se_entrega_a_la_papelera_indicada(self):
        repo = self.raiz / "repo"
        repo.mkdir()
        visto = []

        proyectos.mover_a_papelera(repo, visto.append)

        self.assertEqual(visto, [str(repo)])
        self.assertTrue(repo.is_dir())  # el doble no borra: la funcion tampoco tiene otro camino

    def test_no_se_llama_a_la_papelera_si_la_carpeta_ya_no_existe(self):
        visto = []
        with self.assertRaisesRegex(ValueError, "ya no existe"):
            proyectos.mover_a_papelera(self.raiz / "ausente", visto.append)
        self.assertEqual(visto, [])

    def test_no_se_puede_enviar_una_ruta_vacia_a_la_papelera(self):
        visto = []
        with self.assertRaisesRegex(ValueError, "no tiene una carpeta"):
            proyectos.mover_a_papelera("", visto.append)
        self.assertEqual(visto, [])


if __name__ == "__main__":
    unittest.main()
