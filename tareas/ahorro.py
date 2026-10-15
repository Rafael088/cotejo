"""Qué costó de verdad enterarse por la CLI, y qué habría costado leer las notas enteras.

Las dos mitades del número se **miden**, no se estiman, y por eso este archivo existe en vez
de una frase en el README:

- lo que costó es el tamaño de lo que la CLI devolvió, que es exactamente lo que el agente se
  lleva al contexto;
- lo que habría costado es el tamaño de las notas que la fuente tuvo que leer para contestar,
  que ya las leyó y las tiene en la mano.

Lo único que **no** se mide es el supuesto de en medio —que sin Cotejo el agente habría leído
esas notas enteras— y por eso viaja dentro del dato, en la clave `supuesto`, y sale escrito
junto al número en el board. Un ahorro que esconde su supuesto detrás de un total redondo es
una medalla, no una medida.

Tres decisiones que vienen de la nota del proyecto:

- **Fuera de la barra.** Un número permanente es el FOMO que la app evita; el acento se
  reserva para lo que exige una acción. Esto se consulta cuando se quiere.
- **Archivo propio, no `bitacora.jsonl`.** La bitácora es historial, se lee con `tail` y la
  consulta el board en cada repintado: una línea por lectura la llenaría de ruido y
  encarecería justo el camino que este medidor dice abaratar. Aquí solo hay totales, y se
  reemplazan atómicamente.
- **Por día, no por sesión.** El board enseña lo de hoy y el total va en la ayuda. Cotejo no
  sabe desde qué sesión lo llama un agente —Claude Code, OpenCode y Codex la nombran distinto,
  o no la nombran—, y la fecha no hay que adivinarla. Un total que solo crece es otra medalla;
  lo de hoy dice algo de cómo se está trabajando.
- **Contar no puede costar.** Nada de aquí abre una nota: la fuente ya las leyó y solo se le
  pregunta cuánto pesaba lo leído. Si medir el ahorro encareciera una lectura, el medidor se
  comería lo que mide.

Se cuenta en caracteres, que es lo que hay sin volver a tocar nada, y los tokens salen de
dividir. La razón entre las dos mitades —«ocho veces más barato»— no depende del divisor, y
por eso es ella la que se enseña grande.

No importa GTK, como `estado.py`, `cli.py` y `bitacora.py`.
"""

import json
import os
import time

from . import rutas

ARCHIVO = rutas.estado() / "ahorro.json"

# Las claves de este archivo son un contrato como las de `estado.json`: se agregan, no se
# renombran ni se quitan.
ESQUEMA = 1

# Cuántos caracteres pesa un token, más o menos, en texto en español. Es una aproximación
# declarada, no una medición: por eso los caracteres se guardan tal cual y la conversión se
# hace al enseñarlos, donde se puede decir que es aproximada.
CARACTERES_POR_TOKEN = 3.6

SUPUESTO = ("Lo medido son los caracteres que devolvió la CLI y los que pesaban las notas que "
            "hubo que leer para contestar. Lo supuesto, y no medido, es que sin Cotejo habrías "
            "leído esas notas enteras.")

VACIO = {"esquema": ESQUEMA, "lecturas": 0, "devuelto": 0, "leido": 0, "desde": 0, "dias": {}}

# Cuántos días se guardan por separado. Más atrás solo queda el total, que es lo único que se
# enseña de antes de hoy: guardar cada día para siempre haría crecer sin fin un archivo que se
# reescribe entero en cada lectura.
DIAS_GUARDADOS = 30


def hoy():
    """La fecha local de hoy, «2026-09-26». Local y no UTC: el día es el de quien trabaja."""
    return time.strftime("%Y-%m-%d")


def leer():
    """Los totales acumulados. Si el archivo no está o está roto, se empieza de cero.

    Que un archivo ilegible valga como «todavía no hay nada» es aceptable justo aquí y no lo
    sería en el vault: esto no es trabajo de nadie, es la cuenta de un ahorro. Perderla no
    pierde ninguna tarea.
    """
    try:
        datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(VACIO)
    if not isinstance(datos, dict):
        return dict(VACIO)
    leidos = {clave: datos.get(clave, VACIO[clave]) for clave in VACIO}
    if not isinstance(leidos["dias"], dict):
        leidos["dias"] = {}
    return {**VACIO, **leidos}


def anotar(devuelto, leido):
    """Suma una lectura del camino barato. Devuelve los totales como quedaron.

    Falla en silencio igual que la bitácora: el agente ya tiene su respuesta impresa, y no
    poder apuntar cuánto se ahorró no es motivo para estropearle la llamada.

    Con `leido` en cero no se cuenta nada: es lo que devuelve una fuente que no vive en
    archivos, y comparar contra cero daría un ahorro infinito, que es la clase de número que
    esta tarea existe para no inventar.
    """
    if leido <= 0 or devuelto <= 0:
        return leer()
    datos = leer()
    datos["lecturas"] += 1
    datos["devuelto"] += int(devuelto)
    datos["leido"] += int(leido)
    datos["desde"] = datos["desde"] or int(time.time())
    dias = datos["dias"] = dict(datos["dias"])
    dia = dias[hoy()] = {"lecturas": 0, "devuelto": 0, "leido": 0, **dias.get(hoy(), {})}
    dia["lecturas"] += 1
    dia["devuelto"] += int(devuelto)
    dia["leido"] += int(leido)
    for viejo in sorted(dias)[:-DIAS_GUARDADOS]:
        del dias[viejo]
    try:
        ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
        temporal = ARCHIVO.with_name(f".{ARCHIVO.name}.tmp")
        temporal.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        os.replace(temporal, ARCHIVO)
    except OSError:
        pass
    return datos


def derivar(parte):
    """La razón y los tokens de unos totales, o None si no hay ninguna lectura que contar."""
    if not parte.get("lecturas") or not parte.get("devuelto"):
        return None
    return {
        "lecturas": parte["lecturas"],
        "devuelto": parte["devuelto"],
        "leido": parte["leido"],
        "razon": round(parte["leido"] / parte["devuelto"], 1),
        "tokens_devueltos": int(parte["devuelto"] / CARACTERES_POR_TOKEN),
        "tokens_ahorrados": int((parte["leido"] - parte["devuelto"]) / CARACTERES_POR_TOKEN),
    }


def resumen(datos=None):
    """Los totales con lo derivado ya calculado, y lo de hoy en `hoy`; o None si todavía no
    hay ninguna lectura.

    Devolver None y no un cero es a propósito: sin lecturas no hay nada que decir, y el board
    prefiere no enseñar una línea a enseñar «1× más barato» el primer día. Por lo mismo `hoy`
    es None mientras hoy no haya habido ninguna.

    Los días sueltos no salen: los pide un agente por la CLI, y treinta días de números que no
    ha pedido serían justo el gasto que este medidor cuenta.
    """
    datos = leer() if datos is None else datos
    total = derivar(datos)
    if total is None:
        return None
    return {
        **{clave: valor for clave, valor in datos.items() if clave != "dias"},
        **total,
        "hoy": derivar(datos["dias"].get(hoy(), {})),
        "caracteres_por_token": CARACTERES_POR_TOKEN,
        "supuesto": SUPUESTO,
    }
