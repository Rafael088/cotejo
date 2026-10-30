"""El CSS del board. Sin un color: todos son `var(--k-…)` y los pone el tema."""




# Monocromo con un único acento (Verde Hecho) para lo activo o lo que se toca.
#
# Aquí no hay ni un color: todos son `var(--k-…)` y los pone el tema elegido (`tareas/temas.py`,
# que antepone su propio `:root`). Los nombres dicen el papel —fondo, superficie, texto, tenue—
# y no el color, porque en el tema claro el fondo es claro. `pruebas/test_temas.py` se pone
# roja si alguien vuelve a escribir un color literal aquí: un `#FFFFFF` suelto se ve bien en el
# oscuro y deja un botón invisible en el claro.
#
# Lo que decidió cada color, aunque los valores ya no vivan aquí:
# - Tenue (la antigua Plata) es el texto secundario; Acero no pasa AA sobre oscuro.
# - Ámbar es lo detenido o roto: ver .anotacion.detenida y el banner.
# - Cada columna se apoya en su propia superficie, un punto más clara que la ventana: así una
#   columna vacía sigue siendo una columna y no un hueco. Las separaciones de dentro del board
#   (borde-hondo) se callan: el borde fuerte es para la ventana.
# - El chip de agente deja el verde y pasa a contorno (borde-chip, texto-chip): ver .chip-agente.
# - tenue-hondo es solo el icono de un vacío: por debajo de tenue, que ya es texto, pero no tanto
#   como para dejar de verse (3:1 como mínimo; `temas comprobar` lo mide).
# - Tres velos y no uno (sutil, normal, fuerte): el hover más sutil es sobre una fila ya clara
#   del boxed-list, el intermedio sobre fondos (banda, chip) y el más fuerte es el único que
#   compite con la headerbar.
CSS = """
:root {
  /* Seis pasos de tipografía, no los diez de antes (9,5 a 15px en saltos de medio píxel que
     no se ven y redondean distinto según la escala de pantalla). Lo que manda es el papel del
     texto —etiqueta, dato mono, mensaje de estado, contenido que se lee, encabezado de sección
     o título de ventana—, no el tamaño que tenía hoy: dos reglas con el mismo papel caen en el
     mismo paso aunque antes difirieran en medio píxel. .anotacion-titulo sube de 9,5px: era el
     texto más chico de la app y además mono en mayúsculas con letter-spacing, la combinación
     que peor se lee. En la 1.2.6 (cotejo-x968aw) etiqueta y dato suben un píxel: a 11 y
     12px la mono fina en gris era lo que no se leía en Windows, y era casi todo lo pequeño.
     Dato y secundario quedan en 13px, uno en mono y el otro no: el papel lo da la letra. */
  --k-etiqueta: 12px;    /* chips, badges y etiquetas de sección: MOVER A, PROYECTOS, un chip */
  --k-dato: 13px;        /* dato mono secundario bajo un título: el sub de una tarea, un conteo */
  --k-secundario: 13px;  /* mensaje de estado o encabezado de un vacío: banda de avisos, Sin pendientes */
  --k-contenido: 14px;   /* lo que se lee como contenido: el texto de una tarea, un nombre de fila */
  --k-encabezado: 15px;  /* encabezado de una sección: columna del board, grupo de proyecto */
  --k-ventana: 16px;     /* el título de la ventana, siempre el más grande */
  --k-portada: 24px;     /* solo el titular de la pestaña Inicio (v1.3.0): es una portada, no una ventana */

  /* Escala de espaciado: cinco pasos en suma de 4px. Los valores 1, 2, 3 px (micro-ajustes
     de componentes como .boxed-list row padding, .menu-item padding)
     quedan fuera: son precisiones dentro de controles, no espaciado de layout. */
  --k-espacio-xs: 4px;   /* muy compacto: separadores, encabezados de preferencias */
  --k-espacio-sm: 8px;   /* compacto: chips, padding interno, spacing dentro de elementos */
  --k-espacio-md: 12px;  /* normal: padding estándar, spacing entre elementos */
  --k-espacio-lg: 16px;  /* amplio: separación clara entre secciones */
  --k-espacio-xl: 20px;  /* máximo: aire alrededor de contenido principal */

  /* Duración del hover de .carta y .banda-chip. La misma que ya llevaban escrita las dos
     reglas antes de tokenizarla; sube aquí porque gtk-enable-animations la apaga en las dos
     a la vez (ver .sin-animaciones más abajo) y un solo número es el que hay que tocar. */
  --k-dur-hover: 140ms;

  --window-bg-color: var(--k-fondo);
  --window-fg-color: var(--k-texto);
  --view-bg-color: var(--k-fondo);
  --view-fg-color: var(--k-texto);
  --headerbar-bg-color: var(--k-fondo);
  --headerbar-fg-color: var(--k-texto);
  --headerbar-backdrop-color: var(--k-fondo);
  --headerbar-shade-color: transparent;
  --card-bg-color: var(--k-superficie);
  --card-fg-color: var(--k-texto);
  --card-shade-color: var(--k-borde);
  --popover-bg-color: var(--k-superficie);
  --popover-fg-color: var(--k-texto);
  --dialog-bg-color: var(--k-superficie);
  --dialog-fg-color: var(--k-texto);
  --accent-bg-color: var(--k-senal);
  --accent-fg-color: var(--k-sobre-senal);
  --accent-color: var(--k-senal);
  --border-color: var(--k-borde);
  --window-radius: 16px;
  --document-font-family: "Inter";
  --monospace-font-family: "IBM Plex Mono";
}

window, .toast { font-family: "Inter", sans-serif; }
/* gtk-enable-animations apagado: la misma señal que ya consulta animaciones_activas() para la
   entrada del tablero apaga aquí --k-dur-hover, y con ella los hover de .carta y .banda-chip.
   El CSS no puede leer la propiedad de GtkSettings, así que aplicar_clase_animaciones() pone y
   quita esta clase en cada ventana, también si el ajuste cambia con la app abierta. */
window.sin-animaciones { --k-dur-hover: 0ms; }
/* Maximizada o a pantalla completa, sin esquinas, sombra ni contorno: la ventana es la
   pantalla. Adwaita ya lo hace con `.maximized`, pero en Windows GTK no pone esa clase y el
   board quedaba con las esquinas redondeadas enseñando el escritorio (cotejo-yuwm63). */
window.a-pantalla, window.a-pantalla.csd { --window-radius: 0px; border-radius: 0;
                                           box-shadow: none; outline: none; }

headerbar { min-height: 52px; box-shadow: none; border-bottom: 1px solid var(--k-borde); }
.marca-titulo { font-family: "Sora"; font-weight: 600; font-size: var(--k-ventana); letter-spacing: -0.01em; }
.marca-producto { color: var(--k-tenue); }
.dato { font-family: "IBM Plex Mono"; font-size: var(--k-dato); color: var(--k-tenue); letter-spacing: 0.06em; }
/* El subtítulo es una frase («4 sin terminar · menu-digital»), no un dato: en Inter, sin
   mayúsculas ni espaciado, que con la mono era lo que peor se leía de la cabecera. */
.marca-subtitulo { font-size: var(--k-dato); color: var(--k-tenue); }
.en-cotejo { color: var(--k-senal); }

searchbar > revealer > box { background: var(--k-fondo); border-bottom: 1px solid var(--k-borde); box-shadow: none; }
entry, searchentry { border-radius: 10px; background: var(--k-superficie); }
/* La búsqueda deja de estar escondida detrás de un botón: se ve, y dice con qué tecla se
   llama. Era la única acción que había que adivinar. */
.buscador { border-radius: 10px; background: var(--k-superficie); padding: 0 var(--k-espacio-sm); }
.buscador image { color: var(--k-tenue); }
.buscador entry, .buscador entry:focus { background: transparent; outline: none; box-shadow: none;
                                         min-height: 30px; }
.buscador:focus-within { outline: 2px solid var(--k-senal); outline-offset: -1px; }
.atajo { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
         border: 1px solid var(--k-borde); border-radius: 5px; padding: 0 var(--k-espacio-xs); }

preferencesgroup > box > box.header { margin-bottom: var(--k-espacio-xs); }
preferencesgroup .header .heading { font-family: "Sora"; font-weight: 600; font-size: var(--k-encabezado); letter-spacing: -0.015em; }
preferencesgroup .header .body { font-family: "IBM Plex Mono"; font-size: var(--k-dato); color: var(--k-tenue); letter-spacing: 0.02em; opacity: 1; }

.boxed-list { border-radius: 10px; border: 1px solid var(--k-borde); box-shadow: none; background: var(--k-superficie); }
.boxed-list > row { padding: 2px 0; }
.boxed-list > row:hover { background: var(--k-velo-sutil); }
.boxed-list > row .title { font-size: var(--k-contenido); line-height: 1.4; }
.boxed-list > row .subtitle { font-family: "IBM Plex Mono"; font-size: var(--k-dato); color: var(--k-tenue); }

checkbutton check { border-radius: 6px; border: 2px solid var(--k-tenue); background: transparent; min-width: 16px; min-height: 16px; }
checkbutton check:hover { border-color: var(--k-senal); }
checkbutton check:checked { background: var(--k-senal); border-color: var(--k-senal); color: var(--k-sobre-senal); }

button.flat { color: var(--k-tenue); border-radius: 8px; }
button.flat:hover { color: var(--k-texto); background: var(--k-velo-fuerte); }

/* Board */
.columna-titulo { font-family: "Sora"; font-weight: 600; font-size: var(--k-contenido); }
list.columna, list.columna > row { background: transparent; }
.columna-caja { background: var(--k-columna); border-radius: 12px; }
/* El contador de cada columna, en pastilla tenue. El de la que te espera es solo el número en
   verde y en negrita, sin pastilla: el mismo acento del título, sin un óvalo que lo grite. */
.cuenta-columna { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
                  background: var(--k-velo-fuerte); border-radius: 10px; padding: 1px var(--k-espacio-sm); }
.cuenta-columna.en-cotejo { color: var(--k-senal); background: transparent; font-weight: 600; }
.columna-icono { color: var(--k-tenue); }
.columna-icono.en-cotejo { color: var(--k-senal); }
/* Finalizada es la única columna que no reclama nada: su título baja a Plata. */
.columna-titulo.terminada, .columna-icono.terminada { color: var(--k-tenue); }
.carta { background: var(--k-superficie); border: 1px solid var(--k-borde); border-radius: 10px;
         padding: var(--k-espacio-md) var(--k-espacio-sm) var(--k-espacio-sm) var(--k-espacio-md); margin-bottom: var(--k-espacio-sm);
         transition: border-color var(--k-dur-hover) ease-out, background-color var(--k-dur-hover) ease-out; }
.carta:hover { border-color: var(--k-senal); background: var(--k-superficie-alta); }
/* Recorrer con Tab tiene que verse tan claro como pasar el mouse, y además saberse dónde está el foco. */
.carta:focus-visible { border-color: var(--k-senal); background: var(--k-superficie-alta);
                       outline: 2px solid var(--k-senal); outline-offset: 1px; }
/* Mientras se arrastra, la carta se queda como el hueco que dejó. */
/* El código de la carta es un dato, no una alerta: va en tenue para que el único verde
   quede en lo que de verdad espera a la persona (Para comprobar y el maestro con texto). */
.carta-codigo { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue); }
/* Pendiente solo enseña el id: carta baja, con el ⋮ a su altura. El nombre trae su propio aire. */
.carta-compacta { padding: var(--k-espacio-xs) var(--k-espacio-xs) var(--k-espacio-xs) var(--k-espacio-md); }
.carta-compacta menubutton > button { min-height: 26px; min-width: 26px; padding: 0; }
.carta-nombre { font-family: "Sora"; font-weight: 600; font-size: var(--k-contenido); }
.carta-descripcion { font-size: var(--k-secundario); color: var(--k-tenue); }
.carta-version { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
                 border: 1px solid var(--k-borde); border-radius: 6px; padding: 0 var(--k-espacio-xs); }
/* Pendiente agrupada por versión: el encabezado sale una vez y la carta queda en su id. */
.grupo-version { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
                 letter-spacing: 0.06em; }
/* La ficha de una tarea (dialogo_detalle). El nombre manda; la descripción, a medida de
   lectura y un punto más tenue; los datos, en una franja de velo bajo el texto, y las
   acciones, fijas abajo tras la raya callada del board. */
.detalle-columna { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
                   margin-left: var(--k-espacio-sm); }
.detalle-tenue { color: var(--k-tenue); }
/* Señal de vida del agente en la ficha (cotejo-21y2ah): el punto late solo con animaciones. */
.vida-punto { font-size: var(--k-etiqueta); opacity: 0.45; transition: opacity 900ms ease-in-out; }
.vida.activo .vida-punto { color: @success_color; }
.vida.pensando .vida-punto { color: var(--k-tenue); }
.vida.murio .vida-punto { color: var(--k-ambar); }
.vida-ayuda { color: var(--k-tenue); font-family: "IBM Plex Mono"; font-size: var(--k-dato); }
.vida-punto.late { opacity: 1; }
.vida.murio .vida-punto { opacity: 1; }
window.sin-animaciones .vida-punto { transition: none; opacity: 1; }
.detalle-id { font-size: var(--k-dato); }
.detalle-nombre { font-family: "Sora"; font-weight: 600; font-size: var(--k-ventana);
                  line-height: 1.3; }
.detalle-nombre.largo { font-size: var(--k-encabezado); }
.detalle-descripcion { font-size: var(--k-contenido); color: var(--k-texto-chip); line-height: 1.5; }
.detalle-datos { background: var(--k-velo-sutil); border-radius: 10px;
                 padding: var(--k-espacio-md) var(--k-espacio-lg); }
.detalle-clave { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
                 letter-spacing: 0.06em; }
.detalle-valor { font-family: "Inter"; font-weight: 500; font-size: var(--k-contenido); }
.detalle-ruta { font-family: "IBM Plex Mono"; font-size: var(--k-dato); }
/* El modelo es un botón, pero se alinea con los otros dos datos: el relleno que necesita para
   el hover se le devuelve con margen negativo. */
.detalle-agente > button { margin: -4px -8px; padding: 2px 8px; min-height: 0; }
.detalle-agente > button .detalle-valor { font-size: var(--k-contenido); font-weight: 500; }
.detalle-acciones { border-top: 1px solid var(--k-borde-hondo);
                    padding: var(--k-espacio-md) var(--k-espacio-xl); }
.detalle-acciones button { font-family: "Sora"; font-weight: 600; font-size: var(--k-dato);
                           padding: var(--k-espacio-xs) var(--k-espacio-md); }
.carta.arrastrada { opacity: 0.4; border-style: dashed; background: transparent; }
/* La carta de una decisión propuesta (C5, v1.2): mismo ámbar que una entrega devuelta o
   bloqueada, porque le pide lo mismo a quien mira la columna, que se detenga a mirarla. */
.carta-decision { border-color: var(--k-ambar-velo); }
.carta-decision:hover, .carta-decision:focus-visible { border-color: var(--k-ambar); }
.columna-destino { background: var(--k-senal-suave); border-radius: 12px; }

/* La banda de proyectos: una fila de chips centrada; solo se desplaza si no caben. */
.banda-proyectos { background: var(--k-columna); border-top: 1px solid var(--k-borde-hondo);
                   border-bottom: 1px solid var(--k-borde-hondo); padding: var(--k-espacio-sm) 0; }
.banda-chip { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
              border: 1px solid var(--k-borde-chip); border-radius: 999px; background: transparent;
              padding: 0 var(--k-espacio-md); min-height: 36px; min-width: 0;
              transition: background-color var(--k-dur-hover) ease-out; }
.banda-chip:hover { background: var(--k-velo); }
/* El número de tareas va aparte del nombre y más callado: se lee el proyecto primero. */
.banda-cuenta { color: var(--k-tenue); }
.banda-chip.activo .banda-cuenta { color: var(--k-texto-chip); }
.banda-separador { background: var(--k-borde-chip); min-width: 1px; margin: 0 var(--k-espacio-xs); }
.banda-flecha { min-width: 28px; min-height: 28px; padding: 0; border-radius: 999px;
                color: var(--k-tenue); }
.banda-flecha:hover { color: var(--k-texto); background: var(--k-velo); }
.banda-flecha:disabled { opacity: 0.3; }
.banda-fundido { min-width: 40px; }
.banda-fundido.izquierda { background-image: linear-gradient(to right, var(--k-columna), alpha(var(--k-columna), 0)); }
.banda-fundido.derecha { background-image: linear-gradient(to left, var(--k-columna), alpha(var(--k-columna), 0)); }
/* El proyecto abierto se marca con superficie y texto claros, no con verde: el verde de la
   banda es solo el número de lo que espera comprobación, y tiene que leerse también aquí. */
.banda-chip.activo { color: var(--k-texto); background: var(--k-superficie-alta);
                     border-color: var(--k-tenue); }
.grupo-titulo { font-family: "Sora"; font-weight: 600; font-size: var(--k-etiqueta); color: var(--k-tenue);
                letter-spacing: 0.03em; }
/* El vacío: ver vacio(). La pista a 0.75 queda en 5,0:1
   sobre la columna y 5,1:1 sobre la ventana. */
.vacio-icono { color: var(--k-tenue-hondo); }
.vacio-titulo { font-size: var(--k-contenido); color: var(--k-texto); font-weight: 500; }
.vacio-pista { font-size: var(--k-dato); color: var(--k-tenue); line-height: 1.4; }
/* Lo roto no es un vacío cualquiera: ámbar, como la banda de avisos y la anotación detenida,
   sobre el mismo velo que esta. La pista va entera y no a 0.75 porque aquí es la instrucción
   para arreglarlo (7,2:1 sobre el velo; el ámbar, 10,4:1). */
.vacio.roto { background: var(--k-ambar-velo); border-radius: 10px; padding: var(--k-espacio-md); }
.vacio.roto .vacio-icono, .vacio.roto .vacio-titulo { color: var(--k-ambar); }
/* Lo que te espera en ese proyecto: el número en verde y en negrita, sin pastilla. Es el único
   verde de la banda, y se lee igual en el chip abierto que en los demás. */
.aviso-chip { color: var(--k-senal); font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta);
              font-weight: 600; }
/* El pie bajo el tablero: medidor + café a la izquierda, hueco para Maestro al centro,
   botón volver a la derecha. La raya de arriba es la callada del board, no la de la ventana. */
.pie { border-top: 1px solid var(--k-borde-hondo); padding: 0; }
/* Izquierda: medidor + café, sin raya de separación entre ellos en vertical. */
.pie-izquierda { padding: 14px 0 18px 0; }
.ahorro { border: 0; padding: 0; }
.ahorro-cifra { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue); }
/* La invitación al café, sin raya de separación: en plata y sin acento. */
.pie-cafe { font-size: var(--k-dato); color: var(--k-tenue);
            padding: 0; margin: 0; min-height: 0; min-width: 0; background: transparent; border: 0; text-decoration: none; }
.pie-cafe:hover { color: var(--k-texto); background: transparent; }
/* Centro: la barra del Maestro, una pastilla como el buscador. El verde va solo en el ícono y
   en el botón mientras hay algo que mandar; el borde se enciende al escribir. */
.pie-centro { padding: 14px 0 18px 0; }
.maestro-barra { border: 1px solid var(--k-borde); border-radius: 10px; background: var(--k-superficie);
                 padding: 2px 2px 2px var(--k-espacio-md); }
.maestro-barra:focus-within { border-color: var(--k-senal); }
.maestro-barra entry, .maestro-barra entry:focus { background: transparent; outline: none;
                                                    box-shadow: none; min-height: 30px; }
.maestro-chispa { color: var(--k-senal); }
/* Un solo botón, dividido: la parte grande abre el maestro, la flecha elige el cliente.
   Sin texto es un contorno tenue: el verde lleno se reserva para cuando el botón manda algo,
   y así el acento no compite con Para comprobar. Con texto, las dos mitades van rellenas y
   separadas por una raya del color del texto sobre él. */
.maestro-ejecutar > button, .maestro-ejecutar > menubutton > button {
    font-family: "Sora"; font-weight: 600; font-size: var(--k-dato);
    color: var(--k-tenue); background: transparent; border: 1px solid var(--k-borde-chip);
    min-height: 30px; }
.maestro-ejecutar.con-texto > button, .maestro-ejecutar.con-texto > menubutton > button {
    color: var(--k-sobre-senal); background: var(--k-senal); border-color: var(--k-senal); }
.maestro-ejecutar > button { border-radius: 8px 0 0 8px; padding: 0 var(--k-espacio-md); }
.maestro-ejecutar > menubutton > button { border-radius: 0 8px 8px 0; padding: 0 var(--k-espacio-sm);
                                         border-left: none; }
.maestro-ejecutar > button:hover, .maestro-ejecutar > menubutton > button:hover {
    color: var(--k-texto); background: var(--k-velo); }
.maestro-ejecutar.con-texto > button:hover, .maestro-ejecutar.con-texto > menubutton > button:hover {
    filter: brightness(1.1); }
.maestro-ejecutar > separator { background: var(--k-borde-chip); min-width: 1px; }
.maestro-ejecutar.con-texto > separator { background: var(--k-sobre-senal); opacity: 0.25; }
.maestro-ejecutar:disabled > button, .maestro-ejecutar:disabled > menubutton > button {
    color: var(--k-tenue); background: var(--k-velo); border-color: var(--k-borde); }
/* La conversación con el maestro (cotejo-9ybn1a): sube encima del pie. La persona a la
   derecha sobre el velo del acento; el maestro a la izquierda, en superficie; el verde solo
   en el botón que lanza algo (Repartir). */
.maestro-panel { border: 1px solid var(--k-borde); border-radius: 12px; background: var(--k-fondo);
                 padding: var(--k-espacio-md); }
.maestro-burbuja { border-radius: 10px; padding: var(--k-espacio-sm) var(--k-espacio-md); }
.maestro-persona { background: var(--k-senal-suave); }
.maestro-respuesta { background: var(--k-superficie); border: 1px solid var(--k-borde-hondo); }
.maestro-fallo { border-color: var(--k-ambar); }
.maestro-texto { font-size: var(--k-contenido); color: var(--k-texto); }
.maestro-pista, .maestro-vivo { font-size: var(--k-dato); color: var(--k-tenue); }
.maestro-vivo { font-family: "IBM Plex Mono"; }
.maestro-accion { font-size: var(--k-dato); color: var(--k-tenue); }
.maestro-repartir { font-family: "Sora"; font-weight: 600; font-size: var(--k-dato);
                    color: var(--k-sobre-senal); background: var(--k-senal); border-radius: 8px; }
.maestro-repartir:disabled { color: var(--k-tenue); background: var(--k-velo); }
/* Derecha: Deshacer la última tarea finalizada, solo mientras hay algo que deshacer. */
.pie-derecha { padding: 14px 0 18px 0; }
.pie-deshacer { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
                border: 1px solid var(--k-borde-chip); border-radius: 8px;
                padding: var(--k-espacio-sm) var(--k-espacio-md); }
.pie-deshacer:hover { border-color: var(--k-senal); color: var(--k-senal); }
.carta-texto { font-size: var(--k-contenido); }
.chip { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
        background: var(--k-velo); border-radius: 6px; padding: 1px var(--k-espacio-sm); }
.chip image { -gtk-icon-size: 12px; }
/* El tamaño de icono de GTK, el mismo que ya traía: escrito aquí para que `escala` lo agrande
   con el resto en Windows (los botones de la cabecera no pasan por `piezas.icono`). Se hereda:
   ponerlo en la ventana alcanza a todos los que no piden otro. */
window, popover { -gtk-icon-size: 16px; }
/* El agente deja de ir en verde. Tenerlo asignado no es una alerta —casi todas las cartas
   lo llevan—, y mientras fue el color de lo urgente el verde no señalaba nada. Queda en
   contorno plata, que se lee igual de bien y le devuelve el acento a lo que sí espera. */
.chip-agente { color: var(--k-texto-chip); background: transparent;
               border: 1px solid var(--k-borde-chip); }
/* En espera de hueco para su agente (v1.3.0): detenida, así que ámbar. */
.chip-espera { color: var(--k-ambar); background: var(--k-ambar-velo); }
/* Lo que alguien dejó dicho de la tarea: se lee dentro de la carta, sin abrir nada. Va en
   bloque y no colgando de un filete: dentro de una carta que ya tiene borde, un segundo
   borde se pierde, y lo que hay que distinguir es el texto de la tarea del texto sobre la
   tarea. Una superficie lo separa sin añadir otra línea. */
.anotacion { background: var(--k-velo-sutil); border-radius: 7px;
             padding: var(--k-espacio-sm); }
/* Ámbar, como la banda de avisos: el verde es para lo que está en foco, no para lo que se
   frenó. Una devolución y un bloqueo se ven igual porque piden lo mismo: que alguien mire. */
.anotacion.detenida { background: var(--k-ambar-velo); }
.anotacion.detenida .anotacion-titulo { color: var(--k-ambar); }
.anotacion-titulo { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
                    letter-spacing: 0.06em; }
.anotacion-texto { font-family: "IBM Plex Mono"; font-size: var(--k-dato); color: var(--k-tenue);
                   line-height: 1.35; }
/* La vista de revisión (B4). Verde Hecho es lo que pasa —una prueba en verde, una línea que
   se añade—; ámbar, lo que falla o se quita. Son los mismos dos colores de siempre y no unos
   nuevos de semáforo: el verde ya es «lo que espera que lo compruebes», y lo que está en rojo
   es exactamente eso, lo que se frenó. El texto de cada línea va en texto sobre su velo
   (medido en CONTRASTES); solo el signo lleva el color, que en una línea de código se lee mejor. */
.revision-dato { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue); }
.chip.verde { color: var(--k-senal); background: var(--k-senal-suave); }
.chip.rojo, .chip.sin-terminar { color: var(--k-ambar); background: var(--k-ambar-velo); }
.barra-diff { border-radius: 2px; background: var(--k-velo); min-height: 4px; }
.barra-mas { background: var(--k-senal); min-height: 4px; }
.barra-menos { background: var(--k-ambar); min-height: 4px; }
.revision-botones button { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta);
                           padding: 2px var(--k-espacio-sm); min-height: 24px; }
.revision-titulo { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue);
                   letter-spacing: 0.06em; }
.revision-explicacion { font-size: var(--k-encabezado); line-height: 1.4; }
.revision-texto { font-size: var(--k-encabezado); font-weight: 600; }
.diff { font-family: "IBM Plex Mono"; font-size: var(--k-dato); background: var(--k-superficie);
        border: 1px solid var(--k-borde-hondo); border-radius: 7px; padding: var(--k-espacio-xs) 0; }
.diff-linea { padding: 0 var(--k-espacio-sm); color: var(--k-texto); }
.diff-linea.mas { background: var(--k-senal-suave); }
.diff-linea.menos { background: var(--k-ambar-velo); }
.diff-linea.hunk { color: var(--k-tenue); }
.diff-linea.contexto { color: var(--k-tenue); }
.diff-signo { font-family: "IBM Plex Mono"; font-size: var(--k-dato); min-width: 1.2em; }
.diff-linea.mas .diff-signo { color: var(--k-senal); }
.diff-linea.menos .diff-signo { color: var(--k-ambar); }
.salida-prueba { font-family: "IBM Plex Mono"; font-size: var(--k-dato); color: var(--k-tenue); }
.menu-titulo { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue); letter-spacing: 0.06em; }
.menu-item { border-radius: 6px; padding: 3px var(--k-espacio-sm); }
.menu-item image { color: var(--k-tenue); }
/* La opción a la que va la tarea si no dices otra cosa, resaltada: mover una columna a la
   derecha es lo que se hace casi siempre, y así no hay que leer la lista entera. */
.menu-item.sugerida { background: var(--k-velo); }
/* La fila de Tamaño no es un botón: es una fila del menú con tres opciones dentro. */
.menu-tamano { padding: 3px 3px 3px var(--k-espacio-sm); }
.menu-tamano > label { font-weight: bold; }  /* como el texto de los botones de encima */
.menu-tamano .linked { border: 1px solid var(--k-borde); border-radius: 7px; padding: 2px; }
.menu-tamano button.tamano { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); font-weight: 500;
                             min-height: 24px; padding: 0 var(--k-espacio-sm); border-radius: 5px;
                             background: transparent; color: var(--k-tenue); box-shadow: none; }
.menu-tamano button.tamano:hover { color: var(--k-texto); }
.menu-tamano button.tamano:checked { background: var(--k-superficie-alta); color: var(--k-texto); }
.menu-atajo { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue); }
/* Ámbar y no Verde Hecho: el acento es para lo que está en foco, no para lo que está roto. */
banner > revealer > widget { background: var(--k-ambar-fondo); color: var(--k-ambar); }
.aviso-banda label { font-size: var(--k-secundario); }
/* El fondo es del tema y el texto también: Adwaita lo deja blanco, y en el claro no se leía. */
toast { background: var(--k-superficie); color: var(--k-texto); border: 1px solid var(--k-borde); border-radius: 10px; }
toast button.circular { color: var(--k-tenue); }
toast button { color: var(--k-senal); }

/* Las barras de desplazamiento son una pista, no un control que haya que ver todo el rato:
   en reposo, una línea de 3 px casi transparente; al acercar el mouse, lo justo para
   agarrarla. Forzarles un ancho fijo y un gris opaco —como estuvo— anulaba el indicador
   flotante de GTK y dejaba una franja ancha pegada a cada columna. */
scrollbar, scrollbar trough { background: transparent; border: none; box-shadow: none; }
/* El borde transparente con margen negativo es el truco de Adwaita para que una línea de
   3 px se pueda agarrar igual que una barra ancha: se ve fina y se atrapa con holgura.
   Quitarle el borde dejando su margen negativo le daba a GTK un mínimo de -13 px. */
scrollbar slider { background: var(--k-barra); border: 4px solid transparent;
                   background-clip: padding-box; margin: -4px; border-radius: 99px; }
scrollbar.vertical slider { min-width: 3px; min-height: 32px; }
scrollbar.horizontal slider { min-height: 3px; min-width: 32px; }
scrollbar.vertical.hovering slider { min-width: 6px; }
scrollbar.horizontal.hovering slider { min-height: 6px; }
scrollbar.hovering slider, scrollbar slider:hover { background: var(--k-barra-activa); }
scrollbar slider:active { background: var(--k-tenue); }
tooltip { background: var(--k-superficie); border: 1px solid var(--k-borde); border-radius: 8px; }
tooltip label { color: var(--k-texto); font-size: var(--k-dato); }
/* Finalizada siempre plegada: el riel es un botón plano a todo lo alto, con el check y su
   conteo debajo. */
.riel-finalizada { padding: var(--k-espacio-sm) 0; }
.riel-cuenta { font-family: "IBM Plex Mono"; font-size: var(--k-etiqueta); color: var(--k-tenue); }

/* Las pestañas Inicio | Tablero de la cabecera (v1.3.0): la elegida, en superficie alta. */
.pestanas > button.pestana { font-size: var(--k-secundario); min-height: 30px;
                             padding: 0 var(--k-espacio-md); color: var(--k-tenue);
                             background: var(--k-superficie); }
.pestanas > button.pestana:hover { background: var(--k-velo-fuerte); color: var(--k-texto); }
.pestanas > button.pestana:checked { background: var(--k-superficie-alta); color: var(--k-texto);
                                     font-weight: 600; }
/* La pestaña Inicio: saludo en tenue, titular en Sora, tarjetas como las cartas del board.
   El verde sigue siendo solo para lo que espera comprobación (el chip «N por comprobar»). */
.inicio-saludo { color: var(--k-tenue); font-size: var(--k-contenido); }
.inicio-titular { font-family: "Sora"; font-weight: 600; font-size: var(--k-portada); letter-spacing: -0.01em; }
.inicio-tarjeta, .inicio-nuevo { padding: var(--k-espacio-lg); min-height: 112px; }
.inicio-nuevo { border-style: dashed; background: transparent; }
.inicio-nuevo:hover { background: var(--k-velo-sutil); }
.inicio-mas { font-family: "Sora"; font-weight: 600; font-size: var(--k-portada); color: var(--k-tenue); }
.inicio-avance trough { min-height: 4px; border-radius: 4px; background: var(--k-velo-fuerte); }
.inicio-avance progress { min-height: 4px; border-radius: 4px; background: var(--k-tenue); }
/* La entrevista de «Nuevo proyecto» (cotejo-kf94so). */
.entrevista-marco { background: var(--k-columna); border: 1px solid var(--k-borde); border-radius: 8px; }
.entrevista-texto { background: transparent; color: var(--k-texto); font-size: var(--k-contenido); }
/* La pantalla Preparando (cotejo-hiifrz): el verde queda para lo que espera a la persona. */
.preparando-simbolo { font-size: var(--k-contenido); color: var(--k-tenue); }
.preparando-simbolo.paso-en-curso, .paso-en-curso.carta-nombre { color: var(--k-texto); }
.preparando-simbolo.paso-hecho { color: var(--k-texto); }
.preparando-simbolo.paso-fallo, .paso-fallo.carta-nombre, .preparando-error { color: var(--k-ambar); }
.paso-pendiente.carta-nombre { color: var(--k-tenue); }
/* «Revisar el plan» (cotejo-m195bn): las tareas de la persona, «tú», con el contorno del texto. */
.plan-bloque { padding: var(--k-espacio-lg); }
.plan-tarea { padding: var(--k-espacio-xs) 0; border-top: 1px solid var(--k-borde-hondo); }
.chip.chip-tu { color: var(--k-texto); border: 1px solid var(--k-texto); background: transparent; }
.constelacion-caja { background: var(--k-columna); border: 1px solid var(--k-borde); border-radius: 10px; padding: var(--k-espacio-md); }
.constelacion-leyenda { padding-top: var(--k-espacio-sm); border-top: 1px solid var(--k-borde-hondo); }
/* Los nombres de la leyenda son palabras, no datos: en Inter y sin espaciado. */
.constelacion-leyenda .dato { font-family: "Inter"; letter-spacing: 0; }
/* El mapa del proyecto (cotejo-p86sa9): cuatro capas sobre el fondo, piezas como cartas
   pequeñas; la tocada, con el borde del texto (el verde solo en el punto de lo que espera). */
.mapa-capa { background: var(--k-columna); border: 1px solid var(--k-borde); border-radius: 10px;
             padding: var(--k-espacio-md); }
.mapa-pieza { background: var(--k-superficie); border: 1px solid var(--k-borde); border-radius: 8px;
              padding: var(--k-espacio-xs) var(--k-espacio-sm); font-weight: 400; }
.mapa-pieza:hover, .mapa-pieza:checked { border-color: var(--k-texto); background: var(--k-superficie-alta); }
"""
