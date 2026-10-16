# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Framer Motion (`motion`), con Vite, salida estática para GitHub Pages con dominio propio. Vive en `web/` dentro del repo `cotejo`; se publica desde el repo público de releases.

## Users

Desarrolladores primero: personas que trabajan con agentes de código (Claude Code, Codex, opencode, Gemini CLI) y quieren que lo que construyen con vibe coding quede estructurado y pueda crecer. Quien no programa también puede usar Cotejo, pero entra **a través de su agente y de una revisión en lenguaje llano**, sin una interfaz propia. Llegan en español, en su mayoría desde el canal de YouTube y sus directos, donde se ve Cotejo usado de verdad. Su trabajo en la página: entender en segundos qué hace, convencerse de que les da control sobre lo que entregan sus agentes y copiar el comando de instalación. Hay que decirles, sin rodeos, que instalar pide pegar un comando en una terminal (o pedírselo a su agente).

## Product Purpose

**Qué es:** el tablero de control para tu vibe coding. Tus agentes escriben el código; Cotejo ordena el proyecto, reparte las tareas y no da nada por hecho hasta que tú lo revisas. No escribe código por ti.

**Para qué sirve:** que cualquier persona, programe o no, construya software con IA de forma estructurada y que pueda crecer. Cada proyecto guarda su contexto, sus decisiones y su arquitectura en `.cotejo/`, dentro de su propio repo; cada tarea va al modelo adecuado (el enrutador); y nada se da por hecho sin evidencia y sin tu revisión.

**Cómo se usa:** con cualquier agente de terminal (Claude Code, Codex, Gemini CLI, opencode) o con cualquier agente que hable MCP. Gratis, en Windows y Linux.

Éxito: que un agente trabaje gastando pocos tokens y que «hecho» signifique «alguien lo revisó». Son CotejoBoard (GTK4 + libadwaita) y una CLI en JSON para agentes. El repo es la entrada por defecto; Obsidian y Notion son puertas para importar un proyecto que ya existe, no el discurso.

## Positioning

Muchos tableros para agentes se venden como sacar a la persona del ciclo. Cotejo hace lo contrario: no existe un verbo para finalizar; el check lo pone una persona. Y lo demuestra con un medidor de ahorro de tokens que enseña su supuesto en vez de esconderlo. «Tablero de control», no «app para vibe coding»: esto último sugiere que Cotejo escribe el código, y no lo hace.

## Operating Context

- El agente usa los verbos `tareas`, `tomar`, `entregar`, `bloquear`, `asignar`, `crear`, `estado`, `ahorro`; el enrutador `plan`, `decidir`, `despachar`, `revisar`, `maestro`, `protocolo`.
- Cada repo puede llevar su conocimiento (decisiones, arquitectura, problemas, aprendizajes, bitácora, referencias) en `.cotejo/`, un archivo por entrada. El agente se entera con `contexto`, `buscar` y `leer`, y escribe con `proponer decision`, `anotar`, `bitacora`, `editar` y `resolver`; `cotejo init` crea el esqueleto. `importar obsidian` e `importar notion` traen un proyecto entero a su `.cotejo/` de una vez (ensayo por defecto, `--aplicar` sin commit).
- Cuatro columnas: Pendiente, Haciéndola, Para comprobar, Finalizada. Finalizada la mueve solo la persona; una decisión propuesta se acepta igual, solo desde el board, nunca por un verbo.
- Las tareas viven por defecto en `.cotejo/tareas.md` del repo. Quien ya tiene el proyecto en Obsidian o Notion lo trae con `importar`; esas fuentes siguen funcionando, pero salen del hero y del discurso.
- En Linux se integra con la barra de Omarchy (widget `cotejo.barra`).

## Capabilities and Constraints

- Sistemas: Linux (tar.gz con `install.sh`, paquete de Arch/Omarchy) y Windows 10/11 x64 (instalador). No hay macOS.
- Instalación prevista por un comando servido desde el dominio de Cotejo: `curl -fsSL https://<dominio>/install.sh | sh` (Linux) e `irm https://<dominio>/install.ps1 | iex` (Windows). **Dominio sin comprar todavía**: el valor vive en una constante y está marcado como pendiente.
- Fuente por defecto: el **repo** (`.cotejo/`). Obsidian (incluida) y Notion (adaptador `cotejo-notion`) funcionan y sirven sobre todo para importar. Cualquier otra app se conecta escribiendo un adaptador (4 métodos, plantilla en `extras/plantilla/`). No se puede presentar ninguna otra app, RAG o servicio como compatible.
- Versión 1.2.4 en **beta**; licencia propietaria, gratis (se dice «gratis», nunca «libre» ni «open source»); sin macOS; donaciones por Mercado Pago (`https://link.mercadopago.com.co/cotejo`).
- Primer release en español; inglés después.

## Brand Commitments

- Nombre: **Cotejo**. Frase de pie: **«Tus agentes entregan. Tú compruebas.»** (firma en el footer y og:image). De apoyo: «Hecho es cuando alguien lo revisó.»
- Logo: la palabra «Cotejo» con la C que se cierra con un check. Lo único verde es el check. No se separa la C de «otejo», no se rota, sombrea ni degrada, no se usa texto vivo en «otejo». Kit en `docs/marca/`.
- Color: neutros del negro (`#101114`) al blanco y un único acento, **Verde Hecho** `#16C98D` (sobre claro, `#0E9F6E` en el logo y `#08734F` en texto). El verde significa «espera que lo compruebes / hecho»; no se pinta de verde otra cosa. Ámbar `#F0C987` = devuelta o bloqueada.
- Tipografías: Sora (titulares, logo), Inter (texto), IBM Plex Mono (comandos, cifras). OFL, en `data/fonts/`.
- Voz: español, tuteo, frases cortas; verbos fijos (tomar, entregar, bloquear, comprobar, rechazar); dice el porqué; **no promete productividad** (nada de «10x», «supercarga», «automatiza todo») y **solo promete lo que trae la versión publicada**; el dot no sale en la web ni en la campaña de la beta; sin emojis en la interfaz.

## Evidence on Hand

- Medidor de ahorro, medición real de la máquina del autor: razón **19,7×** (37.098 caracteres devueltos contra 730.071 leídos, ~192.000 tokens ahorrados en 4 lecturas). Estimación documentada: pendientes de un proyecto ~480 tokens contra ~4.700 de la nota; vault entero ~7.300 contra ~36.600. Supuesto declarado: que sin Cotejo el agente habría leído las notas enteras.
- 580 pruebas automáticas en verde (v1.0).
- Kit de marca en `docs/marca/`; temas de color en `data/temas/`; prototipo de CotejoBoard en `data/diseno/CotejoBoard Rediseño.dc.html`.
- No hay testimonios, clientes, capturas de prensa ni cifras de usuarios: no se inventan.

## Product Principles

1. La persona pone el check. Nada en la página sugiere que Cotejo termina el trabajo solo.
2. Medir antes que prometer: cada cifra viaja con su supuesto.
3. Hacer menos a propósito: una cosa a la vez, sin FOMO.
4. Lo verdadero hoy, sin adelantar compatibilidades que no existen.
5. Para agentes primero: JSON, verbos estrechos, ids estables.

## Accessibility & Inclusion

Contrastes WCAG AA medidos (los temas ya los vigila `pruebas/test_temas.py`). Toda animación respeta `prefers-reduced-motion`. El verde nunca es el único portador de significado.
