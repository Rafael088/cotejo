"""Un vault de Obsidian como fuente: notas de Markdown con tareas `- [ ]`.

Todo lo que aquí se da por supuesto —que hay una carpeta `01-Proyectos/`, que el estado va en
un tag al final de la línea, que la identidad de una tarea es su marca de bloque— vale para
Obsidian y para nadie más. Ese es el trato de una fuente: quedarse con esas suposiciones para
que el resto de Cotejo no las tenga.

Lo que no cambia, lo diga quien lo diga: antes de escribir se comprueba que la línea siga
exactamente igual que cuando se leyó, y el archivo se reemplaza entero de forma atómica. Es el
único código del proyecto que modifica las notas del usuario.

Además de los proyectos, se pueden leer **carpetas sueltas** —`00-Inbox` y `06-Diario` en un
vault típico—, que no son proyectos: no tienen frontmatter de proyecto ni sección de tareas,
solo notas con algún `- [ ]` suelto. Cada carpeta cuenta como un proyecto sintético que se
llama como ella sin el número de delante («Inbox», «Diario»), y cada nota suya es una sub-nota:
la fecha de la nota diaria sale como etiqueta de la tarea, igual que el nombre de una sub-nota
en un proyecto-carpeta. Uno por carpeta y no uno por nota porque el diario gana una nota al
día, y un proyecto por día llenaría el board de grupos de una tarea. Al resto de Cotejo le llegan
como `Proyecto` normales, así que el board, la CLI y `estado.json` los tratan igual
sin saber de dónde salieron. Viene apagado: ver `carpetas_sueltas` en `__init__`.
"""

import json
import os
import random
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import quote

from .. import configuracion, rutas
from .. import version as versiones
from ..fuente import Fuente
from ..modelo import PENDIENTE, NoSeCreaAqui, Proyecto, Tarea, TareaCambiada

# "- [ ] texto", "* [x] texto", "1. [ ] texto", con cualquier sangría.
TASK_RE = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+\[)(.)(\]\s+)(.*?)\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

# Los estados intermedios van como tag al final de la línea para no romper el "- [ ]" que
# Obsidian entiende, y para que se vean igual desde Obsidian que desde Cotejo.
# El límite no puede ser \b: un guion no es carácter de palabra, así que "#en-curso-luego"
# habría colado como "#en-curso" dejando "-luego" tirado en el texto. Un tag de Obsidian
# sigue mientras haya letras, dígitos, guion bajo, guion o barra.
FIN_TAG = r"(?![\w/-])"
ESTADO_RE = re.compile(r"\s*#(por-validar|en-curso)" + FIN_TAG)

# Ya se escribe a mano así en notas existentes: "texto — AAAA-MM-DD", con guion largo y al final del todo
# (antes de la marca, que es lo único que va después). marcar() la copia en vez de inventar un
# formato propio; el $ exige que sea lo último del cuerpo, así que una fecha en medio del texto
# —por ejemplo citando cuándo pasó algo— no cuenta como la fecha de cierre y no se toca.
# El grupo es para `_tarea`, que lee de ahí `Tarea.cerrada`; `marcar` solo usa `search` y `sub`,
# a quienes un grupo de más no les cambia nada.
FECHA_RE = re.compile(r"\s+—\s+(\d{4}-\d{2}-\d{2})\s*$")

# La marca de bloque de Obsidian al final de la línea: "^cotejo-a1b2". Es el identificador
# estable de la tarea: viaja con ella aunque la nota se edite por arriba, cosa que el número
# de línea no hace. Obsidian solo la reconoce al final del bloque, así que toda escritura la
# deja ahí. Leemos cualquier marca válida (si alguien puso la suya a mano, esa vale); las que
# ponemos nosotros llevan el prefijo para que se distingan de un vistazo.
MARCA_RE = re.compile(r"\s+\^([A-Za-z0-9-]+)\s*$")
PREFIJO_MARCA = "cotejo-"
ALFABETO_MARCA = "abcdefghijklmnopqrstuvwxyz0123456789"

# Quién tiene la tarea: "#agente/opus". Tag anidado, que Obsidian filtra de fábrica.
AGENTE_RE = re.compile(r"\s*#agente/([\w.-]+)")
# Dificultad del [[Enrutador]]: decide a qué modelo se le encarga.
DIFICULTAD_RE = re.compile(r"\s*#(facil|medio|dificil)" + FIN_TAG)
# La versión a la que pertenece (v1.2.4): "#v1.2.4" o "#v1.2". Un punto seguido de un dígito
# tampoco cierra el tag, para que "#v1.2.4.5" no se lea como "#v1.2.4" dejando ".5" tirado; lo
# que case pero no sea una versión (`#v01.2`) se queda en el texto: lo decide `version.de_tarea`.
VERSION_RE = re.compile(r"\s*#(v\d+(?:\.\d+){1,2})(?![\w/-]|\.\d)")

# El encabezado de la sección de tareas de una nota, con o sin emoji delante: «## ✅ Tareas».
ENCABEZADO_TAREAS_RE = re.compile(r"^#{1,6}[ \t]+(?:\W+[ \t]*)?(tareas|tasks|to-?do)\b",
                                  re.IGNORECASE)

ESTADOS_OCULTOS = {"terminado", "descartado"}


@dataclass(frozen=True)
class Sitio:
    """Dónde está la tarea dentro del vault, y con qué texto se la leyó.

    Va dentro de `Tarea.sitio` y no lo mira nadie más: es lo que hace falta para volver a
    encontrarla y para comprobar que nadie la tocó mientras tanto.
    """

    nota: Path  # relativa al vault
    linea: int  # índice 0
    original: str  # la línea tal cual estaba al leerla, sin salto de línea
    marca: str  # marca de bloque, sin el "^"


class Obsidian(Fuente):
    nombre = "obsidian"
    accion_abrir = "Abrir en Obsidian"
    # El CLI de Obsidian instalado en ~/.local/bin tapa a /usr/bin/obsidian en el PATH, y solo
    # funciona con la app abierta; por eso el respaldo va con ruta absoluta.
    respaldo = ("/usr/bin/obsidian",)
    parametros = {
        "vault": "Ruta al vault. Sin ella, el que tenga abierto Obsidian.",
        "carpeta_proyectos": "Dónde están las notas de proyecto, relativa al vault "
                             "(por defecto 01-Proyectos).",
        "carpetas_sueltas": "Carpetas sin proyecto cuyas tareas también se leen, como "
                            "[\"00-Inbox\", \"06-Diario\"]. Apagado por defecto.",
        "migrados": "Proyectos que ya viven en su repo, como {\"Cotejo\": \"/ruta/al/repo\"}: "
                    "se leen de <repo>/.cotejo/tareas.md y dejan de leerse del vault, aunque "
                    "su nota siga ahí. Quitar la marca lo deshace.",
    }

    @classmethod
    def config_inicial(cls):
        return {"vault": vault_valido() or "", "carpeta_proyectos": "01-Proyectos"}

    def __init__(self, config=None):
        config = config or {}
        # `COTEJO_VAULT` apunta a otro vault en una sola invocación, sin tocar la config: es lo
        # que deja probar contra un vault de mentira sin ensuciar el de verdad.
        vault = os.environ.get("COTEJO_VAULT") or config.get("vault") or vault_abierto()
        self.vault = Path(vault) if vault else None
        self.carpeta_proyectos = (os.environ.get("COTEJO_CARPETA_PROYECTOS")
                                  or config.get("carpeta_proyectos") or "01-Proyectos")
        # Apagado por defecto, porque encenderlo cambia lo que ve el board y no siempre se
        # quiere: el diario acumula un «⏭️ Mañana» por día, y cada `- [ ]` que nadie cerró
        # pasaría a ser una tarea pendiente para siempre. Quien lo quiera lo enciende con
        # `"carpetas_sueltas": ["00-Inbox", "06-Diario"]`; `COTEJO_CARPETAS_SUELTAS`, separadas
        # por comas, lo hace en una sola invocación, y vacía lo apaga aunque la config lo pida.
        entorno = os.environ.get("COTEJO_CARPETAS_SUELTAS")
        sueltas = entorno.split(",") if entorno is not None else config.get("carpetas_sueltas") or []
        if isinstance(sueltas, str):
            sueltas = [sueltas]
        self.carpetas_sueltas = [c.strip().strip("/") for c in sueltas if _carpeta_valida(c)]
        # Lo que pesó cada nota leída, por su ruta relativa al vault: el medidor de ahorro.
        self._leido = {}
        # Qué rutas se leyeron para cada proyecto (su `donde`), para que `leido()` pueda
        # contar solo las de los proyectos que pasaron el filtro y no el vault entero que
        # `escanear` tuvo que recorrer para encontrarlos.
        self._notas_por_proyecto = {}

    @property
    def problema(self):
        # Se mira en cada consulta y no una vez al arrancar: una ruta que no existe (un disco
        # sin montar, un COTEJO_VAULT mal escrito) escaneaba cero proyectos, y la lista decía
        # «Todo al día» —la peor mentira para un gestor de tareas—. Y si el disco aparece con
        # la app abierta, la siguiente recarga ya lo lee sin reiniciar nada.
        forma = '{"vault": "/ruta/al/vault", "carpeta_proyectos": "01-Proyectos"}'
        if not self.vault:
            return (f"No encontré ningún vault de Obsidian. Define la ruta en {configuracion.ruta()}, "
                    f"con la forma {forma}")
        if not self.vault.is_dir():
            return (f"El vault {self.vault} no existe o no es una carpeta. Corrige la ruta en "
                    f"{configuracion.ruta()} o en COTEJO_VAULT")
        return None

    # --- leer ---------------------------------------------------------

    def escanear(self, incluir_hechas=False, avisos=None):
        # Se reinicia en cada escaneo: `leido()` contesta por la última respuesta que se dio,
        # no por todo lo que esta fuente haya leído en su vida.
        self._leido = {}
        self._notas_por_proyecto = {}
        proyectos = []
        base = self.vault / self.carpeta_proyectos if self.vault else None
        if base is None or not base.is_dir():
            return proyectos

        for entrada in sorted(base.iterdir()):
            if entrada.name.startswith((".", "_")):
                continue
            if entrada.is_dir():
                notas = sorted(_notas(entrada))
                principal = entrada / f"{entrada.name}.md"
                nombre = entrada.name
            elif entrada.suffix == ".md":
                notas = [entrada]
                principal = entrada
                nombre = entrada.stem
            else:
                continue

            meta = {}
            if principal.is_file():
                relativa = principal.relative_to(self.vault)
                meta = leer_frontmatter(self._leer(principal, avisos, relativa)[:60])
                if meta.get("tipo") and meta["tipo"] != "proyecto":
                    continue
            if meta.get("estado") in ESTADOS_OCULTOS:
                continue

            proyecto = Proyecto(
                nombre=nombre,
                donde=str(principal.relative_to(self.vault)),
                estado=meta.get("estado", ""),
                prioridad=meta.get("prioridad", ""),
            )
            # La nota principal primero, luego las sub-notas.
            notas.sort(key=lambda p: (p != principal, str(p).lower()))
            self._llenar(proyecto, notas, principal, incluir_hechas, avisos)
            proyectos.append(proyecto)

        proyectos.extend(self._sueltas(proyectos, incluir_hechas, avisos))
        proyectos.sort(key=lambda p: p.orden)
        if avisos is not None:
            # La nota principal se lee dos veces, una para el frontmatter y otra para las
            # tareas; el aviso es el mismo y no hace falta contarlo dos veces.
            avisos[:] = list({aviso["nota"]: aviso for aviso in avisos}.values())
        return proyectos

    def _llenar(self, proyecto, notas, principal, incluir_hechas, avisos):
        """Reparte las tareas de `notas` en el proyecto. Las de la principal van sin etiqueta;
        las demás llevan el nombre de su nota, que es lo que el board enseña al lado."""
        for nota in notas:
            relativa = nota.relative_to(self.vault)
            lineas = self._leer(nota, avisos, relativa)
            # Con qué proyecto va esta ruta, para que `leido()` pueda filtrar sin releer nada.
            self._notas_por_proyecto.setdefault(proyecto.donde, set()).add(str(relativa))
            sub = "" if nota == principal else nota.stem
            for tarea in leer_tareas(relativa, lineas, incluir_hechas, sub):
                (proyecto.hechas if tarea.hecha else proyecto.tareas).append(tarea)

    def _sueltas(self, proyectos, incluir_hechas, avisos):
        """Un proyecto sintético por carpeta suelta que tenga alguna tarea.

        Sin estado ni prioridad, así que se ordenan detrás de los proyectos de verdad: son el
        cajón de lo que todavía no tiene proyecto, no un proyecto que empuje a los demás de la
        barra. Una carpeta sin tareas no sale, a diferencia de un proyecto vacío: el proyecto
        lo escribió alguien como proyecto, y un «Inbox» vacío en el board solo es ruido.
        """
        tomados = {p.nombre.lower() for p in proyectos}
        for carpeta in self.carpetas_sueltas:
            base = self.vault / carpeta
            if carpeta == self.carpeta_proyectos.strip("/") or not base.is_dir():
                continue
            notas = sorted((p for p in _notas(base) if not p.name.startswith("_")),
                           key=lambda p: str(p).lower())
            # «00-Inbox» se llama «Inbox», que es como se lo nombra. Si ya hay un proyecto con
            # ese nombre, la carpeta se queda con el suyo entero: dos grupos con el mismo
            # nombre harían que `--proyecto Inbox` mezclara tareas de los dos.
            nombre = re.sub(r"^\d+[-_ ]+", "", Path(carpeta).name) or carpeta
            if nombre.lower() in tomados:
                nombre = carpeta
            tomados.add(nombre.lower())
            proyecto = Proyecto(nombre=nombre, donde=carpeta)
            # Sin nota principal: todas las tareas llevan la etiqueta de su nota, que en el
            # diario es la fecha y es lo único que distingue un «llamar a X» de otro.
            self._llenar(proyecto, notas, None, incluir_hechas, avisos)
            if proyecto.tareas or proyecto.hechas:
                yield proyecto

    def normalizar_id(self, texto):
        """Acepta la marca con el "^" delante, que es como se ve en la nota y como la copia
        quien la lee ahí."""
        return str(texto).strip().lstrip("^")

    def leido(self, proyectos=None):
        """Lo que pesaron las notas del último escaneo, cada una contada una sola vez.

        Sin `proyectos`, es el vault entero que se escaneó, no solo lo que la respuesta acabó
        enseñando. Con `proyectos` —los que pasaron el filtro de quien llama, `tareas
        --proyecto`— cuenta solo las notas de esos proyectos: `_llenar` ya apuntó qué ruta es
        de cuál mientras leía, así que filtrar no reabre nada (cotejo-mbzjoj: antes se sumaba el
        vault entero aunque la respuesta fuera de un solo proyecto).
        """
        if proyectos is None:
            return sum(self._leido.values())
        rutas = set()
        for proyecto in proyectos:
            rutas.update(self._notas_por_proyecto.get(proyecto.donde, ()))
        return sum(self._leido.get(ruta, 0) for ruta in rutas)

    # --- escribir -----------------------------------------------------

    def crear(self, proyecto, texto, dificultad="", version=""):
        """Añade un `- [ ]` con las demás tareas de la nota principal del proyecto.

        `version` (`"v1.2.4"`, ya validada por la CLI) va como tag, `#v1.2.4`, detrás de la
        dificultad: es como se lee.

        Nace con su marca de bloque puesta, y no como las que escribe una persona a mano, que
        la ganan la primera vez que se las toca. La diferencia importa: quien crea una tarea
        por aquí es un agente que va a querer nombrarla en la siguiente llamada, y un id que
        es «nota más número de línea» se le mueve en cuanto alguien edite por encima.

        Solo en la nota principal. Una carpeta suelta (el Inbox, el Diario) no tiene ninguna
        —es un montón de notas de una persona—, y elegir por ella en cuál cae la tarea, o
        abrirle una nota nueva, sería inventarse dónde vive. Lo mismo un proyecto-carpeta sin
        su nota del mismo nombre. En los dos casos se niega con `NoSeCreaAqui` y no escribe.
        """
        ruta = self._archivo(proyecto.donde)
        if not ruta.is_file():
            if proyecto.donde.strip("/") in self.carpetas_sueltas:
                raise NoSeCreaAqui(
                    f"«{proyecto.nombre}» es una carpeta de notas sueltas, no un proyecto: no "
                    "tiene una nota principal donde vaya la tarea")
            raise NoSeCreaAqui(f"«{proyecto.nombre}» no tiene nota principal ({proyecto.donde})")
        # newline="" por lo mismo que en `_reescribir`: los saltos de la nota se respetan tal
        # cual, y una tarea añadida no debe reformatear el archivo entero.
        with ruta.open(encoding="utf-8", newline="") as archivo:
            lineas = archivo.readlines()

        indice = _fin_de_las_tareas(lineas)
        salto = _salto(lineas, indice)
        cuerpo = f"- [ ] {texto.strip()}"
        if dificultad:
            cuerpo += f" #{dificultad}"
        version = versiones.de_tarea(version) or ""
        if version:
            cuerpo += f" #{version}"
        marca = _marca_nueva(lineas)
        nueva = f"{cuerpo} ^{marca}"

        # Una nota que no termina en salto de línea se queda sin él y la tarea nueva acabaría
        # pegada a la última línea.
        if indice == len(lineas) and lineas and not lineas[-1].endswith(("\n", "\r")):
            lineas[-1] += salto
        lineas.insert(indice, nueva + salto)

        temporal = ruta.with_name(f".{ruta.name}.tareas-tmp")
        with temporal.open("w", encoding="utf-8", newline="") as archivo:
            archivo.write("".join(lineas))
        os.replace(temporal, ruta)

        return Tarea(texto.strip(), id=marca, donde=proyecto.donde, dificultad=dificultad,
                     version=version, sitio=Sitio(Path(proyecto.donde), indice, nueva, marca))

    def marcar(self, tarea, hecha=True):
        """Cambia el check. Marcarla es la validación humana, así que de paso borra el tag de
        estado: «en curso» o «por validar» no significan nada en una tarea hecha.

        De paso pone o quita la fecha, con el mismo formato que ya se escribe a mano en notas
        existentes. Si la línea ya traía una —de antes— no se le suma otra; y deshacer quita
        justo esa fecha, para que marcar y deshacer sean inversos y no dejen basura atrás.
        """
        def transformar(cuerpo):
            if hecha:
                cuerpo = ESTADO_RE.sub("", cuerpo).rstrip()
                if not FECHA_RE.search(cuerpo):
                    cuerpo = f"{cuerpo} — {_hoy()}"
            else:
                cuerpo = FECHA_RE.sub("", cuerpo)
            return TASK_RE.sub(
                lambda m: m.group(1) + ("x" if hecha else " ") + m.group(3) + m.group(4),
                cuerpo, count=1)

        actual = self._reescribir(tarea, transformar)
        return replace(actual, hecha=hecha, estado=PENDIENTE if hecha else tarea.estado)

    def poner_estado(self, tarea, nuevo):
        def transformar(cuerpo):
            limpio = ESTADO_RE.sub("", cuerpo).rstrip()
            return limpio if nuevo == PENDIENTE else f"{limpio} #{nuevo}"

        return replace(self._reescribir(tarea, transformar), estado=nuevo)

    def poner_agente(self, tarea, agente):
        def transformar(cuerpo):
            limpio = AGENTE_RE.sub("", cuerpo).rstrip()
            return f"{limpio} #agente/{agente}" if agente else limpio

        return replace(self._reescribir(tarea, transformar), agente=agente)

    def quitar(self, tarea):
        """Borra la línea de la tarea si sigue exactamente igual que al leerla.

        La misma garantía que `_reescribir`: se busca por su marca (o su número de línea si no
        tiene), se compara con lo que se leyó y, si alguien la tocó, `TareaCambiada` sin
        escribir nada. El archivo se reemplaza entero de forma atómica y con sus saltos de
        línea tal cual.
        """
        sitio = tarea.sitio
        ruta = self._archivo(sitio.nota)
        with ruta.open(encoding="utf-8", newline="") as archivo:
            lineas = archivo.readlines()
        indice = _localizar(lineas, sitio)
        if indice is None or lineas[indice].rstrip("\r\n") != sitio.original:
            raise TareaCambiada(str(sitio.nota))
        del lineas[indice]
        temporal = ruta.with_name(f".{ruta.name}.tareas-tmp")
        with temporal.open("w", encoding="utf-8", newline="") as archivo:
            archivo.write("".join(lineas))
        os.replace(temporal, ruta)

    def fecha_cierre(self, tarea):
        """El "— AAAA-MM-DD" que `marcar` (o una persona) dejó al final de la línea, o None.

        Se lee de la línea tal como se leyó (`Sitio.original`). Cuando `Tarea.cerrada` exista
        en el modelo (rama del filtro de Finalizada, cotejo-5wq71w), la de la clase base gana
        y esto queda de respaldo.
        """
        cerrada = super().fecha_cierre(tarea)
        if cerrada or not isinstance(tarea.sitio, Sitio):
            return cerrada
        cuerpo, _ = _sacar_marca(tarea.sitio.original.rstrip())
        m = FECHA_RE.search(cuerpo)
        return re.search(r"\d{4}-\d{2}-\d{2}", m.group(0)).group(0) if m else None

    def asegurar_id(self, tarea):
        """Le pone su marca a la tarea si no la tiene. Cualquier escritura ya la pone; esto es
        para cuando se entrega el id sin cambiar nada más."""
        if tarea.sitio.marca:
            return tarea
        return self._reescribir(tarea, lambda cuerpo: cuerpo)

    def _reescribir(self, tarea, transformar):
        """Reescribe la línea de la tarea si sigue igual que al leerla.

        Verificar antes de escribir es lo que evita pisar una nota editada por fuera, y el
        reemplazo atómico evita dejarla a medias. Toda escritura deja la línea con su marca de
        bloque al final: es lo que le da a la tarea un id que no depende de dónde esté.
        """
        sitio = tarea.sitio
        ruta = self._archivo(sitio.nota)
        # newline="" para que los saltos de línea pasen tal cual: sin esto, Python traduce los
        # \r\n al leer y escribe \n, así que tocar una tarea reescribía los saltos de la nota
        # entera. Una línea cambiada tiene que verse como una línea cambiada, no como un
        # archivo reformateado.
        with ruta.open(encoding="utf-8", newline="") as archivo:
            lineas = archivo.readlines()

        indice = _localizar(lineas, sitio)
        if indice is None or lineas[indice].rstrip("\r\n") != sitio.original:
            raise TareaCambiada(str(sitio.nota))

        linea = lineas[indice]
        fin = linea[len(linea.rstrip("\r\n")):]
        cuerpo, marca = _sacar_marca(linea.rstrip("\r\n"))
        marca = marca or _marca_nueva(lineas)
        # El transformar trabaja sobre la línea sin marca y la marca vuelve al final, porque
        # Obsidian solo la reconoce ahí. Los espacios finales se van con ella.
        nueva = f"{transformar(cuerpo).rstrip()} ^{marca}"
        if nueva + fin != linea:
            lineas[indice] = nueva + fin
            temporal = ruta.with_name(f".{ruta.name}.tareas-tmp")
            with temporal.open("w", encoding="utf-8", newline="") as archivo:
                archivo.write("".join(lineas))
            os.replace(temporal, ruta)
        return replace(tarea, id=marca,
                       sitio=replace(sitio, linea=indice, original=nueva, marca=marca))

    def _archivo(self, relativa):
        """El archivo de verdad detrás de una ruta de nota (`Sitio.nota`, `Proyecto.donde`).

        En un vault es la ruta relativa colgada del vault. Está aparte para que otra fuente
        hecha de las mismas líneas —la de repos, `fuentes/repo.py`— reutilice la escritura
        verificada entera cambiando solo dónde cae cada nota.
        """
        return self.vault / relativa

    # --- dónde vive ---------------------------------------------------

    def vigilables(self):
        """Las carpetas de proyectos y las sueltas, para enterarse de que alguien editó una
        nota. Una suelta que no se vigilara dejaría el board viejo al capturar en el Inbox."""
        if not self.vault:
            return []
        rutas = []
        for carpeta in [self.carpeta_proyectos, *self.carpetas_sueltas]:
            base = self.vault / carpeta
            if base.is_dir():
                rutas += [str(base)] + [str(p) for p in _carpetas(base)]
        return list(dict.fromkeys(rutas))

    def uri(self, tarea):
        if not self.vault:
            return ""
        archivo = str(Path(tarea.donde).with_suffix(""))
        return f"obsidian://open?vault={quote(self.vault.name)}&file={quote(archivo)}"

    def carpetas_propias(self):
        return [self.vault] if self.vault else []

    # --- lectura de archivos ------------------------------------------

    def _leer(self, ruta, avisos=None, nombre=None):
        """Las líneas de una nota, o ninguna si no se puede leer.

        Una nota rota no debe tumbar el escaneo del vault entero, pero tampoco desaparecer sin
        que nadie se entere: sus tareas dejan de existir para Cotejo y eso se ve exactamente
        igual que si nunca se hubieran escrito. Por eso el fallo se anota en `avisos`.
        """
        try:
            texto = ruta.read_text(encoding="utf-8")
            # Lo que pesó, para el medidor de ahorro. Va en un diccionario por nota y no en un
            # contador porque la nota principal se lee dos veces —una para el frontmatter y
            # otra para las tareas— y contarla dos veces inflaría justo la mitad cara del
            # número. Es un `len` sobre un texto que ya está en memoria: no abre nada.
            self._leido[str(nombre or ruta)] = len(texto)
            return texto.splitlines()
        except UnicodeDecodeError:
            _anotar_aviso(avisos, nombre or ruta, "no está en UTF-8, así que no pude leerla")
        except OSError as error:
            _anotar_aviso(avisos, nombre or ruta, f"no pude abrirla ({error.strerror or error})")
        return []


def _hoy():
    """La fecha de hoy en AAAA-MM-DD, aparte para que las pruebas la fijen sin tocar el reloj."""
    return time.strftime("%Y-%m-%d")


def _vaults_registrados():
    """Los vaults de `obsidian.json`, el abierto primero y luego el más reciente."""
    try:
        vaults = json.loads(rutas.obsidian().read_text(encoding="utf-8")).get("vaults", {}).values()
        vaults = [v for v in vaults if isinstance(v, dict) and isinstance(v.get("path"), str)]
    except (OSError, ValueError, AttributeError):
        return []
    return sorted(vaults, key=lambda v: (not v.get("open"), -(v.get("ts") or 0)))


def vault_abierto():
    """El vault abierto en Obsidian, o el primero registrado."""
    vaults = _vaults_registrados()
    return vaults[0]["path"] if vaults else None


def vault_valido():
    """El primer vault de `obsidian.json` que existe de verdad como carpeta, o None.

    Obsidian no borra de su lista un vault cuya carpeta ya no está, así que «hay un vault
    registrado» no basta para decir que hay uno que Cotejo pueda leer.
    """
    return next((v["path"] for v in _vaults_registrados() if Path(v["path"]).is_dir()), None)


def leer_frontmatter(lineas):
    """Solo las claves escalares de primer nivel; basta para estado y prioridad."""
    datos = {}
    if not lineas or lineas[0].strip() != "---":
        return datos
    for linea in lineas[1:]:
        if linea.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", linea)
        if m:
            datos[m.group(1)] = m.group(2).strip().strip("'\"")
    return datos


def leer_tareas(ruta_rel, lineas, incluir_hechas=False, sub=""):
    tareas = []
    en_codigo = False
    for i, linea in enumerate(lineas):
        if FENCE_RE.match(linea):
            en_codigo = not en_codigo
            continue
        if en_codigo:
            continue
        m = TASK_RE.match(linea)
        if not m or not m.group(4):
            continue
        hecha = m.group(2) != " "
        if hecha and not incluir_hechas:
            continue
        tarea = _tarea(m.group(4), ruta_rel, i, linea, hecha, sub)
        if tarea is not None:
            tareas.append(tarea)
    return tareas


def _tarea(texto, ruta_rel, i, linea, hecha, sub):
    """Saca los tags de estado, agente, dificultad y versión: se guardan aparte y no se
    muestran."""
    estado = PENDIENTE
    m = ESTADO_RE.search(texto)
    if m:
        estado = m.group(1)
        texto = ESTADO_RE.sub("", texto)
    agente = ""
    m = AGENTE_RE.search(texto)
    if m:
        agente = m.group(1)
        texto = AGENTE_RE.sub("", texto)
    dificultad = ""
    m = DIFICULTAD_RE.search(texto)
    if m:
        dificultad = m.group(1)
        texto = DIFICULTAD_RE.sub("", texto)
    texto, version = _sacar_version(texto)
    # La marca va al final de todo, después de los tags: se saca al final para encontrarla
    # igual si alguien dejó un tag detrás de ella.
    texto, marca = _sacar_marca(texto)
    # La fecha de cierre, si la línea trae una: no se saca de `texto` (se sigue viendo, como
    # hasta ahora, y como la escribió una persona o `marcar`), solo se lee aparte.
    m = FECHA_RE.search(texto)
    cerrada = m.group(1) if m else None
    texto = texto.strip()
    if not texto:
        return None
    sitio = Sitio(ruta_rel, i, linea, marca)
    # Sin marca todavía, la tarea se nombra por su nota y su número de línea, que sí se mueve;
    # gana la marca la primera vez que se le escribe.
    return Tarea(texto, id=marca or f"{ruta_rel}:{i}", donde=str(ruta_rel), sub=sub,
                 estado=estado, agente=agente, dificultad=dificultad, hecha=hecha,
                 cerrada=cerrada, version=version, sitio=sitio)


def _sacar_version(texto):
    """(texto sin sus tags de versión, la primera versión válida o ""). Una que no lo es
    (`#v01.2`) se queda en el texto, a la vista."""
    encontradas = []

    def quitar(m):
        valida = versiones.de_tarea(m.group(1))
        if not valida:
            return m.group(0)
        encontradas.append(valida)
        return ""
    texto = VERSION_RE.sub(quitar, texto)
    return texto, (encontradas[0] if encontradas else "")


def _sacar_marca(cuerpo):
    """Parte la línea en lo que dice y su marca de bloque: ("- [ ] algo", "cotejo-a1b2")."""
    m = MARCA_RE.search(cuerpo)
    if not m:
        return cuerpo, ""
    return cuerpo[:m.start()], m.group(1)


def _marca_nueva(lineas):
    """Una marca que no esté ya en la nota.

    Seis caracteres y no cuatro porque la unicidad solo se comprueba dentro de la nota: para
    saber si otra nota ya la usa habría que releer el vault entero en cada escritura, y no
    vale la pena. Con 36^6 el choque entre notas deja de ser plausible, y si aun así ocurre,
    `modelo.buscar()` lo ve y se niega en vez de escribir en la tarea equivocada.
    """
    usadas = {m.group(1) for m in (MARCA_RE.search(l) for l in lineas) if m}
    while True:
        marca = PREFIJO_MARCA + "".join(random.choices(ALFABETO_MARCA, k=6))
        if marca not in usadas:
            return marca


def _fin_de_las_tareas(lineas):
    """Justo después de la última tarea de la nota; si no hay ninguna, debajo de su
    encabezado de tareas (`## ✅ Tareas`, `## Tasks`); y si tampoco lo hay, al final.

    Una tarea nueva va con las otras y no al final del archivo: debajo de la lista, en una
    nota de proyecto, viven las decisiones y los enlaces, y colar un `- [ ]` ahí deja la nota
    rara en Obsidian aunque Cotejo la siga leyendo igual. Una nota recién sacada de la
    plantilla tiene la sección vacía, y la primera tarea es la que más cuenta que caiga en
    ella (cotejo-n9mou2).
    """
    ultima = encabezado = None
    en_codigo = False
    for i, linea in enumerate(lineas):
        if FENCE_RE.match(linea):
            en_codigo = not en_codigo
            continue
        if en_codigo:
            continue
        if TASK_RE.match(linea):
            ultima = i
        elif encabezado is None and ENCABEZADO_TAREAS_RE.match(linea):
            encabezado = i
    if ultima is not None:
        return ultima + 1
    return len(lineas) if encabezado is None else encabezado + 1


def _salto(lineas, indice):
    """El salto de línea que usa la nota, mirando a su vecina. Sin pistas, `\\n`."""
    for vecina in (lineas[indice - 1] if indice else "", lineas[0] if lineas else ""):
        if vecina.endswith("\r\n"):
            return "\r\n"
        if vecina.endswith("\n"):
            return "\n"
    return "\n"


def _localizar(lineas, sitio):
    """En qué línea está hoy la tarea, o None si ya no está. Con marca se la busca por ella,
    así que la encuentra aunque se haya movido; sin marca solo queda el número de línea."""
    if sitio.marca:
        for i, linea in enumerate(lineas):
            m = MARCA_RE.search(linea)
            if m and m.group(1) == sitio.marca:
                return i
        return None
    return sitio.linea if sitio.linea < len(lineas) else None


def _carpeta_valida(carpeta):
    """Una carpeta del vault, relativa a su raíz. Una absoluta o con «..» leería (y luego
    escribiría) notas fuera del vault, que es lo único que esta fuente promete no hacer."""
    if not isinstance(carpeta, str) or not carpeta.strip().strip("/"):
        return False
    ruta = Path(carpeta.strip())
    return not ruta.is_absolute() and ".." not in ruta.parts


# Carpetas de herramientas que nunca son notas aunque lleven `.md` dentro.
_NO_SON_NOTAS = {"node_modules"}


def _se_salta(carpeta):
    """Una subcarpeta que no es del segundo cerebro: oculta, `node_modules` o la raíz de un
    repo de código anidado en la carpeta del proyecto (su `.git` es carpeta en un clon y
    archivo en un worktree o un submódulo). Sus `.md` son READMEs y CHANGELOGs, y sus
    casillas no son tareas de nadie."""
    return (carpeta.name.startswith(".") or carpeta.name in _NO_SON_NOTAS
            or os.path.lexists(carpeta / ".git"))


def _carpetas(base):
    """Las subcarpetas de `base` que pueden tener notas, sin entrar en las que se saltan: un
    `node_modules` puede tener decenas de miles de archivos. `base` misma nunca se salta,
    aunque sea un repo: es la carpeta que se pidió leer."""
    for raiz, dirs, _ in os.walk(base):
        raiz = Path(raiz)
        dirs[:] = sorted(d for d in dirs if not _se_salta(raiz / d))
        for d in dirs:
            yield raiz / d


def _notas(base):
    """Los `.md` de `base` y de sus subcarpetas, salvo los que caen en una que se salta."""
    for carpeta in [base, *_carpetas(base)]:
        for archivo in carpeta.glob("*.md"):
            if not archivo.name.startswith(".") and archivo.is_file():
                yield archivo


def _anotar_aviso(avisos, nombre, motivo):
    if avisos is not None:
        avisos.append({"nota": str(nombre), "motivo": motivo})
