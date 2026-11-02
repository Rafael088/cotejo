"""Lo único del proyecto que modifica las notas del usuario.

Aquí el fallo que importa no es el que rompe, es el que pisa trabajo ajeno sin que nadie se
entere. Por eso casi cada prueba comprueba dos cosas: que lo que debía cambiar cambió, y que
lo que no debía cambiar sigue exactamente igual.
"""

import os
from unittest import mock

from apoyo import PruebaConVault, proyecto

from tareas import modelo
from tareas.fuentes import obsidian


class Marcar(PruebaConVault):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Antes", "- [ ] La tarea", "- [ ] Después"))

    def tarea(self, texto="La tarea"):
        _, tareas = self.tareas_de("Uno")
        return next(t for t in tareas if t.texto == texto)

    def test_marcar_escribe_la_equis(self):
        self.fuente.marcar(self.tarea())
        self.assertIn("- [x] La tarea", self.leer_nota("Uno.md"))

    def test_marcar_devuelve_la_tarea_como_quedo(self):
        nueva = self.fuente.marcar(self.tarea())
        self.assertTrue(nueva.hecha)
        self.assertTrue(nueva.sitio.original.startswith("- [x] La tarea"))

    def test_marcar_borra_el_tag_de_estado(self):
        self.escribir_nota("Dos.md", proyecto("- [ ] Entregada #por-validar #agente/opus"))
        _, tareas = self.tareas_de("Dos")
        self.fuente.marcar(tareas[0])
        linea = self.leer_nota("Dos.md")
        self.assertIn("- [x] Entregada", linea)
        self.assertNotIn("#por-validar", linea)
        self.assertIn("#agente/opus", linea)  # quién la tuvo sí se conserva

    def test_desmarcar_la_devuelve_a_pendiente(self):
        hecha = self.fuente.marcar(self.tarea())
        self.fuente.marcar(hecha, hecha=False)
        self.assertIn("- [ ] La tarea", self.leer_nota("Uno.md"))

    def test_marcar_pone_la_fecha_de_hoy(self):
        with mock.patch.object(obsidian, "_hoy", return_value="2026-09-23"):
            self.fuente.marcar(self.tarea())
        self.assertIn("- [x] La tarea — 2026-09-23", self.leer_nota("Uno.md"))

    def test_desmarcar_quita_la_fecha_que_puso_marcar(self):
        with mock.patch.object(obsidian, "_hoy", return_value="2026-09-23"):
            hecha = self.fuente.marcar(self.tarea())
        self.fuente.marcar(hecha, hecha=False)
        texto = self.leer_nota("Uno.md")
        self.assertIn("- [ ] La tarea", texto)
        self.assertNotIn("2026-09-23", texto)

    def test_marcar_no_duplica_una_fecha_puesta_a_mano(self):
        self.escribir_nota("Dos.md", proyecto("- [ ] Con fecha propia — 2026-01-01"))
        _, tareas = self.tareas_de("Dos")
        with mock.patch.object(obsidian, "_hoy", return_value="2026-09-23"):
            self.fuente.marcar(tareas[0])
        texto = self.leer_nota("Dos.md")
        self.assertIn("- [x] Con fecha propia — 2026-01-01", texto)
        self.assertNotIn("2026-09-23", texto)

    def test_la_fecha_queda_antes_de_la_marca_y_no_rompe_el_id(self):
        with mock.patch.object(obsidian, "_hoy", return_value="2026-09-23"):
            hecha = self.fuente.marcar(self.tarea())
        linea = next(l for l in self.leer_nota("Uno.md").splitlines() if "La tarea" in l)
        self.assertTrue(linea.endswith(f"^{hecha.sitio.marca}"))
        self.assertLess(linea.index("2026-09-23"), linea.index("^"))
        # Se sigue leyendo con el mismo id y el mismo texto visible.
        _, tareas = self.tareas_de("Uno", incluir_hechas=True)
        releida = next(t for t in tareas if t.id == hecha.sitio.marca)
        self.assertEqual(releida.texto, "La tarea — 2026-09-23")

    def test_marcar_dos_veces_seguidas_no_cambia_nada(self):
        primera = self.fuente.marcar(self.tarea())
        antes = self.leer_nota("Uno.md")
        self.fuente.marcar(primera)
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_no_toca_las_lineas_de_alrededor(self):
        self.fuente.marcar(self.tarea())
        texto = self.leer_nota("Uno.md")
        self.assertIn("- [ ] Antes", texto)
        self.assertIn("- [ ] Después", texto)
        self.assertTrue(texto.startswith("---\ntipo: proyecto\n---\n"))


class Estados(PruebaConVault):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] La tarea"))

    def tarea(self):
        return self.una_tarea()

    def test_poner_estado_escribe_el_tag(self):
        self.fuente.poner_estado(self.tarea(), "en-curso")
        self.assertIn("- [ ] La tarea #en-curso", self.leer_nota("Uno.md"))

    def test_poner_estado_reemplaza_el_anterior_en_vez_de_sumarlo(self):
        primera = self.fuente.poner_estado(self.tarea(), "en-curso")
        self.fuente.poner_estado(primera, "por-validar")
        texto = self.leer_nota("Uno.md")
        self.assertIn("#por-validar", texto)
        self.assertNotIn("#en-curso", texto)

    def test_por_integrar_queda_abierta_y_persistida(self):
        nueva = self.fuente.poner_estado(self.tarea(), modelo.POR_INTEGRAR)
        self.assertFalse(nueva.hecha)
        self.assertEqual((nueva.estado, nueva.columna),
                         (modelo.POR_INTEGRAR, "por-validar"))
        self.assertIn("- [ ] La tarea #por-integrar", self.leer_nota("Uno.md"))

    def test_volver_a_pendiente_borra_el_tag(self):
        primera = self.fuente.poner_estado(self.tarea(), "en-curso")
        self.fuente.poner_estado(primera, modelo.PENDIENTE)
        self.assertNotIn("#en-curso", self.leer_nota("Uno.md"))

    def test_repetir_el_mismo_estado_no_duplica_el_tag(self):
        primera = self.fuente.poner_estado(self.tarea(), "en-curso")
        self.fuente.poner_estado(primera, "en-curso")
        self.assertEqual(self.leer_nota("Uno.md").count("#en-curso"), 1)

    def test_poner_agente_y_quitarlo(self):
        con = self.fuente.poner_agente(self.tarea(), "opus")
        self.assertIn("#agente/opus", self.leer_nota("Uno.md"))
        self.fuente.poner_agente(con, "")
        self.assertNotIn("#agente", self.leer_nota("Uno.md"))

    def test_cambiar_de_agente_no_deja_el_anterior(self):
        primera = self.fuente.poner_agente(self.tarea(), "opus")
        self.fuente.poner_agente(primera, "sonnet")
        texto = self.leer_nota("Uno.md")
        self.assertIn("#agente/sonnet", texto)
        self.assertNotIn("#agente/opus", texto)

    def test_el_estado_y_el_agente_conviven(self):
        con_estado = self.fuente.poner_estado(self.tarea(), "en-curso")
        self.fuente.poner_agente(con_estado, "opus")
        texto = self.leer_nota("Uno.md")
        self.assertIn("#en-curso", texto)
        self.assertIn("#agente/opus", texto)


class Verificacion(PruebaConVault):
    """Un agente siempre actúa sobre una lectura vieja. Esto es lo que evita que eso pise."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] La tarea"))
        self.tarea = self.una_tarea()

    def test_no_escribe_si_la_linea_cambio_por_fuera(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] La tarea, pero reescrita a mano"))
        antes = self.leer_nota("Uno.md")
        with self.assertRaises(modelo.TareaCambiada):
            self.fuente.marcar(self.tarea)
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_el_error_dice_qué_nota_fue(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Otra cosa"))
        with self.assertRaises(modelo.TareaCambiada) as caso:
            self.fuente.marcar(self.tarea)
        self.assertIn("Uno.md", str(caso.exception))

    def test_no_escribe_si_la_tarea_ya_no_esta(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Nada que ver"))
        with self.assertRaises(modelo.TareaCambiada):
            self.fuente.marcar(self.tarea)

    def test_una_nota_que_desaparecio_da_un_error_de_disco(self):
        (self.vault / self.CARPETA / "Uno.md").unlink()
        with self.assertRaises(OSError):
            self.fuente.marcar(self.tarea)

    def test_si_falla_el_reemplazo_la_nota_queda_intacta(self):
        antes = self.leer_nota("Uno.md")
        with mock.patch.object(os, "replace", side_effect=OSError("disco lleno")):
            with self.assertRaises(OSError):
                self.fuente.marcar(self.tarea)
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_no_deja_archivos_temporales(self):
        self.fuente.marcar(self.tarea)
        sueltos = [p.name for p in (self.vault / self.CARPETA).iterdir()
                   if p.name != "Uno.md"]
        self.assertEqual(sueltos, [])


class MarcaAlEscribir(PruebaConVault):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] La tarea"))

    def test_la_primera_escritura_le_deja_su_marca(self):
        nueva = self.fuente.poner_estado(self.una_tarea(), "en-curso")
        self.assertTrue(nueva.sitio.marca.startswith(obsidian.PREFIJO_MARCA))
        self.assertIn(f"^{nueva.sitio.marca}", self.leer_nota("Uno.md"))

    def test_la_marca_va_al_final_de_la_linea(self):
        # Obsidian solo la reconoce ahí, así que los tags tienen que quedar antes.
        nueva = self.fuente.poner_estado(self.una_tarea(), "en-curso")
        linea = next(l for l in self.leer_nota("Uno.md").splitlines() if "La tarea" in l)
        self.assertTrue(linea.endswith(f"^{nueva.sitio.marca}"))
        self.assertLess(linea.index("#en-curso"), linea.index("^"))

    def test_la_marca_se_conserva_entre_escrituras(self):
        primera = self.fuente.poner_estado(self.una_tarea(), "en-curso")
        segunda = self.fuente.poner_agente(primera, "opus")
        tercera = self.fuente.marcar(segunda)
        self.assertEqual({primera.sitio.marca, segunda.sitio.marca, tercera.sitio.marca}, {primera.sitio.marca})
        self.assertEqual(self.leer_nota("Uno.md").count("^"), 1)

    def test_respeta_una_marca_puesta_a_mano(self):
        self.escribir_nota("Dos.md", proyecto("- [ ] Con la mía ^mi-marca"))
        _, tareas = self.tareas_de("Dos")
        nueva = self.fuente.poner_estado(tareas[0], "en-curso")
        self.assertEqual(nueva.sitio.marca, "mi-marca")
        self.assertIn("^mi-marca", self.leer_nota("Dos.md"))

    def test_no_repite_una_marca_que_ya_esta_en_la_nota(self):
        marcas = set()
        for i in range(12):
            self.escribir_nota("Muchas.md", proyecto(*[f"- [ ] Tarea {j}" for j in range(12)]))
        _, tareas = self.tareas_de("Muchas")
        for tarea in tareas:
            marcas.add(self.fuente.poner_agente(tarea, "opus").sitio.marca)
        self.assertEqual(len(marcas), 12)

    def test_asegurar_marca_no_cambia_nada_mas(self):
        tarea = self.una_tarea()
        nueva = self.fuente.asegurar_id(tarea)
        self.assertTrue(nueva.sitio.marca)
        self.assertEqual(self.leer_nota("Uno.md").replace(f" ^{nueva.sitio.marca}", ""),
                         proyecto("- [ ] La tarea"))

    def test_asegurar_marca_no_hace_nada_si_ya_la_tiene(self):
        con_marca = self.fuente.asegurar_id(self.una_tarea())
        antes = self.leer_nota("Uno.md")
        otra_vez = self.fuente.asegurar_id(con_marca)
        self.assertEqual(otra_vez.sitio.marca, con_marca.sitio.marca)
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_la_marca_encuentra_la_tarea_aunque_se_haya_movido(self):
        con_marca = self.fuente.asegurar_id(self.una_tarea())
        # Alguien escribe tres párrafos encima: el número de línea ya no sirve, la marca sí.
        texto = self.leer_nota("Uno.md")
        self.escribir_nota("Uno.md", "---\ntipo: proyecto\n---\n\nUno\n\nDos\n\nTres\n\n"
                           + texto.split("---\n", 2)[2].lstrip("\n"))
        nueva = self.fuente.poner_estado(con_marca, "en-curso")
        self.assertEqual(nueva.sitio.marca, con_marca.sitio.marca)
        self.assertIn("#en-curso", self.leer_nota("Uno.md"))

    def test_sin_marca_una_linea_insertada_arriba_se_detecta_en_vez_de_pisar(self):
        tarea = self.una_tarea()
        texto = self.leer_nota("Uno.md")
        self.escribir_nota("Uno.md", texto.replace("- [ ] La tarea",
                                                   "- [ ] Colada\n- [ ] La tarea"))
        with self.assertRaises(modelo.TareaCambiada):
            self.fuente.poner_estado(tarea, "en-curso")


class Formato(PruebaConVault):
    def test_respeta_la_sangria_de_una_anidada(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Madre", "    - [ ] Hija"))
        _, tareas = self.tareas_de("Uno")
        hija = next(t for t in tareas if t.texto == "Hija")
        self.fuente.poner_estado(hija, "en-curso")
        self.assertRegex(self.leer_nota("Uno.md"), r"\n    - \[ \] Hija #en-curso \^")

    def test_respeta_la_vineta_original(self):
        self.escribir_nota("Uno.md", proyecto("* [ ] Con asterisco", "3) [ ] Numerada"))
        _, tareas = self.tareas_de("Uno")
        for tarea in tareas:
            self.fuente.poner_estado(tarea, "en-curso")
        texto = self.leer_nota("Uno.md")
        self.assertIn("* [ ] Con asterisco #en-curso", texto)
        self.assertIn("3) [ ] Numerada #en-curso", texto)

    def test_quita_los_espacios_sobrantes_del_final(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Con espacios   "))
        nueva = self.fuente.poner_agente(self.una_tarea(), "opus")
        self.assertTrue(nueva.sitio.original.endswith(f"^{nueva.sitio.marca}"))

    def test_conserva_la_ultima_linea_sin_salto_final(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Antes")[:-1] + "\n- [ ] La última")
        _, tareas = self.tareas_de("Uno")
        ultima = next(t for t in tareas if t.texto == "La última")
        self.fuente.poner_estado(ultima, "en-curso")
        texto = self.leer_nota("Uno.md")
        self.assertIn("#en-curso", texto)
        self.assertFalse(texto.endswith("\n"))

    def test_conserva_los_acentos(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Añadir el símbolo 🎯"))
        self.fuente.poner_estado(self.una_tarea(), "en-curso")
        self.assertIn("Añadir el símbolo 🎯 #en-curso", self.leer_nota("Uno.md"))

    def test_una_nota_con_saltos_de_windows(self):
        crudo = proyecto("- [ ] Antes", "- [ ] La tarea", "- [ ] Después")
        self.escribir_nota("Win.md", None, binario=crudo.replace("\n", "\r\n").encode())
        _, tareas = self.tareas_de("Win")
        la_tarea = next(t for t in tareas if t.texto == "La tarea")
        self.fuente.poner_estado(la_tarea, "en-curso")
        crudo_despues = self.leer_bytes("Win.md")
        self.assertIn(b"#en-curso", crudo_despues)
        # Las otras líneas conservan su salto: escribir una tarea no reformatea la nota entera.
        self.assertIn(b"- [ ] Antes\r\n", crudo_despues)
        self.assertIn(b"- [ ] Despu\xc3\xa9s\r\n", crudo_despues)
