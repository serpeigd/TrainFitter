"""Tests for the diet rule engine (agents/dieta_reglas.py)."""

from dieta_reglas import PROTEINA_G_POR_KG, generar_borrador_dieta_reglas


def test_hypertrophy_targets_more_calories_than_fat_loss(perfil_base):
    perfil_base["objetivo"]["principal"] = "hipertrofia"
    hipertrofia = generar_borrador_dieta_reglas(perfil_base)

    perfil_base["objetivo"]["principal"] = "perdida_grasa"
    perdida = generar_borrador_dieta_reglas(perfil_base)

    assert hipertrofia["calorias_objetivo_kcal"] > perdida["calorias_objetivo_kcal"]


def test_protein_target_matches_goal_ratio(perfil_base):
    peso_kg = perfil_base["datos_basicos"]["peso_kg"]
    for objetivo, g_por_kg in PROTEINA_G_POR_KG.items():
        perfil_base["objetivo"]["principal"] = objetivo
        borrador = generar_borrador_dieta_reglas(perfil_base)
        assert borrador["macros"]["proteina_g"] == round(peso_kg * g_por_kg)


def test_vegan_diet_gets_iron_absorption_tip(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert any("iron" in consejo.lower() for consejo in borrador["consejos_sinergias"])


def test_omnivore_diet_has_no_iron_tip(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "omnivora"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert not any("iron" in consejo.lower() for consejo in borrador["consejos_sinergias"])


def test_food_allergy_generates_human_review_warning(perfil_base):
    perfil_base["salud"]["alergias_alimentarias"] = ["peanuts"]
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert len(borrador["advertencias_revision_humana"]) == 1
    assert "peanuts" in borrador["advertencias_revision_humana"][0]


def test_pregnancy_generates_human_review_warning(perfil_base):
    perfil_base["salud"]["embarazo_o_lactancia"] = {"aplica": True, "detalle": "week 20"}
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert any("pregnan" in w.lower() for w in borrador["advertencias_revision_humana"])


def test_clean_profile_has_no_warnings(perfil_base):
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert borrador["advertencias_revision_humana"] == []


def test_meals_per_day_respected(perfil_base):
    perfil_base["nutricion"]["comidas_al_dia_preferidas"] = 5
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert borrador["comidas_al_dia"] == 5
