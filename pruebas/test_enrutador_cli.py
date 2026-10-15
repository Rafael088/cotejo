"""Los verbos del enrutador, y sobre todo los que no existen.

Dos de estas pruebas no comprueban que algo funcione: comprueban que algo *siga sin existir*.
Una ausencia no se defiende sola —nadie revisa lo que no está— y las dos ausencias del
enrutador son las que sostienen que sus decisiones signifiquen algo.
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaDeEnrutador, proyecto

from enrutador import aislamiento, procesos, verbos


def verbos_del_enrutador():
    """Solo los que cuelga el enrutador, sin los de Cotejo."""
    sub = argparse.ArgumentParser().add_subparsers()
    verbos.anadir(sub)
    return sub.choices


class Ausencias(unittest.TestCase):
    def test_ningun_verbo_del_enrutador_entrega_ni_finaliza_tareas(self):
        # El enrutador reparte trabajo. Quien lo hizo dice qué hizo con `entregar`, que es de
        # Cotejo y lo llama quien la hace. Si el que reparte pudiera entregar, la evidencia
        # pasaría a significar «esto se mandó» en vez de «esto se hizo».
        mios = set(verbos_del_enrutador())
        for prohibido in ("entregar", "finalizar", "marcar", "hecha", "completar", "aprobar"):
            self.assertNotIn(prohibido, mios)

    def test_despachar_no_tiene_ninguna_bandera_para_forzar_una_tarea_humana(self):
        # `--modelo` fuerza el nivel, pero una tarea vetada no se despacha ni con él: se
        # comprueba en test_una_tarea_humana_no_se_puede_forzar. Aquí se vigila que no aparezca
        # una bandera nueva («--igual», «--forzar») que abra esa puerta por la espalda.
        despachar = verbos_del_enrutador()["despachar"]
        banderas = {o for accion in despachar._actions for o in accion.option_strings}
        for prohibida in ("--forzar", "--igual", "--humano", "-f"):
            self.assertNotIn(prohibida, banderas)


class SinTocarNada(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Comprar el dominio atlas.co ^cotejo-hum1",
            "- [ ] Arreglar el parseo de los tags #agente/haiku ^cotejo-asig",
            "- [ ] Rediseñar la capa Fuente #medio ^cotejo-prop",
        ))

    def test_modelos_trae_el_catalogo_entero(self):
        codigo, datos = self.correr("modelos")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual({n["modelo"] for n in datos["niveles"]},
                         {"humano", "haiku", "sonnet", "opus"})

    def test_modelos_agregar_deja_el_modelo_disponible_para_cualquier_cliente(self):
        codigo, agregado = self.correr(
            "modelos", "agregar", "--clave", "luna", "--nombre", "GPT 5.6 Luna",
            "--modelo-id", "opencode-go/gpt-5.6-luna", "--cliente", "opencode",
            "--nivel", "n2")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(agregado["modelo"]["clave"], "luna")
        _, catalogo = self.correr("modelos")
        luna = next(n for n in catalogo["niveles"] if n["modelo"] == "luna")
        self.assertEqual((luna["modelo_id"], luna["cliente"]),
                         ("opencode-go/gpt-5.6-luna", "opencode"))

    def test_decidir_un_texto_suelto_no_necesita_que_exista_la_tarea(self):
        codigo, datos = self.correr("decidir", "Comprar", "el", "dominio")
        self.assertEqual(codigo, verbos.OK)
        self.assertFalse(datos["decision"]["despachable"])
        self.assertEqual(datos["decision"]["regla"], "compras")

    def test_decidir_sin_nada_que_decidir_dice_como_se_usa(self):
        codigo, datos = self.correr("decidir")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("--tarea", datos["salida"])

    def test_plan_cuenta_cuantas_no_son_para_ningun_modelo(self):
        codigo, datos = self.correr("plan")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["por_modelo"]["humano"], 1)
        self.assertEqual(datos["despachables"], 2)

    def test_plan_dice_cuantas_esperan_que_alguien_elija_modelo(self):
        _, datos = self.correr("plan")
        porid = {t["id"]: t for t in datos["tareas"]}
        self.assertEqual(datos["sin_asignar"], 1)          # la de #medio
        self.assertTrue(porid["cotejo-asig"]["asignado"])    # el modelo lo puso una persona
        self.assertFalse(porid["cotejo-prop"]["asignado"])   # lo proponen las reglas
        self.assertFalse(porid["cotejo-hum1"]["asignado"])

    def test_mirar_no_escribe_en_las_notas(self):
        antes = self.leer_nota("Uno.md")
        self.correr("plan")
        self.correr("decidir", "--tarea", "cotejo-asig")
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.despachados(), [])

    def test_protocolo_imprime_markdown_sin_frontmatter(self):
        codigo, texto = self.correr_crudo("protocolo")
        self.assertEqual(codigo, verbos.OK)
        self.assertFalse(texto.startswith("---"))
        self.assertIn("cotejo entregar", texto)

    def test_el_protocolo_nombra_solo_verbos_que_existen(self):
        # Si alguien renombra un verbo y se olvida del protocolo, esta prueba se pone roja.
        from tareas import cli
        _, texto = self.correr_crudo("protocolo")
        existen = set(cli.analizador()._subparsers._group_actions[0].choices)
        # `cotejo` es el nombre público y `tareas-obsidian` el de antes: los dos son el mismo.
        for nombrado in set(re.findall(r"(?:cotejo|tareas-obsidian) (\w+)", texto)):
            self.assertIn(nombrado, existen, f"el protocolo nombra «{nombrado}», que no existe")

    def test_protocolo_completo_añade_las_referencias_y_el_nucleo_no(self):
        from tareas import skill
        _, nucleo = self.correr_crudo("protocolo")
        codigo, completo = self.correr_crudo("protocolo", "--completo")
        self.assertEqual(codigo, verbos.OK)
        self.assertGreater(len(completo), len(nucleo))
        self.assertTrue(completo.startswith(nucleo.rstrip("\n")))
        self.assertNotIn("--motor sesion", nucleo)
        self.assertIn("--motor sesion", completo)
        self.assertIn("cotejo contexto", completo)
        self.assertTrue(skill.referencias())


class Despachar(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Comprar el dominio atlas.co ^cotejo-hum1",
            "- [ ] Revisar los textos legales #agente/persona ^cotejo-hum2",
            "- [ ] Arreglar el parseo de los tags #agente/haiku ^cotejo-asig",
            "- [ ] Rediseñar la capa Fuente #medio ^cotejo-prop",
            "- [ ] Haciéndola ya #en-curso #agente/sonnet ^cotejo-curso",
        ))

    def test_una_tarea_humana_no_se_puede_forzar(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-hum1")
        self.assertEqual(codigo, verbos.HUMANO)
        self.assertIn("no hay bandera", datos["salida"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        # Y queda anotado: cuántas entregas falsas evitó el veto es la cifra que justifica
        # todo esto, y solo se puede contar si la negativa deja rastro.
        rechazo, = self.despachados()
        self.assertEqual((rechazo["rechazo"], rechazo["regla"], rechazo["tomada"]),
                         ("veto", "compras", False))

    def test_con_modelo_a_mano_si_sale_porque_es_una_persona_pidiendolo(self):
        # Lo que no existe es una bandera que salte el veto «porque sí»: `--modelo` es alguien
        # diciéndolo explícitamente y a la vista.
        codigo, datos = self.correr("despachar", "cotejo-hum1", "--modelo", "opus")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["decision"]["por"], "override")

    def test_el_veto_dice_como_rebatirse_segun_quien_lo_puso(self):
        # A quien la asignó a mano no se le puede mandar a apagar una regla que no existe.
        _, por_regla = self.correr("despachar", "cotejo-hum1")
        self.assertIn("apaga la regla «compras»", por_regla["salida"])
        _, por_asignacion = self.correr("despachar", "cotejo-hum2")
        self.assertIn("asignar cotejo-hum2", por_asignacion["salida"])
        self.assertNotIn("la regla «»", por_asignacion["salida"])

    def test_si_nadie_asigno_modelo_se_pregunta_antes_de_gastar(self):
        # Las reglas proponen; quien decide gastar es una persona. La tarea lleva #medio, así
        # que hay propuesta —sonnet—, y aun así no se despacha sola.
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-prop")
        self.assertEqual(codigo, verbos.FALTA_MODELO)
        self.assertIn("sonnet", datos["error"])             # la propuesta, para preguntarla
        self.assertIn("asignar cotejo-prop", datos["salida"])  # dónde se escribe la respuesta
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        # Con la propuesta que nadie contestó: eso es lo que después dirá si preguntar tanto
        # estaba justificado o si las reglas ya se podían creer.
        pregunta, = self.despachados()
        self.assertEqual((pregunta["rechazo"], pregunta["modelo"]), ("falta_modelo", "sonnet"))

    def test_simular_tampoco_esquiva_la_pregunta_del_modelo(self):
        # Simular es el ensayo de despachar: un ensayo que pasa donde el real fallaría no
        # sirve de ensayo. Para mirar sin que nadie se queje está `decidir`.
        self.assertEqual(self.correr("despachar", "cotejo-prop", "--simular")[0],
                         verbos.FALTA_MODELO)
        self.assertEqual(self.correr("decidir", "--tarea", "cotejo-prop")[0], verbos.OK)

    def test_simular_no_toma_la_tarea_ni_ejecuta_nada(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-asig", "--simular")
        self.assertEqual(codigo, verbos.OK)
        self.assertFalse(datos["tomada"])
        self.assertFalse(datos["ejecutado"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_una_tarea_asignada_en_la_nota_no_pregunta_nada(self):
        codigo, datos = self.correr("despachar", "cotejo-asig")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["decision"]["modelo"], "haiku")

    def test_despachar_toma_la_tarea_a_nombre_del_modelo_elegido(self):
        codigo, datos = self.correr("despachar", "cotejo-prop", "--auto")
        self.assertEqual(codigo, verbos.OK)
        self.assertTrue(datos["tomada"])
        nota = self.leer_nota("Uno.md")
        self.assertIn("#en-curso #agente/sonnet ^cotejo-prop", nota)
        self.assertEqual([o["operacion"] for o in self.operaciones()], ["tomar"])

    def test_el_encargo_lo_trae_el_motor_por_defecto_sin_lanzar_nada(self):
        _, datos = self.correr("despachar", "cotejo-asig")
        self.assertEqual(datos["motor"], "agente")
        self.assertFalse(datos["ejecutado"])
        self.assertIn("Arreglar el parseo", datos["salida"])
        self.assertIn("cotejo entregar", datos["salida"])

    def test_el_despacho_queda_anotado_con_su_porque(self):
        self.correr("despachar", "cotejo-asig")
        despacho, = self.despachados()
        self.assertEqual((despacho["tarea"], despacho["modelo"], despacho["por"]),
                         ("cotejo-asig", "haiku", "asignacion"))
        self.assertTrue(despacho["tomada"])

    def test_no_despacha_una_tarea_que_ya_tiene_dueno(self):
        codigo, datos = self.correr("despachar", "cotejo-curso")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("en-curso", datos["error"])
        self.assertEqual(self.despachados()[0]["rechazo"], "no_pendiente")

    def test_un_id_que_no_existe_se_puede_reintentar(self):
        codigo, datos = self.correr("despachar", "cotejo-zzzz")
        self.assertTrue(datos["reintentable"])
        self.assertEqual(codigo, verbos.ERROR)

    def test_todo_error_dice_que_hacer(self):
        for argumentos in (["despachar", "cotejo-hum1"], ["despachar", "cotejo-prop"],
                           ["despachar", "cotejo-zzzz"], ["decidir"]):
            with self.subTest(argumentos=argumentos):
                _, datos = self.correr(*argumentos)
                self.assertTrue(datos["salida"],
                                "un error sin salida le cuesta al agente otra vuelta")

    def test_si_no_se_puede_anotar_el_rechazo_se_dice_en_vez_de_perderse(self):
        # El rechazo es la decisión; si no se pudo dejar constancia de ella, eso no puede
        # desaparecer en el mismo sitio donde desaparecía antes el rechazo entero.
        from unittest import mock
        from enrutador import bitacora
        with mock.patch.object(bitacora, "ARCHIVO", Path("/proc/no-se-puede/escribir.jsonl")):
            codigo, datos = self.correr("despachar", "cotejo-hum1")
        self.assertEqual(codigo, verbos.HUMANO)
        self.assertTrue(any("No pude anotar" in a for a in datos["avisos"]))

    def test_un_motor_inventado_no_toca_la_tarea(self):
        # El motor se abre antes de tomar la tarea justamente para esto: si no hay a dónde
        # mandarla, no se tocó nada.
        antes = self.leer_nota("Uno.md")
        codigo, _ = self.correr("despachar", "cotejo-asig", "--motor", "telepatia")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertEqual(self.leer_nota("Uno.md"), antes)



class DespacharHeadless(PruebaDeEnrutador):
    """El headless se anota al lanzarlo, con su pid, y no solo al terminar (cotejo-uxaj6m).

    El cliente es un script de mentira que mira la bitácora mientras corre: si la línea del
    lanzamiento no está ahí antes de que él termine, un headless que muere a medias no deja
    ningún rastro, que es justo lo que se arregla.
    """

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Arreglar el parseo #agente/sonnet ^cotejo-hl"))
        cliente = self.vault / "cliente-falso"
        cliente.write_text(
            "#!/bin/sh\n"
            f"grep -q '\"fase\": \"lanzado\"' '{self.despachos}' && echo 'ya estaba anotado'\n",
            encoding="utf-8")
        cliente.chmod(0o755)
        # «aislar: False»: esta prueba vigila el orden pid-antes-de-terminar, no el aislamiento
        # (que tiene su propia batería más abajo). Envolver este cliente con systemd-run metería
        # una carrera de verdad entre el `al_lanzar` de Python y el exec de systemd-run contra el
        # propio grep del script, y no es eso lo que aquí se comprueba.
        self.escribir_config({"motores": {"headless": {"comando": [str(cliente)], "aislar": False}}})

    @unittest.skipUnless(sys.platform.startswith("linux"), "el cliente falso es un script sh")
    def test_queda_anotado_con_su_pid_antes_de_terminar(self):
        codigo, datos = self.correr("despachar", "cotejo-hl", "--motor", "headless")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertEqual(datos["salida"], "ya estaba anotado")
        lanzado, terminado = self.despachados()
        self.assertEqual((lanzado["fase"], terminado["fase"]), ("lanzado", "terminado"))
        self.assertEqual(lanzado["pid"], terminado["pid"])
        self.assertEqual(lanzado["pid"], datos["pid"])
        self.assertEqual(lanzado["host"], socket.gethostname())
        self.assertTrue(lanzado["tomada"])
        self.assertNotIn("ok", lanzado)   # aún no se sabe cómo acabó

    def test_los_demas_motores_no_anotan_lanzamiento(self):
        self.correr("despachar", "cotejo-hl")
        despacho, = self.despachados()
        self.assertNotIn("fase", despacho)


class SimularConMotorExplicito(PruebaDeEnrutador):
    """`--simular` es el ensayo de cualquier motor, incluido el que pide `--motor`.

    `--motor headless --simular` lanzaba el cliente de verdad (cotejo-gh65rr, visto con
    `opencode run` y kimi) y `--motor agente --simular` tomaba la tarea igual (cotejo-katop4):
    en los dos, `--motor` ganaba la resolución del motor y `--simular` se quedaba sin efecto.
    El cliente es el mismo script de mentira que `DespacharHeadless`, pero aquí lo que importa
    es que **no se ejecute en absoluto**: si corriera, dejaría la marca.
    """

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Arreglar el parseo #agente/sonnet ^cotejo-sim"))
        self.marca = self.vault / "se-lanzo"
        cliente = self.vault / "cliente-falso"
        cliente.write_text(f"#!/bin/sh\ntouch '{self.marca}'\necho hecho\n", encoding="utf-8")
        cliente.chmod(0o755)
        self.escribir_config({"motores": {
            "headless": {"comando": [str(cliente)]},
            "sesion": {"comando": [str(cliente)]},
        }})

    @unittest.skipUnless(sys.platform.startswith("linux"), "el cliente falso es un script sh")
    def test_simular_con_motor_headless_no_toma_ni_lanza_el_cliente(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-sim", "--motor", "headless", "--simular")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertFalse(datos["tomada"])
        self.assertFalse(datos["ejecutado"])
        self.assertEqual(datos["motor"], "headless")
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertFalse(self.marca.exists(), "el ensayo lanzó el cliente de verdad")
        self.assertIn(str(self.vault / "cliente-falso"), " ".join(datos["comando"]))
        despacho, = self.despachados()
        self.assertFalse(despacho["tomada"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "el cliente falso es un script sh")
    def test_simular_con_motor_sesion_no_toma_ni_abre_la_instancia(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-sim", "--motor", "sesion", "--simular")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertFalse(datos["tomada"])
        self.assertFalse(datos["ejecutado"])
        self.assertEqual(datos["motor"], "sesion")
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertFalse(self.marca.exists(), "el ensayo abrió la instancia de verdad")
        self.assertIn(str(self.vault / "cliente-falso"), " ".join(datos["comando"]))

    def test_simular_con_motor_agente_no_toma_la_tarea(self):
        # `agente` nunca lanza un proceso, lo pida quien lo pida: el bug de cotejo-katop4 no
        # estaba en ejecutar, sino en tomar la tarea antes de preguntarle nada al motor.
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("despachar", "cotejo-sim", "--motor", "agente", "--simular")
        self.assertEqual(codigo, verbos.OK, datos)
        self.assertFalse(datos["tomada"])
        self.assertFalse(datos["ejecutado"])
        self.assertEqual(datos["motor"], "agente")
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        despacho, = self.despachados()
        self.assertFalse(despacho["tomada"])

    def test_simular_con_headless_sigue_fallando_si_el_cliente_no_esta(self):
        # El ensayo falla donde fallaría el real: `comprobar()` del motor pedido corre también
        # con --simular, y si el cliente no está la tarea tampoco se toca.
        from unittest import mock
        with mock.patch("enrutador.motores.claude_cli.shutil.which", return_value=None):
            codigo, datos = self.correr("despachar", "cotejo-sim", "--motor", "headless",
                                        "--simular")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("#agente/sonnet", self.leer_nota("Uno.md"))
        self.assertNotIn("#en-curso", self.leer_nota("Uno.md"))
        self.assertEqual(self.despachados()[-1]["rechazo"], "motor")


NECESITA_SYSTEMD = "necesita un systemd de usuario que conteste (systemctl --user is-system-running)"


class DespacharHeadlessAislado(PruebaDeEnrutador):
    """El headless aislado corre en su propio scope de systemd, y sigue contando como vivo
    (cotejo-flccw4).

    `despachar` bloquea hasta que el cliente termina (`Popen.communicate()`), así que para
    mirarlo desde fuera mientras sigue vivo hace falta despacharlo en un hilo aparte y sondear
    la bitácora hasta ver la línea «lanzado»; el cliente duerme un segundo para dar tiempo a eso.

    Se corre contra el systemd de verdad de esta máquina, no contra uno simulado: es la forma
    de comprobar, en la batería y no solo a mano, que `revisar` no daría por perdida una tarea
    que un OOM no se llevó (el riesgo que señaló cotejo-flccw4: si `al_lanzar` anotara el argv
    de systemd-run en vez del del cliente, `procesos.vivo` compararía contra el programa
    equivocado justo cuando el proceso sigue corriendo).
    """

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Arreglar el parseo #agente/sonnet ^cotejo-hl"))
        self.cliente = self.vault / "cliente-lento"
        self.cliente.write_text("#!/bin/sh\nsleep 1\n", encoding="utf-8")
        self.cliente.chmod(0o755)

    def despachar_en_hilo(self):
        resultado = {}

        def ir():
            resultado["valor"] = self.correr("despachar", "cotejo-hl", "--motor", "headless")

        hilo = threading.Thread(target=ir)
        hilo.start()
        return hilo, resultado

    def esperar(self, condicion, tope=3.0, mensaje="no se cumplió a tiempo"):
        """Sondea hasta que `condicion()` sea verdad, en vez de una espera fija y frágil.

        Hace falta para `procesos.vivo`: `al_lanzar` anota el pid en cuanto `Popen` vuelve del
        `fork`, que es antes de que systemd-run termine su ida y vuelta por D-Bus y haga el exec
        final hacia el cliente. Mientras tanto `/proc/<pid>/cmdline` todavía puede decir
        «systemd-run» un instante, y comprobarlo justo ahí sería una carrera de verdad y no un
        reflejo de qué ve `revisar`, que corre bastante después de lanzar.
        """
        fin = time.monotonic() + tope
        while time.monotonic() < fin:
            if condicion():
                return
            time.sleep(0.02)
        self.fail(mensaje)

    def esperar_lanzamiento(self, tope=5.0):
        fin = time.monotonic() + tope
        while time.monotonic() < fin:
            lineas = self.despachados()
            if lineas and lineas[0].get("fase") == "lanzado":
                return lineas[0]
            time.sleep(0.02)
        self.fail("nunca se anotó el lanzamiento")

    @unittest.skipUnless(aislamiento.disponible(), NECESITA_SYSTEMD)
    def test_sigue_vivo_bajo_systemd_run_con_el_pid_y_el_programa_del_cliente(self):
        self.escribir_config({"motores": {"headless": {
            "comando": [str(self.cliente)], "aislar": True, "memoria_max": "200M"}}})
        unidad = f"cotejo-prueba-aislamiento-{os.getpid()}"
        with mock.patch.object(aislamiento, "_nombre_unidad", return_value=unidad):
            hilo, resultado = self.despachar_en_hilo()
            try:
                lanzado = self.esperar_lanzamiento()
                # El cliente, no «systemd-run»: es justo lo que evita que `procesos.vivo`
                # compare contra el programa equivocado mientras el proceso sigue corriendo.
                self.assertEqual(Path(lanzado["programa"]).name, self.cliente.name)
                self.esperar(
                    lambda: procesos.vivo(lanzado["pid"], lanzado["programa"]),
                    mensaje="el pid anotado nunca contó como vivo con systemd-run de por medio")
                mostrado = subprocess.run(
                    ["systemctl", "--user", "show", f"{unidad}.scope", "-p", "MemoryMax"],
                    capture_output=True, text=True, timeout=5).stdout.strip()
                self.assertEqual(mostrado, "MemoryMax=209715200")  # 200M, de la config
            finally:
                hilo.join(timeout=5)
        self.assertEqual(resultado["valor"][0], verbos.OK, resultado["valor"])

    @unittest.skipUnless(aislamiento.disponible(), NECESITA_SYSTEMD)
    def test_con_aislar_en_false_no_pasa_por_systemd_run(self):
        self.escribir_config({"motores": {"headless": {
            "comando": [str(self.cliente)], "aislar": False}}})
        hilo, resultado = self.despachar_en_hilo()
        try:
            lanzado = self.esperar_lanzamiento()
            cgroup = Path(f"/proc/{lanzado['pid']}/cgroup").read_text()
            self.assertNotIn("cotejo-headless-", cgroup)
        finally:
            hilo.join(timeout=5)
        self.assertEqual(resultado["valor"][0], verbos.OK, resultado["valor"])


class Aislamiento(unittest.TestCase):
    """`envolver` decide si antepone systemd-run; aquí se mockea si lo hay o no de verdad."""

    COMANDO = ["claude", "-p", "haz esto"]

    def test_antepone_systemd_run_con_el_tope_y_la_politica_de_oom(self):
        with mock.patch.object(aislamiento, "disponible", return_value=True):
            argv = aislamiento.envolver(self.COMANDO, {"memoria_max": "1G"}, "cotejo-xyz")
        self.assertEqual(argv[:4], ["systemd-run", "--user", "--scope", "--quiet"])
        self.assertIn("MemoryMax=1G", argv)
        self.assertIn("OOMPolicy=continue", argv)
        self.assertIn("--", argv)
        self.assertEqual(argv[-len(self.COMANDO):], self.COMANDO)

    def test_usa_el_defecto_de_memoria_si_la_config_no_dice_nada(self):
        with mock.patch.object(aislamiento, "disponible", return_value=True):
            argv = aislamiento.envolver(self.COMANDO, {})
        self.assertIn("MemoryMax=50%", argv)

    def test_aislar_en_false_apaga_incluso_si_hay_systemd(self):
        with mock.patch.object(aislamiento, "disponible", return_value=True):
            argv = aislamiento.envolver(self.COMANDO, {"aislar": False})
        self.assertEqual(argv, self.COMANDO)

    def test_sin_systemd_run_se_lanza_igual_que_antes(self):
        with mock.patch.object(aislamiento, "disponible", return_value=False):
            argv = aislamiento.envolver(self.COMANDO, {})
        self.assertEqual(argv, self.COMANDO)

    def test_disponible_es_falso_fuera_de_linux(self):
        with mock.patch.object(aislamiento.sys, "platform", "win32"):
            self.assertFalse(aislamiento.disponible())

    def test_disponible_es_falso_sin_el_binario_en_el_path(self):
        with mock.patch.object(aislamiento.shutil, "which", return_value=None):
            self.assertFalse(aislamiento.disponible())

    def test_disponible_es_falso_si_la_sesion_no_contesta(self):
        with mock.patch.object(aislamiento.shutil, "which", return_value="/usr/bin/systemd-run"), \
                mock.patch.object(aislamiento.subprocess, "run", side_effect=OSError()):
            self.assertFalse(aislamiento.disponible())

    def test_dos_lanzamientos_de_la_misma_tarea_no_chocan_de_nombre(self):
        self.assertNotEqual(aislamiento._nombre_unidad("cotejo-xyz"),
                            aislamiento._nombre_unidad("cotejo-xyz"))


class Revisar(PruebaDeEnrutador):
    """Cruzar lo que se repartió con dónde está hoy la tarea. Es lo que cierra el lazo."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Entregada #por-validar #agente/opus ^cotejo-entregada",
            "- [ ] Trabajándola #en-curso #agente/sonnet ^cotejo-curso",
            "- [ ] Devuelta, volvió a pendiente ^cotejo-vuelta",
            "- [ ] La tiene otro #en-curso #agente/haiku ^cotejo-otro",
            "- [x] Comprobada ^cotejo-hecha",
            "- [ ] En curso sin pasar por aquí #en-curso #agente/persona ^cotejo-ajena",
        ))

    def anotar(self, tarea, modelo="sonnet", hace_dias=0, **extra):
        """Una línea en la bitácora de despachos, con la antigüedad que haga falta."""
        linea = {"esquema": 1, "ts": int(time.time()) - int(hace_dias * 86400),
                 "tarea": tarea, "proyecto": "Uno", "nivel": "n2", "modelo": modelo,
                 "por": "asignacion", "regla": "", "motor": "agente", "tomada": True,
                 "ok": True, **extra}
        with open(self.despachos, "a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(linea, ensure_ascii=False) + "\n")

    def revisar(self, *extra):
        codigo, datos = self.correr("revisar", *extra)
        self.assertEqual(codigo, verbos.OK)
        return datos

    def desenlaces(self, datos):
        return {f["tarea"]: f["desenlace"] for f in datos["repartidas"]}

    def test_dice_en_que_acabo_cada_cosa_que_reparte(self):
        self.anotar("cotejo-entregada", "opus")
        self.anotar("cotejo-hecha")
        self.anotar("cotejo-vuelta")
        self.anotar("cotejo-curso")
        self.assertEqual(self.desenlaces(self.revisar()),
                         {"cotejo-entregada": "entregada", "cotejo-hecha": "comprobada",
                          "cotejo-vuelta": "devuelta", "cotejo-curso": "trabajando"})

    def test_lo_que_lleva_dias_tomado_y_nadie_movio_esta_colgado(self):
        # Es para lo que existe el verbo: nadie la entregó, nadie la devolvió, y no hay otro
        # sitio donde eso se vea.
        self.anotar("cotejo-curso", hace_dias=5)
        datos = self.revisar()
        colgada, = datos["repartidas"]
        self.assertEqual(colgada["desenlace"], "colgada")
        self.assertEqual(colgada["dias"], 5.0)
        # Y el umbral se puede mover, porque «cuánto es demasiado» depende del trabajo.
        self.assertEqual(self.desenlaces(self.revisar("--dias", "9")),
                         {"cotejo-curso": "trabajando"})

    def test_una_devuelta_trae_el_motivo_que_es_lo_que_dice_si_el_ruteo_fallo(self):
        self.correr("bloquear", "cotejo-curso", "--motivo", "esto era para una persona")
        self.anotar("cotejo-curso")
        devuelta, = self.revisar()["repartidas"]
        self.assertEqual(devuelta["desenlace"], "devuelta")
        self.assertIn("para una persona", devuelta["motivo"])

    def test_si_la_tiene_otro_modelo_se_dice_en_vez_de_darla_por_buena(self):
        self.anotar("cotejo-otro", modelo="sonnet")
        self.assertEqual(self.desenlaces(self.revisar()), {"cotejo-otro": "reasignada"})

    def test_un_id_que_dejo_de_resolver_se_dice_en_vez_de_esconderse(self):
        self.anotar("01-Proyectos/Uno.md:7")
        self.assertEqual(self.desenlaces(self.revisar()), {"01-Proyectos/Uno.md:7": "perdida"})

    def test_lo_que_esta_en_curso_sin_haber_pasado_por_aqui_tambien_se_ve(self):
        # No es un error, pero es la diferencia entre «el enrutador reparte el trabajo» y
        # «reparte parte del trabajo», y no se ve en ningún otro sitio.
        self.anotar("cotejo-curso")
        datos = self.revisar()
        ajenas = {t["tarea"] for t in datos["en_curso_sin_despacho"]}
        self.assertEqual(ajenas, {"cotejo-otro", "cotejo-ajena"})

    def test_cuenta_los_rechazos_que_es_lo_que_el_veto_ahorro(self):
        self.correr("despachar", "cotejo-vuelta", "--modelo", "humano")   # veto
        self.correr("despachar", "cotejo-vuelta")                          # falta modelo
        resumen = self.revisar()["resumen"]
        self.assertEqual(resumen["rechazos"], {"veto": 1, "falta_modelo": 1})
        self.assertEqual(resumen["repartidas"], 0)

    def test_un_ensayo_no_cuenta_como_reparto(self):
        self.correr("despachar", "cotejo-vuelta", "--modelo", "opus", "--simular")
        resumen = self.revisar()["resumen"]
        self.assertEqual((resumen["ensayos"], resumen["repartidas"]), (1, 0))

    def test_solo_se_queda_el_ultimo_despacho_de_cada_tarea(self):
        # Una tarea devuelta y vuelta a repartir cuenta una vez, con lo último que le pasó.
        self.anotar("cotejo-curso", "haiku", hace_dias=4)
        self.anotar("cotejo-curso", "sonnet", hace_dias=0)
        fila, = self.revisar()["repartidas"]
        self.assertEqual((fila["modelo"], fila["desenlace"]), ("sonnet", "trabajando"))

    def test_lo_que_pide_que_alguien_mire_va_primero(self):
        self.anotar("cotejo-hecha")
        self.anotar("cotejo-curso", hace_dias=5)
        self.assertEqual([f["desenlace"] for f in self.revisar()["repartidas"]],
                         ["colgada", "comprobada"])

    def test_se_puede_mirar_un_solo_proyecto(self):
        self.escribir_nota("Dos.md", proyecto("- [ ] De otro #en-curso #agente/opus ^cotejo-dos"))
        self.anotar("cotejo-curso")
        self.anotar("cotejo-dos", "opus", proyecto="Dos")
        self.assertEqual(list(self.desenlaces(self.revisar("--proyecto", "Dos"))), ["cotejo-dos"])


    # --- headless que murió sin volver (cotejo-uxaj6m) -------------------------------------

    def pid_muerto(self):
        proceso = subprocess.Popen([sys.executable, "-c", "pass"])
        proceso.wait()
        return proceso.pid

    def test_un_headless_cuyo_proceso_ya_no_existe_esta_perdido(self):
        self.anotar("cotejo-curso", motor="headless", fase="lanzado", pid=self.pid_muerto(),
                    programa="claude", host=socket.gethostname())
        fila, = self.revisar()["repartidas"]
        self.assertEqual(fila["desenlace"], "perdida")
        self.assertIn("proceso", fila["por_que"])

    def test_un_headless_vivo_sigue_trabajando(self):
        self.anotar("cotejo-curso", motor="headless", fase="lanzado", pid=os.getpid(),
                    programa=sys.executable, host=socket.gethostname())
        self.assertEqual(self.desenlaces(self.revisar()), {"cotejo-curso": "trabajando"})

    @unittest.skipUnless(Path("/proc/self/cmdline").exists(), "sin /proc no se ve el programa")
    def test_un_pid_reciclado_por_otro_programa_no_cuenta_como_vivo(self):
        self.anotar("cotejo-curso", motor="headless", fase="lanzado", pid=os.getpid(),
                    programa="claude", host=socket.gethostname())
        self.assertEqual(self.desenlaces(self.revisar()), {"cotejo-curso": "perdida"})

    def test_si_volvio_cuenta_lo_que_dijo_al_terminar_y_no_el_pid(self):
        pid = self.pid_muerto()
        comun = dict(motor="headless", pid=pid, programa="claude", host=socket.gethostname())
        self.anotar("cotejo-curso", fase="lanzado", **comun)
        self.anotar("cotejo-curso", fase="terminado", **comun)
        self.assertEqual(self.desenlaces(self.revisar()), {"cotejo-curso": "trabajando"})

    def test_desde_otra_maquina_no_se_da_por_muerto(self):
        # El vault puede venir sincronizado: allí ese pid es de cualquiera.
        self.anotar("cotejo-curso", motor="headless", fase="lanzado", pid=self.pid_muerto(),
                    programa="claude", host="otra-maquina-" + socket.gethostname())
        self.assertEqual(self.desenlaces(self.revisar()), {"cotejo-curso": "trabajando"})

    def test_lanzar_y_terminar_cuentan_como_una_sola_decision(self):
        comun = dict(motor="headless", pid=1, programa="claude", host=socket.gethostname())
        self.anotar("cotejo-curso", fase="lanzado", **comun)
        self.anotar("cotejo-curso", fase="terminado", **comun)
        self.assertEqual(self.revisar()["resumen"]["decisiones"], 1)


class Procesos(unittest.TestCase):
    def test_este_proceso_esta_vivo(self):
        self.assertTrue(procesos.vivo(os.getpid()))
        self.assertTrue(procesos.vivo(os.getpid(), sys.executable))

    def test_uno_que_ya_termino_no(self):
        proceso = subprocess.Popen([sys.executable, "-c", "pass"])
        proceso.wait()
        self.assertFalse(procesos.vivo(proceso.pid))

    def test_lo_que_no_es_un_pid_no_esta_vivo(self):
        for raro in (None, "", "abc", 0, -3):
            self.assertFalse(procesos.vivo(raro), raro)


class Evaluar(PruebaDeEnrutador):
    def test_mide_las_reglas_contra_el_set_que_viaja_con_el_paquete(self):
        codigo, datos = self.correr("evaluar")
        self.assertEqual(codigo, verbos.OK)
        self.assertGreaterEqual(datos["tasa"], 0.85)
        self.assertEqual(datos["abaratados"], 0)

    def test_dice_donde_acierta_y_donde_no_sin_rehacer_la_cuenta(self):
        # cotejo-lbmv7e: la decisión de añadir un clasificador sale de este desglose.
        _, datos = self.correr("evaluar")
        self.assertEqual(sum(datos["confusion"].values()), datos["casos"])
        aciertos = sum(n for clave, n in datos["confusion"].items()
                       if clave.split("→")[0] == clave.split("→")[1])
        self.assertEqual(aciertos, datos["aciertos"])
        for desglose in (datos["por_escalon"], datos["por_origen"]):
            self.assertEqual(sum(f["casos"] for f in desglose.values()), datos["casos"])
            self.assertEqual(sum(f["aciertos"] for f in desglose.values()), datos["aciertos"])

    def test_un_set_que_no_existe_dice_que_hacer(self):
        codigo, datos = self.correr("evaluar", "--set", "/no/existe.json")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("--set", datos["salida"])


class Config(PruebaDeEnrutador):
    def test_dice_de_donde_salio_cada_cosa(self):
        codigo, datos = self.correr("config")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["origen"]["clave"], "enrutador")
        self.assertEqual(sorted(datos["motores"]), ["agente", "headless", "sesion", "simulado"])


if __name__ == "__main__":
    unittest.main()
