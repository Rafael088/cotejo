"""Config, bitácora de despachos, encargo y motores: las piezas de alrededor del reparto."""

import json
import os
import unittest
from pathlib import Path

from apoyo import PruebaDeEnrutador

from enrutador import bitacora, config as cfg, decision, encargo as enc, motor, niveles


def tarea(**cambios):
    base = {"id": "cotejo-a1b2", "texto": "Arreglar el parseo de los tags", "proyecto": "Cotejo",
            "estado": "pendiente", "agente": "", "dificultad": ""}
    base.update(cambios)
    return base


class Config(PruebaDeEnrutador):
    def test_vive_dentro_del_config_de_cotejo_y_no_en_uno_aparte(self):
        # Un solo archivo: el que elige la fuente es el mismo que ajusta el enrutador.
        self.escribir_config({"reglas_apagadas": ["compras"]}, fuera={"fuente": "obsidian"})
        self.assertEqual(cfg.cargar()["reglas_apagadas"], ["compras"])
        self.assertEqual(json.loads(self.config.read_text())["fuente"], "obsidian")

    def test_lo_que_no_escribes_conserva_su_defecto(self):
        # Sin la mezcla recursiva, tocar un timeout borraría el comando del motor.
        self.escribir_config({"motores": {"sesion": {"timeout_seg": 60}}})
        config = cfg.cargar()
        self.assertEqual(config["motores"]["sesion"]["timeout_seg"], 60)
        self.assertEqual(config["motores"]["sesion"]["comando"], ["claude"])

    def test_un_config_sin_la_clave_del_enrutador_no_es_un_error(self):
        self.config.write_text(json.dumps({"fuente": "obsidian"}), encoding="utf-8")
        self.assertEqual(cfg.cargar()["motor"], "agente")

    def test_una_config_rota_se_dice_en_vez_de_ignorarse(self):
        self.config.write_text("{esto no es json", encoding="utf-8")
        with self.assertRaises(cfg.ConfigInvalida):
            cfg.cargar()

    def test_las_rutas_se_resuelven_al_llamar_y_no_al_importar(self):
        # Es lo que hace que un binario congelado y un HOME distinto no rompan nada.
        os.environ["COTEJO_CONFIG"] = "/tmp/otro-sitio/config.json"
        self.assertEqual(str(cfg.ruta_config()), "/tmp/otro-sitio/config.json")

    def test_el_motor_se_puede_fijar_por_entorno(self):
        # Es la red que impide que una prueba llame a un modelo por descuido.
        self.escribir_config({"motor": "headless"})
        os.environ["COTEJO_MOTOR"] = "simulado"
        config = cfg.cargar()
        self.assertEqual(config["motor"], "simulado")
        self.assertEqual(config["_origen"]["motor"], "COTEJO_MOTOR")

    def test_el_directorio_de_un_proyecto_expande_la_virgulilla(self):
        self.escribir_config({"proyectos": {"Cotejo": "~/repos/cotejo"}})
        ruta = cfg.directorio_de(cfg.cargar(), "Cotejo")
        self.assertTrue(str(ruta).startswith(str(Path.home())))
        self.assertIsNone(cfg.directorio_de(cfg.cargar(), "Otro"))

    def test_un_cliente_puede_registrar_un_modelo_sin_perder_el_resto_del_config(self):
        self.escribir_config({"motor": "agente"}, fuera={"fuente": "obsidian"})
        guardado, reemplazado = cfg.registrar_modelo({
            "clave": "luna", "nombre": "GPT 5.6 Luna",
            "modelo_id": "opencode-go/gpt-5.6-luna", "cliente": "opencode",
            "nivel": "n2",
        })
        self.assertFalse(reemplazado)
        self.assertEqual(guardado["clave"], "luna")
        entero = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(entero["fuente"], "obsidian")
        self.assertEqual(entero["enrutador"]["modelos"][0]["modelo_id"],
                         "opencode-go/gpt-5.6-luna")

    def test_un_modelo_registrado_se_resuelve_como_asignacion_explicita(self):
        propio = {"clave": "luna", "modelo_id": "opencode-go/gpt-5.6-luna",
                  "cliente": "opencode", "nivel": "n2"}
        nivel = niveles.personalizados([propio])
        elegida = decision.decidir("Arreglar el parseo", agente="luna", niveles_extra=nivel)
        self.assertEqual((elegida.por, elegida.nivel.modelo, elegida.nivel.modelo_id),
                         ("asignacion", "luna", "opencode-go/gpt-5.6-luna"))


class Bitacora(PruebaDeEnrutador):
    def test_anota_una_linea_por_despacho(self):
        self.assertEqual(bitacora.anotar(tarea="a", modelo="opus"), "")
        self.assertEqual(bitacora.anotar(tarea="b", modelo="haiku"), "")
        self.assertEqual([d["tarea"] for d in bitacora.ultimos()], ["a", "b"])

    def test_esta_aparte_de_la_bitacora_de_las_tareas(self):
        # Aquella cuenta qué pasó con la tarea y la lee el board; esta, qué pasó con el
        # reparto. Mezclarlas obligaría al board a saber qué es un modelo.
        bitacora.anotar(tarea="a", modelo="opus")
        self.assertNotEqual(bitacora.ruta(), self.bitacora)
        self.assertEqual(self.operaciones(), [])

    def test_la_salida_larga_se_recorta_y_se_dice(self):
        bitacora.anotar(tarea="a", salida="x" * 5000)
        ultimo = bitacora.ultimos()[-1]
        self.assertTrue(ultimo["salida_recortada"])
        self.assertLess(len(ultimo["salida"]), 1000)

    def test_si_no_se_puede_escribir_se_devuelve_el_problema_en_vez_de_romper(self):
        # El despacho ya ocurrió: la tarea está tomada y el modelo trabajando. Pero el fallo
        # tampoco puede desaparecer en silencio, así que sale como aviso.
        from unittest import mock
        with mock.patch.object(bitacora, "ARCHIVO", Path("/proc/no-se-puede/escribir.jsonl")):
            self.assertIn("No pude anotar", bitacora.anotar(tarea="a"))

    def test_una_linea_rota_no_se_lleva_por_delante_el_resto(self):
        bitacora.anotar(tarea="a")
        with open(bitacora.ruta(), "a", encoding="utf-8") as archivo:
            archivo.write("{esto no es json\n")
        bitacora.anotar(tarea="b")
        self.assertEqual(len(bitacora.ultimos()), 2)

    def test_se_pueden_pedir_los_de_una_sola_tarea(self):
        bitacora.anotar(tarea="a")
        bitacora.anotar(tarea="b")
        self.assertEqual(len(bitacora.ultimos(tarea_id="a")), 1)


class Encargo(unittest.TestCase):
    def armar(self, **cambios):
        t = tarea(**cambios)
        return enc.armar(t, decision.de_tarea(t))

    def test_trae_lo_que_el_modelo_tendria_que_preguntar(self):
        texto = self.armar()
        for esperado in ("cotejo-a1b2", "Cotejo", "Arreglar el parseo"):
            self.assertIn(esperado, texto)

    def test_dice_por_que_le_toco_a_el(self):
        self.assertIn("Te tocó a ti porque", self.armar(agente="opus"))

    def test_una_tarea_devuelta_lleva_el_motivo_por_delante(self):
        # Sin esto, el agente rehace lo mismo y se lo devuelven otra vez.
        texto = self.armar(motivo="Faltaban las pruebas")
        self.assertIn("Faltaban las pruebas", texto)
        self.assertIn("antes de rehacerla", texto)

    def test_siempre_dice_como_entregar_y_que_no_marque_hecha(self):
        texto = self.armar()
        self.assertIn("entregar cotejo-a1b2 --evidencia", texto)
        self.assertIn("bloquear cotejo-a1b2 --motivo", texto)
        self.assertIn("No la marques como hecha", texto)

    def test_la_nota_de_quien_reparte_viaja_y_se_lee_aparte(self):
        # El caso que la pidió: la tarea decía «crear el repo» y el repo ya existía. Sin sitio
        # donde decirlo, despachar tal cual es pedir que se rehaga trabajo bueno.
        t = tarea()
        texto = enc.armar(t, decision.de_tarea(t), nota="Ya está hecho: verifícalo y entrégalo")
        self.assertIn("Ya está hecho", texto)
        self.assertIn("no está en su enunciado", texto)
        # Y sin nota, el encargo no habla de notas.
        self.assertNotIn("quien te reparte", enc.armar(t, decision.de_tarea(t)))

    def test_no_le_dice_como_hacer_la_tarea(self):
        # Quien decide cómo es el modelo; para eso se eligió uno u otro.
        self.assertNotIn("paso 1", self.armar().lower())


class Motores(PruebaDeEnrutador):
    def test_el_registro_es_explicito_para_que_sobreviva_a_compilarse(self):
        # Un importlib que recorra la carpeta deja de encontrar los módulos dentro de un binario.
        self.assertEqual(sorted(motor.registro()),
                         ["agente", "headless", "sesion", "simulado"])

    def test_el_defecto_no_lanza_ningun_proceso(self):
        # Que el defecto sea `agente` es la diferencia entre «el enrutador manda el trabajo a un
        # proceso que nadie ve» y «el enrutador le dice a quien está trabajando qué le toca».
        self.assertEqual(cfg.DEFECTOS["motor"], "agente")
        resultado = motor.abrir("agente", cfg.cargar()).ejecutar(
            motor.Encargo(prompt="haz esto", modelo="opus"))
        self.assertFalse(resultado.ejecutado)
        self.assertEqual(resultado.comando, [])
        self.assertEqual(resultado.salida, "haz esto")

    def test_una_sesion_se_abre_con_bg_y_con_su_modelo(self):
        # `--bg` abre una sesión completa que se puede abrir y dirigir, no un `-p` que corre
        # solo. El alias va en --model para que siga apuntando al modelo vigente.
        argv = motor.abrir("sesion", cfg.cargar()).argv(
            motor.Encargo(prompt="haz esto", modelo="opus", modelo_id="claude-opus-5"))
        self.assertEqual(argv[:4], ["claude", "--bg", "--model", "opus"])
        self.assertNotIn("-p", argv)
        self.assertNotIn("claude-opus-5", argv)

    def test_el_id_de_la_instancia_se_lee_de_la_salida_de_verdad(self):
        # Esta es la salida literal de `claude --bg`, con sus códigos de color. La primera
        # versión de la expresión devolvía None contra ella: los colores llevan dígitos dentro
        # (ESC[36m) y se comía el «36» como si fuera el identificador.
        from enrutador.motores.sesion import identificador
        real = "backgrounded · \x1b[36m2a3a10f4\x1b[39m\n\x1b[2m  claude agents\x1b[22m"
        self.assertEqual(identificador(real), "2a3a10f4")
        self.assertEqual(identificador("no arrancó nada"), "")

    def test_el_headless_sigue_existiendo_pero_hay_que_pedirlo(self):
        argv = motor.abrir("headless", cfg.cargar()).argv(
            motor.Encargo(prompt="haz esto", modelo="sonnet"))
        self.assertEqual(argv[:4], ["claude", "-p", "--model", "sonnet"])
        self.assertNotEqual(cfg.DEFECTOS["motor"], "headless")

    def test_el_simulado_no_ejecuta_nada_pero_dice_que_habria_corrido(self):
        resultado = motor.abrir("simulado", cfg.cargar()).ejecutar(
            motor.Encargo(prompt="haz esto", modelo="haiku"))
        self.assertFalse(resultado.ejecutado)
        self.assertIn("--model", resultado.comando)

    def test_si_falta_el_ejecutable_se_dice_que_hacer_y_ese_que_hacer_existe(self):
        # La versión anterior de esta prueba armaba el texto esperado y no lo comprobaba: el
        # mensaje mandaba a un `--motor imprimir` que no existe desde hace dos versiones.
        motores = sorted(motor.registro())
        for nombre in ("headless", "sesion"):
            with self.subTest(motor=nombre):
                self.escribir_config({"motores": {nombre: {"comando": ["no-existe-esto"]}}})
                resultado = motor.abrir(nombre, cfg.cargar()).ejecutar(
                    motor.Encargo(prompt="x", modelo="opus"))
                self.assertFalse(resultado.ok)
                nombrados = [m for m in motores if f"--motor {m}" in resultado.error]
                self.assertTrue(nombrados, f"«{resultado.error}» no propone ningún motor real")

    def test_un_motor_inventado_dice_cuales_hay(self):
        with self.assertRaises(motor.MotorDesconocido) as caso:
            motor.abrir("telepatia", cfg.cargar())
        self.assertIn("agente", str(caso.exception))


if __name__ == "__main__":
    unittest.main()
