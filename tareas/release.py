"""El verbo `cotejo release [--version X.Y.Z] [--aplicar]` (v1.2.4): las notas de una versión.

Es un ensayo por defecto: dice qué notas saldrían y no escribe nada. Con `--aplicar` las
escribe en `.cotejo/releases/vX.Y.Z.md` (por el almacén) y devuelve en `salida` el comando
`git tag` para la persona. **Nunca etiqueta ni publica**, y no toca `version:` de
`proyecto.md`: todavía no existe el tag, y después del tag la en curso se calcula sola
(`tareas/version.py`). Etiquetar y publicar son de una persona, como finalizar.

Qué entra en las notas, desde la fecha del commit del último tag (las de ese mismo día se dan
por incluidas en él, igual que en `cotejo version`):

- las tareas aprobadas de esa versión: el mismo cálculo que `cotejo version`
  (`version_verbo.contar`);
- las decisiones aceptadas (por `aceptada_el`, o su `fecha` si es de antes de que se anotara),
  sin las importadas (`autor: importado`), que son historia y no de esta versión;
- los problemas resueltos (por `resuelto_el`, o su `fecha`).

Sin tag, todo lo de arriba sin límite de fecha. Se niega, nombrando las tareas, si queda alguna
de esa versión sin aprobar; y también si la versión ya está etiquetada o no sube la publicada.
Sin proyecto conocido (un repo que ninguna fuente nombra) el ensayo sale sin tareas y con un
aviso, y `--aplicar` se niega: no se puede comprobar que no quede nada abierto.

El archivo: repetir `--aplicar` con lo mismo no cambia nada (`hecho: ya-estaba`). Si ya existe
con otro contenido (se aprobó algo después, o alguien lo retocó a mano), se niega y da su hash;
`--reemplazar <hash>` lo reescribe, verificado como cualquier entrada del almacén, para no pisar
en silencio lo que otro escribió.
"""

import re

from . import almacen, version as versiones
from .cli import ESQUEMA, ErrorCLI, imprimir
from .modelo import HECHA
from .version_verbo import _fecha_del_tag, _git, _resolver, contar

# El «— AAAA-MM-DD» de cierre sigue en el texto de la tarea (la fuente no lo quita): en las
# notas sobra, porque todo lo de ahí está cerrado.
CIERRE_RE = re.compile(r"\s+—\s+\d{4}-\d{2}-\d{2}\s*$")


def _version_pedida(texto, estado):
    """La `Semver` que se va a sacar: `--version` o la en curso. ErrorCLI si no vale."""
    if texto:
        pedida = versiones.parsear(texto)
        if pedida is None:
            raise ErrorCLI(f"«{texto}» no es una versión", "Usa X.Y.Z, por ejemplo 1.2.4.")
    else:
        pedida = versiones.parsear(estado["en_curso"])
        if pedida is None:
            raise ErrorCLI("El proyecto no tiene versión en curso",
                           "`cotejo init` le pone `version:` en proyecto.md, o pasa --version.")
    publicada = versiones.parsear(estado["publicada"])
    if publicada and pedida <= publicada:
        raise ErrorCLI(f"{pedida} no sube la publicada ({publicada})",
                       "`cotejo version` dice cuál está en curso.")
    return pedida


def sin_aprobar(proyecto, pedida):
    """Las tareas de `pedida` que aún no están hechas, como `{id, tarea, estado}`."""
    return [{"id": t.id, "tarea": t.nombre_corto, "estado": t.columna}
            for t in proyecto.tareas
            if t.columna != HECHA and versiones.pertenece(t.version_del_texto, str(pedida))]


def _desde(entrada, clave, fecha_tag):
    """Si `entrada` cuenta para esta versión: su fecha (`clave` o `fecha`) es posterior al tag."""
    fecha = str(entrada.datos.get(clave) or entrada.datos.get("fecha") or "")
    return not fecha_tag or fecha > fecha_tag


def conocimiento(raiz, fecha_tag, avisos):
    """`(decisiones, problemas)` que entran en las notas, leídos por el almacén."""
    alm = almacen.Almacen(raiz)
    leidos = []
    decisiones = [{"id": e.id, "titulo": e.titulo}
                  for e in alm.entradas("decision", leidos)
                  if e.estado == "aceptada" and e.datos.get("autor") != "importado"
                  and _desde(e, "aceptada_el", fecha_tag)]
    problemas = [{"id": e.id, "titulo": e.titulo,
                  "solucion": " ".join(str(e.datos.get("solucion") or "").split())}
                 for e in alm.entradas("problema", leidos)
                 if e.estado == "resuelto" and _desde(e, "resuelto_el", fecha_tag)]
    avisos.extend(leidos)
    return decisiones, problemas


def componer(nombre, pedida, tag, fecha_tag, tareas, decisiones, problemas):
    """El Markdown de las notas. Sin la fecha de hoy: lo mismo da siempre el mismo archivo."""
    datos = {"version": str(pedida), "tag": pedida.etiqueta}
    if tag:
        datos.update({"desde": tag, "desde_fecha": fecha_tag})
    partes = [f"# {nombre} {pedida}\n"]
    for titulo, filas in (
            ("Tareas", [f"- {CIERRE_RE.sub('', t['tarea'])} (`{t['id']}`)" for t in tareas]),
            ("Decisiones", [f"- {d['titulo']} (`{d['id']}`)" for d in decisiones]),
            ("Problemas resueltos", [f"- {p['titulo']} (`{p['id']}`)"
                                     + (f": {p['solucion']}" if p["solucion"] else "")
                                     for p in problemas])):
        if filas:
            partes.append(f"\n## {titulo}\n\n" + "\n".join(filas) + "\n")
    return almacen.componer(datos, "".join(partes))


def comando_tag(raiz, nombre, pedida):
    """El `git tag` que corre la persona. Solo se devuelve: ningún verbo lo ejecuta."""
    return f'git -C "{raiz}" tag -a {pedida.etiqueta} -m "{nombre} {pedida}"'


def cmd_release(args):
    raiz, proyecto, _, avisos = _resolver(args)
    avisos = list(avisos)
    if proyecto is None:
        if args.aplicar:
            raise ErrorCLI("No se encontró el proyecto de este repo",
                           "Pasa --proyecto: sin sus tareas no se puede comprobar que estén "
                           "todas aprobadas, y sin eso no se escriben notas.")
        avisos.append("No se encontró el proyecto de este repo: el ensayo va sin tareas y "
                      "--aplicar se negará. Pasa --proyecto.")
    estado = versiones.estado(raiz)
    pedida = _version_pedida(args.version, estado)
    if _git(raiz, "tag", "--list", pedida.etiqueta):
        raise ErrorCLI(f"{pedida.etiqueta} ya está etiquetada",
                       "Las notas se arman antes del tag; `cotejo version` dice la en curso.")
    abiertas = sin_aprobar(proyecto, pedida) if proyecto else []
    if abiertas:
        nombres = "; ".join(f"{t['id']} ({t['tarea']}, {t['estado']})" for t in abiertas)
        raise ErrorCLI(f"Quedan {len(abiertas)} tareas de la {pedida} sin aprobar: {nombres}",
                       "Que se aprueben en el board, o muévelas de versión; después, repite.")
    fecha = _fecha_del_tag(raiz, estado["tag"])
    _, aprobadas = contar(proyecto, str(pedida), fecha, bool(estado["tag"]))
    if aprobadas["sin_fecha"]:
        avisos.append(f"{aprobadas['sin_fecha']} tareas hechas de la {pedida} sin fecha de "
                      f"cierre: no se sabe si van antes o después de {estado['tag']}, y no "
                      f"entran en las notas.")
    decisiones, problemas = conocimiento(raiz, fecha, avisos)
    nombre = proyecto.nombre if proyecto else raiz.name
    notas = componer(nombre, pedida, estado["tag"], fecha, aprobadas["tareas"],
                     decisiones, problemas)
    ruta = f"{almacen.CARPETA}/{almacen.CARPETA_RELEASES}/{pedida.etiqueta}.md"
    comando = comando_tag(raiz, nombre, pedida)
    salida = {"esquema": ESQUEMA, "repo": str(raiz),
              "proyecto": proyecto.nombre if proyecto else None, "version": str(pedida),
              "tag": pedida.etiqueta,
              "desde": {"tag": estado["tag"], "fecha": fecha}, "aplicado": bool(args.aplicar),
              "tareas": aprobadas["tareas"], "decisiones": decisiones, "problemas": problemas,
              "archivo": ruta, "notas": notas}
    if not args.aplicar:
        salida["salida"] = f"Ensayo: nada escrito. Con --aplicar se escriben en {ruta}."
    else:
        try:
            hecho, _, version = almacen.Almacen(raiz).escribir_release(
                pedida.etiqueta, notas, args.reemplazar)
        except almacen.EntradaCambiada as error:
            raise ErrorCLI(f"{ruta} ya existe con otro contenido (version {error.version_actual})",
                           f"Míralo; para reescribirlo con estas notas, repite con "
                           f"--reemplazar {error.version_actual}. No se escribió nada.",
                           codigo=4) from error
        salida.update({"hecho": hecho, "version_archivo": version, "comando": comando,
                       "salida": f"Notas en {ruta}. Commitéalas y, cuando lo decidas, "
                                 f"etiqueta tú: {comando}"})
    if avisos:
        salida["avisos"] = avisos
    imprimir(salida)
    return 0


def anadir(sub):
    verbo = sub.add_parser(
        "release", help="Notas de la versión (ensayo; --aplicar las escribe en "
                        ".cotejo/releases/). Nunca etiqueta: devuelve el git tag")
    verbo.add_argument("--proyecto", help="El proyecto. Por defecto, el repo donde estás")
    verbo.add_argument("--version", metavar="X.Y.Z", help="Por defecto, la en curso")
    verbo.add_argument("--aplicar", action="store_true", help="Escribir las notas")
    verbo.add_argument("--reemplazar", metavar="HASH",
                       help="Reescribir unas notas que ya existen con otro contenido: su hash")
    verbo.set_defaults(funcion=cmd_release)
