"""
Orquestador: coordina el pipeline completo (rutina -> dieta -> validador) sobre
un perfil de cliente, con estado explícito y logging de cada transición.

DISEÑO — por qué un dataclass de estado explícito y no variables sueltas:
Con variables sueltas (rutina = ..., dieta = ..., veredicto = ...) el "estado
del pipeline" no existe como concepto: solo se puede inferir mirando qué
variables están rellenas en un momento dado. Con un PipelineState explícito,
el estado es un dato de primera clase: se puede loguear, guardar, inspeccionar,
o (en la Fase 5+) persistir en Notion sin cambiar la lógica del orquestador.
También hace el flujo auto-documentado: la lista ESTADOS de abajo ES el
diagrama de flujo de docs/arquitectura.md, no una aproximación de él.

DISEÑO — por qué transicionar() no imprime directamente:
El logging por consola es una forma de observar las transiciones, no la
única. La UI de Streamlit (ui/app.py) necesita pintar el mismo recorrido de
estados en pantalla en vez de en una terminal que el usuario nunca ve. En
vez de acoplar el orquestador a print(), transicionar() solo actualiza el
dato; quien llama a ejecutar_pipeline() decide cómo reaccionar a cada
transición vía el callback on_transition (por defecto, sigue imprimiendo en
consola para no romper los scripts de demo existentes).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from diet_agent import DietAgentError, generar_borrador_dieta
from routine_agent import RoutineAgentError, generar_borrador_rutina
from validator_agent import validar_borradores

# Orden de los estados por los que pasa cada cliente. PipelineState.estado
# siempre debe ser uno de estos valores.
ESTADOS = [
    "ficha_recibida",
    "rutina_generada",
    "dieta_generada",
    "validado",
    "pendiente_aprobacion_humana",
    "pendiente_revision_reforzada",
    "error",
]


@dataclass
class PipelineState:
    """Estado explícito del pipeline para un cliente concreto."""

    cliente_id: str
    perfil_cliente: dict
    estado: str = "ficha_recibida"
    historial: list[str] = field(default_factory=lambda: ["ficha_recibida"])
    borrador_rutina: dict | None = None
    borrador_dieta: dict | None = None
    veredicto: dict | None = None
    error: str | None = None

    def transicionar(self, nuevo_estado: str) -> None:
        if nuevo_estado not in ESTADOS:
            raise ValueError(f"Estado desconocido: {nuevo_estado!r}")
        self.estado = nuevo_estado
        self.historial.append(nuevo_estado)


def _log_consola(cliente_id: str, nuevo_estado: str) -> None:
    marca = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"  [{marca}] {cliente_id}: -> {nuevo_estado}")


def ejecutar_pipeline(perfil_cliente: dict, motor: str = "reglas", on_transition=None) -> PipelineState:
    """
    Ejecuta el pipeline completo sobre un cliente y devuelve el estado final.

    Args:
        perfil_cliente: dict con el esquema de examples/cliente_ejemplo_*.json.
        motor: "reglas" (por defecto) o "llm", se pasa tal cual a cada agente.
        on_transition: callback opcional (cliente_id: str, nuevo_estado: str) -> None,
            invocado justo después de cada transición. Por defecto loguea a consola
            (comportamiento histórico de los scripts run_*_demo.py); la UI pasa su
            propio callback para actualizar la pantalla en vez de la terminal.

    No lanza excepción si un agente falla: la captura, deja el estado en
    "error" con el detalle, y devuelve el PipelineState para que el llamador
    decida qué hacer (nunca se envía nada en ese caso).
    """
    on_transition = on_transition or _log_consola
    cliente_id = perfil_cliente.get("id_cliente", "desconocido")
    estado = PipelineState(cliente_id=cliente_id, perfil_cliente=perfil_cliente)

    def avanzar(nuevo_estado: str) -> None:
        estado.transicionar(nuevo_estado)
        on_transition(cliente_id, nuevo_estado)

    try:
        rutina = generar_borrador_rutina(perfil_cliente, motor=motor)
        estado.borrador_rutina = rutina.contenido
        avanzar("rutina_generada")

        dieta = generar_borrador_dieta(perfil_cliente, motor=motor)
        estado.borrador_dieta = dieta.contenido
        avanzar("dieta_generada")

        veredicto = validar_borradores(perfil_cliente, estado.borrador_rutina, estado.borrador_dieta)
        estado.veredicto = veredicto
        avanzar("validado")

    except (RoutineAgentError, DietAgentError) as exc:
        estado.error = str(exc)
        avanzar("error")
        return estado

    if veredicto["veredicto"] == "revision_reforzada":
        avanzar("pendiente_revision_reforzada")
    else:
        avanzar("pendiente_aprobacion_humana")

    return estado
