"""Texto externo que CotejoBoard puede enseñar.

Los clientes de agentes escriben para una terminal: incluyen colores ANSI y errores en inglés.
El board no es una terminal. Esta capa quita los controles y explica los errores frecuentes sin
ocultar el texto original, que sigue siendo útil para buscar o pedir ayuda.
"""

import re


# CSI (colores, cursor...), OSC (título e hipervínculos) y escapes de dos caracteres. Acepta
# BEL y ST como cierre de OSC. El segundo patrón cubre también secuencias CSI sin ESC que
# algunos intermediarios dejan como ``[91m`` al limpiar el byte de control por su cuenta.
_ANSI = re.compile(
    r"\x1b(?:\][^\x07\x1b]*(?:\x07|\x1b\\)|\[[0-?]*[ -/]*[@-~]|[@-_])"
)
_CSI_SIN_ESCAPE = re.compile(r"\[[0-9;?]+[ -/]*[A-Za-z]")


def sin_ansi(texto):
    """Devuelve ``texto`` sin controles ANSI; tolera ``None`` y otros valores."""
    texto = "" if texto is None else str(texto)
    return _CSI_SIN_ESCAPE.sub("", _ANSI.sub("", texto))


_ERRORES = (
    (("invalid model reference", "invalid model", "model not found", "unknown model",
      "unsupported model", "model does not exist"),
     "El modelo configurado no es válido o no está disponible."),
    (("insufficient account funds", "insufficient funds", "insufficient credits",
      "payment required", "out of credits", "credit balance is too low"),
     "La cuenta del modelo no tiene saldo."),
    (("not logged in", "not authenticated", "authentication required", "authentication_error",
      "unauthorized", "please log in", "please login", "run /login", "missing credentials",
      "invalid api key", "api key not found"),
     "El agente no tiene una sesión iniciada."),
    (("usage limit", "rate limit", "rate_limit", "rate limited", "quota exceeded",
      "insufficient_quota", "too many requests", "error 429", "status 429", "429"),
     "La cuenta alcanzó su límite de uso."),
)


def para_mostrar(texto):
    """Limpia texto para el board y explica un error conocido, con el original debajo.

    Solo añade una explicación cuando reconoce una respuesta estable de los clientes. El resto
    se conserva tal cual, salvo los controles ANSI.
    """
    limpio = sin_ansi(texto)
    minusculas = limpio.lower()
    for marcadores, explicacion in _ERRORES:
        if any(marcador in minusculas for marcador in marcadores):
            if limpio.startswith(explicacion + "\n\nOriginal:\n"):
                return limpio
            return f"{explicacion}\n\nOriginal:\n{limpio}"
    return limpio
