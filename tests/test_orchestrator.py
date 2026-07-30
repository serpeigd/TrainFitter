"""Integration tests: the full orchestrator pipeline end-to-end, motor="reglas"
(the free path — no API key involved, matches what CI runs). Uses the real
example client profiles so this doubles as a regression check against the
shipped examples/output_*.json snapshots."""

import json
from pathlib import Path

import orchestrator
from orchestrator import ejecutar_pipeline
from routine_agent import RoutineAgentError

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def _cargar_cliente(numero: int) -> dict:
    return json.loads((EXAMPLES_DIR / f"cliente_ejemplo_{numero}.json").read_text(encoding="utf-8"))


def test_clean_client_reaches_pending_human_approval():
    perfil = _cargar_cliente(1)  # no injuries, no allergies
    estado = ejecutar_pipeline(perfil, on_transition=lambda *_: None)
    assert estado.estado == "pendiente_aprobacion_humana"
    assert estado.veredicto["veredicto"] == "aprobado_automatico"
    assert estado.error is None


def test_injury_and_intolerance_client_reaches_enhanced_review():
    perfil = _cargar_cliente(2)  # knee injury + lactose intolerance
    estado = ejecutar_pipeline(perfil, on_transition=lambda *_: None)
    assert estado.estado == "pendiente_revision_reforzada"
    assert estado.veredicto["veredicto"] == "revision_reforzada"
    assert estado.veredicto["motivos"]  # non-empty


def test_state_history_follows_the_documented_order():
    perfil = _cargar_cliente(1)
    estado = ejecutar_pipeline(perfil, on_transition=lambda *_: None)
    assert estado.historial == [
        "ficha_recibida",
        "rutina_generada",
        "dieta_generada",
        "validado",
        "pendiente_aprobacion_humana",
    ]


def test_on_transition_callback_is_invoked_for_every_step():
    perfil = _cargar_cliente(1)
    transiciones = []
    ejecutar_pipeline(perfil, on_transition=lambda cliente_id, estado: transiciones.append((cliente_id, estado)))
    assert transiciones == [
        ("cliente_001", "rutina_generada"),
        ("cliente_001", "dieta_generada"),
        ("cliente_001", "validado"),
        ("cliente_001", "pendiente_aprobacion_humana"),
    ]


def test_pipeline_never_sends_anything_automatically():
    """Both success branches are "pendiente_*" (pending) states — there is
    no code path that reaches a "sent" or "enviado" state on its own."""
    for numero in (1, 2):
        estado = ejecutar_pipeline(_cargar_cliente(numero), on_transition=lambda *_: None)
        assert estado.estado.startswith("pendiente_")


def test_idioma_es_propagates_to_every_stage():
    """ejecutar_pipeline()'s idioma param must reach routine, diet, AND the
    validator's motivos -- a real regression risk since each is threaded
    through separately (routine_agent, diet_agent, validator_agent)."""
    perfil = _cargar_cliente(2)  # knee injury + lactose intolerance -> non-empty motivos
    estado = ejecutar_pipeline(perfil, on_transition=lambda *_: None, idioma="es")
    assert "Hola" in estado.borrador_rutina["mensaje_para_el_cliente"]
    assert "Hola" in estado.borrador_dieta["mensaje_para_el_cliente"]
    assert any("lesión" in motivo.lower() or "rodilla" in motivo.lower() for motivo in estado.veredicto["motivos"])


def test_routine_agent_failure_lands_in_error_state_without_crashing(monkeypatch):
    """A RoutineAgentError (e.g. motor="llm" hitting a bad API key, a
    timeout, or a malformed model response) must be caught, not propagated —
    ejecutar_pipeline() always returns a PipelineState, even on failure, so
    the caller (the UI) never has to wrap it in its own try/except."""
    def _fallar(*args, **kwargs):
        raise RoutineAgentError("simulated failure: bad API key")

    monkeypatch.setattr(orchestrator, "generar_borrador_rutina", _fallar)

    transiciones = []
    estado = ejecutar_pipeline(
        _cargar_cliente(1), on_transition=lambda cliente_id, nuevo_estado: transiciones.append(nuevo_estado)
    )

    assert estado.estado == "error"
    assert "simulated failure" in estado.error
    assert estado.historial == ["ficha_recibida", "error"]
    assert transiciones == ["error"]
    # Never got far enough to generate a diet or a verdict.
    assert estado.borrador_dieta is None
    assert estado.veredicto is None
