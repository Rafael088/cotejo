"""El orden en que se decide quién atiende una tarea. Sin entrada/salida: entra texto, sale una
decisión.

Que este módulo no lea archivos ni lance procesos es lo que deja probar el enrutamiento entero
sin vault, sin `claude` y sin gastar un centavo — y es también lo que permite que `evaluar`
corra las 30 tareas del set en milisegundos.

El orden va de lo más explícito a lo más adivinado, y cada escalón dice por qué ganó:

    1. --modelo            una persona lo está pidiendo ahora mismo
    2. asignación          una persona ya lo escribió en la nota (#agente/opus)
    3. veto humano         nadie lo asignó y el texto dice que no es para un modelo
    4. dificultad          una persona etiquetó el tamaño (#facil / #medio / #dificil)
    5. reglas              regex sobre el texto, gratis
    6. defecto             sonnet

El veto humano va **antes** que la dificultad y no antes que la asignación, y esa posición es
la decisión de diseño de este archivo. Si una persona escribió `#agente/opus` en «comprar el
dominio», sabrá por qué: su decisión explícita gana. Pero `#facil` no dice «que lo haga un
modelo», dice «es corto» — y «Comprar 3 tarjetas de muestra #facil» ruteado a Haiku es un
modelo intentando comprar tarjetas.

Ante la duda se escala, nunca se abarata: el defecto de cualquier ambigüedad es Sonnet y no
Haiku. La asimetría no está en el medio — un ruteo caro equivocado cuesta unos centavos, uno
barato equivocado arruina la tarea y hay que rehacerla, que cuesta las dos cosas.
"""

from dataclasses import dataclass, field

from . import clientes, niveles, reglas as r


@dataclass
class Decision:
    nivel: niveles.Nivel
    por: str        # override | asignacion | veto | dificultad | regla | defecto
    razon: str      # en castellano, para que una persona pueda discutirla
    regla: str = ""     # qué regla ganó, si fue una regla
    coincidencia: str = ""  # qué palabra la disparó
    confianza: str = "media"  # alta | media | baja
    descartadas: list = field(default_factory=list)

    @property
    def despachable(self):
        return self.nivel.despachable

    def como_json(self):
        datos = {
            "nivel": self.nivel.clave,
            "modelo": self.nivel.modelo or niveles.HUMANO,
            "modelo_id": self.nivel.modelo_id,
            "despachable": self.despachable,
            # Dice la máquina, no el enrutador: despachable no cambia si falta el cliente.
            **({"cliente_instalado": clientes.esta_instalado(self.nivel.cliente)}
               if self.despachable else {}),
            "por": self.por,
            "razon": self.razon,
            "confianza": self.confianza,
        }
        if self.regla:
            datos["regla"] = self.regla
            datos["coincidencia"] = self.coincidencia
        if self.descartadas:
            datos["descartadas"] = self.descartadas
        return datos


DIFICULTAD_A_NIVEL = {"facil": "n1", "medio": "n2", "dificil": "n3"}


# Lo que decide un tamaño y no un modelo concreto: ahí cabe traducirlo al agente del proyecto.
POR_TAMANO = ("dificultad", "regla", "defecto")


def decidir(texto, *, agente="", dificultad="", override="", reglas_humano=None,
            reglas_nivel=None, niveles_extra=(), alias_persona=None, cliente=""):
    """Quién atiende esta tarea, y por qué. Con `cliente` (el agente del proyecto,
    `origen.agente_de`), lo que se decide por tamaño se propone con un modelo de ese agente
    (`niveles.del_cliente`); lo que dijo una persona no se toca."""
    elegida = _decidir(texto, agente=agente, dificultad=dificultad, override=override,
                       reglas_humano=reglas_humano, reglas_nivel=reglas_nivel,
                       niveles_extra=niveles_extra, alias_persona=alias_persona)
    if cliente and elegida.por in POR_TAMANO:
        propio = niveles.del_cliente(elegida.nivel, cliente, niveles_extra)
        if propio is not elegida.nivel:
            titulo = clientes.CLIENTES[cliente].titulo if cliente in clientes.CLIENTES else cliente
            elegida.razon += f" (con {titulo}, el agente del proyecto: {propio.modelo})"
            elegida.nivel = propio
    return elegida


def _decidir(texto, *, agente="", dificultad="", override="", reglas_humano=None,
             reglas_nivel=None, niveles_extra=(), alias_persona=None):
    """Quién atiende esta tarea, y por qué.

    `agente` y `dificultad` son lo que Cotejo ya sabe de la tarea (`#agente/opus`, `#dificil`);
    `override` es lo que alguien acaba de escribir en la línea de comandos. Los tres pueden
    venir vacíos: entonces deciden las reglas, y si tampoco, el defecto.

    `alias_persona` es una lista de nombres adicionales que se tratan como persona.
    """
    if reglas_humano is None or reglas_nivel is None:
        reglas_humano, reglas_nivel = r.cargar()
    descartadas = []

    if override:
        nivel = niveles.por_nombre(override, niveles_extra, alias_persona=alias_persona)
        if nivel is None:
            raise ValueError(f"«{override}» no es un nivel ni un modelo conocido")
        return Decision(nivel, "override",
                        f"lo pediste a mano: {nivel.modelo or niveles.HUMANO}",
                        confianza="alta")

    if agente:
        nivel = niveles.por_nombre(agente, niveles_extra, alias_persona=alias_persona)
        if nivel:
            razon = (f"la tarea está asignada a #agente/{agente}"
                     if nivel.despachable else
                     f"la tarea está asignada a #agente/{agente}, que eres tú")
            return Decision(nivel, "asignacion", razon, confianza="alta")
        # Un nombre de agente que no es ninguno de los niveles (otra persona, otro sistema).
        # No se inventa un modelo para él: se dice que tiene dueño y se sigue decidiendo.
        descartadas.append(f"asignada a «{agente}», que no es un nivel de este enrutador")

    regla, pedazo = r.primera(reglas_humano, texto)
    if regla:
        return Decision(niveles.HUMANO_NIVEL, "veto", regla.porque, regla.nombre, pedazo,
                        confianza="media", descartadas=descartadas)

    clave = DIFICULTAD_A_NIVEL.get((dificultad or "").lower())
    if clave:
        nivel = niveles.POR_CLAVE[clave]
        return Decision(nivel, "dificultad", f"la tarea está etiquetada #{dificultad}",
                        confianza="media", descartadas=descartadas)

    regla, pedazo = r.primera(reglas_nivel, texto)
    if regla:
        return Decision(niveles.POR_CLAVE[regla.nivel], "regla", regla.porque, regla.nombre,
                        pedazo, confianza="media", descartadas=descartadas)

    return Decision(niveles.DEFECTO, "defecto",
                    "ninguna regla la reconoció, y ante la duda se escala: el defecto es "
                    "Sonnet, no Haiku",
                    confianza="baja", descartadas=descartadas)


def de_tarea(tarea, *, override="", reglas_humano=None, reglas_nivel=None,
             niveles_extra=(), alias_persona=None, cliente=""):
    """Lo mismo, a partir de una tarea tal como la devuelve la CLI de Cotejo."""
    return decidir(tarea.get("texto", ""), agente=tarea.get("agente", ""),
                   dificultad=tarea.get("dificultad", ""), override=override,
                   reglas_humano=reglas_humano, reglas_nivel=reglas_nivel,
                   niveles_extra=niveles_extra, alias_persona=alias_persona, cliente=cliente)
