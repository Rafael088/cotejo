"""Anotar trabajo nuevo: que quede donde toca y que repetirlo no duplique.

Un verbo que escribe una línea nueva falla distinto que uno que reescribe una que ya está: no
puede pisar nada, pero sí puede dejar la nota rara —la tarea fuera de la lista, los saltos de
línea mezclados— o, si un agente reintenta, llenar el board de copias.
"""

import unittest

from apoyo import PruebaDeCLI, nota, proyecto


class Donde(PruebaDeCLI):
    """Dónde cae la línea nueva, que es lo que decide si la nota sigue legible en Obsidian."""

    def test_va_detras_de_la_ultima_tarea_y_no_al_final_del_archivo(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Primera",
            "- [x] Segunda",
            "",
            "## Decisiones",
            "Aquí no pinta nada una tarea.",
        ))
        self.correr("crear", "Tercera", "--proyecto", "Uno")
        lineas = self.leer_nota("Uno.md").splitlines()
        self.assertTrue(lineas[lineas.index("- [x] Segunda") + 1].startswith("- [ ] Tercera"))
        self.assertEqual(lineas[-1], "Aquí no pinta nada una tarea.")

    def test_una_nota_sin_tareas_la_recibe_al_final(self):
        self.escribir_nota("Uno.md", proyecto("Solo prosa."))
        self.correr("crear", "La primera", "--proyecto", "Uno")
        self.assertTrue(self.leer_nota("Uno.md").rstrip().endswith("^" + self.una_tarea().id))

    def test_una_nota_sin_tareas_la_recibe_bajo_su_encabezado_de_tareas(self):
        # La nota tal como sale de la plantilla del vault: la sección existe pero está vacía,
        # y debajo vienen las decisiones (cotejo-n9mou2).
        self.escribir_nota("Uno.md", proyecto(
            "## 🎯 Objetivo",
            "Algo.",
            "",
            "## ✅ Tareas",
            "",
            "## 🧠 Decisiones técnicas",
            "Aquí no pinta nada una tarea.",
        ))
        self.correr("crear", "La primera", "--proyecto", "Uno")
        lineas = self.leer_nota("Uno.md").splitlines()
        self.assertTrue(lineas[lineas.index("## ✅ Tareas") + 1].startswith("- [ ] La primera"))
        self.assertEqual(lineas[-1], "Aquí no pinta nada una tarea.")

    def test_un_encabezado_de_tareas_dentro_de_un_bloque_de_codigo_no_cuenta(self):
        self.escribir_nota("Uno.md", proyecto("```", "## Tareas", "```", "Prosa."))
        self.correr("crear", "La primera", "--proyecto", "Uno")
        self.assertTrue(self.leer_nota("Uno.md").rstrip().endswith("^" + self.una_tarea().id))

    def test_no_se_mete_en_un_bloque_de_codigo(self):
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Real",
            "```",
            "- [ ] Esto es un ejemplo, no una tarea",
            "```",
        ))
        self.correr("crear", "Nueva", "--proyecto", "Uno")
        lineas = self.leer_nota("Uno.md").splitlines()
        self.assertTrue(lineas[lineas.index("- [ ] Real") + 1].startswith("- [ ] Nueva"))

    def test_respeta_los_saltos_de_linea_de_la_nota(self):
        crudo = proyecto("- [ ] Primera").replace("\n", "\r\n")
        self.escribir_nota("Uno.md", None, binario=crudo.encode("utf-8"))
        self.correr("crear", "Segunda", "--proyecto", "Uno")
        bytes_ = self.leer_bytes("Uno.md")
        self.assertIn(b"- [ ] Segunda", bytes_)
        # Todos los saltos siguen siendo CRLF: ni uno solo quedó como LF suelto.
        self.assertEqual(bytes_.count(b"\n"), bytes_.count(b"\r\n"))

    def test_una_nota_sin_salto_final_no_deja_la_tarea_pegada(self):
        self.escribir_nota("Uno.md", None,
                           binario=nota("---", "tipo: proyecto", "---", "", "Prosa").rstrip(
                               "\n").encode("utf-8"))
        self.correr("crear", "Nueva", "--proyecto", "Uno")
        self.assertIn("Prosa\n- [ ] Nueva", self.leer_nota("Uno.md"))


class Como(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Ya estaba"))

    def test_nace_pendiente_sin_dueño_y_con_id_estable(self):
        codigo, datos = self.correr("crear", "Algo nuevo", "--proyecto", "Uno")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["cambio"])
        tarea = datos["tarea"]
        self.assertEqual(tarea["texto"], "Algo nuevo")
        self.assertEqual(tarea["estado"], "pendiente")
        self.assertEqual(tarea["agente"], "")
        # Con marca desde el primer momento: quien la creó va a querer nombrarla después, y
        # un id de «nota más línea» se mueve en cuanto alguien edite por encima.
        self.assertTrue(tarea["id"].startswith("cotejo-"), tarea["id"])

    def test_el_id_que_devuelve_sirve_para_la_llamada_siguiente(self):
        _, datos = self.correr("crear", "Algo nuevo", "--proyecto", "Uno")
        codigo, tomada = self.correr("tomar", datos["tarea"]["id"], "--agente", "opus")
        self.assertEqual(codigo, 0)
        self.assertEqual(tomada["tarea"]["estado"], "en-curso")

    def test_guarda_la_dificultad_si_se_la_dan(self):
        _, datos = self.correr("crear", "Algo", "--proyecto", "Uno", "--dificultad", "dificil")
        self.assertEqual(datos["tarea"]["dificultad"], "dificil")
        self.assertIn("#dificil", self.leer_nota("Uno.md"))

    def test_queda_anotada_en_la_bitacora(self):
        self.correr("crear", "Algo", "--proyecto", "Uno")
        operacion, = [o for o in self.operaciones() if o["operacion"] == "crear"]
        self.assertEqual(operacion["texto"], "Algo")

    def test_aparece_en_la_lista_como_una_tarea_más(self):
        self.correr("crear", "Algo nuevo", "--proyecto", "Uno")
        _, datos = self.correr("tareas", "--proyecto", "Uno", "--estado", "pendiente")
        self.assertIn("Algo nuevo", [t["texto"] for t in datos["tareas"]])


class Repetir(PruebaDeCLI):
    """Que reintentar sea seguro, que es el contrato del resto de los verbos."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Ya estaba"))

    def test_crear_dos_veces_lo_mismo_no_deja_dos_tareas(self):
        _, primera = self.correr("crear", "Algo nuevo", "--proyecto", "Uno")
        codigo, segunda = self.correr("crear", "Algo nuevo", "--proyecto", "Uno")
        self.assertEqual(codigo, 0)
        self.assertFalse(segunda["cambio"])
        self.assertEqual(segunda["tarea"]["id"], primera["tarea"]["id"])
        self.assertEqual(self.leer_nota("Uno.md").count("- [ ] Algo nuevo"), 1)

    def test_una_tarea_que_ya_existía_a_mano_tampoco_se_duplica(self):
        codigo, datos = self.correr("crear", "Ya estaba", "--proyecto", "Uno")
        self.assertEqual(codigo, 0)
        self.assertFalse(datos["cambio"])


class NoEscribe(PruebaDeCLI):
    """Los casos en los que la nota tiene que quedar exactamente como estaba."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Ya estaba"))
        self.escribir_nota("Otro.md", proyecto("- [ ] De otro"))
        self.antes = self.leer_nota("Uno.md")

    def test_un_proyecto_que_no_existe_no_escribe_nada(self):
        codigo, datos = self.correr("crear", "Algo", "--proyecto", "Inventado")
        self.assertEqual(codigo, 3)
        self.assertIn("Inventado", datos["error"])
        self.assertEqual(self.leer_nota("Uno.md"), self.antes)

    def test_un_nombre_que_responde_a_dos_proyectos_los_nombra_en_vez_de_elegir(self):
        codigo, datos = self.correr("crear", "Algo", "--proyecto", "o")
        self.assertEqual(codigo, 3)
        self.assertIn("Uno", datos["error"])
        self.assertIn("Otro", datos["error"])
        self.assertEqual(self.leer_nota("Uno.md"), self.antes)

    def test_una_tarea_sin_texto_no_se_escribe(self):
        codigo, datos = self.correr("crear", "   ", "--proyecto", "Uno")
        self.assertEqual(codigo, 3)
        self.assertEqual(self.leer_nota("Uno.md"), self.antes)
        self.assertIn("texto", datos["salida"])


class QueProyecto(PruebaDeCLI):
    """A qué proyecto va, que es lo único que el agente nombra a mano."""

    def test_el_nombre_exacto_gana_a_los_que_lo_contienen(self):
        # En el vault de verdad «Cotejo» es parte de «Cotejo - Planning para Producción»: sin
        # esta preferencia, `crear --proyecto Cotejo` se negaría siempre por ambiguo.
        self.escribir_nota("Cotejo.md", proyecto("- [ ] Una"))
        self.escribir_nota("Cotejo - Planning.md", proyecto("- [ ] Otra"))
        codigo, datos = self.correr("crear", "Nueva", "--proyecto", "cotejo")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["proyecto"], "Cotejo")
        self.assertIn("- [ ] Nueva", self.leer_nota("Cotejo.md"))
        self.assertNotIn("Nueva", self.leer_nota("Cotejo - Planning.md"))

    def test_en_un_proyecto_carpeta_va_a_su_nota_principal(self):
        self.escribir_nota("Grande/Grande.md", proyecto("- [ ] Principal"))
        self.escribir_nota("Grande/Parte.md", "- [ ] De una sub-nota\n")
        self.correr("crear", "Nueva", "--proyecto", "Grande")
        self.assertIn("- [ ] Nueva", self.leer_nota("Grande/Grande.md"))
        self.assertNotIn("Nueva", self.leer_nota("Grande/Parte.md"))

    def test_un_proyecto_carpeta_sin_nota_principal_no_se_inventa_una(self):
        self.escribir_nota("Suelto/Parte.md", "- [ ] De una sub-nota\n")
        codigo, datos = self.correr("crear", "Nueva", "--proyecto", "Suelto")
        self.assertEqual(codigo, 3)
        self.assertIn("nota principal", datos["error"])
        self.assertEqual(sorted(p.name for p in (self.vault / self.CARPETA / "Suelto").iterdir()),
                         ["Parte.md"])

    def test_un_salto_de_linea_en_el_texto_no_parte_la_nota(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Ya estaba"))
        _, datos = self.correr("crear", "Primera parte\n- [x] segunda", "--proyecto", "Uno")
        self.assertEqual(datos["tarea"]["texto"], "Primera parte - [x] segunda")
        self.assertNotIn("\n- [x]", self.leer_nota("Uno.md"))


class CarpetasSueltas(PruebaDeCLI):
    """El Inbox y el Diario salen en `tareas`, pero en ellos no se crea.

    No tienen nota principal: son un montón de notas de una persona. Elegir en cuál cae la
    tarea, o abrirle una nueva, sería inventarse dónde vive; y lo que el agente encuentra
    pertenece a un proyecto, que es donde alguien lo va a buscar.
    """

    def setUp(self):
        super().setUp()
        from unittest import mock
        self.escribir_nota("Uno.md", proyecto("- [ ] Ya estaba"))
        (self.vault / "00-Inbox").mkdir()
        self.captura = self.vault / "00-Inbox" / "Captura.md"
        self.captura.write_text("- [ ] Llamar a alguien\n", encoding="utf-8")
        parche = mock.patch.dict("os.environ", {"COTEJO_CARPETAS_SUELTAS": "00-Inbox"})
        parche.start()
        self.addCleanup(parche.stop)

    def test_se_niega_y_no_toca_ninguna_nota(self):
        codigo, datos = self.correr("crear", "Algo", "--proyecto", "Inbox")
        self.assertEqual(codigo, 3)
        self.assertIn("carpeta de notas sueltas", datos["error"])
        self.assertEqual(self.captura.read_text(encoding="utf-8"), "- [ ] Llamar a alguien\n")
        self.assertEqual([p.name for p in (self.vault / "00-Inbox").iterdir()], ["Captura.md"])
        self.assertEqual(self.operaciones(), [])

    def test_en_un_proyecto_sigue_funcionando_con_ellas_encendidas(self):
        codigo, _ = self.correr("crear", "Algo", "--proyecto", "Uno")
        self.assertEqual(codigo, 0)


if __name__ == "__main__":
    unittest.main()
