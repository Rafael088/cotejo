"""El resumen que lee el widget de la barra, y que ahora también leen los agentes.

`estado.json` es un contrato con gente que no se puede ver: el widget QML, un script de nadie,
un agente. Por eso lleva número de esquema y por eso las claves se agregan pero no se
renombran: romperlo no da error en ninguna parte, simplemente deja de funcionar en silencio.
"""

import os
from unittest import mock

from apoyo import PruebaDeCLI, proyecto

from tareas import estado


class Resumen(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Pendiente",
            "- [ ] Haciéndola #en-curso",
            "- [ ] Esperando #por-validar",
            "- [x] Finalizada",
        ))

    def test_lleva_el_numero_de_esquema(self):
        self.assertEqual(estado.calcular()["esquema"], estado.ESQUEMA)

    def test_las_claves_que_lee_el_widget_siguen_estando(self):
        # Si alguna de estas desaparece, el widget de la barra deja de contar sin avisar.
        datos = estado.calcular()
        for clave in ("pendientes", "en_curso", "por_validar", "hechas", "proyectos",
                      "top", "actualizado"):
            self.assertIn(clave, datos)

    def test_sin_problemas_no_mete_la_clave_de_avisos(self):
        self.assertNotIn("avisos", estado.calcular())

    def test_los_avisos_viajan_con_el_resumen(self):
        self.escribir_nota("Rota.md", None, binario=b"\xff\xfe tareas")
        datos = estado.calcular()
        self.assertEqual(len(datos["avisos"]), 1)
        self.assertIn("Rota.md", datos["avisos"][0]["nota"])

    def test_sin_vault_lo_dice_en_vez_de_devolver_ceros(self):
        from tareas.fuentes import obsidian
        with mock.patch.dict(os.environ, {"COTEJO_VAULT": "", "COTEJO_FUENTE": "obsidian"}), \
                mock.patch.object(obsidian, "vault_abierto", return_value=None):
            datos = estado.calcular()
        # El texto lo pone la fuente: es ella la que sabe qué le falta para poder trabajar.
        self.assertIn("error", datos)
        self.assertIn("vault", datos["error"])


class Escritura(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Una"))

    def test_escribe_el_archivo_que_vigila_la_barra(self):
        self.assertIsNone(estado.escribir(estado.calcular()))
        self.assertTrue(self.archivo_estado.exists())

    def test_no_deja_el_temporal_a_medias(self):
        estado.escribir(estado.calcular())
        sueltos = [p.name for p in self.archivo_estado.parent.iterdir()
                   if p.name != self.archivo_estado.name]
        self.assertEqual(sueltos, [])

    def test_si_no_puede_escribir_lo_dice_en_vez_de_callarse(self):
        # Antes se tragaba el OSError, y eso significaba que con el disco lleno la barra
        # enseñaba el conteo de ayer para siempre sin manera de saberlo.
        with mock.patch.object(os, "replace", side_effect=OSError(28, "No space left on device")):
            fallo = estado.escribir(estado.calcular())
        self.assertIsNotNone(fallo)
        self.assertIn("No space left", fallo)

    def test_el_comando_devuelve_error_cuando_no_pudo_escribir(self):
        with mock.patch.object(os, "replace", side_effect=OSError(13, "Permission denied")):
            codigo, datos = self.correr("estado")
        self.assertEqual(codigo, 1)
        self.assertIn("pendientes", datos)  # el resumen sale igual por la salida estándar


class ContratoDeLaCLI(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Una"))
        self.escribir_nota("Rota.md", None, binario=b"\xff\xfe tareas")

    def test_listar_tareas_trae_los_avisos(self):
        _, datos = self.correr("tareas")
        self.assertIn("Rota.md", datos["avisos"][0]["nota"])

    def test_listar_sin_problemas_no_trae_la_clave(self):
        (self.vault / self.CARPETA / "Rota.md").unlink()
        _, datos = self.correr("tareas")
        self.assertNotIn("avisos", datos)

    def test_el_resumen_del_comando_estado_lleva_esquema_y_avisos(self):
        _, datos = self.correr("estado")
        self.assertEqual(datos["esquema"], estado.ESQUEMA)
        self.assertIn("avisos", datos)
