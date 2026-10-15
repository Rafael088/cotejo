"""Hace `cotejo.ico` a partir del icono de la app (`data/io.github.cotejoapp.Cotejo.svg`).

Windows quiere un .ico para el acceso del menú, el instalador y la lista de programas, y no
sabe leer SVG. Se guarda hecho en el repo, como los iconos de `data/iconos/`, para que
construir no dependa de tener con qué rasterizar; si cambia el SVG, se vuelve a correr:

    python3 empaquetado/windows/icono.py

Rasteriza con `rsvg-convert` y arma el .ico a mano: cada tamaño va como PNG dentro, que es lo
que Windows acepta desde Vista y ahorra depender de Pillow.
"""

import hashlib
import shutil
import struct
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SVG = AQUI.parent.parent / "data" / "io.github.cotejoapp.Cotejo.svg"
DESTINO = AQUI / "cotejo.ico"
# El SHA-256 del SVG del que salió el .ico: construir.py se niega si ya no es el del SVG de hoy.
HUELLA = AQUI / "cotejo.ico.sha256"
TAMANOS = (16, 20, 24, 32, 40, 48, 64, 256)


def ico(pngs):
    """Un .ico con estos PNG ({tamaño: bytes})."""
    cabecera = struct.pack("<HHH", 0, 1, len(pngs))
    desplazamiento = 6 + 16 * len(pngs)
    directorio, cuerpo = b"", b""
    for tamano, png in sorted(pngs.items()):
        lado = 0 if tamano >= 256 else tamano  # 0 quiere decir 256
        directorio += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png),
                                  desplazamiento + len(cuerpo))
        cuerpo += png
    return cabecera + directorio + cuerpo


def huella_svg():
    return hashlib.sha256(SVG.read_bytes()).hexdigest()


def main():
    if not shutil.which("rsvg-convert"):
        sys.exit("Hace falta rsvg-convert (paquete librsvg).")
    pngs = {t: subprocess.run(["rsvg-convert", "-w", str(t), "-h", str(t), str(SVG)],
                              capture_output=True, check=True).stdout for t in TAMANOS}
    DESTINO.write_bytes(ico(pngs))
    HUELLA.write_text(huella_svg() + "\n", encoding="utf-8")
    print(f"{DESTINO} ({len(TAMANOS)} tamaños)")


if __name__ == "__main__":
    main()
