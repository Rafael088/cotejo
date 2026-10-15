"""Arma Cotejo para Windows: una carpeta con su propio Python y su GTK, y su instalador .exe.

    python3 empaquetado/windows/construir.py [--version X] [--salida DIR]

Corre en Linux, macOS o Windows, y deja en `construido/` (junto a este archivo):

- `Cotejo/`, la instalación entera, relocalizable:
  `bin/` los comandos (`cotejo.exe`, `cotejoboard.exe` y los nombres de antes), `interno/` los
  que no van al PATH, `app/` el código de Cotejo, `runtime/` Python, PyGObject, GTK 4 y
  libadwaita, y `cotejo.ico`;
- `Cotejo-<version>-windows-x64-instalador.exe`, si hay Inno Setup (`iscc`), que es lo único
  que no existe fuera de Windows. Sin él lo dice y deja el comando para compilarlo allí.

No hay ZIP portable: Cotejo es sobre todo la CLI de los agentes, y sin PATH ni aviso a los
agentes una carpeta suelta no sirve para eso. El instalador es para el usuario y no pide
administrador, que era lo único que la carpeta suelta daba de más.

**El runtime sale de MSYS2** (UCRT64), que es de donde sale GTK para Windows en todas partes:
se lee el índice del repositorio, se resuelven las dependencias de `PAQUETES`, se descarga
cada paquete, se comprueba su SHA-256 contra el índice y se desempaqueta. No hace falta tener
MSYS2 instalado ni estar en Windows, y lo descargado se guarda en `cache/`.

Lo que pacman haría al instalar y aquí no corre: los esquemas de GSettings se compilan con
`glib-compile-schemas` (el del runtime en Windows, el del sistema fuera; el formato es el
mismo), y la caché de cargadores de gdk-pixbuf no se genera, porque llevaría rutas absolutas:
el lanzador apunta `GDK_PIXBUF_MODULEDIR` a la carpeta y gdk-pixbuf los busca ahí.

**Nada GPL en el proceso**: jbigkit y lzo2 no se bajan y en su sitio va una DLL propia que no
hace nada (`SUSTITUTAS`); los programas GPL de otros paquetes se podan (`PODAR_PROGRAMAS`), y
un paquete nuevo que nombre la GPL para la construcción hasta que esté en `GPL_REVISADOS`.

**Los lanzadores** son `lanzador.c`, compilado con clang y lld-link (LLVM) sin SDK de Windows:
las bibliotecas de importación se generan aquí con `llvm-dlltool`. Qué corre cada comando se
le pega al final del .exe (`carga()`), y la lista está en `LANZADORES` y en ningún otro sitio.

No toca nada fuera de `--salida` y `--cache`, y no instala nada en esta máquina.
"""

import argparse
import contextlib
import gzip
import hashlib
import io
import lzma
import os
import re
import shutil
import ssl
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent

ESPEJO = "https://repo.msys2.org/mingw/ucrt64"
FUENTES = "https://repo.msys2.org/mingw/sources"
REPOSITORIO = "ucrt64"
PREFIJO = "mingw-w64-ucrt-x86_64-"
# Lo que Cotejo necesita; el resto lo trae la resolución de dependencias.
PAQUETES = ("python", "python-gobject", "python-cairo", "gtk4", "libadwaita", "librsvg",
            "adwaita-icon-theme")
# Librerías GPL sin excepción de enlace que GTK carga en el proceso de Cotejo, que es
# propietario, aunque Cotejo no las use nunca: jbigkit la importa libtiff (y a libtiff, GTK 4 y
# gdk-pixbuf) para los TIFF con JBIG; lzo2, el intérprete de scripts de cairo (y a ese, GTK 4).
# No se bajan: en su lugar va una DLL propia con el mismo nombre y los mismos símbolos, que no
# hace nada (`sustitutas/<paquete>.c`). Sin una DLL con ese nombre, Windows no abre el board.
SUSTITUTAS = {"jbigkit": "libjbig-0.dll", "lzo2": "liblzo2-2.dll"}
# Dependencias que se cortan, con su porqué: python pide tcl y tk para tkinter, que Cotejo no
# usa; las de SUSTITUTAS se reemplazan.
EXCLUIDOS = ("tcl", "tk", *SUSTITUTAS)
# Paquetes cuya licencia nombra la GPL (no la LGPL) y por qué pueden ir igual. Uno nuevo hace
# fallar la construcción hasta que alguien lo revise y lo apunte aquí: o se poda lo GPL, o va a
# SUSTITUTAS, o se explica por qué no entra en el proceso de Cotejo.
GPL_REVISADOS = {
    "ca-certificates": "datos MPL; lo GPL es update-ca-trust, que se poda",
    "gettext-runtime": "libintl es LGPL; los programas GPL se podan",
    "gmp": "la librería es LGPL-3.0 o GPL-2.0, a elegir",
    "gnutls": "libgnutls es LGPL; libgnutls-openssl y los programas, GPL, se podan",
    "hicolor-icon-theme": "datos (index.theme), no código",
    "libiconv": "la librería es LGPL; lo GPL es la documentación",
    "libidn2": "la librería es LGPL-3.0 o GPL-2.0, a elegir; idn2.exe se poda",
    "libtasn1": "la librería es LGPL; los programas asn1*, GPL, se podan",
    "nettle": "las librerías son LGPL-3.0 o GPL-2.0, a elegir; los programas se podan",
    "shared-mime-info": "datos; update-mime-database.exe, GPL, se poda",
    "xz": "liblzma es 0BSD; los scripts xz*, GPL, se podan",
    "freetype": "GPL-2.0 o FTL, a elegir: se usa la FTL",
    "zstd": "BSD-3-Clause o GPL-2.0, a elegir: se usa la BSD",
    "libunistring": "LGPL-3.0 o GPL-3.0, a elegir: se usa la LGPL",
    "cc-libs": "runtime de GCC, con la GCC Runtime Library Exception",
    "libgcc": "runtime de GCC, con la GCC Runtime Library Exception",
    "libatomic": "runtime de GCC, con la GCC Runtime Library Exception",
    "libstdc++": "runtime de GCC, con la GCC Runtime Library Exception",
}

# El código de Cotejo, lo mismo que copia install.sh; y los datos de la interfaz.
DE_LA_APP = ("tareas", "enrutador", "skills", "extras")
DATOS = ("marca", "iconos", "temas", "fonts")
SUELTOS = ("LICENSE", "THIRD-PARTY-NOTICES", "README.md")
ICONO_APP = "io.github.cotejoapp.Cotejo.svg"

# Comando → (orden, ¿de ventana?). La orden es `-m modulo` o `@ruta\relativa\a\app`.
# Solo los nombres de hoy. `tareas-obsidian`, `foco` y `foco-notion` son compatibilidad con
# instalaciones de Linux de antes del cambio de nombre; en Windows no hubo ninguna.
LANZADORES = {
    "bin/cotejo": ("-m tareas", False),
    "bin/cotejoboard": ("-m tareas.board", True),
    "bin/cotejo-notion": ("@extras\\notion\\cotejo_notion.py", False),
    # Fuera del PATH: el instalador lo corre para avisar a los agentes (y al desinstalar).
    "interno/cotejo-agentes": ("-m tareas.skill", False),
}
MAGIA = b"COTEJO01"

# Lo que un runtime no necesita para correr: cabeceras, estáticas, documentación.
PODAR_CARPETAS = ("include", "share/doc", "share/man", "share/info", "share/gtk-doc",
                  "lib/pkgconfig", "lib/cmake", "share/aclocal", "share/gir-1.0")
PODAR_SUFIJOS = (".a", ".la")
# Programas de demostración y de consola que traen los paquetes y Cotejo no llama.
PODAR_PROGRAMAS = ("gtk4-demo.exe", "gtk4-demo-application.exe", "gtk4-widget-factory.exe",
                   "gtk4-node-editor.exe", "gtk4-print-editor.exe", "gtk4-rendernode-tool.exe",
                   "adwaita-1-demo.exe", "rsvg-convert.exe", "sqlite3.exe",
                   # Bajo GPL (ver GPL_REVISADOS): no entran en el proceso, pero tampoco se
                   # reparten. libgnutls-openssl no la importa nadie.
                   "libgnutls-openssl-27.dll", "certtool.exe", "gnutls-cli.exe",
                   "gnutls-cli-debug.exe", "gnutls-serv.exe", "ocsptool.exe", "p11tool.exe",
                   "psktool.exe", "nettle-hash.exe", "nettle-lfib-stream.exe", "nettle-pbkdf2.exe",
                   "pkcs1-conv.exe", "sexp-conv.exe", "asn1Coding.exe", "asn1Decoding.exe",
                   "asn1Parser.exe", "idn2.exe", "envsubst.exe", "gettext.exe", "ngettext.exe",
                   "printf_gettext.exe", "printf_ngettext.exe", "gettext.sh",
                   "update-mime-database.exe", "update-mime-database.exe.manifest",
                   "update-ca-trust", "xzcmp", "xzdiff", "xzegrep", "xzfgrep", "xzgrep", "xzless",
                   "xzmore")
# Las traducciones de GTK que se quedan: Cotejo está en español, y el inglés de respaldo.
IDIOMAS = ("es", "en")

# Las funciones de Win32 que usa lanzador.c, por DLL. Si el lanzador usa una nueva, va aquí.
IMPORTACIONES = {
    "kernel32": ("GetModuleFileNameW", "GetCommandLineW", "SetEnvironmentVariableW",
                 "GetEnvironmentVariableW", "CreateFileW", "ReadFile", "SetFilePointerEx",
                 "CloseHandle", "GetFileAttributesW", "CreateProcessW", "WaitForSingleObject",
                 "GetExitCodeProcess", "GetStdHandle", "ExitProcess", "SetConsoleCtrlHandler",
                 "WriteConsoleW", "WriteFile", "WideCharToMultiByte"),
    "user32": ("MessageBoxW",),
}


class ErrorDeConstruccion(Exception):
    """Algo que impide construir, dicho de forma que se pueda arreglar."""


def avisar(texto):
    print(texto, file=sys.stderr, flush=True)


# --- El runtime: el índice de MSYS2 y sus paquetes ------------------------------------------

@dataclass
class Paquete:
    nombre: str
    archivo: str
    sha256: str
    depende: list = field(default_factory=list)
    provee: list = field(default_factory=list)
    licencia: str = ""
    # El paquete fuente de MSYS2 (%BASE% y %VERSION% del índice) no siempre se llama como el
    # binario (gtk-update-icon-cache sale de mingw-w64-gtk3, python-gobject de mingw-w64-pygobject):
    # con esto se arma el nombre de su .src.tar.zst en FUENTES (H8, H11).
    base: str = ""
    version: str = ""


BLOQUE = 1 << 20  # de a 1 MB: ningún paquete entero en memoria


@contextlib.contextmanager
def abrir_tar(origen):
    """Un .tar comprimido con zstd (lo de MSYS2), gzip o xz, leído en streaming.

    `origen` es una ruta o los bytes ya en memoria (las pruebas). El paquete se descomprime a
    medida que se lee y el tar se recorre una sola vez (`r|`): nunca está entero en RAM. Así no
    se repite lo del 2026-09-27, cuando descomprimir cada paquete entero en memoria llevó la
    construcción a 2,6 GB y el OOM killer se llevó la sesión.
    """
    with contextlib.ExitStack() as pila:
        crudo = pila.enter_context(open(origen, "rb") if isinstance(origen, Path)
                                   else io.BytesIO(origen))
        magia = crudo.read(6)
        crudo.seek(0)
        if magia[:4] == b"\x28\xb5\x2f\xfd":
            flujo = pila.enter_context(_zstd(crudo, origen))
        elif magia[:2] == b"\x1f\x8b":
            flujo = pila.enter_context(gzip.GzipFile(fileobj=crudo))
        elif magia == b"\xfd7zXZ\x00":
            flujo = pila.enter_context(lzma.LZMAFile(crudo))
        else:
            flujo = crudo
        yield pila.enter_context(tarfile.open(fileobj=flujo, mode="r|"))


@contextlib.contextmanager
def _zstd(crudo, origen):
    try:
        from compression import zstd  # Python 3.14
        with zstd.ZstdFile(crudo) as flujo:
            yield flujo
        return
    except ImportError:
        pass
    try:
        import zstandard
        with zstandard.ZstdDecompressor().stream_reader(crudo) as flujo:
            yield flujo
        return
    except ImportError:
        pass
    if not shutil.which("zstd"):
        raise ErrorDeConstruccion("Para leer los paquetes de MSYS2 hace falta zstd: Python 3.14, "
                                  "el módulo zstandard o el comando zstd.")
    # stdin desde el archivo (o un temporal, si son bytes): nada pasa entero por este proceso.
    with contextlib.ExitStack() as pila:
        if isinstance(origen, Path):
            entrada = pila.enter_context(open(origen, "rb"))
        else:
            entrada = pila.enter_context(tempfile.TemporaryFile())
            entrada.write(origen)
            entrada.seek(0)
        proceso = subprocess.Popen(["zstd", "-dc"], stdin=entrada, stdout=subprocess.PIPE)
        try:
            yield proceso.stdout
        finally:
            proceso.stdout.close()
            if proceso.wait():
                raise ErrorDeConstruccion("zstd no pudo descomprimir el paquete.")


def _sin_version(dependencia):
    for signo in "<>=":
        dependencia = dependencia.split(signo, 1)[0]
    return dependencia.strip()


def leer_indice(origen):
    """El índice del repositorio (`ucrt64.db`, ruta o bytes) como {nombre: Paquete}."""
    indice = {}
    with abrir_tar(origen) as tar:
        for miembro in tar:
            if not miembro.isfile() or not miembro.name.endswith("/desc"):
                continue
            campos, clave = {}, None
            for linea in tar.extractfile(miembro).read().decode("utf-8").splitlines():
                if linea.startswith("%") and linea.endswith("%"):
                    clave = linea.strip("%")
                    campos[clave] = []
                elif linea and clave:
                    campos[clave].append(linea)
            nombre = campos["NAME"][0]
            indice[nombre] = Paquete(nombre, campos["FILENAME"][0], campos["SHA256SUM"][0],
                                     [_sin_version(d) for d in campos.get("DEPENDS", [])],
                                     [_sin_version(p) for p in campos.get("PROVIDES", [])],
                                     " AND ".join(campos.get("LICENSE", [])),
                                     campos.get("BASE", [nombre])[0],
                                     campos.get("VERSION", [""])[0])
    return indice


def resolver(indice, pedidos=PAQUETES, excluidos=EXCLUIDOS):
    """Los paquetes que hay que bajar para `pedidos`, con todas sus dependencias.

    Las dependencias se nombran sin versión (el índice solo tiene la última de cada una) y
    pueden apuntar a un paquete o a algo que otro `provee`. Las que no están se juntan y se
    dicen todas a la vez, que es más útil que parar en la primera.
    """
    proveedores = {}
    for paquete in indice.values():
        for provisto in paquete.provee:
            proveedores.setdefault(provisto, paquete.nombre)
    fuera = {PREFIJO + e for e in excluidos}
    pendientes = [PREFIJO + p for p in pedidos]
    elegidos, faltan = {}, []
    while pendientes:
        nombre = pendientes.pop()
        nombre = nombre if nombre in indice else proveedores.get(nombre, nombre)
        if nombre in elegidos or nombre in fuera:
            continue
        if nombre not in indice:
            faltan.append(nombre)
            continue
        elegidos[nombre] = indice[nombre]
        pendientes.extend(indice[nombre].depende)
    if faltan:
        raise ErrorDeConstruccion("El repositorio no tiene: " + ", ".join(sorted(set(faltan))))
    return sorted(elegidos.values(), key=lambda p: p.nombre)


def gpl_sin_revisar(paquetes):
    """Los paquetes cuya licencia nombra la GPL (no la LGPL) y no están en GPL_REVISADOS."""
    return [p.nombre for p in paquetes
            if re.search(r"(?<!L)GPL", p.licencia)
            and p.nombre.removeprefix(PREFIJO) not in GPL_REVISADOS]


def _sha256(ruta):
    suma = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        while bloque := archivo.read(BLOQUE):
            suma.update(bloque)
    return suma.hexdigest()


def _bajar_a(url, parcial, suma, contexto=None):
    """Baja `url` a `parcial` de a trozos, sumando el SHA-256 por el camino."""
    with urllib.request.urlopen(url, timeout=120, context=contexto) as respuesta, \
            open(parcial, "wb") as salida:
        while bloque := respuesta.read(BLOQUE):
            suma.update(bloque)
            salida.write(bloque)


def bajar(url, cache, sha256=None):
    """La ruta en `cache` de lo que hay en `url`: la de antes si cuadra con `sha256`.

    Se baja a disco de a trozos, calculando el SHA-256 por el camino; lo que no cuadra no llega
    a llamarse como el paquete.
    """
    destino = cache / url.rsplit("/", 1)[1]
    if destino.exists() and sha256 and _sha256(destino) == sha256:
        return destino
    avisar(f"  bajando {url}")
    cache.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".parcial")
    suma = hashlib.sha256()
    try:
        try:
            _bajar_a(url, parcial, suma)
        except urllib.error.URLError as error:
            if not isinstance(error.reason, ssl.SSLCertVerificationError):
                raise
            # Un Windows recién instalado puede no tener aún el intermedio de la cadena de
            # repo.msys2.org (Let's Encrypt YE1 → Root YE → ISRG Root X2): SChannel lo baja
            # solo, el OpenSSL de Python no. `truststore` verifica con el propio Windows.
            try:
                import truststore
            except ImportError:
                raise ErrorDeConstruccion(
                    f"No pude verificar el certificado de {url} ({error.reason}). En un Windows "
                    "recién instalado suele faltar un certificado intermedio que Python no baja "
                    "solo: `python -m pip install truststore` y vuelve a construir.") from None
            suma = hashlib.sha256()
            _bajar_a(url, parcial, suma, truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
        if sha256 and suma.hexdigest() != sha256:
            raise ErrorDeConstruccion(f"{destino.name}: el SHA-256 no es el que dice el índice. "
                                      "No se usa; borra la caché y vuelve a intentarlo.")
        parcial.replace(destino)
    finally:
        parcial.unlink(missing_ok=True)
    return destino


def desempaquetar(origen, runtime):
    """Pone los archivos de un paquete (ruta o bytes) en `runtime`, sin el prefijo `ucrt64/`.

    Se extrae miembro a miembro según se lee. Los enlaces (duros, como `libdeflate-gunzip.exe`,
    o simbólicos) se ponen al final como copias: Inno Setup no los guarda y en Windows un
    simbólico pide permisos que el usuario no tiene.

    Devuelve las rutas (relativas a `runtime`) de los archivos que puso, sin las carpetas: es lo
    que `armar_runtime` usa para saber, después de podar, si algo del paquete sigue repartiéndose
    (H8: a uno que no dejó nada no hace falta pedirle su licencia).
    """
    prefijo = REPOSITORIO + "/"
    enlaces, escritos = [], []
    with abrir_tar(origen) as tar:
        for miembro in tar:
            if not miembro.name.startswith(prefijo) or miembro.name == prefijo:
                continue  # .PKGINFO, .MTREE, .INSTALL: de pacman, no del programa
            miembro.name = miembro.name[len(prefijo):]
            if miembro.islnk() or miembro.issym():
                enlaces.append(miembro)
            else:
                tar.extract(miembro, runtime, filter="data")
                if miembro.isfile():
                    escritos.append(miembro.name)
    for enlace in enlaces:
        destino = runtime / enlace.name
        if enlace.islnk():  # relativo a la raíz del paquete
            origen = runtime / enlace.linkname.removeprefix(prefijo)
        else:  # relativo a su carpeta
            origen = destino.parent / enlace.linkname
        origen = origen.resolve()
        if not origen.is_relative_to(runtime.resolve()) or not origen.is_file():
            raise ErrorDeConstruccion(f"{enlace.name} apunta a {enlace.linkname}, que no está "
                                      "en el paquete.")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origen, destino)
        escritos.append(enlace.name)
    return escritos


LICENCIAS_GENERALES = {
    # destino en licenses/ : encabezado que identifica el texto dentro de un archivo del runtime
    # (las primeras líneas, con los saltos y espacios normalizados; ver `poner_licencias_generales`).
    "LGPL-2.1.txt": "GNU LESSER GENERAL PUBLIC LICENSE Version 2.1",
    # La LGPL-3.0 (gmp, nettle, libidn2) remite a la GPL-3.0 para sus términos base (su propio
    # preámbulo lo dice: "incorporates the terms and conditions of version 3 of the GNU General
    # Public License"), así que hace falta el texto de las dos (H8, LGPL-3 residual).
    "LGPL-3.0.txt": "GNU LESSER GENERAL PUBLIC LICENSE Version 3",
    "GPL-3.0.txt": "GNU GENERAL PUBLIC LICENSE Version 3",
}


def poner_licencias_generales(carpeta):
    """`licenses/<LGPL-2.1|LGPL-3.0|GPL-3.0>.txt`, que THIRD-PARTY-NOTICES promete.

    Cada una es una copia textual de la que ya trae algún paquete del runtime en
    `share/licenses/<paquete>/`, para no guardar en el repo un texto que nadie actualiza. Con
    H8 completando lo que faltaba ahí, siempre hay de dónde sacar las tres: si alguna
    desaparece (porque cambió el runtime), es mejor que la construcción falle a que
    THIRD-PARTY-NOTICES remita a un archivo que no está.
    """
    archivos = sorted((carpeta / "runtime" / "share" / "licenses").rglob("*"))
    textos = {ruta: " ".join(ruta.read_text(encoding="utf-8", errors="replace")[:400].split())
              for ruta in archivos if ruta.is_file()}
    hechos = {}
    for nombre, encabezado in LICENCIAS_GENERALES.items():
        encontrado = next((ruta for ruta, texto in textos.items() if encabezado in texto), None)
        if not encontrado:
            raise ErrorDeConstruccion(f"Ningún paquete del runtime trae el texto de {encabezado}, "
                                      f"y THIRD-PARTY-NOTICES remite a licenses/{nombre}.")
        destino = carpeta / "licenses" / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(encontrado, destino)
        hechos[nombre] = destino
    return hechos


# --- H8: la licencia de un paquete que el binario no trae, sacada de su código fuente -------

LICENCIA_FUENTE = re.compile(r"^(COPYING|LICEN[CS]E|COPYRIGHT)", re.IGNORECASE)
# Extensiones que descartan un falso positivo (un .c o un .py que empiece por «copying», que no
# se ha visto nunca, pero mejor curarse en salud que confundirlo con el texto de una licencia).
_NO_ES_LICENCIA = (".c", ".h", ".py", ".pl", ".sh", ".cmake", ".in", ".am", ".ac")


def bajar_fuente(paquete, fuentes, cache):
    """El `.src.tar.zst` de MSYS2 del paquete fuente de `paquete` (PKGBUILD, parches y el
    código original): se publica por paquete fuente, con `%BASE%` y `%VERSION%` del índice, no
    por binario (gtk-update-icon-cache viene de mingw-w64-gtk3, python-gobject de
    mingw-w64-pygobject). El índice de binarios no trae su SHA-256, así que no se comprueba.
    """
    return bajar(f"{fuentes.rstrip('/')}/{paquete.base}-{paquete.version}.src.tar.zst", cache)


def _fuente_principal(ruta_src):
    """Los bytes del código fuente original dentro de un `.src.tar.zst`: el archivo más grande
    que no sea el PKGBUILD, un parche o una firma. Se lee en streaming (`abrir_tar`) y solo se
    queda en memoria el candidato más grande visto hasta el momento, nunca el paquete entero.
    """
    mejor_tamano, mejor_datos = -1, None
    with abrir_tar(ruta_src) as tar:
        for miembro in tar:
            if not miembro.isfile():
                continue
            nombre = Path(miembro.name).name
            if nombre in ("PKGBUILD", ".SRCINFO") or nombre.endswith(
                    (".patch", ".diff", ".sig", ".asc")):
                continue
            if miembro.size > mejor_tamano:
                mejor_tamano, mejor_datos = miembro.size, tar.extractfile(miembro).read()
    if mejor_datos is None:
        raise ErrorDeConstruccion(f"{ruta_src}: no encontré el código fuente original dentro.")
    return mejor_datos


def _candidatos_de_licencia(tar):
    """Los `COPYING`/`LICENSE`/`COPYRIGHT` de la raíz de un `tar` ya abierto.

    Si el proyecto no trae ninguno ahí (como el paquete de datos de ca-certificates, que
    reempaqueta el certdata.txt de Mozilla sin su propio COPYING), se usa `debian/copyright`,
    que es donde Debian documenta la licencia de lo que no la trae consigo.
    """
    raiz = [m for m in tar.getmembers()
            if m.isfile() and m.name.count("/") <= 1
            and LICENCIA_FUENTE.match(Path(m.name).name)
            and not Path(m.name).name.lower().endswith(_NO_ES_LICENCIA)]
    if raiz:
        return raiz
    return [m for m in tar.getmembers() if m.isfile() and m.name.endswith("debian/copyright")]


def licencias_del_paquete_fuente(ruta_src):
    """{nombre de archivo: bytes} de las licencias que trae el código fuente de `ruta_src`."""
    datos = _fuente_principal(ruta_src)
    with tarfile.open(fileobj=io.BytesIO(datos), mode="r:*") as interno:
        candidatos = _candidatos_de_licencia(interno)
        return {Path(m.name).name: interno.extractfile(m).read() for m in candidatos}


# Paquetes cuya carpeta en `share/licenses/` no se llama como el paquete: Python la deja en
# `python<mayor>.<menor>/`, no en `python/` (lo mismo que mira `comprobar()` al llamarlo). Sin
# esto, H8 no la encontraría y la bajaría del código fuente otra vez, de más.
ALIAS_CARPETA_LICENCIA = {"python": lambda version: "python" + ".".join(version.split(".")[:2])}


def _tiene_licencia(carpeta_licencias, nombre, version):
    alias = ALIAS_CARPETA_LICENCIA.get(nombre)
    candidatos = (nombre,) if not alias else (nombre, alias(version))
    return any((carpeta_licencias / c).is_dir() and any((carpeta_licencias / c).iterdir())
               for c in candidatos)


def completar_licencias(runtime, paquetes, presentes, fuentes, cache):
    """Para cada paquete que de verdad reparte algo y el binario no trae su licencia, la saca de
    su código fuente (H8). `presentes` son los nombres (sin el prefijo) de los paquetes que
    dejaron al menos un archivo en `runtime` después de podar: uno que no dejó nada (como
    egl-headers o gles-headers, que son solo cabeceras que `podar` quita enteras) no reparte
    nada suyo, y pedirle su licencia sería trabajo —y una descarga— sin ningún efecto.
    """
    carpeta_licencias = runtime / "share" / "licenses"
    for paquete in paquetes:
        nombre = paquete.nombre.removeprefix(PREFIJO)
        if nombre not in presentes:
            continue
        if _tiene_licencia(carpeta_licencias, nombre, paquete.version):
            continue
        destino = carpeta_licencias / nombre
        avisar(f"  licencia de {nombre}: no la trae el binario, se saca de su código fuente")
        licencias = licencias_del_paquete_fuente(bajar_fuente(paquete, fuentes, cache))
        if not licencias:
            raise ErrorDeConstruccion(
                f"{nombre}: no encontré su licencia ni en el binario ni en su código fuente "
                f"({paquete.base}-{paquete.version}). Revísalo a mano.")
        destino.mkdir(parents=True, exist_ok=True)
        for archivo, datos in licencias.items():
            (destino / archivo).write_bytes(datos)


def podar(runtime):
    for carpeta in PODAR_CARPETAS:
        shutil.rmtree(runtime / carpeta, ignore_errors=True)
    for archivo in runtime.rglob("*"):
        if archivo.is_file() and archivo.suffix in PODAR_SUFIJOS:
            archivo.unlink()
    for programa in PODAR_PROGRAMAS:
        (runtime / "bin" / programa).unlink(missing_ok=True)
    for idioma in (runtime / "share" / "locale").glob("*"):
        if idioma.is_dir() and idioma.name.split("_")[0].split("@")[0] not in IDIOMAS:
            shutil.rmtree(idioma)
    for version in (runtime / "lib").glob("python3*"):
        shutil.rmtree(version / "test", ignore_errors=True)
    for cache in list(runtime.rglob("__pycache__")):
        shutil.rmtree(cache, ignore_errors=True)


def compilar_esquemas(runtime):
    """Lo que haría el `glib-compile-schemas` de la instalación de pacman."""
    esquemas = runtime / "share" / "glib-2.0" / "schemas"
    if not esquemas.is_dir():
        return
    propio = runtime / "bin" / "glib-compile-schemas.exe"
    comando = str(propio) if sys.platform == "win32" and propio.exists() else \
        shutil.which("glib-compile-schemas")
    if not comando:
        raise ErrorDeConstruccion("Hace falta glib-compile-schemas (paquete glib2) para "
                                  "compilar los esquemas de GSettings del runtime.")
    subprocess.run([comando, str(esquemas)], check=True)


def armar_runtime(runtime, espejo, cache, fuentes=FUENTES):
    avisar(f"Runtime: índice de {espejo}")
    indice = leer_indice(bajar(f"{espejo}/{REPOSITORIO}.db", cache))
    paquetes = resolver(indice)
    if revisar := gpl_sin_revisar(paquetes):
        raise ErrorDeConstruccion(
            "Estos paquetes nombran la GPL y nadie ha revisado si pueden ir junto a Cotejo, que "
            "es propietario: " + ", ".join(revisar) + ". Apúntalos en GPL_REVISADOS con su "
            "porqué, o en SUSTITUTAS si GTK los carga en el proceso.")
    avisar(f"Runtime: {len(paquetes)} paquetes")
    archivos_por_paquete = {
        paquete.nombre: desempaquetar(bajar(f"{espejo}/{paquete.archivo}", cache, paquete.sha256),
                                      runtime)
        for paquete in paquetes}
    podar(runtime)
    compilar_esquemas(runtime)
    # Lo que de verdad sigue repartiéndose después de podar (H8): a lo que no dejó nada (las
    # cabeceras de egl-headers y gles-headers, que `podar` quita enteras) no hace falta pedirle
    # su licencia.
    presentes = {paquete.nombre.removeprefix(PREFIJO) for paquete in paquetes
                 if any((runtime / ruta).exists() for ruta in archivos_por_paquete[paquete.nombre])}
    completar_licencias(runtime, paquetes, presentes, fuentes, cache)
    # Lo que THIRD-PARTY-NOTICES remite aquí: cada paquete, su huella, la licencia que declara y
    # el nombre de su paquete fuente (lo que fuentes_terceros.py usa para armar la oferta de
    # código, H11; no siempre es el mismo nombre que el binario).
    (runtime / "PAQUETES.txt").write_text(
        "".join(f"{p.archivo}  sha256:{p.sha256}  licencia:{p.licencia or '?'}  "
                f"fuente:{p.base}-{p.version}.src.tar.zst\n" for p in paquetes), encoding="utf-8")


# --- La app ---------------------------------------------------------------------------------

def _ignorar(_carpeta, nombres):
    return [n for n in nombres if n == "__pycache__" or n.endswith(".pyc")]


def copiar_app(app):
    for carpeta in DE_LA_APP:
        shutil.copytree(RAIZ / carpeta, app / carpeta, ignore=_ignorar)
    for carpeta in DATOS:
        shutil.copytree(RAIZ / "data" / carpeta, app / "data" / carpeta, ignore=_ignorar)
    for archivo in SUELTOS:
        shutil.copy2(RAIZ / archivo, app / archivo)
    # H7: Inno Setup muestra app\LICENSE en la página de licencia (LicenseFile, en cotejo.iss).
    # Sin BOM, un .txt con tildes puede leerlo con la página de códigos ANSI y mostrarlo con
    # mojibake («tÃ©rminos»); con BOM UTF-8, lo detecta y lo muestra bien. La copia del repo se
    # queda tal cual (sin BOM): `install.sh`, el PKGBUILD y `git archive`, en Linux, no lo piden.
    (app / "LICENSE").write_text((RAIZ / "LICENSE").read_text(encoding="utf-8"),
                                 encoding="utf-8-sig")
    # El ícono de la app, que el board le pone a su ventana (`Gtk.Window.set_default_icon_name`).
    shutil.copy2(RAIZ / "data" / ICONO_APP, app / "data" / ICONO_APP)


# --- Los lanzadores -------------------------------------------------------------------------

def carga(orden):
    """Lo que se pega al final del lanzador para que sepa qué correr (ver lanzador.c)."""
    texto = orden.encode("utf-16-le")
    return texto + struct.pack("<I", len(texto)) + MAGIA


def leer_carga(exe):
    """La orden pegada al final de un lanzador, o None si no la tiene."""
    if len(exe) < 12 or exe[-8:] != MAGIA:
        return None
    (largo,) = struct.unpack("<I", exe[-12:-8])
    return exe[-12 - largo:-12].decode("utf-16-le")


def subsistema(exe):
    """El subsistema de un PE: 3 de consola, 2 de ventana."""
    pe = struct.unpack("<I", exe[0x3C:0x40])[0]
    if exe[:2] != b"MZ" or exe[pe:pe + 4] != b"PE\0\0":
        raise ValueError("no es un ejecutable de Windows")
    return struct.unpack("<H", exe[pe + 24 + 68:pe + 24 + 70])[0]


def herramientas_llvm():
    faltan = [h for h in ("clang", "lld-link", "llvm-dlltool") if not shutil.which(h)]
    if faltan:
        raise ErrorDeConstruccion(f"Para compilar los lanzadores hace falta LLVM ({', '.join(faltan)}"
                                  "): en Linux, clang, lld y llvm; en Windows, winget install "
                                  "LLVM.LLVM.")


def compilar_lanzadores(trabajo):
    """{¿de ventana?: bytes del .exe}, compilado de `lanzador.c`."""
    herramientas_llvm()
    trabajo.mkdir(parents=True, exist_ok=True)
    for dll, funciones in IMPORTACIONES.items():
        definicion = trabajo / f"{dll}.def"
        definicion.write_text(f"LIBRARY {dll}.dll\nEXPORTS\n" + "\n".join(funciones) + "\n")
        subprocess.run(["llvm-dlltool", "-m", "i386:x86-64", "-d", str(definicion),
                        "-l", str(trabajo / f"{dll}.lib")], check=True)
    binarios = {}
    for ventana in (False, True):
        nombre = "ventana" if ventana else "consola"
        objeto, exe = trabajo / f"{nombre}.obj", trabajo / f"{nombre}.exe"
        subprocess.run(["clang", "--target=x86_64-pc-windows-msvc", "-O2", "-ffreestanding",
                        "-fno-builtin", "-fno-stack-protector", "-Wall", "-Werror",
                        *(["-DVENTANA"] if ventana else []),
                        "-c", str(AQUI / "lanzador.c"), "-o", str(objeto)], check=True)
        subprocess.run(["lld-link", "/nologo", "/entry:inicio", "/nodefaultlib",
                        f"/subsystem:{'windows' if ventana else 'console'}", str(objeto),
                        str(trabajo / "kernel32.lib"),
                        *([str(trabajo / "user32.lib")] if ventana else []),
                        f"/out:{exe}"], check=True)
        binarios[ventana] = exe.read_bytes()
    return binarios


def compilar_sustitutas(trabajo):
    """{nombre de la DLL: bytes}, compiladas de `sustitutas/<paquete>.c` (ver SUSTITUTAS)."""
    herramientas_llvm()
    trabajo.mkdir(parents=True, exist_ok=True)
    binarios = {}
    for paquete, dll in SUSTITUTAS.items():
        objeto, salida = trabajo / f"{paquete}.obj", trabajo / dll
        subprocess.run(["clang", "--target=x86_64-pc-windows-msvc", "-O2", "-ffreestanding",
                        "-fno-builtin", "-fno-stack-protector", "-Wall", "-Werror",
                        "-c", str(AQUI / "sustitutas" / f"{paquete}.c"), "-o", str(objeto)],
                       check=True)
        subprocess.run(["lld-link", "/nologo", "/dll", "/noentry", "/nodefaultlib",
                        "/machine:x64", str(objeto), f"/out:{salida}"], check=True)
        binarios[dll] = salida.read_bytes()
    return binarios


def poner_sustitutas(runtime, binarios):
    for dll, datos in binarios.items():
        (runtime / "bin" / dll).write_bytes(datos)
    comprobar_sustitutas(runtime, binarios)


def _pe(datos):
    """(¿64 bits?, directorios de datos, secciones) de un PE; ValueError si no lo es."""
    try:
        pe = struct.unpack_from("<I", datos, 0x3C)[0]
        if datos[:2] != b"MZ" or datos[pe:pe + 4] != b"PE\0\0":
            raise ValueError
        secciones_n, opcional_largo = struct.unpack_from("<H", datos, pe + 6)[0], \
            struct.unpack_from("<H", datos, pe + 20)[0]
        opcional = pe + 24
        de64 = struct.unpack_from("<H", datos, opcional)[0] == 0x20B
        directorios = opcional + (112 if de64 else 96)
        n = struct.unpack_from("<I", datos, directorios - 4)[0]
        dirs = [struct.unpack_from("<II", datos, directorios + 8 * i) for i in range(n)]
        secciones = [struct.unpack_from("<IIII", datos, opcional + opcional_largo + 40 * i + 8)
                     for i in range(secciones_n)]  # tamaño virtual, RVA, tamaño, puntero
    except struct.error:
        raise ValueError("no es un PE") from None
    return de64, dirs, secciones


def _desplazamiento(secciones, rva):
    for virtual, inicio, crudo, puntero in secciones:
        if inicio <= rva < inicio + max(virtual, crudo):
            return puntero + rva - inicio
    raise ValueError(f"RVA {rva:#x} fuera de las secciones")


def _texto(datos, desde):
    return datos[desde:datos.index(b"\0", desde)].decode("ascii")


def exportes(datos):
    """Los nombres que exporta una DLL."""
    _, dirs, secciones = _pe(datos)
    if not dirs or not dirs[0][0]:
        return set()
    base = _desplazamiento(secciones, dirs[0][0])
    nombres_n, nombres_rva = struct.unpack_from("<I", datos, base + 24)[0], \
        struct.unpack_from("<I", datos, base + 32)[0]
    tabla = _desplazamiento(secciones, nombres_rva)
    return {_texto(datos, _desplazamiento(secciones, struct.unpack_from("<I", datos, tabla + 4 * i)[0]))
            for i in range(nombres_n)}


def importes(datos):
    """{DLL en minúsculas: nombres que importa de ella} de un PE (las de por ordinal no salen)."""
    de64, dirs, secciones = _pe(datos)
    if len(dirs) < 2 or not dirs[1][0]:
        return {}
    hecho, descriptor = {}, _desplazamiento(secciones, dirs[1][0])
    ancho, ordinal = (8, 1 << 63) if de64 else (4, 1 << 31)
    while True:
        original, _, _, nombre, primero = struct.unpack_from("<IIIII", datos, descriptor)
        if not nombre:
            return hecho
        simbolos = hecho.setdefault(_texto(datos, _desplazamiento(secciones, nombre)).lower(), set())
        thunk = _desplazamiento(secciones, original or primero)
        while valor := struct.unpack_from("<Q" if de64 else "<I", datos, thunk)[0]:
            if not valor & ordinal:
                simbolos.add(_texto(datos, _desplazamiento(secciones, valor & 0x7FFFFFFF) + 2))
            thunk += ancho
        descriptor += 20


def comprobar_sustitutas(runtime, binarios):
    """Que cada sustituta exporte todo lo que el runtime le pide: si no, Windows no abre el board.

    Si una versión nueva de libtiff o de cairo pide una función más, la construcción falla aquí
    y no en el PC de quien instala.
    """
    exportan = {dll.lower(): exportes(datos) for dll, datos in binarios.items()}
    faltan = []
    for binario in runtime.rglob("*"):
        if binario.suffix.lower() not in (".dll", ".exe", ".pyd") or not binario.is_file():
            continue
        try:
            pide = importes(binario.read_bytes())
        except (ValueError, struct.error):
            continue
        for dll, simbolos in pide.items():
            if dll in exportan and simbolos - exportan[dll]:
                faltan.append(f"{binario.relative_to(runtime)} pide a {dll} "
                              + ", ".join(sorted(simbolos - exportan[dll])))
    if faltan:
        raise ErrorDeConstruccion("Las DLL sustitutas no tienen todo lo que se les pide (añádelo "
                                  "a sustitutas/):\n  " + "\n  ".join(faltan))


def poner_lanzadores(carpeta, binarios):
    for nombre, (orden, ventana) in LANZADORES.items():
        destino = carpeta / f"{nombre}.exe"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(binarios[ventana] + carga(orden))


# --- El paquete -----------------------------------------------------------------------------

def comprobar_icono():
    """Que `cotejo.ico` salga del icono de la app de hoy y no de uno anterior.

    Pasó: el logo cambió el 2026-09-28 y el .ico, hecho el 27, seguía siendo el viejo.
    """
    sys.path.insert(0, str(AQUI))
    import icono
    huella = icono.HUELLA.read_text(encoding="utf-8").strip() if icono.HUELLA.exists() else ""
    if huella != icono.huella_svg():
        raise ErrorDeConstruccion(f"cotejo.ico no es el de {icono.SVG.name} de hoy: "
                                  "python3 empaquetado/windows/icono.py y vuelve a construir.")


def comprobar_arbol():
    """Que lo que se copia esté en un commit: el paquete lleva el árbol de trabajo.

    Un cambio a medias en `tareas/` o en `data/` viajaría en el instalador sin que ningún commit diga
    qué versión es. Sin git (una copia suelta del código) no hay nada que comparar.
    """
    rutas = [*DE_LA_APP, *(f"data/{d}" for d in DATOS), *SUELTOS, "empaquetado/windows/cotejo.ico"]
    try:
        cambios = subprocess.run(["git", "-C", str(RAIZ), "status", "--porcelain", "--", *rutas],
                                 capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return
    if cambios.strip():
        raise ErrorDeConstruccion("Hay cambios sin commit en lo que va en el paquete:\n" + cambios
                                  + "Haz commit (o pasa --con-cambios-sin-commit para una prueba).")


def version_por_defecto():
    """`tareas.__version__`: la misma que `cotejo --version` y que construir.sh de Linux.

    Se lee del archivo y no con `import tareas`, que copiaría variables de entorno al importarse.
    Sale del árbol de trabajo, que es de donde `copiar_app` copia el código.
    """
    texto = (RAIZ / "tareas" / "__init__.py").read_text(encoding="utf-8")
    encontrada = re.search(r'^__version__ = "([^"]+)"$', texto, re.MULTILINE)
    if not encontrada:
        raise ErrorDeConstruccion("No encontré __version__ en tareas/__init__.py")
    return encontrada.group(1)


def instalador(carpeta, version, salida):
    """Compila `cotejo.iss` con Inno Setup, si está. Devuelve el .exe o None."""
    argumentos = [f"/DOrigen={carpeta}", f"/DVersion={version}", f"/O{salida}",
                  str(AQUI / "cotejo.iss")]
    iscc = shutil.which("iscc") or shutil.which("ISCC") or next(
        (str(r) for r in (Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
                          Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe")
         if r.is_file()), None)
    if not iscc:
        avisar("Instalador: no hay Inno Setup (iscc) en esta máquina; se queda la carpeta. En Windows:\n"
               "  iscc " + " ".join(f'"{a}"' for a in argumentos))
        return None
    subprocess.run([iscc, "/Q", *argumentos], check=True)
    return salida / f"Cotejo-{version}-windows-x64-instalador.exe"


def comprobar(carpeta):
    """En Windows, que los comandos arrancan de verdad; fuera, no se puede y se dice."""
    if sys.platform != "win32":
        avisar("Comprobación: se salta, los .exe solo corren en Windows.")
        return
    entorno = {**os.environ, "COTEJO_VAULT": str(carpeta / "vacio"),
               "COTEJO_ESTADO": str(carpeta / "vacio")}
    for orden in (["bin/cotejo.exe", "--help"],
                  ["runtime/bin/python.exe", "-c", "import gi; gi.require_version('Gtk', '4.0'); "
                   "gi.require_version('Adw', '1'); from gi.repository import Gtk, Adw"]):
        subprocess.run([str(carpeta / orden[0]), *orden[1:]], check=True, env=entorno,
                       stdout=subprocess.DEVNULL)
    shutil.rmtree(carpeta / "vacio", ignore_errors=True)
    avisar("Comprobación: cotejo.exe responde y el runtime carga GTK 4 y libadwaita.")


def construir(salida, version, espejo=ESPEJO, cache=AQUI / "cache", runtime=None,
              con_instalador=True, fuentes=FUENTES):
    """Arma todo en `salida` y devuelve {qué: ruta}."""
    carpeta = salida / "Cotejo"
    shutil.rmtree(carpeta, ignore_errors=True)
    carpeta.mkdir(parents=True)
    avisar(f"Cotejo {version} para Windows → {carpeta}")
    binarios = compilar_lanzadores(salida / "lanzadores")
    sustitutas = compilar_sustitutas(salida / "sustitutas")
    if runtime:
        shutil.copytree(runtime, carpeta / "runtime")
    else:
        armar_runtime(carpeta / "runtime", espejo.rstrip("/"), cache, fuentes)
    poner_sustitutas(carpeta / "runtime", sustitutas)
    copiar_app(carpeta / "app")
    poner_licencias_generales(carpeta)
    poner_lanzadores(carpeta, binarios)
    shutil.copy2(AQUI / "cotejo.ico", carpeta / "cotejo.ico")
    comprobar(carpeta)
    hecho = {"carpeta": carpeta}
    if con_instalador:
        exe = instalador(carpeta, version, salida)
        if exe:
            hecho["instalador"] = exe
            avisar(f"Instalador: {exe}")
    return hecho


def main(argumentos=None):
    analizador = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    analizador.add_argument("--version", default=version_por_defecto())
    analizador.add_argument("--salida", type=Path, default=AQUI / "construido")
    analizador.add_argument("--cache", type=Path, default=AQUI / "cache")
    analizador.add_argument("--espejo", default=ESPEJO,
                            help="de dónde bajar los paquetes de MSYS2 (una URL o file://)")
    analizador.add_argument("--fuentes", default=FUENTES,
                            help="de dónde bajar el código fuente de MSYS2 para las licencias "
                                 "que el binario no trae (H8; una URL o file://)")
    analizador.add_argument("--runtime", type=Path,
                            help="usar este runtime ya armado en vez de bajarlo")
    analizador.add_argument("--sin-instalador", action="store_true",
                            help="solo la carpeta, sin compilar el instalador")
    analizador.add_argument("--con-cambios-sin-commit", action="store_true",
                            help="construir aunque el código tenga cambios sin commit (pruebas)")
    args = analizador.parse_args(argumentos)
    try:
        comprobar_icono()
        if not args.con_cambios_sin_commit:
            comprobar_arbol()
        construir(args.salida.resolve(), args.version, args.espejo, args.cache.resolve(),
                  args.runtime, not args.sin_instalador, args.fuentes)
    except ErrorDeConstruccion as error:
        avisar(f"No se pudo construir: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
