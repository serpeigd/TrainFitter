"""Shared fixtures for the test suite.

`perfil_base` returns a minimal-but-complete client profile matching the
schema in examples/cliente_ejemplo_*.json, with no injuries/allergies/
conditions — a "clean" baseline. Individual tests deep-copy it and mutate
only the fields relevant to what they're checking.

`fake_anthropic` lets test_routine_agent.py/test_diet_agent.py exercise
motor="llm"'s real request-building/response-parsing/error-handling code
(agents/routine_agent.py's/agents/diet_agent.py's `_generar_borrador_*_llm()`)
without the real `anthropic` package installed and without ever touching the
network -- see that fixture's own docstring for how and why.
"""

import copy
import sys
import types

import pytest


def _perfil_base() -> dict:
    return {
        "id_cliente": "test_cliente",
        "fecha_admision": "2026-01-01",
        "datos_basicos": {"nombre": "Test Person", "edad": 30, "sexo": "hombre", "peso_kg": 80, "altura_cm": 180},
        "objetivo": {"principal": "hipertrofia", "en_sus_palabras": ""},
        "experiencia": {"nivel": "intermedio", "anios_entrenando": 2, "detalle": ""},
        "disponibilidad": {
            "dias_por_semana": 4,
            "minutos_por_sesion": 60,
            "lugar_entreno": "gimnasio_completo",
            "material_disponible": ["maquinas_guiadas", "poleas", "barras_y_discos", "mancuernas", "bancos"],
        },
        "salud": {
            "lesiones": [],
            "enfermedades_o_condiciones": [],
            "embarazo_o_lactancia": {"aplica": False, "detalle": ""},
            "medicacion_habitual": [],
            "alergias_alimentarias": [],
            "intolerancias_alimentarias": [],
            "analitica_adjunta": {"tiene": False, "archivo": None, "fecha": None, "notas": ""},
        },
        "nutricion": {
            "tipo_dieta": "omnivora",
            "restricciones": [],
            "alimentos_que_no_le_gustan": [],
            "comidas_al_dia_preferidas": 4,
            "contexto": "",
        },
        "estilo_de_vida": {
            "horas_sueno_promedio": 7,
            "nivel_estres_percibido": "medio",
            "tipo_trabajo": "sedentary office job",
            "pasos_diarios_aprox": 6000,
        },
        "notas_libres": "",
    }


@pytest.fixture
def perfil_base() -> dict:
    return copy.deepcopy(_perfil_base())


class FakeAPITimeoutError(Exception):
    """Stand-in for anthropic.APITimeoutError -- a real Exception subclass
    (not a MagicMock) because the real code under test does
    `except anthropic.APITimeoutError as exc:`, and Python requires the
    thing named in an except clause to actually be an exception class."""


class FakeAPIConnectionError(Exception):
    """Stand-in for anthropic.APIConnectionError -- see FakeAPITimeoutError."""


class FakeAPIStatusError(Exception):
    """Stand-in for anthropic.APIStatusError. Carries .status_code/.message
    because agents/routine_agent.py's and agents/diet_agent.py's except
    clauses read both off the real exception."""

    def __init__(self, message: str = "error", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@pytest.fixture
def fake_anthropic(monkeypatch):
    """Injects a fake `anthropic` module into sys.modules so
    agents/routine_agent.py's/agents/diet_agent.py's lazy `import anthropic`
    (inside _generar_borrador_*_llm()) binds to it instead of trying to
    import the real package -- which isn't installed in CI on purpose (see
    requirements.txt: the free rule-engine pipeline never needs it, and
    motor="llm" is deliberately never exercised against the real,
    paid API). This tests the REAL request-building/response-parsing/
    error-handling code in those two functions, just against a fake
    `anthropic.Anthropic(...).messages.create(...)` instead of a live call
    -- no network, no API key, no cost, same mocked-dependency approach
    already used for Gmail/Notion (see test_gmail_client_network.py/
    test_notion_connector_network.py).

    Yields the fake module. A test configures the mock response via
    `fake_anthropic.Anthropic.return_value.messages.create.return_value = ...`
    (a real API response's .content is a list of blocks; a tool_use block
    needs `.type = "tool_use"` and `.input = {...}`) or raises one of the
    Fake*Error classes above via `.side_effect = FakeAPITimeoutError(...)`.
    """
    from unittest.mock import MagicMock

    modulo_falso = types.ModuleType("anthropic")
    modulo_falso.Anthropic = MagicMock()
    modulo_falso.APITimeoutError = FakeAPITimeoutError
    modulo_falso.APIConnectionError = FakeAPIConnectionError
    modulo_falso.APIStatusError = FakeAPIStatusError
    monkeypatch.setitem(sys.modules, "anthropic", modulo_falso)
    return modulo_falso
