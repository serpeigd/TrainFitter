"""Tests for the diet rule engine (agents/dieta_reglas.py)."""

from dieta_reglas import (
    DISTRIBUCION_VARIANTES,
    MENSAJE_CLIENTE_DIETA_VARIANTES,
    PROTEINA_G_POR_KG,
    generar_borrador_dieta_reglas,
)


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


def test_idioma_es_translates_narrative_text_only(perfil_base):
    """Same invariant as rutina_reglas.py's equivalent test: idioma="es"
    translates the narrative text but food "nombre" values in
    fuentes_*_sugeridas stay canonical English -- the validator's allergy
    cross-check depends on it (see food_bank.py's module docstring)."""
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    borrador = generar_borrador_dieta_reglas(perfil_base, idioma="es")

    assert "Estimación de" in borrador["resumen_enfoque"]
    # distribucion_comidas is picked from a pool of equivalent Spanish
    # phrasings (see variacion.py) -- check that it's a real (formatted)
    # member of that pool rather than one exact legacy string, so this test
    # doesn't depend on which variant got picked.
    assert borrador["distribucion_comidas"] in {v.format(n=4) for v in DISTRIBUCION_VARIANTES["es"]}
    assert borrador["mensaje_para_el_cliente"].startswith("Hola ")
    assert any("hierro" in consejo.lower() for consejo in borrador["consejos_sinergias"])
    assert "Lentils" in borrador["fuentes_proteina_sugeridas"]  # still canonical English


def test_default_idioma_matches_explicit_english(perfil_base):
    borrador_default = generar_borrador_dieta_reglas(perfil_base)
    borrador_en = generar_borrador_dieta_reglas(perfil_base, idioma="en")
    assert borrador_default == borrador_en


def test_regenerating_the_same_client_is_stable(perfil_base):
    """Same id_cliente -> same narrative phrasing every time (seeded by
    id_cliente, see variacion.py)."""
    borrador_1 = generar_borrador_dieta_reglas(perfil_base)
    borrador_2 = generar_borrador_dieta_reglas(perfil_base)
    assert borrador_1 == borrador_2


def test_different_clients_get_varied_narrative_text(perfil_base):
    """Clients with an otherwise-identical profile shouldn't all read
    byte-identical boilerplate. Only 4 variants exist, so sample enough
    distinct IDs that the pool's actual size shows up, rather than
    asserting inequality between two arbitrary picks (which can
    coincidentally collide -- a 1-in-4 chance)."""
    mensajes = set()
    for i in range(15):
        perfil_base["id_cliente"] = f"cliente_variedad_{i}"
        borrador = generar_borrador_dieta_reglas(perfil_base)
        assert borrador["mensaje_para_el_cliente"].startswith("Hi Test, ")
        cuerpo = borrador["mensaje_para_el_cliente"].removeprefix("Hi Test, ")
        assert cuerpo in MENSAJE_CLIENTE_DIETA_VARIANTES["en"]
        mensajes.add(cuerpo)
    assert len(mensajes) > 1


# --- plan_semanal / fuentes_verdura_sugeridas (weekly meal planner) -------


def test_weekly_plan_has_seven_days_starting_monday(perfil_base):
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert len(borrador["plan_semanal"]) == 7
    assert borrador["plan_semanal"][0]["dia"] == "Monday"
    assert borrador["plan_semanal"][-1]["dia"] == "Sunday"


def test_weekly_plan_day_names_follow_idioma(perfil_base):
    borrador = generar_borrador_dieta_reglas(perfil_base, idioma="es")
    assert borrador["plan_semanal"][0]["dia"] == "Lunes"


def test_weekly_plan_meal_count_matches_comidas_al_dia(perfil_base):
    perfil_base["nutricion"]["comidas_al_dia_preferidas"] = 5
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert all(len(dia["comidas"]) == 5 for dia in borrador["plan_semanal"])


def test_weekly_plan_meals_include_kcal_and_description(perfil_base):
    borrador = generar_borrador_dieta_reglas(perfil_base)
    for comida in borrador["plan_semanal"][0]["comidas"]:
        assert comida["aprox_kcal"] > 0
        assert comida["descripcion"]
        assert comida["tipo"]


def test_vegetable_sources_present_and_diet_type_filtered(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert "Broccoli" in borrador["fuentes_verdura_sugeridas"]


def test_allergy_excludes_food_from_weekly_plan(perfil_base):
    """The weekly plan only ever draws from the already-filtered
    fuentes_*_sugeridas candidate pools (see planificador_comidas.py's
    docstring) -- a declared allergy must never show up in plan_semanal's
    own text either, not just be absent from the flat lists."""
    perfil_base["salud"]["alergias_alimentarias"] = ["tree nut allergy"]
    borrador = generar_borrador_dieta_reglas(perfil_base)
    texto_plan = str(borrador["plan_semanal"]).lower()
    assert "nuts (walnuts" not in texto_plan
