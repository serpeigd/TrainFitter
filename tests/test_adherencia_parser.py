"""Tests for agents/adherencia_parser.py -- pure formatting, no I/O.

Note: this module used to also parse a plain-text checklist reply --
replaced by a fillable PDF form (see docs/decisiones.md and
agents/pdf_generador.py). Reading structured data out of a reply is now
tested in tests/test_pdf_generador.py; this file only covers what's left
here: the rating heuristic and the summary formatter."""

from adherencia_parser import resumir_adherencia, sugerencia_seguimiento, valoracion_desde_ratios


def test_valoracion_high_for_strong_adherence():
    assert valoracion_desde_ratios([0.9, 0.85]) == "High"


def test_valoracion_medium_for_partial_adherence():
    assert valoracion_desde_ratios([0.75, 0.6]) == "Medium"


def test_valoracion_low_for_weak_adherence():
    assert valoracion_desde_ratios([0.2]) == "Low"


def test_valoracion_none_for_no_ratios_at_all():
    assert valoracion_desde_ratios([]) is None


def test_valoracion_averages_routine_and_diet_ratios():
    # 0.75 + ~0.71 averages to ~0.73 -> Medium, not High (either ratio alone
    # would round up to High on its own).
    assert valoracion_desde_ratios([0.75, 5 / 7]) == "Medium"


def _datos(**overrides):
    base = {
        "dias_rutina_completados": 3,
        "dias_rutina_totales": 4,
        "notas_rutina": "",
        "dias_dieta_seguidos": 5,
        "dias_dieta_totales": 7,
        "notas_dieta": "",
    }
    base.update(overrides)
    return base


def test_summary_combines_routine_and_diet_into_one_line():
    resumen = resumir_adherencia(_datos(notas_rutina="Knee felt off.", notas_dieta="Struggled on weekends."))
    assert "Routine: 3/4 sessions completed." in resumen
    assert "Knee felt off." in resumen
    assert "Diet: 5/7 days followed." in resumen
    assert "Struggled on weekends." in resumen


def test_summary_omits_routine_line_when_no_routine_data_found():
    """dias_rutina_totales == 0 means no checkbox fields were found at all
    -- "0/0 sessions completed" would misleadingly read as "did zero
    sessions" rather than "no routine data in this reply"."""
    resumen = resumir_adherencia(_datos(dias_rutina_totales=0, dias_rutina_completados=0))
    assert "Routine:" not in resumen
    assert "Diet: 5/7 days followed." in resumen


def test_summary_omits_diet_line_when_no_diet_data_found():
    resumen = resumir_adherencia(_datos(dias_dieta_totales=None, dias_dieta_seguidos=None))
    assert "Diet:" not in resumen
    assert "Routine: 3/4 sessions completed." in resumen


def test_summary_shows_question_mark_when_diet_answer_left_blank():
    resumen = resumir_adherencia(_datos(dias_dieta_seguidos=None, dias_dieta_totales=7))
    assert "Diet: ?/7 days followed." in resumen


def test_summary_is_truncated_to_notion_rich_text_limit():
    resumen = resumir_adherencia(_datos(notas_rutina="x" * 3000))
    assert len(resumen) == 2000


def test_sugerencia_for_each_valoracion_is_distinct_and_non_empty():
    """Locks in that every branch is reachable and gives a real,
    distinguishable suggestion -- not just that the function returns
    *some* string for each input."""
    sugerencias = {v: sugerencia_seguimiento(v) for v in ["High", "Medium", "Low", None]}
    assert len(set(sugerencias.values())) == 4
    assert all(sugerencias.values())


def test_sugerencia_high_points_toward_progression():
    assert "progression" in sugerencia_seguimiento("High").lower()


def test_sugerencia_low_points_toward_simplifying_not_pushing():
    """Matches this loop's own evidence base (Lally et al. 2010, see
    docs/base_conocimiento/adherencia_y_cambio_de_conducta.md): low
    adherence is a signal to address a barrier, not a failure to punish
    with more volume."""
    sugerencia = sugerencia_seguimiento("Low").lower()
    assert "simplify" in sugerencia or "barrier" in sugerencia
