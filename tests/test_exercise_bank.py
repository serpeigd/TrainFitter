"""Tests for exercise_bank.py's bilingual display names.

nombre_mostrado()/NOMBRES_ES are display-only (see the module docstring):
the canonical "nombre" field used for selection and the validator's safety
cross-check must never depend on these."""

from exercise_bank import EXERCISE_BANK, nombre_mostrado


def test_every_exercise_has_a_spanish_display_name():
    for ejercicio in EXERCISE_BANK:
        assert ejercicio.get("nombre_es"), f"missing nombre_es for {ejercicio['nombre']!r}"


def test_nombre_mostrado_returns_spanish_only_for_es():
    assert nombre_mostrado("Barbell squat", "es") == "Sentadilla con barra"
    assert nombre_mostrado("Barbell squat", "en") == "Barbell squat"


def test_nombre_mostrado_falls_back_to_english_for_unknown_name():
    """A future motor="llm" exercise not in this catalog shouldn't crash
    display -- it just shows whatever name it came with."""
    assert nombre_mostrado("Some LLM-invented exercise", "es") == "Some LLM-invented exercise"
