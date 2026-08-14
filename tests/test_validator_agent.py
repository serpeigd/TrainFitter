"""Tests for validator_agent.py — the pipeline's safety gate.

Covers both aggregation (does it surface warnings the draft agents already
flagged) and the "defense in depth" cross-check (does it catch a risky
exercise/food even when the draft's own advertencias_revision_humana is
empty — simulating a future engine, e.g. motor="llm", getting its
self-assessment wrong)."""

from dieta_reglas import generar_borrador_dieta_reglas
from rutina_reglas import generar_borrador_rutina_reglas
from validator_agent import validar_borradores


def test_clean_profile_is_auto_approved(perfil_base):
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["veredicto"] == "aprobado_automatico"
    assert veredicto["motivos"] == []


def test_injury_profile_forces_enhanced_review(perfil_base):
    perfil_base["salud"]["lesiones"] = [
        {"zona": "knee", "descripcion": "old ACL injury", "estado": "antigua_controlada", "activa_actualmente": False}
    ]
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("injury" in motivo.lower() for motivo in veredicto["motivos"])


def test_catches_contraindicated_exercise_even_if_draft_did_not_flag_it(perfil_base):
    """Defense in depth: a hand-built draft that "forgot" to exclude a
    contraindicated exercise and didn't self-report a warning must still be
    caught by the validator's independent cross-check against exercise_bank."""
    perfil_base["salud"]["lesiones"] = [
        {"zona": "knee", "descripcion": "", "estado": "antigua_controlada", "activa_actualmente": False}
    ]
    borrador_rutina_defectuoso = {
        "advertencias_revision_humana": [],  # simulates a buggy/LLM engine that self-reported nothing
        "sesiones": [
            {
                "dia": "Day 1 — Legs",
                "ejercicios": [{"nombre": "Barbell squat", "series": 4, "repeticiones": "5-8", "descanso_seg": 150, "notas": ""}],
            }
        ],
    }
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, borrador_rutina_defectuoso, dieta)
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("Barbell squat" in motivo for motivo in veredicto["motivos"])


def test_catches_conflicting_food_even_if_draft_did_not_flag_it(perfil_base):
    perfil_base["salud"]["alergias_alimentarias"] = ["egg allergy"]
    borrador_dieta_defectuoso = {
        "advertencias_revision_humana": [],
        "fuentes_proteina_sugeridas": ["Eggs"],
        "fuentes_carbohidrato_sugeridas": [],
        "fuentes_grasa_sugeridas": [],
    }
    rutina = generar_borrador_rutina_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, borrador_dieta_defectuoso)
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("Eggs" in motivo for motivo in veredicto["motivos"])


def test_catches_conflicting_vegetable_even_if_draft_did_not_flag_it(perfil_base):
    """Same defense-in-depth pattern as test_catches_conflicting_food_
    even_if_draft_did_not_flag_it, for the vegetable/fruit category added
    alongside the weekly meal planner -- locks in that adding a 4th food
    list didn't accidentally skip it in the cross-check."""
    perfil_base["salud"]["alergias_alimentarias"] = ["fish allergy"]
    borrador_dieta_defectuoso = {
        "advertencias_revision_humana": [],
        "fuentes_proteina_sugeridas": [],
        "fuentes_carbohidrato_sugeridas": [],
        "fuentes_grasa_sugeridas": ["Oily fish (EPA/DHA)"],
        "fuentes_verdura_sugeridas": ["Broccoli"],
    }
    rutina = generar_borrador_rutina_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, borrador_dieta_defectuoso)
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("Oily fish" in motivo for motivo in veredicto["motivos"])
    assert not any("Broccoli" in motivo for motivo in veredicto["motivos"])


def test_out_of_range_bloodwork_marker_forces_enhanced_review(perfil_base):
    """Same defense-in-depth pattern as injuries/allergies, applied to
    parsed bloodwork markers (agents/analytics_parser.py)."""
    perfil_base["salud"]["analitica_adjunta"] = {
        "tiene": True,
        "archivo": "analitica.pdf",
        "fecha": "2026-01-20",
        "notas": "",
        "marcadores": [
            {"nombre": "TSH", "valor": 6.8, "unidad": "mIU/L", "rango_normal": "0.4-4.0 mIU/L", "fuera_de_rango": True},
            {"nombre": "Ferritin", "valor": 75.0, "unidad": "ng/mL", "rango_normal": "15-200 ng/mL", "fuera_de_rango": False},
        ],
    }
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("TSH" in motivo for motivo in veredicto["motivos"])
    assert not any("Ferritin" in motivo for motivo in veredicto["motivos"])


def test_all_normal_bloodwork_markers_do_not_force_review(perfil_base):
    perfil_base["salud"]["analitica_adjunta"] = {
        "tiene": True,
        "archivo": "analitica.pdf",
        "fecha": "2026-01-15",
        "notas": "",
        "marcadores": [
            {"nombre": "Ferritin", "valor": 75.0, "unidad": "ng/mL", "rango_normal": "15-200 ng/mL", "fuera_de_rango": False},
        ],
    }
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["veredicto"] == "aprobado_automatico"


def test_idioma_es_translates_motivos(perfil_base):
    """The verdict logic itself must not change with idioma -- only the
    language of the "motivos" strings shown to the trainer does."""
    perfil_base["salud"]["lesiones"] = [
        {"zona": "rodilla", "descripcion": "old ACL injury", "estado": "antigua_controlada", "activa_actualmente": False}
    ]
    rutina = generar_borrador_rutina_reglas(perfil_base, idioma="es")
    dieta = generar_borrador_dieta_reglas(perfil_base, idioma="es")
    veredicto = validar_borradores(perfil_base, rutina, dieta, idioma="es")
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("lesión" in motivo.lower() for motivo in veredicto["motivos"])


def test_idioma_es_translates_condition_pregnancy_medication_and_bloodwork_motivos(perfil_base):
    """test_idioma_es_translates_motivos above only exercises the injury
    branch of _motivos_desde_perfil()'s Spanish path -- a coverage report
    (see pyproject.toml's [tool.coverage.run]) surfaced that the other
    four (condition, pregnancy, medication, bloodwork) were untested in
    Spanish specifically, on the pipeline's safety gate. Closed here."""
    perfil_base["salud"]["enfermedades_o_condiciones"] = ["hipertensión"]
    perfil_base["salud"]["embarazo_o_lactancia"] = {"aplica": True, "detalle": "second trimester"}
    perfil_base["salud"]["medicacion_habitual"] = ["metformina"]
    perfil_base["salud"]["analitica_adjunta"] = {
        "tiene": True, "archivo": "x.pdf", "fecha": "2026-01-01", "notas": "",
        "marcadores": [{"nombre": "TSH", "valor": 6.8, "unidad": "mIU/L", "rango_normal": "0.4-4.0", "fuera_de_rango": True}],
    }
    rutina = generar_borrador_rutina_reglas(perfil_base, idioma="es")
    dieta = generar_borrador_dieta_reglas(perfil_base, idioma="es")
    veredicto = validar_borradores(perfil_base, rutina, dieta, idioma="es")
    motivos_texto = " ".join(veredicto["motivos"]).lower()
    assert "condición" in motivos_texto
    assert "embarazo" in motivos_texto
    assert "medicación" in motivos_texto
    assert "tsh" in motivos_texto


def test_idioma_es_translates_diet_allergy_conflict_motivo(perfil_base):
    """Same coverage gap as above, for _validar_dieta_contra_alergias()'s
    own Spanish branch -- the defense-in-depth cross-check that catches a
    conflicting food even when the draft didn't self-flag it."""
    perfil_base["salud"]["alergias_alimentarias"] = ["huevo"]
    borrador_dieta_defectuoso = {
        "advertencias_revision_humana": [],
        "fuentes_proteina_sugeridas": ["Eggs"],
        "fuentes_carbohidrato_sugeridas": [],
        "fuentes_grasa_sugeridas": [],
    }
    rutina = generar_borrador_rutina_reglas(perfil_base, idioma="es")
    veredicto = validar_borradores(perfil_base, rutina, borrador_dieta_defectuoso, idioma="es")
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("revisión necesaria" in motivo.lower() and "eggs" in motivo.lower() for motivo in veredicto["motivos"])


def test_exercise_not_in_the_bank_is_skipped_not_crashed(perfil_base):
    """Defensive branch for a future motor="llm" routine: an exercise name
    the local EXERCISE_BANK doesn't recognize can't be cross-checked
    against injuries, so it's silently skipped rather than raising a
    KeyError -- locked in here rather than only implicitly relied upon."""
    perfil_base["salud"]["lesiones"] = [
        {"zona": "rodilla", "descripcion": "", "estado": "antigua_controlada", "activa_actualmente": False}
    ]
    borrador_rutina_llm = {
        "advertencias_revision_humana": [],
        "sesiones": [{"dia": "Day 1", "ejercicios": [{"nombre": "Some exercise not in our bank", "series": 3, "repeticiones": "8-12"}]}],
    }
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, borrador_rutina_llm, dieta)
    # Still flagged for the declared injury itself (from the raw profile),
    # just not for a cross-check against an exercise it can't identify.
    assert veredicto["veredicto"] == "revision_reforzada"
    assert not any("Some exercise not in our bank" in motivo for motivo in veredicto["motivos"])


def test_duplicate_reasons_are_not_repeated(perfil_base):
    """Both the routine and diet engines independently warn about a declared
    health condition using the exact same wording — the validator must
    dedup that overlap instead of showing it to the trainer twice."""
    perfil_base["salud"]["enfermedades_o_condiciones"] = ["asthma"]
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    condicion_msg = "Declared health condition: asthma. Enhanced review before sending."
    assert condicion_msg in rutina["advertencias_revision_humana"]
    assert condicion_msg in dieta["advertencias_revision_humana"]

    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["motivos"].count(condicion_msg) == 1
    assert len(veredicto["motivos"]) == len(set(veredicto["motivos"]))


def test_supplements_alongside_medication_forces_enhanced_review(perfil_base):
    perfil_base["salud"]["suplementos_actuales"] = ["creatine"]
    perfil_base["salud"]["medicacion_habitual"] = ["blood thinner"]
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("supplement" in motivo.lower() for motivo in veredicto["motivos"])


def test_supplements_alone_do_not_force_enhanced_review(perfil_base):
    """Only the combination with regular medication is treated as a
    possible interaction -- supplements on their own aren't a safety
    concern (see docs/base_conocimiento/suplementacion.md's own scope)."""
    perfil_base["salud"]["suplementos_actuales"] = ["creatine"]
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["veredicto"] == "aprobado_automatico"


def test_idioma_es_translates_supplement_interaction_motivo(perfil_base):
    perfil_base["salud"]["suplementos_actuales"] = ["creatina"]
    perfil_base["salud"]["medicacion_habitual"] = ["anticoagulante"]
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta, idioma="es")
    assert any("suplemento" in motivo.lower() for motivo in veredicto["motivos"])


def test_a_recognized_pair_adds_a_specific_motivo_alongside_the_generic_one(perfil_base):
    """suplementos_interacciones.pares_interaccion_declarados() is
    additive: a recognized pair (vitamin K + an anticoagulant) still
    keeps the generic 'supplements alongside medication' motivo AND adds
    a more specific one naming the actual mechanism."""
    perfil_base["salud"]["suplementos_actuales"] = ["Vitamin K"]
    perfil_base["salud"]["medicacion_habitual"] = ["Warfarin"]
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["veredicto"] == "revision_reforzada"
    assert any("supplements" in m.lower() and "alongside" in m.lower() for m in veredicto["motivos"])
    assert any("known interaction" in m.lower() for m in veredicto["motivos"])


def test_an_unrecognized_pair_still_forces_review_without_a_specific_motivo(perfil_base):
    """Creatine has no known relevant interaction -- validar_borradores()
    must still force revision_reforzada off the generic check alone,
    exactly as before this feature existed."""
    perfil_base["salud"]["suplementos_actuales"] = ["creatine"]
    perfil_base["salud"]["medicacion_habitual"] = ["ibuprofen"]
    rutina = generar_borrador_rutina_reglas(perfil_base)
    dieta = generar_borrador_dieta_reglas(perfil_base)
    veredicto = validar_borradores(perfil_base, rutina, dieta)
    assert veredicto["veredicto"] == "revision_reforzada"
    assert not any("known interaction" in m.lower() for m in veredicto["motivos"])
