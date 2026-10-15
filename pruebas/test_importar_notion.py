"""`cotejo importar notion` (v1.2 · D3): tareas por el adaptador que ya existe, páginas como
referencias.

Contra el mismo Notion de mentira que `test_notion.py` (`NotionFalso`, un servidor HTTP de
verdad en un hilo): nunca se llama a la API real. Lo que se vigila: que las tareas salgan con
la misma línea que escribe Obsidian, que cada página se importe además como referencia con
resumen pendiente, que el repo se resuelva sin inventarse uno (`--destino` o un migrado
anterior), que el `origen` sea estable y que aplicar dos veces no duplique nada.
"""

import json
import tempfile
from pathlib import Path

from test_notion import PruebaConNotion

from tareas import almacen
from tareas.importar_notion import NoSeImporta, planear


class PruebaImportarNotion(PruebaConNotion):

    def plan(self, nombre="Cotejo", destino=None):
        return planear(nombre, destino)

    def destino_nuevo(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        return Path(temporal.name) / "repo-notion"


class Reparto(PruebaImportarNotion):

    def test_las_tareas_salen_con_la_linea_de_obsidian(self):
        plan = self.plan(destino=str(self.destino_nuevo()))
        self.assertEqual(plan.tareas, 3)
        self.assertIn("Escribir el README #en-curso #agente/sonnet ^cotejo-", plan.tareas_md)
        self.assertIn("Publicar la versión #por-validar #agente/opus ^cotejo-", plan.tareas_md)
        self.assertIn("- [ ] Probar en Windows ^cotejo-", plan.tareas_md)
        self.assertTrue(plan.tareas_md.startswith("# Tareas\n\n"))

    def test_una_marca_hecha_lleva_el_corchete_x_y_la_dificultad(self):
        plan = self.plan("Atlas", destino=str(self.destino_nuevo()))
        self.assertIn("- [ ] Diseñar el logo #dificil ^cotejo-", plan.tareas_md)
        self.assertIn("- [x] Comprar el dominio ^cotejo-", plan.tareas_md)

    def test_cada_pagina_es_una_referencia_con_resumen_pendiente(self):
        plan = self.plan(destino=str(self.destino_nuevo()))
        referencias = {e.titulo: e for e in plan.entradas}
        self.assertEqual(set(referencias), {"Escribir el README", "Publicar la versión",
                                            "Probar en Windows"})
        for entrada in referencias.values():
            self.assertEqual(entrada.tipo, "referencia")
            self.assertEqual(entrada.campos["resumen"], almacen.PENDIENTE)
            self.assertEqual(entrada.temas, ["notion"])
            self.assertIn("notion.so", entrada.campos["url"])
            self.assertIn(entrada.campos["url"], entrada.texto)

    def test_las_marcas_y_los_origenes_son_estables_entre_dos_planes(self):
        destino = str(self.destino_nuevo())
        uno, dos = self.plan(destino=destino), self.plan(destino=destino)
        self.assertEqual(uno.tareas_md, dos.tareas_md)
        origenes = [e.origen for e in uno.entradas]
        self.assertEqual(origenes, [e.origen for e in dos.entradas])
        self.assertEqual(len(origenes), len(set(origenes)))
        self.assertTrue(all(o.startswith("notion:") for o in origenes))


class Repo(PruebaImportarNotion):

    def test_un_proyecto_que_no_existe_sugiere_el_parecido(self):
        with self.assertRaisesRegex(NoSeImporta, "¿Buscabas Cotejo"):
            self.plan("Cotej")

    def test_sin_destino_ni_migracion_previa_pide_destino(self):
        with self.assertRaises(NoSeImporta) as caso:
            self.plan("Cotejo")
        self.assertIn("--destino", caso.exception.salida)

    def test_un_destino_sin_git_se_anuncia_como_git_init_y_no_se_crea(self):
        destino = self.destino_nuevo()
        plan = self.plan(destino=str(destino))
        self.assertEqual((plan.repo["como"], plan.repo["git_init"]), ("destino", True))
        self.assertFalse(destino.exists())

    def test_la_fuente_sin_configurar_lo_dice(self):
        self.usar({"tipo": "externa", "comando": "no-existe-de-verdad"})
        with self.assertRaises(NoSeImporta) as caso:
            self.plan("Cotejo")
        self.assertIn("fuentes agregar notion", caso.exception.salida)


class Cli(PruebaImportarNotion):

    def test_el_ensayo_por_la_cli_no_escribe_nada(self):
        destino = self.destino_nuevo()
        codigo, datos = self.correr("importar", "notion", "Cotejo", "--destino", str(destino),
                                    "--detalle")
        self.assertEqual(codigo, 0, datos)
        self.assertTrue(datos["ensayo"])
        self.assertEqual(datos["conteo"]["tareas"], 3)
        self.assertEqual(datos["conteo"]["referencia"], 3)
        self.assertEqual(len(datos["entradas"]), datos["nuevas"])
        self.assertIn("no se escribió nada", datos["salida"])
        self.assertFalse(destino.exists())

    def test_lee_notion_aunque_la_fuente_activa_sea_otra(self):
        self.config.write_text(json.dumps({"fuente": "obsidian",
                                           "fuentes": {"notion": self.params}}),
                               encoding="utf-8")
        codigo, datos = self.correr("importar", "notion", "Cotejo", "--destino",
                                    str(self.destino_nuevo()))
        self.assertEqual(codigo, 0, datos)


class Aplicar(PruebaImportarNotion):
    """`--aplicar` (D3): escribe el plan en el repo, sin commit, y marca el proyecto migrado."""

    def setUp(self):
        super().setUp()
        self.repo = self.destino_nuevo()

    def aplicar(self, *extra):
        codigo, datos = self.correr("importar", "notion", "Cotejo", "--destino", str(self.repo),
                                    *extra)
        self.assertEqual(codigo, 0, datos)
        return datos

    def cotejo(self):
        return almacen.Almacen(self.repo)

    def test_escribe_las_tareas_y_las_referencias(self):
        datos = self.aplicar("--aplicar")
        self.assertFalse(datos["ensayo"])
        self.assertTrue(datos["git_init"])
        self.assertEqual(datos["escritas"], {"referencia": 3})
        tareas = (self.repo / ".cotejo" / "tareas.md").read_text(encoding="utf-8")
        self.assertIn("Escribir el README #en-curso #agente/sonnet ^cotejo-", tareas)
        self.assertIn("Publicar la versión #por-validar #agente/opus ^cotejo-", tareas)
        referencias = self.cotejo().entradas("referencia")
        self.assertEqual({r.titulo for r in referencias},
                         {"Escribir el README", "Publicar la versión", "Probar en Windows"})
        self.assertTrue(all(r.datos["resumen"] == "pendiente" for r in referencias))
        self.assertTrue(all(r.datos["origen"].startswith("notion:") for r in referencias))

    def test_crea_la_tarea_de_revision(self):
        self.aplicar("--aplicar")
        tareas = (self.repo / ".cotejo" / "tareas.md").read_text(encoding="utf-8")
        self.assertIn("Revisar lo importado: resúmenes, temas y fichas", tareas)

    def test_marca_el_proyecto_migrado_en_la_config_de_notion(self):
        datos = self.aplicar("--aplicar")
        self.assertEqual(datos["migrado"], {"Cotejo": str(self.repo.resolve())})
        config = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(config["fuentes"]["notion"]["migrados"], datos["migrado"])

    def test_pone_version_en_proyecto_md(self):
        datos = self.aplicar("--aplicar")
        self.assertEqual(datos["version"], {"version": "0.1.0", "hecho": "puesta"})
        self.assertEqual(self.cotejo().leer("proyecto").datos["version"], "0.1.0")

    def test_repetirlo_no_escribe_nada(self):
        self.aplicar("--aplicar")
        antes = {str(p): p.read_bytes() for p in sorted(self.repo.rglob("*")) if p.is_file()}
        datos = self.aplicar("--aplicar")
        self.assertEqual(datos["escritas"], {})
        self.assertEqual(datos["ya_estaban"], 3)
        self.assertEqual(datos["tareas_md"], "ya-estaban")
        despues = {str(p): p.read_bytes() for p in sorted(self.repo.rglob("*")) if p.is_file()}
        self.assertEqual(antes, despues)

    def test_tras_aplicar_una_segunda_llamada_sin_destino_reutiliza_el_repo(self):
        self.aplicar("--aplicar")
        codigo, datos = self.correr("importar", "notion", "Cotejo")
        self.assertEqual(codigo, 0, datos)
        self.assertEqual(datos["repo"]["como"], "migrado")
        self.assertEqual(datos["repo"]["ruta"], str(self.repo.resolve()))

    def test_un_repo_con_otras_tareas_se_niega_sin_escribir(self):
        (self.repo / ".cotejo").mkdir(parents=True)
        (self.repo / ".git").mkdir()
        (self.repo / ".cotejo" / "tareas.md").write_text("- [ ] Otra cosa ^cotejo-otra01\n",
                                                          encoding="utf-8")
        codigo, datos = self.correr("importar", "notion", "Cotejo", "--destino", str(self.repo),
                                    "--aplicar")
        self.assertEqual(codigo, 3)
        self.assertIn("ya tiene tareas", datos["error"])
        self.assertFalse((self.repo / ".cotejo" / "referencias").exists())
