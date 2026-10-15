"""La versión a la que pertenece una tarea (v1.2.4): `#v1.2.4` o `#v1.2` en su línea.

La fuente la lee como lee `#agente/…` —la saca del texto y la deja en `Tarea.version`—, la CLI
filtra por ella (`tareas --version`) y la escribe al crear (`crear --version`). Un solo parser,
`version.de_tarea`, sirve a la fuente, al modelo (el prefijo `v1.2.4 ·` de antes) y a la CLI.
"""

import unittest

import test_fuente_externa as externa
from apoyo import PruebaDeCLI, proyecto
from test_fuente_repo import PruebaConRepos, hacer_repo
from tareas import version
from tareas.modelo import Tarea


class ElParser(unittest.TestCase):
    def test_normaliza_con_y_sin_v(self):
        for texto, esperada in (("1.2", "v1.2"), ("v1.2", "v1.2"), ("1.2.4", "v1.2.4"),
                                (" v1.2.4 ", "v1.2.4"), ("0.1.0", "v0.1.0")):
            self.assertEqual(version.de_tarea(texto), esperada, texto)

    def test_lo_que_no_es_una_version_no_cuenta(self):
        for texto in ("", None, "1", "v1", "1.2.3.4", "v01.2", "1.2-rc1", "vx.y", "1.2.", "V1.2"):
            self.assertIsNone(version.de_tarea(texto), texto)

    def test_pertenece(self):
        self.assertTrue(version.pertenece("v1.2.4", "1.2.4"))
        self.assertTrue(version.pertenece("v1.2.4", "v1.2"))  # la línea entera
        self.assertTrue(version.pertenece("v1.2", "1.2"))
        self.assertFalse(version.pertenece("v1.2", "1.2.4"))  # la de la línea no es de un parche
        self.assertFalse(version.pertenece("v1.2.4", "1.2.5"))
        self.assertFalse(version.pertenece("v1.20.1", "1.2"))
        self.assertFalse(version.pertenece("", "1.2"))

    def test_el_campo_y_el_prefijo_se_leen_igual(self):
        self.assertEqual(Tarea("v1.2.4 · Algo: x").version_del_texto, "v1.2.4")
        self.assertEqual(Tarea("Algo: x", version="v1.2").version_del_texto, "v1.2")
        self.assertEqual(Tarea("Algo: x").version_del_texto, "")


class EnObsidian(PruebaDeCLI):
    def test_el_tag_se_lee_como_el_del_agente_y_no_se_ve_en_el_texto(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el botón #v1.2.4 #agente/opus #en-curso ^a1",
            "- [ ] De la línea #v1.3 ^a2",
            "- [ ] Sin versión ^a3",
            "- [ ] No es versión #v01.2 ni #v1.2.3.4 ^a4",
        ))
        _, tareas = self.tareas_de("Uno")
        por_id = {t.id: t for t in tareas}
        self.assertEqual((por_id["a1"].version, por_id["a1"].texto, por_id["a1"].agente),
                         ("v1.2.4", "Arreglar el botón", "opus"))
        self.assertEqual(por_id["a2"].version, "v1.3")
        self.assertEqual(por_id["a3"].version, "")
        self.assertEqual(por_id["a4"].version, "")
        self.assertIn("#v01.2", por_id["a4"].texto)
        self.assertIn("#v1.2.3.4", por_id["a4"].texto)

    def test_escribir_otra_cosa_no_le_quita_la_version(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Arreglar #v1.2.4 ^a1"))
        self.correr("tomar", "a1", "--agente", "opus")
        self.assertIn("#v1.2.4", self.leer_nota("Uno.md"))
        self.assertEqual(self.una_tarea().version, "v1.2.4")

    def test_filtro_por_parche_y_por_linea(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Parche cuatro #v1.2.4 ^a1",
            "- [ ] Parche cinco #v1.2.5 ^a2",
            "- [ ] De la línea #v1.2 ^a3",
            "- [ ] v1.2.4 · Con el prefijo de antes ^a4",
            "- [ ] Otra línea #v1.3.0 ^a5",
            "- [ ] Sin versión ^a6",
        ))
        _, datos = self.correr("tareas", "--version", "1.2.4")
        self.assertEqual(sorted(t["id"] for t in datos["tareas"]), ["a1", "a4"])
        _, datos = self.correr("tareas", "--version", "v1.2")
        self.assertEqual(sorted(t["id"] for t in datos["tareas"]), ["a1", "a2", "a3", "a4"])
        self.assertEqual(next(t for t in datos["tareas"] if t["id"] == "a3")["version"], "v1.2")
        _, datos = self.correr("tareas")
        self.assertEqual(len(datos["tareas"]), 6)

    def test_crear_con_version_escribe_el_tag(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Primera ^a1"))
        codigo, datos = self.correr("crear", "Segunda", "--proyecto", "Uno",
                                    "--dificultad", "facil", "--version", "1.2.4")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["version"], "v1.2.4")
        linea = self.leer_nota("Uno.md").splitlines()[-1]
        self.assertTrue(linea.startswith("- [ ] Segunda #facil #v1.2.4 ^"), linea)
        _, datos = self.correr("tareas", "--version", "1.2.4")
        self.assertEqual([t["texto"] for t in datos["tareas"]], ["Segunda"])

    def test_una_version_invalida_no_llega_a_escribir(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Primera ^a1"))
        antes = self.leer_nota("Uno.md")
        for mala in ("1", "1.2.3.4", "v01.2", "uno"):
            for argumentos in (("crear", "Otra", "--proyecto", "Uno", "--version", mala),
                               ("tareas", "--version", mala)):
                with self.assertRaises(SystemExit) as salida:  # error de uso de argparse
                    self.correr_crudo(*argumentos)
                self.assertEqual(salida.exception.code, 2, mala)
        self.assertEqual(self.leer_nota("Uno.md"), antes)


class EnUnRepo(PruebaConRepos):
    def test_lee_el_tag_y_crea_con_version(self):
        hacer_repo(self.cosas, "# Tareas", "", "- [ ] Con versión #v2.0 ^r1")
        _, datos = self.correr("tareas", "--version", "2.0")
        self.assertEqual([t["id"] for t in datos["tareas"]], ["r1"])
        codigo, datos = self.correr("crear", "Nueva", "--proyecto", "Cosas", "--version", "2.0.1")
        self.assertEqual((codigo, datos["tarea"]["version"]), (0, "v2.0.1"))
        self.assertIn("- [ ] Nueva #v2.0.1 ^", self.archivo())
        _, datos = self.correr("tareas", "--version", "2.0")
        self.assertEqual(len(datos["tareas"]), 2)


class EnUnaFuenteExterna(externa.PruebaConAdaptador):
    def test_el_adaptador_da_la_version_y_la_recibe_al_crear(self):
        self.guardar_tareas([{"nombre": "Casa", "tareas": [
            externa.tarea("casa-1", "Pintar la reja", version="1.2"),
            externa.tarea("casa-2", "Arreglar el grifo", version="no-es"),
        ]}])
        _, datos = self.correr("tareas", "--version", "1.2")
        self.assertEqual([t["id"] for t in datos["tareas"]], ["casa-1"])
        self.assertEqual(datos["tareas"][0]["version"], "v1.2")
        codigo, datos = self.correr("crear", "Cambiar el foco", "--proyecto", "Casa",
                                    "--version", "1.2.4")
        self.assertEqual((codigo, datos["tarea"]["version"]), (0, "v1.2.4"))
        self.assertEqual(self.leer_tareas()[datos["tarea"]["id"]]["version"], "v1.2.4")

    def test_sin_version_el_adaptador_no_recibe_la_opcion(self):
        # Un adaptador que no sepa de versiones no puede romperse por una opción que no pidió.
        codigo, datos = self.correr("crear", "Cambiar el foco", "--proyecto", "Casa")
        self.assertEqual(codigo, 0)
        self.assertNotIn("version", self.leer_tareas()[datos["tarea"]["id"]])


if __name__ == "__main__":
    unittest.main()
