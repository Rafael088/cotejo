"""El medidor de ahorro: que el número sea medido, y que medirlo no cueste.

Un medidor de ahorro es la clase de cosa que se convierte en medalla sin que nadie lo decida:
basta con redondear hacia arriba, contar dos veces la misma nota o comparar contra cero. Cada
prueba de aquí vigila una de esas maneras de mentir.
"""

import unittest
from pathlib import Path
from unittest import mock

from apoyo import PruebaConVault, PruebaDeCLI, proyecto

from tareas import ahorro

try:
    from tareas.app.comun import frase_ahorro
    HAY_GTK = True
except (ImportError, ValueError):
    HAY_GTK = False


class Contar(PruebaDeCLI):
    """Los totales, que viven en su propio archivo y se reemplazan atómicamente."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))

    def test_sin_lecturas_no_hay_nada_que_decir(self):
        # Ni un cero ni un «1× más barato» el primer día: nada.
        self.assertIsNone(ahorro.resumen())

    def test_una_lectura_deja_las_dos_mitades_medidas(self):
        datos = ahorro.anotar(devuelto=100, leido=800)
        self.assertEqual(datos["lecturas"], 1)
        self.assertEqual((datos["devuelto"], datos["leido"]), (100, 800))
        self.assertEqual(ahorro.resumen()["razon"], 8.0)

    def test_los_totales_se_acumulan_entre_llamadas(self):
        ahorro.anotar(devuelto=100, leido=800)
        ahorro.anotar(devuelto=50, leido=200)
        datos = ahorro.leer()
        self.assertEqual(datos["lecturas"], 2)
        self.assertEqual((datos["devuelto"], datos["leido"]), (150, 1000))

    def test_una_fuente_que_no_vive_en_archivos_no_cuenta_nada(self):
        # Comparar contra cero daría un ahorro infinito, que es justo el número inventado que
        # esta tarea existe para no dar.
        ahorro.anotar(devuelto=100, leido=0)
        self.assertIsNone(ahorro.resumen())

    def test_el_supuesto_viaja_dentro_del_dato(self):
        # Quien lea el número tiene que tropezarse con lo que no se midió, no ir a buscarlo.
        ahorro.anotar(devuelto=100, leido=800)
        self.assertIn("no medido", ahorro.resumen()["supuesto"])

    def test_un_archivo_roto_empieza_de_cero_en_vez_de_reventar(self):
        self.ahorro.write_text("{no es json", encoding="utf-8")
        self.assertEqual(ahorro.leer()["lecturas"], 0)
        self.assertEqual(ahorro.anotar(devuelto=10, leido=20)["lecturas"], 1)

    def test_no_deja_el_temporal_del_reemplazo_atomico(self):
        ahorro.anotar(devuelto=100, leido=800)
        self.assertEqual([p.name for p in self.ahorro.parent.iterdir() if p.name.startswith(".")],
                         [])

    def test_no_poder_apuntar_no_estropea_la_llamada(self):
        # El agente ya tiene su respuesta impresa cuando esto corre.
        with mock.patch.object(Path, "write_text", side_effect=OSError("disco lleno")):
            self.assertEqual(ahorro.anotar(devuelto=10, leido=20)["lecturas"], 1)


class PorDia(PruebaDeCLI):
    """Lo de hoy, que es lo que enseña el board; el total queda para la ayuda."""

    def en(self, fecha):
        return mock.patch.object(ahorro, "hoy", return_value=fecha)

    def test_lo_de_hoy_se_cuenta_aparte_del_total(self):
        with self.en("2026-09-25"):
            ahorro.anotar(devuelto=100, leido=800)
        with self.en("2026-09-26"):
            ahorro.anotar(devuelto=50, leido=200)
            datos = ahorro.resumen()
        self.assertEqual(datos["lecturas"], 2)
        self.assertEqual((datos["hoy"]["lecturas"], datos["hoy"]["leido"]), (1, 200))
        self.assertEqual(datos["hoy"]["razon"], 4.0)

    def test_un_dia_nuevo_empieza_sin_nada_que_decir(self):
        # Ni «0 tokens ahorrados hoy»: nada, como el primer día de todos.
        with self.en("2026-09-25"):
            ahorro.anotar(devuelto=100, leido=800)
        with self.en("2026-09-26"):
            datos = ahorro.resumen()
        self.assertIsNone(datos["hoy"])
        self.assertEqual(datos["lecturas"], 1)

    def test_solo_se_guardan_los_ultimos_dias(self):
        for dia in range(1, ahorro.DIAS_GUARDADOS + 6):
            with self.en(f"2026-08-{dia:02d}"):
                ahorro.anotar(devuelto=10, leido=20)
        dias = ahorro.leer()["dias"]
        self.assertEqual(len(dias), ahorro.DIAS_GUARDADOS)
        self.assertNotIn("2026-08-01", dias)
        # El total no pierde lo que se sale de la ventana.
        self.assertEqual(ahorro.leer()["lecturas"], ahorro.DIAS_GUARDADOS + 5)

    def test_un_archivo_de_antes_sin_dias_sigue_sirviendo(self):
        # Las claves se agregan, no se renombran: el ahorro.json de antes tiene que leerse.
        self.ahorro.write_text('{"esquema": 1, "lecturas": 3, "devuelto": 10, "leido": 90,'
                               ' "desde": 1}', encoding="utf-8")
        self.assertIsNone(ahorro.resumen()["hoy"])
        self.assertEqual(ahorro.anotar(devuelto=10, leido=20)["lecturas"], 4)
        self.assertEqual(ahorro.resumen()["hoy"]["lecturas"], 1)

    def test_la_cli_no_devuelve_los_dias_sueltos(self):
        # Treinta días de números que el agente no pidió serían el gasto que esto cuenta.
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))
        self.correr("tareas")
        _, datos = self.correr("ahorro")
        self.assertNotIn("dias", datos)
        self.assertEqual(datos["hoy"]["lecturas"], 1)


class LaMitadCara(PruebaConVault):
    """Lo que la fuente ya leyó, que es de dónde sale el número sin volver a leer nada."""

    def test_cuenta_lo_que_pesaron_las_notas_leidas(self):
        contenido = proyecto("- [ ] Una tarea")
        self.escribir_nota("Uno.md", contenido)
        fuente = self.fuente
        fuente.escanear()
        self.assertEqual(fuente.leido(), len(contenido))

    def test_la_nota_principal_se_lee_dos_veces_y_se_cuenta_una(self):
        # El frontmatter y las tareas se leen por separado; contarla dos veces inflaría la
        # mitad cara del número, que es la que hace que el ahorro parezca mayor.
        contenido = proyecto("- [ ] Una tarea", estado="activo")
        self.escribir_nota("Uno.md", contenido)
        fuente = self.fuente
        fuente.escanear()
        self.assertEqual(fuente.leido(), len(contenido))

    def test_contar_no_abre_ni_un_archivo_mas(self):
        # La condición de la nota del proyecto: si medir el ahorro encarece la lectura, el
        # medidor se come lo que mide.
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))
        fuente = self.fuente
        fuente.escanear()
        original = Path.read_text
        with mock.patch.object(Path, "read_text", autospec=True, side_effect=original) as leer:
            fuente.leido()
            fuente.leido()
        leer.assert_not_called()

    def test_cada_escaneo_contesta_por_su_propia_respuesta(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))
        fuente = self.fuente
        fuente.escanear()
        primero = fuente.leido()
        fuente.escanear()
        self.assertEqual(fuente.leido(), primero, "los escaneos se están sumando entre sí")

    def test_las_carpetas_sueltas_cuentan_si_se_leen(self):
        # El Inbox y el Diario, encendidos, son notas que la fuente abrió para contestar: sin
        # Cotejo también habría que leerlas, así que entran en la mitad cara como las demás.
        contenido = proyecto("- [ ] Una tarea")
        self.escribir_nota("Uno.md", contenido)
        suelta = "- [ ] Llamar a alguien\n"
        (self.vault / "00-Inbox").mkdir()
        (self.vault / "00-Inbox" / "Captura.md").write_text(suelta, encoding="utf-8")
        from tareas.fuentes.obsidian import Obsidian
        with mock.patch.dict("os.environ", {"COTEJO_CARPETAS_SUELTAS": "00-Inbox"}):
            fuente = Obsidian({"vault": str(self.vault), "carpeta_proyectos": self.CARPETA})
        fuente.escanear()
        self.assertEqual(fuente.leido(), len(contenido) + len(suelta))

    def test_una_fuente_cualquiera_no_promete_saber_cuanto_leyó(self):
        from tareas.fuente import Fuente
        self.assertEqual(Fuente().leido(), 0)

    def test_con_proyectos_solo_cuenta_las_notas_de_los_filtrados(self):
        # `escanear` lee el vault entero para saber qué proyectos hay, pero `leido()` tiene
        # que poder contar solo los que pasaron el filtro de quien llama (`tareas --proyecto`)
        # y no el vault entero que hizo falta recorrer para encontrarlos (tarea cotejo-mbzjoj).
        uno = proyecto("- [ ] Una tarea")
        self.escribir_nota("Uno.md", uno)
        self.escribir_nota("Otro.md", proyecto("- [ ] Otra tarea"))
        fuente = self.fuente
        proyectos = fuente.escanear()
        filtrados = [p for p in proyectos if p.nombre == "Uno"]
        self.assertEqual(fuente.leido(filtrados), len(uno))

    def test_sin_proyectos_sigue_contando_el_vault_entero(self):
        # El caso sin `--proyecto` no puede salir perdiendo con el arreglo: ahí sí es el vault
        # entero lo que hubo que leer para contestar.
        uno = proyecto("- [ ] Una tarea")
        otro = proyecto("- [ ] Otra tarea")
        self.escribir_nota("Uno.md", uno)
        self.escribir_nota("Otro.md", otro)
        fuente = self.fuente
        fuente.escanear()
        self.assertEqual(fuente.leido(), len(uno) + len(otro))

    def test_una_carpeta_suelta_filtrada_no_arrastra_las_demas_notas(self):
        # Las carpetas sueltas cuentan como un proyecto más (079a9da): filtrar por «Inbox»
        # tiene que dejar fuera tanto los proyectos de verdad como cualquier otra suelta.
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))
        suelta = "- [ ] Llamar a alguien\n"
        (self.vault / "00-Inbox").mkdir()
        (self.vault / "00-Inbox" / "Captura.md").write_text(suelta, encoding="utf-8")
        from tareas.fuentes.obsidian import Obsidian
        with mock.patch.dict("os.environ", {"COTEJO_CARPETAS_SUELTAS": "00-Inbox"}):
            fuente = Obsidian({"vault": str(self.vault), "carpeta_proyectos": self.CARPETA})
        proyectos = fuente.escanear()
        inbox = [p for p in proyectos if p.nombre == "Inbox"]
        self.assertEqual(fuente.leido(inbox), len(suelta))


class PorLaCLI(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        # Una nota de proyecto de verdad: párrafos, decisiones y contexto alrededor de unas
        # pocas tareas. Con dos líneas pelás el JSON de la CLI pesa más que la nota, y medir
        # el ahorro contra una nota de juguete daría un número que no dice nada.
        relleno = ["Contexto, decisiones y por qué de este proyecto, párrafo " + str(i) + "." * 40
                   for i in range(30)]
        self.escribir_nota("Uno.md", proyecto(*relleno, "- [ ] Una tarea", "- [ ] Otra tarea"))

    def test_pedir_tareas_apunta_una_lectura_con_las_dos_mitades(self):
        self.correr("tareas")
        datos = ahorro.leer()
        self.assertEqual(datos["lecturas"], 1)
        self.assertGreater(datos["devuelto"], 0)
        self.assertGreater(datos["leido"], datos["devuelto"])

    def test_el_resumen_de_la_barra_no_cuenta(self):
        # Lo llama el widget cada pocos minutos sin que haya ningún agente: sumarlo
        # convertiría el ahorro en una medida de cuánto lleva encendida la barra.
        self.correr("estado")
        self.assertEqual(ahorro.leer()["lecturas"], 0)

    def test_escribir_una_tarea_tampoco_cuenta(self):
        # El medidor compara maneras de *enterarse*, no de escribir.
        _, datos = self.correr("tareas", "--limite", "1")
        antes = ahorro.leer()["lecturas"]
        self.correr("tomar", datos["tareas"][0]["id"], "--agente", "opus")
        self.assertEqual(ahorro.leer()["lecturas"], antes)

    def test_el_verbo_ahorro_devuelve_el_numero_y_su_supuesto(self):
        self.correr("tareas")
        codigo, datos = self.correr("ahorro")
        self.assertEqual(codigo, 0)
        self.assertGreater(datos["razon"], 1)
        self.assertIn("no medido", datos["supuesto"])

    def test_el_verbo_ahorro_sin_lecturas_dice_qué_hacer(self):
        codigo, datos = self.correr("ahorro")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["lecturas"], 0)
        self.assertIn("tareas", datos["salida"])

    def test_consultar_el_ahorro_no_se_cuenta_a_sí_mismo(self):
        self.correr("tareas")
        self.correr("ahorro")
        self.assertEqual(ahorro.leer()["lecturas"], 1)

    def test_proyecto_filtrado_no_infla_la_mitad_cara_con_otros_proyectos(self):
        # Antes, `escanear` leía el vault entero aunque se pidiera `--proyecto`, y la mitad
        # cara sumaba también las notas de un proyecto que la respuesta ni mencionó, inflando
        # la razón contra un solo proyecto (tarea cotejo-mbzjoj).
        contenido_uno = self.leer_nota("Uno.md")
        self.escribir_nota("Otro.md", proyecto(
            "Un proyecto entero que --proyecto Uno no debería tener que pagar.",
            "- [ ] Una tarea de otro proyecto"))
        self.correr("tareas", "--proyecto", "Uno")
        self.assertEqual(ahorro.leer()["leido"], len(contenido_uno))

    def test_con_notas_chicas_el_camino_barato_no_lo_es_y_se_dice(self):
        # Una nota de dos líneas se describe con un JSON que pesa más que ella. El medidor
        # tiene que poder dar un número menor que uno: si solo supiera felicitar, no estaría
        # midiendo nada.
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))
        self.correr("tareas", "--proyecto", "Uno")
        self.assertLess(ahorro.resumen()["razon"], 1)


@unittest.skipUnless(HAY_GTK, "la frase vive en tareas.app, que necesita PyGObject")
class LaFrase(unittest.TestCase):
    """Cómo se dice el número en la lateral del board, que es lo único que se ve."""

    def frase(self, ahorrados):
        return frase_ahorro({"tokens_ahorrados": ahorrados})

    def test_dice_cuántos_tokens_se_ahorraron(self):
        self.assertEqual(self.frase(90490), "90.4K tokens ahorrados hoy")

    def test_notacion_compacta(self):
        from tareas.app.comun import compacto
        casos = {0: "0", 999: "999", 1000: "1K", 1100: "1.1K", 1199: "1.1K",
                 999_999: "999.9K", 2_100_000: "2.1M", 20_150_000: "20.1M", 3_000_000_000: "3B"}
        for numero, esperado in casos.items():
            self.assertEqual(compacto(numero), esperado, numero)

    def test_si_no_se_ahorró_nada_lo_dice_al_revés(self):
        # Con notas chicas el JSON pesa más que la nota. Un medidor que solo sabe felicitar
        # es un cartel, no una medida.
        self.assertEqual(self.frase(-43), "43 tokens de más hoy")

    def test_cero_no_es_un_caso_raro(self):
        self.assertEqual(self.frase(0), "0 tokens ahorrados hoy")


if __name__ == "__main__":
    unittest.main()
