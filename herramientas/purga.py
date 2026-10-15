"""Purga: revisa un árbol antes de que se convierta en un bundle público.

No arregla nada — señala. La única forma de que un release no lleve encima rutas del equipo
donde se escribió, el nombre de quien lo escribió, un token pegado por accidente o una carpeta
de caché es que algo lo compruebe siempre, de la misma forma, antes de cada release; a mano se
olvida.

Los patrones que busca y las excepciones que acepta viven en `purga_config.json`, al lado de
este archivo, no en el código: así la lista de marcas pendientes de una decisión de identidad
(`marcas`) se edita sin tocar una línea de Python, y una excepción real queda escrita —con su
motivo— en vez de silenciada con un comentario que nadie vuelve a leer.

Nunca imprime el contenido de un hallazgo de categoría «secreto»: solo dónde está y qué patrón
lo disparó. Un informe que repite el secreto que denuncia es otra forma de filtrarlo.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_HERRAMIENTA = Path(__file__).resolve().parent
CONFIG_POR_DEFECTO = RAIZ_HERRAMIENTA / "purga_config.json"

# Extensiones que no vale la pena abrir como texto: binarios legítimos del propio proyecto
# (fuentes, íconos rasterizados si los hubiera). Un archivo que no decodifica como UTF-8 se
# salta igual, esto solo evita el intento y lo cuenta aparte.
EXTENSIONES_BINARIAS = {".ttf", ".otf", ".woff", ".woff2", ".png", ".jpg", ".jpeg", ".webp",
                        ".gif", ".ico", ".pdf"}


@dataclass
class Patron:
    id: str
    categoria: str
    regex: re.Pattern
    motivo: str


@dataclass
class Hallazgo:
    archivo: str
    linea: int
    patron: str
    categoria: str
    motivo: str
    fragmento: str | None  # None para «secreto»: no se repite lo que se denuncia


@dataclass
class Resultado:
    hallazgos: list[Hallazgo] = field(default_factory=list)
    exentos: list[Hallazgo] = field(default_factory=list)
    binarios_omitidos: int = 0
    directorios_prohibidos: list[str] = field(default_factory=list)

    @property
    def limpio(self) -> bool:
        return not self.hallazgos and not self.directorios_prohibidos


def cargar_config(ruta: Path) -> dict:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SystemExit(f"No pude leer la config de purga en {ruta}: {error}")
    faltan = {"patrones", "marcas", "directorios_prohibidos", "lista_blanca"} - datos.keys()
    if faltan:
        raise SystemExit(f"La config de purga en {ruta} no tiene: {', '.join(sorted(faltan))}")
    return datos


def compilar_patrones(config: dict) -> list[Patron]:
    patrones = [Patron(p["id"], p["categoria"], re.compile(p["regex"]), p["motivo"])
                for p in config["patrones"]]
    for marca in config["marcas"]:
        patrones.append(Patron(
            id=f"marca:{marca}",
            categoria="marca",
            regex=re.compile(re.escape(marca), re.IGNORECASE),
            motivo="nombre de marca/identidad pendiente de una decisión (lista «marcas» de la "
                   "config: editarla ahí, no aquí, cuando esa decisión se cierre)"))
    return patrones


def en_lista_blanca(config: dict, ruta_relativa: str, patron_id: str) -> str | None:
    """Devuelve el motivo de la excepción si aplica, o None si el hallazgo cuenta de verdad."""
    for entrada in config["lista_blanca"]:
        if fnmatch.fnmatch(ruta_relativa, entrada["ruta"]) and entrada["patron"] in ("*", patron_id):
            return entrada["motivo"]
    return None


def _es_binario(ruta: Path) -> bool:
    return ruta.suffix.lower() in EXTENSIONES_BINARIAS


def escanear_arbol(raiz: Path, config: dict) -> Resultado:
    """Camina `raiz` y aplica los patrones a cada archivo de texto.

    No desciende dentro de un directorio prohibido (`.git`, `__pycache__`, cachés): su sola
    presencia ya es el hallazgo, y mirar adentro sería caro y no aporta nada nuevo — lo que
    importa de `.git` para este propósito es el historial, que revisa `--historial`, no el
    contenido de sus objetos empaquetados.

    Un *worktree* de git tiene un archivo `.git` (no una carpeta) que solo apunta a la ruta
    real del repo en este equipo: es plomería del checkout, no contenido del proyecto, así que
    se ignora sin contarlo como hallazgo ni como directorio prohibido.

    `.claude/worktrees/` (los worktrees que arma la propia herramienta cuando varios agentes
    trabajan en paralelo) tampoco viaja en el bundle: `worktrees` está en la lista de
    `directorios_prohibidos`, así que se trata como `.git` — se reporta como carpeta, no se
    desciende dentro y su contenido no se cuenta como hallazgo.
    """
    patrones = compilar_patrones(config)
    prohibidos = set(config["directorios_prohibidos"])
    resultado = Resultado()

    for actual_dir, subdirs, archivos in os.walk(raiz):
        subdirs.sort()
        archivos.sort()
        podados = []
        for nombre in list(subdirs):
            if nombre in prohibidos:
                relativo = (Path(actual_dir) / nombre).relative_to(raiz)
                resultado.directorios_prohibidos.append(relativo.as_posix())
                podados.append(nombre)
        for nombre in podados:
            subdirs.remove(nombre)

        for nombre in archivos:
            ruta = Path(actual_dir) / nombre
            relativo = ruta.relative_to(raiz)
            if relativo == Path(".git"):
                continue  # archivo puntero de un worktree, no contenido del proyecto
            if _es_binario(ruta):
                resultado.binarios_omitidos += 1
                continue
            try:
                texto = ruta.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                resultado.binarios_omitidos += 1
                continue

            ruta_relativa = relativo.as_posix()
            for numero, linea in enumerate(texto.splitlines(), start=1):
                for patron in patrones:
                    coincidencia = patron.regex.search(linea)
                    if not coincidencia:
                        continue
                    fragmento = None if patron.categoria == "secreto" else coincidencia.group(0)
                    hallazgo = Hallazgo(ruta_relativa, numero, patron.id, patron.categoria,
                                        patron.motivo, fragmento)
                    motivo_exento = en_lista_blanca(config, ruta_relativa, patron.id)
                    (resultado.exentos if motivo_exento else resultado.hallazgos).append(hallazgo)

    resultado.directorios_prohibidos.sort()
    return resultado


# --- Historial de git: solo secretos, y sin repetir lo que encuentra ---------------------

PATRON_COMMIT = re.compile(r"^commit ([0-9a-f]{40})")


def escanear_historial(raiz: Path, config: dict) -> list[dict]:
    """Busca patrones de categoría «secreto» en todo el historial (`git log --all -p`).

    Solo secretos: purgar identidad del historial es una operación distinta (reescribir
    commits, `filter-repo` o similar) que no hace esta herramienta y que además rompería
    cualquier clon existente — eso lo decide una persona, no un script. Lo que sí hace falta
    verificar siempre es que no quedó un secreto pegado por accidente en algún commit viejo.
    """
    patrones_secreto = [Patron(p["id"], p["categoria"], re.compile(p["regex"]), p["motivo"])
                        for p in config["patrones"] if p["categoria"] == "secreto"]
    if not patrones_secreto:
        return []
    try:
        proceso = subprocess.run(
            ["git", "-C", str(raiz), "log", "--all", "-p", "--no-color"],
            capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"No pude leer el historial de git en {raiz}: {error}")

    hallazgos, commit_actual = [], None
    vistos = set()
    for linea in proceso.stdout.splitlines():
        commit = PATRON_COMMIT.match(linea)
        if commit:
            commit_actual = commit.group(1)
            continue
        for patron in patrones_secreto:
            if patron.regex.search(linea):
                clave = (commit_actual, patron.id)
                if clave in vistos:
                    continue
                vistos.add(clave)
                hallazgos.append({"commit": commit_actual, "patron": patron.id,
                                  "categoria": "secreto", "motivo": patron.motivo})
    return hallazgos


# --- CLI -----------------------------------------------------------------------------------

def _a_dict(hallazgo: Hallazgo) -> dict:
    d = {"archivo": hallazgo.archivo, "linea": hallazgo.linea, "patron": hallazgo.patron,
        "categoria": hallazgo.categoria, "motivo": hallazgo.motivo}
    if hallazgo.fragmento is not None:
        d["fragmento"] = hallazgo.fragmento
    return d


def main(argv=None) -> int:
    analizador = argparse.ArgumentParser(
        prog="purga.py",
        description="Revisa un árbol antes de empaquetarlo: identidad, rutas, secretos y "
                    "carpetas que no deberían viajar en un bundle público.")
    analizador.add_argument("--raiz", type=Path, default=None,
                            help="Árbol a revisar (por defecto, el repo donde vive esta "
                                 "herramienta).")
    analizador.add_argument("--config", type=Path, default=CONFIG_POR_DEFECTO,
                            help=f"Config de patrones y lista blanca (por defecto "
                                 f"{CONFIG_POR_DEFECTO.name}, al lado de este script).")
    analizador.add_argument("--historial", action="store_true",
                            help="Además, busca secretos en todo el historial de git "
                                 "(`git log --all -p`). Más lento; no corre por defecto.")
    analizador.add_argument("--json", action="store_true", help="Salida en JSON.")
    args = analizador.parse_args(argv)

    raiz = (args.raiz or RAIZ_HERRAMIENTA.parent).resolve()
    if not raiz.is_dir():
        analizador.error(f"{raiz} no es un directorio")

    config = cargar_config(args.config)
    resultado = escanear_arbol(raiz, config)
    hallazgos_historial = escanear_historial(raiz, config) if args.historial else None

    if args.json:
        salida = {
            "raiz": str(raiz),
            "limpio": resultado.limpio and not hallazgos_historial,
            "hallazgos": [_a_dict(h) for h in resultado.hallazgos],
            "exentos": [_a_dict(h) for h in resultado.exentos],
            "directorios_prohibidos": resultado.directorios_prohibidos,
            "binarios_omitidos": resultado.binarios_omitidos,
        }
        if hallazgos_historial is not None:
            salida["historial"] = hallazgos_historial
        print(json.dumps(salida, indent=2, ensure_ascii=False))
    else:
        print(f"Purga sobre {raiz}")
        if resultado.directorios_prohibidos:
            print(f"\nDirectorios que no deberían viajar en el bundle "
                 f"({len(resultado.directorios_prohibidos)}):")
            for d in resultado.directorios_prohibidos:
                print(f"  {d}/")
        if resultado.hallazgos:
            print(f"\nHallazgos ({len(resultado.hallazgos)}):")
            for h in resultado.hallazgos:
                extra = f" -> {h.fragmento!r}" if h.fragmento is not None else " (secreto, no se repite el valor)"
                print(f"  {h.archivo}:{h.linea}  [{h.categoria}/{h.patron}] {h.motivo}{extra}")
        if resultado.exentos:
            print(f"\nExentos por lista blanca ({len(resultado.exentos)}):")
            for h in resultado.exentos:
                print(f"  {h.archivo}:{h.linea}  [{h.categoria}/{h.patron}]")
        if hallazgos_historial:
            print(f"\nPosibles secretos en el historial de git ({len(hallazgos_historial)}):")
            for h in hallazgos_historial:
                print(f"  commit {h['commit']}  [{h['patron']}] {h['motivo']} "
                     f"(valor no repetido; revisar ese commit a mano)")
        if resultado.limpio and not hallazgos_historial:
            print("\nSin hallazgos.")
        print(f"\n({resultado.binarios_omitidos} archivos binarios/no-UTF-8 omitidos del "
             f"contenido; su sola presencia no se revisa)")

    limpio = resultado.limpio and not hallazgos_historial
    return 0 if limpio else 1


if __name__ == "__main__":
    sys.exit(main())
