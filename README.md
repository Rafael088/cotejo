# Cotejo — Releases

Este repositorio aloja los artefactos publicados de [Cotejo](https://github.com/Rafael088/cotejo): instaladores, paquetes y archivos portables listos para usar.

> **Tus agentes entregan. Tú compruebas.** Cotejo es un board de pendientes de escritorio que lee las tareas de tu segundo cerebro y decide qué modelo puede atender cada una.

## Descargar la última versión

Ve a [Releases](../../releases/latest) y elige el archivo para tu sistema:

| Archivo | Sistema | Qué es |
|---|---|---|
| `cotejo-<version>-linux.tar.gz` | Linux | Descomprime y corre `./install.sh`. |
| `Cotejo-<version>-windows-x64.zip` | Windows | Portable: descomprime y corre `bin\cotejoboard.exe`. |
| `Cotejo-<version>-windows-x64-instalador.exe` | Windows | Instalador con PATH, menú Inicio y tipografías. |
| `cotejo-<version>-1-any.pkg.tar.zst` | Arch / Omarchy | Paquete de pacman: `sudo pacman -U cotejo-…-pkg.tar.zst`. |

Cada release lleva sus checksums SHA-256 en el cuerpo de la nota y en el archivo `SHA256SUMS`
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
