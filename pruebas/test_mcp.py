"""`cotejo mcp`: el protocolo, el catálogo sacado de la CLI y que una tool hace lo mismo que su verbo.

Todo contra un vault, una config y una bitácora de mentira (`PruebaDeCLI`), y el servidor de
punta a punta en un subproceso con HOME, XDG y COTEJO_* temporales.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apoyo import RAIZ, PruebaDeCLI, proyecto

from tareas import almacen, cli, mcp


def peticion(id_, metodo, **params):
    return {"jsonrpc": "2.0", "id": id_, "method": metodo, "params": params}


class Catalogo(PruebaDeCLI):

    def test_cada_tool_sale_de_un_verbo_de_la_cli(self):
        nombres = {t["name"] for t in mcp.tools()}
        self.assertIn("tareas", nombres)
        self.assertIn("fuentes_info", nombres)
        self.assertIn("importar_plan", nombres)
        # `importar` sin acción no se puede llamar en la CLI, así que tampoco es tool.
        self.assertNotIn("importar", nombres)
        # El servidor no se sirve a sí mismo.
        self.assertNotIn("mcp", nombres)

    def test_los_argumentos_se_traducen_a_json_schema(self):
        por_nombre = {t["name"]: t["inputSchema"] for t in mcp.tools()}
        entregar = por_nombre["entregar"]
        self.assertEqual(set(entregar["required"]), {"id", "evidencia"})
        self.assertEqual(entregar["properties"]["prueba"]["type"], "array")
        tareas = por_nombre["tareas"]["properties"]
        self.assertEqual(tareas["todas"], {"type": "boolean", "description": tareas["todas"]["description"]})
        self.assertEqual(tareas["limite"]["type"], "integer")
        self.assertIn("pendiente", tareas["estado"]["enum"])
        self.assertNotIn("required", por_nombre["asignar"]["properties"])
        self.assertEqual(por_nombre["asignar"]["required"], ["id"])

    def test_una_bandera_nueva_aparece_sola(self):
        # Lo que pidió el reparto: el catálogo no se mantiene a mano.
        analizador = cli.analizador()
        sub = analizador._subparsers._group_actions[0].choices["tomar"]
        sub.add_argument("--nueva", type=int, help="Una que todavía no existe")
        esquema = next(t for t in mcp.tools(analizador) if t["name"] == "tomar")["inputSchema"]
        self.assertEqual(esquema["properties"]["nueva"]["type"], "integer")

    def test_argv_protege_los_valores_que_parecen_banderas(self):
        self.assertEqual(mcp.argv("crear", {"texto": "-x", "proyecto": "--y"}),
                         ["crear", "--proyecto=--y", "--", "-x"])
        self.assertEqual(mcp.argv("fuentes_info", {"nombre": "obsidian"}),
                         ["fuentes", "info", "--", "obsidian"])
        self.assertEqual(mcp.argv("tareas", {"todas": True, "limite": 3}),
                         ["tareas", "--limite=3", "--todas"])

    def test_argv_rechaza_lo_que_el_verbo_no_tiene(self):
        with self.assertRaises(mcp.ArgumentosMalos):
            mcp.argv("tareas", {"finalizar": True})
        with self.assertRaises(mcp.ArgumentosMalos):
            mcp.argv("tareas", {"todas": "si"})


class Protocolo(PruebaDeCLI):

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))

    def test_initialize_negocia_la_version(self):
        r = mcp.atender(peticion(1, "initialize", protocolVersion="2025-06-18", capabilities={},
                                 clientInfo={"name": "x", "version": "1"}))
        self.assertEqual(r["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", r["result"]["capabilities"])
        self.assertEqual(r["result"]["serverInfo"]["name"], "cotejo")
        r = mcp.atender(peticion(1, "initialize", protocolVersion="1999-01-01"))
        self.assertEqual(r["result"]["protocolVersion"], mcp.VERSIONES[0])

    def test_las_notificaciones_no_se_contestan(self):
        self.assertIsNone(mcp.atender({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_errores_de_json_rpc(self):
        self.assertEqual(mcp.atender(peticion(1, "recursos/raros"))["error"]["code"], mcp.NO_EXISTE)
        self.assertEqual(mcp.atender({"id": 1})["error"]["code"], mcp.PETICION_INVALIDA)
        r = mcp.atender(peticion(2, "tools/call", name="no_existe", arguments={}))
        self.assertEqual(r["error"]["code"], mcp.PARAMETROS)
        self.assertEqual(mcp.atender(peticion(3, "ping")), {"jsonrpc": "2.0", "id": 3, "result": {}})

    def test_una_tool_devuelve_lo_mismo_que_su_verbo(self):
        _, por_cli = self.correr("tareas", "--proyecto", "Uno")
        r = mcp.atender(peticion(1, "tools/call", name="tareas", arguments={"proyecto": "Uno"}))
        self.assertFalse(r["result"]["isError"])
        self.assertEqual(r["result"]["structuredContent"], por_cli)
        self.assertEqual(json.loads(r["result"]["content"][0]["text"]), por_cli)

    def test_escribe_por_los_mismos_verbos_y_deja_bitacora(self):
        r = mcp.atender(peticion(1, "tools/call", name="crear",
                                 arguments={"texto": "Por MCP", "proyecto": "Uno"}))
        identificador = r["result"]["structuredContent"]["tarea"]["id"]
        r = mcp.atender(peticion(2, "tools/call", name="tomar",
                                 arguments={"id": identificador, "agente": "opus"}))
        self.assertEqual(r["result"]["structuredContent"]["tarea"]["estado"], "en-curso")
        self.assertEqual([o["operacion"] for o in self.operaciones()], ["crear", "tomar"])

    def test_un_error_del_verbo_es_un_resultado_con_iserror(self):
        r = mcp.atender(peticion(1, "tools/call", name="entregar",
                                 arguments={"id": "no-existe", "evidencia": "x"}))
        self.assertTrue(r["result"]["isError"])
        self.assertIn("error", r["result"]["structuredContent"])

    def test_un_error_de_argumentos_no_tumba_el_servidor(self):
        r = mcp.atender(peticion(1, "tools/call", name="tomar", arguments={"id": "x"}))
        self.assertTrue(r["result"]["isError"])
        self.assertIn("--agente", r["result"]["content"][0]["text"])


class LoQueNoEsDelAgente(PruebaDeCLI):
    """Pedir por MCP aceptar una decisión o finalizar una tarea: no hay tool, y la respuesta lo
    dice igual que la CLI, en vez de un «no existe» que invite a buscar otro nombre."""

    def test_pedir_aceptar_contesta_que_es_de_la_persona(self):
        for nombre in ("aceptar", "aceptar_decision", "decision_aprobar", "firmar"):
            r = mcp.atender(peticion(1, "tools/call", name=nombre, arguments={"id": "dec-aaaa"}))
            self.assertTrue(r["result"]["isError"], nombre)
            datos = r["result"]["structuredContent"]
            self.assertEqual(datos["error"], "Aceptar es de la persona: se hace desde el board")
            self.assertFalse(datos["reintentable"])
            self.assertNotIn(nombre, mcp.catalogo())

    def test_pedir_finalizar_contesta_lo_mismo_que_la_cli(self):
        _, por_cli = self.correr("finalizar", "cotejo-aaaa")
        r = mcp.atender(peticion(1, "tools/call", name="finalizar", arguments={}))
        self.assertTrue(r["result"]["isError"])
        self.assertEqual(r["result"]["structuredContent"], por_cli)
        self.assertEqual(self.operaciones(), [])


class VerbosDelAlmacen(PruebaDeCLI):
    """Los verbos de la 1.2 sobre `.cotejo/`, expuestos uno a uno (C4): misma tool que verbo,
    mismos argumentos y la misma respuesta. No se diseñan aparte."""

    TOOLS = {"contexto", "buscar", "leer", "proponer_decision", "anotar_problema",
             "anotar_aprendizaje", "anotar_referencia", "anotar_arquitectura", "bitacora",
             "editar", "resolver"}

    def setUp(self):
        super().setUp()
        self.repo = Path(tempfile.mkdtemp(dir=self.vault)) / "repo"
        (self.repo / ".git").mkdir(parents=True)
        self.assertEqual(self.correr("init", "--repo", str(self.repo))[0], 0)

    def llamar(self, nombre, **argumentos):
        r = mcp.atender(peticion(1, "tools/call", name=nombre,
                                 arguments={"repo": str(self.repo), **argumentos}))
        return r["result"]

    def test_cada_verbo_nuevo_es_una_tool(self):
        por_nombre = {t["name"]: t for t in mcp.tools()}
        self.assertLessEqual(self.TOOLS, set(por_nombre))
        # Sin acción no hay tool: `proponer` y `anotar` piden siempre el tipo.
        self.assertNotIn("proponer", por_nombre)
        self.assertNotIn("anotar", por_nombre)
        self.assertEqual(set(por_nombre["editar"]["inputSchema"]["required"]),
                         {"id", "version", "texto"})
        self.assertEqual(set(por_nombre["resolver"]["inputSchema"]["required"]),
                         {"id", "solucion"})

    def test_las_descripciones_son_cortas(self):
        # Baratas en tokens: el catálogo entero viaja en cada sesión del cliente.
        for tool in mcp.tools():
            if tool["name"] in self.TOOLS:
                self.assertLess(len(tool["description"]), 200, tool["name"])

    def test_el_ciclo_entero_por_mcp(self):
        r = self.llamar("proponer_decision", titulo="Usar SQLite", texto="Porque sí.")
        self.assertFalse(r["isError"], r)
        decision = r["structuredContent"]["id"]
        r = self.llamar("anotar_problema", titulo="Se cae", texto="Con tráfico.")
        problema = r["structuredContent"]["id"]
        r = self.llamar("bitacora", texto="Probado por MCP.")
        self.assertFalse(r["isError"], r)

        leida = self.llamar("leer", id=decision)["structuredContent"]
        _, por_cli = self.correr("leer", decision, "--repo", str(self.repo))
        self.assertEqual(leida, por_cli)
        # Nace propuesta y por MCP no hay forma de que salga de ahí más que reemplazándola.
        self.assertEqual(almacen.Almacen(self.repo).leer(decision).estado, "propuesta")

        r = self.llamar("buscar", texto="sqlite")
        self.assertEqual([e["id"] for e in r["structuredContent"]["entradas"]], [decision])
        r = self.llamar("resolver", id=problema, solucion="Más pool.")
        self.assertTrue(r["structuredContent"]["cambio"])

        proyecto_md = self.llamar("leer", id="proyecto")["structuredContent"]
        r = self.llamar("editar", id="proyecto", version=proyecto_md["version"], texto="Nuevo.")
        self.assertFalse(r["isError"], r)
        r = self.llamar("editar", id=decision, version=leida["version"], texto="Otra.")
        self.assertTrue(r["isError"])
        self.assertEqual(r["structuredContent"]["error"], "Las decisiones no se editan")

        contexto = self.llamar("contexto")["structuredContent"]
        _, por_cli = self.correr("contexto", "--repo", str(self.repo))
        self.assertEqual(contexto, por_cli)
        self.assertEqual([d["id"] for d in contexto["decisiones_vigentes"]], [decision])
        self.assertEqual(contexto["problemas_abiertos"], [])


# Lo que pidió la persona (2026-10-06) para el núcleo. La lista vive aquí solo para comprobar el
# analizador: lo que manda es la marca `cli.nucleo()` en cada verbo, y `mcp.py` solo filtra.
NUCLEO = {"contexto", "tareas", "buscar", "leer", "crear", "tomar", "entregar", "bloquear",
          "anotar", "bitacora"}

# Lo que mide `tools/list` del núcleo, en tokens (caracteres / 3,6, la constante del medidor de
# ahorro). Antes de cotejo-32d7b6: 6.771 car. ≈ 1.881 tok el núcleo y 21.794 car. ≈ 6.054 tok el
# completo; el objetivo de 1.500 es ahora el tope.
CARACTERES_POR_TOKEN = 3.6
OBJETIVO_TOKENS = 1500


def verbos_marcados():
    raiz = mcp._subcomandos(cli.analizador())
    return {v for v, sub in raiz.choices.items() if getattr(sub, "nucleo", False)}


def tokens_de_tools_list(perfil):
    respuesta = mcp.atender(peticion(1, "tools/list"), perfil)
    texto = json.dumps(respuesta["result"], ensure_ascii=False)
    return len(texto) / CARACTERES_POR_TOKEN


class PerfilNucleo(PruebaDeCLI):

    def test_ningun_verbo_del_nucleo_falta_en_la_cli(self):
        raiz = mcp._subcomandos(cli.analizador())
        self.assertLessEqual(NUCLEO, set(raiz.choices))
        self.assertEqual(verbos_marcados(), NUCLEO)

    def test_tools_list_del_nucleo_son_exactamente_esos_y_el_completo_todos(self):
        nucleo = {t["name"] for t in mcp.atender(peticion(1, "tools/list"), mcp.NUCLEO)
                  ["result"]["tools"]}
        completo = {t["name"] for t in mcp.atender(peticion(1, "tools/list"), mcp.COMPLETO)
                    ["result"]["tools"]}
        # Cada verbo marcado con todas sus acciones (anotar → anotar_problema…), y nada más.
        esperadas = {n for n, (ruta, _, _) in mcp.catalogo().items() if ruta[0] in NUCLEO}
        self.assertEqual(nucleo, esperadas)
        self.assertEqual({n.split("_")[0] for n in nucleo}, NUCLEO)
        self.assertIn("anotar_problema", nucleo)
        self.assertEqual(completo, set(mcp.catalogo()))
        self.assertLess(nucleo, completo)
        self.assertNotIn("proponer_decision", nucleo)

    def test_el_perfil_por_defecto_es_nucleo(self):
        self.assertEqual(cli.analizador().parse_args(["mcp"]).perfil, mcp.NUCLEO)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            cli.analizador().parse_args(["mcp", "--perfil", "otro"])

    def test_una_tool_fuera_del_nucleo_dice_donde_esta(self):
        r = mcp.atender(peticion(1, "tools/call", name="editar", arguments={}), mcp.NUCLEO)
        self.assertEqual(r["error"]["code"], mcp.PARAMETROS)
        self.assertIn("--perfil completo", r["error"]["message"])
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))
        r = mcp.atender(peticion(2, "tools/call", name="tareas", arguments={}), mcp.NUCLEO)
        self.assertFalse(r["result"]["isError"])

    def test_tools_list_del_nucleo_cabe_en_el_objetivo(self):
        self.assertLessEqual(tokens_de_tools_list(mcp.NUCLEO), OBJETIVO_TOKENS)
        self.assertLess(tokens_de_tools_list(mcp.NUCLEO),
                        tokens_de_tools_list(mcp.COMPLETO) / 3)


class DePuntaAPunta(PruebaDeCLI):
    """El servidor de verdad, por stdio, en un proceso aparte y sin nada del usuario."""

    def test_conversacion_por_stdio(self):
        self.escribir_nota("Uno.md", proyecto("- [ ] Una tarea"))
        raiz = Path(tempfile.mkdtemp(dir=self.vault))
        entorno = {k: v for k, v in os.environ.items()
                   if not k.startswith(("COTEJO_", "XDG_", "PYTHON"))}
        entorno.update({"HOME": str(raiz), "XDG_STATE_HOME": str(raiz / "estado"),
                        "XDG_CONFIG_HOME": str(raiz / "config"),
                        "COTEJO_CONFIG": str(self.config), "COTEJO_VAULT": str(self.vault),
                        "COTEJO_CARPETA_PROYECTOS": self.CARPETA})
        mensajes = [
            peticion(1, "initialize", protocolVersion="2025-06-18", capabilities={},
                     clientInfo={"name": "prueba", "version": "0"}),
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            peticion(2, "tools/list"),
            peticion(3, "tools/call", name="tareas", arguments={}),
        ]
        entrada = "".join(json.dumps(m) + "\n" for m in mensajes) + "esto no es json\n"
        nombres = {}
        for bandera in ([], ["--perfil", "completo"], ["--perfil", "nucleo"]):
            hecho = subprocess.run([sys.executable, "-m", "tareas", "mcp", *bandera], cwd=RAIZ,
                                   env=entorno, input=entrada, capture_output=True, text=True,
                                   timeout=60)
            self.assertEqual(hecho.returncode, 0, hecho.stderr)
            # Cada línea de la salida es un mensaje de JSON-RPC, y nada más.
            respuestas = [json.loads(l) for l in hecho.stdout.splitlines()]
            self.assertEqual([r.get("id") for r in respuestas], [1, 2, 3, None])
            self.assertTrue(all(r["jsonrpc"] == "2.0" for r in respuestas))
            nombres[" ".join(bandera)] = {t["name"] for t in respuestas[1]["result"]["tools"]}
            self.assertIn("tareas", nombres[" ".join(bandera)])
            self.assertEqual(respuestas[2]["result"]["structuredContent"]["total"], 1)
            self.assertEqual(respuestas[3]["error"]["code"], mcp.PARSEO)
        # Sin bandera, el núcleo; con `completo`, el catálogo entero.
        self.assertEqual(nombres[""], nombres["--perfil nucleo"])
        self.assertEqual(nombres[""], set(mcp.catalogo(perfil=mcp.NUCLEO)))
        self.assertEqual(nombres["--perfil completo"], set(mcp.catalogo()))
