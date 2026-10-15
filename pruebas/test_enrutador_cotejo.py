"""El adaptador a las tareas: que el enrutador las lea y las escriba como un agente más.

Antes esto probaba un contrato entre dos programas —esquemas, JSON, códigos de salida— y la
mitad de aquellas pruebas dejaron de tener sentido el día que dejó de haber subproceso. Lo que
queda es lo que sí puede romperse: que busque la tarea correcta, que no se invente ninguna, y
que al tomarla escriba por el mismo camino verificado que usa `tomar`.
"""

from apoyo import PruebaDeEnrutador, proyecto

from enrutador.cotejo import Cotejo
from tareas.cli import ErrorCLI


class Leer(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Arreglar el parseo de los tags",
            "- [ ] Haciéndola #en-curso #agente/opus",
        ))
        self.escribir_nota("Dos.md", proyecto("- [ ] De otro proyecto"))

    def test_filtra_por_proyecto_y_por_estado_como_el_verbo_tareas(self):
        cotejo = Cotejo()
        self.assertEqual(len(cotejo.tareas()), 3)
        self.assertEqual(len(cotejo.tareas(proyecto="Uno")), 2)
        self.assertEqual(len(cotejo.tareas(estado="pendiente")), 2)

    def test_el_vault_se_lee_una_sola_vez_por_invocacion(self):
        # Es lo que ganó la mudanza: antes cada pregunta era un subproceso que volvía a
        # escanear el vault entero. `plan` sobre 65 tareas hacía 65 veces el mismo trabajo.
        cotejo = Cotejo()
        cotejo.tareas()
        cargado = cotejo._abierto
        cotejo.tareas()
        cotejo.tarea(cotejo.tareas()[0]["id"])
        self.assertIs(cotejo._abierto, cargado)

    def test_la_marca_vale_con_el_circunflejo_delante_y_sin_el(self):
        # Es como se ve en la nota y como la copia quien la lee ahí.
        self.escribir_nota("Tres.md", proyecto("- [ ] Con su marca ^cotejo-a1b2"))
        for escrito in ("cotejo-a1b2", "^cotejo-a1b2"):
            self.assertEqual(Cotejo().tarea(escrito)["id"], "cotejo-a1b2")

    def test_un_id_que_no_existe_dice_que_se_puede_reintentar(self):
        with self.assertRaises(ErrorCLI) as caso:
            Cotejo().tarea("cotejo-zzzz")
        self.assertTrue(caso.exception.reintentable)

    def test_los_avisos_de_notas_ilegibles_viajan(self):
        # Una nota que no se puede leer esconde sus tareas, y eso no puede pasar callando: quien
        # reparte concluiría que ahí no hay nada que hacer.
        self.escribir_nota("Rota.md", "", binario=b"\xff\xfe no soy utf-8")
        cotejo = Cotejo()
        cotejo.tareas()
        self.assertTrue(cotejo.avisos)


class Escribir(PruebaDeEnrutador):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Arreglar el parseo de los tags"))

    def test_tomar_deja_la_tarea_en_curso_y_a_nombre_del_modelo(self):
        cotejo = Cotejo()
        tarea = cotejo.tomar(cotejo.tareas()[0]["id"], "opus")
        self.assertEqual((tarea["estado"], tarea["agente"]), ("en-curso", "opus"))
        self.assertIn("#en-curso", self.leer_nota("Uno.md"))
        self.assertIn("#agente/opus", self.leer_nota("Uno.md"))

    def test_tomar_queda_anotado_en_la_bitacora_de_cotejo(self):
        # Por el mismo camino que `tomar`: lo que el board enseña no depende de quién la tomó.
        cotejo = Cotejo()
        cotejo.tomar(cotejo.tareas()[0]["id"], "sonnet")
        self.assertEqual([o["operacion"] for o in self.operaciones()], ["tomar"])

    def test_una_tarea_que_ya_tiene_dueno_no_se_le_quita_a_nadie(self):
        cotejo = Cotejo()
        # El id que vale después de escribir es el que devuelve la escritura: al tocar la línea,
        # Cotejo le pone su marca de bloque y el «archivo:línea» de antes deja de nombrarla.
        tomada = cotejo.tomar(cotejo.tareas()[0]["id"], "opus")
        with self.assertRaises(ErrorCLI) as caso:
            Cotejo().tomar(tomada["id"], "haiku")
        self.assertIn("en-curso", caso.exception.mensaje)

    def test_despues_de_escribir_se_vuelve_a_leer_el_vault(self):
        # Lo cargado describía el vault de antes de la escritura. Seguir contestando con eso
        # sería decir que la tarea sigue pendiente justo después de haberla tomado.
        cotejo = Cotejo()
        cotejo.tomar(cotejo.tareas()[0]["id"], "opus")
        self.assertIsNone(cotejo._abierto)
        self.assertEqual(cotejo.tareas()[0]["estado"], "en-curso")
