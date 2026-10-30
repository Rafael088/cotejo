"""Las capturas de una entrega: lo que se ve del trabajo, para comprobarlo sin abrir nada.

`cotejo entregar --captura <png>` (repetible) COPIA cada PNG a la carpeta de capturas de Cotejo,
junto a la bitácora, y anota en la entrega dónde quedó, qué tamaño tiene y de qué tipo es. Se
copia, no se referencia: el worktree del agente se borra al aprobar y la captura tiene que seguir
ahí mientras alguien la mira. Con `--captura-desde <archivo|url>` el agente solo deja la petición:
CotejoBoard saca fuera del sandbox una captura móvil y otra de escritorio por cada destino.

El tipo (`movil` o `escritorio`) se deduce del ancho del PNG, que es lo único que Cotejo sabe
con certeza: ancho de hasta 600 px es móvil. La cabecera se lee a mano (no hace falta GTK ni
Pillow): firma de 8 bytes y el trozo IHDR con ancho y alto.

No importa GTK, como el resto del núcleo.
"""

import argparse
import shutil
import struct
from pathlib import Path

from . import bitacora

FIRMA = b"\x89PNG\r\n\x1a\n"
MAXIMO = 8      # capturas por entrega: con móvil y escritorio de cada pantalla sobra
BYTES_MAX = 6 * 1024 * 1024   # por captura; una pantalla de 1280x800 pesa unos cientos de KiB
ANCHO_MOVIL = 600


def dimensiones(ruta):
    """(ancho, alto) del PNG en `ruta`. Lanza ValueError si no es un PNG de verdad."""
    try:
        with open(ruta, "rb") as f:
            cabeza = f.read(24)
    except OSError as error:
        raise ValueError(f"no puedo leer «{ruta}»: {error.strerror or error}") from error
    if len(cabeza) < 24 or not cabeza.startswith(FIRMA) or cabeza[12:16] != b"IHDR":
        raise ValueError(f"«{ruta}» no es un PNG (la cabecera no lo es)")
    ancho, alto = struct.unpack(">II", cabeza[16:24])
    if not ancho or not alto:
        raise ValueError(f"«{ruta}» es un PNG vacío (0 px)")
    return ancho, alto


def tipo(ancho):
    return "movil" if ancho <= ANCHO_MOVIL else "escritorio"


def captura(texto):
    """El tipo de `--captura` en argparse: se rechaza antes de escribir nada."""
    ruta = Path(texto).expanduser()
    try:
        dimensiones(ruta)
        peso = ruta.stat().st_size
    except (ValueError, OSError) as error:
        raise argparse.ArgumentTypeError(
            f"{error}. --captura quiere un PNG ya hecho; con --captura-desde <archivo|URL> "
            "CotejoBoard lo saca por ti fuera del sandbox.") from error
    if peso > BYTES_MAX:
        raise argparse.ArgumentTypeError(
            f"«{texto}» pesa {peso // 1024} KiB y el tope es {BYTES_MAX // 1024} KiB por captura.")
    return str(ruta)


def destino(texto):
    """El tipo de `--captura-desde`: una petición, no una imagen que el agente tenga que crear."""
    if not (texto or "").strip():
        raise argparse.ArgumentTypeError("--captura-desde quiere un archivo o una URL")
    return texto.strip()


def solicitudes(rutas):
    """Destinos sin repetir; cada uno dará dos PNG, así que caben la mitad que capturas sueltas."""
    rutas = list(dict.fromkeys(rutas or ()))
    if len(rutas) > MAXIMO // 2:
        raise ValueError(f"{len(rutas)} destinos son demasiados: el tope es {MAXIMO // 2} "
                         "por entrega (dos capturas por destino)")
    return rutas


def carpeta(tarea_id):
    return bitacora.ARCHIVO.parent / "capturas" / tarea_id


def guardar(tarea_id, rutas):
    """Copia los PNG a la carpeta de la tarea y devuelve lo que se anota en la entrega.

    Una entrega nueva sustituye a las capturas de la anterior. Lanza ValueError si hay demasiadas.
    """
    rutas = list(dict.fromkeys(rutas or ()))
    if len(rutas) > MAXIMO:
        raise ValueError(f"{len(rutas)} capturas son demasiadas: el tope es {MAXIMO} por entrega")
    destino = carpeta(tarea_id)
    if destino.exists():
        shutil.rmtree(destino, ignore_errors=True)
    guardadas = []
    for n, origen in enumerate(rutas, 1):
        ancho, alto = dimensiones(origen)
        destino.mkdir(parents=True, exist_ok=True)
        copia = destino / f"{n:02d}-{tipo(ancho)}.png"
        shutil.copyfile(origen, copia)
        guardadas.append({"ruta": str(copia), "tipo": tipo(ancho), "ancho": ancho, "alto": alto})
    return guardadas


def de_la_entrega(entrega):
    """Las capturas de una entrega que siguen en disco, en su orden. Sin ninguna, lista vacía."""
    vistas = []
    for una in (entrega or {}).get("capturas") or ():
        if isinstance(una, dict) and una.get("ruta") and Path(una["ruta"]).is_file():
            vistas.append(una)
    return vistas


def rotulo(una):
    return {"movil": "Móvil", "escritorio": "Escritorio"}.get(una.get("tipo"), "Captura")
