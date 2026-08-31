"""Tests for agents/adherencia_parser.py -- pure formatting, no I/O.

Note: this module used to also parse a plain-text checklist reply --
replaced by a fillable PDF form (see docs/decisiones.md and
agents/pdf_generador.py). Reading structured data out of a reply is now
tested in tests/test_pdf_generador.py; this file only covers what's left
here: the rating heuristic and the summary formatter."""

from datetime import date, timedelta

from adherencia_parser import (
    checklist_tiene_contenido_real,
    resumen_mensual_tendencia,
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


# --- Language: real, reported bug (mixed-language trainer notification) ---


def test_summary_labels_are_translated_in_spanish():
    resumen = resumir_adherencia(
        _datos(notas_rutina="Molestia en la rodilla.", notas_dieta="Cuesta los findes."), idioma="es",
    )
    assert "Rutina: 3/4 sesiones completadas." in resumen
    assert "Notas de rutina: Molestia en la rodilla." in resumen
    assert "Dieta: 5/7 días seguidos." in resumen
    assert "Notas de dieta: Cuesta los findes." in resumen
    # No English label should leak through when idioma="es". ("Diet" is
    # deliberately not checked as a bare substring -- it's contained
    # inside "Dieta" itself.)
    assert "Routine" not in resumen
    assert "sessions completed" not in resumen
    assert "days followed" not in resumen


def test_summary_diet_blank_answer_in_spanish():
    resumen = resumir_adherencia(_datos(dias_dieta_seguidos=None, dias_dieta_totales=7), idioma="es")
    assert "Dieta: ?/7 días seguidos." in resumen


def test_sugerencia_for_each_valoracion_is_distinct_and_non_empty_in_spanish():
    sugerencias = {v: sugerencia_seguimiento(v, idioma="es") for v in ["High", "Medium", "Low", None]}
    assert len(set(sugerencias.values())) == 4
    assert all(sugerencias.values())


def test_sugerencia_es_default_stays_english_for_backward_compatibility():
    """No idioma argument passed -- every existing caller before this fix
    keeps getting English until it's updated to pass idioma explicitly."""
    assert sugerencia_seguimiento("High") == sugerencia_seguimiento("High", idioma="en")


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


# --- resumen_mensual_tendencia() (free monthly digest) ---------------------


def _hace(dias: int) -> str:
    return (date.today() - timedelta(days=dias)).isoformat()


def _fila(fecha, tipo="Adherence check-in", valoracion=None, peso_kg=None, notas=""):
    return {"fecha": fecha, "tipo": tipo, "valoracion": valoracion, "peso_kg": peso_kg, "notas": notas}


def test_none_for_empty_history():
    assert resumen_mensual_tendencia([]) is None


def test_none_when_everything_is_older_than_the_window():
    historial = [
        _fila(_hace(45), valoracion="High"),
        _fila(_hace(40), peso_kg=80.0),
        _fila(_hace(35), peso_kg=79.0),
    ]
    assert resumen_mensual_tendencia(historial) is None


def test_none_with_a_single_recent_weight_point_and_no_checkins():
    """One weight point in the window, no adherence check-ins at all --
    same "don't fabricate a trend from one data point" bar as
    tendencia_peso()."""
    assert resumen_mensual_tendencia([_fila(_hace(5), peso_kg=80.0)]) is None


def test_reports_adherence_trend_from_recent_checkins():
    historial = [
        _fila(_hace(2), valoracion="High"),
        _fila(_hace(10), valoracion="High"),
        _fila(_hace(20), valoracion="Medium"),
    ]
    resumen = resumen_mensual_tendencia(historial)
    assert "3 check-ins" in resumen
    assert "trending strong" in resumen  # average (3+3+2)/3 = 2.67 -> rounds to 3 -> "strong"


def test_ignores_plan_sent_rows_for_the_adherence_count():
    historial = [
        _fila(_hace(1), tipo="Plan sent"),
        _fila(_hace(2), valoracion="High"),
    ]
    resumen = resumen_mensual_tendencia(historial)
    assert "1 check-in," in resumen  # singular, and the "Plan sent" row isn't counted


def test_reports_weight_change_when_available():
    historial = [_fila(_hace(25), peso_kg=80.0), _fila(_hace(2), peso_kg=78.5)]
    resumen = resumen_mensual_tendencia(historial)
    assert "Weight: 80.0kg → 78.5kg (-1.5kg)." in resumen


def test_weight_gain_shows_a_plus_sign():
    historial = [_fila(_hace(25), peso_kg=70.0), _fila(_hace(2), peso_kg=71.2)]
    resumen = resumen_mensual_tendencia(historial)
    assert "(+1.2kg)" in resumen


def test_combines_adherence_and_weight_in_one_message():
    historial = [
        _fila(_hace(2), valoracion="Low", peso_kg=None),
        _fila(_hace(20), peso_kg=80.0),
        _fila(_hace(3), peso_kg=79.0),
    ]
    resumen = resumen_mensual_tendencia(historial)
    assert "1 check-in, adherence trending low." in resumen
    assert "Weight: 80.0kg → 79.0kg (-1.0kg)." in resumen


def test_ignores_rows_older_than_the_window_even_when_mixed_with_recent_ones():
    historial = [
        _fila(_hace(2), valoracion="High"),
        _fila(_hace(45), valoracion="Low"),  # outside the 30-day window -- must not count
    ]
    resumen = resumen_mensual_tendencia(historial)
    assert "1 check-in, adherence trending strong." in resumen


def test_translates_to_spanish():
    historial = [_fila(_hace(2), valoracion="High"), _fila(_hace(20), peso_kg=80.0), _fila(_hace(3), peso_kg=79.0)]
    resumen = resumen_mensual_tendencia(historial, idioma="es")
    assert "Últimos 30 días: 1 check-in, adherencia con tendencia alta." in resumen
    assert "Peso: 80.0kg → 79.0kg (-1.0kg)." in resumen
    assert "Weight" not in resumen
    assert "trending" not in resumen


def test_ignores_a_malformed_or_missing_date_rather_than_crashing():
    """Degrades to "excluded from the window" rather than crashing --
    same discipline as tendencia_peso()'s own malformed-date test."""
    historial = [
        _fila("not-a-date", valoracion="High"),
        _fila(None, peso_kg=999.0),
        _fila(_hace(2), valoracion="Low"),
    ]
    resumen = resumen_mensual_tendencia(historial)
    assert "1 check-in, adherence trending low." in resumen
    assert "999.0" not in resumen
