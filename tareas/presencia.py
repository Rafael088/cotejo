"""Dónde se para el dot en el board y en qué estado (D5), sin GTK.

El planning del dot, sección 3, dice qué hace el dot en el board; esto lo traduce a una pequeña
máquina de estados y a unas cuentas de geometría que se prueban sin pantalla
(`pruebas/test_presencia.py`). En `app/capa_dot.py` queda solo el cableado: el overlay, leer los
rectángulos de los widgets y mover el dot.

| Estado      | Cuándo                                          | Dónde se para                          |
| ----------- | ----------------------------------------------- | -------------------------------------- |
| `idle`      | nada en juego                                   | en el pie, a la derecha del maestro    |
| `trabaja`   | hay cartas en Haciéndola                        | en la primera (Alt+← → la cambia)      |
| `comprobar` | hay cartas en Para comprobar                    | al borde de esa columna                |
| `celebra`   | una persona pasa una tarea a Finalizada         | sobre el riel de Finalizada, un ciclo  |
| `falla`     | una persona devuelve una tarea de Para comprobar| sobre la carta devuelta, un ciclo      |

Los que duran ganan por prioridad (`comprobar` › `trabaja` › `idle`); los de un momento se ponen
encima durante un ciclo de su animación (`ciclo`, sacado de `dot.PISTAS`) y al acabar vuelve el
que duraba. `piensa` no está: se quedó en el laboratorio. Que la fuente no responda tampoco es
`falla`: eso lo dice la banda de avisos.

Las cartas se destruyen en cada repintado, así que un ancla nunca guarda un widget: guarda el
id de la tarea (`fila.clave`) y la columna a la que caer si la carta no está a la vista.
"""

from collections import namedtuple

from . import dot

TALLA = 56                     # el dot del board (la talla mediana: sin brillo)
ENTRADA_S = dot.ENTRADA.duracion   # la entrada al pie; después sale a su ancla
EN_CURSO = "en-curso"
POR_COMPROBAR = "por-validar"
FINALIZADA = "hecha"

DURADEROS = ("comprobar", "trabaja", "idle")   # en orden de prioridad
MOMENTOS = ("celebra", "falla")

# Un ancla: `sitio` es pie, carta, columna o riel; `clave`, el id de la tarea (en las cartas);
# `columna`, a dónde ir si la carta no se ve (un filtro, un scroll que la sacó de la lista).
Ancla = namedtuple("Ancla", "sitio clave columna", defaults=(None, None))
PIE = Ancla("pie")
RIEL = Ancla("riel", columna=FINALIZADA)
COLUMNA_COMPROBAR = Ancla("columna", columna=POR_COMPROBAR)

Vista = namedtuple("Vista", "estado ancla etiqueta hasta")

NOMBRES_COLUMNA = {"pendiente": "Pendiente", EN_CURSO: "Haciéndola",
                   POR_COMPROBAR: "Para comprobar", FINALIZADA: "Finalizada"}


def ciclo(estado):
    """Lo que dura un ciclo de la animación del estado, en segundos: la pista más larga de
    `dot.PISTAS` (celebra 2,4 s, falla 5,2 s). Así no hay un segundo número que se desfase."""
    return max(p.duracion for p in dot.PISTAS[estado].values() if p is not None)


def _tareas(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


def etiqueta(estado, en_curso=0, por_comprobar=0, columna=None):
    """Lo que dice el lector de pantalla del dot en cada estado."""
    if estado == "comprobar":
        if por_comprobar == 1:
            return "Cotejo: 1 tarea espera que la compruebes"
        return f"Cotejo: {por_comprobar} tareas esperan que las compruebes"
    if estado == "trabaja":
        return f"Cotejo: {_tareas(en_curso, 'tarea', 'tareas')} en curso"
    if estado == "celebra":
        return "Cotejo: una tarea pasó a Finalizada"
    if estado == "falla":
        return f"Cotejo: devolviste una tarea a {NOMBRES_COLUMNA.get(columna, columna)}"
    return "Cotejo: nada en juego"


class Presencia:
    """Qué hace el dot ahora. Sin reloj propio: quien llama pasa `ahora` en segundos.

    `ver` se llama en cada repintado con lo que hay en Haciéndola y en Para comprobar;
    `reaccionar` cuando pasa algo de un momento; `pasar` con Alt+← →; `vigente` dice el
    estado, el ancla y la etiqueta de este instante.
    """

    def __init__(self):
        self.en_curso = []         # ids de las cartas de Haciéndola, en el orden en que se ven
        self.por_comprobar = 0     # cartas en Para comprobar (tareas y decisiones)
        self.elegida = None        # la carta en curso a la que se pasó con Alt+← →
        self.momento = None        # Vista de celebra o falla mientras dura

    def ver(self, en_curso, por_comprobar):
        self.en_curso = list(en_curso)
        self.por_comprobar = por_comprobar
        if self.elegida not in self.en_curso:
            self.elegida = None    # salió de Haciéndola: vuelve a la primera

    def carta_en_curso(self):
        """La carta de `trabaja`: la elegida con Alt+← → o, si no, la primera."""
        if self.elegida is not None:
            return self.elegida
        return self.en_curso[0] if self.en_curso else None

    def pasar(self, paso):
        """Alt+← → : el dot a la carta en curso anterior (−1) o siguiente (+1), sin dar la
        vuelta. Devuelve si cambió de carta."""
        actual = self.carta_en_curso()
        if actual is None:
            return False
        indice = self.en_curso.index(actual) + paso
        if not 0 <= indice < len(self.en_curso):
            return False
        self.elegida = self.en_curso[indice]
        return True

    def reaccionar(self, estado, ancla, ahora, texto=None):
        """Pone encima un estado de un momento durante un ciclo. Uno nuevo pisa al anterior."""
        if estado not in MOMENTOS:
            raise ValueError(f"{estado} no es de un momento (son {', '.join(MOMENTOS)})")
        self.momento = Vista(estado, ancla, texto or etiqueta(estado, columna=ancla.columna),
                             ahora + ciclo(estado))

    def celebrar(self, ahora):
        self.reaccionar("celebra", RIEL, ahora)

    def fallar(self, clave, columna, ahora):
        self.reaccionar("falla", Ancla("carta", clave, columna), ahora)

    def duradero(self):
        """El que gana entre los que duran: comprobar › trabaja › idle."""
        if self.por_comprobar:
            return Vista("comprobar", COLUMNA_COMPROBAR,
                         etiqueta("comprobar", por_comprobar=self.por_comprobar), None)
        carta = self.carta_en_curso()
        if carta is not None:
            return Vista("trabaja", Ancla("carta", carta, EN_CURSO),
                         etiqueta("trabaja", en_curso=len(self.en_curso)), None)
        return Vista("idle", PIE, etiqueta("idle"), None)

    def vigente(self, ahora):
        if self.momento is not None and ahora < self.momento.hasta:
            return self.momento
        self.momento = None
        return self.duradero()


# --- dónde cae el dot ---------------------------------------------------------------------------
#
# Rectángulos (x, y, ancho, alto) en coordenadas del overlay. El dot se posa al margen, nunca
# encima del texto: en las cartas y en la columna, sentado en el borde de arriba, a la izquierda
# del menú ⋮ o del contador; en el riel, encima del ícono; en el pie, en el hueco entre la barra
# del maestro y Volver, pegado a la barra (Volver puede estar apagado).

HUECO_PIE = 16          # entre el borde derecho de la barra del maestro y el dot
MARGEN_MENU = 44        # lo que ocupa el ⋮ de la carta a la derecha, con su aire
MARGEN_CONTADOR = 44    # lo que ocupa el contador de la columna a la derecha
ICONO_RIEL = 22         # el ícono del riel de Finalizada
HUECO_RIEL = 10         # entre el dot y el ícono del riel


def en_pie(barra, pie, talla=TALLA):
    x, _y, ancho, _alto = barra
    _px, py, _pancho, palto = pie
    return x + ancho + HUECO_PIE, py + (palto - talla) / 2


def en_carta(carta, talla=TALLA):
    x, y, ancho, _alto = carta
    return x + ancho - MARGEN_MENU - talla, y - talla / 2


def a_la_vista(carta, vista, talla=TALLA):
    """¿Se ve el borde de arriba de la carta dentro de la lista de su columna (`vista`, el
    rectángulo del scroll)? Con medio dot de margen por arriba y por abajo: el dot se sienta en
    ese borde, y una carta que asoma apenas por abajo no sirve de ancla."""
    _x, y, _ancho, _alto = carta
    _vx, vy, _vancho, valto = vista
    return vy - talla / 2 <= y <= vy + valto - talla / 2


def en_columna(columna, talla=TALLA):
    x, y, ancho, _alto = columna
    return x + ancho - MARGEN_CONTADOR - talla, y - talla / 2


def en_riel(riel, talla=TALLA):
    x, y, ancho, alto = riel
    return x + (ancho - talla) / 2, y + alto / 2 - ICONO_RIEL / 2 - HUECO_RIEL - talla


def de_camino(desde, hasta, t):
    """Dónde va el dot a los `t` segundos de salir de `desde` hacia `hasta`, con `VIAJE`."""
    p = dot.viaje(t)
    return desde[0] + (hasta[0] - desde[0]) * p, desde[1] + (hasta[1] - desde[1]) * p


def viaje_terminado(t):
    return t >= dot.VIAJE.duracion
