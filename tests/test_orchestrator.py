"""Integration tests: the full orchestrator pipeline end-to-end, motor="reglas"
(the free path — no API key involved, matches what CI runs). Uses the real
example client profiles so this doubles as a regression check against the
shipped examples/output_*.json snapshots."""

import json
from pathlib import Path

from orchestrator import ejecutar_pipeline

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
