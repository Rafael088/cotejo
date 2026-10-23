"""El progreso del inicio: la bitácora traducida a los cinco pasos de la pantalla Preparando.

Dos tipos de prueba. Las reales corren los verbos de verdad (`init`, `editar`, `proponer`,
`anotar`, `crear`) en un repo temporal con `COTEJO_FUENTE=repo`, como el agente de la
preparación, y leen lo que dejaron en la bitácora. Las sintéticas escriben líneas a mano para
los casos que un agente sano no produce: pasos desordenados, repetidos, un proceso colgado.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ
from tareas import inicio, progreso

VERBOS = [p.verbo for p in inicio.PASOS]


def estados(pasos):
    return [p["estado"] for p in pasos]


def linea(operacion, carpeta, cuando, **extra):
    base = {"cuando": cuando, "operacion": operacion, "proyecto": os.path.basename(carpeta),
            "carpeta": carpeta}
    return json.dumps({**base, **extra})


def crear(carpeta, cuando, identificador, nota=None):
    nombre = os.path.basename(carpeta)
    return json.dumps({"cuando": cuando, "operacion": "crear", "id": identificador,
                       "proyecto": nombre, "texto": "algo",
                       "nota": nota or f"{nombre}/.cotejo/tareas.md", "agente": ""})


class Sintetica(unittest.TestCase):
    C = "/tmp/proyectos/lista"

    def eventos(self, *lineas, desde=0):
        return progreso.eventos_de(lineas, self.C, desde)

    def test_sin_nada_el_primero_esta_en_curso_y_los_demas_pendientes(self):
        pasos = progreso.pasos([])
        self.assertEqual([p["verbo"] for p in pasos], VERBOS)
        self.assertEqual([p["titulo"] for p in pasos], [p.titulo for p in inicio.PASOS])
        self.assertEqual(estados(pasos), ["en curso", "pendiente", "pendiente", "pendiente",
                                          "pendiente"])

    def test_cada_verbo_hace_hecho_el_suyo_y_deja_en_curso_el_siguiente(self):
        e = self.eventos(linea("init", self.C, 100, git_init=True, creados=5),
                         linea("editar", self.C, 130, tipo="proyecto", entrada="proyecto"))
        pasos = progreso.pasos(e, "preparando", desde=90, ahora=140)
        self.assertEqual(estados(pasos), ["hecho", "hecho", "en curso", "pendiente", "pendiente"])
        self.assertEqual((pasos[0]["inicio"], pasos[0]["fin"], pasos[0]["duracion"]),
                         (90, 100, 10))
        self.assertEqual((pasos[1]["inicio"], pasos[1]["fin"], pasos[1]["duracion"]),
                         (100, 130, 30))
        self.assertEqual((pasos[2]["inicio"], pasos[2]["fin"], pasos[2]["duracion"]),
                         (130, None, 10))
        self.assertEqual(pasos[0]["detalle"], "Carpeta creada y preparada")
        self.assertEqual(pasos[1]["detalle"], "Proyecto escrito")
        self.assertEqual(pasos[2]["detalle"], "En marcha")
        self.assertIsNone(pasos[3]["inicio"])

    def test_detalles_con_cuenta(self):
        e = self.eventos(
            linea("init", self.C, 1), linea("editar", self.C, 2, tipo="proyecto", entrada="p"),
            *[linea("proponer", self.C, 3, tipo="decision", entrada=f"dec-{i}") for i in range(3)],
            linea("anotar", self.C, 4, tipo="arquitectura", entrada="arq-1", piezas=5),
            *[crear(self.C, 5, f"t{i}") for i in range(6)])
        pasos = progreso.pasos(e, "listo")
        self.assertEqual(estados(pasos), ["hecho"] * 5)
        self.assertEqual(pasos[2]["detalle"], "3 decisiones propuestas")
        self.assertEqual(pasos[3]["detalle"], "Arquitectura anotada: 5 piezas")
        self.assertEqual(pasos[4]["detalle"], "6 tareas creadas")
        self.assertEqual(pasos[4]["n"], 6)

    def test_una_sola_se_dice_en_singular(self):
        e = self.eventos(linea("proponer", self.C, 3, entrada="dec-1"), crear(self.C, 4, "t1"))
        pasos = progreso.pasos(e)
        self.assertEqual(pasos[2]["detalle"], "1 decisión propuesta")
        self.assertEqual(pasos[4]["detalle"], "1 tarea creada")

    def test_mientras_crea_el_ultimo_sigue_en_curso_y_al_terminar_pasa_a_hecho(self):
        e = self.eventos(linea("init", self.C, 1),
                         linea("editar", self.C, 2, tipo="proyecto", entrada="p"),
                         linea("proponer", self.C, 3, entrada="d1"),
                         linea("anotar", self.C, 4, tipo="arquitectura", entrada="a1"),
                         crear(self.C, 5, "t1"))
        self.assertEqual(estados(progreso.pasos(e, "preparando"))[-1], "en curso")
        self.assertEqual(estados(progreso.pasos(e, {"estado": "listo"}))[-1], "hecho")

    def test_pasos_fuera_de_orden_dejan_pendiente_el_que_falta(self):
        e = self.eventos(linea("init", self.C, 1), crear(self.C, 2, "t1"),
                         linea("proponer", self.C, 3, entrada="d1"))
        pasos = progreso.pasos(e, "preparando")
        self.assertEqual(estados(pasos), ["hecho", "pendiente", "hecho", "pendiente", "en curso"])
        self.assertEqual(estados(progreso.pasos(e, "listo")),
                         ["hecho", "pendiente", "hecho", "pendiente", "hecho"])

    def test_pasos_repetidos_no_suman_dos_veces_lo_mismo(self):
        e = self.eventos(linea("proponer", self.C, 3, entrada="d1"),
                         linea("proponer", self.C, 4, entrada="d1"),
                         linea("proponer", self.C, 5, entrada="d2"),
                         linea("init", self.C, 6), linea("init", self.C, 7),
                         crear(self.C, 8, "t1"), crear(self.C, 9, "t1"))
        pasos = progreso.pasos(e)
        self.assertEqual(pasos[2]["detalle"], "2 decisiones propuestas")
        self.assertEqual(pasos[4]["n"], 1)
        self.assertEqual(pasos[0]["fin"], 7)

    def test_editar_y_anotar_de_otro_tipo_no_cuentan(self):
        e = self.eventos(linea("editar", self.C, 2, tipo="arquitectura", entrada="arq-1"),
                         linea("editar", self.C, 3, tipo="referencia", entrada="ref-1"),
                         linea("anotar", self.C, 4, tipo="problema", entrada="prob-1"),
                         linea("anotar", self.C, 5, tipo="aprendizaje", entrada="apr-1"))
        self.assertEqual(e, [])
        self.assertEqual(progreso.pasos(e)[0]["estado"], "en curso")
        e = self.eventos(linea("anotar", self.C, 5, tipo="arquitectura", entrada="a1"))
        self.assertEqual(progreso.pasos(e)[3]["estado"], "hecho")

    def test_lineas_de_otro_proyecto_o_de_otra_fuente_no_cuentan(self):
        e = self.eventos(linea("init", "/tmp/otros/lista2", 1), linea("init", "/tmp/x/lista", 2),
                         crear(self.C, 3, "t1", nota="01-Proyectos/lista.md"),
                         json.dumps({"cuando": 4, "operacion": "tomar", "id": "x"}),
                         "esto no es json", "[1, 2]", json.dumps({"operacion": "init"}))
        self.assertEqual(e, [])

    def test_lo_anterior_al_lanzamiento_no_cuenta_si_se_reintento(self):
        lineas = (linea("init", self.C, 10), linea("init", self.C, 100))
        self.assertEqual(len(self.eventos(*lineas)), 2)
        self.assertEqual(len(self.eventos(*lineas, desde=50)), 1)

    def test_colgado_o_fallo_ponen_el_paso_en_curso_en_fallo(self):
        e = self.eventos(linea("init", self.C, 1),
                         linea("editar", self.C, 2, tipo="proyecto", entrada="p"))
        for nivel in ("colgado", "fallo"):
            pasos = progreso.pasos(e, {"estado": nivel, "por_que": "Se paró."})
            self.assertEqual(estados(pasos), ["hecho", "hecho", "fallo", "pendiente", "pendiente"])
            self.assertEqual(pasos[2]["detalle"], "Se paró.")
            self.assertIsNone(pasos[2]["fin"])
        self.assertEqual(progreso.pasos(e, "fallo")[2]["detalle"], "Se detuvo en este paso")
        self.assertEqual(estados(progreso.pasos([], "fallo"))[0], "fallo")

    def test_fallo_en_el_ultimo_paso_con_tareas_a_medias(self):
        e = self.eventos(*[linea(v, self.C, i, tipo={"editar": "proyecto",
                                                    "anotar": "arquitectura"}.get(v), entrada=v)
                           for i, v in enumerate(VERBOS[:4], 1)], crear(self.C, 9, "t1"))
        pasos = progreso.pasos(e, "colgado")
        self.assertEqual(estados(pasos), ["hecho"] * 4 + ["fallo"])
        self.assertEqual(pasos[4]["n"], 1)

    def test_preparacion_en_terminal_o_vista_se_lee_por_lo_que_dejo(self):
        e = self.eventos(linea("init", self.C, 1))
        for nivel in ("en-terminal", "visto", None, "preparando"):
            self.assertEqual(estados(progreso.pasos(e, nivel))[:2], ["hecho", "en curso"])

    def test_el_estado_puede_ser_el_dict_de_la_preparacion(self):
        e = self.eventos(linea("init", self.C, 1))
        self.assertEqual(progreso.pasos(e, {"estado": "preparando", "id": "x"})[1]["estado"],
                         "en curso")

    def test_los_pasos_no_cambian_la_entrada(self):
        e = self.eventos(linea("init", self.C, 1))
        antes = json.dumps(e)
        progreso.pasos(e, "fallo", ahora=50)
        self.assertEqual(json.dumps(e), antes)


class Seguir(unittest.TestCase):
    """`Seguimiento`: leer la bitácora por offset."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.archivo = Path(tmp.name) / "bitacora.jsonl"
        self.c = "/tmp/proyectos/lista"
        self.s = progreso.Seguimiento(self.c, 0, self.archivo)

    def escribir(self, *lineas, fin="\n"):
        with open(self.archivo, "a", encoding="utf-8") as f:
            f.write("\n".join(lineas) + fin)

    def test_sin_bitacora_al_principio_no_falla_y_sigue_cuando_aparece(self):
        self.assertFalse(self.s.avanzar())
        self.assertEqual(estados(self.s.pasos())[:2], ["en curso", "pendiente"])
        self.escribir(linea("init", self.c, 5))
        self.assertTrue(self.s.avanzar())
        self.assertEqual(estados(self.s.pasos())[:2], ["hecho", "en curso"])

    def test_solo_lee_lo_que_creció(self):
        self.escribir(linea("init", self.c, 1), json.dumps({"cuando": 1, "operacion": "tomar",
                                                             "id": "a"}))
        self.assertTrue(self.s.avanzar())
        fin = self.s.offset
        self.assertEqual(fin, self.archivo.stat().st_size)
        self.assertFalse(self.s.avanzar())
        self.escribir(linea("proponer", self.c, 2, entrada="d1"))
        self.assertTrue(self.s.avanzar())
        self.assertEqual(len(self.s.eventos), 2)
        self.assertEqual(self.s.offset, self.archivo.stat().st_size)

    def test_no_relee_lo_viejo(self):
        self.escribir(linea("init", self.c, 1))
        self.s.avanzar()
        # Si volviera a leer desde el principio, esta línea cambiada se vería.
        texto = self.archivo.read_text().replace('"init"', '"zzzz"')
        self.archivo.write_text(texto)
        self.s.avanzar()
        self.assertEqual(len(self.s.eventos), 1)

    def test_una_linea_a_medias_espera_a_que_se_complete(self):
        completa = linea("init", self.c, 1)
        self.escribir(completa[:20], fin="")
        self.assertFalse(self.s.avanzar())
        self.assertEqual(self.s.offset, 0)
        self.escribir(completa[20:])
        self.assertTrue(self.s.avanzar())
        self.assertEqual(len(self.s.eventos), 1)

    def test_si_el_archivo_se_vacia_empieza_de_nuevo(self):
        self.escribir(linea("init", self.c, 1), linea("proponer", self.c, 2, entrada="d"))
        self.s.avanzar()
        self.archivo.write_text(linea("init", self.c, 9) + "\n")
        self.assertTrue(self.s.avanzar() or len(self.s.eventos) == 1)
        self.assertEqual([e["cuando"] for e in self.s.eventos], [9])

    def test_la_primera_lectura_mira_solo_la_cola(self):
        from tareas import bitacora
        relleno = json.dumps({"cuando": 1, "operacion": "tomar", "id": "x", "texto": "r" * 500})
        self.escribir(linea("init", self.c, 1),
                      *[relleno] * (bitacora.COLA_BYTES // 500 + 20),
                      linea("editar", self.c, 2, tipo="proyecto", entrada="p"))
        self.s.avanzar()
        self.assertEqual([e["operacion"] for e in self.s.eventos], ["editar"])

    def test_desde_ignora_lo_anterior(self):
        s = progreso.Seguimiento(self.c, 50, self.archivo)
        self.escribir(linea("init", self.c, 10), linea("init", self.c, 60))
        s.avanzar()
        self.assertEqual([e["cuando"] for e in s.eventos], [60])

    def test_crudo_trae_las_lineas_tal_cual_y_el_final_del_log(self):
        log = Path(self.archivo.parent) / "agente.log"
        log.write_text("hola\n" * 3 + "fin")
        propia = linea("init", self.c, 1)
        self.escribir(propia, linea("init", "/otro/sitio", 2))
        self.s.avanzar()
        crudo = self.s.crudo({"log": str(log)})
        self.assertEqual(crudo["bitacora"], [propia])
        self.assertTrue(crudo["log"].endswith("fin"))
        self.assertEqual(self.s.crudo()["log"], "")
        self.assertEqual(self.s.crudo(lineas=1)["bitacora"], [propia])

    def test_de_preparacion_usa_carpeta_y_hora_del_registro(self):
        s = progreso.de_preparacion({"carpeta": self.c, "ts": 7}, self.archivo)
        self.assertEqual((s.carpeta, s.desde), (self.c, 7))


class ConVerbosReales(unittest.TestCase):
    """Lo que dejan de verdad `cotejo init/editar/proponer/anotar/crear`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.casa = base / "casa"
        self.casa.mkdir()
        self.carpeta = str(base / "proyectos" / "lista-compra")
        self.bitacora = base / "estado" / "bitacora.jsonl"
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("COTEJO_", "FOCO_", "XDG_"))}
        self.env.update(HOME=str(self.casa), XDG_CONFIG_HOME=str(base / "config"),
                        XDG_STATE_HOME=str(base / "xdg-estado"), XDG_DATA_HOME=str(base / "datos"),
                        COTEJO_ESTADO=str(base / "estado"), COTEJO_FUENTE="repo",
                        PYTHONPATH=str(RAIZ), GIT_CONFIG_GLOBAL=os.devnull)
        self.s = progreso.Seguimiento(self.carpeta, 0, self.bitacora)

    def cotejo(self, *args):
        hecho = subprocess.run([sys.executable, "-m", "tareas", *args], cwd=self.casa,
                               env=self.env, capture_output=True, text=True, timeout=60)
        self.assertEqual(hecho.returncode, 0, f"{args}: {hecho.stderr}{hecho.stdout}")
        return json.loads(hecho.stdout)

    def paso(self, *args):
        self.cotejo(*args)
        self.s.avanzar()
        return self.s.pasos("preparando", ahora=int(__import__("time").time()))

    def test_el_agente_hace_los_cinco_pasos_y_la_pantalla_los_sigue(self):
        c = self.carpeta
        pasos = self.paso("init", "--repo", c)
        self.assertEqual(estados(pasos), ["hecho", "en curso", "pendiente", "pendiente",
                                          "pendiente"])
        self.assertEqual(pasos[0]["detalle"], "Carpeta creada y preparada")

        version = self.cotejo("leer", "proyecto", "--repo", c)["version"]
        # Editar algo que no es el proyecto no mueve el paso 2: la arquitectura viene después.
        pasos = self.paso("editar", "proyecto", "--repo", c, "--version", version, "--texto",
                          "## Objetivo\nLista de la compra.\n## Stack\nPython.\n"
                          "## Siguiente paso\nModelo de datos.")
        self.assertEqual(estados(pasos)[:3], ["hecho", "hecho", "en curso"])

        self.cotejo("proponer", "decision", "--repo", c, "--titulo", "SQLite",
                    "--temas", "datos", "--texto", "Un archivo basta.")
        pasos = self.paso("proponer", "decision", "--repo", c, "--titulo", "Sin cuentas",
                          "--temas", "alcance", "--texto", "Se comparte por enlace.")
        self.assertEqual(pasos[2]["detalle"], "2 decisiones propuestas")
        self.assertEqual(estados(pasos)[2:], ["hecho", "en curso", "pendiente"])

        # Un problema anotado no es la arquitectura: el paso 4 sigue en curso.
        pasos = self.paso("anotar", "problema", "--repo", c, "--titulo", "Algo raro",
                          "--texto", "No se sabe todavía.")
        self.assertEqual(estados(pasos)[3], "en curso")
        pasos = self.paso("anotar", "arquitectura", "--repo", c, "--titulo", "Arquitectura",
                          "--temas", "arquitectura", "--texto", "Web y SQLite.",
                          "--pieza", "ve|Pantalla|Lo que ve la gente||",
                          "--pieza", "guarda|Base|Los artículos|SQLite|")
        self.assertEqual(pasos[3]["detalle"], "Arquitectura anotada: 2 piezas")
        self.assertEqual(estados(pasos)[3:], ["hecho", "en curso"])

        for tarea in ("Modelo de datos: tabla", "Pantalla de la lista"):
            self.cotejo("crear", tarea, "--proyecto", "lista-compra", "--version", "0.1.0")
        self.cotejo("crear", "Pantalla de la lista", "--proyecto", "lista-compra",
                    "--version", "0.1.0")  # repetida: no se anota ni se cuenta dos veces
        self.s.avanzar()
        pasos = self.s.pasos("preparando")
        self.assertEqual(pasos[4]["detalle"], "2 tareas creadas")
        self.assertEqual(estados(pasos)[4], "en curso")
        pasos = self.s.pasos({"estado": "listo"})
        self.assertEqual(estados(pasos), ["hecho"] * 5)
        self.assertEqual(pasos[1]["detalle"], "Proyecto escrito")

        crudo = self.s.crudo()["bitacora"]
        self.assertEqual([json.loads(x)["operacion"] for x in crudo],
                         ["init", "editar", "proponer", "proponer", "anotar", "crear", "crear"])

    def test_editar_la_arquitectura_o_los_verbos_de_otro_proyecto_no_cuentan(self):
        c = self.carpeta
        self.cotejo("init", "--repo", c)
        self.cotejo("init", "--repo", os.path.join(os.path.dirname(c), "otro"))
        arq = self.cotejo("anotar", "arquitectura", "--repo", c, "--titulo", "Arq", "--texto",
                          "x", "--pieza", "ve|Pantalla|Algo||")["id"]
        leida = self.cotejo("leer", arq, "--repo", c)
        self.cotejo("editar", arq, "--repo", c, "--version", leida["version"], "--texto",
                    leida["cuerpo"] + "\nMás.")
        self.s.avanzar()
        self.assertEqual([e["operacion"] for e in self.s.eventos], ["init", "anotar"])
        self.assertEqual(len(self.s.crudas), 2)
        editadas = [json.loads(x) for x in self.bitacora.read_text().splitlines()]
        self.assertEqual([x["operacion"] for x in editadas],
                         ["init", "init", "anotar", "editar"])  # sí quedó en la bitácora
        self.assertEqual(editadas[-1]["tipo"], "arquitectura")


if __name__ == "__main__":
    unittest.main()
