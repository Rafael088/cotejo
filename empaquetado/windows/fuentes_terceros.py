"""Arma el archivo de fuentes de terceros que promete THIRD-PARTY-NOTICES (sección C): los
`.src.tar.zst` de MSYS2 de cada paquete bajo LGPL o GPL del runtime de Windows, con el PKGBUILD,
los parches y el código fuente original que declaran. Es la oferta de código fuente de la LGPL
y la GPL (H11), no una obligación aparte de Cotejo: el runtime no se modifica, `construir.py` lo
baja tal cual lo publica MSYS2.

    python3 empaquetado/windows/fuentes_terceros.py <runtime o PAQUETES.txt> [--version X]

`<runtime o PAQUETES.txt>` es la carpeta `runtime/` que dejó `construir.py` (o directamente su
`PAQUETES.txt`): de ahí sale, para cada paquete, su licencia y el nombre de su paquete fuente
(«fuente:», añadido por `armar_runtime`; no siempre es el mismo nombre que el binario: el de
gtk-update-icon-cache es mingw-w64-gtk3, el de python-gobject, mingw-w64-pygobject).

Deja en `--salida` (por omisión, `construido/`, junto a este archivo) un
`Cotejo-<versión>-fuentes-terceros.tar` con el `.src.tar.zst` de cada paquete LGPL o GPL, un
`LEEME.txt` (ES/EN) y `SHA256SUMS`. No toca nada fuera de `--salida` y `--cache`.
"""

import argparse
import re
import shutil
import sys
import tarfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import construir  # noqa: E402  construir.py comparte la caché y bajar()/bajar_fuente()/FUENTES


class ErrorDeFuentes(Exception):
    """Como construir.ErrorDeConstruccion: algo que impide armar el archivo, dicho para arreglarlo."""


LINEA_PAQUETES = re.compile(
    r"^(?P<archivo>\S+)\s+sha256:(?P<sha256>\S+)\s+licencia:(?P<licencia>.+?)\s+"
    r"fuente:(?P<fuente>\S+)$")

LEEME = """\
Cotejo {version} — código fuente de los componentes LGPL/GPL del runtime de Windows
===============================================================================

Estos son los paquetes fuente de MSYS2 ({fuentes}) de cada componente bajo
LGPL o GPL que va en la carpeta «runtime» del instalador de Windows de
Cotejo {version}. Cada .src.tar.zst trae el código fuente original, los
parches y el PKGBUILD con el que MSYS2 lo compiló: son exactamente los
binarios que Cotejo incluye, sin modificar. La lista de binarios, con su
licencia, está en runtime\\PAQUETES.txt.

SHA256SUMS da la huella de cada archivo: sha256sum -c SHA256SUMS

Source packages from MSYS2 ({fuentes}) for every LGPL- or GPL-licensed
component shipped in the «runtime» folder of Cotejo {version} for Windows.
Each .src.tar.zst contains the original source, the patches and the
PKGBUILD MSYS2 used to build the unmodified binaries Cotejo includes. The
binary list, with licenses, is in runtime\\PAQUETES.txt.

Paquetes fuente cubiertos / source packages covered:
{lista}
"""


def leer_paquetes_gpl(ruta_paquetes):
    """{nombre del .src.tar.zst: licencia que declara} de los paquetes GPL o LGPL de un
    `PAQUETES.txt` (lo que deja `construir.armar_runtime`)."""
    elegidos = {}
    for numero, linea in enumerate(ruta_paquetes.read_text(encoding="utf-8").splitlines(), 1):
        coincide = LINEA_PAQUETES.match(linea)
        if not coincide:
            raise ErrorDeFuentes(f"{ruta_paquetes}:{numero}: no entiendo esta línea: {linea!r}")
        if "GPL" in coincide["licencia"].upper():
            elegidos[coincide["fuente"]] = coincide["licencia"]
    return elegidos


def armar(ruta_paquetes, version, salida, fuentes=construir.FUENTES, cache=AQUI / "cache"):
    """Baja el `.src.tar.zst` de cada paquete GPL/LGPL y los empaqueta en un `.tar`. Devuelve su
    ruta."""
    elegidos = leer_paquetes_gpl(ruta_paquetes)
    if not elegidos:
        raise ErrorDeFuentes(f"{ruta_paquetes} no tiene ningún paquete LGPL o GPL: ¿es de "
                             "verdad el PAQUETES.txt de un runtime de Windows?")
    nombre = f"Cotejo-{version}-fuentes-terceros"
    trabajo = salida / nombre
    shutil.rmtree(trabajo, ignore_errors=True)
    trabajo.mkdir(parents=True)
    archivos = []
    for fuente_archivo, licencia in sorted(elegidos.items()):
        construir.avisar(f"  bajando {fuente_archivo} ({licencia})")
        ruta = construir.bajar(f"{fuentes.rstrip('/')}/{fuente_archivo}", cache)
        destino = trabajo / fuente_archivo
        shutil.copy2(ruta, destino)
        archivos.append(destino)
    (trabajo / "SHA256SUMS").write_text(
        "".join(f"{construir._sha256(a)}  {a.name}\n" for a in archivos), encoding="utf-8")
    (trabajo / "LEEME.txt").write_text(LEEME.format(
        version=version, fuentes=fuentes,
        lista="\n".join(f"  {a.name}  licencia:{elegidos[a.name]}" for a in archivos)),
        encoding="utf-8")
    tar_final = salida / f"{nombre}.tar"
    with tarfile.open(tar_final, "w") as tar:
        for archivo in sorted(trabajo.iterdir()):
            tar.add(archivo, arcname=f"{nombre}/{archivo.name}")
    shutil.rmtree(trabajo)
    return tar_final


def main(argumentos=None):
    analizador = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    analizador.add_argument("runtime", type=Path,
                            help="runtime/ de un build de construir.py, o su PAQUETES.txt")
    analizador.add_argument("--version", default=construir.version_por_defecto())
    analizador.add_argument("--salida", type=Path, default=AQUI / "construido")
    analizador.add_argument("--fuentes", default=construir.FUENTES,
                            help="de dónde bajar los paquetes fuente de MSYS2 (una URL o file://)")
    analizador.add_argument("--cache", type=Path, default=AQUI / "cache")
    args = analizador.parse_args(argumentos)
    ruta_paquetes = args.runtime / "PAQUETES.txt" if args.runtime.is_dir() else args.runtime
    if not ruta_paquetes.is_file():
        construir.avisar(f"No encontré {ruta_paquetes}. Corre primero construir.py.")
        return 1
    try:
        tar_final = armar(ruta_paquetes, args.version, args.salida.resolve(), args.fuentes,
                          args.cache.resolve())
    except (ErrorDeFuentes, construir.ErrorDeConstruccion) as error:
        construir.avisar(f"No se pudo armar el archivo de fuentes: {error}")
        return 1
    construir.avisar(f"Fuentes de terceros: {tar_final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
