"""`buscar` (v1.2, B2): una línea por entrada del almacén `.cotejo/`, barata.

Todo corre contra un repo de mentira en una carpeta temporal, como `test_almacen.py`, pero
pasando por la CLI de verdad (`tareas.cli.main`) y no por `Almacen` directo: lo que se vigila
es el verbo —cómo resuelve el repo, cómo filtra, qué tan barata sale la línea— y no el almacén,
que ya tiene su batería.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)
from tareas import almacen, cli, conocimiento


class PruebaDeBuscar(unittest.TestCase):

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "mi-repo"
        (self.repo / ".git").mkdir(parents=True)
        self.almacen = almacen.Almacen(self.repo)
        hoy = mock.patch.object(almacen, "_hoy", return_value="2026-10-04")
        hoy.start()
        self.addCleanup(hoy.stop)

    def correr(self, *args):
        """Llama a `cli.main` y devuelve (código, JSON de lo que imprimió)."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            codigo = cli.main(list(args))
        salida = buf.getvalue().strip()
        return codigo, (json.loads(salida) if salida else None)

    def buscar(self, *args):
        return self.correr("buscar", "--repo", str(self.repo), *args)

    def ids(self, *args):
        _, datos = self.buscar(*args)
        return [e["id"] for e in datos["entradas"]]

    def leer(self, entrada_id, *args):
        return self.correr("leer", entrada_id, "--repo", str(self.repo), *args)

    def proponer_decision(self, *args):
        return self.correr("proponer", "decision", "--repo", str(self.repo), *args)

    def anotar(self, tipo, *args):
        return self.correr("anotar", tipo, "--repo", str(self.repo), *args)

    def bitacora(self, texto, *args):
        return self.correr("bitacora", texto, "--repo", str(self.repo), *args)

    def contexto(self, *args):
        return self.correr("contexto", "--repo", str(self.repo), *args)

    def editar(self, entrada_id, *args):
        return self.correr("editar", entrada_id, "--repo", str(self.repo), *args)

    def resolver(self, entrada_id, *args):
        return self.correr("resolver", entrada_id, "--repo", str(self.repo), *args)


class ResolverRepo(PruebaDeBuscar):

    def test_sin_repo_git_el_error_es_exacto(self):
        fuera = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(fuera, ignore_errors=True))
        codigo, datos = self.correr("buscar", "--repo", str(fuera))
        self.assertEqual(codigo, 3)
        self.assertEqual(datos, {
            "esquema": 1, "error": "No estás dentro de un repo git",
            "salida": "`cotejo init` se corre dentro de un repo (o con --repo apuntando a "
                      "uno). Si todavía no lo es, `git init` primero.",
            "reintentable": False})

    def test_el_techo_git_para_la_busqueda(self):
        # Una temporal dentro de un repo (o de /tmp, si /tmp lo es) no hereda ese repo.
        from tareas import conexion
        techo = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(techo, ignore_errors=True))
        (techo / ".git").mkdir()
        dentro = techo / "temporal"
        dentro.mkdir()
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(techo)}):
            self.assertIsNone(conexion._raiz_git(dentro))
        self.assertEqual(conexion._raiz_git(dentro), techo)

    def test_repo_con_git_pero_sin_cotejo_pide_init(self):
        # Con repo de git pero sin `.cotejo/` el arreglo es otro (`cotejo init`, no `git init`),
        # así que el error tiene que ser distinto del de no estar en un repo git.
        codigo, datos = self.buscar()
        self.assertEqual(codigo, 3)
        self.assertEqual(datos, {"esquema": 1, "error": "Este repo no tiene .cotejo/",
                                 "salida": "`cotejo init`", "reintentable": False})

    def test_repo_que_no_es_una_carpeta_se_rechaza_antes(self):
        codigo, datos = self.correr("buscar", "--repo", str(self.repo / "no-existe"))
        self.assertEqual(codigo, 3)
        self.assertIn("no es una carpeta", datos["error"])

    def test_sin_repo_usa_la_raiz_git_de_la_carpeta_actual(self):
        self.almacen.crear("problema", "Se cae el login")
        sub = self.repo / "src" / "modulo"
        sub.mkdir(parents=True)
        import os
        anterior = os.getcwd()
        os.chdir(sub)
        self.addCleanup(os.chdir, anterior)
        codigo, datos = self.correr("buscar")
        self.assertEqual((codigo, datos["total"]), (0, 1))

    def test_no_escribe_nada_en_cotejo(self):
        self.almacen.crear("problema", "Se cae el login")
        antes = sorted((self.repo / ".cotejo").rglob("*"))
        self.buscar()
        despues = sorted((self.repo / ".cotejo").rglob("*"))
        self.assertEqual(antes, despues)


class SinFiltros(PruebaDeBuscar):

    def test_sin_entradas_la_lista_sale_vacia(self):
        # `.cotejo/` existe (como lo deja `cotejo init`) pero no hay ninguna entrada todavía.
        (self.repo / ".cotejo" / "decisiones").mkdir(parents=True)
        codigo, datos = self.buscar()
        self.assertEqual((codigo, datos["total"], datos["entradas"]), (0, 0, []))

    def test_cada_tipo_sale_en_la_busqueda_general(self):
        self.almacen.crear("decision", "D", autor="x")
        self.almacen.crear("problema", "P")
        self.almacen.crear("referencia", "R")
        codigo, datos = self.buscar()
        self.assertEqual((codigo, datos["total"]), (0, 3))
        self.assertEqual({e["tipo"] for e in datos["entradas"]},
                         {"decision", "problema", "referencia"})

    def test_salen_ordenadas_por_ruta_de_forma_estable(self):
        self.almacen.crear("referencia", "Zeta")
        self.almacen.crear("referencia", "Alfa")
        self.almacen.crear("decision", "D", autor="x")
        _, primera = self.buscar()
        _, segunda = self.buscar()
        self.assertEqual([e["id"] for e in primera["entradas"]],
                         [e["id"] for e in segunda["entradas"]])


class Linea(PruebaDeBuscar):

    def test_la_linea_trae_id_tipo_titulo_y_resumen(self):
        entrada = self.almacen.crear("referencia", "Manual de marca", "Colores y voz.")
        _, datos = self.buscar()
        linea = datos["entradas"][0]
        self.assertEqual(linea, {"id": entrada.id, "tipo": "referencia",
                                 "titulo": "Manual de marca", "resumen": "Colores y voz."})

    def test_el_estado_sale_solo_si_la_entrada_lo_tiene(self):
        self.almacen.crear("decision", "D", autor="x")
        self.almacen.crear("referencia", "R")
        _, datos = self.buscar()
        por_tipo = {e["tipo"]: e for e in datos["entradas"]}
        self.assertEqual(por_tipo["decision"]["estado"], "propuesta")
        self.assertNotIn("estado", por_tipo["referencia"])

    def test_el_resumen_usa_el_mismo_recorte_que_el_almacen(self):
        entrada = self.almacen.crear("referencia", "Larga", "palabra " * 100)
        _, datos = self.buscar()
        self.assertEqual(datos["entradas"][0]["resumen"], entrada.resumen())

    def test_avisos_de_frontmatter_roto_se_propagan(self):
        self.almacen.crear("problema", "Bueno")
        roto = self.repo / ".cotejo" / "problemas" / "roto.md"
        roto.parent.mkdir(parents=True, exist_ok=True)
        roto.write_text("---\nid: pro-zzzz\nesto no\n---\n", encoding="utf-8")
        codigo, datos = self.buscar()
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["total"], 1)
        self.assertEqual(len(datos["avisos"]), 1)
        self.assertIn(".cotejo/problemas/roto.md", datos["avisos"][0]["nota"])


class Filtros(PruebaDeBuscar):

    def test_tipo_filtra_a_uno_solo(self):
        self.almacen.crear("decision", "D", autor="x")
        self.almacen.crear("problema", "P")
        self.assertEqual(self.ids("--tipo", "problema"),
                         [self.almacen.entradas("problema")[0].id])

    def test_tipo_desconocido_lo_rechaza_argparse(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.buscar("--tipo", "marca")

    def test_temas_coinciden_todos_los_pedidos(self):
        auth_y_api = self.almacen.crear("decision", "Con los dos", autor="x",
                                        temas=["auth", "api"])
        solo_auth = self.almacen.crear("decision", "Solo uno", autor="x", temas=["auth"])
        self.assertEqual(self.ids("--temas", "auth,api"), [auth_y_api.id])
        self.assertEqual(sorted(self.ids("--temas", "auth")),
                         sorted([auth_y_api.id, solo_auth.id]))

    def test_estado_filtra_por_el_estado_actual(self):
        abierto = self.almacen.crear("problema", "Abierto")
        resuelto = self.almacen.crear("problema", "Resuelto")
        resuelto = self.almacen.poner_estado(resuelto.id, resuelto.version, "resuelto")
        self.assertEqual(self.ids("--estado", "abierto"), [abierto.id])
        self.assertEqual(self.ids("--estado", "resuelto"), [resuelto.id])

    def test_desde_filtra_por_fecha_o_por_actualizado_segun_el_tipo(self):
        vieja = self.almacen.crear("decision", "Vieja", autor="x", fecha="2026-01-01")
        nueva = self.almacen.crear("decision", "Nueva", autor="x", fecha="2026-10-01")
        arq_vieja = self.almacen.crear("arquitectura", "Flujo viejo", actualizado="2026-02-01")
        self.assertEqual(sorted(self.ids("--desde", "2026-09-01")), sorted([nueva.id]))
        self.assertNotIn(vieja.id, self.ids("--desde", "2026-09-01"))
        self.assertNotIn(arq_vieja.id, self.ids("--desde", "2026-09-01"))

    def test_entradas_sin_fecha_ni_actualizado_quedan_fuera_de_desde(self):
        self.almacen.crear("referencia", "Sin fecha")
        self.assertEqual(self.ids("--desde", "2020-01-01"), [])

    def test_desde_con_formato_invalido_es_un_error(self):
        self.almacen.crear("problema", "P")
        codigo, datos = self.buscar("--desde", "ayer")
        self.assertEqual(codigo, 3)
        self.assertIn("AAAA-MM-DD", datos["error"] + datos["salida"])

    def test_texto_sin_mayusculas_ni_acentos(self):
        self.almacen.crear("referencia", "Política de Café", "Nada que ver.")
        self.assertEqual(len(self.ids("--texto", "politica")), 1)
        self.assertEqual(len(self.ids("--texto", "CAFE")), 1)
        self.assertEqual(len(self.ids("--texto", "te")), 0)

    def test_texto_busca_tambien_en_el_cuerpo(self):
        entrada = self.almacen.crear("arquitectura", "Flujo", "El cobro pasa por Stripe.")
        self.assertEqual(self.ids("--texto", "stripe"), [entrada.id])

    def test_los_filtros_se_combinan(self):
        self.almacen.crear("decision", "D1", autor="x", temas=["auth"])
        buena = self.almacen.crear("decision", "D2", autor="x", temas=["auth", "api"])
        self.assertEqual(self.ids("--tipo", "decision", "--temas", "api", "--texto", "d2"),
                         [buena.id])


class Limite(PruebaDeBuscar):

    def test_por_defecto_no_corta_si_hay_pocas(self):
        for i in range(5):
            self.almacen.crear("referencia", f"R{i}")
        _, datos = self.buscar()
        self.assertEqual(len(datos["entradas"]), 5)
        self.assertNotIn("salida", datos)

    def test_el_limite_corta_y_dice_cuantas_quedaron_fuera(self):
        for i in range(5):
            self.almacen.crear("referencia", f"R{i}")
        _, datos = self.buscar("--limite", "2")
        self.assertEqual(len(datos["entradas"]), 2)
        self.assertEqual(datos["total"], 5)
        self.assertIn("3", datos["salida"])

    def test_limite_cero_no_devuelve_ninguna(self):
        self.almacen.crear("referencia", "R")
        _, datos = self.buscar("--limite", "0")
        self.assertEqual(datos["entradas"], [])
        self.assertEqual(datos["total"], 1)


class Medida(PruebaDeBuscar):
    """La compacidad que pide B2: ~30 tokens por entrada (≈4 caracteres por token) con un
    almacén de 20 entradas y contenido del largo normal de una nota, no de relleno."""

    def test_veinte_entradas_salen_a_unos_30_tokens_cada_una(self):
        datos = [
            ("decision", "Auth con JWT", "Usamos JWT para las sesiones.", ["backend"]),
            ("decision", "Cache con Redis", "Redis para cachear sesiones.", ["infra"]),
            ("decision", "Postgres 16", "Migramos a Postgres 16.", ["infra"]),
            ("decision", "Rate limiting", "Limite por API key.", ["backend"]),
            ("decision", "Versionado de API", "Semver en la API publica.", ["backend"]),
            ("decision", "Colas con RabbitMQ", "RabbitMQ para los webhooks.", ["infra"]),
            ("problema", "Login falla con carga", "Se cae con mucho trafico.", ["backend"]),
            ("problema", "Timeout en pagos", "El webhook de pagos tarda.", ["backend"]),
            ("problema", "Memory leak worker", "El worker de imagenes crece.", ["infra"]),
            ("problema", "Eventos duplicados", "La cola repite eventos.", ["backend"]),
            ("arquitectura", "Flujo de autenticacion", "Como fluye el login hoy.", ["infra"]),
            ("arquitectura", "Pipeline de deploy", "Como se despliega hoy.", ["infra"]),
            ("arquitectura", "Arquitectura de eventos", "Como viajan los eventos.", ["infra"]),
            ("aprendizaje", "Medir, no estimar", "Usar datos, no suponer.", ["backend"]),
            ("aprendizaje", "Reintentos idempotentes", "Repetir sin duplicar.", ["backend"]),
            ("aprendizaje", "Cache y fechas", "El cache falla con fechas.", ["backend"]),
            ("referencia", "Manual de marca", "Colores y tipografias.", []),
            ("referencia", "Guia de estilo API", "Convenciones de la API.", []),
            ("referencia", "Paleta de colores", "Los HEX de la marca.", []),
            ("recurso", "Logo principal", "Ficha del logo.", []),
        ]
        for tipo, titulo, texto, temas in datos:
            campos = {"archivo": "logo.svg"} if tipo == "recurso" else {}
            self.almacen.crear(tipo, titulo, texto, temas=temas, **campos)

        codigo, respuesta = self.correr("buscar", "--repo", str(self.repo), "--limite", "50")
        self.assertEqual(codigo, 0)
        n = len(respuesta["entradas"])
        self.assertEqual(n, 20)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(["buscar", "--repo", str(self.repo), "--limite", "50"])
        chars_totales = len(buf.getvalue().strip())
        tokens_por_entrada = (chars_totales / n) / 4
        # ~30 tokens/entrada es la medida que pide B2; se deja margen porque depende del
        # contenido real de cada nota, no de un tamaño fijo.
        self.assertLess(tokens_por_entrada, 40,
                        f"salió a {tokens_por_entrada:.1f} tokens/entrada")


class Leer(PruebaDeBuscar):
    """`leer` (v1.2, B3): la entrada completa, nunca por el camino de `buscar`."""

    def test_devuelve_la_entrada_completa_con_cuerpo_y_version(self):
        entrada = self.almacen.crear("referencia", "Manual de marca", "Colores y voz.",
                                     temas=["marca"])
        codigo, datos = self.leer(entrada.id)
        self.assertEqual(codigo, 0)
        self.assertEqual(datos, entrada.como_dict(con_cuerpo=True))
        self.assertIn("version", datos)
        self.assertEqual(datos["cuerpo"], entrada.cuerpo)

    def test_proyecto_se_lee_por_su_id(self):
        self.almacen.crear("proyecto", "Mi Proyecto", "De qué va.")
        codigo, datos = self.leer("proyecto")
        self.assertEqual((codigo, datos["id"], datos["tipo"]), (0, "proyecto", "proyecto"))

    def test_id_inexistente_sugiere_los_parecidos_y_buscar(self):
        self.almacen.crear("problema", "Se cae el login")
        parecido = self.almacen.entradas("problema")[0].id
        casi = parecido[:-1] + ("a" if parecido[-1] != "a" else "b")
        codigo, datos = self.leer(casi)
        self.assertEqual(codigo, 3)
        self.assertIn(parecido, datos["error"])
        self.assertEqual(datos["salida"], "`cotejo buscar --texto <algo>`")

    def test_id_inexistente_sin_ninguna_entrada_tambien_manda_a_buscar(self):
        (self.repo / ".cotejo" / "referencias").mkdir(parents=True)
        codigo, datos = self.leer("ref-zzzz")
        self.assertEqual(codigo, 3)
        self.assertIn("ref-zzzz", datos["error"])
        self.assertEqual(datos["salida"], "`cotejo buscar --texto <algo>`")

    def test_id_repetido_da_error_con_las_rutas_de_los_dos_archivos(self):
        primera = self.almacen.crear("problema", "Primera")
        carpeta = self.repo / ".cotejo" / "problemas"
        segunda = carpeta / "duplicada.md"
        segunda.write_text((carpeta / Path(primera.ruta).name).read_text("utf-8")
                           .replace(primera.titulo, "Segunda"), encoding="utf-8")
        codigo, datos = self.leer(primera.id)
        self.assertEqual(codigo, 3)
        self.assertIn(primera.ruta, datos["error"])
        self.assertIn("duplicada.md", datos["error"])

    def test_recurso_trae_la_ruta_y_si_existe_pero_nunca_su_contenido(self):
        # El verbo nunca abre la imagen: solo dice su ruta dentro de .cotejo/ y si está ahí.
        entrada = self.almacen.crear("recurso", "Logo", "Ficha del logo.", archivo="logo.svg")
        (self.repo / ".cotejo" / "recursos" / "logo.svg").write_bytes(b"\x89PNG\r\n")
        codigo, datos = self.leer(entrada.id)
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["recurso"], {"ruta": ".cotejo/recursos/logo.svg", "existe": True})
        self.assertNotIn("contenido", datos)

    def test_recurso_sin_el_archivo_en_disco_dice_que_no_existe(self):
        entrada = self.almacen.crear("recurso", "Logo", "Ficha.", archivo="falta.svg")
        codigo, datos = self.leer(entrada.id)
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["recurso"], {"ruta": ".cotejo/recursos/falta.svg",
                                            "existe": False})

    def test_una_entrada_que_no_es_recurso_no_trae_la_clave_recurso(self):
        entrada = self.almacen.crear("referencia", "R")
        _, datos = self.leer(entrada.id)
        self.assertNotIn("recurso", datos)

    def test_repo_sin_cotejo_dice_que_falta_init(self):
        # setUp deja el repo con `.git` pero sin `.cotejo/` todavía.
        codigo, datos = self.leer("ref-aaaa")
        self.assertEqual(codigo, 3)
        self.assertEqual(datos, {"esquema": 1, "error": "Este repo no tiene .cotejo/",
                                 "salida": "`cotejo init`", "reintentable": False})


class Proponer(PruebaDeBuscar):
    """`proponer decision` (v1.2, B... C1): nace en propuesta, con el agente como autor; nunca
    hay forma de aceptarla desde aquí, solo de reemplazarla."""

    def setUp(self):
        super().setUp()
        (self.repo / ".cotejo" / "decisiones").mkdir(parents=True)

    def test_crea_la_decision_en_propuesta_con_el_agente_como_autor(self):
        codigo, datos = self.proponer_decision("--titulo", "Usar JWT", "--texto",
                                               "Es lo más simple para el equipo.")
        self.assertEqual(codigo, 0)
        self.assertEqual(set(datos), {"esquema", "id", "ruta", "version"})
        entrada = self.almacen.leer(datos["id"])
        self.assertEqual((entrada.tipo, entrada.estado, entrada.datos["autor"]),
                         ("decision", "propuesta", "agente"))
        self.assertEqual(entrada.cuerpo.strip().splitlines()[-1],
                         "Es lo más simple para el equipo.")

    def test_titulo_y_texto_son_obligatorios(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.proponer_decision("--texto", "Sin título")
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.proponer_decision("--titulo", "Sin texto")

    def test_temas_quedan_coma_separados(self):
        _, datos = self.proponer_decision("--titulo", "D", "--texto", "T", "--temas",
                                          "auth, api")
        entrada = self.almacen.leer(datos["id"])
        self.assertEqual(entrada.temas, ["auth", "api"])

    def test_autor_por_defecto_es_agente_pero_se_puede_pasar_otro(self):
        _, datos = self.proponer_decision("--titulo", "D", "--texto", "T", "--autor", "opus")
        entrada = self.almacen.leer(datos["id"])
        self.assertEqual(entrada.datos["autor"], "opus")

    def test_reemplaza_marca_la_vieja_como_reemplazada_y_devuelve_las_dos(self):
        vieja = self.almacen.crear("decision", "Vieja", "Razón vieja.", autor="agente")
        codigo, datos = self.proponer_decision("--titulo", "Nueva", "--texto", "Razón nueva.",
                                               "--reemplaza", vieja.id)
        self.assertEqual(codigo, 0)
        nueva = self.almacen.leer(datos["id"])
        self.assertEqual(nueva.datos.get("reemplaza"), vieja.id)
        self.assertEqual(datos["reemplazada"]["id"], vieja.id)
        vieja_otra_vez = self.almacen.leer(vieja.id)
        self.assertEqual((vieja_otra_vez.estado, vieja_otra_vez.datos.get("reemplazada_por")),
                         ("reemplazada", nueva.id))
        self.assertEqual(datos["reemplazada"]["version"], vieja_otra_vez.version)

    def test_reemplazar_una_decision_inexistente_no_crea_nada(self):
        antes = sorted((self.repo / ".cotejo").rglob("*"))
        codigo, datos = self.proponer_decision("--titulo", "Nueva", "--texto", "T",
                                               "--reemplaza", "dec-zzzz")
        self.assertEqual(codigo, 3)
        self.assertIn("dec-zzzz", datos["error"])
        despues = sorted((self.repo / ".cotejo").rglob("*"))
        self.assertEqual(antes, despues)

    def test_reemplazar_una_decision_ya_reemplazada_no_crea_nada(self):
        primera = self.almacen.crear("decision", "Primera", "R1", autor="agente")
        segunda = self.almacen.crear("decision", "Segunda", "R2", autor="agente",
                                     reemplaza=primera.id)
        self.almacen.poner_estado(primera.id, primera.version, "reemplazada",
                                  campos={"reemplazada_por": segunda.id})
        antes = sorted((self.repo / ".cotejo").rglob("*"))
        codigo, datos = self.proponer_decision("--titulo", "Tercera", "--texto", "T",
                                               "--reemplaza", primera.id)
        self.assertEqual(codigo, 3)
        self.assertIn("ya está reemplazada", datos["error"])
        self.assertIn(segunda.id, datos["error"])
        despues = sorted((self.repo / ".cotejo").rglob("*"))
        self.assertEqual(antes, despues)

    def test_reemplazar_algo_que_no_es_decision_no_crea_nada(self):
        problema = self.almacen.crear("problema", "Un bug")
        antes = sorted((self.repo / ".cotejo").rglob("*"))
        codigo, datos = self.proponer_decision("--titulo", "Nueva", "--texto", "T",
                                               "--reemplaza", problema.id)
        self.assertEqual(codigo, 3)
        self.assertIn(problema.id, datos["error"])
        despues = sorted((self.repo / ".cotejo").rglob("*"))
        self.assertEqual(antes, despues)

    def test_reemplazar_una_decision_aceptada_tambien_vale(self):
        vieja = self.almacen.crear("decision", "Vieja", "R", autor="agente")
        vieja = self.almacen.poner_estado(vieja.id, vieja.version, "aceptada")
        codigo, datos = self.proponer_decision("--titulo", "Nueva", "--texto", "T",
                                               "--reemplaza", vieja.id)
        self.assertEqual(codigo, 0)
        self.assertEqual(self.almacen.leer(vieja.id).estado, "reemplazada")

    def test_las_decisiones_no_se_editan_ni_siquiera_la_recien_creada(self):
        _, datos = self.proponer_decision("--titulo", "D", "--texto", "T")
        with self.assertRaises(almacen.NoSeEdita):
            self.almacen.reescribir(datos["id"], datos["version"], texto="Otro texto")

    def test_no_hay_ninguna_accion_para_aceptar(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.correr("proponer", "aceptar", "--repo", str(self.repo), "dec-aaaa")
        self.assertNotIn("aceptar", cli.analizador()._subparsers._group_actions[0].choices)


class Anotar(PruebaDeBuscar):
    """`anotar <problema|aprendizaje|referencia|arquitectura>` (v1.2, C2): deja constancia,
    no cierra ni acepta nada."""

    def setUp(self):
        super().setUp()
        for tipo in ("problemas", "aprendizajes", "referencias", "arquitectura"):
            (self.repo / ".cotejo" / tipo).mkdir(parents=True)

    def test_anota_un_problema_que_nace_abierto(self):
        codigo, datos = self.anotar("problema", "--titulo", "Se cae el login", "--texto",
                                    "Con mucho tráfico.")
        self.assertEqual(codigo, 0)
        self.assertEqual(set(datos), {"esquema", "id", "ruta", "version"})
        entrada = self.almacen.leer(datos["id"])
        self.assertEqual((entrada.tipo, entrada.estado), ("problema", "abierto"))

    def test_anota_un_aprendizaje(self):
        _, datos = self.anotar("aprendizaje", "--titulo", "Medir, no estimar", "--texto",
                               "Usar datos.")
        entrada = self.almacen.leer(datos["id"])
        self.assertEqual(entrada.tipo, "aprendizaje")

    def test_anota_una_referencia_con_temas(self):
        _, datos = self.anotar("referencia", "--titulo", "Manual de marca", "--texto",
                               "Colores y voz.", "--temas", "marca, diseño")
        entrada = self.almacen.leer(datos["id"])
        self.assertEqual((entrada.tipo, entrada.temas), ("referencia", ["marca", "diseño"]))

    def test_anota_una_arquitectura(self):
        _, datos = self.anotar("arquitectura", "--titulo", "Flujo de login", "--texto",
                               "Cómo fluye hoy.")
        entrada = self.almacen.leer(datos["id"])
        self.assertEqual(entrada.tipo, "arquitectura")

    def test_titulo_y_texto_son_obligatorios(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.anotar("problema", "--texto", "Sin título")
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.anotar("problema", "--titulo", "Sin texto")

    def test_no_anota_decisiones_ni_proyecto_ni_bitacora(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.correr("anotar", "decision", "--repo", str(self.repo),
                           "--titulo", "D", "--texto", "T")
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.correr("anotar", "bitacora", "--repo", str(self.repo),
                           "--titulo", "D", "--texto", "T")

    def test_repo_sin_cotejo_dice_que_falta_init(self):
        fuera = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(fuera, ignore_errors=True))
        (fuera / ".git").mkdir()
        codigo, datos = self.correr("anotar", "problema", "--repo", str(fuera),
                                    "--titulo", "P", "--texto", "T")
        self.assertEqual(codigo, 3)
        self.assertEqual(datos["error"], "Este repo no tiene .cotejo/")


class Bitacora(PruebaDeBuscar):
    """`bitacora TEXTO` (v1.2, C2): un archivo por día, solo se añade al final."""

    def setUp(self):
        super().setUp()
        self.almacen.base.mkdir(parents=True)

    def test_anade_el_texto_a_la_bitacora_de_hoy(self):
        codigo, datos = self.bitacora("Probé el núcleo sin GTK.")
        self.assertEqual(codigo, 0)
        self.assertEqual(set(datos), {"esquema", "id", "ruta", "version"})
        self.assertEqual(datos["id"], "2026-10-04")
        entrada = self.almacen.leer("2026-10-04")
        self.assertIn("Probé el núcleo sin GTK.", entrada.cuerpo)

    def test_dos_anotaciones_el_mismo_dia_quedan_las_dos_una_tras_otra(self):
        self.bitacora("Primera.")
        _, datos = self.bitacora("Segunda.")
        entrada = self.almacen.leer("2026-10-04")
        self.assertIn("Primera.", entrada.cuerpo)
        self.assertIn("Segunda.", entrada.cuerpo)
        self.assertLess(entrada.cuerpo.index("Primera."), entrada.cuerpo.index("Segunda."))
        self.assertEqual(datos["version"], entrada.version)

    def test_texto_vacio_es_un_error(self):
        codigo, datos = self.bitacora("   ")
        self.assertEqual(codigo, 3)
        self.assertIn("vacías", datos["error"])

    def test_bitacora_no_tiene_subacciones_es_solo_texto_libre(self):
        subparser = cli.analizador()._subparsers._group_actions[0].choices["bitacora"]
        self.assertIsNone(subparser._subparsers)

    def test_repo_sin_cotejo_dice_que_falta_init(self):
        fuera = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(fuera, ignore_errors=True))
        (fuera / ".git").mkdir()
        codigo, datos = self.correr("bitacora", "x", "--repo", str(fuera))
        self.assertEqual(codigo, 3)
        self.assertEqual(datos["error"], "Este repo no tiene .cotejo/")


class Contexto(PruebaDeBuscar):
    """`contexto` (v1.2, B1): objetivo, tareas por estado, decisiones vigentes, problemas
    abiertos y temas, en menos de 1k tokens (medido con `medir.py` de la skill `ax`)."""

    def setUp(self):
        super().setUp()
        self.almacen.base.mkdir(parents=True, exist_ok=True)

    def test_sin_proyecto_ni_entradas_sale_vacio_y_en_cero(self):
        codigo, datos = self.contexto()
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["proyecto"], {"titulo": "", "objetivo": "", "stack": "",
                                             "siguiente_paso": ""})
        self.assertEqual(datos["tareas"], {"pendiente": 0, "en-curso": 0, "por-validar": 0,
                                           "hecha": 0})
        self.assertEqual(datos["decisiones_vigentes"], [])
        self.assertEqual(datos["problemas_abiertos"], [])
        self.assertEqual(datos["temas"], {})
        self.assertNotIn("avisos", datos)

    def test_lee_objetivo_stack_y_siguiente_paso_del_proyecto(self):
        # Las mismas cabeceras con emoji que escribe `importar obsidian --aplicar` (D2).
        self.almacen.crear("proyecto", "Mi Repo",
                           "## 🎯 Objetivo\nQue funcione.\n\n"
                           "## 🧱 Stack y arquitectura\nPython.\n\n"
                           "## ⏭️ Siguiente paso\nEscribir pruebas.\n")
        _, datos = self.contexto()
        self.assertEqual(datos["proyecto"], {
            "titulo": "Mi Repo", "objetivo": "Que funcione.", "stack": "Python.",
            "siguiente_paso": "Escribir pruebas."})

    def test_un_campo_de_proyecto_largo_se_recorta(self):
        self.almacen.crear("proyecto", "P", "## Objetivo\n" + ("palabra " * 200))
        _, datos = self.contexto()
        self.assertLessEqual(len(datos["proyecto"]["objetivo"]), conocimiento.LARGO_CAMPO)

    def test_tareas_por_estado_lee_el_tareas_md_del_repo(self):
        (self.repo / ".cotejo" / "tareas.md").write_text(
            "# Tareas\n\n"
            "- [ ] Pendiente ^cotejo-aaaa\n"
            "- [ ] En curso #en-curso ^cotejo-bbbb\n"
            "- [x] Hecha ^cotejo-cccc\n", encoding="utf-8")
        _, datos = self.contexto()
        self.assertEqual(datos["tareas"], {"pendiente": 1, "en-curso": 1, "por-validar": 0,
                                           "hecha": 1})

    def test_decisiones_vigentes_excluyen_las_reemplazadas(self):
        vieja = self.almacen.crear("decision", "Vieja", autor="x")
        nueva = self.almacen.crear("decision", "Nueva", autor="x", reemplaza=vieja.id)
        self.almacen.poner_estado(vieja.id, vieja.version, "reemplazada",
                                  campos={"reemplazada_por": nueva.id})
        _, datos = self.contexto()
        self.assertEqual([d["id"] for d in datos["decisiones_vigentes"]], [nueva.id])

    def test_problemas_abiertos_excluyen_los_resueltos(self):
        abierto = self.almacen.crear("problema", "Abierto")
        resuelto = self.almacen.crear("problema", "Resuelto")
        self.almacen.poner_estado(resuelto.id, resuelto.version, "resuelto")
        _, datos = self.contexto()
        self.assertEqual([p["id"] for p in datos["problemas_abiertos"]], [abierto.id])

    def test_decisiones_y_problemas_solo_traen_id_y_titulo(self):
        self.almacen.crear("decision", "D", "Razonamiento largo que no debe salir aquí.",
                           autor="x")
        self.almacen.crear("problema", "P", "Detalle que tampoco debe salir aquí.")
        _, datos = self.contexto()
        self.assertEqual(set(datos["decisiones_vigentes"][0]), {"id", "titulo"})
        self.assertEqual(set(datos["problemas_abiertos"][0]), {"id", "titulo"})

    def test_decisiones_vigentes_se_acotan_y_cuentan_el_total(self):
        # v1.2 · B1b: un almacén importado puede tener decenas de decisiones, todas
        # `aceptada` (vigentes): listarlas todas es lo que hacía pasar `contexto` de 1k
        # tokens. Con `--tope` se queda con las más recientes y dice cuántas hay de verdad.
        for i in range(15):
            self.almacen.crear("decision", f"Decisión {i}", autor="x",
                               fecha=f"2026-01-{i + 1:02d}")
        _, datos = self.contexto("--tope", "4")
        self.assertEqual(len(datos["decisiones_vigentes"]), 4)
        self.assertEqual(datos["decisiones_vigentes_total"], 15)
        # Las 4 mostradas son las de fecha más reciente (15 a 12 de enero), no las primeras
        # en crearse.
        self.assertEqual([d["titulo"] for d in datos["decisiones_vigentes"]],
                         ["Decisión 14", "Decisión 13", "Decisión 12", "Decisión 11"])
        self.assertIn("hay 15 decisiones vigentes (mostrando 4)", datos["salida"])
        self.assertIn("cotejo buscar --tipo decision", datos["salida"])

    def test_decisiones_importadas_cuentan_aparte_y_no_ocupan_el_tope(self):
        for i in range(5):
            self.almacen.crear("decision", f"Importada {i}", autor="importado",
                               fecha=f"2026-03-{i + 1:02d}")
        propia = self.almacen.crear("decision", "Propia", autor="agente", fecha="2026-01-01")
        _, datos = self.contexto("--tope", "2")
        self.assertEqual([d["id"] for d in datos["decisiones_vigentes"]], [propia.id])
        self.assertEqual(datos["decisiones_vigentes_total"], 1)
        self.assertEqual(datos["decisiones_importadas"], 5)
        self.assertIn("5 decisiones importadas", datos["salida"])

    def test_sin_importadas_el_conteo_es_cero_y_no_hay_pista(self):
        self.almacen.crear("decision", "D", autor="x")
        _, datos = self.contexto()
        self.assertEqual(datos["decisiones_importadas"], 0)
        self.assertNotIn("salida", datos)

    def test_problemas_abiertos_se_acotan_igual_que_las_decisiones(self):
        for i in range(6):
            self.almacen.crear("problema", f"Problema {i}", fecha=f"2026-02-{i + 1:02d}")
        _, datos = self.contexto("--tope", "2")
        self.assertEqual(len(datos["problemas_abiertos"]), 2)
        self.assertEqual(datos["problemas_abiertos_total"], 6)
        self.assertIn("hay 6 problemas abiertos (mostrando 2)", datos["salida"])

    def test_tope_por_defecto_alcanza_para_no_cortar_pocas_entradas(self):
        # Con menos entradas que el tope por defecto, no hay corte ni pista.
        self.almacen.crear("decision", "D", autor="x")
        _, datos = self.contexto()
        self.assertEqual(len(datos["decisiones_vigentes"]), 1)
        self.assertEqual(datos["decisiones_vigentes_total"], 1)
        self.assertNotIn("salida", datos)

    def test_titulo_largo_se_recorta_y_se_marca_cortado(self):
        largo = "Palabra " * 30  # bastante más que LARGO_TITULO_CONTEXTO
        self.almacen.crear("decision", largo, autor="x")
        _, datos = self.contexto()
        linea = datos["decisiones_vigentes"][0]
        self.assertLessEqual(len(linea["titulo"]), conocimiento.LARGO_TITULO_CONTEXTO)
        self.assertTrue(linea["titulo"].endswith("…"))
        self.assertIs(linea["cortado"], True)

    def test_titulo_corto_no_trae_la_clave_cortado(self):
        self.almacen.crear("decision", "Corto", autor="x")
        _, datos = self.contexto()
        self.assertNotIn("cortado", datos["decisiones_vigentes"][0])

    def test_temas_cuenta_entradas_por_tema_entre_tipos(self):
        self.almacen.crear("decision", "D", autor="x", temas=["auth", "api"])
        self.almacen.crear("problema", "P", temas=["auth"])
        self.almacen.crear("referencia", "R", temas=["api"])
        _, datos = self.contexto()
        self.assertEqual(datos["temas"], {"auth": 2, "api": 2})

    def test_avisos_de_frontmatter_roto_salen_en_contexto(self):
        self.almacen.crear("problema", "Bueno")
        roto = self.repo / ".cotejo" / "problemas" / "roto.md"
        roto.parent.mkdir(parents=True, exist_ok=True)
        roto.write_text("---\nid: pro-zzzz\nesto no\n---\n", encoding="utf-8")
        codigo, datos = self.contexto()
        self.assertEqual(codigo, 0)
        self.assertEqual(len(datos["avisos"]), 1)
        self.assertIn(".cotejo/problemas/roto.md", datos["avisos"][0]["nota"])

    def test_repo_sin_cotejo_dice_que_falta_init(self):
        fuera = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(fuera, ignore_errors=True))
        (fuera / ".git").mkdir()
        codigo, datos = self.correr("contexto", "--repo", str(fuera))
        self.assertEqual(codigo, 3)
        self.assertEqual(datos["error"], "Este repo no tiene .cotejo/")

    def test_cuesta_menos_de_mil_tokens_con_un_almacen_realista(self):
        # v1.2 · B1b: un almacén *importado*, con historial —como el caso real que hizo
        # saltar el bug— puede tener 70+ decisiones y el importador las deja todas
        # `aceptada` (vigentes). El criterio de éxito del planning es `contexto` < 1k tokens
        # sobre un almacén así, no uno vacío ni uno con un puñado de entradas.
        self.almacen.crear("proyecto", "Repo de prueba",
                           "## Objetivo\nQue un agente se entere barato de este repo.\n\n"
                           "## Stack\nPython, argparse, Markdown con frontmatter.\n\n"
                           "## Siguiente paso\nSeguir afinando `contexto`.\n")
        (self.repo / ".cotejo" / "tareas.md").write_text(
            "# Tareas\n\n" + "\n".join(f"- [ ] Tarea {i} ^cotejo-{i:04d}" for i in range(6))
            + "\n" + "\n".join(f"- [x] Hecha {i} ^cotejo-h{i:03d}" for i in range(4)) + "\n",
            encoding="utf-8")
        for i in range(70):
            self.almacen.crear(
                "decision",
                f"Decisión importada número {i} sobre cómo quedó repartido el trabajo entre "
                "los distintos módulos del sistema",
                "Un razonamiento con algo de contexto y alternativas.",
                autor="importado" if i < 30 else "agente", temas=["infra", "backend"],
                fecha=f"2026-01-{(i % 28) + 1:02d}")
        for i in range(8):
            self.almacen.crear("problema", f"Problema {i}", "Detalle técnico del problema.",
                               temas=["backend"])
        for i in range(3):
            self.almacen.crear("referencia", f"Referencia {i}", "Información de contexto.",
                               temas=["marca", "legal"])
        _, salida = self.correr("contexto", "--repo", str(self.repo))
        # 30 importadas cuentan aparte (v1.2.3); las otras 40 son las vigentes que se acotan.
        self.assertEqual(salida["decisiones_vigentes_total"], 40)
        self.assertEqual(salida["decisiones_importadas"], 30)
        self.assertLessEqual(len(salida["decisiones_vigentes"]), conocimiento.TOPE_VIGENTES)
        caracteres = len(json.dumps(salida, ensure_ascii=False))
        self.assertLess(round(caracteres / 4), 1000, f"contexto pesó ~{caracteres // 4} tokens")


class Editar(PruebaDeBuscar):
    """`editar <id> --version --texto` (v1.2, C3): arquitectura, referencias y proyecto.md,
    verificado por versión; las decisiones se niegan diciendo cómo reemplazarlas."""

    def setUp(self):
        super().setUp()
        for tipo in ("arquitectura", "referencias", "decisiones", "problemas"):
            (self.repo / ".cotejo" / tipo).mkdir(parents=True)

    def test_cambia_el_texto_y_devuelve_la_version_nueva(self):
        entrada = self.almacen.crear("arquitectura", "Flujo de pago", "Como es hoy.")
        codigo, datos = self.editar(entrada.id, "--version", entrada.version, "--texto",
                                    "Como es ahora.")
        self.assertEqual(codigo, 0)
        self.assertEqual(set(datos), {"esquema", "id", "ruta", "version"})
        self.assertEqual(datos["id"], entrada.id)
        self.assertNotEqual(datos["version"], entrada.version)
        actual = self.almacen.leer(entrada.id)
        self.assertIn("Como es ahora.", actual.cuerpo)
        self.assertEqual(actual.version, datos["version"])

    def _ida_y_vuelta(self, entrada_id, cambio):
        _, leida = self.leer(entrada_id)
        nuevo = leida["cuerpo"].replace("ORIGINAL", cambio)
        codigo, datos = self.editar(entrada_id, "--version", leida["version"], "--texto", nuevo)
        self.assertEqual(codigo, 0)
        _, vuelta = self.leer(entrada_id)
        self.assertEqual(vuelta["cuerpo"].count("# " + leida["titulo"]), 1)
        self.assertTrue(vuelta["cuerpo"].lstrip().startswith("# " + leida["titulo"]))
        self.assertIn(cambio, vuelta["cuerpo"])
        # una segunda vuelta con el cuerpo leído no cambia nada más
        _, otra = self.leer(entrada_id)
        self.assertEqual(otra["cuerpo"], vuelta["cuerpo"])
        return vuelta

    def test_leer_cambiar_editar_no_duplica_el_titulo_en_proyecto(self):
        self.almacen.crear("proyecto", "Mi Proyecto", "ORIGINAL.")
        self._ida_y_vuelta("proyecto", "Cambiado.")

    def test_leer_cambiar_editar_no_duplica_el_titulo_en_arquitectura_y_referencia(self):
        for tipo in ("arquitectura", "referencia"):
            entrada = self.almacen.crear(tipo, f"Titulo de {tipo}", "ORIGINAL.")
            self._ida_y_vuelta(entrada.id, "Cambiado.")

    def test_editar_con_texto_sin_titulo_sigue_poniendo_el_titulo(self):
        entrada = self.almacen.crear("arquitectura", "Flujo", "ORIGINAL.")
        self.editar(entrada.id, "--version", entrada.version, "--texto", "Solo texto.")
        _, vuelta = self.leer(entrada.id)
        self.assertEqual(vuelta["cuerpo"], "# Flujo\n\nSolo texto.\n")

    def test_edita_proyecto_md_por_su_id(self):
        self.almacen.crear("proyecto", "Mi Proyecto", "De qué va.")
        proyecto = self.almacen.leer("proyecto")
        codigo, datos = self.editar("proyecto", "--version", proyecto.version, "--texto",
                                    "Lo nuevo.")
        self.assertEqual(codigo, 0)
        self.assertIn("Lo nuevo.", self.almacen.leer("proyecto").cuerpo)

    def test_version_vieja_se_niega_sin_escribir_y_dice_como_reintentar(self):
        entrada = self.almacen.crear("referencia", "Manual", "Original.")
        self.almacen.reescribir(entrada.id, entrada.version, texto="Ya cambió por otro lado.")
        codigo, datos = self.editar(entrada.id, "--version", entrada.version, "--texto",
                                    "Lo que yo quería escribir.")
        self.assertEqual(codigo, 4)
        self.assertTrue(datos["reintentable"])
        self.assertIn(entrada.id, datos["error"])
        self.assertIn("cambió desde que la leíste", datos["error"])
        self.assertEqual(datos["salida"], f"`cotejo leer {entrada.id}` y reintenta. "
                                          "No se escribió nada.")
        self.assertIn("Ya cambió por otro lado.", self.almacen.leer(entrada.id).cuerpo)
        self.assertNotIn("Lo que yo quería escribir.", self.almacen.leer(entrada.id).cuerpo)

    def test_editar_una_decision_se_niega_y_manda_a_reemplazarla(self):
        decision = self.almacen.crear("decision", "Usar JWT", "Razón.", autor="agente")
        codigo, datos = self.editar(decision.id, "--version", decision.version, "--texto",
                                    "Otra razón.")
        self.assertEqual(codigo, 3)
        self.assertEqual(datos["error"], "Las decisiones no se editan")
        self.assertEqual(datos["salida"],
                         f"`cotejo proponer decision --reemplaza {decision.id}`")
        self.assertFalse(datos["reintentable"])
        self.assertEqual(self.almacen.leer(decision.id).cuerpo, decision.cuerpo)

    def test_editar_un_problema_no_es_una_decision_pero_tampoco_se_edita(self):
        problema = self.almacen.crear("problema", "Se cae el login")
        codigo, datos = self.editar(problema.id, "--version", problema.version, "--texto", "X")
        self.assertEqual(codigo, 3)
        self.assertNotIn("decisiones", datos["error"])
        self.assertFalse(datos["reintentable"])

    def test_id_inexistente_sugiere_los_parecidos_y_buscar(self):
        entrada = self.almacen.crear("referencia", "Manual de marca")
        casi = entrada.id[:-1] + ("a" if entrada.id[-1] != "a" else "b")
        codigo, datos = self.editar(casi, "--version", "000000000000", "--texto", "X")
        self.assertEqual(codigo, 3)
        self.assertIn(entrada.id, datos["error"])
        self.assertEqual(datos["salida"], "`cotejo buscar --texto <algo>`")

    def test_repo_sin_cotejo_dice_que_falta_init(self):
        fuera = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(fuera, ignore_errors=True))
        (fuera / ".git").mkdir()
        codigo, datos = self.correr("editar", "arq-aaaa", "--repo", str(fuera),
                                    "--version", "000000000000", "--texto", "X")
        self.assertEqual(codigo, 3)
        self.assertEqual(datos["error"], "Este repo no tiene .cotejo/")

    def test_version_y_texto_son_obligatorios(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.editar("arq-aaaa", "--texto", "X")
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.editar("arq-aaaa", "--version", "000000000000")


class Resolver(PruebaDeBuscar):
    """`resolver <pro-id> --solucion` (v1.2, C3): abierto → resuelto, con la solución."""

    def setUp(self):
        super().setUp()
        for tipo in ("problemas", "aprendizajes"):
            (self.repo / ".cotejo" / tipo).mkdir(parents=True)

    def test_resuelve_un_problema_abierto(self):
        problema = self.almacen.crear("problema", "Se cae el login", "Con mucho tráfico.")
        codigo, datos = self.resolver(problema.id, "--solucion", "Se subió el límite de pool.")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["cambio"], True)
        self.assertEqual(set(datos), {"esquema", "cambio", "id", "ruta", "version"})
        actual = self.almacen.leer(problema.id)
        self.assertEqual(actual.estado, "resuelto")
        self.assertEqual(actual.datos["solucion"], "Se subió el límite de pool.")
        self.assertEqual(actual.version, datos["version"])

    def test_resolver_uno_ya_resuelto_no_vuelve_a_escribir(self):
        problema = self.almacen.crear("problema", "Bug")
        self.almacen.poner_estado(problema.id, problema.version, "resuelto",
                                  campos={"solucion": "Primera solución."})
        resuelto = self.almacen.leer(problema.id)
        codigo, datos = self.resolver(problema.id, "--solucion", "Otra solución distinta.")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["cambio"], False)
        self.assertEqual(datos["version"], resuelto.version)
        self.assertEqual(self.almacen.leer(problema.id).datos["solucion"], "Primera solución.")

    def test_resolver_algo_que_no_es_problema_se_niega(self):
        aprendizaje = self.almacen.crear("aprendizaje", "Medir, no estimar")
        codigo, datos = self.resolver(aprendizaje.id, "--solucion", "X")
        self.assertEqual(codigo, 3)
        self.assertIn(aprendizaje.id, datos["error"])
        self.assertIn("no es un problema", datos["error"])

    def test_id_inexistente_sugiere_los_parecidos_y_buscar(self):
        problema = self.almacen.crear("problema", "Se cae el login")
        casi = problema.id[:-1] + ("a" if problema.id[-1] != "a" else "b")
        codigo, datos = self.resolver(casi, "--solucion", "X")
        self.assertEqual(codigo, 3)
        self.assertIn(problema.id, datos["error"])
        self.assertEqual(datos["salida"], "`cotejo buscar --texto <algo>`")

    def test_solucion_vacia_es_un_error(self):
        problema = self.almacen.crear("problema", "Bug")
        codigo, datos = self.resolver(problema.id, "--solucion", "   ")
        self.assertEqual(codigo, 3)
        self.assertIn("solución", datos["error"])
        self.assertEqual(self.almacen.leer(problema.id).estado, "abierto")

    def test_solucion_es_obligatoria(self):
        problema = self.almacen.crear("problema", "Bug")
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.resolver(problema.id)

    def test_repo_sin_cotejo_dice_que_falta_init(self):
        fuera = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(fuera, ignore_errors=True))
        (fuera / ".git").mkdir()
        codigo, datos = self.correr("resolver", "pro-aaaa", "--repo", str(fuera),
                                    "--solucion", "X")
        self.assertEqual(codigo, 3)
        self.assertEqual(datos["error"], "Este repo no tiene .cotejo/")


if __name__ == "__main__":
    unittest.main()


class FrescuraDeContexto(unittest.TestCase):
    """v1.2.3: `contexto` avisa en `salida` si `proyecto.md` lleva más de `contexto.dias_viejo`
    días sin commit (y es anterior al último tag). Repo de git de verdad, fechas fijadas."""

    def setUp(self):
        import os
        import subprocess
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repo = Path(temporal.name) / "mi-repo"
        self.repo.mkdir()
        self.env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        self._sub = subprocess
        self.git("init", "-q")
        self.alm = almacen.Almacen(self.repo)
        self.alm.base.mkdir(parents=True, exist_ok=True)
        with mock.patch.object(almacen, "_hoy", return_value="2026-01-01"):
            self.alm.crear("proyecto", "Mi Repo", "## Objetivo\nQue funcione.\n\n"
                           "## Siguiente paso\nPruebas.\n")

    def git(self, *args, fecha=None):
        env = dict(self.env)
        if fecha:
            env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"{fecha}T12:00:00+0000"
        self._sub.run(["git", "-C", str(self.repo), *args], check=True, env=env,
                      capture_output=True)

    def commit(self, fecha):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "x", "--allow-empty", fecha=fecha)

    def frescura(self, hoy="2026-02-01", limite=14):
        import datetime
        campos = {"objetivo": "Que funcione.", "stack": "", "siguiente_paso": "Pruebas."}
        return conocimiento.frescura_proyecto(
            self.repo, campos, hoy=datetime.date.fromisoformat(hoy), limite=limite)

    def test_viejo_sin_tags_pasa_el_umbral(self):
        self.commit("2026-01-01")
        r = self.frescura(hoy="2026-01-20")
        self.assertEqual((r["actualizado"], r["dias"]), ("2026-01-01", 19))
        self.assertEqual(r["viejos"], ["objetivo", "siguiente_paso"])
        self.assertIn("cotejo editar proyecto", r["pistas"][0])

    def test_dentro_del_umbral_no_avisa(self):
        self.commit("2026-01-01")
        self.assertEqual(self.frescura(hoy="2026-01-15")["pistas"], [])
        self.assertTrue(self.frescura(hoy="2026-01-15", limite=3)["pistas"])

    def test_editado_despues_del_ultimo_tag_no_se_acusa(self):
        self.commit("2026-01-01")
        self.git("tag", "v1", fecha="2026-01-01")
        # el tag es de la misma fecha que el archivo: no es anterior al tag
        self.assertEqual(self.frescura(hoy="2026-02-01")["pistas"], [])
        self.git("commit", "-q", "--allow-empty", "-m", "y", fecha="2026-01-10")
        self.git("tag", "v2", fecha="2026-01-10")
        r = self.frescura(hoy="2026-02-01")
        self.assertEqual(r["tag"], "v2")
        self.assertIn("anterior al tag v2", r["pistas"][0])

    def test_contexto_lo_trae_en_actualizado_y_en_salida(self):
        self.commit("2026-01-01")
        self.git("commit", "-q", "--allow-empty", "-m", "y", fecha="2026-01-10")
        self.git("tag", "v2", fecha="2026-01-10")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), \
                mock.patch.object(conocimiento, "dias_viejo", return_value=14), \
                mock.patch.object(conocimiento, "_hoy",
                                  return_value=__import__("datetime").date(2026, 3, 1)):
            cli.main(["contexto", "--repo", str(self.repo)])
        datos = json.loads(buf.getvalue())
        self.assertEqual(datos["proyecto"]["actualizado"], "2026-01-01")
        self.assertIn("cotejo editar proyecto", datos["salida"])

    def test_dias_viejo_de_la_config_y_su_validacion(self):
        from tareas import configuracion
        self.assertEqual(conocimiento.dias_viejo({}), 14)
        self.assertEqual(conocimiento.dias_viejo({"contexto": {"dias_viejo": 3}}), 3)
        self.assertEqual(conocimiento.dias_viejo({"contexto": {"dias_viejo": "x"}}), 14)
        errores, avisos = [], []
        configuracion._validar_contexto({"contexto": {"dias_viejo": -1, "otra": 1}},
                                        errores, avisos)
        self.assertEqual((len(errores), len(avisos)), (1, 1))
        errores, avisos = [], []
        configuracion._validar_contexto({"contexto": {"dias_viejo": 7}}, errores, avisos)
        self.assertEqual((errores, avisos), ([], []))

    def test_sin_git_usa_la_fecha_de_la_entrada(self):
        import datetime
        fuera = self.repo.parent / "sin-git"
        fuera.mkdir()
        entrada = mock.Mock(datos={"actualizado": "2026-01-01"})
        r = conocimiento.frescura_proyecto(
            fuera, {"objetivo": "x"}, entrada, hoy=datetime.date(2026, 2, 1), limite=14)
        self.assertEqual(r["actualizado"], "2026-01-01")
        self.assertTrue(r["pistas"])
