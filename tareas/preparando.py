"""Lo que enseña la pantalla Preparando (v1.3.0, cotejo-hiifrz), sin GTK.

La pantalla del board (`tareas/app/preparando.py`) solo pinta; todo lo que se puede decidir sin
pantalla está aquí para probarlo sin ella. Junta tres cosas que ya existen y no las repite:

- el estado de la preparación (`tareas/preparacion.py`: `preparando`, `colgado`, `fallo`, `listo`,
  y `visto` / `en-terminal` cuando la persona ya lo atendió),
- los cinco pasos con su estado y su tiempo (`tareas/progreso.py`, que lee la bitácora y los
  `PASOS` de `tareas/inicio.py`),
- las acciones de rescate (`enrutador/preparar.py`: `reintentar`, `abrir_en_terminal`), que
  la pantalla llama; aquí solo se dice cuándo se ofrecen.

`Preparando(id)` es lo que la pantalla guarda: cada `refrescar()` (una vez por segundo, mientras
se ve) relee el registro, lee solo lo nuevo de la bitácora y devuelve una `Vista` ya en llano.
Nada de esto escribe.
"""

import time
from dataclasses import dataclass, field

from . import preparacion, progreso

SUELE_TARDAR = "suele tardar 2 a 4 minutos"
SIMBOLOS = {progreso.PENDIENTE: "○", progreso.EN_CURSO: "◐", progreso.HECHO: "✓",
            progreso.FALLO: "✕"}


def tiempo(segundos):
    """Un reloj: 0:00, 2:15, 1:02:03."""
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, seg = divmod(resto, 60)
    return f"{horas}:{minutos:02d}:{seg:02d}" if horas else f"{minutos}:{seg:02d}"


def duracion(segundos):
    """Lo que tardó un paso, corto: «12 s», «1 min 5 s», «2 min»."""
    if segundos is None:
        return ""
    segundos = max(0, int(segundos))
    if segundos < 60:
        return f"{segundos} s"
    minutos, seg = divmod(segundos, 60)
    return f"{minutos} min" + (f" {seg} s" if seg else "")


@dataclass
class Vista:
    """Todo lo que la pantalla pinta, ya en texto."""
    id: str = ""
    proyecto: str = ""
    cliente: str = ""
    situacion: str = preparacion.PREPARANDO   # el `estado` de la preparación
    eyebrow: str = ""
    titulo: str = ""
    reloj: str = ""
    pasos: list = field(default_factory=list)   # {titulo, estado, simbolo, tiempo, detalle}
    mensaje: str = ""                           # el porqué del fallo, o la nota de «en terminal»
    acciones: tuple = ()                        # "reintentar" y/o "abrir_en_terminal"
    puede_revisar: bool = False                 # «Revisar el plan»
    registro: str = ""                          # «Ver lo que hace el agente»


def _nombre_del_agente(cliente):
    try:
        from enrutador import clientes
        return clientes.CLIENTES[cliente].titulo or cliente
    except (ImportError, KeyError, AttributeError, TypeError):
        return cliente or "Tu agente"


def _linea_de_bitacora(texto):
    import json
    try:
        d = json.loads(texto)
    except ValueError:
        return texto
    partes = [str(d.get("operacion", "")), str(d.get("tipo", ""))]
    nombre = d.get("titulo") or d.get("proyecto") or ""
    return "$ cotejo " + " ".join(p for p in partes + [str(nombre)] if p)


def texto_del_registro(crudo):
    """El registro desplegable: lo que Cotejo vio hacer al agente y el final de su salida."""
    lineas = [_linea_de_bitacora(t) for t in crudo.get("bitacora", [])]
    if crudo.get("log"):
        lineas += ["", "--- salida del agente ---", crudo["log"]]
    return "\n".join(lineas) if lineas else "Todavía no hay nada que enseñar."


class Preparando:
    """Sigue una preparación: `refrescar()` devuelve la `Vista` de ese momento."""

    def __init__(self, ident, archivo_bitacora=None):
        self.id = ident
        self.archivo = archivo_bitacora
        self.seguimiento = None
        self.ts = None

    def _seguir(self, registro):
        # Un reintento relanza con el mismo id y un `ts` nuevo: se empieza a contar de cero.
        if self.seguimiento is None or registro.get("ts") != self.ts:
            self.ts = registro.get("ts")
            self.seguimiento = progreso.de_preparacion(registro, self.archivo)

    def refrescar(self, ahora=None):
        ahora = int(ahora if ahora is not None else time.time())
        registro = preparacion.leer(self.id)
        if registro is None:
            return Vista(id=self.id, situacion=preparacion.FALLO, titulo="No encuentro esta preparación",
                         mensaje=f"No hay ninguna preparación «{self.id}».")
        self._seguir(registro)
        self.seguimiento.avanzar()
        e = preparacion.estado(registro, ahora)
        return vista(e, registro, self.seguimiento, ahora)


def vista(e, registro, seguimiento, ahora):
    """La `Vista` de un estado (`preparacion.estado`) con su registro y su seguimiento."""
    situacion = e["estado"]
    # Para los pasos: «visto» es que ya se terminó; en una terminal, el agente sigue.
    para_pasos = {preparacion.VISTO: preparacion.LISTO,
                  preparacion.EN_TERMINAL: preparacion.PREPARANDO}.get(situacion, situacion)
    if para_pasos == situacion:
        para_pasos = e
    pasos = seguimiento.pasos(para_pasos, ahora)
    desde = int(registro.get("ts") or ahora)
    fin = registro.get("terminado_ts")
    transcurrido = (int(fin) if fin else ahora) - desde
    proyecto = e.get("proyecto") or "el proyecto"
    v = Vista(id=e.get("id") or "", proyecto=proyecto, cliente=_nombre_del_agente(e.get("cliente")),
              situacion=situacion)
    v.pasos = [{"titulo": p["titulo"], "estado": p["estado"], "simbolo": SIMBOLOS[p["estado"]],
                "tiempo": duracion(p["duracion"]), "detalle": p["detalle"]} for p in pasos]
    v.registro = texto_del_registro(seguimiento.crudo(registro))
    rehacer = bool(registro.get("rehacer"))
    if rehacer:
        _pasos_de_rehacer(v.pasos, situacion)
    if situacion == preparacion.LISTO or situacion == preparacion.VISTO:
        v.eyebrow = "Listo"
        v.titulo = f"{proyecto} está listo"
        v.reloj = f"Listo en {tiempo(transcurrido)}"
        v.puede_revisar = True
    elif situacion in (preparacion.FALLO, preparacion.COLGADO):
        v.eyebrow = f"{v.cliente} se detuvo"
        v.titulo = f"No se pudo terminar {proyecto}" if situacion == preparacion.FALLO \
            else f"{proyecto} lleva mucho sin avanzar"
        v.reloj = f"Se detuvo a los {tiempo(transcurrido)}"
        v.mensaje = e.get("por_que") or "El agente se detuvo."
        v.acciones = tuple(e.get("acciones") or ())
    elif situacion == preparacion.EN_TERMINAL:
        v.eyebrow = "En una terminal"
        v.titulo = f"{proyecto} sigue en tu terminal"
        v.reloj = f"{tiempo(transcurrido)}"
        v.mensaje = ("Cotejo abrió tu agente en una terminal con las mismas respuestas. "
                     "Termina allí; los pasos se marcan solos.")
    elif rehacer:
        v.eyebrow = f"{v.cliente} está proponiendo otra decisión"
        v.titulo = f"Rehaciendo el plan de {proyecto}"
        v.reloj = tiempo(transcurrido)
        v.mensaje = "Le pasé tu motivo: «%s»." % (registro["rehacer"].get("motivo") or "")
    else:
        v.eyebrow = f"{v.cliente} está preparando tu proyecto"
        v.titulo = f"Preparando {proyecto}"
        v.reloj = f"{tiempo(transcurrido)} · {SUELE_TARDAR}"
    return v


def _pasos_de_rehacer(pasos, situacion):
    """Relanzada para rehacer una decisión (`preparar.rehacer`): lo de la primera vez ya está
    hecho, y lo único que vuelve a moverse es «Proponer las decisiones»."""
    estado = {preparacion.LISTO: progreso.HECHO, preparacion.VISTO: progreso.HECHO,
              preparacion.FALLO: progreso.FALLO,
              preparacion.COLGADO: progreso.FALLO}.get(situacion, progreso.EN_CURSO)
    proponer = [p.verbo for p in progreso.PASOS].index("proponer")
    for i, paso in enumerate(pasos):
        if i == proponer:
            paso.update(estado=estado, simbolo=SIMBOLOS[estado])
            if estado == progreso.EN_CURSO:
                paso.update(detalle="Proponiendo otra", tiempo="")
        else:
            paso.update(estado=progreso.HECHO, simbolo=SIMBOLOS[progreso.HECHO])
