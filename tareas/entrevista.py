"""La entrevista de «Nuevo proyecto» (v1.3.0), sin GTK: qué se pregunta y cómo se vuelve `Respuestas`.

El formulario del board (`tareas/app/entrevista.py`) solo pinta y recoge texto; todo lo que se
puede decidir sin pantalla está aquí para probarlo sin ella. Nada de lógica de prompt: el armado y
la validación son de `tareas/inicio.py` (`armar`, `validar`); esto solo traduce el formulario a
`inicio.Respuestas` y propone una carpeta.

Las preguntas "dónde se usa" y "qué más necesita" son opciones marcables; viajan al prompt como una
lista en texto (`donde_se_usa`, `necesita`), que es lo que `Respuestas` espera.
"""

import os
import re
import unicodedata

from . import inicio

# Valores de ejemplo: la persona los corrige. Son los del prototipo aprobado.
EJEMPLOS = {
    "que_es": "Una app para que los clientes de la barbería reserven su turno",
    "para_quien": "Los clientes de la barbería y yo, que atiendo los turnos",
    "que_hace": "Ver los horarios libres\nReservar con nombre y teléfono\nVer mis turnos del día",
    "fuera": "Pagos en línea y varias sedes",
}

# (texto, marcada por defecto). El texto es lo que se muestra y lo que viaja al prompt.
DONDE = (
    ("En el celular", True),
    ("En el navegador", True),
    ("En el computador, como programa", False),
    ("No sé, que decida el agente", False),
)
NECESITA = (
    ("Guardar datos", True),
    ("Cuentas con contraseña", False),
    ("Cobrar pagos", False),
    ("Enviar avisos (WhatsApp, correo)", True),
)

CARPETA_BASE = "Proyectos"
PALABRAS_NOMBRE = 4
_RELLENO = {"a", "al", "app", "aplicacion", "con", "de", "del", "el", "en", "la", "las", "lo", "los",
            "para", "por", "que", "su", "sus", "un", "una", "uno", "unos", "unas", "y"}


def nombre_sugerido(que_es):
    """Un nombre de carpeta corto a partir de la frase («reservas-barberia»), sin tildes."""
    plano = unicodedata.normalize("NFKD", que_es or "").encode("ascii", "ignore").decode().lower()
    palabras = [p for p in re.findall(r"[a-z0-9]+", plano) if p not in _RELLENO]
    return "-".join(palabras[:PALABRAS_NOMBRE]) or "proyecto-nuevo"


def carpeta_sugerida(que_es, casa=None):
    """`~/Proyectos/<nombre>` con la ruta absoluta de la casa de quien usa Cotejo."""
    casa = casa or os.path.expanduser("~")
    return os.path.join(casa, CARPETA_BASE, nombre_sugerido(que_es))


def lista(marcadas, vacio=""):
    """Las opciones marcadas, en el orden del formulario, como una línea de texto."""
    return ", ".join(marcadas) if marcadas else vacio


def respuestas(que_es, para_quien, que_hace, donde, necesita, fuera, carpeta):
    """Lo que escribió la persona → `inicio.Respuestas` (sin validar: eso es de `inicio.validar`).
    `donde` y `necesita` son las listas de opciones marcadas."""
    return inicio.Respuestas(que_es=que_es, para_quien=para_quien, que_hace=que_hace,
                             carpeta=carpeta, donde_se_usa=lista(donde),
                             necesita=lista(necesita), fuera=fuera)


def prompt_o_error(r):
    """(prompt, "") con lo que se le enviará al agente, o ("", motivo) si falta algo."""
    try:
        return inicio.armar(r), ""
    except ValueError as error:
        return "", str(error)


def rellenadas(r):
    """Cuántas de las seis preguntas tienen respuesta (para la barra de avance del formulario)."""
    return sum(bool((getattr(r, k) or "").strip()) for k in
               ("que_es", "para_quien", "que_hace", "donde_se_usa", "necesita", "fuera"))
