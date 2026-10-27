"""Los modelos de todos los agentes (v1.3.0, cotejo-qixs4j).

Ninguna prueba depende de los CLIs instalados: los agentes son scripts falsos en un PATH
temporal (que solo tiene esos y `sh`), `HOME` apunta a una carpeta de prueba con o sin sus
credenciales, y la caché de modelos vive en un `XDG_STATE_HOME` temporal. El board se prueba
con un Board falso (solo lo que `lista_de_agentes` y el diálogo leen), sin abrir ventana.
"""

import json
import os
import shutil
import stat
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

import apoyo  # noqa: F401  (pone la raíz del repo en sys.path)

from enrutador import clientes, config as cfg, decision, modelos_vivos, niveles
from tareas import almacen, origen, revisar_plan

from test_revisar_plan import ConProyecto

OPENCODE = """#!/bin/sh
[ "$1" = "models" ] || exit 3
echo "opencode/gratis-free"
echo "opencode-go/kimi-k2.7-code"
echo "openrouter/deepseek/deepseek-v4.1-flash-1017"
"""
CODEX = """#!/bin/sh
[ "$1 $2" = "debug models" ] || exit 3
echo '{"models": [{"slug": "oculto", "visibility": "hide", "priority": 1},'
echo '  {"slug": "gpt-luna", "visibility": "list", "priority": 9},'
echo '  {"slug": "gpt-terra", "visibility": "list", "priority": 8}]}'
"""
LENTO = "#!/bin/sh\nsleep 5\n"
ROTO = "#!/bin/sh\nexit 1\n"
NADA = "#!/bin/sh\nexit 0\n"


class ConMaquinaFalsa(unittest.TestCase):
    """Un HOME, un PATH y un estado de mentira para esta prueba."""

    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.raiz = Path(temporal.name)
        self.casa = self.raiz / "casa"
        self.bin = self.raiz / "bin"
        self.casa.mkdir()
        self.bin.mkdir()
        sh = shutil.which("sh")
        os.symlink(sh, self.bin / "sh")
        entorno = {"HOME": str(self.casa), "PATH": str(self.bin),
                   "XDG_STATE_HOME": str(self.raiz / "estado"),
                   "XDG_DATA_HOME": "", "CODEX_HOME": ""}
        for clave in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY",
                      "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
            entorno[clave] = ""
        p = mock.patch.dict(os.environ, entorno)
        p.start()
        self.addCleanup(p.stop)

    def cli(self, nombre, guion=NADA):
        ruta = self.bin / nombre
        ruta.write_text(guion, encoding="utf-8")
        ruta.chmod(ruta.stat().st_mode | stat.S_IEXEC)
        return ruta

    def archivo(self, relativa, texto="{}"):
        ruta = self.casa / relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(texto, encoding="utf-8")
        return ruta

    def con_sesion(self, *nombres):
        credenciales = {"claude": (".claude/.credentials.json", "{}"),
                        "codex": (".codex/auth.json", "{}"),
                        "opencode": (".local/share/opencode/auth.json",
                                     '{"openrouter": {"type": "api"}}'),
                        "gemini": (".gemini/oauth_creds.json", "{}")}
        for nombre in nombres:
            self.archivo(*credenciales[nombre])


class Sesion(ConMaquinaFalsa):
    def test_instalado_sin_credenciales_no_esta_listo(self):
        for nombre in clientes.CLIENTES:
            self.cli(nombre)
        self.assertEqual(clientes.instalados(), ["claude", "opencode", "codex", "gemini"])
        self.assertEqual(modelos_vivos.listos(), [])

    def test_con_credenciales_si(self):
        for nombre in ("claude", "codex", "gemini"):
            self.cli(nombre)
        self.con_sesion("claude", "codex", "opencode", "gemini")   # opencode no instalado
        self.assertEqual(modelos_vivos.listos(), ["claude", "codex", "gemini"])

    def test_opencode_necesita_alguna_credencial(self):
        self.cli("opencode")
        self.archivo(".local/share/opencode/auth.json", "{}")
        self.assertFalse(modelos_vivos.sesion("opencode"))
        self.con_sesion("opencode")
        self.assertTrue(modelos_vivos.sesion("opencode"))

    def test_claude_en_macos_y_por_variable(self):
        self.archivo(".claude.json", '{"oauthAccount": {"x": 1}}')
        self.assertTrue(modelos_vivos.sesion("claude"))
        self.assertTrue(modelos_vivos.sesion("gemini", {"GEMINI_API_KEY": "x"}))
        self.assertFalse(modelos_vivos.sesion("desconocido"))

    def test_doctor_dice_quien_tiene_sesion(self):
        self.cli("codex")
        self.con_sesion("codex")
        self.assertEqual(modelos_vivos.listos(), ["codex"])


class Listar(ConMaquinaFalsa):
    def test_opencode_y_codex_se_preguntan_al_cli(self):
        self.cli("opencode", OPENCODE)
        self.cli("codex", CODEX)
        self.assertEqual(modelos_vivos.listar("opencode"),
                         ["opencode/gratis-free", "opencode-go/kimi-k2.7-code",
                          "openrouter/deepseek/deepseek-v4.1-flash-1017"])
        # Solo los visibles, por prioridad.
        self.assertEqual(modelos_vivos.listar("codex"), ["gpt-terra", "gpt-luna"])

    def test_claude_y_gemini_son_sus_alias_sin_lanzar_nada(self):
        self.cli("claude", "#!/bin/sh\ntouch \"$HOME/lanzado\"\n")
        self.cli("gemini", "#!/bin/sh\ntouch \"$HOME/lanzado\"\n")
        self.assertEqual(modelos_vivos.listar("claude"), ["opus", "sonnet", "haiku"])
        self.assertEqual(modelos_vivos.listar("gemini"), ["pro", "flash", "flash-lite", "auto"])
        self.assertFalse((self.casa / "lanzado").exists())

    def test_lo_guardado_se_usa_y_caduca(self):
        guion = self.cli("codex", CODEX)
        self.assertEqual(modelos_vivos.listar("codex"), ["gpt-terra", "gpt-luna"])
        guion.write_text(ROTO, encoding="utf-8")
        # Reciente: ni se pregunta.
        self.assertEqual(modelos_vivos.listar("codex"), ["gpt-terra", "gpt-luna"])
        # Caducado y el CLI falla: lo último guardado.
        with mock.patch.object(modelos_vivos, "CADUCA", -1):
            self.assertEqual(modelos_vivos.listar("codex"), ["gpt-terra", "gpt-luna"])
        self.assertEqual(modelos_vivos.en_cache("codex"), ["gpt-terra", "gpt-luna"])

    def test_cli_que_tarda_o_falla_da_el_respaldo(self):
        self.cli("opencode", LENTO)
        inicio = time.monotonic()
        self.assertEqual(modelos_vivos.listar("opencode", tope=1), [])
        self.assertLess(time.monotonic() - inicio, 4)
        self.cli("codex", ROTO)
        self.assertEqual(modelos_vivos.listar("codex"), [])
        self.assertEqual(modelos_vivos.listar("opencode", tope=1), [])  # sin instalar tampoco

    def test_leer_codex_aguanta_basura(self):
        self.assertEqual(modelos_vivos.leer_codex("no es json"), [])
        self.assertEqual(modelos_vivos.leer_codex('{"models": 3}'), [])
        self.assertEqual(modelos_vivos.leer_opencode("Error: algo\nproveedor/m\n\n"),
                         ["proveedor/m"])

    def test_resumen_para_la_cli(self):
        self.cli("codex", CODEX)
        self.con_sesion("codex")
        filas = {f["cliente"]: f for f in modelos_vivos.resumen()}
        self.assertEqual(filas["codex"]["modelos"], ["gpt-terra", "gpt-luna"])
        self.assertFalse(filas["claude"]["instalado"])
        self.assertEqual(filas["claude"]["modelos"], [])
        sin = {f["cliente"]: f for f in modelos_vivos.resumen(preguntar_cli=False)}
        self.assertEqual(sin["codex"]["modelos"], ["gpt-terra", "gpt-luna"])  # lo guardado


class Catalogo(unittest.TestCase):
    def test_los_de_claude_son_la_familia_5_5(self):
        ids = {n.modelo: n.modelo_id for n in niveles.NIVELES if n.modelo}
        self.assertEqual(ids, {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5",
                               "opus": "claude-opus-5-5"})

    def test_claude_se_lanza_con_el_alias(self):
        self.assertEqual(clientes.de("claude").modelo_de("opus", "claude-opus-5-5"), "opus")

    def test_codex_de_fabrica_se_lanza_sin_modelo(self):
        codex = niveles.por_nombre("codex")
        self.assertEqual((codex.cliente, codex.modelo_id), ("codex", ""))
        cliente = clientes.de("codex")
        argv = cliente.argv_sin_interfaz(cliente.modelo_de(codex.modelo, codex.modelo_id), "hola")
        self.assertEqual(argv, ["codex", "exec", "hola"])
        gemini = niveles.por_nombre("gemini-pro")
        self.assertEqual(clientes.de("gemini").modelo_de(gemini.modelo, gemini.modelo_id), "pro")

    def test_un_registrado_con_la_misma_clave_gana_al_de_fabrica(self):
        propio = [{"clave": "codex", "modelo_id": "gpt-terra", "cliente": "codex", "nivel": "n2"}]
        self.assertEqual(niveles.por_nombre("codex", propio).modelo_id, "gpt-terra")
        self.assertEqual(sum(n.clave == "codex" for n in niveles.disponibles(propio)), 1)

    def test_grupos_con_el_agente_del_proyecto_primero(self):
        propios = [{"clave": "kimi", "modelo_id": "opencode-go/kimi", "cliente": "opencode",
                    "nivel": "n2"},
                   {"clave": "raro", "modelo_id": "x", "cliente": "otro", "nivel": "n2"}]
        grupos = niveles.grupos(propios, ["claude", "codex", "opencode"], primero="codex")
        self.assertEqual(grupos, [("codex", ["codex"]),
                                  ("claude", ["opus", "sonnet", "haiku"]),
                                  ("opencode", ["opencode", "kimi"]),
                                  ("otro", ["raro"])])
        # Sin agente del proyecto, Claude primero; Gemini sin sesión no sale.
        self.assertEqual([c for c, _ in niveles.grupos((), ["gemini", "claude"])],
                         ["claude", "gemini"])
        self.assertEqual(dict(niveles.grupos((), ["gemini"]))["gemini"],
                         ["gemini-pro", "gemini-flash", "gemini-flash-lite"])

    def test_sin_ningun_agente_listo_salen_todos(self):
        self.assertEqual([c for c, _ in niveles.grupos((), [])],
                         ["claude", "opencode", "codex", "gemini"])

    def test_del_cliente_nunca_abarata(self):
        n1, n2, n3 = (niveles.POR_CLAVE[c] for c in ("n1", "n2", "n3"))
        self.assertIs(niveles.del_cliente(n2, "claude"), n2)
        self.assertEqual(niveles.del_cliente(n1, "gemini").modelo, "gemini-flash-lite")
        self.assertEqual(niveles.del_cliente(n3, "gemini").modelo, "gemini-pro")
        self.assertEqual(niveles.del_cliente(n1, "codex").modelo, "codex")
        propios = [{"clave": "barato", "modelo_id": "p/b", "cliente": "opencode", "nivel": "n1"}]
        self.assertEqual(niveles.del_cliente(n1, "opencode", propios).modelo, "barato")
        # n2 sin registrado de n2: escala al de fábrica (n3), nunca baja al n1.
        self.assertEqual(niveles.del_cliente(n2, "opencode", propios).modelo, "opencode")
        self.assertIs(niveles.del_cliente(niveles.HUMANO_NIVEL, "codex"), niveles.HUMANO_NIVEL)


class Decision(unittest.TestCase):
    def test_la_propuesta_es_del_agente_del_proyecto(self):
        elegida = decision.decidir("cambiar el color del botón", reglas_humano=(),
                                   reglas_nivel=(), cliente="codex")
        self.assertEqual((elegida.por, elegida.nivel.modelo), ("defecto", "codex"))
        self.assertIn("Codex", elegida.razon)
        gemini = decision.decidir("algo", dificultad="dificil", reglas_humano=(),
                                  reglas_nivel=(), cliente="gemini")
        self.assertEqual(gemini.nivel.modelo, "gemini-pro")

    def test_lo_que_dijo_una_persona_no_se_toca(self):
        for kwargs in ({"agente": "opus"}, {"override": "haiku"}):
            elegida = decision.decidir("algo", reglas_humano=(), reglas_nivel=(),
                                       cliente="codex", **kwargs)
            self.assertIn(elegida.nivel.modelo, ("opus", "haiku"))

    def test_sin_cliente_como_siempre(self):
        elegida = decision.decidir("algo", reglas_humano=(), reglas_nivel=())
        self.assertEqual(elegida.nivel.modelo, "sonnet")


class AgenteDelProyecto(ConProyecto):
    def test_sin_marca_es_claude(self):
        self.assertEqual(origen.agente_de(self.carpeta), "")
        self.assertEqual(origen.agente_de(None), "")
        self.assertEqual(origen.agente_de(self.raiz / "no-existe"), "")

    def test_init_deja_el_agente_elegido(self):
        self.assertFalse(origen.marcar_agente(self.carpeta, {}))
        self.assertFalse(origen.marcar_agente(self.carpeta, {"COTEJO_AGENTE": "co dex;"}))
        self.assertTrue(origen.marcar_agente(self.carpeta, {"COTEJO_AGENTE": "Codex"}))
        self.assertEqual(origen.agente_de(self.carpeta), "codex")
        # Nunca pisa otro.
        self.assertFalse(origen.marcar_agente(self.carpeta, {"COTEJO_AGENTE": "gemini"}))
        self.assertEqual(origen.agente_de(self.carpeta), "codex")

    def test_un_proyecto_de_codex_queda_listo_para_codex(self):
        origen.marcar_agente(self.carpeta, {"COTEJO_AGENTE": "codex"})
        reglas = {"reglas_humano": None, "reglas_nivel": None, "niveles_extra": (),
                  "alias_persona": None}
        with mock.patch("enrutador.preparar.descartar"):
            asignadas = revisar_plan.empezar(self.estado, reglas)
        self.assertEqual(asignadas, [{"id": "cotejo-aaa111", "agente": "codex"},
                                     {"id": "cotejo-ccc333", "agente": "codex"}])
        self.assertIn("#agente/codex ^cotejo-aaa111", self.tareas_md())
        self.assertIn("#agente/persona ^cotejo-bbb222", self.tareas_md())


class AnadirModelo(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.config = Path(temporal.name) / "config.json"

    def test_clave_a_partir_del_id(self):
        self.assertEqual(modelos_vivos.nueva_clave("opencode-go/kimi-k2.7-code"), "kimi-k2.7-code")
        self.assertEqual(modelos_vivos.nueva_clave("x/Opus"), "opus-2")       # reservada
        self.assertEqual(modelos_vivos.nueva_clave("codex"), "codex-2")       # de fábrica
        self.assertEqual(modelos_vivos.nueva_clave("a/b c", ["b-c"]), "b-c-2")

    def test_definicion_valida(self):
        with self.assertRaises(ValueError):
            modelos_vivos.definicion("", "x")
        with self.assertRaises(ValueError):
            modelos_vivos.definicion("codex", "con espacio")
        with self.assertRaises(ValueError):
            modelos_vivos.definicion("codex", "gpt", nivel="n0")

    def test_agregar_es_lo_mismo_que_la_cli_y_no_duplica(self):
        guardado, reemplazado = modelos_vivos.agregar("codex", "gpt-terra", "Terra", "n3",
                                                      ruta=self.config)
        self.assertFalse(reemplazado)
        self.assertEqual({k: guardado[k] for k in ("clave", "nombre", "cliente", "nivel")},
                         {"clave": "gpt-terra", "nombre": "Terra", "cliente": "codex",
                          "nivel": "n3"})
        otra, reemplazado = modelos_vivos.agregar("codex", "gpt-terra", "", "n2",
                                                  ruta=self.config)
        self.assertTrue(reemplazado)
        modelos = cfg.cargar(self.config)["modelos"]
        self.assertEqual(len(modelos), 1)
        self.assertEqual(modelos[0]["nivel"], "n2")
        self.assertEqual(niveles.por_nombre("gpt-terra", modelos).cliente, "codex")


try:
    from gi.repository import Gtk
    from tareas import app, modelo
    HAY_GTK = Gtk.init_check()
except (ImportError, ValueError):
    HAY_GTK = False


def textos(widget):
    if isinstance(widget, Gtk.Label):
        yield widget.get_label()
    hijo = widget.get_first_child()
    while hijo is not None:
        yield from textos(hijo)
        hijo = hijo.get_next_sibling()


@unittest.skipUnless(HAY_GTK, "sin GTK o sin pantalla no se puede construir el menú")
class EnElBoard(ConMaquinaFalsa):
    def board(self, agente_del_proyecto=""):
        asignadas, avisos = [], []
        falso = types.SimpleNamespace(
            agentes=("opus", "sonnet", "haiku", "persona"), alias_persona=("persona",),
            definiciones=[], listos=["claude", "codex", "gemini"],
            agentes_de_proyecto={"Uno": agente_del_proyecto},
            fuente=types.SimpleNamespace(poner_agente=lambda t, a: asignadas.append(a) or t),
            app=types.SimpleNamespace(refrescar=lambda: None),
            aviso=avisos.append, al_asignar=lambda *a: None)
        for nombre in ("opcion", "lista_de_agentes", "grupos_de", "agente_del_proyecto",
                       "al_anadir_y_asignar", "abrir_anadir_modelo", "cliente_del_dialogo",
                       "poner_modelos", "cargar_modelos_del_dialogo", "modelo_del_dialogo",
                       "al_responder_anadir", "leer_modelos", "modelos_para_preguntar"):
            setattr(falso, nombre, types.MethodType(getattr(app.Board, nombre), falso))
        falso.listar_en_fondo = lambda cliente, al_terminar: al_terminar(
            modelos_vivos.listar(cliente))
        falso.asignadas, falso.avisos = asignadas, avisos
        return falso

    def tarea(self):
        return modelo.Tarea("Una tarea", id="cotejo-aaa111", donde="Uno.md", estado="pendiente")

    def test_asignar_a_agrupa_por_agente_con_el_del_proyecto_primero(self):
        falso = self.board("codex")
        lista = falso.lista_de_agentes(types.SimpleNamespace(nombre="Uno"), self.tarea(),
                                       Gtk.Popover())
        vistos = [t for t in textos(lista) if t]
        self.assertEqual(vistos[:3], ["Codex", "codex", "Añadir modelo…"])
        self.assertLess(vistos.index("Claude Code"), vistos.index("Gemini CLI"))
        self.assertIn("gemini-flash-lite", vistos)
        self.assertNotIn("OpenCode", vistos)            # sin sesión
        # La persona al final («Sin agente» no: ya lo está).
        self.assertEqual(vistos[-1], "persona")

    def test_preguntar_ofrece_todos_con_la_propuesta_primero(self):
        falso = self.board("codex")
        modelos = falso.modelos_para_preguntar("codex", types.SimpleNamespace(nombre="Uno"))
        self.assertEqual(modelos[:2], ["codex", "opus"])
        self.assertIn("gemini-pro", modelos)

    def test_anadir_modelo_con_la_lista_en_vivo_y_asignarlo(self):
        self.cli("codex", CODEX)
        config = self.raiz / "config.json"
        falso = self.board()
        with mock.patch.object(cfg, "ruta_config", return_value=config), \
                mock.patch("gi.repository.Adw.Dialog.present"):
            dialogo = falso.al_anadir_y_asignar(None, self.tarea(), "codex", None)
            nombres = [dialogo.lista.get_string(i) for i in range(dialogo.lista.get_n_items())]
            self.assertEqual(nombres, ["gpt-terra", "gpt-luna", "Otro (escríbelo abajo)"])
            dialogo.modelo.set_selected(1)
            dialogo.nivel.set_selected(0)
            with mock.patch("tareas.bitacora.anotar"):
                guardado = falso.al_responder_anadir(dialogo, "agregar",
                                                     falso.asignadas.append)
        self.assertEqual((guardado["clave"], guardado["modelo_id"], guardado["nivel"]),
                         ("gpt-luna", "gpt-luna", "n1"))
        self.assertEqual(falso.asignadas, ["gpt-luna"])
        self.assertEqual(cfg.cargar(config)["modelos"][0]["cliente"], "codex")

    def test_escrito_gana_y_vacio_no_registra(self):
        config = self.raiz / "config.json"
        falso = self.board()
        with mock.patch.object(cfg, "ruta_config", return_value=config), \
                mock.patch("gi.repository.Adw.Dialog.present"):
            dialogo = falso.abrir_anadir_modelo("gemini")
            self.assertEqual(dialogo.lista.get_string(0), "pro")
            dialogo.modelo.set_selected(dialogo.lista.get_n_items() - 1)   # «Otro»
            self.assertIsNone(falso.al_responder_anadir(dialogo, "agregar"))
            self.assertTrue(falso.avisos and "No añadí" in falso.avisos[-1])
            dialogo.escrito.set_text("gemini-3-pro-preview")
            guardado = falso.al_responder_anadir(dialogo, "agregar")
        self.assertEqual((guardado["cliente"], guardado["modelo_id"]),
                         ("gemini", "gemini-3-pro-preview"))


if __name__ == "__main__":
    unittest.main()
