"""Las reglas deterministas: expresiones regulares sobre el texto de la tarea.

Son lo primero que se prueba cuando nadie dijo explícitamente a quién va la tarea, y son
gratis. Esa es toda la razón de que existan: «Guarda esto en el segundo cerebro» se resuelve
con un regex en microsegundos y a costo cero, y pagarle a un modelo para que decida cada
trivialidad se come el ahorro que justifica el proyecto entero.

Las reglas no son sagradas: `tareas-obsidian evaluar` las mide contra un set de tareas reales
etiquetadas a mano (`enrutador/datos/evaluacion.json`) e imprime en qué falla. Ese número es lo que
decide si hace falta un clasificador; hasta que exista, cambiar una regla es cambiar una línea
y volver a medir.

Cada regla dice **por qué** decidió, no solo qué. El agente que lee la decisión necesita poder
discutirla: «lo mandé a humano por la regla compras» es rebatible, «lo mandé a humano» no.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Regla:
    nombre: str
    nivel: str
    patron: str
    porque: str

    def __post_init__(self):
        object.__setattr__(self, "_re", re.compile(self.patron, re.IGNORECASE))

    def coincide(self, texto):
        encontrado = self._re.search(texto)
        return encontrado.group(0) if encontrado else ""


# Las de `n0` van primero y se prueban aparte: no eligen un modelo más barato, vetan que haya
# modelo. Salieron de leer las 105 tareas reales del vault, no de imaginar casos.
HUMANO = (
    Regla("compras", "n0",
          r"\b(comprar|compra de|pagar|pagarle|contratar|cotizar|encargar a la imprenta)\b",
          "hay que gastar dinero, y eso lo autoriza una persona"),
    Regla("tramites", "n0",
          # «contador» es la persona; «contador de debates» es un número en pantalla.
          r"\b(abogado|contador(?!(es)?\s+de\b)|notari\w+|registrar la marca|ante la SIC|"
          r"figura legal|"
          r"documento de venta|c[ée]dula|factura electr[óo]nica)\b",
          "es un trámite legal o contable con una persona del otro lado"),
    Regla("credenciales", "n0",
          # «token» y «OAuth» a secas también son código («emite un token firmado», «botón con
          # OAuth PKCE»): solo vetan cuando hay que ir a buscar o autorizar uno como tú.
          r"\b(api[- ]?key|(sacar|guardar|copiar|pegar|conseguir|pedir|generar|rotar|renovar|"
          r"revocar) (el |la |un |una |tu |mi |su )?token|token de acceso|"
          r"(autorizar|aprobar|dar acceso)\b.{0,40}\boauth|credencial\w*|contrase[ñn]a|"
          r"iniciar sesi[óo]n|"
          r"crear (el |la |un |una )?(proyecto en |cuenta|bot en)|@\w*bot\w*|"
          # Abrir algo en el panel de un servicio, o poner ahí sus variables, también es entrar
          # como tú: «Crear la base de Upstash», «pasar las variables a Vercel».
          r"crear (el |la |un |una )?(base de datos|base|sitio|proyecto|app|aplicaci[óo]n|"
          r"instancia|bucket) (de|en) (upstash|supabase|vercel|cloudflare|firebase|netlify|"
          r"railway|render|neon|planetscale|mongodb|mercado ?pago|openrouter|resend|twilio|aws)|"
          r"(pasar|poner|cargar|definir|guardar)\w*\b.{0,50}\b(vercel|netlify|railway|render)|"
          r"console\.(anthropic|cloud)|google cloud console|search console)\b",
          "hay que autenticarse como tú en un sitio de terceros"),
    Regla("fisico", "n0",
          r"\b(imprenta|imprimir|impres\w+|grabado|tarjetas? de muestra|pegatinas?|"
          r"celular|acr[íi]lico|portaprecios|chip nfc|con el n[úu]mero real|"
          r"escane\w+ impres\w+)\b",
          "pasa fuera de la pantalla: papel, plástico o un teléfono en la mano"),
    Regla("criterio_propio", "n0",
          r"\b(decidir (si|los|las|el|la|qu[ée]|cu[áa]nt\w+|c[óo]mo|entre)|"
          r"(fijar|definir|poner|decidir) (el |la |los |las |su |sus )?(precio|tarifa|paquete)\w*|"
          r"definir qu[ée] se (le )?cobra|escoger (la|el|entre)|elegir entre|"
          r"usar\w* .{0,20}unos d[íi]as|probar con (mi|la) voz real|"
          r"revisar el vault|confirmar (tras|despu[ée]s de) (un )?reinici\w+)\b",
          "la respuesta es una preferencia tuya, no algo que se averigüe"),
)

# Las de nivel: solo se miran si nadie asignó la tarea y no la vetó ninguna de arriba.
NIVEL = (
    Regla("diseno", "n3",
          r"\b(arquitectur\w+|refactor\w*|redise[ñn]\w+|migrar|capa \w+|"
          r"de punta a punta|spec\b|dise[ñn]ar el|dise[ñn]o del sistema|"
          r"(varios|m[úu]ltiples) archivos|repensar|partir|dividir|separar en|"
          r"construir (la|el|una|un) (skill|agente|servidor|integraci[óo]n|capa))\b",
          "toca la forma del sistema, no una función: se decide antes de escribir"),
    Regla("riesgo", "n3",
          r"\b(seguridad|permisos|concurren\w+|corrupci[óo]n|p[ée]rdida de datos|"
          r"escritura at[óo]mica|race condition)\b",
          "equivocarse aquí se paga caro y no siempre se nota"),
    Regla("enunciado_largo", "n3",
          r"^.{220,}$",
          "hicieron falta varias frases para enunciarla: lo que no cabe en una línea rara vez "
          "cabe en un archivo"),
    Regla("mecanico", "n1",
          r"\b(anotar|anota|apuntar|guardar (esto|esta|en el)|renombrar|corregir (el|la) "
          r"(typo|tilde|acento)|cambiar el print|actualizar el (readme|changelog)|"
          r"a[ñn]adir (una|la) l[íi]nea|documentar el paso|imprim\w+ (en|un) json)\b",
          "es una edición mecánica y acotada: se sabe de antemano cómo termina"),
    Regla("codigo", "n2",
          r"\b(prueba[s]?\b|test\w*|bug|fallo|arreglar|corregir|implementar|a[ñn]adir|"
          r"agregar|exponer|parsear|validar|script|cli\b|endpoint|funci[óo]n)\b",
          "es trabajo normal de código sobre uno o dos archivos"),
)


def cargar(extra=(), apagadas=()):
    """Las reglas efectivas: las de fábrica menos las apagadas, más las de la config.

    Las extra van **antes** que las de fábrica dentro de su grupo. Quien escribe una regla en
    su config lo hace porque las de aquí se equivocan con su caso, así que la suya tiene que
    poder ganar sin que haya que borrar nada.
    """
    apagadas = set(apagadas or ())
    propias = tuple(Regla(r["nombre"], r["nivel"], r["patron"], r.get("porque", "regla propia"))
                    for r in (extra or ()))
    humano = tuple(r for r in propias if r.nivel == "n0")
    nivel = tuple(r for r in propias if r.nivel != "n0")
    return (humano + tuple(r for r in HUMANO if r.nombre not in apagadas),
            nivel + tuple(r for r in NIVEL if r.nombre not in apagadas))


def primera(reglas, texto):
    """La primera regla que coincide y con qué palabra, o (None, "")."""
    for regla in reglas:
        pedazo = regla.coincide(texto)
        if pedazo:
            return regla, pedazo
    return None, ""
