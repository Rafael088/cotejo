"""Los verbos del almacén `.cotejo/` (v1.2 · A1-D2) y el importador de Obsidian, con el
`cotejo` ya instalado — no el del repo.

    python empaquetado/windows/probar_almacen.py [COTEJO]

Pensado para el runner de `.github/workflows/windows.yml`, después de «Instalar y probar»
(`probar_instalado.py`): ejercita `init`, `contexto`, `anotar` (cada tipo), `bitacora`,
`proponer decision` (y `--reemplaza`), `buscar`, `leer`, `editar`, `resolver` y
`importar obsidian` (ensayo y `--aplicar`, con una imagen que cae en `recursos/`), todo contra
un repo de prueba con espacios y acentos en la ruta —justo lo que rompe en Windows y que una
ruta corta de ASCII nunca pone a prueba—.

La raíz del repo se queda justo por debajo de lo que git aguanta en Windows
(`LARGO_RAIZ`, 240 caracteres), y lo que pasa de los 260 de MAX_PATH son los archivos que
Cotejo escribe *dentro*: `recursos/<slug>.png` y `bitacora/<fecha>.md`. Una raíz más larga
no se puede probar porque no existe: `git init` no puede tener la raíz de un repo por encima
de ~248 caracteres en Windows, ni con `LongPathsEnabled=1` ni con `core.longpaths=true`
(prueba a mano del 2026-10-06). Lo que sí se comprueba es que `importar obsidian --aplicar`
lo diga así, en vez de devolver el error crudo de git. El vault de origen, en cambio, no es un
repo y vive en una ruta de más de 260 caracteres.

En Windows exige `LongPathsEnabled=1` (lo comprueba al arrancar), como `probar_despachar.py`.

También corre en Linux (sin Windows no hay forma de confirmar nada de lo anterior, pero sí de
demostrar que el script funciona antes de pedirle a nadie que lo corra en Windows). Busca el
`cotejo` a probar, en orden:

1. El argumento, si se da (la ruta a `cotejo` o `cotejo.exe`).
2. `$COTEJO_BIN`.
3. En Windows, el que acaba de instalar `probar_instalado.py`
   (`%LOCALAPPDATA%\\Programs\\Cotejo\\bin\\cotejo.exe`).
4. En Linux, el del PATH (`shutil.which`) — el de `~/.local/bin/cotejo` si `install.sh` ya
   corrió ahí la 1.2.

Todo pasa en carpetas temporales (`COTEJO_ESTADO`, `COTEJO_CONFIG` y, para `importar obsidian`,
`COTEJO_VAULT`/`COTEJO_CARPETA_PROYECTOS`): nada toca el vault real, la config de verdad ni el
estado de ninguna tarea. No llama a Notion ni a ningún servicio: todo es local.

Cada comprobación que falla se junta en `fallos` y el script sigue con las demás —como
`probar_instalado.py`—, porque un verbo roto no debería esconder si los otros once funcionan.
La salida completa de cada `cotejo ...` queda en `construido/registros/almacen.txt`, que el
workflow ya sube como artefacto.
"""

import atexit
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
REGISTROS = AQUI / "construido" / "registros"

# A propósito larga, con espacios y con acentos: varios niveles de una carpeta así son lo que
# en Windows pasa los 260 caracteres de MAX_PATH *y* lo que sus APIs de archivo manejan peor
# que un ASCII corto (comillas, acentuación, espacios finales). `recursos/` y los nombres de
# archivo con fecha de la bitácora son justo las rutas que `importar_obsidian.py` y
# `tareas/almacen.py` escriben solos, sin que nadie las pida: si algo se rompe, es ahí.
SEGMENTO = "carpeta de prueba con espacios y acentos áéíóúñ (verificar rutas largas en Windows)"
NIVELES_HONDO = 3
# Lo más larga que se deja la raíz de un repo: por debajo de los 247 de
# `importar_obsidian.RAIZ_GIT_MAXIMA_WINDOWS`, con margen.
LARGO_RAIZ = 240


def localizar_cotejo(argumentos):
    """El `cotejo` a probar: el argumento, `$COTEJO_BIN`, el recién instalado o el del PATH."""
    if argumentos:
        encontrado = Path(argumentos[0]).resolve()
        if not encontrado.is_file():
            raise SystemExit(f"«{encontrado}» no es un archivo.")
        return encontrado
    variable = os.environ.get("COTEJO_BIN")
    if variable:
        encontrado = Path(variable).resolve()
        if not encontrado.is_file():
            raise SystemExit(f"$COTEJO_BIN («{encontrado}») no es un archivo.")
        return encontrado
    if os.name == "nt":
        exe = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Cotejo" / "bin" / "cotejo.exe"
        if not exe.is_file():
            raise SystemExit(f"No hay {exe}: este script espera un Cotejo ya instalado (corre "
                             "después de «Instalar y probar»), o pásalo como argumento.")
        return exe
    encontrado = shutil.which("cotejo")
    if not encontrado:
        raise SystemExit("No encuentro «cotejo» en el PATH. Pásalo como argumento, en "
                         "$COTEJO_BIN, o instala la 1.2 con `install.sh` "
                         "(queda en ~/.local/bin/cotejo).")
    return Path(encontrado)


def ruta_honda(base):
    """`base` con `NIVELES_HONDO` carpetas de `SEGMENTO` colgando."""
    honda = base
    for _ in range(NIVELES_HONDO):
        honda = honda / SEGMENTO
    return honda


def raiz_al_limite(base, nombre, largo=LARGO_RAIZ):
    """`base/<trozos de SEGMENTO>/nombre`, rellenada hasta acercarse a `largo` caracteres sin
    pasarlos: la raíz de repo más larga que git acepta en Windows, con espacios y acentos. Si
    `base` ya es más larga, queda `base/nombre` tal cual."""
    ruta = Path(base)
    while True:
        resto = largo - len(str(ruta / nombre)) - 1  # el separador del trozo nuevo
        trozo = SEGMENTO[:resto].rstrip(" .") if resto > 0 else ""  # Windows no los quiere al final
        if not trozo:
            return ruta / nombre
        ruta = ruta / trozo


def borrar_al_salir(carpeta):
    """Borra `carpeta` al terminar el script, pase lo que pase, salvo con `COTEJO_CONSERVAR=1`
    (para depurar). Quita antes el solo-lectura que deja git en `.git/objects`: sin eso,
    `rmtree` no puede en Windows, y las rutas largas el Explorador tampoco las borra."""
    if os.environ.get("COTEJO_CONSERVAR") == "1":
        return

    def escribible(funcion, ruta, _error):
        os.chmod(ruta, stat.S_IWRITE)
        funcion(ruta)

    atexit.register(shutil.rmtree, carpeta, onerror=escribible)


def exigir_rutas_largas():
    """En Windows, sale con un mensaje claro si `LongPathsEnabled` no está a 1: sin eso, ni
    Python puede crear las carpetas de prueba, y el traceback de `pathlib` no dice por qué."""
    if os.name != "nt":
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\FileSystem") as clave:
            valor, _ = winreg.QueryValueEx(clave, "LongPathsEnabled")
    except OSError:
        valor = 0
    if valor != 1:
        raise SystemExit(
            "Este script necesita las rutas largas de Windows activadas (LongPathsEnabled=1; "
            "el runner windows-latest ya las trae). Actívalas en una PowerShell de "
            "administrador y vuelve a correrlo:\n  New-ItemProperty -Path "
            "HKLM:\\SYSTEM\\CurrentControlSet\\Control\\FileSystem -Name LongPathsEnabled "
            "-Value 1 -PropertyType DWORD -Force")


def git_init(repo, temporal):
    """`git init` como lo hace `importar_obsidian.git_init`: la ruta como argumento y, en
    Windows, `core.longpaths=true` para los archivos de `.git/` que pasan de MAX_PATH."""
    previo = ["-c", "core.longpaths=true"] if os.name == "nt" else []
    subprocess.run(["git", *previo, "init", "-q", str(repo)], check=True, capture_output=True,
                   cwd=str(temporal), timeout=60)


class Fallos(list):
    """Las comprobaciones que no pasaron. Se imprime cada una al momento, para seguir el run."""

    def anota(self, mensaje):
        print(f"FALLO: {mensaje}")
        self.append(mensaje)


def cli(cotejo, entorno, temporal, bitacora, *argumentos):
    """Corre `cotejo <argumentos>`, en una carpeta corta (nunca en la larga: eso es lo que se
    está probando, no el `cwd` del propio script). Devuelve (código, json-o-None, stdout, stderr).
    """
    hecho = subprocess.run([str(cotejo), *argumentos], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=str(temporal), env=entorno)
    bitacora.append(f"$ cotejo {' '.join(argumentos)}\n{hecho.stdout}{hecho.stderr}"
                    f"(código {hecho.returncode})\n")
    datos = None
    if hecho.stdout.strip():
        try:
            datos = json.loads(hecho.stdout)
        except json.JSONDecodeError:
            datos = None
    return hecho.returncode, datos, hecho.stdout, hecho.stderr


def ruta_entrada(repo, ruta_relativa):
    """La ruta real de una entrada del almacén, a partir de su `ruta` (relativa a `.cotejo/`,
    con `/` siempre, lo diga `tareas/almacen.py` en Linux o en Windows). Partir por `/` y
    volver a unir con `Path` es la comprobación: si alguna vez se filtrara un `\\\\` de Windows
    en el JSON, partir por `/` no lo separaría en piezas y esto no encontraría el archivo."""
    if "\\" in ruta_relativa:
        raise AssertionError(f"la ruta «{ruta_relativa}» trae '\\\\': tiene que ser '/'")
    return Path(repo, ".cotejo", *ruta_relativa.split("/"))


def ruta_recurso(repo, ruta_relativa):
    """Como `ruta_entrada`, pero para la `ruta` que ya trae `.cotejo/` delante (la de
    `leer <recurso>`, que es literal `.cotejo/recursos/<archivo>`)."""
    if "\\" in ruta_relativa:
        raise AssertionError(f"la ruta «{ruta_relativa}» trae '\\\\': tiene que ser '/'")
    return Path(repo, *ruta_relativa.split("/"))


def main():
    exigir_rutas_largas()
    REGISTROS.mkdir(parents=True, exist_ok=True)
    cotejo = localizar_cotejo(sys.argv[1:])
    print(f"Probando {cotejo}")
    fallos = Fallos()
    bitacora = []

    temporal = Path(tempfile.mkdtemp(prefix="cotejo-almacen-"))
    borrar_al_salir(temporal)
    repo = raiz_al_limite(temporal, "repo")
    repo.mkdir(parents=True)
    print(f"Repo de prueba: {repo} ({len(str(repo))} caracteres)")

    entorno = {**os.environ, "COTEJO_ESTADO": str(temporal / "estado"),
              "COTEJO_CONFIG": str(temporal / "config.json")}

    def correr(*argumentos):
        return cli(cotejo, entorno, temporal, bitacora, *argumentos)

    try:
        git_init(repo, temporal)
    except (OSError, subprocess.SubprocessError) as error:
        raise SystemExit(f"No pude `git init` en la raíz de prueba ({len(str(repo))} "
                         f"caracteres): {error}")

    # --- init: el esqueleto del almacén, y que repetirlo no cambie nada -----------------------
    codigo, datos, *_ = correr("init", "--repo", str(repo))
    if codigo != 0 or not datos or not datos.get("creado"):
        fallos.anota(f"`init` no creó tareas.md la primera vez: código {codigo}, {datos}")
    for tipo_, carpeta_ in (("decision", "decisiones"), ("problema", "problemas"),
                            ("arquitectura", "arquitectura"), ("aprendizaje", "aprendizajes"),
                            ("bitacora", "bitacora"), ("referencia", "referencias"),
                            ("recurso", "recursos")):
        if not (repo / ".cotejo" / carpeta_).is_dir():
            fallos.anota(f"`init` no dejó la carpeta {carpeta_}/ del tipo {tipo_}")
    if not (repo / ".cotejo" / "proyecto.md").is_file():
        fallos.anota("`init` no dejó proyecto.md")
    codigo, datos, *_ = correr("init", "--repo", str(repo))
    if codigo != 0 or not datos or datos.get("cambio") is not False:
        fallos.anota(f"`init` repetido no fue idempotente: código {codigo}, {datos}")

    # --- contexto: nace vacío, barato -----------------------------------------------------------
    codigo, datos, *_ = correr("contexto", "--repo", str(repo))
    if codigo != 0 or not datos or datos.get("proyecto", {}).get("titulo") != repo.name:
        fallos.anota(f"`contexto` no devolvió el proyecto esperado: código {codigo}, {datos}")
    elif any(datos["tareas"].values()) or datos["decisiones_vigentes"] or datos["problemas_abiertos"]:
        fallos.anota(f"`contexto` de un repo recién creado no debería traer nada: {datos}")

    # --- anotar: una entrada de cada tipo, con temas con acentos --------------------------------
    ids = {}
    textos_anotar = {
        "problema": ("Falla al abrir una ruta con espacios y acentos en Windows",
                    "El instalador se cae si el repo vive bajo una carpeta con tildes."),
        "aprendizaje": ("Las rutas del almacén siempre llevan `/`, nunca `\\\\`",
                        "`Entrada.ruta` usa `Path.as_posix()`: por eso el JSON sale igual en "
                        "Linux y en Windows."),
        "referencia": ("Checklist de rutas largas para el instalador de Windows",
                       "MAX_PATH, `core.longpaths`, y por qué `chdir` es el problema real."),
        "arquitectura": ("Cómo decide `importar_obsidian` el nombre de un recurso",
                         "`almacen._slug` lo deja en ASCII, minúsculas y guiones."),
    }
    for tipo_, (titulo, texto) in textos_anotar.items():
        codigo, datos, *_ = correr("anotar", tipo_, "--titulo", titulo, "--texto", texto,
                                   "--temas", "windows,rutas", "--repo", str(repo))
        if codigo != 0 or not datos or not datos.get("id"):
            fallos.anota(f"`anotar {tipo_}` falló: código {codigo}, {datos}")
            continue
        ids[tipo_] = datos["id"]
        if not ruta_entrada(repo, datos["ruta"]).is_file():
            fallos.anota(f"`anotar {tipo_}` dijo ruta «{datos['ruta']}» pero no existe el archivo")
        con_fecha = tipo_ in ("problema", "aprendizaje")
        if con_fecha and not re.match(r"^\d{4}-\d{2}-\d{2}-", Path(datos["ruta"]).name):
            fallos.anota(f"`anotar {tipo_}` debía llevar fecha en el nombre: {datos['ruta']}")

    # --- bitacora: un archivo por día, que solo crece -------------------------------------------
    hoy = date.today().isoformat()
    codigo, datos, *_ = correr("bitacora", "Primera línea de la bitácora de prueba (con tildes: "
                               "revisión, acción).", "--repo", str(repo))
    if codigo != 0 or not datos or datos.get("ruta") != f"bitacora/{hoy}.md":
        fallos.anota(f"`bitacora` no dejó el archivo con fecha esperado: código {codigo}, {datos}")
    else:
        ruta_bitacora = ruta_entrada(repo, datos["ruta"])
        print(f"Bitácora de hoy: {ruta_bitacora} ({len(str(ruta_bitacora))} caracteres)")
        if not ruta_bitacora.is_file():
            fallos.anota(f"`bitacora` dijo «{datos['ruta']}» pero no existe el archivo")
        codigo2, datos2, *_ = correr("bitacora", "Segunda línea, más tarde el mismo día.",
                                     "--repo", str(repo))
        if codigo2 != 0 or not datos2 or datos2.get("ruta") != datos["ruta"]:
            fallos.anota(f"la segunda `bitacora` del día no reusó el mismo archivo: {datos2}")
        elif ruta_bitacora.is_file():
            contenido = ruta_bitacora.read_text(encoding="utf-8")
            if "Primera línea" not in contenido or "Segunda línea" not in contenido:
                fallos.anota("la bitácora no acumuló las dos líneas del día")

    # --- proponer decision (y --reemplaza) -------------------------------------------------------
    codigo, datos, *_ = correr("proponer", "decision", "--titulo",
                               "Usar pathlib en vez de concatenar strings para rutas",
                               "--texto", "Así se evita mezclar '/' y '\\\\' a mano.",
                               "--temas", "windows,rutas", "--repo", str(repo))
    dec_vieja = None
    if codigo != 0 or not datos or not datos.get("id"):
        fallos.anota(f"`proponer decision` falló: código {codigo}, {datos}")
    else:
        dec_vieja = datos["id"]
        codigo, datos, *_ = correr(
            "proponer", "decision", "--titulo",
            "Usar pathlib en vez de concatenar strings, con `os.fspath` en los bordes",
            "--texto", "La anterior se queda corta con las APIs de C que solo aceptan str.",
            "--reemplaza", dec_vieja, "--repo", str(repo))
        if codigo != 0 or not datos or datos.get("reemplazada", {}).get("id") != dec_vieja:
            fallos.anota(f"`proponer decision --reemplaza` falló: código {codigo}, {datos}")
        else:
            codigo, vieja_leida, *_ = correr("leer", dec_vieja, "--repo", str(repo))
            if codigo != 0 or vieja_leida.get("estado") != "reemplazada":
                fallos.anota(f"la decisión vieja no quedó «reemplazada»: {vieja_leida}")

    # --- buscar: por tipo, por texto (sin acentos) y por temas ------------------------------------
    codigo, datos, *_ = correr("buscar", "--repo", str(repo), "--tipo", "problema")
    if codigo != 0 or not datos or datos.get("total", 0) < 1:
        fallos.anota(f"`buscar --tipo problema` no encontró nada: código {codigo}, {datos}")
    codigo, datos, *_ = correr("buscar", "--repo", str(repo), "--texto", "espacios y acentos")
    if codigo != 0 or not datos or datos.get("total", 0) < 1:
        fallos.anota(f"`buscar --texto` (con acentos en el texto) no encontró nada: {datos}")
    codigo, datos, *_ = correr("buscar", "--repo", str(repo), "--temas", "windows,rutas")
    if codigo != 0 or not datos or datos.get("total", 0) < 2:
        fallos.anota(f"`buscar --temas windows,rutas` encontró menos de lo esperado: {datos}")

    # --- leer: la entrada completa, y el error de un id que no existe ----------------------------
    codigo, datos, *_ = correr("leer", "proyecto", "--repo", str(repo))
    if codigo != 0 or not datos or datos.get("titulo") != repo.name:
        fallos.anota(f"`leer proyecto` no devolvió el proyecto esperado: {datos}")
    codigo, datos, *_ = correr("leer", "zzz-0000", "--repo", str(repo))
    if codigo != 3 or not datos or "error" not in datos:
        fallos.anota(f"`leer` de un id inexistente debía fallar con código 3: {codigo}, {datos}")

    # --- editar: con la versión buena, y con la vieja (código 4, reintentable) -------------------
    arq_id = ids.get("arquitectura")
    if arq_id:
        codigo, leida, *_ = correr("leer", arq_id, "--repo", str(repo))
        version_vieja = leida.get("version") if codigo == 0 else None
        codigo, datos, *_ = correr("editar", arq_id, "--version", str(version_vieja),
                                   "--texto", "Texto actualizado tras revisar el importador.",
                                   "--repo", str(repo))
        if codigo != 0 or not datos or datos.get("version") == version_vieja:
            fallos.anota(f"`editar` con la versión buena no avanzó la versión: {codigo}, {datos}")
        # La misma versión, ya vieja (el archivo cambió con la edición de arriba): tiene que
        # negarse sin escribir, con el código reintentable de siempre (igual que `tareas`).
        codigo, datos, *_ = correr("editar", arq_id, "--version", str(version_vieja),
                                   "--texto", "Un segundo cambio que no debería escribirse.",
                                   "--repo", str(repo))
        if codigo != 4 or not datos or not datos.get("reintentable"):
            fallos.anota(f"`editar` con una versión vieja debía fallar con código 4: "
                        f"{codigo}, {datos}")
    else:
        fallos.anota("no hay id de arquitectura (falló `anotar` antes): se salta `editar`")
    if dec_vieja:
        codigo, datos, *_ = correr("editar", dec_vieja, "--version", "0" * 12, "--texto", "x",
                                   "--repo", str(repo))
        if codigo != 3 or not datos or "no se editan" not in datos.get("error", ""):
            fallos.anota(f"`editar` sobre una decisión debía negarse: {codigo}, {datos}")

    # --- resolver: problema abierto -> resuelto, y que reintentarlo no rompa nada -----------------
    pro_id = ids.get("problema")
    if pro_id:
        codigo, datos, *_ = correr("resolver", pro_id, "--solucion",
                                   "Se cambió a `pathlib.Path` en todas las rutas del instalador.",
                                   "--repo", str(repo))
        if codigo != 0 or not datos or datos.get("cambio") is not True:
            fallos.anota(f"`resolver` no resolvió el problema: código {codigo}, {datos}")
        codigo, datos, *_ = correr("resolver", pro_id, "--solucion", "Lo mismo, otra vez.",
                                   "--repo", str(repo))
        if codigo != 0 or not datos or datos.get("cambio") is not False:
            fallos.anota(f"`resolver` repetido sobre un problema ya resuelto no fue "
                        f"idempotente: código {codigo}, {datos}")
    else:
        fallos.anota("no hay id de problema (falló `anotar` antes): se salta `resolver`")

    # --- aceptar: no es un verbo de agente, y falla con código 3 ----------------------------------
    codigo, datos, *_ = correr("aceptar")
    if codigo != 3 or not datos or "error" not in datos:
        fallos.anota(f"`aceptar` debía fallar con código 3: código {codigo}, {datos}")

    # --- importar obsidian: ensayo y --aplicar, con una imagen que cae en recursos/ ---------------
    importar_obsidian(cotejo, entorno, temporal, bitacora, fallos)

    (REGISTROS / "almacen.txt").write_text("\n".join(bitacora), encoding="utf-8")
    if fallos:
        print(f"\nFalló ({len(fallos)}):\n- " + "\n- ".join(fallos))
        return 1
    print("\nTodos los verbos del almacén y el importador de Obsidian, bien con el cotejo "
         f"instalado ({cotejo}).")
    return 0


def _slug(texto, largo=60):
    """El mismo slug que `tareas/almacen.py` (ASCII, minúsculas, guiones): para saber de
    antemano qué nombre de archivo esperar en `recursos/` y no adivinarlo."""
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")
    return slug[:largo].rstrip("-")


def importar_obsidian(cotejo, entorno_base, temporal, bitacora, fallos):
    """El vault de mentira (D1/D2): un proyecto con tablas, bitácora y una imagen con acentos
    y espacios en el nombre, que tiene que caer en `recursos/` con su ficha. Repetir
    `--aplicar` no debe duplicar nada: ni la imagen, ni su ficha, ni las demás entradas.
    """
    vault = ruta_honda(temporal) / "vault"  # no es un repo: aquí sí cabe una ruta de >260
    carpeta_proyectos = "Proyectos"
    proyecto = "Instalación en Windows"
    imagen = "captura con acentos y espacios áé.png"

    carpeta_proyecto = vault / carpeta_proyectos
    carpeta_proyecto.mkdir(parents=True)
    # Un PNG mínimo pero real (1×1, transparente): no hace falta que se vea, solo que exista
    # como archivo binario y que el importador lo copie bit a bit.
    (carpeta_proyecto / imagen).write_bytes(bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000a4944415478da6364000000020001e221bc330000000049454e44ae426082"))
    (carpeta_proyecto / f"{proyecto}.md").write_text(
        "## 🎯 Objetivo\n\nProbar que una imagen con acentos y espacios en el nombre cae en "
        "`recursos/` con su ficha, y que repetir la importación no la duplica.\n\n"
        # La marca `^cotejo-xxxxx` tiene que parecer una de verdad (solo letras y números tras
        # el prefijo: `importar_obsidian.MARCA_RE` no reconoce guiones ahí), o la comparación
        # de «ya estaba importado» de `_que_hacer_con_las_tareas` no la cuenta y el segundo
        # `--aplicar` se niega pensando que el repo tiene tareas ajenas.
        "## ✅ Tareas\n\n- [ ] Revisar que el instalador funcione con rutas largas "
        "^cotejo-rutalg1\n"
        "- [ ] Avisar cuando el PC de pruebas esté libre ^cotejo-rutalg2\n\n"
        "## 🧠 Decisiones técnicas\n\n"
        "| Fecha | Decisión | Motivo | Alternativas |\n|---|---|---|---|\n"
        "| 2026-10-05 | Probar en una ruta con espacios y acentos | Es donde Windows rompe | "
        "Una ruta corta de ASCII, que no prueba nada |\n\n"
        "## 🐛 Problemas y soluciones\n\n"
        "| Problema | Causa | Solución |\n|---|---|---|\n"
        "| El board no abría en una ruta con tildes | `GDK_PIXBUF_MODULEDIR` mal armado | "
        "Se apuntó con la ruta absoluta del lanzador |\n\n"
        "## 📚 Aprendizajes\n\n- Una imagen enlazada con `![[...]]` no es una subnota: es un "
        "adjunto, y va a `recursos/`.\n\n"
        f"## 🗒️ Bitácora\n\n### 2026-10-01\n\nSe armó el vault de prueba con una imagen "
        f"adjunta ([[{imagen}]]) para probar el importador.\n",
        encoding="utf-8")

    entorno = {**entorno_base, "COTEJO_VAULT": str(vault), "COTEJO_CARPETA_PROYECTOS": carpeta_proyectos}

    def correr(*argumentos):
        return cli(cotejo, entorno, temporal, bitacora, *argumentos)

    # Un destino más largo de lo que git aguanta en Windows: `--aplicar` tiene que negarse con
    # un mensaje que lo diga, sin crear nada, en vez de dejar pasar el error crudo de git.
    if os.name == "nt":
        demasiado = ruta_honda(temporal) / "repo-importado"
        codigo, datos, *_ = correr("importar", "obsidian", proyecto, "--destino", str(demasiado),
                                   "--aplicar")
        if codigo != 3 or "demasiado larga para git" not in (datos or {}).get("error", ""):
            fallos.anota(f"`importar obsidian --aplicar` con un destino de {len(str(demasiado))} "
                        f"caracteres debía negarse por la ruta: código {codigo}, {datos}")
        if demasiado.exists():
            fallos.anota("el destino demasiado largo se creó aunque `--aplicar` se negó")

    destino = raiz_al_limite(temporal, "repo importado")

    # Ensayo: no escribe nada. Se comprueba contando lo que promete, no adivinando el total.
    codigo, datos, *_ = correr("importar", "obsidian", proyecto, "--destino", str(destino))
    if codigo != 0 or not datos or datos.get("ensayo") is not True:
        fallos.anota(f"`importar obsidian` (ensayo) falló: código {codigo}, {datos}")
        return
    if datos["adjuntos"] != 1:
        fallos.anota(f"el ensayo no vio la imagen como adjunto: {datos}")
    if datos["conteo"].get("recurso") != 1:
        fallos.anota(f"el ensayo no iba a crear la ficha del recurso: {datos}")
    if destino.exists():
        fallos.anota("el ensayo escribió algo en destino, y no debía")

    # --aplicar: ahora sí escribe. La imagen tiene que estar en recursos/, con su ficha, y su
    # ruta leída por `cotejo leer` tiene que resolver a un archivo real con '/' y no '\\'.
    codigo, datos, *_ = correr("importar", "obsidian", proyecto, "--destino", str(destino),
                               "--aplicar")
    if codigo != 0 or not datos or datos.get("ensayo") is not False:
        fallos.anota(f"`importar obsidian --aplicar` falló: código {codigo}, {datos}")
        return
    if datos.get("recursos_copiados") != 1:
        fallos.anota(f"`--aplicar` no copió la imagen a recursos/: {datos}")
    if not datos.get("git_init"):
        fallos.anota(f"`--aplicar` sobre un destino sin repo debía hacer `git init`: {datos}")

    slug = _slug(Path(imagen).stem) or "recurso"
    archivo_esperado = destino / ".cotejo" / "recursos" / f"{slug}.png"
    print(f"Recurso importado: {archivo_esperado} ({len(str(archivo_esperado))} caracteres)")
    if not archivo_esperado.is_file():
        fallos.anota(f"no apareció {archivo_esperado} tras `--aplicar`")

    codigo, buscado, *_ = correr("buscar", "--repo", str(destino), "--tipo", "recurso")
    if codigo != 0 or not buscado or buscado.get("total") != 1:
        fallos.anota(f"`buscar --tipo recurso` no encontró exactamente un recurso: {buscado}")
        return
    recurso_id = buscado["entradas"][0]["id"]
    codigo, leido, *_ = correr("leer", recurso_id, "--repo", str(destino))
    if codigo != 0 or not leido or not leido.get("recurso", {}).get("existe"):
        fallos.anota(f"`leer {recurso_id}` no dice que el recurso exista: {leido}")
    else:
        ruta_json = leido["recurso"]["ruta"]
        archivo_real = ruta_recurso(destino, ruta_json)
        if not archivo_real.is_file():
            fallos.anota(f"`leer` dijo la ruta «{ruta_json}», pero no hay archivo ahí "
                        f"({archivo_real})")
        if archivo_real.resolve() != archivo_esperado.resolve():
            fallos.anota(f"la ruta de `leer` ({archivo_real}) no es la imagen que se copió "
                        f"({archivo_esperado})")

    # Repetir `--aplicar` no debe duplicar nada: ni el archivo, ni la ficha, ni la entrada.
    codigo, datos, *_ = correr("importar", "obsidian", proyecto, "--destino", str(destino),
                               "--aplicar")
    if codigo != 0 or not datos:
        fallos.anota(f"repetir `importar obsidian --aplicar` falló: código {codigo}, {datos}")
    else:
        if datos.get("recursos_copiados"):
            fallos.anota(f"repetir `--aplicar` volvió a copiar la imagen: {datos}")
        if datos.get("escritas"):
            fallos.anota(f"repetir `--aplicar` volvió a escribir entradas: {datos}")
        if not datos.get("ya_estaban"):
            fallos.anota(f"repetir `--aplicar` no dijo que ya estaba todo importado: {datos}")
    recursos = list((destino / ".cotejo" / "recursos").glob("*.png"))
    fichas = list((destino / ".cotejo" / "recursos").glob("*.md"))
    if len(recursos) != 1:
        fallos.anota(f"recursos/ tiene {len(recursos)} imágenes tras repetir --aplicar; "
                    "esperaba 1 (sin duplicar)")
    if len(fichas) != 1:
        fallos.anota(f"recursos/ tiene {len(fichas)} fichas tras repetir --aplicar; "
                    "esperaba 1 (sin duplicar)")


if __name__ == "__main__":
    sys.exit(main())
