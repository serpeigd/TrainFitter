"""Tests for agents/diet_agent.py -- same coverage gap and same approach as
test_routine_agent.py (see that file's own docstring for the full
rationale): motor dispatch, plus motor="llm"'s request-building/response-
parsing/error-handling against a fake `anthropic` module
(tests/conftest.py's fake_anthropic fixture), no real API key or network
involved."""

from unittest.mock import MagicMock

import pytest
from diet_agent import ENTREGAR_BORRADOR_DIETA_TOOL, DietAgentError, generar_borrador_dieta

CONTENIDO_VALIDO = {
    "resumen_enfoque": "Estimated 2000 kcal/day.",
    "calorias_objetivo_kcal": 2000,
    "macros": {"proteina_g": 130, "grasa_g": 60, "carbohidratos_g": 200},
    "comidas_al_dia": 4,
    "distribucion_comidas": "Spread across 4 meals.",
    "fuentes_proteina_sugeridas": ["Chicken breast"],
    "fuentes_carbohidrato_sugeridas": ["Rice"],
    "fuentes_grasa_sugeridas": ["Extra virgin olive oil"],
    "fuentes_verdura_sugeridas": ["Broccoli"],
    "plan_semanal": [],
    "consejos_sinergias": [],
    "advertencias_revision_humana": [],
    "mensaje_para_el_cliente": "Here's your first draft diet.",
}


def _bloque_tool_use(contenido: dict) -> MagicMock:
    bloque = MagicMock()
    bloque.type = "tool_use"
    bloque.input = contenido
    return bloque


def _respuesta_valida(contenido: dict) -> MagicMock:
    respuesta = MagicMock()
    respuesta.content = [_bloque_tool_use(contenido)]
    respuesta.stop_reason = "tool_use"
    return respuesta


# --- motor dispatch ---------------------------------------------------------


def test_reglas_is_the_default_and_delegates_to_the_rule_engine(perfil_base):
    borrador = generar_borrador_dieta(perfil_base)
    assert borrador.cliente_id == perfil_base["id_cliente"]
    assert "plan_semanal" in borrador.contenido


def test_invalid_motor_raises_value_error(perfil_base):
    with pytest.raises(ValueError, match="motor"):
        generar_borrador_dieta(perfil_base, motor="not-a-real-engine")


# --- motor="llm": missing credentials ----------------------------------------


def test_llm_without_api_key_raises_clear_error(perfil_base, monkeypatch, fake_anthropic):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(DietAgentError, match="ANTHROPIC_API_KEY"):
        generar_borrador_dieta(perfil_base, motor="llm", api_key=None)
    fake_anthropic.Anthropic.assert_not_called()


def test_llm_falls_back_to_the_env_var_when_no_api_key_argument_given(perfil_base, monkeypatch, fake_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_dieta(perfil_base, motor="llm")
    _args, kwargs = fake_anthropic.Anthropic.call_args
    assert kwargs["api_key"] == "env-key"


def test_llm_explicit_api_key_wins_over_the_env_var(perfil_base, monkeypatch, fake_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_dieta(perfil_base, motor="llm", api_key="explicit-key")
    _args, kwargs = fake_anthropic.Anthropic.call_args
    assert kwargs["api_key"] == "explicit-key"


# --- motor="llm": a well-formed response -------------------------------------


def test_llm_success_returns_the_parsed_draft(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    borrador = generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key")
    assert borrador.contenido == CONTENIDO_VALIDO
    assert borrador.cliente_id == perfil_base["id_cliente"]


def test_llm_call_forces_the_diet_tool(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert kwargs["tools"] == [ENTREGAR_BORRADOR_DIETA_TOOL]
    assert kwargs["tool_choice"] == {"type": "tool", "name": "entregar_borrador_dieta"}


def test_llm_sends_the_clients_own_profile(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert perfil_base["datos_basicos"]["nombre"] in kwargs["messages"][0]["content"]


def test_llm_spanish_appends_a_translation_instruction_to_the_system_prompt(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_dieta(perfil_base, motor="llm", idioma="es", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert "Spanish" in kwargs["system"]


def test_llm_system_prompt_covers_the_personalization_rules(perfil_base, fake_anthropic):
    """Locks in that the rules added for maximal personalization (disliked
    foods, soft dietary preferences, lifestyle-based bias) actually made it
    into the system prompt sent to the model -- not just the rule engine's
    own code."""
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert "disliked foods" in kwargs["system"]
    assert "anti-inflammatory" in kwargs["system"]


def test_llm_passes_through_the_requested_model_and_timeout(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key", model="claude-opus-5", timeout=15.0)
    _args, kwargs = fake_anthropic.Anthropic.call_args
    assert kwargs["timeout"] == 15.0
    _args2, kwargs2 = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert kwargs2["model"] == "claude-opus-5"


# --- motor="llm": every documented failure mode ------------------------------


def test_llm_timeout_is_wrapped_in_diet_agent_error(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.side_effect = fake_anthropic.APITimeoutError("timed out")
    with pytest.raises(DietAgentError, match="Timeout"):
        generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key", timeout=30.0)


def test_llm_connection_error_is_wrapped(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.side_effect = fake_anthropic.APIConnectionError("no network")
    with pytest.raises(DietAgentError, match="connect"):
        generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key")


def test_llm_api_status_error_includes_status_code_and_message(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.side_effect = fake_anthropic.APIStatusError(
        "bad request", status_code=400,
    )
    with pytest.raises(DietAgentError, match="400"):
        generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key")


def test_llm_response_with_no_tool_use_raises_error(perfil_base, fake_anthropic):
    respuesta = MagicMock()
    respuesta.content = []
    respuesta.stop_reason = "end_turn"
    fake_anthropic.Anthropic.return_value.messages.create.return_value = respuesta
    with pytest.raises(DietAgentError, match="structured draft"):
        generar_borrador_dieta(perfil_base, motor="llm", api_key="fake-key")
