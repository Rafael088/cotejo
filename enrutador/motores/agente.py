"""El motor por defecto: no lanza nada, devuelve el encargo para que lo hagas tú.

Es el que corresponde al caso normal, que es una persona diciéndole a un agente que ya está
abierto «ponte con las tareas de este proyecto». Ese agente no necesita que nadie lance un
proceso: necesita que alguien le diga qué tarea le toca, que la tome en Cotejo a su nombre y que
le dé el encargo. Eso es exactamente lo que devuelve este motor.

Que sea el defecto y no `headless` es una decisión, no una casualidad. Mandar el trabajo a un
`claude -p` que corre solo, sin que nadie lo vea, es útil de vez en cuando pero no es lo
habitual: el trabajo lo hace un agente con el que estás hablando, o una instancia que puedes
abrir y dirigir. Los dos caminos pasan por aquí o por `sesion`, y ninguno de los dos necesita
la API.
"""

from .. import motor


class Agente(motor.Motor):
    nombre = "agente"

    def ejecutar(self, encargo):
        return motor.Resultado(True, [], 0, salida=encargo.prompt, ejecutado=False)
