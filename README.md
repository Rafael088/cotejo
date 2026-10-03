# Cotejo — Releases

Este repositorio aloja los artefactos publicados de [Cotejo](https://github.com/Rafael088/cotejo): instaladores y paquetes listos para usar.

> **Tus agentes entregan. Tú compruebas.** Cotejo es un board de pendientes de escritorio que lee las tareas de tu segundo cerebro y decide qué modelo puede atender cada una.

> [!WARNING]
> **Cotejo 1.1 es software en fase beta.** Todavía puede tener fallos o comportarse de forma
> inesperada. Se ofrece «tal cual», sin garantías de ningún tipo, como dice su licencia
> ([`LICENSE`](LICENSE), cláusula 8). Haz copia de tu segundo cerebro antes de probarlo y, si algo
> falla, cuéntalo en un [issue](../../issues).

## Descargar la última versión

Abre la [última versión](../../releases/latest) y descarga el archivo de tu sistema: la nota
trae el enlace de cada uno, y también están en la lista **Assets** al final de la página.

| Archivo | Sistema | Qué es |
|---|---|---|
| `Cotejo-<version>-windows-x64-instalador.exe` | Windows 10/11 | Doble clic: menú Inicio, `cotejo` en el PATH, tipografías y aviso a tus agentes. Sin administrador. |
| `cotejo-<version>-1-any.pkg.tar.zst` | Arch / Omarchy | Paquete de pacman: `sudo pacman -U cotejo-…-pkg.tar.zst`. |
| `cotejo-<version>-linux.tar.gz` | Otras distribuciones de Linux | Descomprime y corre `./install.sh`. |

Cada release lleva el archivo `SHA256SUMS` con los checksums SHA-256 de todos sus archivos
(`sha256sum -c SHA256SUMS`). `Cotejo-<version>-fuentes-terceros.tar` trae el código fuente de
los componentes LGPL/GPL que incluye la versión de Windows.

## Si te sirve

Puedes invitar al autor a un café:

**[☕ Donar con Mercado Pago](https://link.mercadopago.com.co/cotejo)**

## Licencia

Cotejo es software propietario de uso gratuito: su licencia está en [`LICENSE`](LICENSE) y dentro
de cada paquete. Los componentes de terceros que incluye (Python, GTK, libadwaita, etc.) conservan
sus propias licencias: ver [`THIRD-PARTY-NOTICES`](THIRD-PARTY-NOTICES). Para dudas o problemas,
abre un [issue](../../issues).
