"""Quitar proyectos de Cotejo sin borrar su carpeta por accidente.

Un proyecto de repo puede estar en la lista ``fuentes.repo.repos`` o en el mapa
``migrados`` de la fuente activa. Este módulo solo cambia ese registro. Mover la carpeta a
la papelera es una decisión de la interfaz y se hace aparte, después de confirmarla.
"""

import os
from pathlib import Path

from . import configuracion


class ProyectoNoRegistrado(ValueError):
    """La ruta no está en una lista editable de la configuración."""


def _misma_ruta(una, otra):
    if not una or not otra:
        return False
    try:
        return Path(una).expanduser().resolve() == Path(otra).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return os.path.abspath(os.path.expanduser(str(una))) == \
            os.path.abspath(os.path.expanduser(str(otra)))


def ubicacion(nombre="", carpeta=""):
    """Dónde está registrado: repos, migrados, raíz, Obsidian, entorno o ninguno."""
    datos = configuracion.leer()
    activa = configuracion.fuente_activa(datos)
    if activa == "repo" and os.environ.get("COTEJO_REPOS") is not None:
        return "entorno" if any(_misma_ruta(r, carpeta)
                                for r in os.environ["COTEJO_REPOS"].split(os.pathsep)) else None
    parametros = configuracion.parametros(datos, activa)
    repos = parametros.get("repos") or []
    if isinstance(repos, str):
        repos = [repos]
    if any(_misma_ruta(ruta, carpeta) for ruta in repos):
        return "repos"
    migrados = parametros.get("migrados") or {}
    if isinstance(migrados, dict) and any(
            (nombre and proyecto.casefold() == nombre.casefold()) or _misma_ruta(ruta, carpeta)
            for proyecto, ruta in migrados.items()):
        return "migrados"
    raiz = parametros.get("raiz")
    if activa == "repo" and raiz and carpeta:
        try:
            if Path(carpeta).expanduser().resolve().parent == Path(raiz).expanduser().resolve():
                return "raiz"
        except (OSError, RuntimeError, ValueError):
            pass
    if activa == "obsidian" and nombre:
        return "obsidian"
    return None


def mover_a_papelera(carpeta, papelera):
    """Entrega una carpeta existente a ``papelera``; nunca intenta borrarla por su cuenta."""
    if not str(carpeta or "").strip():
        raise ValueError("El proyecto no tiene una carpeta que se pueda mover")
    ruta = Path(carpeta).expanduser()
    if not ruta.is_dir():
        raise ValueError("La carpeta del proyecto ya no existe")
    resuelta = ruta.resolve()
    if resuelta == Path(resuelta.anchor) or resuelta == Path.home().resolve():
        raise ValueError("Esa ruta es demasiado amplia para moverla a la papelera")
    papelera(str(ruta))


def quitar(nombre="", carpeta=""):
    """Quita un proyecto de la configuración y devuelve la ruta escrita.

    ``carpeta`` también puede ser una ruta que ya no existe: es el caso del aviso del Inicio.
    No toca esa carpeta. Las listas dadas por variables de entorno no se pueden cambiar desde
    la app porque una escritura en config no tendría efecto.
    """
    donde = ubicacion(nombre, carpeta)
    datos = configuracion.leer()
    activa = configuracion.fuente_activa(datos)
    if donde == "entorno":
        raise ProyectoNoRegistrado(
            "La lista de repos viene de COTEJO_REPOS. Quitalo de esa variable de entorno.")

    fuentes = dict(datos.get("fuentes") or {})
    parametros = dict(fuentes.get(activa) or {})
    cambio = False

    if activa == "repo":
        repos = parametros.get("repos") or []
        if isinstance(repos, str):
            repos = [repos]
        nuevos = [ruta for ruta in repos if not _misma_ruta(ruta, carpeta)]
        cambio = nuevos != repos
        if cambio:
            parametros["repos"] = nuevos

        raiz = parametros.get("raiz")
        bajo_raiz = False
        if raiz and carpeta:
            try:
                bajo_raiz = (Path(carpeta).expanduser().resolve().parent ==
                              Path(raiz).expanduser().resolve())
            except (OSError, RuntimeError, ValueError):
                pass
        if bajo_raiz:
            ocultos = [ruta for ruta in (parametros.get("ocultos") or [])
                       if isinstance(ruta, str) and ruta.strip()]
            if not any(_misma_ruta(ruta, carpeta) for ruta in ocultos):
                parametros["ocultos"] = [*ocultos, str(Path(carpeta).expanduser())]
                cambio = True

    migrados = parametros.get("migrados") or {}
    if isinstance(migrados, dict):
        nuevos = {proyecto: ruta for proyecto, ruta in migrados.items()
                  if not ((nombre and proyecto.casefold() == nombre.casefold())
                          or _misma_ruta(ruta, carpeta))}
        if nuevos != migrados:
            parametros["migrados"] = nuevos
            cambio = True

    if activa == "obsidian" and nombre:
        ocultos = [proyecto for proyecto in (parametros.get("ocultos") or [])
                   if isinstance(proyecto, str) and proyecto.strip()]
        if nombre.casefold() not in {proyecto.casefold() for proyecto in ocultos}:
            parametros["ocultos"] = [*ocultos, nombre]
            cambio = True

    if not cambio:
        raise ProyectoNoRegistrado(
            "Este proyecto no está en una lista editable de Cotejo.")

    fuentes[activa] = parametros
    return configuracion.guardar({**datos, "fuentes": fuentes})
