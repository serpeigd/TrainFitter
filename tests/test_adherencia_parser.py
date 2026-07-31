"""Tests for agents/adherencia_parser.py -- pure text parsing, no network,
no Gmail/Notion credentials needed."""

from adherencia_parser import analizar_adherencia, resumir_adherencia

CHECKLIST_EN = """TrainFitter — Adherence check-in for Marta

Reply to this email with this same file edited, marking what you actually did.

== ROUTINE ==
Mark each day you completed with an [x]. Leave it as [ ] if you skipped it.

[x] Day 1 — Upper A
[x] Day 2 — Lower A
[x] Day 3 — Upper B
[ ] Day 4 — Lower B

Anything about the routine we should know?
[ROUTINE NOTES BELOW]
> Skipped day 4, knee felt off during warmup.

== DIET ==
Target: 2125 kcal/day, 136 g protein.
Out of the last 7 days, how many would you say you followed the plan?
[DIET DAYS FOLLOWED, out of 7]
> 5

Anything about the diet we should know?
[DIET NOTES BELOW]
> Struggled on weekends, ate out twice.
"""

CHECKLIST_UNTOUCHED = """TrainFitter — Adherence check-in for Marta

== ROUTINE ==
[ ] Day 1 — Upper A
[ ] Day 2 — Lower A

[ROUTINE NOTES BELOW]
>

== DIET ==
[DIET DAYS FOLLOWED, out of 7]
>

[DIET NOTES BELOW]
>
"""


def test_parses_completed_routine_days_and_notes():
    datos = analizar_adherencia(CHECKLIST_EN)
    assert datos["dias_rutina_completados"] == 3
    assert datos["dias_rutina_totales"] == 4
    assert datos["notas_rutina"] == "Skipped day 4, knee felt off during warmup."


def test_parses_diet_days_followed_and_notes():
    datos = analizar_adherencia(CHECKLIST_EN)
    assert datos["dias_dieta_seguidos"] == 5
    assert datos["dias_dieta_totales"] == 7
    assert datos["notas_dieta"] == "Struggled on weekends, ate out twice."


def test_rating_reflects_high_combined_adherence():
    # 3/4 routine (0.75) + 5/7 diet (~0.71) averages to ~0.73 -> Medium.
    assert analizar_adherencia(CHECKLIST_EN)["valoracion"] == "Medium"


def test_untouched_reply_counts_as_zero_completed_but_no_diet_answer():
    """A reply where the client didn't fill in the diet days-followed
    number should record dias_dieta_seguidos as None, not 0 -- an absent
    answer isn't the same claim as "I followed 0 days"."""
    datos = analizar_adherencia(CHECKLIST_UNTOUCHED)
    assert datos["dias_rutina_completados"] == 0
    assert datos["dias_rutina_totales"] == 2
    assert datos["dias_dieta_seguidos"] is None
    assert datos["dias_dieta_totales"] == 7
    assert datos["notas_rutina"] == ""
    assert datos["notas_dieta"] == ""


def test_untouched_reply_rating_falls_back_to_routine_only():
    # No diet ratio counted (answer missing) -- rating is routine-only: 0/2 -> Low.
    assert analizar_adherencia(CHECKLIST_UNTOUCHED)["valoracion"] == "Low"


def test_diet_days_followed_answer_is_capped_at_the_stated_total():
    """A client typing something like "7 out of 7, maybe more!" shouldn't
    produce an adherence ratio above 100%."""
    texto = CHECKLIST_UNTOUCHED.replace("[DIET DAYS FOLLOWED, out of 7]\n>", "[DIET DAYS FOLLOWED, out of 7]\n> 12")
    datos = analizar_adherencia(texto)
    assert datos["dias_dieta_seguidos"] == 7


def test_completely_unparseable_text_returns_no_rating():
    datos = analizar_adherencia("This isn't the checklist at all, just a random reply.")
    assert datos["dias_rutina_totales"] == 0
    assert datos["dias_dieta_totales"] is None
    assert datos["valoracion"] is None


def test_summary_combines_routine_and_diet_into_one_line():
    resumen = resumir_adherencia(analizar_adherencia(CHECKLIST_EN))
    assert "Routine: 3/4 sessions completed." in resumen
    assert "knee felt off" in resumen
    assert "Diet: 5/7 days followed." in resumen
    assert "Struggled on weekends" in resumen


def test_summary_is_truncated_to_notion_rich_text_limit():
    datos = analizar_adherencia(CHECKLIST_EN)
    datos["notas_rutina"] = "x" * 3000
    assert len(resumir_adherencia(datos)) == 2000
