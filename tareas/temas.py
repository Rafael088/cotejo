"""Los temas de CotejoBoard: qué es uno, dónde viven, cómo se comprueban y cuál se usa.

Un tema es un archivo JSON con los colores del board y nada más:

    {
      "nombre": "Claro",
      "descripcion": "Para trabajar de día.",
      "esquema": "claro",
      "colores": {"fondo": "#F6F7F9", "texto": "#101114", ...}
    }

`colores` lleva **todas** las claves de `TOKENS`, ni una más ni una menos: el CSS del board
las pide todas, y un tema al que le falte una deja ese color sin definir y el widget cae al
gris de Adwaita sin que nada avise. `esquema` le dice a Adwaita si lo que no pinta Cotejo
(entradas, casillas, el diálogo) va claro u oscuro.

Los de fábrica viven en `data/temas/`; los que crea un agente, junto a la config, en
`<carpeta de la config>/temas/`. Se crean y se comprueban por la CLI (`temas nuevo`,
`temas comprobar`); en la interfaz solo se **elige**, nunca se edita. Lo que se eligió es la
clave `tema` de la config, así que cambiarlo desde la CLI también llega al board abierto.

Un color solo puede escribirse como `#RGB`, `#RRGGBB`, `#RRGGBBAA`, `rgb()` o `rgba()`. No es
capricho: los valores acaban pegados dentro del CSS, y un formato cerrado es lo que impide
que un tema meta una regla entera donde iba un color —y lo que deja medir el contraste—.

No importa GTK: la CLI lo usa para comprobar, y comprobar no puede costar el arranque de la
interfaz.
"""

import json
import os
import re
from pathlib import Path

from . import configuracion

DATOS = Path(__file__).resolve().parent.parent / "data" / "temas"
DEFECTO = "oscuro"
ESQUEMAS = ("oscuro", "claro")
NOMBRE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# El contrato de un tema: cada color que el CSS del board pide, y para qué lo usa. Los nombres
# dicen el papel y no el color («fondo», no «negro»): en un tema claro el fondo es claro, y un
# token que se llama `blanco` y vale casi negro es una trampa para el siguiente que lo toque.
TOKENS = {
    "fondo": "La ventana y la cabecera",
    "superficie": "Cartas, entradas, listas, menús y diálogos",
    "superficie-alta": "Una carta con el ratón encima o con el foco",
    "columna": "La caja de cada columna del board, un punto por encima del fondo",
    "borde": "El borde de la ventana, de las cartas y de los controles",
    "borde-hondo": "Las separaciones calladas de dentro del board",
    "borde-chip": "El contorno del chip de agente",
    "texto": "El texto principal",
    "texto-chip": "El texto del chip de agente",
    "tenue": "El texto secundario: datos mono, subtítulos, iconos en reposo",
    "tenue-hondo": "Solo el icono de un vacío: por debajo de tenue",
    "senal": "El acento: lo que está en foco o espera que lo compruebes",
    "senal-suave": "El acento como velo: fila elegida, columna donde vas a soltar",
    "sobre-senal": "Texto sobre un relleno de acento: contadores, casilla marcada",
    "ambar": "Lo detenido o roto: devoluciones, avisos",
    "ambar-fondo": "El fondo de la banda de avisos",
    "ambar-velo": "El velo de una anotación detenida o de un vacío roto",
    "velo-sutil": "Hover sobre una fila ya clara; fondo de una anotación",
    "velo": "Hover sobre fondo: chips, opción sugerida",
    "velo-fuerte": "Hover de los botones planos; pastilla del contador",
    "barra": "La barra de desplazamiento en reposo",
    "barra-activa": "La barra de desplazamiento con el ratón encima",
}

# Lo que tiene que leerse, medido como WCAG: (delante, detrás, mínimo, dónde, opacidad).
# `detrás` es un token o una tupla de tokens compuestos de abajo arriba: `("columna", "velo")`
# es el velo encima de la columna, encima del fondo. Así se miden también las opacidades de los
# velos, que era lo que se colaba: un hover aclara o ensucia la base y el texto que va encima
# deja de leerse aunque medido contra la superficie parezca que sí.
# `opacidad` es la del texto, la de un CSS `opacity` (dim-label al 55 %, una pista al 75 %); se
# compone el color con esa opacidad sobre lo de debajo antes de medir. Sin ella, un texto
# atenuado daba por bueno un contraste que no tiene: es el 4,1:1 que enseñó la crítica.
# 4,5 es texto normal; 3, un icono o un trazo que no hace falta leer letra a letra.
CONTRASTES = (
    ("texto", "fondo", 4.5, "texto sobre la ventana"),
    ("texto", "superficie", 4.5, "texto de una carta"),
    ("texto", "superficie-alta", 4.5, "texto de una carta con el ratón encima"),
    ("texto", "columna", 4.5, "texto sobre una columna vacía"),
    ("tenue", "fondo", 4.5, "dato secundario sobre la ventana"),
    ("tenue", "superficie", 4.5, "dato secundario en una carta"),
    ("tenue", "superficie-alta", 4.5, "dato secundario en una carta con el ratón encima"),
    ("tenue", "columna", 4.5, "pista de un vacío"),
    ("tenue", ("superficie", "velo-sutil"), 4.5, "fila de una lista con el ratón encima"),
    ("tenue", ("columna", "velo"), 4.5, "chip de la banda con el ratón encima"),
    ("texto", ("fondo", "velo-fuerte"), 4.5, "botón plano con el ratón encima"),
    ("texto-chip", "superficie", 4.5, "chip de agente"),
    ("tenue-hondo", "columna", 3.0, "icono de un vacío"),
    ("senal", "fondo", 4.5, "título en foco sobre la ventana"),
    ("senal", "senal-suave", 4.5, "proyecto elegido en la banda; prueba en verde"),
    ("sobre-senal", "senal", 4.5, "número del contador en foco"),
    ("ambar", "ambar-fondo", 4.5, "banda de avisos"),
    ("ambar", "fondo", 4.5, "título de una anotación detenida"),
    ("ambar", "ambar-velo", 4.5, "prueba en rojo en la revisión de una entrega"),
    ("texto", "senal-suave", 4.5, "línea añadida de un diff"),
    ("texto", "ambar-velo", 4.5, "línea quitada de un diff"),
)

_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB = re.compile(r"^rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*"
                  r"(?:,\s*(0|1|0?\.\d+|1\.0+)\s*)?\)$")


class TemaRoto(Exception):
    """El tema no existe o no se puede usar. `problemas` dice qué tiene, uno por línea."""

    def __init__(self, mensaje, problemas=()):
        super().__init__(mensaje)
        self.problemas = list(problemas)


def carpeta_propia():
    """Donde van los temas que crea un agente: junto a la config que manda.

    Junto a `COTEJO_CONFIG` si está definida, que es lo que deja a las pruebas (y a quien
    pruebe) trabajar en una carpeta de mentira sin tocar los temas de verdad.
    """
    desde_entorno = os.environ.get("COTEJO_CONFIG")
    base = Path(desde_entorno).expanduser().parent if desde_entorno else configuracion.nueva().parent
    return base / "temas"


def color(texto):
    """`(r, g, b, a)` con r, g, b en 0-255 y a en 0-1, o None si no es un color que se acepte."""
    if not isinstance(texto, str):
        return None
    texto = texto.strip()
    if _HEX.match(texto):
        cifras = texto[1:]
        if len(cifras) == 3:
            cifras = "".join(c * 2 for c in cifras)
        r, g, b = (int(cifras[i:i + 2], 16) for i in (0, 2, 4))
        a = int(cifras[6:8], 16) / 255 if len(cifras) == 8 else 1.0
        return r, g, b, a
    encontrado = _RGB.match(texto)
    if encontrado:
        r, g, b = (int(x) for x in encontrado.group(1, 2, 3))
        if max(r, g, b) > 255:
            return None
        alfa = encontrado.group(4)
        if texto.startswith("rgb(") and alfa is not None:
            return None
        return r, g, b, float(alfa) if alfa is not None else 1.0
    return None


def componer(delante, detras):
    """El color que se ve al poner `delante` (con su alfa) sobre `detras` (opaco)."""
    a = delante[3]
    return tuple(delante[i] * a + detras[i] * (1 - a) for i in range(3)) + (1.0,)


def luminancia(rgb):
    def canal(valor):
        valor /= 255
        return valor / 12.92 if valor <= 0.03928 else ((valor + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(x) for x in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(uno, otro):
    claro, oscuro = sorted((luminancia(uno), luminancia(otro)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


def _base_de(leidos, detras, fondo):
    """Lo que se ve detrás: el token (o los tokens, de abajo arriba) compuesto sobre el fondo."""
    if isinstance(detras, (tuple, list)):
        base = fondo
        for capa in detras:
            base = componer(leidos[capa], base)
        return base
    return componer(leidos[detras], fondo)


def _entrada(entrada):
    """`(delante, detrás, mínimo, dónde, opacidad)`, con opacidad 1 si no la dice."""
    delante, detras, minimo, donde = entrada[:4]
    return delante, detras, minimo, donde, (entrada[4] if len(entrada) > 4 else 1.0)


def nombre_de(detras):
    """El detrás como se lee en un mensaje: `velo sobre columna`."""
    if isinstance(detras, (tuple, list)):
        return " sobre ".join(reversed(detras))
    return detras


def problemas_de(datos):
    """Qué tiene un tema, sin tocar nada: `(errores, medidas)`.

    `errores` es lo que lo deja inservible (falta un color, sobra una clave, un valor que no es
    un color). `medidas` es cada par de CONTRASTES con su cifra y si llega (`ok`): van todas y
    no solo las que fallan, porque quien ajusta un tema necesita saber también cuánto margen le
    queda a lo que pasa. Un contraste que no llega también impide usarlo: un tema que no se lee
    es un tema roto aunque el JSON esté perfecto.
    """
    errores = []
    if not isinstance(datos, dict):
        return ["El tema tiene que ser un objeto JSON"], []
    if not isinstance(datos.get("nombre"), str) or not datos.get("nombre", "").strip():
        errores.append("Falta «nombre»: el texto que se ve en el selector")
    if datos.get("esquema") not in ESQUEMAS:
        errores.append(f"«esquema» vale {datos.get('esquema')!r}: tiene que ser "
                       f"{' o '.join(ESQUEMAS)}")
    sobran = sorted(set(datos) - {"nombre", "descripcion", "esquema", "colores"})
    if sobran:
        errores.append(f"Claves que un tema no lleva: {', '.join(sobran)}")
    colores = datos.get("colores")
    if not isinstance(colores, dict):
        return errores + ["Falta «colores»: un objeto con un valor por cada token"], []
    faltan = [t for t in TOKENS if t not in colores]
    if faltan:
        errores.append(f"Faltan colores: {', '.join(faltan)}")
    extra = sorted(set(colores) - set(TOKENS))
    if extra:
        errores.append(f"Colores que el board no usa: {', '.join(extra)}")
    leidos = {}
    for token in TOKENS:
        if token not in colores:
            continue
        valor = color(colores[token])
        if valor is None:
            errores.append(f"«{token}» vale {colores[token]!r}, que no es un color: "
                           f"#RRGGBB, #RRGGBBAA, rgb() o rgba()")
        else:
            leidos[token] = valor
    if "fondo" in leidos and leidos["fondo"][3] < 1:
        errores.append("«fondo» tiene que ser opaco: todo lo translúcido se compone sobre él")
    if errores:
        return errores, []
    fondo = leidos["fondo"]
    medidas = []
    for entrada in CONTRASTES:
        delante, detras, minimo, donde, opacidad = _entrada(entrada)
        base = _base_de(leidos, detras, fondo)
        tinta = leidos[delante]
        if opacidad < 1:
            tinta = tinta[:3] + (tinta[3] * opacidad,)
        cifra = contraste(componer(tinta, base), base)
        medidas.append({"delante": delante, "detras": detras, "donde": donde,
                        "contraste": round(cifra, 2), "minimo": minimo, "ok": cifra >= minimo})
    return errores, medidas


def fallos(medidas):
    """Las medidas que no llegan, dichas como se leen: qué sobre qué, cuánto y cuánto pide."""
    return [f"{m['delante']} sobre {nombre_de(m['detras'])} ({m['donde']}): {m['contraste']}:1, "
            f"pide {m['minimo']}:1" for m in medidas if not m["ok"]]


def _leer(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise TemaRoto(f"No pude leer {ruta}: {error}", [str(error)]) from error


def disponibles():
    """Los temas que hay, por id: `{id: (ruta, de_fabrica)}`.

    Uno propio no tapa a uno de fábrica: si se llama igual, gana el de fábrica. Si no, un tema
    roto con el nombre `oscuro` dejaría sin salida a quien lo eligió, que es justo el tema al
    que se vuelve cuando el elegido falla.
    """
    hay = {}
    if carpeta_propia().is_dir():
        for ruta in sorted(carpeta_propia().glob("*.json")):
            if NOMBRE_RE.match(ruta.stem):
                hay[ruta.stem] = (ruta, False)
    for ruta in sorted(DATOS.glob("*.json")):
        hay[ruta.stem] = (ruta, True)
    return hay


def cargar(ident):
    """El tema listo para usar, o `TemaRoto` con lo que tiene mal."""
    hay = disponibles()
    if ident not in hay:
        raise TemaRoto(f"No hay ningún tema «{ident}»",
                       [f"Los que hay: {', '.join(sorted(hay))}"])
    datos = _leer(hay[ident][0])
    errores, medidas = problemas_de(datos)
    if errores or fallos(medidas):
        raise TemaRoto(f"El tema «{ident}» no se puede usar", errores + fallos(medidas))
    return datos


def elegido(datos=None):
    """El id del tema que dice la config, o el de defecto si no dice ninguno."""
    datos = configuracion.cargar() if datos is None else datos
    valor = datos.get("tema")
    return valor if isinstance(valor, str) and valor else DEFECTO


def css(tema):
    """El bloque `:root` con los colores del tema, para ponerlo delante del CSS del board."""
    lineas = [f"  --k-{token}: {tema['colores'][token].strip()};" for token in TOKENS]
    return ":root {\n" + "\n".join(lineas) + "\n}\n"


# --- los verbos ---------------------------------------------------------------
#
#     temas                          los que hay, cuál está elegido y si se pueden usar
#     temas comprobar <id|archivo>   si se puede usar, con cada contraste medido
#     temas nuevo <id> [--desde X]   copia uno para editarlo, junto a la config
#     temas usar <id>                elegirlo (solo si `comprobar` pasa)
#
# No hay verbo para editar un tema: se edita el JSON, que es un archivo del agente y no una
# nota de nadie. Lo que sí pasa siempre por aquí es comprobarlo, y elegirlo.


def resumen(ident, ruta, de_fabrica, actual):
    uno = {"id": ident, "de_fabrica": de_fabrica, "elegido": ident == actual, "ruta": str(ruta)}
    try:
        datos = _leer(ruta)
        errores, medidas = problemas_de(datos)
        problemas = errores + fallos(medidas)
    except TemaRoto as error:
        datos, problemas = {}, [str(error)]
    if isinstance(datos, dict):
        uno["nombre"] = datos.get("nombre") or ident
        uno["esquema"] = datos.get("esquema")
    uno["ok"] = not problemas
    if problemas:
        uno["problemas"] = problemas
    return uno


def cmd_temas(args):
    from .cli import ESQUEMA, imprimir

    datos = configuracion.cargar()
    actual = elegido(datos)
    lista = [resumen(i, r, f, actual) for i, (r, f) in sorted(disponibles().items())]
    respuesta = {"esquema": ESQUEMA, "elegido": actual, "temas": lista,
                 "carpeta": str(carpeta_propia()),
                 "nota_para_el_agente": "Un tema nuevo se crea con `temas nuevo <id>`, se edita "
                                        "su JSON y se comprueba con `temas comprobar <id>`. En "
                                        "CotejoBoard solo se elige."}
    if actual not in disponibles():
        respuesta["avisos"] = [f"La config elige «{actual}», que no existe: el board usa "
                               f"«{DEFECTO}»."]
    imprimir(respuesta)
    return 0


def cmd_temas_comprobar(args):
    """Por id o por ruta: así se puede comprobar un archivo antes de dejarlo en su carpeta."""
    from .cli import ESQUEMA, ErrorCLI, imprimir

    cual = args.tema
    hay = disponibles()
    if cual in hay:
        ruta = hay[cual][0]
    elif cual.endswith(".json") or "/" in cual:
        ruta = Path(cual).expanduser()
    else:
        raise ErrorCLI(f"No hay ningún tema «{cual}»",
                       f"Los que hay: {', '.join(sorted(hay))}. También vale la ruta a un .json.")
    try:
        datos = _leer(ruta)
    except TemaRoto as error:
        raise ErrorCLI(str(error), "Arregla el JSON y repite.") from error
    errores, medidas = problemas_de(datos)
    ok = not errores and not fallos(medidas)
    respuesta = {"esquema": ESQUEMA, "ok": ok, "ruta": str(ruta), "errores": errores,
                 "contrastes": medidas}
    avisos = []
    tapado = (ruta.parent.resolve() == carpeta_propia().resolve() and ruta.stem in hay
              and hay[ruta.stem][1])
    if tapado:
        avisos.append(f"Hay uno de fábrica que se llama «{ruta.stem}» y gana: este no se va a "
                      f"ver. Cámbiale el nombre al archivo.")
    # Aviso y no error: sin descripción el tema funciona, pero en el selector sale sin
    # subtítulo, y quien elige no sabe para qué es.
    if isinstance(datos, dict) and not str(datos.get("descripcion") or "").strip():
        avisos.append("«descripcion» está vacía: en el selector sale sin subtítulo. Escribe "
                      "una frase que diga cómo se ve.")
    if avisos:
        respuesta["avisos"] = avisos
    if errores:
        respuesta["salida"] = "Arregla lo de «errores» y repite."
    elif not ok:
        respuesta["salida"] = ("Sube el contraste de los pares con \"ok\": false —casi siempre es "
                               "oscurecer o aclarar el de delante— y repite.")
    else:
        respuesta["salida"] = f"Se puede usar: `temas usar {ruta.stem}`, o elegirlo en CotejoBoard."
    imprimir(respuesta)
    return 0 if ok else 3


def cmd_temas_nuevo(args):
    """Copia un tema en la carpeta propia para editarlo. No pisa uno que ya exista."""
    from .cli import ESQUEMA, ErrorCLI, imprimir

    ident = args.id
    if not NOMBRE_RE.match(ident):
        raise ErrorCLI(f"«{ident}» no sirve de id", "Minúsculas, números, guion o guion bajo.")
    hay = disponibles()
    if ident in hay:
        raise ErrorCLI(f"Ya hay un tema «{ident}» en {hay[ident][0]}",
                       "Edita ese, o elige otro id. No se escribió nada.")
    if args.desde not in hay:
        raise ErrorCLI(f"No hay ningún tema «{args.desde}» del que partir",
                       f"Los que hay: {', '.join(sorted(hay))}.")
    base = _leer(hay[args.desde][0])
    nuevo = {"nombre": args.nombre or ident.replace("-", " ").replace("_", " ").capitalize(),
             "descripcion": "", "esquema": base.get("esquema", "oscuro"),
             "colores": dict(base.get("colores") or {})}
    destino = carpeta_propia() / f"{ident}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(destino, "x", encoding="utf-8") as archivo:
            archivo.write(json.dumps(nuevo, indent=2, ensure_ascii=False) + "\n")
    except FileExistsError as error:
        raise ErrorCLI(f"Ya existe {destino}", "Edita ese, o elige otro id.") from error
    imprimir({"esquema": ESQUEMA, "cambio": True, "id": ident, "ruta": str(destino),
              "desde": args.desde, "tokens": TOKENS,
              "contrastes": [{"delante": d, "detras": t, "minimo": m, "donde": w,
                              "opacidad": o}
                             for d, t, m, w, o in (_entrada(e) for e in CONTRASTES)],
              "nota_para_el_agente": f"Edita «colores» (y «esquema» si pasa de oscuro a claro) "
                                     f"en {destino}; `tokens` dice para qué es cada uno. Escribe "
                                     f"también «descripcion»: una frase, es el subtítulo que se "
                                     f"ve en el selector. Luego "
                                     f"`temas comprobar {ident}`: no se puede elegir hasta que "
                                     f"pase."})
    return 0


def cmd_temas_usar(args):
    """Lo elige, solo si se puede usar: elegir uno roto dejaría el board en el de defecto."""
    from .cli import ESQUEMA, ErrorCLI, imprimir
    from .conexion import _config_o_error

    datos = _config_o_error()
    try:
        cargar(args.id)
    except TemaRoto as error:
        raise ErrorCLI(str(error) + (": " + "; ".join(error.problemas) if error.problemas else ""),
                       f"`temas comprobar {args.id}` dice qué tiene. El elegido sigue siendo "
                       f"«{elegido(datos)}».") from error
    if elegido(datos) == args.id and "tema" in datos:
        imprimir({"esquema": ESQUEMA, "cambio": False, "elegido": args.id})
        return 0
    ruta = configuracion.guardar({**datos, "tema": args.id})
    imprimir({"esquema": ESQUEMA, "cambio": True, "elegido": args.id, "ruta": str(ruta),
              "nota_para_el_agente": "Si CotejoBoard está abierto, cambia solo."})
    return 0


def anadir(sub):
    temas = sub.add_parser("temas", help="Los colores de CotejoBoard: los que hay y cuál se usa")
    temas.set_defaults(funcion=cmd_temas)
    acciones = temas.add_subparsers(dest="accion")

    comprobar = acciones.add_parser("comprobar", help="Si un tema se puede usar, con cada contraste")
    comprobar.add_argument("tema", help="Su id, o la ruta a un .json")
    comprobar.set_defaults(funcion=cmd_temas_comprobar)

    nuevo = acciones.add_parser("nuevo", help="Copiar uno para editarlo, junto a la config")
    nuevo.add_argument("id", help="Minúsculas, números, guion: es el nombre del archivo")
    nuevo.add_argument("--desde", default=DEFECTO, help="El tema del que partir (oscuro)")
    nuevo.add_argument("--nombre", help="El texto que se ve en el selector")
    nuevo.set_defaults(funcion=cmd_temas_nuevo)

    usar = acciones.add_parser("usar", help="Elegirlo (solo si `comprobar` pasa)")
    usar.add_argument("id")
    usar.set_defaults(funcion=cmd_temas_usar)
