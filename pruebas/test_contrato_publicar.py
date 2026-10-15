"""El contrato con el agente: ningún verbo etiqueta ni publica.

Etiquetar y publicar son decisiones de una persona, no de quien reparte o ejecuta trabajo.
Esta prueba existe para que añadir etiquetado o publicación automática sea una decisión consciente.
"""

import argparse
import pathlib
import re
import unittest

from apoyo import PruebaDeCLI

from tareas import cli
from enrutador import verbos


def _nombres_de_la_cli(analizador, ruta=()):
    """(ruta, nombre) de cada verbo, acción, bandera y argumento del analizador, recursivo."""
    for accion in analizador._actions:
        if isinstance(accion, argparse._SubParsersAction):
            for nombre, sub in accion.choices.items():
                yield ruta, nombre
                yield from _nombres_de_la_cli(sub, (*ruta, nombre))
        elif not isinstance(accion, argparse._HelpAction):
            for nombre in (*accion.option_strings, accion.dest):
                yield ruta, nombre


def verbos_del_enrutador():
    """Solo los que cuelga el enrutador, sin los de Cotejo."""
    sub = argparse.ArgumentParser().add_subparsers()
    verbos.anadir(sub)
    return sub.choices


class ContratoPublicar(unittest.TestCase):
    """Ningún verbo etiqueta ni publica: eso es de una persona."""

    def test_ningun_verbo_de_cli_se_llama_tag_o_publicar(self):
        """Ningún verbo, bandera o argumento de la CLI ejecuta git tag, git push o gh release."""
        # Nombres prohibidos: cualquier variante de publicar, subir, empujar, etiquetar, tagear.
        prohibidas = ("tag", "etiqueta", "publicar", "publish", "push", "gh-release")

        # Recorrer verbos de la CLI
        nombres = set()
        for _, nombre in _nombres_de_la_cli(cli.analizador()):
            nombres.add(nombre.lower())

        # Recorrer verbos del enrutador
        verbos = verbos_del_enrutador()
        nombres.update(v.lower() for v in verbos.keys())

        for prohibida in prohibidas:
            for nombre in nombres:
                # Permite lectura: --list, -l, --merged, etc.
                if prohibida in nombre and not any(x in nombre for x in ("--list", "-l", "--merged")):
                    self.fail(f"Encontrado verbo/bandera/argumento prohibido: {nombre} contiene '{prohibida}'")

    def test_ningun_modulo_ejecuta_git_tag_o_push_o_gh_release(self):
        """Busca en tareas/ y enrutador/ si hay subprocess.run que ejecute git tag, push o gh release."""
        raiz = pathlib.Path(__file__).parent.parent
        modulos = list(raiz.glob("tareas/*.py")) + list(raiz.glob("enrutador/*.py"))

        # Patrón para detectar llamadas a ejecutables peligrosas
        # Buscamos argumentos de subprocess.run que incluyan "tag", "push", "release" en contexto de ejecución
        # Excluimos lecturas como ["git", "tag", "--list"] o git.tag("--merged", ...)

        patrones_peligrosos = [
            # git tag -a, git tag -d, git tag -f (creación/eliminación/fuerza, no lectura)
            r'subprocess\.run\s*\(\s*\[\s*["\']git["\']\s*,\s*[^]]*["\']tag["\']\s*,\s*(?!--list|--merged|-l)',
            # git push
            r'subprocess\.run\s*\(\s*\[\s*["\']git["\']\s*,\s*[^]]*["\']push["\']\s*,',
            r'git\s+push',
            # gh release
            r'subprocess\.run\s*\(\s*\[\s*["\']gh["\']\s*,\s*[^]]*["\']release["\']\s*,',
            # También buscar Popen
            r'Popen\s*\(\s*\[\s*["\']git["\']\s*,\s*[^]]*["\']tag["\']\s*,\s*(?!--list|--merged|-l)',
            r'Popen\s*\(\s*\[\s*["\']git["\']\s*,\s*[^]]*["\']push["\']\s*,',
        ]

        encontrados = []
        for archivo in modulos:
            try:
                contenido = archivo.read_text(encoding='utf-8')
            except Exception:
                continue

            # Excluir archivos de prueba
            if 'test_' in archivo.name:
                continue

            lineas = contenido.split('\n')
            for num_linea, linea in enumerate(lineas, 1):
                # Excluir comentarios
                if linea.lstrip().startswith('#'):
                    continue

                # Buscar patrones peligrosos
                for patron in patrones_peligrosos:
                    if re.search(patron, linea):
                        # Verificar que no sea solo en un string de retorno (como en release.py)
                        # Si la línea tiene subprocess.run o Popen, es peligroso
                        if 'subprocess.run' in linea or 'Popen' in linea:
                            # Si contiene "return" o "=" y luego un string con git tag, es devolución
                            if 'return' in linea and 'f' in linea[:linea.find('git')]:
                                # Probablemente es un f-string que se retorna
                                continue
                            if '"git -C' in linea and 'tag' in linea and '"' in linea[linea.find('tag'):]:
                                # Es un string que se devuelve, no se ejecuta
                                continue
                            encontrados.append(f"{archivo.name}:{num_linea}: {linea.strip()}")

        if encontrados:
            self.fail(f"Encontrados comandos peligrosos:\n" + "\n".join(encontrados))

    def test_release_devuelve_comando_pero_no_lo_ejecuta(self):
        """El verbo `release` devuelve un comando `git tag` para la persona, pero nunca lo ejecuta."""
        # Leer tareas/release.py y verificar que:
        # 1. Tiene una función que devuelve el comando
        # 2. Nunca ejecuta subprocess.run o Popen con "tag"

        release_file = pathlib.Path(__file__).parent.parent / "tareas" / "release.py"
        contenido = release_file.read_text(encoding='utf-8')

        # Debe tener una función comando_tag que devuelva un string
        self.assertIn("def comando_tag", contenido)

        # No debe ejecutar git tag con subprocess
        # (buscar subprocess.run([... tag, -a ...] para ejecución real)
        lineas = contenido.split('\n')
        para_ejecutar = []
        for num_linea, linea in enumerate(lineas, 1):
            if 'subprocess.run' in linea and 'tag' in linea:
                para_ejecutar.append(f"Línea {num_linea}: {linea.strip()}")
            elif 'Popen' in linea and 'tag' in linea:
                para_ejecutar.append(f"Línea {num_linea}: {linea.strip()}")

        if para_ejecutar:
            self.fail(f"release.py no debe ejecutar git tag:\n" + "\n".join(para_ejecutar))

        # Verificar que comando_tag está en las funciones exportadas
        self.assertIn("comando_tag", contenido)
