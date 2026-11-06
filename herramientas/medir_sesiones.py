"""Mide la entrada de las sesiones de Claude que nacieron de tareas de Cotejo.

Claude guarda esas sesiones en directorios cuyo nombre termina en ``wt-cotejo-<id>``.
Por defecto se leen de ``~/.claude/projects``:

    python3 herramientas/medir_sesiones.py

La salida TSV agrupa todas las sesiones de cada tarea y muestra los tokens de entrada del
primer turno, el número de turnos y los tokens de entrada acumulados. La entrada de un turno
es la suma de ``input_tokens``, ``cache_creation_input_tokens`` y
``cache_read_input_tokens``: las tres partes forman el contexto que recibió el modelo.

Un mismo mensaje puede aparecer varias veces en el JSONL mientras Claude lo escribe. Se
deduplica por el id del mensaje para no contar esas copias como turnos distintos.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Turno:
    instante: str
    entrada: int


def nombre_de_tarea(carpeta: Path) -> str | None:
    """Devuelve ``cotejo-<id>`` desde el nombre codificado del proyecto de Claude."""
    marca = "wt-cotejo-"
    if marca not in carpeta.name:
        return None
    identificador = carpeta.name.rsplit(marca, 1)[1]
    return f"cotejo-{identificador}" if identificador else None


def entrada_de(uso: dict) -> int:
    """Tokens de contexto del turno, estén o no en caché."""
    campos = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    return sum(valor if isinstance(valor, int) else 0 for campo in campos
               if (valor := uso.get(campo)) is not None)


def turnos_de(archivo: Path) -> list[Turno]:
    """Lee un JSONL y conserva una sola copia, la última, de cada mensaje medido."""
    mensajes: dict[str, Turno] = {}
    with archivo.open(encoding="utf-8") as lineas:
        for numero, linea in enumerate(lineas):
            try:
                registro = json.loads(linea)
            except json.JSONDecodeError:
                # Una sesión activa puede acabar temporalmente en una línea a medio escribir.
                continue
            if registro.get("type") != "assistant":
                continue
            mensaje = registro.get("message")
            if not isinstance(mensaje, dict) or not isinstance(mensaje.get("usage"), dict):
                continue
            # Los JSONL reales traen id; el sustituto evita fusionar registros antiguos que no.
            identificador = mensaje.get("id") or f"sin-id:{numero}"
            mensajes[str(identificador)] = Turno(
                instante=str(registro.get("timestamp") or ""),
                entrada=entrada_de(mensaje["usage"]),
            )
    return list(mensajes.values())


def medir(raiz: Path) -> dict[str, list[Turno]]:
    """Agrupa, por tarea, los turnos únicos de todos sus archivos de sesión."""
    tareas: dict[str, list[Turno]] = {}
    for archivo in raiz.glob("*wt-cotejo-*/*.jsonl"):
        tarea = nombre_de_tarea(archivo.parent)
        if tarea is not None:
            tareas.setdefault(tarea, []).extend(turnos_de(archivo))
    for turnos in tareas.values():
        turnos.sort(key=lambda turno: turno.instante)
    return tareas


def tabla(tareas: dict[str, list[Turno]]) -> str:
    """TSV estable y fácil de guardar para comparar dos mediciones."""
    filas = ["tarea\tprimer_turno\tturnos\tentrada_sumada"]
    for tarea, turnos in sorted(tareas.items()):
        if not turnos:
            continue
        filas.append(f"{tarea}\t{turnos[0].entrada}\t{len(turnos)}\t"
                     f"{sum(turno.entrada for turno in turnos)}")
    return "\n".join(filas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mide los tokens de entrada de las sesiones de Claude por tarea de Cotejo.")
    parser.add_argument("--raiz", type=Path, default=Path.home() / ".claude" / "projects",
                        help="carpeta projects de Claude (por defecto: ~/.claude/projects)")
    args = parser.parse_args(argv)
    print(tabla(medir(args.raiz)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
