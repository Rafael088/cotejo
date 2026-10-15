"""Qué tareas sacaría un plan.md, y quién las atendería. Sin entrada/salida, como `decision.py`:
entra el texto del plan, sale una lista de tareas; entra el texto de una tarea, sale la decisión
de siempre. Quien lee el archivo y quien escribe en el vault es el verbo (`verbos.cmd_importar_plan`).

Qué cuenta como tarea, en el orden en que se prueba (decidido en [[Cotejo - Planning v1.1]]):

    1. Sus casillas `- [ ]` sin marcar, si tiene alguna.
    2. Si no tiene ninguna, sus encabezados de paso (`## Paso N`, `### Tarea N`).

Las dos cosas a la vez no: un plan con checklist y con «## Paso 1» por encima de ella crearía el
doble de tareas que hay. Y nunca dentro de un bloque de código, por la misma razón que `crear`
no se mete en uno al escribir: ``` - [ ] esto es un ejemplo ``` no es trabajo pendiente.

Los encabezados de paso se reconocen en español (`Paso`, `Fase`, `Tarea`, como quedó escrito en
la decisión) y en inglés (`Phase`, `Task`), que es como los escribe la skill `writing-plans` de
superpowers. No se cuentan las dos palabras en el mismo nivel aparte: cualquier encabezado de
nivel 2 o 3 que lleve número cuenta, y el texto de la tarea es el encabezado entero —«Tarea 3:
escribir las pruebas» dice más que «escribir las pruebas» cuando el plan tiene varias tareas
con un verbo parecido—.
"""

import re

from . import decision

CASILLA_RE = re.compile(r"^[ \t]*[-*][ \t]+\[([ xX])\][ \t]+(.+?)\s*$")
ENCABEZADO_RE = re.compile(
    r"^(#{2,3})[ \t]+(?:paso|fase|phase|tarea|task)\s*\d+\b.*$", re.IGNORECASE)

# La clave del nivel que decidiría el enrutador, traducida a la etiqueta que Cotejo entiende en
# la línea de la tarea (`#facil`, `#medio`, `#dificil`). El nivel humano (`n0`) no tiene
# etiqueta: no es que la tarea sea «difícil», es que no es de ningún modelo.
NIVEL_A_DIFICULTAD = {"n1": "facil", "n2": "medio", "n3": "dificil"}

# La dificultad que ya trae escrita la casilla del plan (`- [ ] Hacer esto #facil`). La misma
# forma que lee la fuente en la línea de una tarea: un tag suelto, no el pedazo de una palabra.
DIFICULTAD_RE = re.compile(r"(?:^|\s)#(facil|medio|dificil)(?=\s|$)", re.IGNORECASE)


def separar_dificultad(texto):
    """(texto sin el tag, dificultad escrita). Sin tag, la dificultad sale vacía.

    Quien escribe `#facil` en su plan ya decidió: esa etiqueta manda sobre la que propondrían
    las reglas, y se saca del texto para que `crear` no la escriba dos veces («#facil #medio»)
    y para que el texto se compare igual que el de una tarea leída de la fuente, que tampoco la
    lleva (cotejo-n9mou2).
    """
    encontradas = DIFICULTAD_RE.findall(texto)
    if not encontradas:
        return texto, ""
    limpio = " ".join(DIFICULTAD_RE.sub(" ", texto).split())
    return limpio, encontradas[-1].lower()


def tareas_de_plan(texto):
    """Las tareas que crearía este plan, en el orden en que aparecen. Puede devolver [].

    No decide nada todavía, ni limpia espacios de más: eso es lo mismo que hace `crear` con
    cualquier texto, y se hace una sola vez en el verbo, no aquí y otra vez allá.
    """
    casillas, encabezados = [], []
    en_bloque = False
    for linea in texto.splitlines():
        if linea.strip().startswith("```"):
            en_bloque = not en_bloque
            continue
        if en_bloque:
            continue
        coincide = CASILLA_RE.match(linea)
        if coincide:
            marca, cuerpo = coincide.groups()
            if marca.strip().lower() != "x" and cuerpo.strip():
                casillas.append(cuerpo.strip())
            continue
        if ENCABEZADO_RE.match(linea.strip()):
            encabezados.append(linea.strip().lstrip("#").strip())
    return casillas or encabezados


def proponer(texto, *, dificultad="", reglas_humano=None, reglas_nivel=None, niveles_extra=(),
             alias_persona=None):
    """La decisión de `decision.decidir` para una tarea que todavía no existe, más la
    dificultad que le pondría `crear` si se aplicara. Devuelve (Decision, dificultad).

    `dificultad` es la que ya traía escrita el plan (`separar_dificultad`): se le pasa a
    `decidir` como la de cualquier tarea etiquetada y se respeta tal cual al crear, aunque un
    veto la deje en manos de una persona —lo que escribió alguien no se borra—.
    """
    elegida = decision.decidir(texto, dificultad=dificultad, reglas_humano=reglas_humano,
                               reglas_nivel=reglas_nivel, niveles_extra=niveles_extra,
                               alias_persona=alias_persona)
    return elegida, dificultad or NIVEL_A_DIFICULTAD.get(elegida.nivel.clave, "")
