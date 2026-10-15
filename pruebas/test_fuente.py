"""La capa `Fuente`: que Cotejo funcione con un segundo cerebro que no es Obsidian.

Esta es la prueba que justifica la capa. Todo lo demás se puede comprobar contra el vault de
mentira, pero eso no distingue entre «funciona» y «funciona porque por dentro sigue siendo
Markdown». Aquí se enchufa una fuente que vive en memoria —sin notas, sin tags, sin rutas— y
se corren contra ella los mismos verbos que usa un agente. Si alguien vuelve a colar una
suposición sobre Obsidian en `cli.py`, `estado.py` o el modelo, esto se pone rojo.

La fuente de mentira es a la vez el ejemplo más corto de qué hay que escribir para añadir un
segundo cerebro nuevo: cuatro métodos.
"""

import os
import unittest
from dataclasses import replace
from unittest import mock

from apoyo import PruebaDeCLI
from tareas import configuracion, estado, fuente as f, modelo


class Memoria(f.Fuente):
    """Un segundo cerebro de mentira: las tareas viven en una lista y no hay archivos.

    Deja los valores por defecto de `Fuente` para lo que no aplica: no hay nada que vigilar
    (`vigilables`) ni app donde abrir una tarea (`uri`). Eso no la hace una fuente coja: el
    board pierde la recarga automática y el botón de abrir, no la capacidad de mover tareas.
    """

    nombre = "memoria"

    def __init__(self, config=None):
        self.problema = (config or {}).get("problema")
        self.proyecto = modelo.Proyecto("Cosas", donde="lista de cosas", estado="activo")
        self.proyecto.tareas = [
            modelo.Tarea("Comprar café", id="m1", donde="lista de cosas", dificultad="facil"),
            modelo.Tarea("Llamar al banco", id="m2", donde="lista de cosas",
                         estado="en-curso", agente="sonnet"),
        ]
        self.proyecto.hechas = [
            modelo.Tarea("Regar las plantas", id="m3", donde="lista de cosas", hecha=True),
        ]
        self.escrituras = 0

    def escanear(self, incluir_hechas=False, avisos=None):
        proyecto = replace(self.proyecto, tareas=list(self.proyecto.tareas),
                           hechas=list(self.proyecto.hechas) if incluir_hechas else [])
        return [proyecto]

    def _guardar(self, tarea, **cambios):
        self.escrituras += 1
        nueva = replace(tarea, **cambios)
        for lista in (self.proyecto.tareas, self.proyecto.hechas):
            for i, vieja in enumerate(lista):
                if vieja.id == tarea.id:
                    lista.pop(i)
                    break
        (self.proyecto.hechas if nueva.hecha else self.proyecto.tareas).append(nueva)
        return nueva

    def marcar(self, tarea, hecha=True):
        return self._guardar(tarea, hecha=hecha,
                             estado=modelo.PENDIENTE if hecha else tarea.estado)

    def poner_estado(self, tarea, nuevo):
        return self._guardar(tarea, estado=nuevo)

    def poner_agente(self, tarea, agente):
        return self._guardar(tarea, agente=agente)


class PruebaConMemoria(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        # Una sola fuente para toda la prueba: la CLI la abre en cada invocación, como haría
        # de verdad, y lo que escribió una llamada tiene que seguir ahí en la siguiente.
        self.memoria = Memoria()
        parche = mock.patch.dict(f.FUENTES, {"memoria": self.construir})
        parche.start()
        self.addCleanup(parche.stop)
        entorno = mock.patch.dict("os.environ", {"COTEJO_FUENTE": "memoria"})
        entorno.start()
        self.addCleanup(entorno.stop)

    def construir(self, config):
        self.memoria.problema = (config or {}).get("problema")
        return self.memoria


class LosVerbosNoSabenDeObsidian(PruebaConMemoria):
    def test_listar_devuelve_las_tareas_de_la_fuente(self):
        codigo, datos = self.correr("tareas", "--todas")
        self.assertEqual(codigo, 0)
        self.assertEqual({t["texto"] for t in datos["tareas"]},
                         {"Comprar café", "Llamar al banco", "Regar las plantas"})
        self.assertEqual(datos["tareas"][0]["proyecto"], "Cosas")

    def test_los_filtros_siguen_valiendo(self):
        _, datos = self.correr("tareas", "--estado", "en-curso")
        self.assertEqual([t["id"] for t in datos["tareas"]], ["m2"])

    def test_tomar_y_entregar_recorren_las_columnas(self):
        codigo, datos = self.correr("tomar", "m1", "--agente", "opus")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["estado"], "en-curso")
        self.assertEqual(datos["tarea"]["agente"], "opus")
        codigo, datos = self.correr("entregar", "m1", "--evidencia", "ya está")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["estado"], "por-validar")

    def test_bloquear_la_suelta_con_su_motivo(self):
        self.correr("tomar", "m1", "--agente", "opus")
        _, datos = self.correr("bloquear", "m1", "--motivo", "No hay café en la tienda")
        self.assertEqual(datos["tarea"]["estado"], "pendiente")
        self.assertEqual(datos["tarea"]["agente"], "")
        _, datos = self.correr("tareas", "--estado", "pendiente")
        bloqueada = next(t for t in datos["tareas"] if t["id"] == "m1")
        self.assertEqual(bloqueada["motivo"], "No hay café en la tienda")

    def test_no_se_toca_ningun_archivo_del_vault(self):
        """La prueba de que la capa sirve: los mismos verbos, sin un solo Markdown detrás."""
        self.correr("tomar", "m1", "--agente", "opus")
        self.correr("entregar", "m1", "--evidencia", "x")
        self.assertEqual(list((self.vault / self.CARPETA).iterdir()), [])
        # Tomar escribe dos veces (el estado y el agente) y entregar una: el trabajo lo hizo
        # la fuente entera, no un atajo que se saltó la capa.
        self.assertEqual(self.memoria.escrituras, 3)

    def test_el_resumen_de_la_barra_tambien_sale_de_la_fuente(self):
        datos = estado.calcular()
        self.assertEqual(datos["proyectos"], 1)
        self.assertEqual(datos["pendientes"], 2)
        self.assertNotIn("error", datos)

    def test_una_fuente_que_no_sabe_crear_lo_dice_con_su_nombre(self):
        # `crear` es opcional en la interfaz: la fuente sigue sirviendo para todo lo demás, y
        # la CLI tiene que decirlo en vez de reventar con un NotImplementedError.
        codigo, datos = self.correr("crear", "Comprar pan", "--proyecto", "Cosas")
        self.assertEqual(codigo, 3)
        self.assertIn("memoria", datos["error"])
        self.assertEqual(self.memoria.escrituras, 0)

    def test_un_id_que_no_existe_se_explica_igual(self):
        codigo, datos = self.correr("tomar", "no-existe", "--agente", "opus")
        self.assertNotEqual(codigo, 0)
        self.assertTrue(datos["reintentable"])


class CuandoLaFuenteNoEstaLista(PruebaConMemoria):
    def setUp(self):
        super().setUp()
        parche = mock.patch.object(f, "cargar_config",
                                   return_value={"fuente": "memoria", "problema": "Falta el token"})
        parche.start()
        self.addCleanup(parche.stop)

    def test_la_cli_repite_lo_que_dice_la_fuente_y_no_escribe(self):
        codigo, datos = self.correr("tareas")
        self.assertNotEqual(codigo, 0)
        self.assertEqual(datos["salida"], "Falta el token")

    def test_el_resumen_lo_dice_en_vez_de_devolver_ceros(self):
        """Un cero y un «no pude mirar» se ven igual en la barra si nadie los distingue."""
        self.assertEqual(estado.calcular()["error"], "Falta el token")


class ElijeLaFuente(unittest.TestCase):
    def _entorno(self, **extra):
        entorno = {k: v for k, v in os.environ.items()
                   if k not in ("COTEJO_FUENTE", "COTEJO_VAULT")}
        entorno["COTEJO_CONFIG"] = "/ruta/que/no/existe/config.json"
        entorno.update(extra)
        return mock.patch.dict(os.environ, entorno, clear=True)

    def test_por_defecto_es_el_repo(self):
        # v1.2.4: sin config y sin COTEJO_FUENTE, la entrada es el repo, no un vault.
        with self._entorno():
            self.assertEqual(f.cargar_config()["fuente"], "repo")

    def test_la_config_sin_fuente_ni_rastro_de_obsidian_es_repo(self):
        datos = {"fuentes": {"repo": {"repos": ["/x"]}}, "tema": "oscuro"}
        with self._entorno():
            self.assertEqual(configuracion.fuente_activa(datos), "repo")

    def test_quien_ya_usaba_obsidian_sin_escribir_fuente_sigue_en_obsidian(self):
        with self._entorno():
            self.assertEqual(configuracion.fuente_activa({"vault": "/v"}), "obsidian")
            self.assertEqual(configuracion.fuente_activa(
                {"fuentes": {"obsidian": {"vault": "/v"}}}), "obsidian")
        with self._entorno(COTEJO_VAULT="/v"):
            self.assertEqual(configuracion.fuente_activa({}), "obsidian")

    def test_fuente_escrita_o_en_el_entorno_manda(self):
        with self._entorno():
            self.assertEqual(configuracion.fuente_activa({"fuente": "obsidian"}), "obsidian")
        with self._entorno(COTEJO_FUENTE="obsidian"):
            self.assertEqual(configuracion.fuente_activa({}), "obsidian")

    def test_una_fuente_que_no_existe_dice_cuales_hay(self):
        with self.assertRaises(ValueError) as caso:
            f.abrir({"fuente": "notion"})
        self.assertIn("obsidian", str(caso.exception))

    def test_la_interfaz_no_trae_nada_hecho_a_medias(self):
        """Los métodos que una fuente tiene que escribir sí o sí revientan si no se escriben,
        en vez de devolver una lista vacía y hacer creer que no hay tareas."""
        for metodo, args in (("escanear", ()), ("marcar", (None,)),
                             ("poner_estado", (None, "en-curso")), ("poner_agente", (None, "x"))):
            with self.subTest(metodo=metodo):
                with self.assertRaises(NotImplementedError):
                    getattr(f.Fuente(), metodo)(*args)


if __name__ == "__main__":
    unittest.main()
