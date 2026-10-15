"""El contrato con el agente: qué devuelve la CLI, qué se niega a hacer y qué deja anotado.

Lo que se prueba aquí no es solo que funcione, es que siga significando lo mismo. Si mañana
aparece un verbo para finalizar tareas o para aceptar una decisión, una de estas pruebas tiene
que ponerse roja.
"""

import argparse

from apoyo import PruebaDeCLI, proyecto

from tareas import cli

# Las raíces de lo que el agente no puede hacer, en sus sinónimos: dar una tarea por hecha y
# aceptar (firmar) una decisión. Se buscan como trozo de cualquier nombre —verbo, acción, tool,
# bandera o argumento—, así que `aceptar_decision`, `--aprobada` o `marcar_hecha` también caen.
PROHIBIDAS = ("finaliz", "complet", "termin", "marcar", "hecha", "cerrar", "cierr",
              "acept", "aprob", "aprueb", "firm", "ratific", "confirm", "valida")
# Los nombres que contienen una raíz y están bien a propósito: `config validar` comprueba la
# config, no una entrega. (`resolver` no está en PROHIBIDAS: cierra un problema con su solución,
# que no es aceptar nada.) `--completo` es la bandera de `protocolo` que imprime también las
# referencias de la skill: «completo» habla del texto, no de dar nada por hecho.
PERMITIDAS = {"validar", "completo"}


def _prohibida(nombre):
    nombre = nombre.lower().lstrip("-")
    return nombre not in PERMITIDAS and any(r in nombre for r in PROHIBIDAS)


def _nombres_de_la_cli(analizador, ruta=()):
    """(ruta, nombre) de cada verbo, acción, bandera y argumento del analizador, recursivo."""
    for accion in analizador._actions:
        if isinstance(accion, argparse._SubParsersAction):
            for nombre, sub in accion.choices.items():
                yield ruta, nombre
                yield from _nombres_de_la_cli(sub, (*ruta, nombre))
        elif not isinstance(accion, argparse._HelpAction):
            for nombre in (*accion.option_strings, accion.dest):
                yield ruta, nombre


class Listar(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Pendiente pelada",
            "- [ ] Haciéndola #en-curso #agente/opus",
            "- [ ] Esperando #por-validar #agente/sonnet #dificil",
            "- [x] Finalizada",
        ))
        self.escribir_nota("Dos.md", proyecto("- [ ] De otro proyecto"))

    def test_devuelve_todas_con_su_esquema(self):
        codigo, datos = self.correr("tareas", "--todas")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["esquema"], cli.ESQUEMA)
        self.assertEqual(datos["total"], 5)

    def test_cada_tarea_trae_lo_que_el_agente_necesita(self):
        _, datos = self.correr("tareas", "--proyecto", "Uno", "--estado", "por-validar")
        tarea, = datos["tareas"]
        self.assertEqual(tarea["texto"], "Esperando")
        self.assertEqual(tarea["proyecto"], "Uno")
        self.assertEqual(tarea["estado"], "por-validar")
        self.assertEqual(tarea["agente"], "sonnet")
        self.assertEqual(tarea["dificultad"], "dificil")
        self.assertEqual(tarea["nota"], "01-Proyectos/Uno.md")
        self.assertTrue(tarea["id"])

    def test_filtra_por_proyecto_con_parte_del_nombre(self):
        _, datos = self.correr("tareas", "--proyecto", "un")
        self.assertEqual({t["proyecto"] for t in datos["tareas"]}, {"Uno"})

    def test_filtra_por_estado(self):
        _, datos = self.correr("tareas", "--estado", "pendiente")
        self.assertEqual({t["estado"] for t in datos["tareas"]}, {"pendiente"})

    def test_filtra_por_agente(self):
        _, datos = self.correr("tareas", "--agente", "opus")
        self.assertEqual([t["texto"] for t in datos["tareas"]], ["Haciéndola"])

    def test_filtra_las_que_no_tienen_dueno(self):
        _, datos = self.correr("tareas", "--agente", "")
        self.assertEqual({t["agente"] for t in datos["tareas"]}, {""})

    def test_el_limite_recorta_pero_el_total_sigue_diciendo_cuantas_hay(self):
        _, datos = self.correr("tareas", "--todas", "--limite", "2")
        self.assertEqual(len(datos["tareas"]), 2)
        self.assertEqual(datos["total"], 5)

    def test_listar_no_escribe_en_las_notas(self):
        antes = self.leer_nota("Uno.md")
        self.correr("tareas")
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.operaciones(), [])

    def test_un_estado_que_no_existe_lo_rechaza_argparse(self):
        with self.assertRaises(SystemExit):
            self.correr("tareas", "--estado", "inventado")


class Tomar(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Libre",
            "- [ ] Ocupada #en-curso #agente/sonnet",
            "- [x] Terminada",
        ))

    def id_de(self, texto):
        _, datos = self.correr("tareas", "--todas")
        return next(t["id"] for t in datos["tareas"] if t["texto"] == texto)

    def test_mueve_a_haciendola_y_la_asigna(self):
        codigo, datos = self.correr("tomar", self.id_de("Libre"), "--agente", "opus")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["cambio"])
        self.assertEqual(datos["tarea"]["estado"], "en-curso")
        self.assertEqual(datos["tarea"]["agente"], "opus")
        self.assertIn("#en-curso", self.leer_nota("Uno.md"))

    def test_devuelve_el_id_nuevo_porque_la_tarea_gana_su_marca_al_escribir(self):
        viejo = self.id_de("Libre")
        _, datos = self.correr("tomar", viejo, "--agente", "opus")
        self.assertNotEqual(datos["tarea"]["id"], viejo)
        self.assertTrue(datos["tarea"]["id"].startswith("cotejo-"))

    def test_tomarla_dos_veces_el_mismo_agente_no_cambia_nada(self):
        _, primera = self.correr("tomar", self.id_de("Libre"), "--agente", "opus")
        antes = self.leer_nota("Uno.md")
        codigo, segunda = self.correr("tomar", primera["tarea"]["id"], "--agente", "opus")
        self.assertEqual(codigo, 0)
        self.assertFalse(segunda["cambio"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_no_se_puede_tomar_la_que_ya_tiene_otro(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("tomar", self.id_de("Ocupada"), "--agente", "opus")
        self.assertNotEqual(codigo, 0)
        self.assertIn("sonnet", datos["error"])
        self.assertFalse(datos["reintentable"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_no_se_puede_tomar_una_finalizada(self):
        codigo, datos = self.correr("tomar", self.id_de("Terminada"), "--agente", "opus")
        self.assertNotEqual(codigo, 0)
        self.assertIn("hecha", datos["error"])

    def test_un_nombre_de_agente_absurdo_lo_rechaza_argparse(self):
        with self.assertRaises(SystemExit):
            self.correr("tomar", self.id_de("Libre"), "--agente", "opus y sonnet")


class Entregar(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Pendiente",
            "- [ ] Haciéndola #en-curso #agente/opus",
            "- [x] Terminada",
        ))

    def id_de(self, texto):
        _, datos = self.correr("tareas", "--todas")
        return next(t["id"] for t in datos["tareas"] if t["texto"] == texto)

    def test_mueve_a_en_espera_de_comprobacion(self):
        codigo, datos = self.correr("entregar", self.id_de("Haciéndola"),
                                    "--evidencia", "corrí las pruebas")
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["tarea"]["estado"], "por-validar")
        self.assertEqual(datos["evidencia"], "corrí las pruebas")

    def test_la_evidencia_es_obligatoria(self):
        with self.assertRaises(SystemExit):
            self.correr("entregar", self.id_de("Haciéndola"))

    def test_no_se_entrega_lo_que_no_se_ha_tomado(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("entregar", self.id_de("Pendiente"), "--evidencia", "x")
        self.assertNotEqual(codigo, 0)
        self.assertIn("Tómala primero", datos["salida"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_no_se_entrega_una_finalizada(self):
        codigo, datos = self.correr("entregar", self.id_de("Terminada"), "--evidencia", "x")
        self.assertNotEqual(codigo, 0)
        self.assertIn("finalizada", datos["salida"])

    def test_entregarla_dos_veces_no_cambia_nada(self):
        _, primera = self.correr("entregar", self.id_de("Haciéndola"), "--evidencia", "x")
        antes = self.leer_nota("Uno.md")
        codigo, segunda = self.correr("entregar", primera["tarea"]["id"], "--evidencia", "y")
        self.assertEqual(codigo, 0)
        self.assertFalse(segunda["cambio"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_le_recuerda_al_agente_que_finalizar_no_es_suyo(self):
        _, datos = self.correr("entregar", self.id_de("Haciéndola"), "--evidencia", "x")
        self.assertIn("persona", datos["nota_para_el_agente"])


class Bloquear(PruebaDeCLI):
    """La salida honesta del agente: no pude, y esto es lo que me lo impide."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto(
            "- [ ] Pendiente",
            "- [ ] Haciéndola #en-curso #agente/opus",
            "- [ ] Entregada #por-validar #agente/opus",
            "- [x] Terminada",
        ))

    def id_de(self, texto):
        _, datos = self.correr("tareas", "--todas")
        return next(t["id"] for t in datos["tareas"] if t["texto"] == texto)

    def test_vuelve_a_pendiente_y_sin_dueno(self):
        codigo, datos = self.correr("bloquear", self.id_de("Haciéndola"),
                                    "--motivo", "Falta la clave de la API de pagos")
        self.assertEqual(codigo, 0)
        self.assertTrue(datos["cambio"])
        self.assertEqual(datos["tarea"]["estado"], "pendiente")
        self.assertEqual(datos["tarea"]["agente"], "")
        self.assertEqual(datos["motivo"], "Falta la clave de la API de pagos")
        linea = next(l for l in self.leer_nota("Uno.md").splitlines() if "Haciéndola" in l)
        self.assertNotIn("#en-curso", linea)
        self.assertNotIn("#agente/", linea)

    def test_el_motivo_es_obligatorio(self):
        """Una tarea que vuelve a Pendiente sin explicación la toma el siguiente agente para
        estrellarse contra lo mismo. Es la misma regla que la evidencia al entregar."""
        with self.assertRaises(SystemExit):
            self.correr("bloquear", self.id_de("Haciéndola"))

    def test_el_motivo_queda_en_la_bitacora_con_quien_se_atasco(self):
        self.correr("bloquear", self.id_de("Haciéndola"), "--motivo", "Falta una decisión tuya")
        anotacion = self.operaciones()[-1]
        self.assertEqual(anotacion["operacion"], "bloquear")
        self.assertEqual(anotacion["motivo"], "Falta una decisión tuya")
        self.assertEqual(anotacion["agente"], "opus")  # quién la tenía, aunque ya la soltó

    def test_el_motivo_le_llega_al_siguiente_que_la_liste(self):
        self.correr("bloquear", self.id_de("Haciéndola"), "--motivo", "El repo no tiene remoto")
        _, datos = self.correr("tareas", "--estado", "pendiente")
        bloqueada = next(t for t in datos["tareas"] if t["texto"] == "Haciéndola")
        self.assertEqual(bloqueada["motivo"], "El repo no tiene remoto")

    def test_no_se_bloquea_lo_que_no_se_ha_tomado(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("bloquear", self.id_de("Pendiente"), "--motivo", "x")
        self.assertEqual(codigo, 0)
        self.assertFalse(datos["cambio"])  # ya estaba libre: reintentar es seguro
        self.assertEqual(self.leer_nota("Uno.md"), antes)
        self.assertEqual(self.operaciones(), [])

    def test_no_se_bloquea_lo_ya_entregado(self):
        antes = self.leer_nota("Uno.md")
        codigo, datos = self.correr("bloquear", self.id_de("Entregada"), "--motivo", "x")
        self.assertNotEqual(codigo, 0)
        self.assertIn("CotejoBoard", datos["salida"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)

    def test_no_se_bloquea_una_finalizada(self):
        codigo, datos = self.correr("bloquear", self.id_de("Terminada"), "--motivo", "x")
        self.assertNotEqual(codigo, 0)
        self.assertEqual(self.operaciones(), [])

    def test_bloquear_no_marca_nada_como_hecho(self):
        self.correr("bloquear", self.id_de("Haciéndola"), "--motivo", "x")
        self.assertEqual(self.leer_nota("Uno.md").count("- [x]"), 1)  # la que ya venía marcada


class Asignar(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] La tarea #agente/opus"))

    def id_de(self):
        _, datos = self.correr("tareas")
        return datos["tareas"][0]["id"]

    def test_cambia_el_dueno(self):
        _, datos = self.correr("asignar", self.id_de(), "sonnet")
        self.assertEqual(datos["tarea"]["agente"], "sonnet")
        self.assertIn("#agente/sonnet", self.leer_nota("Uno.md"))

    def test_sin_nombre_la_deja_sin_dueno(self):
        _, datos = self.correr("asignar", self.id_de())
        self.assertEqual(datos["tarea"]["agente"], "")
        self.assertNotIn("#agente", self.leer_nota("Uno.md"))

    def test_asignar_al_mismo_no_cambia_nada(self):
        antes = self.leer_nota("Uno.md")
        _, datos = self.correr("asignar", self.id_de(), "opus")
        self.assertFalse(datos["cambio"])
        self.assertEqual(self.leer_nota("Uno.md"), antes)


class Errores(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] La tarea ^cotejo-repe01"))

    def test_un_id_que_no_existe_es_reintentable_y_dice_que_hacer(self):
        codigo, datos = self.correr("tomar", "cotejo-nohay", "--agente", "opus")
        self.assertNotEqual(codigo, 0)
        self.assertTrue(datos["reintentable"])
        self.assertIn("tareas", datos["salida"])

    def test_un_id_ambiguo_se_niega_y_nombra_las_notas(self):
        self.escribir_nota("Dos.md", proyecto("- [ ] La otra ^cotejo-repe01"))
        antes = self.leer_nota("Uno.md"), self.leer_nota("Dos.md")
        codigo, datos = self.correr("tomar", "cotejo-repe01", "--agente", "opus")
        self.assertNotEqual(codigo, 0)
        self.assertIn("Uno.md", datos["error"])
        self.assertIn("Dos.md", datos["error"])
        self.assertEqual((self.leer_nota("Uno.md"), self.leer_nota("Dos.md")), antes)

    def test_todo_error_trae_salida_y_reintentable(self):
        for argumentos in (("tomar", "cotejo-nohay", "--agente", "opus"),
                           ("entregar", "cotejo-nohay", "--evidencia", "x"),
                           ("asignar", "cotejo-nohay", "opus")):
            with self.subTest(argumentos[0]):
                _, datos = self.correr(*argumentos)
                self.assertIn("error", datos)
                self.assertTrue(datos["salida"])
                self.assertIn("reintentable", datos)


class Bitacora(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] La tarea"))

    def test_anota_cada_operacion_con_su_evidencia(self):
        _, datos = self.correr("tareas")
        identificador = datos["tareas"][0]["id"]
        _, tomada = self.correr("tomar", identificador, "--agente", "opus")
        self.correr("entregar", tomada["tarea"]["id"], "--evidencia", "la prueba que lo demuestra")

        operaciones = self.operaciones()
        self.assertEqual([o["operacion"] for o in operaciones], ["tomar", "entregar"])
        self.assertEqual(operaciones[0]["de"], "pendiente")
        self.assertEqual(operaciones[0]["a"], "en-curso")
        self.assertEqual(operaciones[1]["evidencia"], "la prueba que lo demuestra")
        self.assertTrue(all(o["agente"] == "opus" for o in operaciones))
        self.assertTrue(all(o["texto"] == "La tarea" for o in operaciones))

    def test_una_operacion_que_falla_no_se_anota(self):
        self.correr("tomar", "cotejo-nohay", "--agente", "opus")
        self.assertEqual(self.operaciones(), [])

    def test_que_la_bitacora_no_se_pueda_escribir_no_tumba_la_operacion(self):
        self.bitacora.parent.chmod(0o500)
        self.addCleanup(self.bitacora.parent.chmod, 0o700)
        _, datos = self.correr("tareas")
        codigo, resultado = self.correr("tomar", datos["tareas"][0]["id"], "--agente", "opus")
        self.assertEqual(codigo, 0)
        self.assertEqual(resultado["tarea"]["estado"], "en-curso")


class Contrato(PruebaDeCLI):
    """Lo que la CLI promete que seguirá siendo verdad."""

    def setUp(self):
        super().setUp()
        self.escribir_nota("Uno.md", proyecto("- [ ] La tarea #en-curso #agente/opus"))

    def test_no_hay_ningun_verbo_para_finalizar_una_tarea(self):
        # Si el agente puede marcar hecha la suya, «hecha» deja de significar que alguien la
        # revisó. Esta prueba existe para que añadirlo tenga que ser una decisión consciente.
        verbos = set(cli.analizador()._subparsers._group_actions[0].choices)
        # `ahorro` solo lee: cuánto costó enterarse por aquí. `crear` está y `finalizar` no, y
        # la diferencia no es un descuido: apuntar trabajo no afirma que esté hecho, así que
        # no erosiona lo que significa «hecha».
        self.assertEqual(verbos, {"estado", "tareas", "ahorro", "crear", "tomar", "entregar", "bloquear", "asignar",
                                  # Vuelve a correr las pruebas de la entrega y dice si
                                  # siguen igual; lee, no escribe estado ni bitácora.
                                  "comprobar",
                                  # Lista los worktrees de despacho y retira los que sobran;
                                  # no mueve ninguna tarea ni borra ramas.
                                  "worktrees",
                                  # Borra de la nota las que una persona ya finalizó hace
                                  # más de una semana, dejando su rastro en la bitácora; no
                                  # mueve ninguna de columna (v1.2.2, cotejo-r3cs5t).
                                  "limpiar",
                                  # Los del enrutador, que reparte trabajo y tampoco finaliza.
                                  "modelos", "decidir", "plan", "despachar", "evaluar",
                                  "revisar", "despachos", "config", "protocolo",
                                  # Abre un agente que reparte; ni él ni el verbo finalizan.
                                  "maestro",
                                  # Mide la máquina antes de repartir; no toca tareas.
                                  "capacidad",
                                  # Convierte un plan.md en tareas con `crear`; no finaliza
                                  # ninguna, solo las anota.
                                  "importar",
                                  # Los de la instalación: de qué fuente se lee y si
                                  # funciona, y preparar un repo para la fuente «repo».
                                  # Tocan la config, nunca una tarea.
                                  "init", "doctor", "fuentes",
                                  # Los colores del board: tocan la config y los archivos
                                  # de tema, nunca una tarea.
                                  "temas",
                                  # El almacén `.cotejo/` (v1.2): leen entradas, no tareas, y
                                  # no cambian su estado.
                                  "buscar", "leer",
                                  # El resumen barato del repo para enterarse sin leer sus
                                  # notas (B1): lee tareas y entradas, no cambia nada.
                                  "contexto",
                                  # Crea una decisión en propuesta (o la que la reemplaza);
                                  # no existe ni existirá una acción para aceptarla.
                                  "proponer",
                                  # Deja constancia —problema, aprendizaje, referencia o
                                  # arquitectura— y añade a la bitácora del día; ninguno
                                  # de los dos cierra ni acepta nada.
                                  "anotar", "bitacora",
                                  # Cambia el texto de una entrada editable, verificado por
                                  # version (nunca una decisión, que se reemplaza), y cierra
                                  # un problema con su solución; ninguno de los dos acepta.
                                  "editar", "resolver",
                                  # La puerta MCP: sirve estos mismos verbos como tools.
                                  # Y la versión del proyecto (v1.2.4): lee tags y tareas; con --siguiente planea, no aprueba.
                                  "version",
                                  # Las notas de una versión (v1.2.4): ensayo, o con --aplicar
                                  # las escribe; nunca etiqueta, solo devuelve el `git tag`.
                                  "release", "mcp"})
        # Ni con otro nombre: ningún verbo, acción, bandera ni argumento suena a finalizar ni a
        # aceptar. Una `--aceptada` en `proponer` sería el mismo agujero que un verbo `aceptar`.
        for ruta, nombre in _nombres_de_la_cli(cli.analizador()):
            self.assertFalse(_prohibida(nombre), f"`cotejo {' '.join(ruta)}` tiene «{nombre}»")
        # Y por MCP lo mismo: cada tool es un verbo de aquí (o `verbo_accion`), ninguna más, y
        # ninguna con nombre de finalizar. Una tool escrita a mano fuera del analizador también
        # la pondría roja, que es lo que mantiene a MCP como otra puerta y no otro contrato.
        from tareas import mcp
        permitidas = set(verbos)
        for verbo, sub in cli.analizador()._subparsers._group_actions[0].choices.items():
            if sub._subparsers is not None:
                permitidas |= {f"{verbo}_{a}" for a in sub._subparsers._group_actions[0].choices}
        nombres = {t["name"] for t in mcp.tools()}
        self.assertLessEqual(nombres, permitidas - {"mcp"})
        self.assertEqual({n.split("_")[0] for n in nombres}, verbos - {"mcp"})
        for tool in mcp.tools():
            self.assertFalse(_prohibida(tool["name"]), tool["name"])
            for argumento in tool["inputSchema"]["properties"]:
                self.assertFalse(_prohibida(argumento), f"{tool['name']}.{argumento}")
        # Ninguna tool que escribe en el almacén deja elegir el estado en que nace la entrada:
        # una decisión sale `propuesta` y solo la persona la pasa a `aceptada`.
        for tool in mcp.tools():
            if tool["name"].split("_")[0] in ("proponer", "anotar", "bitacora", "editar",
                                              "resolver"):
                self.assertNotIn("estado", tool["inputSchema"]["properties"], tool["name"])
                self.assertNotIn("aceptada", str(tool["inputSchema"]), tool["name"])
        # Un adaptador externo sí sabe `marcar` —el board lo necesita—, pero eso es el contrato
        # con la fuente, no un verbo: no puede asomar como subacción de nada.
        fuentes = cli.analizador()._subparsers._group_actions[0].choices["fuentes"]
        acciones = set(fuentes._subparsers._group_actions[0].choices)
        self.assertEqual(acciones, {"info", "probar", "usar", "agregar", "quitar"})

    def test_pedir_aceptar_o_finalizar_dice_que_es_de_la_persona(self):
        for verbo in ("aceptar", "aprobar", "firmar", "Aceptar"):
            codigo, datos = self.correr(verbo, "dec-aaaa")
            self.assertEqual(codigo, 3)
            self.assertEqual(datos["error"], "Aceptar es de la persona: se hace desde el board")
            self.assertFalse(datos["reintentable"])
        for verbo in ("finalizar", "completar", "marcar"):
            codigo, datos = self.correr(verbo, "cotejo-aaaa")
            self.assertEqual(codigo, 3)
            self.assertIn("es de la persona", datos["error"])
            self.assertIn("cotejo entregar", datos["salida"])
        self.assertEqual(self.operaciones(), [])

    def test_ningun_verbo_escribe_una_equis_en_el_markdown(self):
        _, datos = self.correr("tareas")
        identificador = datos["tareas"][0]["id"]
        self.correr("entregar", identificador, "--evidencia", "x")
        self.correr("asignar", identificador, "sonnet")
        self.correr("bloquear", identificador, "--motivo", "x")
        self.assertNotIn("- [x]", self.leer_nota("Uno.md"))

    def test_estado_sigue_dando_el_resumen_que_lee_el_widget(self):
        codigo, datos = self.correr("estado")
        self.assertEqual(codigo, 0)
        for clave in ("pendientes", "en_curso", "por_validar", "hechas", "proyectos", "top"):
            self.assertIn(clave, datos)

    def test_el_estado_viejo_con_dos_guiones_tambien_vale(self):
        # Es lo que llama el widget de la barra desde antes de que existieran los verbos.
        codigo, datos = self.correr("--estado")
        self.assertEqual(codigo, 0)
        self.assertIn("pendientes", datos)

    def test_estado_escribe_el_archivo_que_vigila_la_barra(self):
        self.correr("estado")
        self.assertTrue(self.archivo_estado.exists())


class ExcluirHechasPorDefecto(PruebaDeCLI):
    def setUp(self):
        super().setUp()
        self.escribir_nota("Proyecto.md", proyecto(
            "- [ ] Pendiente",
            "- [x] Hecha",
        ))

    def test_tareas_sin_parametros_excluye_las_hechas(self):
        codigo, datos = self.correr("tareas")
        self.assertEqual(codigo, 0)
        textos = {t["texto"] for t in datos["tareas"]}
        self.assertIn("Pendiente", textos)
        self.assertNotIn("Hecha", textos)
        self.assertEqual(datos["total"], 1)

    def test_tareas_con_todas_incluye_las_hechas(self):
        codigo, datos = self.correr("tareas", "--todas")
        self.assertEqual(codigo, 0)
        textos = {t["texto"] for t in datos["tareas"]}
        self.assertIn("Pendiente", textos)
        self.assertIn("Hecha", textos)
        self.assertEqual(datos["total"], 2)

    def test_tareas_con_estado_hecha_devuelve_solo_las_hechas(self):
        codigo, datos = self.correr("tareas", "--estado", "hecha")
        self.assertEqual(codigo, 0)
        textos = {t["texto"] for t in datos["tareas"]}
        self.assertNotIn("Pendiente", textos)
        self.assertIn("Hecha", textos)
        self.assertEqual(datos["total"], 1)
        for tarea in datos["tareas"]:
            self.assertEqual(tarea["estado"], "hecha")
