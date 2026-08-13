"""Tests for agents/adherencia_parser.py -- pure formatting, no I/O.

Note: this module used to also parse a plain-text checklist reply --
replaced by a fillable PDF form (see docs/decisiones.md and
agents/pdf_generador.py). Reading structured data out of a reply is now
tested in tests/test_pdf_generador.py; this file only covers what's left
here: the rating heuristic and the summary formatter."""

from adherencia_parser import (
    checklist_tiene_contenido_real,
    resumir_adherencia,
    sugerencia_seguimiento,
    tendencia_peso,
    valoracion_desde_ratios,
)


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


# --- checklist_tiene_contenido_real() (forward-tracking safety net) -------


def test_blank_checklist_has_no_real_content():
    """The exact shape a genuinely blank-but-structurally-intact checklist
    reads as (see leer_checklist_pdf()): fields present, all unfilled."""
    datos = _datos(dias_rutina_completados=0, dias_dieta_seguidos=None, notas_rutina="", notas_dieta="")
    assert checklist_tiene_contenido_real(datos) is False


def test_completed_sessions_count_as_real_content():
    assert checklist_tiene_contenido_real(_datos(dias_rutina_completados=1)) is True


def test_a_zero_diet_days_answer_counts_as_real_content():
    """Explicitly answering "0 days followed" is real information -- not
    the same as leaving the question blank (dias_dieta_seguidos=None)."""
    datos = _datos(dias_rutina_completados=0, dias_dieta_seguidos=0, notas_rutina="", notas_dieta="")
    assert checklist_tiene_contenido_real(datos) is True


def test_notes_alone_count_as_real_content():
    datos = _datos(dias_rutina_completados=0, dias_dieta_seguidos=None, notas_rutina="Felt great!", notas_dieta="")
    assert checklist_tiene_contenido_real(datos) is True


# --- tendencia_peso() (weight-trend nudge) ---------------------------------


def _checkin(fecha, peso_kg):
    return {"fecha": fecha, "peso_kg": peso_kg, "tipo": "Adherence check-in", "valoracion": None, "notas": ""}


def test_flags_stalled_weight_for_a_fat_loss_goal():
    historial = [_checkin("2026-08-01", 80.0), _checkin("2026-08-15", 79.9)]
    resultado = tendencia_peso(historial, "perdida_grasa")
    assert resultado is not None
    assert "down" in resultado.lower()
    assert "14 days" in resultado


def test_no_flag_when_weight_is_trending_down_for_a_fat_loss_goal():
    historial = [_checkin("2026-08-01", 80.0), _checkin("2026-08-15", 78.5)]
    assert tendencia_peso(historial, "perdida_grasa") is None


def test_flags_stalled_weight_for_a_hypertrophy_goal():
    historial = [_checkin("2026-08-01", 70.0), _checkin("2026-08-15", 70.1)]
    resultado = tendencia_peso(historial, "hipertrofia")
    assert resultado is not None
    assert "up" in resultado.lower()


def test_no_flag_when_weight_is_trending_up_for_a_hypertrophy_goal():
    historial = [_checkin("2026-08-01", 70.0), _checkin("2026-08-15", 71.5)]
    assert tendencia_peso(historial, "hipertrofia") is None


def test_no_flag_for_goals_with_no_clear_weight_direction():
    """recomposicion_corporal (fat loss + muscle gain can net to ~stable
    weight) and salud_general (no specific weight target) deliberately
    never get a trend check at all -- guessing would be worse than
    silence, same discipline as the dietary-concern presets."""
    historial = [_checkin("2026-08-01", 80.0), _checkin("2026-08-15", 80.0)]
    assert tendencia_peso(historial, "recomposicion_corporal") is None
    assert tendencia_peso(historial, "salud_general") is None
    assert tendencia_peso(historial, None) is None


def test_no_flag_with_fewer_than_two_weight_points():
    assert tendencia_peso([_checkin("2026-08-01", 80.0)], "perdida_grasa") is None
    assert tendencia_peso([], "perdida_grasa") is None


def test_no_flag_when_the_window_is_too_short():
    historial = [_checkin("2026-08-01", 80.0), _checkin("2026-08-05", 80.0)]
    assert tendencia_peso(historial, "perdida_grasa") is None


def test_rows_without_weight_are_ignored_not_counted():
    historial = [
        _checkin("2026-08-01", 80.0),
        {"fecha": "2026-08-10", "peso_kg": None, "tipo": "x", "valoracion": "High", "notas": ""},
        _checkin("2026-08-15", 79.9),
    ]
    resultado = tendencia_peso(historial, "perdida_grasa")
    assert resultado is not None  # still computed from the two real weight points, 14 days apart


def test_sorts_by_date_regardless_of_input_order():
    """historial_checkins() returns most-recent-first -- this function
    must not assume any particular input order."""
    historial = [_checkin("2026-08-15", 79.9), _checkin("2026-08-01", 80.0)]
    resultado = tendencia_peso(historial, "perdida_grasa")
    assert resultado is not None
    assert "80.0kg -> 79.9kg" in resultado


def test_translates_for_spanish():
    historial = [_checkin("2026-08-01", 80.0), _checkin("2026-08-15", 79.9)]
    resultado = tendencia_peso(historial, "perdida_grasa", idioma="es")
    assert "no ha bajado" in resultado.lower()


def test_no_flag_when_a_date_is_malformed():
    """Degrades to "nothing to flag" rather than crashing -- Notion data
    should always be well-formed, but this is a nudge, not a safety gate,
    so silence is the right failure mode if it somehow isn't."""
    historial = [_checkin("not-a-date", 80.0), _checkin("2026-08-15", 79.9)]
    assert tendencia_peso(historial, "perdida_grasa") is None
