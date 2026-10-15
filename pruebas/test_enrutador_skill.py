"""El reparto del protocolo. Lo que se prueba es que no rompa archivos ajenos.

Escribir en el `GEMINI.md` o el `AGENTS.md` de alguien es la operación con más consecuencias de
todo el instalador: son archivos que el usuario escribió y que su agente carga en cada sesión.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tareas import skill


class Bloque(unittest.TestCase):
    def test_inyectar_dos_veces_deja_el_archivo_igual(self):
        una = skill.inyectar("# Mis instrucciones\n")
        self.assertEqual(skill.inyectar(una), una)
        self.assertEqual(una.count(skill.INICIO), 1)

    def test_no_se_lleva_por_delante_lo_que_el_usuario_escribio(self):
        texto = skill.inyectar("# Mis reglas\nNunca uses tabuladores.\n")
        self.assertIn("Nunca uses tabuladores.", texto)

    def test_quitar_deja_el_archivo_como_estaba(self):
        original = "# Mis reglas\nNunca uses tabuladores.\n"
        self.assertEqual(skill.quitar(skill.inyectar(original)), original)

    def test_quitar_de_un_archivo_que_creamos_nosotros_lo_deja_vacio(self):
        self.assertEqual(skill.quitar(skill.inyectar("")), "")

    def test_el_bloque_es_corto_porque_se_carga_en_cada_sesion(self):
        self.assertLess(len(skill.BLOQUE), 1200)

    def test_el_protocolo_se_lee_sin_frontmatter(self):
        cuerpo = skill.cuerpo()
        self.assertFalse(cuerpo.startswith("---"))
        self.assertIn("cotejo plan", cuerpo)

    def test_el_bloque_viejo_del_enrutador_se_reemplaza_y_no_se_acumula(self):
        # Quien tuviera instalado el focorouter de antes acabaría con dos protocolos, y el
        # viejo nombra un comando que ya no existe.
        antes = ("# Lo mío\n\n<!-- focorouter:inicio -->\nllama a `focorouter plan`\n"
                 "<!-- focorouter:fin -->\n")
        despues = skill.inyectar(antes)
        self.assertNotIn("focorouter", despues)
        self.assertIn("# Lo mío", despues)
        self.assertEqual(despues.count(skill.INICIO), 1)


class Destinos(unittest.TestCase):
    def setUp(self):
        temporal = tempfile.TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        self.dir = Path(temporal.name)
        # Sin clientes en el PATH de quien corre las pruebas: ahora un `claude` real cuenta.
        vacio = tempfile.TemporaryDirectory()
        self.addCleanup(vacio.cleanup)
        parche = mock.patch.dict(os.environ, {"PATH": vacio.name})
        parche.start()
        self.addCleanup(parche.stop)

    def falso(self, *nombres):
        """Una carpeta con clientes falsos ejecutables, puesta al frente del PATH."""
        bin_ = self.dir / "bin"
        bin_.mkdir(exist_ok=True)
        for nombre in nombres:
            (bin_ / nombre).write_text("#!/bin/sh\n", encoding="utf-8")
            (bin_ / nombre).chmod(0o755)
        os.environ["PATH"] = str(bin_)

    def test_el_cliente_en_el_path_cuenta_aunque_no_tenga_carpeta(self):
        hogar = self.dir / "hogar"
        hogar.mkdir()
        self.falso("claude")
        hecho = skill.instalar(hogar=hogar)
        self.assertTrue((hogar / ".claude/skills/cotejo/SKILL.md").exists())
        self.assertTrue((hogar / ".claude/skills/cotejo-modelos/SKILL.md").exists())
        self.assertFalse((hogar / ".codex").exists())
        self.assertTrue(any(l.startswith("Claude Code:") for l in hecho))

    def test_gemini_y_opencode_por_binario_reciben_el_bloque(self):
        hogar = self.dir / "hogar"
        hogar.mkdir()
        self.falso("gemini", "opencode", "codex")
        with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}):
            skill.instalar(hogar=hogar)
        self.assertIn(skill.INICIO, (hogar / ".gemini/GEMINI.md").read_text(encoding="utf-8"))
        self.assertIn(skill.INICIO,
                      (hogar / ".config/opencode/AGENTS.md").read_text(encoding="utf-8"))
        self.assertTrue((hogar / ".codex/skills/cotejo/SKILL.md").exists())

    def test_un_binario_con_otro_nombre_no_cuenta(self):
        hogar = self.dir / "hogar"
        hogar.mkdir()
        self.falso("claudex")
        self.assertEqual(skill.instalar(hogar=hogar), [])
        self.assertFalse((hogar / ".claude").exists())

    def test_de_punta_a_punta_con_hogar_vacio_y_claude_falso(self):
        hogar = self.dir / "hogar"
        hogar.mkdir()
        self.falso("claude")
        entorno = {"HOME": str(hogar), "PATH": os.environ["PATH"]}
        salida = subprocess.run(
            [sys.executable, "-m", "tareas.skill"], cwd=skill.RAIZ, env=entorno,
            capture_output=True, text=True, check=True).stdout
        self.assertNotIn("Ningún agente conocido", salida)
        self.assertTrue((hogar / ".claude/skills/cotejo/SKILL.md").exists())

    def test_no_se_le_crea_carpeta_a_un_agente_que_no_esta_instalado(self):
        hecho = skill.instalar(hogar=self.dir)
        self.assertEqual(hecho, [])
        self.assertFalse((self.dir / ".gemini").exists())

    def test_al_agente_instalado_se_le_deja_el_protocolo(self):
        (self.dir / ".claude").mkdir()
        (self.dir / ".gemini").mkdir()
        (self.dir / ".gemini/GEMINI.md").write_text("# Lo mío\n", encoding="utf-8")
        skill.instalar(hogar=self.dir)
        self.assertTrue((self.dir / ".claude/skills/cotejo/SKILL.md").exists())
        self.assertTrue((self.dir / ".claude/skills/cotejo-modelos/SKILL.md").exists())
        gemini = (self.dir / ".gemini/GEMINI.md").read_text(encoding="utf-8")
        self.assertIn("# Lo mío", gemini)
        self.assertIn(skill.INICIO, gemini)

    def test_la_skill_vieja_del_enrutador_se_quita_al_instalar(self):
        vieja = self.dir / ".claude/skills/focorouter"
        vieja.mkdir(parents=True)
        (vieja / "SKILL.md").write_text("el de antes\n", encoding="utf-8")
        skill.instalar(hogar=self.dir)
        self.assertFalse(vieja.exists())
        self.assertTrue((self.dir / ".claude/skills/cotejo/SKILL.md").exists())

    def test_se_guarda_copia_antes_de_tocar_un_archivo_ajeno(self):
        (self.dir / ".gemini").mkdir()
        (self.dir / ".gemini/GEMINI.md").write_text("# Lo mío\n", encoding="utf-8")
        skill.instalar(hogar=self.dir)
        self.assertTrue((self.dir / ".gemini/GEMINI.md.bak").exists())

    def test_desinstalar_devuelve_el_archivo_ajeno_a_como_estaba(self):
        (self.dir / ".gemini").mkdir()
        ruta = self.dir / ".gemini/GEMINI.md"
        ruta.write_text("# Lo mío\n", encoding="utf-8")
        skill.instalar(hogar=self.dir)
        skill.desinstalar(hogar=self.dir)
        self.assertEqual(ruta.read_text(encoding="utf-8"), "# Lo mío\n")

    def test_desinstalar_quita_tambien_la_skill_de_modelos(self):
        (self.dir / ".claude").mkdir()
        skill.instalar(hogar=self.dir)
        skill.desinstalar(hogar=self.dir)
        self.assertFalse((self.dir / ".claude/skills/cotejo-modelos").exists())


if __name__ == "__main__":
    unittest.main()


# Los (verbo, acción) que nombraba SKILL.md antes de partirlo en núcleo y referencias (v1.2.2):
# la prueba de que partirlo no perdió ninguno.
VERBOS_DE_ANTES = {
    "anotar", "asignar", "bitacora", "bloquear", "buscar", "capacidad", "comprobar", "contexto",
    "crear", "despachar", "doctor", "editar", "entregar", "init", "leer", "limpiar", "modelos",
    "plan", "resolver", "revisar", "tareas", "worktrees",
}
ACCIONES_DE_ANTES = {("config", "validar"), ("fuentes", "agregar"), ("fuentes", "usar"),
                     ("importar", "plan"), ("modelos", "agregar"), ("proponer", "decision"),
                     ("temas", "comprobar"), ("temas", "nuevo")}
TOKENS_MAXIMOS = 1500
CARACTERES_POR_TOKEN = 3.6      # la constante del medidor de ahorro


def _nombrados(texto):
    return re.findall(r"(?:cotejo|tareas-obsidian) (\w+)(?: (\w+))?", texto)


class SkillCorta(unittest.TestCase):
    def archivos(self):
        return sorted(skill.REFERENCIAS.glob("*.md"))

    def test_skill_md_cabe_en_1500_tokens(self):
        texto = skill.SKILL.read_text(encoding="utf-8")
        self.assertLessEqual(len(texto) / CARACTERES_POR_TOKEN, TOKENS_MAXIMOS)

    def test_hay_referencias_y_skill_md_dice_cuando_leer_cada_una(self):
        archivos = self.archivos()
        self.assertTrue(archivos)
        texto = skill.SKILL.read_text(encoding="utf-8")
        for archivo in archivos:
            self.assertIn(f"referencias/{archivo.name}", texto)

    def test_las_referencias_nombran_solo_verbos_que_existen(self):
        from tareas import cli
        verbos = cli.analizador()._subparsers._group_actions[0].choices
        for archivo in self.archivos():
            for verbo, accion in _nombrados(archivo.read_text(encoding="utf-8")):
                self.assertIn(verbo, verbos, f"{archivo.name} nombra «{verbo}», que no existe")
                sub = getattr(verbos[verbo], "_subparsers", None)
                if accion and sub:
                    acciones = set(sub._group_actions[0].choices)
                    if accion in acciones or verbo in ("fuentes", "temas", "config"):
                        self.assertIn(accion, acciones, f"«{verbo} {accion}» no existe")

    def test_el_conjunto_no_pierde_ningun_verbo_de_antes(self):
        textos = [skill.SKILL] + self.archivos()
        pares = set()
        for archivo in textos:
            pares |= set(_nombrados(archivo.read_text(encoding="utf-8")))
        verbos = {v for v, _ in pares}
        acciones = {(v, a) for v, a in pares if a}
        self.assertFalse(VERBOS_DE_ANTES - verbos, VERBOS_DE_ANTES - verbos)
        self.assertFalse(ACCIONES_DE_ANTES - acciones, ACCIONES_DE_ANTES - acciones)

    def test_se_instalan_junto_a_la_skill_y_se_quitan_al_desinstalar(self):
        with tempfile.TemporaryDirectory() as hogar:
            hogar = Path(hogar)
            for agente in (".claude", ".codex"):
                (hogar / agente).mkdir()
            skill.instalar(hogar)
            for agente in (".claude", ".codex"):
                carpeta = hogar / agente / "skills/cotejo/referencias"
                for archivo in self.archivos():
                    copia = carpeta / archivo.name
                    self.assertEqual(copia.read_text(encoding="utf-8"),
                                     archivo.read_text(encoding="utf-8"))
            # Una referencia que ya no existe no se queda de una instalación anterior.
            vieja = hogar / ".claude/skills/cotejo/referencias/vieja.md"
            vieja.write_text("x", encoding="utf-8")
            skill.instalar(hogar)
            self.assertFalse(vieja.exists())
            skill.desinstalar(hogar)
            for agente in (".claude", ".codex"):
                self.assertFalse((hogar / agente / "skills/cotejo").exists())


class SkillsCompaneras(unittest.TestCase):
    """`cotejo-fuentes` va con el protocolo, y tampoco puede nombrar verbos que no existen."""

    def test_se_instala_y_se_quita_junto_al_protocolo(self):
        with tempfile.TemporaryDirectory() as hogar:
            hogar = Path(hogar)
            (hogar / ".claude").mkdir()
            skill.instalar(hogar)
            destino = hogar / ".claude/skills/cotejo-fuentes/SKILL.md"
            self.assertTrue(destino.exists())
            skill.desinstalar(hogar)
            self.assertFalse(destino.exists())

    def test_nombra_solo_verbos_y_acciones_que_existen(self):
        from tareas import cli
        texto = (skill.RAIZ / "skills/cotejo-fuentes/SKILL.md").read_text(encoding="utf-8")
        verbos = cli.analizador()._subparsers._group_actions[0].choices
        acciones = set(verbos["fuentes"]._subparsers._group_actions[0].choices)
        for verbo, accion in re.findall(r"cotejo (\w+)(?: (\w+))?", texto):
            self.assertIn(verbo, verbos, f"cotejo-fuentes nombra «{verbo}», que no existe")
            if verbo == "fuentes" and accion:
                self.assertIn(accion, acciones, f"«fuentes {accion}» no existe")
