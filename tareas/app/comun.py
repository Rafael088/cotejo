"""Constantes, medidas y funciones sin widgets del board (y `board.json`)."""

import json
import math
import re
import time
from pathlib import Path

from gi.repository import GLib, Gtk
from enrutador import config as enrutador_config, niveles as enrutador_niveles

from .. import modelo, rutas
from .escala import px


APP_ID = "io.github.cotejoapp.Cotejo"


DATOS = Path(__file__).resolve().parents[2] / "data"


BOARD_PATH = rutas.estado() / "board.json"


TODOS = "\x00todos"  # opción "Todos los proyectos" del board


def cargar_board():
    """Lo que se guardó de la interfaz, entero: `board.json` es un diccionario, no un valor."""
    try:
        datos = json.loads(BOARD_PATH.read_text())
        return datos if isinstance(datos, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def guardar_board(**cambios):
    """Guarda claves sueltas sin pisar las demás: cada cosa que recuerda la interfaz
    (el proyecto elegido, el filtro de Finalizada...) se guarda por su cuenta."""
    datos = cargar_board()
    datos.update(cambios)
    try:
        BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
        BOARD_PATH.write_text(json.dumps(datos, ensure_ascii=False))
    except OSError:
        pass


def texto_a_markup(texto):
    """Markdown mínimo de una línea a Pango: enlaces a texto plano y `código` a monoespacio."""
    texto = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", texto)
    texto = re.sub(r"\[\[([^\]]+)\]\]", r"\1", texto)
    texto = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", texto)
    partes = texto.split("`")
    salida = []
    for i, parte in enumerate(partes):
        parte = GLib.markup_escape_text(parte)
        if i % 2 == 1 and i < len(partes) - 1:
            parte = f'<span font_family="IBM Plex Mono" size="92%">{parte}</span>'
        elif i % 2 == 1:
            parte = "`" + parte
        salida.append(parte)
    markup = "".join(salida)
    markup = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", markup)
    return markup


# Tokens de movimiento: dos duraciones, no una copiada en todo (entrar es lo único que se anima).
ENTRADA_MS = 180


# Escala de espaciado: cinco pasos uniforme (suma de 4px). Los valores 1, 2, 3 px (micro-ajustes
# de componentes específicos: .boxed-list row padding, .menu-item padding)
# quedan fuera porque son precisiones de control, no espaciado de layout.
# VINCULACIÓN CSS: estos valores deben coincidir con --k-espacio-* en :root del CSS arriba.
ESPACIADO_XS = 4   # muy compacto: separadores, encabezados


ESPACIADO_SM = 8   # compacto: chips, padding interno


ESPACIADO_MD = 12  # normal: padding estándar, spacing entre elementos


ESPACIADO_LG = 16  # amplio: separación clara entre secciones


ESPACIADO_XL = 20  # máximo: aire alrededor de contenido principal


def posicion_centrado(chip_x, chip_ancho, banda_ancho, maximo):
    """Valor del hadjustment que deja el centro del chip en el centro de la banda.

    `chip_x` es la posición del chip dentro del contenido desplazable; `maximo` es lo más lejos
    que puede ir el ajuste (upper - page-size). Se acota a [0, maximo]: el primero y el
    último se quedan en su extremo en vez de dejar un hueco al lado.
    """
    objetivo = chip_x + chip_ancho / 2 - banda_ancho / 2
    return max(0.0, min(objetivo, max(0.0, maximo)))


def animaciones_activas():
    ajustes = Gtk.Settings.get_default()
    return bool(ajustes and ajustes.get_property("gtk-enable-animations"))


def agentes_disponibles():
    """El menú del board refleja los modelos que un cliente registró en Cotejo."""
    try:
        config = enrutador_config.cargar()
        return enrutador_niveles.agentes(config.get("modelos"))
    except enrutador_config.ConfigInvalida:
        # El board sigue siendo usable para corregir una config rota desde la CLI.
        return modelo.AGENTES


def aplicar_clase_animaciones(ventana):
    """Pone o quita `.sin-animaciones` en la ventana según gtk-enable-animations.

    Es el puente entre GtkSettings y el CSS: aparecer() puede preguntarle a
    animaciones_activas() antes de animar porque anima desde Python, pero los `transition` de
    .carta y .banda-chip los resuelve el motor de CSS solo, sin pasar por aquí. Por eso hace
    falta la clase, y por eso quien cambia el ajuste con la app abierta (notify::gtk-enable-
    animations) tiene que volver a llamar esto.
    """
    if animaciones_activas():
        ventana.remove_css_class("sin-animaciones")
    else:
        ventana.add_css_class("sin-animaciones")


def hace(cuando):
    """«hace 3 h». Una evidencia de hace un rato y una de hace tres días no se revisan igual,
    y una fecha completa obliga a hacer la resta a mano."""
    try:
        segundos = max(0, int(time.time()) - int(cuando))
    except (TypeError, ValueError):
        return ""
    if segundos < 60:
        return "recién"
    if segundos < 5400:
        return f"hace {segundos // 60} min"
    if segundos < 172800:
        return f"hace {segundos // 3600} h"
    return f"hace {segundos // 86400} d"


def miles(numero):
    """«382.104». Un número de seis cifras sin separar no se lee, se cuenta con el dedo."""
    return f"{int(numero):,}".replace(",", ".")


def compacto(numero):
    """«1.1K», «2.1M», «20.1M»: la cifra del pie en notación compacta, que se lee de un vistazo.

    Se trunca y no se redondea, para no prometer nunca más de lo ahorrado (999.999 es «999.9K»,
    no «1000K»). El número exacto sigue en la ayuda del medidor.
    """
    numero = int(numero)
    for divisor, sufijo in ((10**9, "B"), (10**6, "M"), (10**3, "K")):
        if numero >= divisor:
            valor = math.floor(numero * 10 / divisor) / 10
            return f"{valor:.1f}".removesuffix(".0") + sufijo
    return str(numero)


# A dónde lleva «Invita al autor a un café». Vacío, la fila no sale: un botón que no lleva a
# ningún sitio es peor que no tenerlo.
DONAR_URL = "https://link.mercadopago.com.co/cotejo"


def frase_ahorro(datos):
    """«90.4K tokens ahorrados hoy», o «43 tokens de más hoy» cuando no se ahorró nada.

    Que la frase pueda decir «de más» no es un adorno: con notas chicas, el JSON de la CLI pesa
    más que la nota que describe, y un medidor que solo sabe felicitar es un cartel, no una
    medida. Ese día el número sigue saliendo en plata y no en ámbar ni en rojo, porque tampoco
    es una alarma: es lo que se midió.
    """
    ahorrados = datos.get("tokens_ahorrados", 0)
    if ahorrados < 0:
        return f"{compacto(-ahorrados)} tokens de más hoy"
    return f"{compacto(ahorrados)} tokens ahorrados hoy"


def anotacion_visible(tarea, anotacion):
    """Qué enseñar de la última anotación de una tarea: (clase, título, texto), o None.

    El motivo de una devolución acompaña a la tarea hasta que se vuelva a entregar, porque es
    lo que hay que leer antes de rehacerla. La evidencia solo importa mientras alguien tiene
    que comprobarla: una vez marcada, ya cumplió.
    """
    if anotacion is None or tarea.hecha:
        return None
    if anotacion.get("motivo"):
        palabra = "BLOQUEADA" if anotacion.get("operacion") == "bloquear" else "DEVUELTA"
        clase, texto = "detenida", anotacion["motivo"]
    elif tarea.columna == "por-validar" and anotacion.get("evidencia"):
        clase, palabra, texto = "entregada", "ENTREGADA", anotacion["evidencia"]
    else:
        return None
    detalle = " · ".join(parte for parte in (
        f"@{anotacion['agente']}" if anotacion.get("agente") else "",
        hace(anotacion.get("cuando")),
    ) if parte)
    return clase, f"{palabra} · {detalle}" if detalle else palabra, texto


SALIDA_CARTA_MS = 1500


REVELAR_MS = 160


def id_corto(id_tarea):
    """La parte final del id sin «cotejo-» (cotejo-8y7t68 -> 8y7t68).

    Una tarea sin `^cotejo-…` en su nota tiene por id su ruta y su línea
    («01-Proyectos/Bot.md:45»): en una carta de 354 px eso no es un id, así que queda «L45».
    """
    id_tarea = id_tarea or ""
    for prefijo in ("cotejo-", "foco-"):
        if id_tarea.startswith(prefijo):
            return id_tarea[len(prefijo):]
    ruta, dos_puntos, linea = id_tarea.rpartition(":")
    if dos_puntos and ruta and linea.isdigit():
        return f"L{linea}"
    return id_tarea


def ordenar_por_version(tareas):
    """Las tareas de Pendiente agrupadas por versión, de la más próxima a la más lejana.

    Estable: dentro de una versión queda el orden de la nota. Las que no tienen versión van al
    final, porque no son de ninguna entrega en curso.
    """
    def clave(tarea):
        version = tarea.version_del_texto
        if not version:
            return (1, ())
        return (0, tuple(int(n) for n in re.findall(r"\d+", version)))
    return sorted(tareas, key=clave)


# Qué decirle a alguien cuando una columna está vacía: nunca un hueco en blanco.
# Cada columna con su icono: el estado se reconoce por la forma antes que por el texto,
# que es lo que deja leer el board de refilón.
ICONOS_COLUMNA = {
    "pendiente": "estado-pendiente",
    "en-curso": "estado-en-curso",
    "por-validar": "estado-por-validar",
    "hecha": "estado-hecha",
}


NOMBRES_DIFICULTAD = {"facil": "Fácil", "medio": "Media", "dificil": "Difícil"}


ICONOS_DIFICULTAD = {"facil": "dificultad-facil", "medio": "dificultad-medio",
                     "dificil": "dificultad-dificil"}


# Las columnas miden un ancho fijo, cada una el suyo: no se estiran con la ventana. El
# conjunto va centrado con aire a los lados y arriba/abajo; si la ventana es más estrecha, el
# ScrolledWindow deja llegar a todo. Un texto largo hace la carta más alta, nunca la columna
# más ancha. (El CSS de GTK no tiene width: los anchos van aquí.)
ANCHO_PENDIENTE = 354


ANCHO_HACIENDO = 450


ANCHO_POR_COMPROBAR = 540


# Finalizada siempre plegada: un riel que solo tiene que caber el ícono.
ANCHO_RIEL = 52


ANCHO_COLUMNAS = {"pendiente": ANCHO_PENDIENTE, "en-curso": ANCHO_HACIENDO,
                  "por-validar": ANCHO_POR_COMPROBAR, "hecha": ANCHO_RIEL}


MARGEN_TABLERO_LADOS = 40


# Lo más que se deja encoger cada columna cuando la ventana es estrecha (el riel no encoge).
# Con los anchos de arriba el tablero pide ~1500 px: en una ventana de 1430 la última columna
# quedaba fuera de pantalla. Debajo de estos pisos ya manda el desplazamiento horizontal.
ANCHO_MINIMO_COLUMNAS = {"pendiente": 300, "en-curso": 360, "por-validar": 440}


def anchos_columnas(disponible):
    """Ancho de cada columna para un tablero que dispone de `disponible` px.

    Con espacio de sobra, los anchos de ANCHO_COLUMNAS (a la escala de ahora, `px`); si falta, lo que falta se reparte
    entre las tres columnas anchas en proporción a lo que pueden ceder, sin pasar de su piso.
    """
    anchos = {clave: px(ancho) for clave, ancho in ANCHO_COLUMNAS.items()}
    falta = (sum(anchos.values()) + 3 * px(ESPACIADO_SM) + 2 * px(MARGEN_TABLERO_LADOS)
             - disponible)
    if falta <= 0:
        return anchos
    cesion = {c: anchos[c] - px(m) for c, m in ANCHO_MINIMO_COLUMNAS.items()}
    total = sum(cesion.values())
    for clave, puede in cesion.items():
        anchos[clave] -= round(min(falta, total) * puede / total)
    return anchos


ANCHO_BARRA_MAESTRO = 520


MARGEN_TABLERO_VERTICAL = 28


# Tope del ancho natural de una etiqueta de carta (en caracteres): el texto se envuelve.
MAX_CARACTERES_CARTA = 36


# La banda de proyectos mide el 60 % del ancho: en una rejilla de cinco columnas iguales,
# la banda ocupa las tres del centro.
FRANJA_BANDA = 5


ALTO_CHIP_BANDA = 36  # alto del chip; con el padding de la banda (8 + 8) da ~52


CENTRADO_MS = 220


UMBRAL_ARRASTRE = 6  # píxeles que hay que mover el mouse para que un clic pase a ser arrastre


# Los atajos que el board ya tenía. Se enseñan porque tenerlos y no decirlos es igual que
# no tenerlos: hasta ahora solo se llegaba a ellos por accidente o leyendo el código.
ATAJOS = (
    ("Ctrl F", "Buscar entre las tareas"),
    ("Ctrl ← / →", "Mover la tarea a la columna de al lado"),
    ("Alt ← / →", "Pasar el dot a otra tarea en curso"),
    ("← / →", "Cambiar de columna"),
    ("↑ / ↓", "Cambiar de tarea"),
    ("Tab", "Saltar de columna en columna"),
    ("Enter", "Abrir la ficha de la tarea"),
    ("Menú", "Abrir las acciones de la tarea"),
    ("Ctrl R", "Volver a leer el vault"),
    ("F9", "Enseñar u ocultar los proyectos"),
    ("Esc", "Borrar la búsqueda, o cerrar el board"),
)


# Con algo buscado, «Sin pendientes» sería mentira: hay tareas, pero ninguna dice esto. Lo que
# hay que ofrecer es la salida, no el consuelo.
VACIO_BUSQUEDA = ("Nada coincide", "Esc borra la búsqueda")


VACIOS = {
    "pendiente": ("Nada pendiente", "Las tareas que escribas en el vault entran por aquí"),
    "en-curso": ("Nada en curso", "Asígnale una tarea a un agente desde el menú de su carta"),
    "por-validar": ("Nada por comprobar", "Lo que un agente entregue espera aquí a que lo revises"),
    "hecha": ("Nada finalizada", "Lo que des por bueno se queda aquí"),
}


# Lo que mide el símbolo en la animación de arranque, en píxeles: el de un ícono grande.
LADO_ARRANQUE = 112
