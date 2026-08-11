"""Tests for agents/routine_agent.py -- both the motor dispatch ("reglas" vs
"llm" vs an invalid value) and the "llm" engine's own request-building/
response-parsing/error-handling, exercised against a fake `anthropic`
module (see tests/conftest.py's fake_anthropic fixture) instead of a real,
paid API call.

This closes a real, previously-disclosed gap: motor="llm" is designed but
deliberately never exercised against the real Anthropic API (see
docs/decisiones.md, CLAUDE.md's Free-only guardrail) -- until now, that
also meant the request/response-handling code itself had zero test
coverage of any kind, mocked or otherwise. These tests don't validate the
model's actual output quality (nothing can, without a real call), but they
do lock in that a well-formed response gets parsed correctly, and that
every documented failure mode (missing key, timeout, connection error, API
error, a response with no tool_use) raises the right, clearly-worded
RoutineAgentError -- all for free, with no API key and no network."""

from unittest.mock import MagicMock

import pytest
from routine_agent import ENTREGAR_BORRADOR_RUTINA_TOOL, RoutineAgentError, generar_borrador_rutina

CONTENIDO_VALIDO = {
    "resumen_enfoque": "Full body split for a beginner.",
    "nivel_asumido": "principiante",
    "dias_por_semana": 3,
    "advertencias_revision_humana": [],
    "sesiones": [{"dia": "Day 1", "ejercicios": [{"nombre": "Goblet squat", "series": 3, "repeticiones": "8-12"}]}],
    "progresion": "Add one rep per session.",
    "mensaje_para_el_cliente": "Here's your first draft routine.",
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
    borrador = generar_borrador_rutina(perfil_base)
    assert borrador.cliente_id == perfil_base["id_cliente"]
    assert "sesiones" in borrador.contenido


def test_invalid_motor_raises_value_error(perfil_base):
    with pytest.raises(ValueError, match="motor"):
        generar_borrador_rutina(perfil_base, motor="not-a-real-engine")


# --- motor="llm": missing credentials ----------------------------------------


def test_llm_without_api_key_raises_clear_error(perfil_base, monkeypatch, fake_anthropic):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RoutineAgentError, match="ANTHROPIC_API_KEY"):
        generar_borrador_rutina(perfil_base, motor="llm", api_key=None)
    # Fails before ever touching the (fake) network -- no client built.
    fake_anthropic.Anthropic.assert_not_called()


def test_llm_falls_back_to_the_env_var_when_no_api_key_argument_given(perfil_base, monkeypatch, fake_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_rutina(perfil_base, motor="llm")
    _args, kwargs = fake_anthropic.Anthropic.call_args
    assert kwargs["api_key"] == "env-key"


def test_llm_explicit_api_key_wins_over_the_env_var(perfil_base, monkeypatch, fake_anthropic):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_rutina(perfil_base, motor="llm", api_key="explicit-key")
    _args, kwargs = fake_anthropic.Anthropic.call_args
    assert kwargs["api_key"] == "explicit-key"


# --- motor="llm": a well-formed response -------------------------------------


def test_llm_success_returns_the_parsed_draft(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    borrador = generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key")
    assert borrador.contenido == CONTENIDO_VALIDO
    assert borrador.cliente_id == perfil_base["id_cliente"]


def test_llm_call_forces_the_routine_tool(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert kwargs["tools"] == [ENTREGAR_BORRADOR_RUTINA_TOOL]
    assert kwargs["tool_choice"] == {"type": "tool", "name": "entregar_borrador_rutina"}


def test_llm_sends_the_clients_own_profile(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert perfil_base["datos_basicos"]["nombre"] in kwargs["messages"][0]["content"]


def test_llm_spanish_appends_a_translation_instruction_to_the_system_prompt(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_rutina(perfil_base, motor="llm", idioma="es", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert "Spanish" in kwargs["system"]


def test_llm_english_system_prompt_has_no_spanish_instruction(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_rutina(perfil_base, motor="llm", idioma="en", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert "Spanish" not in kwargs["system"]


def test_llm_system_prompt_includes_the_trainers_method(perfil_base, fake_anthropic):
    """Locks in that _build_system_prompt() actually loaded and embedded
    docs/metodo_entrenador.md -- not just some placeholder text."""
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key")
    _args, kwargs = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert "entregar_borrador_rutina" in kwargs["system"]


def test_llm_passes_through_the_requested_model_and_timeout(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.return_value = _respuesta_valida(CONTENIDO_VALIDO)
    generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key", model="claude-opus-5", timeout=15.0)
    _args, kwargs = fake_anthropic.Anthropic.call_args
    assert kwargs["timeout"] == 15.0
    _args2, kwargs2 = fake_anthropic.Anthropic.return_value.messages.create.call_args
    assert kwargs2["model"] == "claude-opus-5"


# --- motor="llm": every documented failure mode ------------------------------


def test_llm_timeout_is_wrapped_in_routine_agent_error(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.side_effect = fake_anthropic.APITimeoutError("timed out")
    with pytest.raises(RoutineAgentError, match="Timeout"):
        generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key", timeout=30.0)


def test_llm_connection_error_is_wrapped(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.side_effect = fake_anthropic.APIConnectionError("no network")
    with pytest.raises(RoutineAgentError, match="connect"):
        generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key")


def test_llm_api_status_error_includes_status_code_and_message(perfil_base, fake_anthropic):
    fake_anthropic.Anthropic.return_value.messages.create.side_effect = fake_anthropic.APIStatusError(
        "bad request", status_code=400,
    )
    with pytest.raises(RoutineAgentError, match="400"):
        generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key")


def test_llm_response_with_no_tool_use_raises_error(perfil_base, fake_anthropic):
    """Simulates the model replying with plain text instead of calling the
    forced tool -- should never happen with tool_choice, but the code
    guards against it explicitly, so this locks in that guard."""
    respuesta = MagicMock()
    respuesta.content = []
    respuesta.stop_reason = "end_turn"
    fake_anthropic.Anthropic.return_value.messages.create.return_value = respuesta
    with pytest.raises(RoutineAgentError, match="structured draft"):
        generar_borrador_rutina(perfil_base, motor="llm", api_key="fake-key")
