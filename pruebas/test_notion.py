"""Notion como segundo cerebro: la CLI de Cotejo → `cotejo-notion` → un Notion de mentira.

Cada prueba recorre el camino entero de verdad —otro proceso, HTTP de verdad— contra el
servidor de `notion_falso.py`. Lo único que no es de verdad es Notion.
"""

import json
import os
import sys
from unittest import mock

from apoyo import RAIZ, PruebaDeCLI
from notion_falso import TOKEN, NotionFalso
from tareas import fuente as f, modelo

ADAPTADOR = RAIZ / "extras" / "notion" / "cotejo_notion.py"


class PruebaConNotion(PruebaDeCLI):
    PROPIEDADES = None

    def setUp(self):
        super().setUp()
        self.notion = NotionFalso(propiedades=self.PROPIEDADES)
        url = self.notion.arrancar()
        self.addCleanup(self.notion.parar)
        parche = mock.patch.dict(os.environ, {"COTEJO_NOTION_API": url, "NOTION_TOKEN": TOKEN})
        parche.start()
        self.addCleanup(parche.stop)
        self.sembrar()
        # El archivo del token, dentro de la prueba: el de verdad (~/.config/cotejo/notion.token)
        # no puede decidir si una prueba pasa, ni mandar el token real a un Notion de mentira.
        self.params = {"tipo": "externa", "comando": [sys.executable, str(ADAPTADOR)],
                       "database_id": self.notion.base_id,
                       "token_archivo": str(self.vault / "no-hay-token")}
        self.usar(self.params)

    def sembrar(self):
        self.notion.tarea("Diseñar el logo", proyecto="Atlas", dificultad="Difícil")
        self.notion.tarea("Escribir el README", proyecto="Cotejo", estado="En curso",
                          agente="sonnet")
        self.notion.tarea("Publicar la versión", proyecto="Cotejo", estado="Por validar",
                          agente="opus")
        self.notion.tarea("Comprar el dominio", proyecto="Atlas", hecha=True)
        self.notion.tarea("Probar en Windows", proyecto="Cotejo")

    def usar(self, params):
        self.config.write_text(json.dumps({"fuente": "notion", "fuentes": {"notion": params}}),
                               encoding="utf-8")

    def por_texto(self, texto):
        _, datos = self.correr("tareas")
        return next(t for t in datos["tareas"] if t["texto"] == texto)

    def patches(self):
        return [p for p in self.notion.peticiones if p[0] == "PATCH"]


class Leer(PruebaConNotion):
    def test_las_paginas_son_tareas_y_la_propiedad_proyecto_su_proyecto(self):
        codigo, datos = self.correr("tareas", "--todas")
        self.assertEqual(codigo, 0)
        # Cinco tareas con páginas de tres: si la paginación fallara, faltarían dos.
        self.assertEqual(datos["total"], 5)
        logo = self.por_texto("Diseñar el logo")
        self.assertEqual((logo["proyecto"], logo["estado"], logo["dificultad"]),
                         ("Atlas", "pendiente", "dificil"))
        self.assertEqual(logo["id"], "tar-1")

    def test_los_estados_de_notion_son_las_columnas_de_cotejo(self):
        estados = {t["texto"]: t["estado"] for t in self.correr("tareas", "--todas")[1]["tareas"]}
        self.assertEqual(estados["Escribir el README"], "en-curso")
        self.assertEqual(estados["Publicar la versión"], "por-validar")
        self.assertEqual(estados["Comprar el dominio"], "hecha")

    def test_doctor_dice_que_esta_conectado(self):
        codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 0, datos)
        self.assertIn("Tareas", datos["fuente"]["mensaje"])
        self.assertEqual(datos["fuente"]["pendientes"], 4)

    def test_la_barra_no_cuenta_las_hechas_y_no_las_pide(self):
        from tareas import estado
        resumen = estado.calcular()
        self.assertEqual(resumen["pendientes"], 4)
        consulta = [p for p in self.notion.peticiones if p[0] == "POST"]
        self.assertTrue(consulta)


class Escribir(PruebaConNotion):
    def test_tomar_y_entregar_mueven_la_pagina(self):
        identificador = self.por_texto("Probar en Windows")["id"]
        self.correr("tomar", identificador, "--agente", "haiku")
        self.assertEqual(self.notion.valor("Probar en Windows", "Estado"), "En curso")
        self.assertEqual(self.notion.valor("Probar en Windows", "Agente"), "haiku")
        codigo, datos = self.correr("entregar", identificador, "--evidencia", "probado en W11")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.notion.valor("Probar en Windows", "Estado"), "Por validar")
        self.assertEqual(self.operaciones()[-1]["evidencia"], "probado en W11")

    def test_bloquear_la_devuelve_sin_dueno(self):
        identificador = self.por_texto("Escribir el README")["id"]
        codigo, _ = self.correr("bloquear", identificador, "--motivo", "falta la captura")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.notion.valor("Escribir el README", "Estado"), "Pendiente")
        self.assertIsNone(self.notion.valor("Escribir el README", "Agente"))

    def test_repetir_no_vuelve_a_escribir(self):
        identificador = self.por_texto("Probar en Windows")["id"]
        self.correr("tomar", identificador, "--agente", "haiku")
        escrituras = len(self.patches())
        codigo, datos = self.correr("tomar", identificador, "--agente", "haiku")
        self.assertEqual((codigo, datos["cambio"]), (0, False))
        self.assertEqual(len(self.patches()), escrituras)

    def test_si_alguien_la_cambio_en_notion_no_se_pisa(self):
        fuente = f.abrir()
        leida = next(t for p in fuente.escanear() for t in p.tareas
                     if t.texto == "Probar en Windows")
        self.notion.cambiar("Probar en Windows", "Agente", "rafael")
        with self.assertRaises(modelo.TareaCambiada):
            fuente.poner_estado(leida, "en-curso")
        self.assertEqual(self.notion.valor("Probar en Windows", "Estado"), "Pendiente")
        self.assertEqual(self.patches(), [])

    def test_crear_llena_proyecto_estado_y_dificultad(self):
        codigo, datos = self.correr("crear", "Grabar el vídeo", "--proyecto", "Atlas",
                                    "--dificultad", "facil")
        self.assertEqual(codigo, 0, datos)
        self.assertEqual(self.notion.valor("Grabar el vídeo", "Proyecto"), "Atlas")
        self.assertEqual(self.notion.valor("Grabar el vídeo", "Estado"), "Pendiente")
        self.assertEqual(self.notion.valor("Grabar el vídeo", "Dificultad"), "Fácil")
        self.assertEqual(datos["tarea"]["proyecto"], "Atlas")

    def test_marcar_hecha_es_el_checkbox_y_solo_lo_usa_el_board(self):
        fuente = f.abrir()
        leida = next(t for p in fuente.escanear() for t in p.tareas
                     if t.texto == "Publicar la versión")
        hecha = fuente.marcar(leida, hecha=True)
        self.assertTrue(hecha.hecha)
        self.assertTrue(self.notion.valor("Publicar la versión", "Done"))


class CuandoAlgoFalla(PruebaConNotion):
    def test_un_token_malo_lo_dice_doctor(self):
        with mock.patch.dict(os.environ, {"NOTION_TOKEN": "otro"}):
            codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 3)
        self.assertIn("token", datos["fuente"]["problema"])

    def test_sin_token_dice_donde_se_saca(self):
        entorno = {k: v for k, v in os.environ.items() if k != "NOTION_TOKEN"}
        with mock.patch.dict(os.environ, entorno, clear=True):
            _, datos = self.correr("fuentes", "probar", "notion")
        self.assertFalse(datos["ok"])
        self.assertIn("my-integrations", datos["salida"])

    def test_sin_variable_lee_el_token_del_archivo(self):
        # El board y la barra no los arranca una shell: no ven NOTION_TOKEN, sí el archivo.
        archivo = self.vault / "notion.token"
        archivo.write_text(TOKEN + "\n", encoding="utf-8")
        self.usar({**self.params, "token_archivo": str(archivo)})
        entorno = {k: v for k, v in os.environ.items() if k != "NOTION_TOKEN"}
        with mock.patch.dict(os.environ, entorno, clear=True):
            codigo, datos = self.correr("tareas", "--todas")
        self.assertEqual((codigo, datos["total"]), (0, 5))

    def test_token_archivo_no_cuenta_como_secreto(self):
        from tareas import configuracion
        self.assertFalse(configuracion.parece_secreto("token_archivo"))
        self.assertTrue(configuracion.parece_secreto("token"))

    def test_una_base_no_compartida_dice_que_se_comparta(self):
        self.usar({**self.params, "database_id": "0" * 32})
        codigo, datos = self.correr("tareas")
        self.assertEqual(codigo, 3)
        self.assertIn("comparte", datos["salida"].lower())

    def test_info_ensena_los_parametros_que_pide(self):
        _, datos = self.correr("fuentes", "info", "notion")
        self.assertIn("database_id", datos["parametros"])
        self.assertIn("token_env", datos["parametros"])


class ConLosEstadosDeFabricaDeNotion(PruebaConNotion):
    """Una base recién creada en Notion: «Not started», «In progress», «Done», sin checkbox."""

    PROPIEDADES = {
        "Nombre": {"type": "title", "title": {}},
        "Estado": {"type": "status", "status": {"options": [
            {"name": "Not started"}, {"name": "In progress"}, {"name": "Done"}]}},
        "Agente": {"type": "rich_text", "rich_text": {}},
    }

    def sembrar(self):
        self.notion.tarea("Una", estado="Not started")
        self.notion.tarea("Otra", estado="In progress", agente="opus")
        self.notion.tarea("Vieja", estado="Done")

    def test_se_leen_sin_configurar_nada_y_el_proyecto_es_la_base(self):
        estados = {t["texto"]: (t["estado"], t["proyecto"])
                   for t in self.correr("tareas", "--todas")[1]["tareas"]}
        self.assertEqual(estados, {"Una": ("pendiente", "Tareas"),
                                   "Otra": ("en-curso", "Tareas"),
                                   "Vieja": ("hecha", "Tareas")})

    def test_tomar_escribe_la_opcion_que_la_base_tiene(self):
        identificador = self.por_texto("Una")["id"]
        self.assertEqual(len(identificador), 32)  # sin ID único, el de la página
        codigo, _ = self.correr("tomar", identificador, "--agente", "haiku")
        self.assertEqual(codigo, 0)
        self.assertEqual(self.notion.valor("Una", "Estado"), "In progress")
        self.assertEqual(self.notion.valor("Una", "Agente"), "haiku")

    def test_doctor_avisa_de_que_falta_por_validar(self):
        codigo, datos = self.correr("doctor")
        self.assertEqual(codigo, 3)
        self.assertIn("por-validar", datos["fuente"]["problema"])


class ConProyectosEnOtraBase(PruebaConNotion):
    """El proyecto es una relación a una página de otra base, como en muchas plantillas."""

    PROPIEDADES = {
        "Nombre": {"type": "title", "title": {}},
        "Estado": {"type": "select", "select": {"options": []}},
        "Agente": {"type": "select", "select": {"options": []}},
        "Proyecto": {"type": "relation", "relation": {}},
    }

    def sembrar(self):
        self.atlas = self.notion.pagina_suelta("Atlas")
        self.notion.tarea("Una", estado="Pendiente", proyecto=self.atlas)

    def test_el_proyecto_es_el_titulo_de_la_pagina_relacionada(self):
        tarea = self.por_texto("Una")
        self.assertEqual(tarea["proyecto"], "Atlas")

    def test_crear_en_ese_proyecto_lo_relaciona(self):
        codigo, datos = self.correr("crear", "Otra", "--proyecto", "Atlas")
        self.assertEqual(codigo, 0, datos)
        self.assertEqual(self.por_texto("Otra")["proyecto"], "Atlas")
