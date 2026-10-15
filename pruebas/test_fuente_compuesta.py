"""La fuente compuesta (v1.2, A3): el vault y los repos de los proyectos migrados a la vez.

Es Obsidian con `migrados` en su config. Lo que se vigila es lo que decidió E1: un proyecto
marcado se lee de su repo y deja de leerse del vault aunque su nota siga ahí (gana el repo),
cada escritura va a la fuente dueña de la tarea con su verificación, y sin la marca no cambia
nada. Todo corre con la CLI de verdad, contra un vault y un repo de mentira.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeCLI, nota, proyecto
from tareas import fuente as f, modelo
from tareas.fuentes.compuesta import Compuesta
from tareas.fuentes.obsidian import Obsidian


class PruebaCompuesta(PruebaDeCLI):

    def setUp(self):
        super().setUp()
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "cotejo"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / ".cotejo").mkdir()
        (self.repo / ".cotejo" / "tareas.md").write_text(
            nota("# Tareas", "", "- [ ] Del repo #medio ^cotejo-repo01"), encoding="utf-8")
        # La nota del proyecto sigue en el vault, con una tarea que ya no debe salir.
        self.escribir_nota("Cotejo/Cotejo.md", proyecto("- [ ] Del vault viejo ^cotejo-viej01",
                                                        estado="activo"))
        self.escribir_nota("Seorigen.md", proyecto("- [ ] Del vault ^cotejo-vaul01",
                                                   estado="activo"))
        self.configurar({"Cotejo": str(self.repo)})

    def configurar(self, migrados):
        obsidian = {"vault": str(self.vault), "carpeta_proyectos": self.CARPETA}
        if migrados is not None:
            obsidian["migrados"] = migrados
        self.config.write_text(json.dumps({"fuente": "obsidian",
                                           "fuentes": {"obsidian": obsidian}}),
                               encoding="utf-8")

    def textos(self, proyecto_nombre):
        codigo, datos = self.correr("tareas", "--proyecto", proyecto_nombre)
        self.assertEqual(codigo, 0, datos)
        return [t["texto"] for t in datos["tareas"]]

    def repo_md(self):
        return (self.repo / ".cotejo" / "tareas.md").read_text(encoding="utf-8")


class Leer(PruebaCompuesta):

    def test_con_migrados_abrir_devuelve_la_compuesta_y_sin_ellos_obsidian(self):
        self.assertIsInstance(f.abrir(), Compuesta)
        self.configurar(None)
        self.assertIs(type(f.abrir()), Obsidian)
        self.configurar({})
        self.assertIs(type(f.abrir()), Obsidian)

    def test_el_proyecto_migrado_sale_del_repo_con_su_nombre_y_no_del_vault(self):
        self.assertEqual(self.textos("Cotejo"), ["Del repo"])
        self.assertEqual(self.textos("Seorigen"), ["Del vault"])

    def test_un_solo_proyecto_por_nombre(self):
        nombres = [p.nombre for p in f.abrir().escanear()]
        self.assertEqual(sorted(nombres), ["Cotejo", "Seorigen"])

    def test_el_nombre_migrado_no_distingue_mayusculas(self):
        self.configurar({"cotejo": str(self.repo)})
        nombres = sorted(p.nombre for p in f.abrir().escanear())
        self.assertEqual(nombres, ["Seorigen", "cotejo"])

    def test_quitar_la_marca_lo_deshace_sin_escribir_nada(self):
        antes = self.leer_nota("Cotejo/Cotejo.md"), self.repo_md()
        self.configurar(None)
        self.assertEqual(self.textos("Cotejo"), ["Del vault viejo"])
        self.assertEqual((self.leer_nota("Cotejo/Cotejo.md"), self.repo_md()), antes)

    def test_cotejo_repos_del_entorno_no_cuela_repos_no_migrados(self):
        otro = Path(self.repo.parent) / "otro"
        (otro / ".git").mkdir(parents=True)
        (otro / ".cotejo").mkdir()
        (otro / ".cotejo" / "tareas.md").write_text("- [ ] Intruso ^cotejo-intr01\n",
                                                    encoding="utf-8")
        with mock.patch.dict(os.environ, {"COTEJO_REPOS": str(otro),
                                          "COTEJO_RAIZ_REPOS": str(otro.parent)}):
            nombres = sorted(p.nombre for p in f.abrir().escanear())
        self.assertEqual(nombres, ["Cotejo", "Seorigen"])

    def test_un_repo_migrado_que_no_esta_es_un_problema(self):
        self.configurar({"Cotejo": str(self.repo.parent / "no-existe")})
        self.assertIn("no-existe", f.abrir().problema)

    def test_un_repo_migrado_sin_tareas_md_se_avisa_y_no_vuelve_al_vault(self):
        (self.repo / ".cotejo" / "tareas.md").unlink()
        avisos = []
        nombres = [p.nombre for p in f.abrir().escanear(avisos=avisos)]
        self.assertEqual(nombres, ["Seorigen"])
        self.assertTrue(any(".cotejo/tareas.md" in a["motivo"] for a in avisos))

    def test_carpeta_de_dice_el_repo_del_migrado(self):
        fuente = f.abrir()
        self.assertEqual(fuente.carpeta_de("Cotejo"), self.repo)
        self.assertIsNone(fuente.carpeta_de("Seorigen"))

    def test_vigila_el_vault_y_el_repo(self):
        vigilables = f.abrir().vigilables()
        self.assertIn(str(self.repo.resolve() / ".cotejo"), vigilables)
        self.assertIn(str(self.vault / self.CARPETA), vigilables)

    def test_el_medidor_cuenta_lo_de_cada_lado_una_vez(self):
        fuente = f.abrir()
        proyectos = fuente.escanear()
        repo = [p for p in proyectos if p.nombre == "Cotejo"]
        self.assertEqual(fuente.leido(repo), len(self.repo_md()))
        self.assertGreater(fuente.leido(), fuente.leido(repo))


class Escribir(PruebaCompuesta):

    def test_tomar_una_tarea_del_repo_escribe_en_el_repo_y_no_en_el_vault(self):
        nota_antes = self.leer_nota("Cotejo/Cotejo.md")
        codigo, _ = self.correr("tomar", "cotejo-repo01", "--agente", "opus")
        self.assertEqual(codigo, 0)
        self.assertIn("#agente/opus", self.repo_md())
        self.assertEqual(self.leer_nota("Cotejo/Cotejo.md"), nota_antes)

    def test_tomar_una_tarea_del_vault_escribe_en_el_vault(self):
        repo_antes = self.repo_md()
        codigo, _ = self.correr("tomar", "cotejo-vaul01", "--agente", "sonnet")
        self.assertEqual(codigo, 0)
        self.assertIn("#agente/sonnet", self.leer_nota("Seorigen.md"))
        self.assertEqual(self.repo_md(), repo_antes)

    def test_la_tarea_vieja_del_vault_no_se_encuentra(self):
        codigo, _ = self.correr("tomar", "cotejo-viej01", "--agente", "opus")
        self.assertNotEqual(codigo, 0)
        self.assertNotIn("#agente", self.leer_nota("Cotejo/Cotejo.md"))

    def test_crear_en_el_migrado_cae_en_el_repo(self):
        codigo, datos = self.correr("crear", "Nueva", "--proyecto", "Cotejo")
        self.assertEqual(codigo, 0, datos)
        self.assertIn(f"Nueva ^{datos['tarea']['id']}", self.repo_md())
        self.assertNotIn("Nueva", self.leer_nota("Cotejo/Cotejo.md"))

    def test_la_escritura_del_repo_sigue_verificada(self):
        fuente = f.abrir()
        _, tarea = modelo.buscar(fuente.escanear(), "cotejo-repo01")
        (self.repo / ".cotejo" / "tareas.md").write_text(
            self.repo_md().replace("Del repo", "Del repo, editada"), encoding="utf-8")
        with self.assertRaises(modelo.TareaCambiada):
            fuente.poner_estado(tarea, "en-curso")

    def test_el_uri_de_cada_tarea_es_el_de_su_fuente(self):
        fuente = f.abrir()
        proyectos = fuente.escanear()
        _, del_repo = modelo.buscar(proyectos, "cotejo-repo01")
        _, del_vault = modelo.buscar(proyectos, "cotejo-vaul01")
        self.assertTrue(fuente.uri(del_repo).startswith("file://"))
        self.assertTrue(fuente.uri(del_vault).startswith("obsidian://"))
