"""Tests for the diet rule engine (agents/dieta_reglas.py)."""

from dieta_reglas import (
    DISTRIBUCION_VARIANTES,
    MENSAJE_CLIENTE_DIETA_VARIANTES,
    PLAN_INICIO_DIETA,
    PROTEINA_G_POR_KG,
    _consejos_sinergias,
    generar_borrador_dieta_reglas,
)


def test_mas_proteina_and_menos_proteina_move_protein_target(perfil_base):
    base = generar_borrador_dieta_reglas(perfil_base)

    perfil_base["nutricion"]["ajustes_dieta"] = ["mas_proteina"]
    mas = generar_borrador_dieta_reglas(perfil_base)
    assert mas["macros"]["proteina_g"] > base["macros"]["proteina_g"]

    perfil_base["nutricion"]["ajustes_dieta"] = ["menos_proteina"]
    menos = generar_borrador_dieta_reglas(perfil_base)
    assert menos["macros"]["proteina_g"] < base["macros"]["proteina_g"]


def test_mas_carbohidratos_and_menos_carbohidratos_trade_off_against_fat(perfil_base):
    base = generar_borrador_dieta_reglas(perfil_base)

    perfil_base["nutricion"]["ajustes_dieta"] = ["mas_carbohidratos"]
    mas_carbo = generar_borrador_dieta_reglas(perfil_base)
    assert mas_carbo["macros"]["carbohidratos_g"] > base["macros"]["carbohidratos_g"]
    assert mas_carbo["macros"]["grasa_g"] < base["macros"]["grasa_g"]
    # Protein and calories are untouched by this specific adjustment.
    assert mas_carbo["macros"]["proteina_g"] == base["macros"]["proteina_g"]
    assert mas_carbo["calorias_objetivo_kcal"] == base["calorias_objetivo_kcal"]

    perfil_base["nutricion"]["ajustes_dieta"] = ["menos_carbohidratos"]
    menos_carbo = generar_borrador_dieta_reglas(perfil_base)
    assert menos_carbo["macros"]["carbohidratos_g"] < base["macros"]["carbohidratos_g"]
    assert menos_carbo["macros"]["grasa_g"] > base["macros"]["grasa_g"]


def test_mas_calorias_and_menos_calorias_move_the_calorie_target(perfil_base):
    base = generar_borrador_dieta_reglas(perfil_base)

    perfil_base["nutricion"]["ajustes_dieta"] = ["mas_calorias"]
    mas = generar_borrador_dieta_reglas(perfil_base)
    assert mas["calorias_objetivo_kcal"] > base["calorias_objetivo_kcal"]

    perfil_base["nutricion"]["ajustes_dieta"] = ["menos_calorias"]
    menos = generar_borrador_dieta_reglas(perfil_base)
    assert menos["calorias_objetivo_kcal"] < base["calorias_objetivo_kcal"]


def test_mas_comidas_and_menos_comidas_move_meal_count(perfil_base):
    perfil_base["nutricion"]["comidas_al_dia_preferidas"] = 4

    perfil_base["nutricion"]["ajustes_dieta"] = ["mas_comidas"]
    mas = generar_borrador_dieta_reglas(perfil_base)
    assert len(mas["plan_semanal"][0]["comidas"]) == 5

    perfil_base["nutricion"]["ajustes_dieta"] = ["menos_comidas"]
    menos = generar_borrador_dieta_reglas(perfil_base)
    assert len(menos["plan_semanal"][0]["comidas"]) == 3


def test_sin_lacteos_excludes_dairy_tagged_foods(perfil_base):
    perfil_base["nutricion"]["ajustes_dieta"] = ["sin_lacteos"]
    borrador = generar_borrador_dieta_reglas(perfil_base)
    fuentes = (
        borrador["fuentes_proteina_sugeridas"] + borrador["fuentes_carbohidrato_sugeridas"]
        + borrador["fuentes_grasa_sugeridas"]
    )
    assert not any("yogur" in f.lower() or "yogurt" in f.lower() for f in fuentes)


def test_diet_adjustments_are_disclosed_in_the_summary(perfil_base):
    """Never a silent adjustment -- same transparency principle as
    _consejos_por_preferencias_blandas()'s own notes."""
    perfil_base["nutricion"]["ajustes_dieta"] = ["mas_proteina"]
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert "more protein" in borrador["resumen_enfoque"].lower()


def test_diet_adjustments_are_disclosed_in_spanish_too(perfil_base):
    perfil_base["nutricion"]["ajustes_dieta"] = ["mas_proteina"]
    borrador = generar_borrador_dieta_reglas(perfil_base, idioma="es")
    assert "más proteína" in borrador["resumen_enfoque"].lower()


def test_no_ajustes_dieta_is_byte_identical_to_before_the_field_existed(perfil_base):
    """A profile with no ajustes_dieta key at all (an older intake)
    behaves exactly like one with an empty list."""
    sin_campo = generar_borrador_dieta_reglas(perfil_base)
    perfil_base["nutricion"]["ajustes_dieta"] = []
    con_lista_vacia = generar_borrador_dieta_reglas(perfil_base)
    assert sin_campo == con_lista_vacia


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
    """_consejos_sinergias() is gated to "avanzado"/"tryhard" (see
    test_synergy_tips_only_shown_from_avanzado_up below) -- set explicitly
    here since this test is about the vegan-specific content, not the gate
    itself."""
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert any("iron" in consejo.lower() for consejo in borrador["consejos_sinergias"])


def test_omnivore_diet_has_no_iron_tip(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "omnivora"
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert not any("iron" in consejo.lower() for consejo in borrador["consejos_sinergias"])


def test_synergy_tips_only_shown_from_avanzado_up(perfil_base):
    """_consejos_sinergias() (general nutrient-timing/pairing tips) is
    gated to "avanzado"/"tryhard" -- unlike the client's own explicit
    soft preferences (_consejos_por_preferencias_blandas(), still active
    at every level), so this tests the gated function directly rather
    than the combined consejos_sinergias list, which perfil_base's own
    sedentary-job preference would otherwise also contribute to (see
    docs/decisiones.md)."""
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    for nivel in ("basico", "normal"):
        perfil_base["experiencia"]["nivel_compromiso"] = nivel
        assert _consejos_sinergias(perfil_base) == []
    for nivel in ("avanzado", "tryhard"):
        perfil_base["experiencia"]["nivel_compromiso"] = nivel
        assert _consejos_sinergias(perfil_base) != []


def test_consejos_sinergias_never_empty_even_with_no_active_preference(perfil_base):
    """Real bug fix: a "basico"/"normal" client with no active soft
    preference used to end up with an EMPTY consejos_sinergias list, which
    made gmail_client.obtener_texto_cliente() fall back to the first
    sentence of the generic mensaje_para_el_cliente (e.g. "aquí tienes tu
    dieta en borrador," useless as "the tip" in the email/portal). See
    _consejo_general()'s own docstring."""
    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    perfil_base["nutricion"]["inquietud_principal"] = None
    perfil_base["estilo_de_vida"] = {}
    assert _consejos_sinergias(perfil_base) == []  # confirms the gate is still what's empty
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert borrador["consejos_sinergias"] != []


def test_client_message_includes_goal_specific_starting_plan(perfil_base):
    """Direct request: "propon un plan de inicio" adapted to objetivo,
    appended after the generic MENSAJE_CLIENTE_DIETA_VARIANTES text."""
    perfil_base["objetivo"]["principal"] = "perdida_grasa"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert PLAN_INICIO_DIETA["en"]["perdida_grasa"] in borrador["mensaje_para_el_cliente"]

    borrador_es = generar_borrador_dieta_reglas(perfil_base, idioma="es")
    assert PLAN_INICIO_DIETA["es"]["perdida_grasa"] in borrador_es["mensaje_para_el_cliente"]


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
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"  # consejos_sinergias is gated, see docs/decisiones.md
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
    # Every client here shares the same objetivo, so the goal-adapted
    # PLAN_INICIO_DIETA sentence (see generar_borrador_dieta_reglas()) is
    # identical across all of them -- strip it off before checking which
    # base variant got picked, same idea as stripping the fixed greeting.
    plan_inicio = PLAN_INICIO_DIETA["en"][perfil_base["objetivo"]["principal"]]
    mensajes = set()
    for i in range(15):
        perfil_base["id_cliente"] = f"cliente_variedad_{i}"
        borrador = generar_borrador_dieta_reglas(perfil_base)
        assert borrador["mensaje_para_el_cliente"].startswith("Hi Test, ")
        cuerpo = borrador["mensaje_para_el_cliente"].removeprefix("Hi Test, ")
        assert cuerpo.endswith(f" {plan_inicio}")
        cuerpo_base = cuerpo.removesuffix(f" {plan_inicio}")
        assert cuerpo_base in MENSAJE_CLIENTE_DIETA_VARIANTES["en"]
        mensajes.add(cuerpo_base)
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


# --- Soft dietary preferences (maximal personalization) -------------------


def test_disliked_food_excluded_from_suggested_sources(perfil_base):
    perfil_base["nutricion"]["alimentos_que_no_le_gustan"] = ["broccoli"]
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert "Broccoli" not in borrador["fuentes_verdura_sugeridas"]


def test_gluten_preference_excludes_gluten_but_not_traces(perfil_base):
    perfil_base["nutricion"]["inquietud_principal"] = "quiero bajar el gluten"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert "Whole wheat bread" not in borrador["fuentes_carbohidrato_sugeridas"]
    assert "Oats" in borrador["fuentes_carbohidrato_sugeridas"]


def test_gluten_preference_note_appears_in_synergy_tips(perfil_base):
    perfil_base["nutricion"]["inquietud_principal"] = "bajar el gluten"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert any("gluten" in c.lower() for c in borrador["consejos_sinergias"])


def test_antiinflammatory_note_appears_and_is_diet_type_aware(perfil_base):
    """The tip must not name oily fish for a vegetarian/vegan client, since
    that food is never actually a candidate for them (see
    dieta_reglas.py's _consejos_por_preferencias_blandas())."""
    perfil_base["nutricion"]["inquietud_principal"] = "antiinflamatoria"
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    consejo = next(c for c in borrador["consejos_sinergias"] if "anti-inflammatory" in c.lower())
    assert "oily fish" not in consejo.lower()


def test_gut_health_preference_note_appears(perfil_base):
    perfil_base["nutricion"]["inquietud_principal"] = "gut health"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert any("gut health" in c.lower() for c in borrador["consejos_sinergias"])


def test_more_fiber_preference_note_appears(perfil_base):
    perfil_base["nutricion"]["inquietud_principal"] = "more fiber"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert any("more fiber" in c.lower() for c in borrador["consejos_sinergias"])


def test_more_iron_preference_note_appears(perfil_base):
    perfil_base["nutricion"]["inquietud_principal"] = "iron deficiency"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert any("more iron" in c.lower() for c in borrador["consejos_sinergias"])


def test_no_soft_preference_notes_for_a_clean_profile(perfil_base):
    perfil_base["estilo_de_vida"]["tipo_trabajo"] = "active outdoor work"
    borrador = generar_borrador_dieta_reglas(perfil_base)
    for palabra in ("gluten", "anti-inflammatory", "magnesium", "fiber"):
        assert not any(palabra in c.lower() for c in borrador["consejos_sinergias"])


def test_disliked_food_never_triggers_enhanced_review(perfil_base):
    """A preference, not a safety concern -- must never show up in
    advertencias_revision_humana the way a real allergy would."""
    perfil_base["nutricion"]["alimentos_que_no_le_gustan"] = ["chicken breast"]
    borrador = generar_borrador_dieta_reglas(perfil_base)
    assert borrador["advertencias_revision_humana"] == []


def test_tryhard_pushes_calories_further_from_maintenance_than_basico(perfil_base):
    perfil_base["objetivo"]["principal"] = "perdida_grasa"

    perfil_base["experiencia"]["nivel_compromiso"] = "basico"
    basico = generar_borrador_dieta_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    normal = generar_borrador_dieta_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_dieta_reglas(perfil_base)

    # perdida_grasa is a deficit (fewer kcal = more aggressive), so tryhard
    # (larger-magnitude deficit) lands BELOW normal, basico lands ABOVE it.
    assert tryhard["calorias_objetivo_kcal"] < normal["calorias_objetivo_kcal"] < basico["calorias_objetivo_kcal"]


def test_maintenance_goal_is_unaffected_by_commitment_level(perfil_base):
    """salud_general's 0% adjustment has no direction to scale -- basico/
    tryhard must not invent one."""
    perfil_base["objetivo"]["principal"] = "salud_general"
    perfil_base["experiencia"]["nivel_compromiso"] = "basico"
    basico = generar_borrador_dieta_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_dieta_reglas(perfil_base)
    assert basico["calorias_objetivo_kcal"] == tryhard["calorias_objetivo_kcal"]


def test_commitment_mode_note_appears_in_summary(perfil_base):
    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_dieta_reglas(perfil_base)
    assert "tryhard" in tryhard["resumen_enfoque"].lower()

    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    normal = generar_borrador_dieta_reglas(perfil_base)
    assert "tryhard" not in normal["resumen_enfoque"].lower()


def test_niche_foods_only_suggested_in_tryhard_mode(perfil_base):
    normal = generar_borrador_dieta_reglas(perfil_base)
    assert "Natto" not in normal["fuentes_proteina_sugeridas"]

    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_dieta_reglas(perfil_base)
    assert "Natto" in tryhard["fuentes_proteina_sugeridas"]


def test_niche_foods_not_suggested_in_avanzado_mode(perfil_base):
    """"avanzado" is deliberately NOT "tryhard" -- niche foods stay
    exclusive to tryhard, the literal ceiling of detail this project
    offers (see docs/decisiones.md)."""
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    avanzado = generar_borrador_dieta_reglas(perfil_base)
    assert "Natto" not in avanzado["fuentes_proteina_sugeridas"]


def test_supplement_tips_shown_in_tryhard_mode(perfil_base):
    normal = generar_borrador_dieta_reglas(perfil_base)
    assert not any("creatine" in c.lower() for c in normal["consejos_sinergias"])

    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_dieta_reglas(perfil_base)
    assert any("creatine" in c.lower() for c in tryhard["consejos_sinergias"])


def test_avanzado_calorie_target_matches_normal(perfil_base):
    """"avanzado" is scoped around more detailed food/supplement guidance,
    never a harder calorie push -- that's what sets it apart from
    "tryhard" (see docs/decisiones.md)."""
    perfil_base["objetivo"]["principal"] = "perdida_grasa"
    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    normal = generar_borrador_dieta_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    avanzado = generar_borrador_dieta_reglas(perfil_base)
    assert avanzado["calorias_objetivo_kcal"] == normal["calorias_objetivo_kcal"]


def test_supplement_tips_shown_in_avanzado_mode_except_caffeine(perfil_base):
    """Creatine/protein/magnesium/omega-3 are the "basic supplements" set
    "avanzado" was scoped around; caffeine (a performance/pre-workout aid,
    one level more specific) stays tryhard-only (see docs/decisiones.md)."""
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    avanzado = generar_borrador_dieta_reglas(perfil_base)
    consejos = " ".join(avanzado["consejos_sinergias"]).lower()
    assert "creatine" in consejos
    assert "protein powder" in consejos
    assert "magnesium" in consejos or "200-400 mg" in consejos
    assert "epa" in consejos or "omega" in consejos
    assert "before training" not in consejos  # the caffeine tip's own distinguishing phrase


def test_supplement_tips_skip_what_the_client_already_takes(perfil_base):
    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    perfil_base["salud"]["suplementos_actuales"] = ["Creatina"]
    borrador = generar_borrador_dieta_reglas(perfil_base)
    consejos = " ".join(borrador["consejos_sinergias"]).lower()
    assert "creatine" not in consejos
    assert "45-60 min before training" in consejos  # other tips (caffeine) still show


def test_missing_nivel_compromiso_defaults_to_normal_behavior(perfil_base):
    assert "nivel_compromiso" not in perfil_base["experiencia"]
    sin_campo = generar_borrador_dieta_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    con_normal = generar_borrador_dieta_reglas(perfil_base)
    assert sin_campo["calorias_objetivo_kcal"] == con_normal["calorias_objetivo_kcal"]


def test_commitment_mode_note_appears_in_summary_es(perfil_base):
    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_dieta_reglas(perfil_base, idioma="es")
    assert "tryhard" in tryhard["resumen_enfoque"].lower()

    perfil_base["experiencia"]["nivel_compromiso"] = "basico"
    basico = generar_borrador_dieta_reglas(perfil_base, idioma="es")
    assert "básico" in basico["resumen_enfoque"].lower()


def test_avanzado_mode_note_appears_in_summary(perfil_base):
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    en = generar_borrador_dieta_reglas(perfil_base)
    assert "advanced" in en["resumen_enfoque"].lower()

    es = generar_borrador_dieta_reglas(perfil_base, idioma="es")
    assert "avanzado" in es["resumen_enfoque"].lower()
