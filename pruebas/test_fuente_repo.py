"""La fuente de repos: `.cotejo/tareas.md` en cada repo, con la misma línea que Obsidian.

La primera clase corre **las mismas pruebas** que `test_fuente.py` le pasa a la fuente en
memoria, pero contra repos de verdad en una carpeta temporal: los verbos de un agente (listar,
filtrar, tomar, entregar, bloquear, el resumen de la barra) tienen que comportarse igual. Las
demás cubren lo que es solo de esta fuente: qué repos cuentan, cómo se llaman y que la
escritura verificada de Obsidian sigue protegiendo también aquí.
"""

import os
import tempfile
from pathlib import Path, PureWindowsPath
from unittest import mock

import test_fuente as base
from apoyo import PruebaDeCLI, nota
from tareas import estado, modelo
from tareas.fuentes.repo import Repo

LINEAS = (
    "# Tareas",
    "",
    "- [ ] Comprar café #facil ^m1",
    "- [ ] Llamar al banco #en-curso #agente/sonnet ^m2",
    "- [x] Regar las plantas ^m3",
)


def hacer_repo(donde, *lineas, git="carpeta"):
    """Un repo de mentira: basta con `.git` (carpeta, o archivo como en un worktree)."""
    donde.mkdir(parents=True, exist_ok=True)
    if git == "carpeta":
        (donde / ".git").mkdir(exist_ok=True)
    elif git == "archivo":
        (donde / ".git").write_text("gitdir: /otro/sitio\n", encoding="utf-8")
    if lineas:
        (donde / ".cotejo").mkdir(exist_ok=True)
        (donde / ".cotejo" / "tareas.md").write_text(nota(*lineas), encoding="utf-8")
    return donde


class PruebaConRepos(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.repos = Path(temporal.name)
        self.cosas = hacer_repo(self.repos / "Cosas", *LINEAS)
        self.entorno({"COTEJO_FUENTE": "repo", "COTEJO_REPOS": str(self.cosas)})

    def entorno(self, valores):
        parche = mock.patch.dict(os.environ, valores)
        parche.start()
        self.addCleanup(parche.stop)

    def archivo(self, repo=None):
        return ((repo or self.cosas) / ".cotejo" / "tareas.md").read_text(encoding="utf-8")


class LosMismosVerbosQueLaFuenteEnMemoria(PruebaConRepos, base.LosVerbosNoSabenDeObsidian):
    """Las pruebas de `test_fuente.py`, heredadas tal cual. Solo se cambian las dos que
    miran por dentro de la fuente en memoria (cuántas escrituras hizo, que no sabe crear)."""

    def test_no_se_toca_ningun_archivo_del_vault(self):
        self.correr("tomar", "m1", "--agente", "opus")
        self.correr("entregar", "m1", "--evidencia", "x")
        self.assertEqual(list((self.vault / self.CARPETA).iterdir()), [])
        # Lo que sí se tocó es el archivo del repo, y solo la línea de la tarea.
        self.assertEqual(self.archivo().splitlines()[2],
                         "- [ ] Comprar café #facil #agente/opus #por-validar ^m1")

    def test_una_fuente_que_no_sabe_crear_lo_dice_con_su_nombre(self):
        # Esta sí sabe: la tarea nueva cae con las demás y nace con su marca.
        codigo, datos = self.correr("crear", "Comprar pan", "--proyecto", "Cosas",
                                    "--dificultad", "facil")
        self.assertEqual(codigo, 0)
        marca = datos["tarea"]["id"]
        lineas = self.archivo().splitlines()
        self.assertEqual(lineas[5], f"- [ ] Comprar pan #facil ^{marca}")
        self.assertEqual(datos["tarea"]["nota"], "Cosas/.cotejo/tareas.md")


class QueReposCuentan(PruebaConRepos):
    def test_la_raiz_encuentra_los_repos_con_tareas(self):
        raiz = self.repos / "codigo"
        hacer_repo(raiz / "app", "- [ ] Una ^a1")
        hacer_repo(raiz / "web", "- [ ] Otra ^b1")
        hacer_repo(raiz / "sin-tareas")
        hacer_repo(raiz / "worktree", "- [ ] Una ^a1", git="archivo")
        hacer_repo(raiz / ".oculto", "- [ ] Nada ^c1")
        hacer_repo(raiz / "no-es-repo", "- [ ] Nada ^d1", git=None)
        self.entorno({"COTEJO_REPOS": ""})  # vacía: solo cuenta la raíz de la config
        nombres = [p.nombre for p in Repo({"raiz": str(raiz)}).escanear()]
        self.assertEqual(sorted(nombres), ["app", "web"])

    def test_la_lista_y_la_raiz_se_suman_sin_repetir(self):
        raiz = self.repos / "codigo"
        hacer_repo(raiz / "app", "- [ ] Una ^a1")
        self.entorno({"COTEJO_REPOS": os.pathsep.join([str(self.cosas), str(raiz / "app")]),
                      "COTEJO_RAIZ_REPOS": str(raiz)})
        self.assertEqual(sorted(p.nombre for p in Repo().escanear()), ["Cosas", "app"])

    def test_dos_repos_con_el_mismo_nombre_no_se_mezclan(self):
        uno = hacer_repo(self.repos / "a" / "web", "- [ ] De a ^a1")
        dos = hacer_repo(self.repos / "b" / "web", "- [ ] De b ^b1")
        self.entorno({"COTEJO_REPOS": os.pathsep.join([str(uno), str(dos)])})
        fuente = Repo()
        proyectos = {p.nombre: [t.texto for t in p.tareas] for p in fuente.escanear()}
        self.assertEqual(proyectos, {"web": ["De a"], "b/web": ["De b"]})

    def test_un_repo_de_la_lista_sin_archivo_se_avisa(self):
        vacio = hacer_repo(self.repos / "vacio")
        self.entorno({"COTEJO_REPOS": os.pathsep.join([str(self.cosas), str(vacio)])})
        avisos = []
        proyectos = Repo().escanear(avisos=avisos)
        self.assertEqual([p.nombre for p in proyectos], ["Cosas"])
        self.assertEqual(len(avisos), 1)
        self.assertIn(".cotejo/tareas.md", avisos[0]["motivo"])

    def test_un_repo_cerrado_en_su_frontmatter_no_sale(self):
        hacer_repo(self.repos / "viejo", "---", "estado: terminado", "---", "- [ ] X ^x1")
        self.entorno({"COTEJO_REPOS": str(self.repos / "viejo")})
        self.assertEqual(Repo().escanear(), [])


class CuandoNoEstaLista(PruebaConRepos):
    def test_sin_repos_lo_dice_en_vez_de_todo_al_dia(self):
        self.entorno({"COTEJO_REPOS": ""})
        codigo, datos = self.correr("tareas")
        self.assertNotEqual(codigo, 0)
        self.assertIn("ningún repo", datos["salida"])
        self.assertIn("ningún repo", estado.calcular()["error"])

    def test_un_repo_que_no_existe_es_un_problema(self):
        self.entorno({"COTEJO_REPOS": str(self.repos / "no-existe")})
        self.assertIn("no-existe", Repo().problema)


class EscribeComoObsidian(PruebaConRepos):
    def test_una_linea_editada_por_fuera_no_se_pisa(self):
        fuente = Repo()
        tarea = next(t for p in fuente.escanear() for t in p.tareas if t.id == "m1")
        ruta = self.cosas / ".cotejo" / "tareas.md"
        ruta.write_text(self.archivo().replace("Comprar café", "Comprar té"), encoding="utf-8")
        with self.assertRaises(modelo.TareaCambiada):
            fuente.poner_estado(tarea, "en-curso")
        self.assertIn("Comprar té #facil ^m1", self.archivo())

    def test_una_tarea_sin_marca_se_nombra_por_su_linea_y_la_gana_al_tomarla(self):
        hacer_repo(self.cosas, *LINEAS, "- [ ] Sin marca")
        _, datos = self.correr("tareas", "--estado", "pendiente")
        sin_marca = next(t for t in datos["tareas"] if t["texto"] == "Sin marca")
        self.assertEqual(sin_marca["id"], "Cosas/.cotejo/tareas.md:5")
        codigo, datos = self.correr("tomar", sin_marca["id"], "--agente", "opus")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["tarea"]["id"].startswith("cotejo-"))
        self.assertIn(f"- [ ] Sin marca #en-curso #agente/opus ^{datos['tarea']['id']}",
                      self.archivo())

    def test_los_saltos_de_linea_del_archivo_se_respetan(self):
        ruta = self.cosas / ".cotejo" / "tareas.md"
        ruta.write_bytes(b"- [ ] Uno ^u1\r\n- [ ] Dos ^d2\r\n")
        self.correr("tomar", "u1", "--agente", "opus")
        self.assertEqual(ruta.read_bytes(),
                         b"- [ ] Uno #en-curso #agente/opus ^u1\r\n- [ ] Dos ^d2\r\n")


class DondeVive(PruebaConRepos):
    def test_uri_abre_el_archivo_de_tareas(self):
        fuente = Repo()
        tarea = fuente.escanear()[0].tareas[0]
        self.assertEqual(fuente.uri(tarea),
                         (self.cosas.resolve() / ".cotejo" / "tareas.md").as_uri())

    def test_vigila_la_carpeta_cotejo_de_cada_repo(self):
        vigilables = Repo().vigilables()
        # Debe incluir la carpeta .cotejo y no más en este caso (sin subcarpetas)
        self.assertIn(str(self.cosas.resolve() / ".cotejo"), vigilables)
        # Como no hay subcarpetas del almacén, solo tenemos .cotejo
        self.assertEqual(len(vigilables), 1)

    def test_vigila_tambien_las_subcarpetas_del_almacen(self):
        # Crea subcarpetas del almacén en .cotejo
        cotejo = self.cosas / ".cotejo"
        cotejo.mkdir(exist_ok=True)
        (cotejo / "decisiones").mkdir(exist_ok=True)
        (cotejo / "problemas").mkdir(exist_ok=True)
        (cotejo / "referencias").mkdir(exist_ok=True)
        vigilables = Repo().vigilables()
        # Debe incluir .cotejo y sus subcarpetas
        self.assertIn(str(cotejo), vigilables)
        self.assertIn(str(cotejo / "decisiones"), vigilables)
        self.assertIn(str(cotejo / "problemas"), vigilables)
        self.assertIn(str(cotejo / "referencias"), vigilables)
        # Y no incluir las que no existen
        self.assertNotIn(str(cotejo / "arquitectura"), vigilables)
        self.assertNotIn(str(cotejo / "bitacora"), vigilables)

    def test_leido_cuenta_solo_el_archivo_de_los_proyectos_pedidos(self):
        otro = hacer_repo(self.repos / "Otro", "- [ ] X ^x1")
        self.entorno({"COTEJO_REPOS": os.pathsep.join([str(self.cosas), str(otro)])})
        fuente = Repo()
        proyectos = fuente.escanear()
        cosas = [p for p in proyectos if p.nombre == "Cosas"]
        self.assertEqual(fuente.leido(cosas), len(self.archivo()))
        self.assertEqual(fuente.leido(), len(self.archivo()) + len(self.archivo(otro)))

    def test_fuentes_info_dice_sus_parametros(self):
        codigo, datos = self.correr("fuentes", "info", "repo")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tipo"], "built-in")
        self.assertEqual(set(datos["parametros"]), {"repos", "raiz"})


class NormalizacionParaWindows(PruebaConRepos):
    """Pruebas con PureWindowsPath para verificar que los paths de Windows se normalizan."""

    def test_archivo_con_backslashes_se_encuentra(self):
        """En Windows, str(Path) usa backslashes, pero _archivo() debe encontrar la clave."""
        fuente = Repo()
        fuente.escanear()
        # La clave en _mapa es siempre con slashes: "Cosas/.cotejo/tareas.md"
        # Simulamos lo que pasaría en Windows: un Path con backslashes
        donde_windows = PureWindowsPath(r"Cosas\.cotejo\tareas.md")
        # _archivo() debe normalizar y encontrar la clave
        ruta_archivo = fuente._archivo(donde_windows)
        self.assertEqual(ruta_archivo, self.cosas / ".cotejo" / "tareas.md")

    def test_uri_con_backslashes_funciona(self):
        """El método uri() debe funcionar aunque tarea.donde tenga backslashes (Windows)."""
        fuente = Repo()
        # Escaneamos para llenar _mapa
        fuente.escanear()
        # Creamos un mock de tarea con donde en formato Windows
        class MockTarea:
            donde = PureWindowsPath(r"Cosas\.cotejo\tareas.md")
        tarea_mock = MockTarea()
        # uri() debe poder obtener el archivo incluso con backslashes
        uri_resultado = fuente.uri(tarea_mock)
        self.assertIsNotNone(uri_resultado)
        self.assertIn(".cotejo", uri_resultado)
