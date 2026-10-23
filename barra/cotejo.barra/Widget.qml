import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Botón de Cotejo en la barra. Reemplaza al ícono flotante que vivía sobre el escritorio.
// El resumen lo escribe la propia app en ~/.local/state/tareas-obsidian/estado.json cada vez
// que cambia el vault; este widget solo lo vigila, y lo recalcula él mismo (--estado, que no
// carga GTK) por si la app no está corriendo.
//
// A propósito no muestra el total de pendientes: Cotejo existe para enseñar un proyecto a la vez,
// y un 52 permanente en la barra es justo el FOMO que la app evita. El número aparece solo
// cuando algo te espera de verdad: las tareas que un agente dejó "por validar".
BarWidget {
  id: root
  moduleName: "cotejo.barra"

  readonly property string archivo: Quickshell.env("HOME") + "/.local/state/tareas-obsidian/estado.json"
  readonly property string lanzador: Quickshell.env("HOME") + "/.local/bin/tareas-obsidian"
  readonly property int intervaloSeg: setting("intervaloSeg", 300)
  readonly property bool mostrarPendientes: setting("mostrarPendientes", false)
  readonly property color colorAviso: setting("colorAviso", "#16C98D")

  property int pendientes: -1
  property int porValidar: 0
  property int enCurso: 0
  property var proyectos: []
  property int cuantosProyectos: 0
  property string error: ""
  // Notas que Cotejo no pudo leer. Sus tareas no están en el conteo, y eso hay que poder saberlo.
  property var avisos: []
  // Proyectos que el agente prepara en segundo plano (v1.3.0): listos y fallidos avisan aunque
  // la ventana esté cerrada, porque quien los termina de anotar es el proceso de fondo.
  property var preparaciones: []

  function cuantas(estados) {
    var n = 0
    for (var i = 0; i < preparaciones.length; i++)
      if (estados.indexOf(preparaciones[i].estado) >= 0) n++
    return n
  }
  readonly property int listos: cuantas(["listo"])
  readonly property int fallidos: cuantas(["fallo", "colgado"])

  readonly property bool avisa: porValidar > 0 || listos > 0
  readonly property color colorBase: bar ? bar.foreground : Color.foreground
  readonly property color color: (error !== "" || fallidos > 0) ? (bar ? bar.urgent : Color.urgent)
                                              : (avisa ? colorAviso : colorBase)
  readonly property string etiqueta: {
    if (error !== "") return "!"
    if (avisa) return String(porValidar)
    if (mostrarPendientes && pendientes > 0) return String(pendientes)
    return ""
  }

  visible: pendientes >= 0 || error !== ""
  implicitHeight: barSize
  implicitWidth: contenido.implicitWidth + 10

  function plural(n, singular, plural) { return n + " " + (n === 1 ? singular : plural) }

  function leer(texto) {
    try {
      var datos = JSON.parse(String(texto || ""))
      root.pendientes = Number(datos.pendientes || 0)
      root.porValidar = Number(datos.por_validar || 0)
      root.enCurso = Number(datos.en_curso || 0)
      root.cuantosProyectos = Number(datos.proyectos || 0)
      root.proyectos = datos.top || []
      root.error = datos.error ? String(datos.error) : ""
      root.avisos = datos.avisos || []
      root.preparaciones = datos.preparaciones || []
    } catch (e) {
      root.error = "No pude leer el resumen de tareas"
    }
  }

  function textoAyuda() {
    if (error !== "") return "Cotejo: " + error
    var lineas = ["Cotejo"]
    if (pendientes === 0) lineas.push("Todo al día")
    else lineas.push(plural(pendientes, "pendiente", "pendientes") + " en "
                     + plural(cuantosProyectos, "proyecto", "proyectos"))
    if (porValidar > 0) lineas.push(plural(porValidar, "tarea espera", "tareas esperan") + " que la valides")
    if (enCurso > 0) lineas.push(plural(enCurso, "tarea en curso", "tareas en curso"))
    var dice = {"preparando": "preparándose…", "listo": "listo, ábrelo en Cotejo",
                "fallo": "no se pudo preparar, ábrelo en Cotejo",
                "colgado": "parece colgado, ábrelo en Cotejo"}
    for (var k = 0; k < preparaciones.length; k++)
      lineas.push("«" + preparaciones[k].proyecto + "»: " + (dice[preparaciones[k].estado] || preparaciones[k].estado))
    for (var i = 0; i < proyectos.length; i++)
      lineas.push("· " + proyectos[i].nombre + ": " + proyectos[i].pendientes)
    if (avisos.length > 0) {
      lineas.push(plural(avisos.length, "nota que no pude leer", "notas que no pude leer")
                  + ": sus tareas no están en la cuenta")
      for (var j = 0; j < avisos.length; j++)
        lineas.push("· " + avisos[j].nota + ": " + avisos[j].motivo)
    }
    lineas.push("Clic: abrir o cerrar · Clic central: actualizar")
    return lineas.join("\n")
  }

  function actualizar() {
    if (!recolector.running) recolector.running = true
  }

  FileView {
    id: datos
    path: root.archivo
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.leer(text())
  }

  // Red de seguridad: si la app no está viva, nadie reescribe el archivo.
  Process {
    id: recolector
    command: [root.lanzador, "--estado"]
    onExited: datos.reload()
  }

  Timer {
    interval: root.intervaloSeg * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.actualizar()
  }

  Row {
    id: contenido
    anchors.centerIn: parent
    spacing: 4

    // El símbolo de Cotejo, no un glifo de Nerd Font: con nf-fa-tasks el botón era el de
    // cualquier lista de tareas. Se tiñe como los íconos simbólicos de la bandeja de Omarchy
    // (MultiEffect sobre la imagen oculta), así hereda el color de la barra, el verde del aviso
    // y el rojo del error igual que lo heredaba el glifo; y ocupa el mismo lienzo que el resto
    // de íconos (Style.bar.iconCanvas). A 14 px su alto pintado queda igual que el del volumen o
    // la batería; a 12, como los de la bandeja, el trazo se deshacía en la pantalla de escala 1.
    Item {
      id: glifo
      anchors.verticalCenter: parent.verticalCenter
      width: Style.bar.iconCanvas
      height: Style.bar.iconCanvas

      Image {
        id: simbolo
        anchors.centerIn: parent
        width: Style.space(14)
        height: Style.space(14)
        fillMode: Image.PreserveAspectFit
        // A píxeles físicos: con el tamaño lógico sale borroso en la pantalla con escala 2.
        sourceSize.width: Math.round(width * Screen.devicePixelRatio)
        sourceSize.height: Math.round(height * Screen.devicePixelRatio)
        source: Qt.resolvedUrl("cotejo-simbolo.svg")
        smooth: true
        // Oculta: solo es la textura que tiñe el efecto.
        visible: false
        layer.enabled: true
      }

      MultiEffect {
        anchors.fill: simbolo
        source: simbolo
        colorization: 1.0
        colorizationColor: root.color
      }
    }

    Text {
      visible: root.etiqueta !== ""
      anchors.verticalCenter: parent.verticalCenter
      text: root.etiqueta
      color: root.color
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Style.font.caption + 1
    }
  }

  MouseArea {
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton | Qt.MiddleButton
    onEntered: if (root.bar) root.bar.showTooltip(root, root.textoAyuda())
    onExited: if (root.bar) root.bar.hideTooltip(root)
    onClicked: function (evento) {
      if (evento.button === Qt.MiddleButton) {
        root.actualizar()
        if (root.bar) root.bar.showTooltip(root, root.textoAyuda())
        return
      }
      Quickshell.execDetached([root.lanzador])
    }
  }
}
