"""Aceptar una decisión propuesta del almacén `.cotejo/` (C5, v1.2) —y, desde la 1.3.0,
rechazarla con motivo—: las transiciones que hace la persona, nunca un agente ni un verbo.

E2 (2026-10-04, «Carta propia + aviso») decidió dónde: la decisión propuesta sale como carta
propia en *Para comprobar* y se abre con la misma vista de revisión que una entrega —su texto
y, si reemplaza otra, la vieja al lado— con el único botón de Aceptar. Aprobar o integrar una
tarea nunca acepta una decisión, y la revisión de una tarea solo avisa que su entrega propone
una, sin botón para aceptarla ahí.

Esto es la lógica, sin GTK, igual que `revision.py` lo es para las entregas: el board (`tareas/app/`)
es lo único que la llama, y por eso se prueba sin pantalla. No hay —ni habrá—
un verbo de CLI ni una tool de MCP para `aceptar`: lo vigila
`pruebas/test_cli.py::Contrato`.
"""

from . import almacen


class NoEsDecision(Exception):
    """Se pidió aceptar una entrada que no es una decisión."""

    def __init__(self, entrada):
        super().__init__(f"«{entrada.id}» no es una decisión (es {entrada.tipo}): solo las "
                         f"decisiones se aceptan.")
        self.entrada = entrada


class AceptacionParcial(Exception):
    """La decisión quedó aceptada, pero no se pudo dejar reemplazada la que reemplaza.

    No es una operación atómica entre dos archivos —el almacén no la ofrece—, así que se avisa
    en vez de deshacer: la misma asimetría que ya acepta
    `conocimiento.cmd_proponer_decision` entre crear la nueva y mover la vieja.
    """

    def __init__(self, aceptada, causa):
        super().__init__(f"«{aceptada.id}» quedó aceptada, pero no pude dejar reemplazada la "
                         f"decisión que reemplaza ({causa}). Revísalo a mano.")
        self.aceptada = aceptada
        self.causa = causa


def propuestas(alm, avisos=None):
    """Las decisiones en `propuesta` de este almacén: lo que el board pinta como carta propia
    en *Para comprobar*."""
    return [e for e in alm.entradas("decision", avisos) if e.estado == "propuesta"]


def para_revisar(alm, entrada):
    """Lo que la vista de revisión enseña de una decisión propuesta: su texto y, si
    `reemplaza` otra, la vieja al lado.

    Si la vieja ya no se puede leer (se borró o cambió de id a mano), `reemplaza` sale en
    `None`: la propuesta se sigue pudiendo aceptar, solo que sin la comparación.
    """
    reemplaza_id = entrada.datos.get("reemplaza")
    vieja = None
    if reemplaza_id:
        try:
            vieja = alm.leer(reemplaza_id)
        except (almacen.EntradaNoExiste, almacen.IdRepetido):
            vieja = None
    return {"id": entrada.id, "titulo": entrada.titulo, "texto": entrada.cuerpo,
            "temas": entrada.temas, "autor": entrada.datos.get("autor", ""),
            "fecha": entrada.datos.get("fecha", ""), "version": entrada.version,
            "reemplaza": ({"id": vieja.id, "titulo": vieja.titulo, "texto": vieja.cuerpo,
                           "estado": vieja.estado} if vieja else None)}


def aceptar(alm, entrada_id, version):
    """Acepta la decisión `entrada_id`: pasa a `aceptada`, verificado por versión (A1).

    Si `reemplaza` otra decisión, esa pasa a `reemplazada` en la misma operación, con
    `reemplazada_por` apuntando a la nueva. Devuelve `(aceptada, reemplazada_o_None)`.

    Solo se acepta lo que está `propuesta`: lo garantiza `Almacen.poner_estado` con las mismas
    `TRANSICIONES` que usa `proponer decision`, así que no hay una regla aparte aquí para qué
    estados valen. Si la entrada no es de tipo decisión, se avisa antes de escribir nada.
    """
    entrada = alm.leer(entrada_id)
    if entrada.tipo != "decision":
        raise NoEsDecision(entrada)
    # La fecha en que se aceptó es la que `cotejo release` compara con la del último tag.
    aceptada = alm.poner_estado(entrada.id, version, "aceptada",
                                campos={"aceptada_el": almacen._hoy()})
    reemplaza_id = aceptada.datos.get("reemplaza")
    if not reemplaza_id:
        return aceptada, None
    try:
        vieja = alm.leer(reemplaza_id)
        reemplazada = alm.poner_estado(vieja.id, vieja.version, "reemplazada",
                                       campos={"reemplazada_por": aceptada.id})
    except (almacen.EntradaNoExiste, almacen.IdRepetido, almacen.EntradaCambiada,
            almacen.NoSeEdita) as error:
        raise AceptacionParcial(aceptada, error) from error
    return aceptada, reemplazada


def rechazar(alm, entrada_id, version, motivo):
    """Rechaza la decisión propuesta `entrada_id` con un motivo (v1.3.0, «Revisar el plan»).

    Es la otra mitad de lo que hace la persona con una propuesta: «Cambiar» en la pantalla del
    plan es rechazarla con motivo (decidido en el planning de la fase 2), y el motivo vuelve al
    agente para que proponga otra. Pasa a `rechazada` con `motivo` y `rechazada_el` en la misma
    escritura, verificado por versión. El motivo es obligatorio por la misma regla que devolver
    o bloquear: un rechazo sin porqué hace que el siguiente se estrelle contra lo mismo.
    Como `aceptar`, no tiene verbo de CLI ni tool de MCP: solo lo llama el board.
    """
    motivo = " ".join(str(motivo or "").split())
    if not motivo:
        raise ValueError("Rechazar una decisión exige un motivo: es lo que lee el agente para "
                         "proponer otra.")
    entrada = alm.leer(entrada_id)
    if entrada.tipo != "decision":
        raise NoEsDecision(entrada)
    return alm.poner_estado(entrada.id, version, "rechazada",
                            campos={"motivo": motivo, "rechazada_el": almacen._hoy()})
