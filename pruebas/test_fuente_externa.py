"""Una fuente que es otro programa: los verbos de siempre contra un adaptador por subproceso.

El adaptador es la plantilla de `extras/plantilla/`, que guarda las tareas en un JSON: así
estas pruebas miden el contrato —lo que Cotejo manda y lo que entiende de vuelta— sin depender
de ninguna app de verdad. Las de Notion están en `test_notion.py`.
"""

import json
import sys
from unittest import mock

from apoyo import RAIZ, PruebaDeCLI
from tareas import estado, fuente as f, modelo
from tareas.fuentes.externa import Externa

PLANTILLA = RAIZ / "extras" / "plantilla" / "cotejo_plantilla.py"


def tarea(identificador, texto, **resto):
    return {"id": identificador, "texto": texto, "estado": "pendiente", "agente": "",
            "dificultad": "", "hecha": False, **resto}


class PruebaConAdaptador(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.archivo = self.vault / "tareas.json"
        self.guardar_tareas([{"nombre": "Casa", "url": "https://app/casa", "tareas": [
            tarea("casa-1", "Pintar la reja", url="https://app/casa-1"),
            tarea("casa-2", "Arreglar el grifo", estado="en-curso", agente="sonnet"),
            tarea("casa-3", "Comprar pintura", hecha=True),
        ]}])
        self.params = {"tipo": "externa", "comando": [sys.executable, str(PLANTILLA)],
                       "archivo": str(self.archivo)}
        self.escribir_config({"fuente": "demo", "fuentes": {"demo": self.params}})

    def guardar_tareas(self, proyectos):
        self.archivo.write_text(json.dumps({"proyectos": proyectos}), encoding="utf-8")

    def leer_tareas(self):
        datos = json.loads(self.archivo.read_text(encoding="utf-8"))
        return {t["id"]: t for p in datos["proyectos"] for t in p["tareas"]}

    def escribir_config(self, datos):
        self.config.write_text(json.dumps(datos), encoding="utf-8")

    def externa(self, **cambios):
        return Externa("demo", {**self.params, **cambios})


class LosVerbosDeSiempre(PruebaConAdaptador):
    def test_tareas_lee_lo_que_dice_el_adaptador(self):
        codigo, datos = self.correr("tareas", "--todas")
        self.assertEqual(codigo, 0)
        estados = {t["id"]: t["estado"] for t in datos["tareas"]}
        self.assertEqual(estados, {"casa-1": "pendiente", "casa-2": "en-curso",
                                   "casa-3": "hecha"})
        self.assertEqual(datos["tareas"][0]["proyecto"], "Casa")

    def test_tomar_y_entregar_escriben_en_la_app_y_la_evidencia_en_la_bitacora(self):
        self.correr("tomar", "casa-1", "--agente", "haiku")
        codigo, datos = self.correr("entregar", "casa-1", "--evidencia", "reja pintada, foto")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["estado"], "por-validar")
        guardada = self.leer_tareas()["casa-1"]
        self.assertEqual((guardada["estado"], guardada["agente"]), ("por-validar", "haiku"))
        # El texto libre es de Cotejo: no viaja a la app de fuera.
        self.assertNotIn("reja pintada", self.archivo.read_text(encoding="utf-8"))
        self.assertEqual(self.operaciones()[-1]["evidencia"], "reja pintada, foto")

    def test_bloquear_la_suelta_con_su_motivo(self):
        codigo, datos = self.correr("bloquear", "casa-2", "--motivo", "falta la llave inglesa")
        self.assertEqual(codigo, 0)
        guardada = self.leer_tareas()["casa-2"]
        self.assertEqual((guardada["estado"], guardada["agente"]), ("pendiente", ""))

    def test_tomar_dos_veces_no_escribe_la_segunda(self):
        self.correr("tomar", "casa-1", "--agente", "haiku")
        antes = self.archivo.stat().st_mtime_ns
        codigo, datos = self.correr("tomar", "casa-1", "--agente", "haiku")
        self.assertEqual((codigo, datos["cambio"]), (0, False))
        self.assertEqual(self.archivo.stat().st_mtime_ns, antes)

    def test_crear_pasa_por_el_adaptador_y_no_duplica(self):
        codigo, datos = self.correr("crear", "Cambiar el foco", "--proyecto", "Casa")
        self.assertEqual((codigo, datos["cambio"]), (0, True))
        self.assertIn(datos["tarea"]["id"], self.leer_tareas())
        _, otra = self.correr("crear", "Cambiar el foco", "--proyecto", "Casa")
        self.assertFalse(otra["cambio"])

    def test_el_id_se_acepta_en_mayusculas(self):
        codigo, datos = self.correr("tomar", "CASA-1", "--agente", "haiku")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["id"], "casa-1")

    def test_el_ahorro_cuenta_lo_que_el_adaptador_dice_que_leyo(self):
        with mock.patch("tareas.ahorro.anotar") as anotar:
            self.correr("tareas")
        _, leido = anotar.call_args.args
        self.assertEqual(leido, len(self.archivo.read_text(encoding="utf-8")))


class EscribirVerificado(PruebaConAdaptador):
    def test_si_la_tocaron_en_la_app_despues_de_leerla_no_se_escribe(self):
        fuente = self.externa()
        proyecto = fuente.escanear()[0]
        leida = next(t for t in proyecto.tareas if t.id == "casa-1")
        # Una persona la toma en la app mientras Cotejo la tenía leída.
        datos = json.loads(self.archivo.read_text(encoding="utf-8"))
        datos["proyectos"][0]["tareas"][0]["agente"] = "rafael"
        self.archivo.write_text(json.dumps(datos), encoding="utf-8")
        with self.assertRaises(modelo.TareaCambiada):
            fuente.poner_estado(leida, "en-curso")
        self.assertEqual(self.leer_tareas()["casa-1"]["estado"], "pendiente")

    def test_marcar_existe_para_el_board_pero_no_como_verbo(self):
        fuente = self.externa()
        leida = next(t for t in fuente.escanear()[0].tareas if t.id == "casa-1")
        hecha = fuente.marcar(leida, hecha=True)
        self.assertTrue(hecha.hecha)
        self.assertTrue(self.leer_tareas()["casa-1"]["hecha"])

    def test_la_url_de_la_app_es_como_se_abre(self):
        fuente = self.externa()
        proyecto = fuente.escanear()[0]
        self.assertEqual(fuente.uri(proyecto.tareas[0]), "https://app/casa-1")
        self.assertEqual(fuente.uri(proyecto), "https://app/casa")


class CuandoElAdaptadorFalla(PruebaConAdaptador):
    def test_un_comando_que_no_existe_se_dice_sin_lanzar_nada(self):
        fuente = self.externa(comando="cotejo-que-no-existe-jamas")
        self.assertIn("cotejo-que-no-existe-jamas", fuente.problema)

    def test_si_no_contesta_json_la_lista_no_dice_que_no_hay_nada(self):
        self.escribir_config({"fuente": "demo", "fuentes": {"demo": {
            **self.params, "comando": [sys.executable, "-c", "print('hola')"]}}})
        codigo, datos = self.correr("tareas")
        self.assertEqual(codigo, 3)
        self.assertIn("no contestó JSON", datos["salida"])
        # Un adaptador que contesta basura no se arregla repitiendo.
        self.assertFalse(datos["reintentable"])

    def test_un_error_del_adaptador_llega_con_su_salida(self):
        self.archivo.unlink()
        codigo, datos = self.correr("tareas")
        self.assertEqual(codigo, 3)
        self.assertIn("No existe", datos["salida"])

    def test_si_tarda_demasiado_es_reintentable(self):
        fuente = self.externa(comando=[sys.executable, "-c", "import time; time.sleep(5)"],
                              timeout_seg=0.3)
        with self.assertRaises(modelo.FuenteNoResponde) as error:
            fuente.llamar("escanear")
        self.assertTrue(error.exception.reintentable)

    def test_un_esquema_que_no_es_el_suyo_no_se_lee(self):
        fuente = self.externa(comando=[sys.executable, "-c",
                                       "print('{\"esquema\": 2, \"proyectos\": []}')"])
        self.assertEqual(fuente.escanear(), [])
        self.assertIn("esquema", fuente.problema)

    def test_un_estado_desconocido_se_lee_como_pendiente_y_se_avisa(self):
        self.guardar_tareas([{"nombre": "Casa", "tareas": [
            tarea("casa-1", "Algo", estado="bloqueada")]}])
        avisos = []
        proyecto = self.externa().escanear(avisos=avisos)[0]
        self.assertEqual(proyecto.tareas[0].estado, "pendiente")
        self.assertTrue(any("bloqueada" in a for a in avisos))

    def test_la_barra_ve_el_problema_en_vez_de_todo_al_dia(self):
        # Cero proyectos porque la app no contesta no puede verse como cero pendientes.
        self.escribir_config({"fuente": "demo", "fuentes": {"demo": {
            **self.params, "comando": [sys.executable, "-c", "print('hola')"]}}})
        resumen = estado.calcular()
        self.assertEqual(resumen["pendientes"], 0)
        self.assertIn("no contestó JSON", resumen["error"])
