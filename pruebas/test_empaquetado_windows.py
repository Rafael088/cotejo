"""El empaquetado de Windows (`empaquetado/windows/`), sin Windows y sin red.

MSYS2 se finge con un espejo en una carpeta (`file://`) con un índice y paquetes de mentira,
armados igual que los de verdad: así se prueba la resolución de dependencias, la comprobación
del SHA-256 y la construcción entera. Los lanzadores sí se compilan de verdad si hay LLVM, y se
comprueba lo que se puede sin correrlos: que son ejecutables de Windows del subsistema que toca
y que llevan pegada la orden de su comando.
"""

import codecs
import hashlib
import importlib.util
import io
import re
import shutil
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
AQUI = RAIZ / "empaquetado" / "windows"

_spec = importlib.util.spec_from_file_location("construir_windows", AQUI / "construir.py")
construir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(construir)

P = construir.PREFIJO
HAY_LLVM = all(shutil.which(h) for h in ("clang", "lld-link", "llvm-dlltool"))


def tar_gz(archivos):
    """Un .tar.gz en memoria con estos {ruta: bytes}."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for ruta, datos in archivos.items():
            info = tarfile.TarInfo(ruta)
            info.size = len(datos)
            tar.addfile(info, io.BytesIO(datos))
    return buffer.getvalue()


class Espejo:
    """Un repositorio de MSYS2 en una carpeta: `paquete(...)` y luego `publicar()`."""

    def __init__(self, carpeta):
        self.carpeta = Path(carpeta)
        self.descs = {}

    def paquete(self, nombre, depende=(), provee=(), archivos=None, sha=None, licencia="spdx:MIT",
                base=None, version="1.0-1"):
        completo = P + nombre
        archivo = f"{completo}-{version}-any.pkg.tar.gz"
        # Por omisión, como casi todos los paquetes de verdad: trae su propia licencia (una de
        # mentira, para que las pruebas que arman el runtime entero no tengan que salir a la red
        # a completarla, H8). Las que la prueban de verdad la omiten a propósito con `archivos=`.
        datos = tar_gz({".PKGINFO": b"pkgname", **(archivos if archivos is not None else {
            f"ucrt64/share/{nombre}/LEEME": nombre.encode(),
            f"ucrt64/share/licenses/{nombre}/COPYING": f"licencia de mentira de {nombre}".encode()})})
        (self.carpeta / archivo).write_bytes(datos)
        campos = {"NAME": [completo], "FILENAME": [archivo], "LICENSE": [licencia],
                  "SHA256SUM": [sha or hashlib.sha256(datos).hexdigest()],
                  "DEPENDS": list(depende), "PROVIDES": list(provee),
                  "BASE": [base or completo], "VERSION": [version]}
        self.descs[f"{completo}-{version}/desc"] = "".join(
            f"%{k}%\n" + "".join(f"{v}\n" for v in vs) + "\n" for k, vs in campos.items() if vs
        ).encode()

    def publicar(self):
        (self.carpeta / "ucrt64.db").write_bytes(tar_gz(self.descs))
        return self.carpeta.as_uri()


def repositorio_minimo(espejo):
    """Lo que PAQUETES pide, con dependencias que se cruzan y una por `provides`."""
    espejo.paquete("python", depende=[P + "tcl", P + "tk>=8.6", P + "libffi"], archivos={
        "ucrt64/bin/python.exe": b"MZ", "ucrt64/bin/pythonw.exe": b"MZ",
        "ucrt64/lib/python3.12/os.py": b"", "ucrt64/lib/python3.12/test/t.py": b"",
        "ucrt64/include/Python.h": b"", "ucrt64/lib/libpython3.12.dll.a": b"",
        "ucrt64/share/locale/es/LC_MESSAGES/gtk40.mo": b"", "ucrt64/share/locale/es_AR/x.mo": b"",
        "ucrt64/share/locale/en_GB/x.mo": b"", "ucrt64/share/locale/sr@latin/x.mo": b"",
        "ucrt64/share/locale/de/LC_MESSAGES/gtk40.mo": b"",
        "ucrt64/share/licenses/python/LICENSE": b"licencia de mentira de python"})
    espejo.paquete("gtk4", depende=[P + "glib2", P + "cairo-lib", P + "libtiff"], archivos={
        "ucrt64/bin/libgtk-4-1.dll": b"MZ", "ucrt64/bin/gtk4-demo.exe": b"MZ",
        "ucrt64/share/licenses/gtk4/COPYING": b"licencia de mentira de gtk4"})
    espejo.paquete("python-gobject", depende=[P + "python", P + "gobject-introspection-runtime"],
                   base="mingw-w64-pygobject")  # el paquete fuente no se llama como el binario
    espejo.paquete("python-cairo", depende=[P + "python", P + "cairo-lib"],
                   base="mingw-w64-pycairo")  # el board dibuja con cairo (set_draw_func)
    espejo.paquete("gobject-introspection-runtime", depende=[P + "glib2>=2.80"])
    espejo.paquete("glib2", depende=[P + "libffi"], archivos={
        "ucrt64/share/licenses/glib2/COPYING":
            b"                  GNU LESSER GENERAL PUBLIC LICENSE\n"
            b"                       Version 2.1, February 1999\n"})
    espejo.paquete("libffi")
    espejo.paquete("cairo", provee=[P + "cairo-lib"], depende=[P + "lzo2", P + "gnutls"])
    # Como en MSYS2: GPL sin excepción de enlace que GTK arrastra, y un paquete LGPL con
    # programas GPL.
    espejo.paquete("libtiff", depende=[P + "jbigkit"], archivos={
        "ucrt64/bin/libtiff-6.dll": b"MZ",
        "ucrt64/share/licenses/libtiff/COPYING": b"licencia de mentira de libtiff"})
    espejo.paquete("jbigkit", licencia="spdx:GPL-2.0", archivos={
        "ucrt64/bin/libjbig-0.dll": b"MZ", "ucrt64/share/licenses/jbigkit/COPYING": b"GPL"})
    espejo.paquete("lzo2", licencia="spdx:GPL-2.0-or-later",
                   archivos={"ucrt64/bin/liblzo2-2.dll": b"MZ"})
    espejo.paquete("gnutls", licencia="spdx:GPL-3.0-or-later AND spdx:LGPL-2.1-or-later", archivos={
        "ucrt64/bin/libgnutls-30.dll": b"MZ", "ucrt64/bin/libgnutls-openssl-27.dll": b"MZ",
        "ucrt64/bin/certtool.exe": b"MZ",
        "ucrt64/share/licenses/gnutls/COPYING":
            b"                    GNU GENERAL PUBLIC LICENSE\n"
            b"                       Version 3, 29 June 2007\n"})
    espejo.paquete("libadwaita", depende=[P + "gtk4"])
    # Única fuente, en este repositorio de mentira, del texto de la LGPL-3.0 (gmp, nettle,
    # libidn2 la declaran de verdad; aquí basta con que algún paquete la traiga).
    espejo.paquete("librsvg", depende=[P + "glib2"], archivos={
        "ucrt64/share/licenses/librsvg/COPYING.LESSERv3":
            b"              GNU LESSER GENERAL PUBLIC LICENSE\n"
            b"                   Version 3, 29 June 2007\n"})
    espejo.paquete("adwaita-icon-theme")
    espejo.paquete("tcl")
    espejo.paquete("tk", depende=[P + "tcl"])


class ElRepositorioDeMsys2(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.espejo = Espejo(self.tmp)
        repositorio_minimo(self.espejo)
        self.espejo.publicar()

    def indice(self):
        return construir.leer_indice((self.tmp / "ucrt64.db").read_bytes())

    def test_resuelve_las_dependencias_sin_version_y_por_provides(self):
        nombres = [p.nombre[len(P):] for p in construir.resolver(self.indice())]
        self.assertEqual(nombres, sorted([
            "python", "python-gobject", "python-cairo", "gobject-introspection-runtime", "glib2",
            "libffi",
            "gtk4", "cairo", "libadwaita", "librsvg", "adwaita-icon-theme", "libtiff",
            "gnutls"]))

    def test_tcl_y_tk_se_cortan_aunque_python_los_pida(self):
        nombres = {p.nombre for p in construir.resolver(self.indice())}
        self.assertFalse({P + "tcl", P + "tk"} & nombres)

    def test_jbigkit_y_lzo2_no_se_bajan_aunque_gtk_los_arrastre(self):
        # Son GPL sin excepción de enlace y GTK los carga en el proceso de Cotejo: va una
        # sustituta propia en su lugar.
        nombres = {p.nombre for p in construir.resolver(self.indice())}
        self.assertFalse({P + "jbigkit", P + "lzo2"} & nombres)
        self.assertEqual(set(construir.SUSTITUTAS), {"jbigkit", "lzo2"})
        for paquete in construir.SUSTITUTAS:
            self.assertTrue((AQUI / "sustitutas" / f"{paquete}.c").is_file(), paquete)

    def test_un_paquete_gpl_que_nadie_reviso_para_la_construccion(self):
        indice = self.indice()
        self.assertEqual(construir.gpl_sin_revisar(construir.resolver(indice)), [])
        indice[P + "readline"] = construir.Paquete(P + "readline", "r.pkg", "0",
                                                  licencia="spdx:GPL-3.0-or-later")
        indice[P + "glib2"].depende.append(P + "readline")
        self.assertEqual(construir.gpl_sin_revisar(construir.resolver(indice)), [P + "readline"])

    def test_la_lgpl_sola_no_cuenta_como_gpl(self):
        paquete = construir.Paquete(P + "pango", "p.pkg", "0", licencia="spdx:LGPL-2.1-or-later")
        self.assertEqual(construir.gpl_sin_revisar([paquete]), [])

    def test_lo_que_falta_se_dice_todo_junto(self):
        indice = self.indice()
        del indice[P + "libffi"], indice[P + "librsvg"]
        with self.assertRaises(construir.ErrorDeConstruccion) as error:
            construir.resolver(indice)
        self.assertIn(P + "libffi", str(error.exception))
        self.assertIn(P + "librsvg", str(error.exception))

    def test_un_paquete_que_no_cuadra_con_el_indice_no_se_usa(self):
        self.espejo.paquete("libffi", sha="0" * 64)
        self.espejo.publicar()
        paquete = self.indice()[P + "libffi"]
        cache = self.tmp / "cache"
        with self.assertRaises(construir.ErrorDeConstruccion):
            construir.bajar(f"{self.tmp.as_uri()}/{paquete.archivo}", cache, paquete.sha256)
        self.assertFalse((cache / paquete.archivo).exists())

    def test_desempaqueta_sin_el_prefijo_ni_los_archivos_de_pacman(self):
        runtime = self.tmp / "runtime"
        datos = (self.tmp / self.indice()[P + "python"].archivo).read_bytes()
        construir.desempaquetar(datos, runtime)
        self.assertTrue((runtime / "bin" / "python.exe").is_file())
        self.assertFalse((runtime / ".PKGINFO").exists())
        self.assertFalse((runtime / "ucrt64").exists())

    def test_los_enlaces_se_ponen_como_copias(self):
        # Como en libdeflate de verdad: un enlace duro con la ruta entera del paquete.
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            info = tarfile.TarInfo("ucrt64/bin/gzip.exe")
            info.size = 3
            tar.addfile(info, io.BytesIO(b"exe"))
            for tipo, nombre, destino in ((tarfile.LNKTYPE, "ucrt64/bin/gunzip.exe",
                                           "ucrt64/bin/gzip.exe"),
                                          (tarfile.SYMTYPE, "ucrt64/bin/zcat.exe", "gzip.exe")):
                enlace = tarfile.TarInfo(nombre)
                enlace.type, enlace.linkname = tipo, destino
                tar.addfile(enlace)
        runtime = self.tmp / "runtime"
        construir.desempaquetar(buffer.getvalue(), runtime)
        for nombre in ("gunzip.exe", "zcat.exe"):
            ruta = runtime / "bin" / nombre
            self.assertFalse(ruta.is_symlink(), nombre)
            self.assertEqual(ruta.read_bytes(), b"exe")

    def test_un_paquete_zstd_se_lee_en_streaming(self):
        # Los de MSYS2 son .tar.zst; los de este espejo de mentira, .tar.gz. Se comprime con lo
        # mismo que construir.py sabe leer: compression.zstd (3.14) o zstandard.
        try:
            from compression import zstd
        except ImportError:
            try:
                import zstandard as zstd
            except ImportError:
                self.skipTest("ni compression.zstd (Python 3.14) ni zstandard")
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            info = tarfile.TarInfo("ucrt64/bin/python.exe")
            info.size = 3
            tar.addfile(info, io.BytesIO(b"exe"))
        runtime = self.tmp / "runtime"
        paquete = self.tmp / "p.pkg.tar.zst"
        paquete.write_bytes(zstd.compress(buffer.getvalue()))
        construir.desempaquetar(paquete, runtime)
        self.assertEqual((runtime / "bin" / "python.exe").read_bytes(), b"exe")

    def test_un_enlace_que_se_sale_del_runtime_no_se_sigue(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            enlace = tarfile.TarInfo("ucrt64/bin/fuera.exe")
            enlace.type, enlace.linkname = tarfile.SYMTYPE, "../../../../etc/passwd"
            tar.addfile(enlace)
        with self.assertRaises(construir.ErrorDeConstruccion):
            construir.desempaquetar(buffer.getvalue(), self.tmp / "runtime")


def _tar_interno(archivos):
    """El .tar.gz de mentira que simula el código fuente original dentro de un .src.tar.zst."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for ruta, datos in archivos.items():
            info = tarfile.TarInfo(ruta)
            info.size = len(datos)
            tar.addfile(info, io.BytesIO(datos))
    return buffer.getvalue()


class LaLicenciaDelCodigoFuente(unittest.TestCase):
    """H8: cuando el binario de MSYS2 no trae la licencia de un paquete, se saca de su fuente."""

    def test_saca_el_copying_de_la_raiz_del_codigo_fuente(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "mingw-w64-ejemplo-1.2-3.src.tar.zst"
            ruta.write_bytes(tar_gz({
                "mingw-w64-ejemplo/PKGBUILD": b"# mas corto que la fuente, y no cuenta",
                "mingw-w64-ejemplo/ejemplo-1.2.tar.gz": _tar_interno({
                    "ejemplo-1.2/COPYING": b"texto de la licencia",
                    "ejemplo-1.2/main.c": b"int main(){}" * 10}),  # código, no licencia
            }))
            licencias = construir.licencias_del_paquete_fuente(ruta)
        self.assertEqual(licencias, {"COPYING": b"texto de la licencia"})

    def test_sin_copying_en_la_raiz_usa_debian_copyright(self):
        # Como ca-certificates: reempaqueta datos de Mozilla sin su propio COPYING.
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "mingw-w64-datos-1-1.src.tar.zst"
            ruta.write_bytes(tar_gz({
                "mingw-w64-datos/PKGBUILD": b"#",
                "mingw-w64-datos/datos-1.tar.gz": _tar_interno({
                    "datos-1/debian/copyright": b"licencias segun debian",
                    "datos-1/main.c": b"int main(){}" * 10}),
            }))
            licencias = construir.licencias_del_paquete_fuente(ruta)
        self.assertEqual(licencias, {"copyright": b"licencias segun debian"})

    def test_completa_solo_lo_que_de_verdad_se_reparte(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            runtime = tmp / "runtime" / "bin"
            runtime.mkdir(parents=True)
            (runtime / "libejemplo.dll").write_bytes(b"MZ")  # lo que sobrevivió a podar()
            fuentes = tmp / "fuentes"
            fuentes.mkdir()
            (fuentes / "mingw-w64-ejemplo-1.0-1.src.tar.zst").write_bytes(tar_gz({
                "mingw-w64-ejemplo/PKGBUILD": b"#",
                "mingw-w64-ejemplo/ejemplo-1.0.tar.gz": _tar_interno(
                    {"ejemplo-1.0/COPYING": b"MIT de mentira"}),
            }))
            presente = construir.Paquete(P + "ejemplo", "ejemplo.pkg", "0", licencia="spdx:MIT",
                                         base="mingw-w64-ejemplo", version="1.0-1")
            # «fantasma» no dejó ningún archivo en el runtime (como egl-headers o gles-headers,
            # que podar() les quita hasta la última cabecera): no hay que pedirle su licencia, y
            # si se intentara, fallaría: no hay ningún .src.tar.zst suyo en `fuentes`.
            fantasma = construir.Paquete(P + "fantasma", "fantasma.pkg", "0", licencia="spdx:MIT",
                                         base="mingw-w64-fantasma", version="1.0-1")
            with mock.patch.object(construir, "avisar"):
                construir.completar_licencias(tmp / "runtime", [presente, fantasma], {"ejemplo"},
                                              fuentes.as_uri(), tmp / "cache")
            self.assertEqual((tmp / "runtime" / "share" / "licenses" / "ejemplo" / "COPYING")
                             .read_bytes(), b"MIT de mentira")
            self.assertFalse((tmp / "runtime" / "share" / "licenses" / "fantasma").exists())

    def test_python_no_se_vuelve_a_bajar_si_ya_esta_en_su_carpeta_con_version(self):
        # Pasó de verdad: python.exe deja su licencia en share/licenses/python3.14/, no en
        # share/licenses/python/, y sin este alias H8 la bajaba otra vez, de más.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            licencias = tmp / "runtime" / "share" / "licenses" / "python3.14"
            licencias.mkdir(parents=True)
            (licencias / "LICENSE").write_bytes(b"PSF de verdad")
            (tmp / "runtime" / "bin").mkdir()
            (tmp / "runtime" / "bin" / "python.exe").write_bytes(b"MZ")
            paquete = construir.Paquete(P + "python", "python.pkg", "0", licencia="spdx:PSF-2.0",
                                        base="mingw-w64-python", version="3.14.7-1")
            with mock.patch.object(construir, "avisar"), \
                    mock.patch.object(construir, "bajar_fuente",
                                      side_effect=AssertionError("no debería bajarla de nuevo")):
                construir.completar_licencias(tmp / "runtime", [paquete], {"python"},
                                              "file:///no-debería-usarse", tmp / "cache")
            self.assertFalse((tmp / "runtime" / "share" / "licenses" / "python").exists())

    def test_sin_licencia_en_ningun_lado_falla_con_un_mensaje_util(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "runtime" / "bin").mkdir(parents=True)
            (tmp / "runtime" / "bin" / "x.dll").write_bytes(b"MZ")
            fuentes = tmp / "fuentes"
            fuentes.mkdir()
            (fuentes / "mingw-w64-x-1-1.src.tar.zst").write_bytes(tar_gz({
                "mingw-w64-x/PKGBUILD": b"#",
                "mingw-w64-x/x-1.tar.gz": _tar_interno({"x-1/main.c": b"sin licencia aqui"}),
            }))
            paquete = construir.Paquete(P + "x", "x.pkg", "0", licencia="spdx:MIT",
                                        base="mingw-w64-x", version="1-1")
            with mock.patch.object(construir, "avisar"), \
                    self.assertRaises(construir.ErrorDeConstruccion) as error:
                construir.completar_licencias(tmp / "runtime", [paquete], {"x"},
                                              fuentes.as_uri(), tmp / "cache")
        self.assertIn("x", str(error.exception))


class LaCargaDelLanzador(unittest.TestCase):
    def test_la_orden_va_y_vuelve(self):
        for orden, _ in construir.LANZADORES.values():
            with self.subTest(orden):
                self.assertEqual(construir.leer_carga(b"MZ..." + construir.carga(orden)), orden)

    def test_sin_carga_no_hay_orden(self):
        self.assertIsNone(construir.leer_carga(b"MZ" + b"\0" * 64))

    def test_cabe_en_el_buffer_del_lanzador(self):
        # lanzador.c la lee en `orden[2048]` wchar_t, con su cero al final.
        for orden, _ in construir.LANZADORES.values():
            self.assertLess(len(orden.encode("utf-16-le")), 2048 * 2)

    def test_solo_los_nombres_de_hoy(self):
        # Los de antes del cambio de nombre son compatibilidad de Linux: en Windows no hubo
        # ninguna instalación vieja a la que responder (cotejo-8m34uu).
        en_windows = {Path(n).name for n in construir.LANZADORES if n.startswith("bin/")}
        self.assertEqual(en_windows, {"cotejo", "cotejoboard", "cotejo-notion"})

    def test_lo_que_corren_existe(self):
        for orden, _ in construir.LANZADORES.values():
            with self.subTest(orden):
                if orden.startswith("@"):
                    self.assertTrue((RAIZ / orden[1:].replace("\\", "/")).is_file())
                else:
                    modulo = orden.removeprefix("-m ")
                    self.assertIsNotNone(importlib.util.find_spec(modulo), modulo)

    def test_el_board_es_el_unico_de_ventana(self):
        de_ventana = [n for n, (_, ventana) in construir.LANZADORES.items() if ventana]
        self.assertEqual(de_ventana, ["bin/cotejoboard"])

    def test_cada_funcion_de_win32_que_usa_esta_declarada_para_importar(self):
        codigo = (AQUI / "lanzador.c").read_text(encoding="utf-8")
        declaradas = set(re.findall(r"^IMPORTADA [\w *]+?(\w+)\(", codigo, re.M))
        importadas = {f for funciones in construir.IMPORTACIONES.values() for f in funciones}
        self.assertEqual(declaradas, importadas)


@unittest.skipUnless(HAY_LLVM, "sin clang y lld-link no se compilan las sustitutas")
class LasSustitutas(unittest.TestCase):
    # Lo que libtiff 4.7 y libcairo-script-interpreter 1.18 de MSYS2 les importan.
    PIDEN = {"libjbig-0.dll": {"jbg_dec_free", "jbg_dec_getimage", "jbg_dec_getsize",
                               "jbg_dec_in", "jbg_dec_init", "jbg_enc_free", "jbg_enc_init",
                               "jbg_enc_out", "jbg_newlen", "jbg_strerror"},
             "liblzo2-2.dll": {"lzo2a_999_compress", "lzo2a_decompress"}}

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        cls.binarios = construir.compilar_sustitutas(cls.tmp / "trabajo")
        cls.lanzadores = construir.compilar_lanzadores(cls.tmp / "lanzadores")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_exportan_lo_que_les_piden_y_no_importan_nada(self):
        self.assertEqual(set(self.binarios), set(self.PIDEN))
        for dll, datos in self.binarios.items():
            with self.subTest(dll):
                self.assertLessEqual(self.PIDEN[dll], construir.exportes(datos))
                self.assertEqual(construir.importes(datos), {})

    def test_el_lector_de_importaciones_lee_un_pe_de_verdad(self):
        importa = construir.importes(self.lanzadores[True])
        self.assertLessEqual(importa["kernel32.dll"], set(construir.IMPORTACIONES["kernel32"]))
        self.assertIn("MessageBoxW", importa["user32.dll"])

    def test_si_el_runtime_les_pide_algo_que_no_tienen_no_se_construye(self):
        runtime = self.tmp / "runtime"
        (runtime / "bin").mkdir(parents=True, exist_ok=True)
        (runtime / "bin" / "libtiff-6.dll").write_bytes(b"MZ")
        construir.poner_sustitutas(runtime, self.binarios)  # MZ suelto: no es un PE, se salta
        pide = {"libjbig-0.dll": self.PIDEN["libjbig-0.dll"] | {"jbg_funcion_nueva"}}
        with mock.patch.object(construir, "importes", return_value=pide), \
                self.assertRaises(construir.ErrorDeConstruccion) as error:
            construir.comprobar_sustitutas(runtime, self.binarios)
        self.assertIn("jbg_funcion_nueva", str(error.exception))


    def test_un_certificado_que_no_verifica_explica_que_hacer(self):
        # Prueba a mano del 2026-10-06: un Windows recién instalado no tenía el intermedio de
        # repo.msys2.org y el OpenSSL de Python no lo baja. Sin truststore, un mensaje que lo diga.
        error = construir.urllib.error.URLError(construir.ssl.SSLCertVerificationError("x"))
        with mock.patch.object(construir.urllib.request, "urlopen", side_effect=error), \
                mock.patch.dict("sys.modules", {"truststore": None}), \
                self.assertRaisesRegex(construir.ErrorDeConstruccion, "truststore"):
            construir.bajar("https://repo.msys2.org/nada.db", self.tmp / "otra-cache")
        self.assertEqual(list((self.tmp / "otra-cache").iterdir()), [])


class ElIcono(unittest.TestCase):
    def test_es_un_ico_con_el_tamano_grande(self):
        datos = (AQUI / "cotejo.ico").read_bytes()
        reservado, tipo, cuantos = construir.struct.unpack("<HHH", datos[:6])
        self.assertEqual((reservado, tipo), (0, 1))
        lados = [datos[6 + 16 * i] for i in range(cuantos)]
        self.assertIn(0, lados)  # 0 es 256
        self.assertIn(16, lados)


class ElInstalador(unittest.TestCase):
    def setUp(self):
        self.iss = (AQUI / "cotejo.iss").read_text(encoding="utf-8-sig")

    def test_instala_para_el_usuario_sin_administrador(self):
        self.assertIn("PrivilegesRequired=lowest", self.iss)
        self.assertIn("HKCU", self.iss)
        self.assertNotIn("HKLM", self.iss)

    def test_el_menu_y_el_path_apuntan_a_lanzadores_que_existen(self):
        nombres = {n.replace("/", "\\") + ".exe" for n in construir.LANZADORES}
        for ruta in re.findall(r"\{app\}\\((?:bin|interno)\\[\w-]+\.exe)", self.iss):
            self.assertIn(ruta, nombres)
        self.assertIn("{app}\\bin", self.iss)

    def test_las_tipografias_que_instala_estan_en_el_repo(self):
        for nombre in re.findall(r"app\\data\\fonts\\([^\"]+)\"", self.iss):
            self.assertTrue((RAIZ / "data" / "fonts" / nombre).is_file(), nombre)

    def test_el_nombre_del_exe_es_el_que_construir_espera(self):
        self.assertIn("OutputBaseFilename=Cotejo-{#Version}-windows-x64-instalador", self.iss)

    def test_sin_iscc_no_falla_y_dice_como_compilarlo(self):
        with mock.patch.object(construir.shutil, "which", return_value=None), \
                mock.patch.dict(construir.os.environ, {"ProgramFiles": "/nada",
                                                       "ProgramFiles(x86)": "/nada"}), \
                mock.patch.object(construir, "avisar") as avisar:
            self.assertIsNone(construir.instalador(Path("/c/Cotejo"), "1", Path("/c")))
        self.assertIn("iscc", avisar.call_args[0][0])


@unittest.skipUnless(HAY_LLVM, "sin clang, lld-link y llvm-dlltool no se compilan los lanzadores")
class LaConstruccionEntera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name)
        espejo = Espejo(cls.tmp / "espejo")
        espejo.carpeta.mkdir()
        repositorio_minimo(espejo)
        with mock.patch.object(construir, "avisar"):
            cls.hecho = construir.construir(cls.tmp / "salida", "9.9.9", espejo.publicar(),
                                            cls.tmp / "cache", con_instalador=False)
        cls.carpeta = cls.hecho["carpeta"]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_cada_comando_es_un_exe_de_su_subsistema_con_su_orden(self):
        for nombre, (orden, ventana) in construir.LANZADORES.items():
            with self.subTest(nombre):
                exe = (self.carpeta / f"{nombre}.exe").read_bytes()
                self.assertEqual(construir.subsistema(exe), 2 if ventana else 3)
                self.assertEqual(construir.leer_carga(exe), orden)

    def test_la_app_va_entera_y_sin_cache_de_python(self):
        app = self.carpeta / "app"
        for ruta in ("tareas/cli.py", "tareas/rutas.py", "enrutador/decision.py",
                     "skills/cotejo/SKILL.md", "extras/notion/cotejo_notion.py",
                     "data/temas", "data/marca", "data/fonts/OFL.txt", "LICENSE",
                     "data/io.github.cotejoapp.Cotejo.svg"):
            self.assertTrue((app / ruta).exists(), ruta)
        self.assertEqual(list(app.rglob("__pycache__")), [])

    def test_el_license_de_windows_lleva_bom_para_inno_setup(self):
        # H7: `cotejo.iss` muestra app\LICENSE como página de licencia (LicenseFile). Sin BOM,
        # Inno Setup puede leer un .txt con tildes como ANSI y mostrarlo con mojibake.
        datos = (self.carpeta / "app" / "LICENSE").read_bytes()
        self.assertTrue(datos.startswith(codecs.BOM_UTF8), "app\\LICENSE sin BOM UTF-8")
        # El contenido, aparte del BOM, es el mismo texto que el del repo (sin BOM): no cambia
        # ningún derecho ni obligación, solo cómo se decodifica.
        self.assertEqual(datos[len(codecs.BOM_UTF8):].decode("utf-8"),
                         (construir.RAIZ / "LICENSE").read_text(encoding="utf-8"))

    def test_el_runtime_esta_donde_lo_busca_el_lanzador_y_podado(self):
        runtime = self.carpeta / "runtime"
        self.assertTrue((runtime / "bin" / "python.exe").is_file())
        self.assertTrue((runtime / "bin" / "pythonw.exe").is_file())
        for podado in ("include", "lib/libpython3.12.dll.a", "lib/python3.12/test"):
            self.assertFalse((runtime / podado).exists(), podado)
        self.assertFalse((runtime / "share" / "tk").exists())
        self.assertTrue((runtime / "bin" / "libgtk-4-1.dll").is_file())
        self.assertFalse((runtime / "bin" / "gtk4-demo.exe").exists())
        paquetes = (runtime / "PAQUETES.txt").read_text()
        self.assertIn("libadwaita", paquetes)
        self.assertIn("licencia:spdx:MIT", paquetes)

    def test_nada_gpl_en_el_runtime_y_las_sustitutas_en_su_sitio(self):
        runtime = self.carpeta / "runtime"
        paquetes = (runtime / "PAQUETES.txt").read_text()
        self.assertNotIn("jbigkit", paquetes)
        self.assertNotIn("lzo2", paquetes)
        self.assertFalse((runtime / "share" / "licenses" / "jbigkit").exists())
        for dll in construir.SUSTITUTAS.values():
            self.assertIn("jbg_" if "jbig" in dll else "lzo2a_",
                          " ".join(construir.exportes((runtime / "bin" / dll).read_bytes())))
        self.assertTrue((runtime / "bin" / "libgnutls-30.dll").is_file())
        for podado in ("libgnutls-openssl-27.dll", "certtool.exe"):
            self.assertFalse((runtime / "bin" / podado).exists(), podado)

    def test_la_lgpl_va_donde_la_promete_third_party_notices(self):
        lgpl = self.carpeta / "licenses" / "LGPL-2.1.txt"
        self.assertIn("Version 2.1", lgpl.read_text())
        self.assertIn("licenses/LGPL-2.1.txt", (construir.RAIZ / "THIRD-PARTY-NOTICES").read_text())

    def test_la_lgpl3_y_la_gpl3_tambien_van_donde_las_promete_third_party_notices(self):
        # LGPL-3 residual: gmp, nettle, libidn2 y libunistring la declaran, y su texto no estaba.
        lgpl3 = self.carpeta / "licenses" / "LGPL-3.0.txt"
        gpl3 = self.carpeta / "licenses" / "GPL-3.0.txt"
        self.assertIn("Version 3", lgpl3.read_text())
        self.assertIn("LESSER", lgpl3.read_text())
        self.assertIn("Version 3", gpl3.read_text())
        self.assertNotIn("LESSER", gpl3.read_text())
        notices = (construir.RAIZ / "THIRD-PARTY-NOTICES").read_text()
        self.assertIn("licenses/LGPL-3.0.txt", notices)
        self.assertIn("licenses/GPL-3.0.txt", notices)

    def test_cada_paquete_que_reparte_algo_tiene_su_licencia(self):
        # H8: a ningún paquete presente en el runtime le falta `share/licenses/<paquete>/`, ni
        # siquiera a los que el binario de MSYS2 no la trae (aquí no hay ninguno así, pero esto
        # se pone rojo si `completar_licencias` deja de correr dentro de `armar_runtime`).
        licencias = self.carpeta / "runtime" / "share" / "licenses"
        for nombre in ("python", "gtk4", "glib2", "libtiff", "gnutls", "librsvg"):
            self.assertTrue((licencias / nombre).is_dir(), nombre)
            self.assertTrue(any((licencias / nombre).iterdir()), nombre)

    def test_solo_quedan_las_traducciones_en_espanol_e_ingles(self):
        idiomas = {p.name for p in (self.carpeta / "runtime" / "share" / "locale").iterdir()}
        self.assertEqual(idiomas, {"es", "es_AR", "en_GB"})

    def test_solo_la_carpeta_que_empaqueta_el_instalador_sin_zip(self):
        # Sin ZIP portable: una carpeta suelta sin PATH no le sirve a los agentes.
        self.assertEqual(set(self.hecho), {"carpeta"})
        self.assertEqual(list((self.tmp / "salida").glob("*.zip")), [])
        for ruta in ("bin/cotejo.exe", "runtime/bin/python.exe", "cotejo.ico"):
            self.assertTrue((self.carpeta / ruta).is_file(), ruta)

    def test_lo_bajado_queda_en_la_cache_y_se_reusa(self):
        self.assertTrue(any((self.tmp / "cache").glob("*.pkg.tar.gz")))
        with mock.patch.object(construir.urllib.request, "urlopen",
                               side_effect=AssertionError("volvió a bajarlo")):
            paquete = next(iter(construir.leer_indice(
                (self.tmp / "espejo" / "ucrt64.db").read_bytes()).values()))
            construir.bajar(f"file:///nada/{paquete.archivo}", self.tmp / "cache", paquete.sha256)


class ElIcono(unittest.TestCase):
    def test_el_ico_sale_del_svg_de_hoy(self):
        # Si cambia el logo, esto se pone rojo hasta correr empaquetado/windows/icono.py.
        construir.comprobar_icono()


class LosScriptsDeProbarEnWindows(unittest.TestCase):
    """`probar_instalado.py`, `probar_despachar.py` y `probar_almacen.py` no se pueden correr
    aquí —abren `winreg`, piden un `cotejo.exe` ya instalado o Win32 puro—, pero importarlos
    (como ya se hace arriba con `construir.py`) sí, y eso basta para que un error de sintaxis
    o un nombre mal escrito salga aquí y no en el primer run del runner de Windows, que cuenta
    doble y no corre en cada push.
    """

    def test_importan_sin_reventar(self):
        for nombre in ("probar_instalado.py", "probar_despachar.py", "probar_almacen.py"):
            with self.subTest(script=nombre):
                spec = importlib.util.spec_from_file_location(nombre, AQUI / nombre)
                modulo = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(modulo)
                if hasattr(modulo, "VACIA"):  # probar_instalado.py se hace una carpeta al importar
                    self.addCleanup(shutil.rmtree, modulo.VACIA, ignore_errors=True)
                self.assertTrue(callable(modulo.main), f"{nombre} no define main()")

    def test_probar_almacen_encuentra_el_cotejo_del_argumento_o_del_path(self):
        # Lo que en el runner de Windows resuelve al instalador recién instalado, y en Linux
        # (aquí, para poder correrlo antes de pedirle a nadie que lo pruebe en Windows) a lo
        # que se le pase: el mismo contrato que piden las instrucciones de la tarea.
        spec = importlib.util.spec_from_file_location("probar_almacen", AQUI / "probar_almacen.py")
        probar_almacen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probar_almacen)
        falso = RAIZ / "pruebas" / "apoyo.py"  # cualquier archivo real, no se ejecuta
        self.assertEqual(probar_almacen.localizar_cotejo([str(falso)]), falso.resolve())
        with mock.patch.dict("os.environ", {"COTEJO_BIN": str(falso)}):
            self.assertEqual(probar_almacen.localizar_cotejo([]), falso.resolve())
        with self.assertRaises(SystemExit):
            probar_almacen.localizar_cotejo(["/no/existe/de/verdad"])

    def test_probar_almacen_deja_la_raiz_del_repo_por_debajo_del_limite_de_git(self):
        # git no puede tener la raíz de un repo por encima de ~248 caracteres en Windows (prueba
        # a mano de F1): la raíz se acerca al límite y lo largo son los archivos de dentro.
        spec = importlib.util.spec_from_file_location("probar_almacen", AQUI / "probar_almacen.py")
        probar_almacen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probar_almacen)
        from tareas.importar_obsidian import RAIZ_GIT_MAXIMA_WINDOWS
        self.assertLess(probar_almacen.LARGO_RAIZ, RAIZ_GIT_MAXIMA_WINDOWS)
        base = r"C:\Users\User\AppData\Local\Temp\cotejo-almacen-abcdefgh"
        raiz = probar_almacen.raiz_al_limite(base, "repo")
        self.assertLessEqual(len(str(raiz)), probar_almacen.LARGO_RAIZ)
        self.assertGreater(len(str(raiz)), probar_almacen.LARGO_RAIZ - 5)
        self.assertEqual(raiz.name, "repo")
        self.assertIn("áéíóúñ", str(raiz))
        self.assertTrue(all(not parte.endswith((" ", ".")) for parte in raiz.parts))


if __name__ == "__main__":
    unittest.main()
