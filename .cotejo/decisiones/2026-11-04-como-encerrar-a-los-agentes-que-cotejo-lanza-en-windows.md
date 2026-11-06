---
id: dec-dik7
fecha: 2026-11-04
temas: [windows, sandbox]
estado: reemplazada
autor: agente
reemplazada_por: dec-cxjs
---
# Cómo encerrar a los agentes que Cotejo lanza en Windows

Hoy Windows no encierra al agente dentro de su carpeta: conserva los permisos de la cuenta de la persona, aunque Cotejo limite lo que concede OpenCode y bloquee algunos comandos desde el PATH.\n\nPropuesta: usar AppContainer como destino para el encierro nativo de Windows y hacer antes un prototipo que confirme que git, los agentes y las pruebas siguen funcionando. Si AppContainer no permite una experiencia usable, probar un job object con un token restringido como solución más pequeña, dejando claro qué accesos todavía conserva.\n\nOpciones consideradas:\n\n- AppContainer: encierro nativo y ajustable por carpetas y red; exige integrar y probar bien los permisos de cada agente.\n- Windows Sandbox: aislamiento fuerte, pero abre otro Windows y complica conservar el proyecto, las sesiones y una experiencia sin terminales.\n- Job object con token restringido: más fácil de integrar y sirve para controlar procesos y reducir permisos, pero por sí solo no garantiza que el agente quede encerrado en su carpeta.\n- WSL: permite reutilizar el encierro disponible en un entorno Linux, pero obliga a instalar y entender otro entorno y cambia rutas, herramientas y sesiones.\n\nLa decisión debe aceptarse solo después de un prototipo en Windows real que mida compatibilidad, límites efectivos y coste de mantenimiento.
