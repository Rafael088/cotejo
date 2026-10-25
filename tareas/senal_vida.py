"""Señal de vida del agente en la ficha (v1.3.0, cotejo-21y2ah), sin GTK.

Un agente lanzado desde el board puede pasar minutos sin escribir nada (está pensando) y la
ficha se quedaba en «Empezó con…»: parecía que no había arrancado. Aquí se decide, en llano,
cómo va: cuánto lleva, cuánto hace que se movió y, si pasa demasiado, qué hacer.

**La señal de «último movimiento» es la fecha de modificación del `.log` del agente.** Es la
más fiable y barata: el agente escribe una línea por evento (lo que dice, cada herramienta que
usa y su resultado) y el sistema anota la hora sin que nadie lea el archivo; un `stat` por
segundo no cuesta nada. La actividad del worktree se descartó porque recorrerlo es caro y un
agente que lee o piensa no toca ningún archivo; la bitácora, porque solo se escribe al entregar
o bloquear. Si el log no existe todavía, se cuenta desde que se lanzó (`ts`).

Umbrales: hasta 2 min sin moverse, «trabajando»; de 2 a 10 min, «está pensando, puede tardar»;
más de 10 min, o si el proceso ya no existe, «parece colgado» y qué hacer.
"""

import os
import time

from . import lanzados

PENSANDO_DESDE = 120      # segundos sin moverse para dejar de decir «trabajando»
COLGADO_DESDE = 600       # y para decir «parece colgado»

ACTIVO, PENSANDO, COLGADO = "activo", "pensando", "colgado"


def duracion(segundos):
    """«45 s», «3 min», «1 h 05 min»."""
    segundos = max(0, int(segundos))
    if segundos < 60:
        return f"{segundos} s"
    if segundos < 3600:
        return f"{segundos // 60} min"
    return f"{segundos // 3600} h {segundos % 3600 // 60:02d} min"


def ultimo_movimiento(registro):
    """Cuándo escribió por última vez (mtime del log), o el momento del lanzamiento si aún no
    hay log. None si no hay de dónde sacarlo."""
    try:
        return os.path.getmtime(registro.get("log") or "")
    except (OSError, TypeError, ValueError):
        pass
    try:
        return float(registro.get("ts"))
    except (TypeError, ValueError):
        return None


def nivel(silencio, vivo=True):
    if not vivo or silencio >= COLGADO_DESDE:
        return COLGADO
    return PENSANDO if silencio >= PENSANDO_DESDE else ACTIVO


def evaluar(registro, ahora=None, movimiento=None):
    """Cómo va el agente de este registro, o None si no está trabajando ni se le dio por
    muerto (en espera, detenido, terminado: ahí no hay señal de vida que enseñar).

    Devuelve `{nivel, animar, lleva, silencio, titulo, detalle, ayuda}`; los textos van en
    llano. `movimiento` fuerza la hora del último movimiento (las pruebas)."""
    e = lanzados.estado(registro)
    if not e or e.get("estado") not in (lanzados.TRABAJANDO, lanzados.MURIO):
        return None
    ahora = float(ahora if ahora is not None else time.time())
    inicio = float(registro.get("ts") or ahora)
    lleva = max(0.0, ahora - inicio)
    ultimo = movimiento if movimiento is not None else ultimo_movimiento(registro)
    silencio = max(0.0, ahora - (ultimo if ultimo is not None else inicio))
    vivo = e["estado"] == lanzados.TRABAJANDO
    cual = nivel(silencio, vivo)
    quien = e.get("modelo") or "El agente"
    marca = f"Lleva {duracion(lleva)}. Último movimiento hace {duracion(silencio)}."
    if not vivo:
        return {"nivel": COLGADO, "animar": False, "lleva": lleva, "silencio": silencio,
                "titulo": "Parece colgado: el proceso ya no existe",
                "detalle": marca,
                "ayuda": f"{quien} se cerró sin avisar. Devuelve la tarea a Pendiente para "
                         "dejarla en pausa y vuelve a pasarla a Haciendo para retomarla "
                         "donde quedó."}
    if cual == COLGADO:
        return {"nivel": cual, "animar": False, "lleva": lleva, "silencio": silencio,
                "titulo": "Parece colgado",
                "detalle": marca,
                "ayuda": f"{quien} lleva más de {duracion(COLGADO_DESDE)} sin escribir nada. "
                         "Si no esperas una tarea larga, devuélvela a Pendiente (lo detiene "
                         "sin perder su trabajo) y vuelve a pasarla a Haciendo para retomarla."}
    if cual == PENSANDO:
        return {"nivel": cual, "animar": True, "lleva": lleva, "silencio": silencio,
                "titulo": "Está pensando, puede tardar",
                "detalle": marca,
                "ayuda": "Una tarea difícil puede pasar unos minutos sin escribir. "
                         "Si pasa de 10 min, aquí te diré qué hacer."}
    return {"nivel": cual, "animar": True, "lleva": lleva, "silencio": silencio,
            "titulo": "Trabajando",
            "detalle": marca,
            "ayuda": ""}
