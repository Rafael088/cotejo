"""`cotejo limpiar` (v1.2.2, cotejo-r3cs5t): borrar finalizadas antiguas sin perder su rastro.

Lo que se vigila: que por defecto sea un ensayo que no toca nada, que solo salgan las hechas de
hace más de una semana o sin fecha, que antes de borrar una sin `comprobar` quede su anotación
`limpiar` en la bitácora, que se borre por la fuente verificando la línea, y el aviso de
`entregar` cuando un proyecto pasa del umbral. Todo contra un vault y un estado de mentira.
"""

import json
import tempfile
from datetime import date
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeCLI, nota, proyecto
from tareas import bitacora, cli, configuracion, fuente as f, modelo
from tareas.fuentes.externa import Externa
from tareas.fuentes.obsidian import Obsidian

HOY = date(2026, 10, 6)


class PruebaDeLimpiar(PruebaDeCLI):

    def setUp(self):
        super().setUp()
        parche = mock.patch.object(cli, "_hoy", lambda: HOY)
        parche.start()
        self.addCleanup(parche.stop)
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Pendiente ^cotejo-pend01",
            "- [x] Vieja aprobada #agente/opus — 2026-09-01 ^cotejo-vie001",
            "- [x] Vieja a mano — 2026-09-20 ^cotejo-vie002",
            "- [x] Sin fecha ^cotejo-sinf01",
            "- [x] De esta semana — 2026-10-02 ^cotejo-nuev01",
            "- [x] Justo hace siete — 2026-09-29 ^cotejo-siet01",
            "- [ ] Haciéndola #en-curso #agente/opus ^cotejo-curs01",
        ))
        # La que aprobó una persona en el board dejó su `comprobar`.
        self.bitacora.write_text(json.dumps(
            {"cuando": 1, "operacion": "comprobar", "id": "foco-vie001", "proyecto": "Uno",
             "texto": "Vieja aprobada", "nota": "01-Proyectos/Uno.md", "agente": "opus",
             "de": "por-validar", "a": "hecha"}) + "\n", encoding="utf-8")


class Ensayo(PruebaDeLimpiar):

    def test_lista_las_antiguas_y_las_sin_fecha_y_no_toca_nada(self):
        antes = self.leer_nota("Uno.md"), self.bitacora.read_text(encoding="utf-8")
        codigo, datos = self.correr("limpiar", "Uno")
        self.assertEqual(codigo, 0, datos)
        self.assertTrue(datos["ensayo"])
        self.assertEqual([t["id"] for t in datos["tareas"]],
                         ["cotejo-vie001", "cotejo-vie002", "cotejo-sinf01"])
        self.assertEqual((datos["finalizadas"], datos["total"], datos["sin_comprobar"]), (5, 3, 2))
        self.assertEqual((self.leer_nota("Uno.md"), self.bitacora.read_text(encoding="utf-8")),
                         antes)

    def test_dice_cuales_tienen_ya_su_comprobar_incluso_con_el_id_de_antes(self):
        _, datos = self.correr("limpiar", "Uno")
        por_id = {t["id"]: t for t in datos["tareas"]}
        self.assertTrue(por_id["cotejo-vie001"]["comprobada"])
        self.assertFalse(por_id["cotejo-vie002"]["comprobada"])
        self.assertEqual(por_id["cotejo-vie002"]["fecha"], "2026-09-20")
        self.assertIsNone(por_id["cotejo-sinf01"]["fecha"])

    def test_el_comprobar_se_encuentra_aunque_este_fuera_de_la_cola(self):
        relleno = "".join(json.dumps({"operacion": "tomar", "id": f"x-{i}", "texto": "r" * 200})
                          + "\n" for i in range(2000))
        self.bitacora.write_text(self.bitacora.read_text(encoding="utf-8") + relleno,
                                 encoding="utf-8")
        self.assertGreater(self.bitacora.stat().st_size, bitacora.COLA_BYTES)
        _, datos = self.correr("limpiar", "Uno")
        self.assertTrue({t["id"]: t for t in datos["tareas"]}["cotejo-vie001"]["comprobada"])

    def test_un_proyecto_que_no_existe_es_un_error(self):
        codigo, datos = self.correr("limpiar", "Nadie")
        self.assertNotEqual(codigo, 0)
        self.assertIn("Nadie", datos["error"])


class Aplicar(PruebaDeLimpiar):

    def test_borra_las_lineas_y_deja_las_demas_tal_cual(self):
        codigo, datos = self.correr("limpiar", "Uno", "--aplicar")
        self.assertEqual(codigo, 0, datos)
        self.assertTrue(datos["cambio"])
        self.assertEqual([t["id"] for t in datos["borradas"]],
                         ["cotejo-vie001", "cotejo-vie002", "cotejo-sinf01"])
        self.assertEqual(self.leer_nota("Uno.md"), proyecto(
            "- [ ] Pendiente ^cotejo-pend01",
            "- [x] De esta semana — 2026-10-02 ^cotejo-nuev01",
            "- [x] Justo hace siete — 2026-09-29 ^cotejo-siet01",
            "- [ ] Haciéndola #en-curso #agente/opus ^cotejo-curs01",
        ))

    def test_antes_de_borrar_anota_limpiar_solo_a_las_que_no_tienen_comprobar(self):
        self.correr("limpiar", "Uno", "--aplicar")
        limpiadas = [o for o in self.operaciones() if o.get("operacion") == "limpiar"]
        self.assertEqual({o["id"]: (o["texto"], o["fecha"], o["nota"]) for o in limpiadas}, {
            "cotejo-vie002": ("Vieja a mano — 2026-09-20", "2026-09-20", "01-Proyectos/Uno.md"),
            "cotejo-sinf01": ("Sin fecha", None, "01-Proyectos/Uno.md"),
        })

    def test_el_id_sigue_resolviendo_en_la_bitacora_despues_de_borrar(self):
        self.correr("limpiar", "Uno", "--aplicar")
        self.assertEqual(bitacora.ids_con("comprobar", "limpiar"),
                         {"cotejo-vie001", "cotejo-vie002", "cotejo-sinf01"})

    def test_si_no_puede_anotar_no_borra(self):
        antes = self.leer_nota("Uno.md")
        with mock.patch.object(bitacora, "anotar", return_value=False):
            codigo, datos = self.correr("limpiar", "Uno", "--aplicar")
        self.assertEqual(codigo, 0)
        # La que ya tenía `comprobar` no necesitaba anotación y sí se borra.
        self.assertEqual([t["id"] for t in datos["borradas"]], ["cotejo-vie001"])
        self.assertEqual({t["id"] for t in datos["saltadas"]}, {"cotejo-vie002", "cotejo-sinf01"})
        self.assertIn("Sin fecha", self.leer_nota("Uno.md"))
        self.assertNotEqual(self.leer_nota("Uno.md"), antes)

    def test_una_linea_que_cambio_no_se_borra(self):
        fuente = f.abrir()
        original = type(fuente).quitar

        def quitar_con_carrera(yo, tarea):
            if tarea.id == "cotejo-vie002":
                ruta = self.vault / self.CARPETA / "Uno.md"
                ruta.write_text(ruta.read_text(encoding="utf-8").replace(
                    "Vieja a mano", "Vieja editada"), encoding="utf-8")
            return original(yo, tarea)

        with mock.patch.object(type(fuente), "quitar", quitar_con_carrera):
            _, datos = self.correr("limpiar", "Uno", "--aplicar")
        self.assertEqual([t["id"] for t in datos["saltadas"]], ["cotejo-vie002"])
        self.assertIn("Vieja editada", self.leer_nota("Uno.md"))
        self.assertIn("avisos", datos)

    def test_sin_marca_borra_de_abajo_arriba_y_no_se_equivoca_de_linea(self):
        self.escribir_nota("Dos.md", proyecto(
            "- [x] Primera sin marca — 2026-01-01",
            "- [ ] Queda",
            "- [x] Segunda sin marca — 2026-01-02",
        ))
        codigo, datos = self.correr("limpiar", "Dos", "--aplicar")
        self.assertEqual(codigo, 0, datos)
        self.assertEqual(len(datos["borradas"]), 2)
        self.assertEqual(self.leer_nota("Dos.md"), proyecto("- [ ] Queda"))

    def test_repetirlo_no_hace_nada(self):
        self.correr("limpiar", "Uno", "--aplicar")
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("limpiar", "Uno", "--aplicar")
        self.assertEqual(codigo, 0)
        self.assertFalse(datos["cambio"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_no_toca_las_que_no_estan_finalizadas(self):
        self.correr("limpiar", "Uno", "--aplicar")
        _, datos = self.correr("tareas", "--proyecto", "Uno")
        self.assertEqual({t["id"] for t in datos["tareas"]}, {"cotejo-pend01", "cotejo-curs01"})


class FuenteQueNoSabeBorrar(PruebaDeLimpiar):

    def test_la_externa_lo_dice_sin_escribir_nada(self):
        externa = Externa("falsa", {"comando": "/bin/false"})
        externa.escanear = lambda incluir_hechas=False, avisos=None: Obsidian(
            {"vault": str(self.vault), "carpeta_proyectos": self.CARPETA}).escanear(
                incluir_hechas, avisos)
        antes = self.leer_nota("Uno.md"), self.bitacora.read_text(encoding="utf-8")
        with mock.patch.object(f, "abrir", return_value=externa), \
                mock.patch.object(Externa, "problema", None):
            codigo, datos = self.correr("limpiar", "Uno", "--aplicar")
        self.assertNotEqual(codigo, 0)
        self.assertIn("no sabe borrar", datos["error"])
        self.assertEqual((self.leer_nota("Uno.md"), self.bitacora.read_text(encoding="utf-8")),
                         antes)


class EnLaCompuesta(PruebaDeLimpiar):
    """En un repo migrado la línea se borra de `.cotejo/tareas.md`, no del vault."""

    def test_borra_en_el_repo_migrado(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        repo = Path(temporal.name) / "cotejo"
        (repo / ".git").mkdir(parents=True)
        (repo / ".cotejo").mkdir()
        tareas = repo / ".cotejo" / "tareas.md"
        tareas.write_text(nota("# Tareas", "", "- [x] Vieja del repo — 2026-08-01 ^cotejo-rep001",
                               "- [ ] Viva ^cotejo-rep002"), encoding="utf-8")
        self.config.write_text(json.dumps({"fuente": "obsidian", "fuentes": {"obsidian": {
            "vault": str(self.vault), "carpeta_proyectos": self.CARPETA,
            "migrados": {"Cotejo": str(repo)}}}}), encoding="utf-8")
        _, ensayo = self.correr("limpiar", "Cotejo")
        self.assertEqual([t["id"] for t in ensayo["tareas"]], ["cotejo-rep001"])
        codigo, datos = self.correr("limpiar", "Cotejo", "--aplicar")
        self.assertEqual(codigo, 0, datos)
        self.assertEqual(tareas.read_text(encoding="utf-8"),
                         nota("# Tareas", "", "- [ ] Viva ^cotejo-rep002"))


class AvisoAlEntregar(PruebaDeCLI):

    def setUp(self):
        super().setUp()
        hechas = [f"- [x] Hecha {i} — 2026-01-01 ^cotejo-h{i:05d}" for i in range(4)]
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Haciéndola #en-curso #agente/opus ^cotejo-curs01", *hechas))

    def configurar(self, limpiar):
        self.config.write_text(json.dumps({"limpiar": limpiar}), encoding="utf-8")

    def avisos(self):
        codigo, datos = self.correr("entregar", "cotejo-curs01", "--evidencia", "x")
        self.assertEqual(codigo, 0, datos)
        return datos.get("avisos", [])

    def test_por_encima_del_umbral_avisa_de_limpiar(self):
        self.configurar({"umbral": 3})
        aviso, = self.avisos()
        self.assertIn("cotejo limpiar Uno", aviso)
        self.assertIn("4", aviso)

    def test_en_el_umbral_o_por_debajo_no_avisa(self):
        self.configurar({"umbral": 4})
        self.assertEqual(self.avisos(), [])

    def test_por_defecto_el_umbral_es_50(self):
        self.assertEqual(configuracion.umbral_limpiar({}), 50)
        self.assertEqual(self.avisos(), [])

    def test_cero_lo_apaga(self):
        self.configurar({"umbral": 0})
        self.assertEqual(self.avisos(), [])

    def test_un_umbral_roto_usa_el_de_defecto(self):
        self.assertEqual(configuracion.umbral_limpiar({"limpiar": {"umbral": "mucho"}}), 50)
        self.assertEqual(configuracion.umbral_limpiar({"limpiar": {"umbral": True}}), 50)
        self.assertEqual(configuracion.umbral_limpiar({"limpiar": 7}), 50)


class ValidarLaConfig(PruebaDeCLI):

    def validar(self, datos):
        self.config.write_text(json.dumps(datos), encoding="utf-8")
        return configuracion.validar({"obsidian", "repo"})

    def test_un_umbral_bueno_no_se_queja(self):
        errores, _ = self.validar({"limpiar": {"umbral": 80}})
        self.assertEqual(errores, [])

    def test_un_umbral_que_no_es_entero_es_un_error(self):
        for malo in ("50", -1, 2.5, True, None):
            with self.subTest(umbral=malo):
                errores, _ = self.validar({"limpiar": {"umbral": malo}})
                self.assertTrue(any("limpiar.umbral" in e for e in errores), errores)

    def test_limpiar_tiene_que_ser_un_objeto(self):
        errores, _ = self.validar({"limpiar": 50})
        self.assertTrue(any("«limpiar»" in e for e in errores), errores)

    def test_una_clave_desconocida_es_un_aviso(self):
        errores, avisos = self.validar({"limpiar": {"umbral": 50, "dias": 3}})
        self.assertEqual(errores, [])
        self.assertTrue(any("dias" in a for a in avisos), avisos)

    def test_no_se_lee_como_parametro_de_obsidian(self):
        self.assertNotIn("limpiar", configuracion.parametros({"limpiar": {"umbral": 1}},
                                                             "obsidian"))

    def test_config_validar_lo_dice_por_la_cli(self):
        self.config.write_text(json.dumps({"limpiar": {"umbral": -3}}), encoding="utf-8")
        codigo, datos = self.correr("config", "validar")
        self.assertNotEqual(codigo, 0)
        self.assertIn("limpiar.umbral", json.dumps(datos, ensure_ascii=False))


class FechaDeCierre(PruebaDeCLI):

    def test_obsidian_la_lee_de_la_linea(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [x] Con fecha #agente/opus — 2026-09-01 ^cotejo-a00001",
            "- [x] Fecha en medio 2026-09-01 del texto ^cotejo-a00002",
            "- [x] Sin marca — 2026-08-30",
        ))
        _, tareas = self.tareas_de("Uno")
        self.assertEqual([self.fuente.fecha_cierre(t) for t in tareas],
                         ["2026-09-01", None, "2026-08-30"])

    def test_si_el_modelo_trae_cerrada_gana(self):
        tarea = modelo.Tarea("x")
        tarea.cerrada = "2026-01-02"
        self.assertEqual(f.Fuente().fecha_cierre(tarea), "2026-01-02")
