"""Defensas contra lo repetido cuando se reintenta el inicio de un proyecto (v1.3.0).

Reintentar el inicio relanza al agente sobre una carpeta que ya puede traer decisiones
propuestas y arquitectura del intento anterior. El prompt le pide mirar antes lo que hay
(`tareas/inicio.py`), pero un agente se equivoca, así que el código lo cubre sin esperar a
que obedezca. Sin GTK ni disco propio: trabaja sobre un `Almacen` que le pasan.
"""

import dataclasses
import os

from . import arquitectura

# Los ids de las decisiones que seguían en `propuesta` cuando se relanzó el inicio de un
# proyecto (coma-separados). Lo pone `enrutador/preparar.py` en el entorno del agente.
ENV_PROPUESTAS_PREVIAS = "COTEJO_PROPUESTAS_PREVIAS"


def _temas(temas):
    """Los temas de una decisión sin la marca «propuesta», que el agente a veces añade."""
    if isinstance(temas, str):
        temas = temas.split(",")
    return {str(t).strip().lower() for t in temas} - {"propuesta", ""}


def propuesta_previa_repetida(alm, titulo, temas):
    """La propuesta del intento anterior que esta decisión nueva repite, o None.

    Una nueva decisión repite una de las de `COTEJO_PROPUESTAS_PREVIAS` si tiene el mismo
    título o comparte algún tema (sin contar «propuesta»): los dos intentos de un mismo inicio
    titulan distinto lo mismo, pero los temas coinciden. Solo se miran las que siguen en
    `propuesta`: una aceptada por la persona, o ya reemplazada, no se toca nunca. Sin la
    variable (el uso normal) devuelve None y nada cambia.
    """
    previas = {i.strip() for i in os.environ.get(ENV_PROPUESTAS_PREVIAS, "").split(",")}
    previas.discard("")
    if not previas:
        return None
    nuevos = _temas(temas or "")
    plano = " ".join((titulo or "").lower().split())
    candidatas = []
    for entrada in alm.entradas("decision"):
        if entrada.id not in previas or entrada.estado != "propuesta":
            continue
        igual = " ".join(entrada.titulo.lower().split()) == plano
        if igual or nuevos & _temas(entrada.datos.get("temas") or ()):
            candidatas.append((not igual, entrada.id))
    return min(candidatas)[1] if candidatas else None


def conservar_tareas(piezas, cuerpo_previo):
    """Las piezas nuevas, con las tareas que la arquitectura anterior ya tenía enlazadas a la
    pieza del mismo nombre (si la nueva no trae ninguna)."""
    antes = {p.id: p for p in arquitectura.analizar(cuerpo_previo).piezas}
    return [dataclasses.replace(p, tareas=antes[p.id].tareas, textos=antes[p.id].textos)
            if p.id in antes and not (p.tareas or p.textos) else p for p in piezas]


def guardar(alm, tipo, previa, titulo, texto, temas):
    """Anota una entrada. Con `previa` (la arquitectura que ya había: un reintento del inicio, o
    el agente que se repite) la reescribe, verificada, en vez de abrir una segunda. Un proyecto
    tiene una arquitectura; las piezas nuevas van a esa, con `editar`."""
    if previa is None:
        return alm.crear(tipo, titulo, texto, temas=temas)
    return alm.reescribir(previa.id, previa.version, texto=texto, titulo=titulo,
                          campos={"temas": list(temas)})


def aviso(previa):
    """Lo que se añade a la salida de `anotar` cuando se actualizó en vez de crear."""
    if previa is None:
        return {}
    return {"actualizada": True,
            "salida": f"Ya había una arquitectura («{previa.id}»): la actualicé en vez de crear "
                      "otra."}
