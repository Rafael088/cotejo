"""Conversión pequeña y segura del Markdown que enseña Cotejo a Pango."""

import html
import re


MONO = 'span font_family="IBM Plex Mono" size="92%"'


def _en_linea(texto):
    """Pinta negrita y código; cualquier otra cosa queda escapada como texto."""
    salida = []
    posicion = 0
    while posicion < len(texto):
        if texto.startswith("**", posicion):
            final = texto.find("**", posicion + 2)
            if final != -1:
                salida.append("<b>" + _en_linea(texto[posicion + 2:final]) + "</b>")
                posicion = final + 2
                continue
        if texto[posicion] == "`":
            final = texto.find("`", posicion + 1)
            if final != -1:
                codigo = html.escape(texto[posicion + 1:final], quote=True)
                salida.append(f"<{MONO}>{codigo}</span>")
                posicion = final + 1
                continue
        siguiente = posicion + 1
        while siguiente < len(texto) and texto[siguiente] != "`" \
                and not texto.startswith("**", siguiente):
            siguiente += 1
        salida.append(html.escape(texto[posicion:siguiente], quote=True))
        posicion = siguiente
    return "".join(salida)


def texto_a_markup(texto):
    """Markdown deliberadamente corto a Pango: negrita, código, listas y párrafos.

    Solo las construcciones que entiende esta función producen etiquetas. El resto, incluidos
    ``&``, ``<`` y ``>``, se escapa antes de llegar a Pango.
    """
    texto = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", texto)
    texto = re.sub(r"\[\[([^\]]+)\]\]", r"\1", texto)
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
    lineas = []
    for linea in texto.split("\n"):
        lista = re.match(r"^(\s*)-\s+(.*)$", linea)
        if lista:
            linea = f"{lista.group(1)}• {lista.group(2)}"
        lineas.append(_en_linea(linea))
    return "\n".join(lineas)
