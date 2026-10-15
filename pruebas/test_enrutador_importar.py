"""`cotejo importar plan`: qué tareas sacaría un plan.md, y si de verdad se crean.

Dos niveles de prueba. El de `tareas_de_plan` es puro —entra texto, sale una lista— y no
necesita vault ni fuente; el del verbo sí, porque es el único sitio donde `--aplicar` escribe.
Los planes de ejemplo son los dos que pidió la tarea: uno al estilo de la skill `writing-plans`
de superpowers (solo encabezados, sin checklist) y un PRD con checklist, los dos como texto
dentro de la prueba y no como archivo del repo —viven y mueren con el vault de mentira de cada
prueba, igual que todo lo demás que no debe tocar nada real—.
"""

import unittest

from apoyo import PruebaDeEnrutador, proyecto

from enrutador import decision, importar, verbos

PRD_CON_CHECKLIST = """\
# PRD: Inicio de sesión

## Resumen

Un párrafo cualquiera que no es una tarea.

## Checklist

- [ ] Agregar el endpoint de login
- [x] Ya hecho, no cuenta
- [ ] Comprar el certificado SSL
- [ ] Escribir las pruebas de integración
"""

PLAN_SUPERPOWERS = """\
# Plan: Importar planes a Cotejo

## Resumen

Un párrafo cualquiera que tampoco es una tarea.

## Pasos

### Task 1: Detectar las casillas sin marcar

Contenido de más.

### Task 2: Caer a los encabezados si el plan no tiene casillas

Contenido de más.

### Task 3: Proponer dificultad y modelo con decidir

Contenido de más.
"""


class TareasDePlan(unittest.TestCase):
    """La parte pura: `importar.tareas_de_plan`. Sin vault, sin fuente, sin E/S."""

    def test_las_casillas_marcadas_no_cuentan(self):
        self.assertEqual(
            importar.tareas_de_plan("- [ ] Hacer esto\n- [x] Ya hecho\n- [X] También hecho\n"),
            ["Hacer esto"])

    def test_el_prd_con_checklist_trae_solo_lo_pendiente(self):
        self.assertEqual(importar.tareas_de_plan(PRD_CON_CHECKLIST), [
            "Agregar el endpoint de login",
            "Comprar el certificado SSL",
            "Escribir las pruebas de integración",
        ])

    def test_sin_casillas_cae_a_los_encabezados_de_paso_en_espanol(self):
        texto = "## Paso 1: Primero esto\nTexto.\n### Tarea 2: Después esto otro\nMás texto.\n"
        self.assertEqual(importar.tareas_de_plan(texto), [
            "Paso 1: Primero esto", "Tarea 2: Después esto otro",
        ])

    def test_el_plan_de_superpowers_cae_a_sus_encabezados_en_ingles(self):
        self.assertEqual(importar.tareas_de_plan(PLAN_SUPERPOWERS), [
            "Task 1: Detectar las casillas sin marcar",
            "Task 2: Caer a los encabezados si el plan no tiene casillas",
            "Task 3: Proponer dificultad y modelo con decidir",
        ])

    def test_con_casillas_los_encabezados_no_cuentan_tambien(self):
        texto = "## Paso 1: Un encabezado\n- [ ] Pero esto es lo único que cuenta\n"
        self.assertEqual(importar.tareas_de_plan(texto), ["Pero esto es lo único que cuenta"])

    def test_dentro_de_un_bloque_de_codigo_no_es_una_tarea(self):
        texto = "- [ ] Real\n```\n- [ ] Esto es un ejemplo, no una tarea\n```\n- [ ] También real\n"
        self.assertEqual(importar.tareas_de_plan(texto), ["Real", "También real"])

    def test_un_plan_sin_casillas_ni_encabezados_no_tiene_tareas(self):
        self.assertEqual(importar.tareas_de_plan("Solo prosa.\n\nMás prosa.\n"), [])

    def test_un_plan_vacio_no_tiene_tareas(self):
        self.assertEqual(importar.tareas_de_plan(""), [])


class Proponer(unittest.TestCase):
    """`importar.proponer` es `decision.decidir` más la traducción a la etiqueta de Cotejo."""

    def test_una_tarea_humana_no_lleva_etiqueta_de_dificultad(self):
        elegida, dificultad = importar.proponer("Comprar el certificado SSL")
        self.assertFalse(elegida.despachable)
        self.assertEqual(dificultad, "")

    def test_una_tarea_de_codigo_propone_medio(self):
        elegida, dificultad = importar.proponer("Agregar el endpoint de login")
        self.assertTrue(elegida.despachable)
        self.assertEqual(dificultad, "medio")

    def test_coincide_con_decidir_a_secas(self):
        for texto in ("Agregar el endpoint de login", "Comprar el certificado SSL",
                      "Rediseñar la capa Fuente entera"):
            with self.subTest(texto=texto):
                elegida, _ = importar.proponer(texto)
                esperada = decision.decidir(texto)
                self.assertEqual(elegida.nivel.clave, esperada.nivel.clave)
                self.assertEqual(elegida.por, esperada.por)


class DificultadEscrita(unittest.TestCase):
    """La dificultad que ya trae la casilla del plan manda, y no se escribe dos veces."""

    def test_se_separa_del_texto(self):
        self.assertEqual(importar.separar_dificultad("Topes en la ruta #facil"),
                         ("Topes en la ruta", "facil"))

    def test_sin_tag_no_hay_dificultad(self):
        self.assertEqual(importar.separar_dificultad("Topes en la ruta"), ("Topes en la ruta", ""))

    def test_un_tag_pegado_a_otra_palabra_no_es_dificultad(self):
        self.assertEqual(importar.separar_dificultad("Ver #facilidades"), ("Ver #facilidades", ""))

    def test_proponer_respeta_la_escrita(self):
        elegida, dificultad = importar.proponer("Topes en la ruta", dificultad="facil")
        self.assertEqual(dificultad, "facil")
        self.assertEqual(elegida.nivel.clave, "n1")
        self.assertEqual(elegida.por, "dificultad")


class ImportarPlan(PruebaDeEnrutador):
    """El verbo de punta a punta: ensayo que no toca nada, `--aplicar` que crea con `crear`."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Ya estaba, antes de importar nada"))

    def escribir_plan(self, nombre, texto):
        # Fuera de la carpeta de proyectos del vault de mentira: un plan no es una nota de
        # Cotejo, es un archivo cualquiera que alguien le pasa a `importar plan`.
        ruta = self.vault / nombre
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    # --- ensayo ---------------------------------------------------------

    def test_el_ensayo_no_escribe_nada(self):
        ruta = self.escribir_plan("plan.md", PRD_CON_CHECKLIST)
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("importar", "plan", str(ruta), "--proyecto", "Uno")
        self.assertEqual(codigo, verbos.OK)
        self.assertFalse(datos["aplicado"])
        self.assertEqual(datos["total"], 3)
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.operaciones(), [])
        self.assertEqual(self.despachados(), [])

    def test_el_ensayo_trae_dificultad_y_modelo_por_tarea(self):
        ruta = self.escribir_plan("plan.md", PRD_CON_CHECKLIST)
        _, datos = self.correr("importar", "plan", str(ruta), "--proyecto", "Uno")
        por_texto = {t["texto"]: t for t in datos["tareas"]}
        humana = por_texto["Comprar el certificado SSL"]
        self.assertFalse(humana["despachable"])
        self.assertEqual(humana["dificultad"], "")
        codigo = por_texto["Agregar el endpoint de login"]
        self.assertTrue(codigo["despachable"])
        self.assertEqual(codigo["dificultad"], "medio")
        self.assertIn("modelo", codigo)
        self.assertIn("razon", codigo)

    def test_el_ensayo_no_necesita_que_el_proyecto_exista_para_proponer(self):
        # Proponer es gratis y no depende de dónde caería la tarea; solo --aplicar necesita el
        # proyecto de verdad. Que el ensayo no reviente por un nombre que no existe todavía es
        # lo que deja mirar la propuesta antes de decidir en qué proyecto va.
        ruta = self.escribir_plan("plan.md", PRD_CON_CHECKLIST)
        codigo, datos = self.correr("importar", "plan", str(ruta), "--proyecto", "NoExiste")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["total"], 3)

    def test_un_plan_sin_tareas_lo_dice_y_no_revienta(self):
        ruta = self.escribir_plan("plan.md", "Solo prosa.\n")
        codigo, datos = self.correr("importar", "plan", str(ruta), "--proyecto", "Uno")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["total"], 0)
        self.assertIn("salida", datos)

    def test_un_plan_que_no_existe_da_un_error_legible(self):
        codigo, datos = self.correr(
            "importar", "plan", str(self.vault / "no-existe.md"), "--proyecto", "Uno")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertIn("salida", datos)

    def test_el_formato_de_superpowers_tambien_se_puede_importar(self):
        ruta = self.escribir_plan("plan.md", PLAN_SUPERPOWERS)
        codigo, datos = self.correr("importar", "plan", str(ruta), "--proyecto", "Uno")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["total"], 3)
        self.assertEqual(datos["tareas"][0]["texto"], "Task 1: Detectar las casillas sin marcar")

    # --- aplicar ---------------------------------------------------------

    def test_aplicar_crea_cada_tarea_con_crear(self):
        ruta = self.escribir_plan("plan.md", PRD_CON_CHECKLIST)
        codigo, datos = self.correr(
            "importar", "plan", str(ruta), "--proyecto", "Uno", "--aplicar")
        self.assertEqual(codigo, verbos.OK)
        self.assertTrue(datos["aplicado"])
        self.assertEqual(datos["creadas"], 3)
        for fila in datos["tareas"]:
            self.assertTrue(fila["creada"])
            self.assertTrue(fila["tarea"]["id"].startswith("cotejo-"))
            self.assertEqual(fila["tarea"]["estado"], "pendiente")
            self.assertEqual(fila["tarea"]["agente"], "")

        _, tareas = self.tareas_de("Uno")
        textos = {t.texto for t in tareas}
        self.assertIn("Agregar el endpoint de login", textos)
        self.assertIn("Comprar el certificado SSL", textos)
        self.assertIn("Escribir las pruebas de integración", textos)

        contenido = self.leer_nota("Uno.md")
        self.assertIn("- [ ] Agregar el endpoint de login #medio", contenido)
        # La humana no lleva etiqueta de dificultad: no es que sea "difícil", es que no es de
        # ningún modelo.
        self.assertIn("- [ ] Comprar el certificado SSL ^", contenido)

    def test_aplicar_deja_registro_en_la_bitacora_de_cotejo(self):
        ruta = self.escribir_plan("plan.md", PRD_CON_CHECKLIST)
        self.correr("importar", "plan", str(ruta), "--proyecto", "Uno", "--aplicar")
        operaciones = [o for o in self.operaciones() if o.get("operacion") == "crear"]
        self.assertEqual(len(operaciones), 3)

    def test_aplicar_dos_veces_no_duplica(self):
        ruta = self.escribir_plan("plan.md", PRD_CON_CHECKLIST)
        self.correr("importar", "plan", str(ruta), "--proyecto", "Uno", "--aplicar")
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr(
            "importar", "plan", str(ruta), "--proyecto", "Uno", "--aplicar")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["creadas"], 0)
        for fila in datos["tareas"]:
            self.assertFalse(fila["creada"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_aplicar_no_duplica_la_etiqueta_de_dificultad_del_plan(self):
        ruta = self.escribir_plan("plan.md", "- [ ] Topes en la ruta #facil\n"
                                             "- [ ] Rehacer la capa de datos #dificil\n")
        _, datos = self.correr("importar", "plan", str(ruta), "--proyecto", "Uno", "--aplicar")
        self.assertEqual(datos["creadas"], 2)
        self.assertEqual([t["dificultad"] for t in datos["tareas"]], ["facil", "dificil"])
        contenido = self.leer_nota("Uno.md")
        self.assertIn("- [ ] Topes en la ruta #facil ^", contenido)
        self.assertIn("- [ ] Rehacer la capa de datos #dificil ^", contenido)
        self.assertNotIn("#medio", contenido)
        # Y repetirlo no duplica: el texto se compara sin la etiqueta, como lo lee la fuente.
        _, otra = self.correr("importar", "plan", str(ruta), "--proyecto", "Uno", "--aplicar")
        self.assertEqual(otra["creadas"], 0)

    def test_el_ensayo_dice_cuales_no_se_crearian_y_por_que(self):
        ruta = self.escribir_plan("plan.md", "- [ ] Ya estaba, antes de importar nada\n"
                                             "- [ ] Una nueva\n")
        _, datos = self.correr("importar", "plan", str(ruta), "--proyecto", "Uno")
        ya, nueva = datos["tareas"]
        self.assertFalse(ya["se_crearia"])
        self.assertIn("motivo", ya)
        self.assertTrue(nueva["se_crearia"])

    def test_la_primera_tarea_cae_bajo_el_encabezado_de_tareas_vacio(self):
        self.escribir_nota("Tres.md", proyecto("## ✅ Tareas", "", "## 🧠 Decisiones", "Nada."))
        ruta = self.escribir_plan("plan.md", "- [ ] Primera\n- [ ] Segunda\n")
        self.correr("importar", "plan", str(ruta), "--proyecto", "Tres", "--aplicar")
        lineas = self.leer_nota("Tres.md").splitlines()
        i = lineas.index("## ✅ Tareas")
        self.assertTrue(lineas[i + 1].startswith("- [ ] Primera"))
        self.assertTrue(lineas[i + 2].startswith("- [ ] Segunda"))
        self.assertEqual(lineas[-1], "Nada.")

    def test_un_plan_dentro_del_proyecto_no_se_copia_a_la_nota_principal(self):
        # El caso de Agent Debate: el planning vive en la carpeta del proyecto, así que la
        # fuente ya lee sus casillas como tareas. Antes se saltaban las que no llevaban tag
        # (iguales a sí mismas) y se duplicaban las que sí.
        self.escribir_nota("Dos/Dos.md", proyecto("## ✅ Tareas", "", "## Enlaces"))
        plan = "- [ ] Con etiqueta #facil\n- [ ] Sin etiqueta\n"
        self.escribir_nota("Dos/Dos - Planning.md", plan)
        ruta = self.vault / self.CARPETA / "Dos" / "Dos - Planning.md"
        antes = self.leer_nota("Dos/Dos.md")

        _, ensayo = self.correr("importar", "plan", str(ruta), "--proyecto", "Dos")
        self.assertEqual([t["se_crearia"] for t in ensayo["tareas"]], [False, False])
        self.assertTrue(any("nota de «Dos»" in a for a in ensayo["avisos"]))

        codigo, datos = self.correr("importar", "plan", str(ruta), "--proyecto", "Dos",
                                    "--aplicar")
        self.assertEqual(codigo, verbos.OK)
        self.assertEqual(datos["creadas"], 0)
        for fila in datos["tareas"]:
            self.assertFalse(fila["creada"])
            self.assertIn("este mismo plan", fila["motivo"])
        self.assertEqual(self.leer_nota("Dos/Dos.md"), antes)
        _, tareas = self.tareas_de("Dos")
        self.assertEqual(len(tareas), 2)

    def test_aplicar_con_un_proyecto_que_no_existe_no_crea_nada(self):
        ruta = self.escribir_plan("plan.md", PRD_CON_CHECKLIST)
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr(
            "importar", "plan", str(ruta), "--proyecto", "NoExiste", "--aplicar")
        self.assertEqual(codigo, verbos.ERROR)
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.operaciones(), [])


if __name__ == "__main__":
    unittest.main()
