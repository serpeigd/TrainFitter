"""
Orchestrator: coordinates the full pipeline (routine -> diet -> validator)
over a client profile, with explicit state and logging of every transition.

DESIGN — why an explicit state dataclass instead of loose variables:
With loose variables (routine = ..., diet = ..., verdict = ...) the
"pipeline state" doesn't exist as a concept: it can only be inferred by
looking at which variables happen to be filled in at a given moment. With an
explicit PipelineState, the state is a first-class piece of data: it can be
logged, saved, inspected, or (in Phase 5+) persisted to Notion without
changing the orchestrator's logic. It also makes the flow self-documenting:
the ESTADOS list below literally IS the flow diagram in
docs/arquitectura.md, not an approximation of it.

DESIGN — why transicionar() doesn't print directly:
Console logging is one way to observe transitions, not the only one. The
Streamlit UI (ui/app.py) needs to paint the same state trail on screen
instead of in a terminal the user never sees. Instead of coupling the
orchestrator to print(), transicionar() just updates the data; whoever
calls ejecutar_pipeline() decides how to react to each transition via the
on_transition callback (by default, it keeps logging to the console so the
existing demo scripts don't break).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from diet_agent import DietAgentError, generar_borrador_dieta
from routine_agent import RoutineAgentError, generar_borrador_rutina
from validator_agent import validar_borradores

# Order of the states each client goes through. PipelineState.estado must
# always be one of these values.
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
    """Explicit pipeline state for a specific client."""

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
            raise ValueError(f"Unknown state: {nuevo_estado!r}")
        self.estado = nuevo_estado
        self.historial.append(nuevo_estado)


def _log_consola(cliente_id: str, nuevo_estado: str) -> None:
    marca = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"  [{marca}] {cliente_id}: -> {nuevo_estado}")


def ejecutar_pipeline(perfil_cliente: dict, motor: str = "reglas", on_transition=None, idioma: str = "en") -> PipelineState:
    """
    Runs the full pipeline on a client and returns the final state.

    Args:
        perfil_cliente: dict with the schema from examples/cliente_ejemplo_*.json.
        motor: "reglas" (default) or "llm", passed as-is to each agent.
        on_transition: optional callback (cliente_id: str, nuevo_estado: str) -> None,
            invoked right after each transition. Defaults to logging to the
            console (the historical behavior of the run_*_demo.py scripts);
            the UI passes its own callback to update the screen instead of
            the terminal.
        idioma: "en" (default) or "es", passed as-is to each agent — language
            of the generated narrative text (see routine_agent/diet_agent/
            validator_agent for exactly what this does and doesn't affect).

    Doesn't raise if an agent fails: it catches it, leaves the state as
    "error" with the detail, and returns the PipelineState so the caller can
    decide what to do (nothing is ever sent in that case).
    """
    on_transition = on_transition or _log_consola
    cliente_id = perfil_cliente.get("id_cliente", "desconocido")
    estado = PipelineState(cliente_id=cliente_id, perfil_cliente=perfil_cliente)

    def avanzar(nuevo_estado: str) -> None:
        estado.transicionar(nuevo_estado)
        on_transition(cliente_id, nuevo_estado)

    try:
        rutina = generar_borrador_rutina(perfil_cliente, motor=motor, idioma=idioma)
        estado.borrador_rutina = rutina.contenido
        avanzar("rutina_generada")

        dieta = generar_borrador_dieta(perfil_cliente, motor=motor, idioma=idioma)
        estado.borrador_dieta = dieta.contenido
        avanzar("dieta_generada")

        veredicto = validar_borradores(perfil_cliente, estado.borrador_rutina, estado.borrador_dieta, idioma=idioma)
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
