"""Las reglas, medidas contra tareas reales.

La prueba que importa aquí no es la tasa de acierto: es que **ninguna tarea se decida por
debajo de lo que le toca**. Un fallo hacia arriba cuesta unos centavos; uno hacia abajo manda
un trabajo grande a un modelo que no da para él, y eso se paga rehaciéndolo. Si alguien ajusta
una regla y aparece el primer abaratado, esta prueba se pone roja antes de que llegue al vault.
"""

import json
import unittest

from apoyo import RAIZ

from enrutador import decision, reglas

ORDEN = {"n0": 0, "n1": 1, "n2": 2, "n3": 3}
CASOS = json.loads(
    (RAIZ / "enrutador" / "datos" / "evaluacion.json").read_text(encoding="utf-8"))["casos"]


def decidir_todos():
    humano, nivel = reglas.cargar()
    for caso in CASOS:
        yield caso, decision.decidir(caso["texto"], reglas_humano=humano, reglas_nivel=nivel)


class Evaluacion(unittest.TestCase):
    def test_el_set_son_tareas_reales_del_vault(self):
        self.assertGreaterEqual(len(CASOS), 30)
        self.assertTrue(all(c.get("proyecto") for c in CASOS))
        self.assertTrue(any(c["origen"] == "tag" for c in CASOS),
                        "sin casos etiquetados por una persona, la verdad de referencia es mía")

    def test_ninguna_tarea_se_decide_por_debajo_de_lo_que_le_toca(self):
        abaratadas = [(c["texto"][:70], c["esperado"], d.nivel.clave, d.regla)
                      for c, d in decidir_todos()
                      if ORDEN[d.nivel.clave] < ORDEN[c["esperado"]]]
        self.assertEqual(abaratadas, [], "estas se rutearon a un modelo más barato del que les "
                                         "toca, que es el único fallo que arruina la tarea")

    def test_la_tasa_de_acierto_no_baja_de_lo_medido(self):
        # 0,85 es lo que daban las reglas el 2026-09-18 sobre 42 casos. No es un objetivo: es un
        # suelo, para que un ajuste que arregle un caso y rompa cuatro no pase inadvertido.
        aciertos = sum(1 for c, d in decidir_todos() if d.nivel.clave == c["esperado"])
        self.assertGreaterEqual(aciertos / len(CASOS), 0.85)

    def test_todo_lo_que_no_es_para_un_modelo_se_reconoce(self):
        # Es la mitad que justifica el enrutador: 24 de 65 pendientes del vault son de este tipo.
        for caso, elegida in decidir_todos():
            if caso["esperado"] == "n0":
                self.assertFalse(elegida.despachable,
                                 f"iba a mandarse a un modelo: {caso['texto'][:70]}")


class FalsosVetos(unittest.TestCase):
    def test_una_web_para_el_celular_es_codigo(self):
        for texto in (
                "Crear la web ligera que muestre el menú en el celular, leyendo los datos "
                "del archivo JSON (HTML, CSS y JS; sin backend)",
                "Adaptar el formulario para que se vea bien en el celular",
                "Corregir el menú de navegación de la web para celular"):
            with self.subTest(texto=texto):
                self.assertTrue(decision.decidir(texto).despachable)

    def test_operar_el_celular_sigue_siendo_de_una_persona(self):
        for texto in (
                "Dejar los dos formularios como acceso directo en la pantalla de inicio del celular",
                "Probar el menú en mi celular",
                "Escanear el QR con el celular",
                "Instalar la aplicación en el celular"):
            with self.subTest(texto=texto):
                self.assertFalse(decision.decidir(texto).despachable)

    """Palabras que vetaban a una persona en tareas que son código (cotejo-n9mou2, sacadas del
    planning de Agent Debate). Y las mismas palabras en su sentido de siempre, que siguen
    vetando."""

    def test_token_contador_y_oauth_como_codigo_no_vetan(self):
        for texto in (
                "Contar debates y no llamadas: `/api/debate/start` emite un token firmado del "
                "debate, y la ruta de turnos rechaza los que no traigan un token válido",
                "Verificar Turnstile en `/api/debate/start` antes de emitir el token",
                "Pantalla de configuración con tres modos y contador de debates que quedan hoy",
                "Botón «Conectar con OpenRouter» con OAuth PKCE: redirigir, recibir el `code` y "
                "cambiarlo por la key del usuario"):
            with self.subTest(texto=texto[:50]):
                self.assertTrue(decision.decidir(texto).despachable)

    def test_las_mismas_palabras_como_persona_o_credencial_siguen_vetando(self):
        for texto in ("Confirmar con el contador la figura", "Sacar el token de Notion",
                      "Guardar el token en el gestor", "Generar un token de acceso en GitHub",
                      "Autorizar la app de Google por OAuth", "Sacar la API key de OpenRouter"):
            with self.subTest(texto=texto):
                self.assertFalse(decision.decidir(texto).despachable)


class VetosQueFaltaban(unittest.TestCase):
    """Lo contrario de `FalsosVetos`: tareas de una persona que se despachaban a un modelo
    (cotejo-c3r5o4, también del planning de Agent Debate)."""

    def test_abrir_algo_en_un_servicio_o_poner_alli_sus_variables_es_de_una_persona(self):
        for texto in ("Crear la base de Upstash Redis y el sitio de Cloudflare Turnstile",
                      "Crear el proyecto en Supabase", "Pasar las variables de entorno a Vercel"):
            with self.subTest(texto=texto):
                self.assertFalse(decision.decidir(texto).despachable)

    def test_decidir_y_poner_precio_es_de_una_persona(self):
        for texto in ("Decidir los paquetes de créditos y su precio en COP",
                      "Fijar el precio de la suscripción", "Decidir cuántos debates gratis dar"):
            with self.subTest(texto=texto):
                self.assertFalse(decision.decidir(texto).despachable)

    def test_lo_parecido_que_es_codigo_sigue_despachandose(self):
        for texto in ("Crear el cliente de Supabase en `lib/supabase.ts`",
                      "Crear el repo `enrutador` con las reglas, los niveles y el CLI",
                      "Partir `preguntar()` en decidir + ejecutar",
                      "Sacar los precios exactos por modelo de la skill `claude-api`",
                      "Leer el precio de cada paquete desde `lib/paquetes.ts`"):
            with self.subTest(texto=texto):
                self.assertTrue(decision.decidir(texto).despachable)


class Config(unittest.TestCase):
    def test_una_regla_propia_gana_a_las_de_fabrica(self):
        humano, nivel = reglas.cargar(extra=[{"nombre": "mia", "nivel": "n0",
                                              "patron": r"parseo", "porque": "porque sí"}])
        elegida = decision.decidir("Arreglar el parseo de los tags", reglas_humano=humano,
                                   reglas_nivel=nivel)
        self.assertEqual(elegida.regla, "mia")

    def test_una_regla_de_fabrica_se_puede_apagar_por_nombre(self):
        humano, _ = reglas.cargar(apagadas=["compras"])
        self.assertNotIn("compras", [r.nombre for r in humano])

    def test_toda_regla_explica_por_que(self):
        for grupo in reglas.cargar():
            for regla in grupo:
                self.assertTrue(regla.porque.strip())


if __name__ == "__main__":
    unittest.main()
