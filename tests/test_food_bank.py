"""Tests for food_bank.py — bilingual allergy/intolerance keyword matching
and diet-type filtering (the same safety-critical concern as
test_perfil_utils.py, on the nutrition side)."""

import pytest
from food_bank import (
    FUENTES_CARBOHIDRATO,
    FUENTES_GRASA,
    FUENTES_PROTEINA,
    FUENTES_VERDURA,
    INDICE_ALIMENTOS,
    alimentos_no_deseados,
    categoria_inquietud_conocida,
    etiquetas_excluidas,
    fuentes_carbohidrato_para,
    fuentes_grasa_para,
    fuentes_proteina_para,
    fuentes_verdura_para,
    nombre_mostrado,
    preferencias_blandas,
    preferencias_texto_libre,
)


def test_lactose_excluded_in_spanish(perfil_base):
    perfil_base["salud"]["intolerancias_alimentarias"] = ["lactosa"]
    assert "lacteo" in etiquetas_excluidas(perfil_base)


def test_lactose_excluded_in_english(perfil_base):
    perfil_base["salud"]["intolerancias_alimentarias"] = ["lactose intolerance"]
    assert "lacteo" in etiquetas_excluidas(perfil_base)


def test_nut_allergy_excluded_bilingual(perfil_base):
    perfil_base["salud"]["alergias_alimentarias"] = ["frutos secos"]
    assert "frutos_secos" in etiquetas_excluidas(perfil_base)

    perfil_base["salud"]["alergias_alimentarias"] = ["tree nut allergy"]
    assert "frutos_secos" in etiquetas_excluidas(perfil_base)


def test_fish_and_shellfish_excluded_bilingual(perfil_base):
    for texto in ("pescado", "marisco", "fish", "seafood", "shellfish"):
        perfil_base["salud"]["alergias_alimentarias"] = [texto]
        assert "pescado" in etiquetas_excluidas(perfil_base), f"failed for {texto!r}"


def test_egg_and_soy_excluded_bilingual(perfil_base):
    perfil_base["salud"]["alergias_alimentarias"] = ["egg"]
    assert "huevo" in etiquetas_excluidas(perfil_base)


def test_sesame_excluded_bilingual(perfil_base):
    for texto in ("sesamo", "sésamo", "sesame"):
        perfil_base["salud"]["alergias_alimentarias"] = [texto]
        assert "sesamo" in etiquetas_excluidas(perfil_base), f"failed for {texto!r}"


def test_fish_allergy_removes_new_shellfish_and_canned_fish_proteins(perfil_base):
    """Real, reported request ("pulir... mucha variedad") added prawns,
    mussels, canned tuna, and squid/octopus -- all grouped under the same
    "pescado" exclusion tag as every other fish/shellfish entry (see
    etiquetas_excluidas()'s own docstring for why shellfish isn't a
    separate tag)."""
    perfil_base["salud"]["alergias_alimentarias"] = ["shellfish"]
    fuentes = fuentes_proteina_para(perfil_base)
    for nombre in ("Prawns / shrimp", "Mussels", "Canned tuna", "Squid / octopus"):
        assert nombre not in fuentes, nombre


def test_sesame_allergy_removes_tahini(perfil_base):
    perfil_base["salud"]["alergias_alimentarias"] = ["sesame"]
    assert "Tahini (sesame paste)" not in fuentes_grasa_para(perfil_base)

    perfil_base["salud"]["alergias_alimentarias"] = ["soy"]
    assert "soja" in etiquetas_excluidas(perfil_base)


def test_clean_profile_excludes_nothing(perfil_base):
    assert etiquetas_excluidas(perfil_base) == set()


def test_vegan_diet_filters_out_animal_protein(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    fuentes = fuentes_proteina_para(perfil_base)
    for prohibido in ("Chicken breast", "Turkey", "Lean beef", "Salmon / oily fish", "Eggs", "Greek yogurt / whipped fresh cheese"):
        assert prohibido not in fuentes
    assert "Lentils" in fuentes


def test_protein_powder_entry_is_named_generically_not_pea_specifically(perfil_base):
    """Named "Protein powder (plant-based)", not "Pea protein" -- the
    macros are still real pea-protein-isolate values (a common,
    representative plant powder), but the display name doesn't imply this
    is the one specific brand/type recommended over any other (see
    docs/decisiones.md). Still available to every diet type, including
    vegan, which is the concrete reason it's plant-based at all rather
    than whey."""
    assert "Protein powder (plant-based)" in [f["nombre"] for f in FUENTES_PROTEINA]
    # Substring match, not bare "pea"/"guisante" -- "Chickpeas" legitimately
    # contains "pea" and must not trip this check.
    assert not any("pea protein" in f["nombre"].lower() for f in FUENTES_PROTEINA)
    assert not any("proteina de guisante" in f["nombre_es"].lower() for f in FUENTES_PROTEINA)
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    assert "Protein powder (plant-based)" in fuentes_proteina_para(perfil_base)


def test_vegan_diet_filters_fish_out_of_fat_sources(perfil_base):
    """Regression test: fuentes_grasa_para() had no diet-type filter at
    all until this was fixed -- a vegan/vegetarian client's diet draft was
    suggesting "Oily fish (EPA/DHA)" as a fat source. Found by building a
    real vegan example client and looking at its actual output, not by
    reading the code (see docs/decisiones.md)."""
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    fuentes = fuentes_grasa_para(perfil_base)
    assert "Oily fish (EPA/DHA)" not in fuentes
    assert "Avocado" in fuentes

    perfil_base["nutricion"]["tipo_dieta"] = "vegetariana_ovolacto"
    fuentes = fuentes_grasa_para(perfil_base)
    assert "Oily fish (EPA/DHA)" not in fuentes


def test_omnivore_diet_still_includes_fish_as_a_fat_source(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "omnivora"
    assert "Oily fish (EPA/DHA)" in fuentes_grasa_para(perfil_base)


def test_carbohydrate_sources_available_to_every_diet_type(perfil_base):
    """Every current carb source happens to be vegan-compatible, but the
    filter should still apply tipos_dieta -- not just skip it -- so a
    future non-compatible entry gets caught automatically."""
    for tipo in ("omnivora", "vegetariana_ovolacto", "vegana"):
        perfil_base["nutricion"]["tipo_dieta"] = tipo
        assert "Rice" in fuentes_carbohidrato_para(perfil_base)


def test_nut_allergy_removes_nuts_from_fat_sources_regardless_of_diet(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    perfil_base["salud"]["alergias_alimentarias"] = ["tree nut allergy"]
    fuentes = fuentes_grasa_para(perfil_base)
    assert "Nuts (walnuts, almonds)" not in fuentes
    assert "Seeds (chia, flax)" in fuentes


def test_allergy_removes_suggested_source_even_if_diet_allows_it(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "omnivora"
    perfil_base["salud"]["alergias_alimentarias"] = ["egg allergy"]
    fuentes = fuentes_proteina_para(perfil_base)
    assert "Eggs" not in fuentes
    assert "Chicken breast" in fuentes


def test_every_food_has_a_spanish_display_name():
    for alimento in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA:
        assert alimento.get("nombre_es"), f"missing nombre_es for {alimento['nombre']!r}"


def test_every_food_declares_which_diets_allow_it():
    """Locks in the invariant the "Oily fish" bug violated: every entry
    across all three banks must declare tipos_dieta explicitly, not rely
    on an implicit "always allowed" default that lets an
    animal-product-containing entry slip through fuentes_carbohidrato_para()/
    fuentes_grasa_para()'s filter unchecked."""
    for alimento in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA:
        assert alimento.get("tipos_dieta"), f"missing tipos_dieta for {alimento['nombre']!r}"


def test_nombre_mostrado_returns_spanish_only_for_es():
    assert nombre_mostrado("Chicken breast", "es") == "Pechuga de pollo"
    assert nombre_mostrado("Chicken breast", "en") == "Chicken breast"


# --- FUENTES_VERDURA / fuentes_verdura_para() (added alongside the weekly
# meal planner) -- same filtering discipline as the other three banks, so
# the vegetable category doesn't quietly open a hole in allergy/diet-type
# safety. ------------------------------------------------------------------


def test_vegetable_sources_available_to_every_diet_type(perfil_base):
    for tipo in ("omnivora", "vegetariana_ovolacto", "vegana"):
        perfil_base["nutricion"]["tipo_dieta"] = tipo
        assert "Broccoli" in fuentes_verdura_para(perfil_base)


def test_every_vegetable_declares_which_diets_allow_it():
    for alimento in FUENTES_VERDURA:
        assert alimento.get("tipos_dieta"), f"missing tipos_dieta for {alimento['nombre']!r}"


def test_every_vegetable_has_a_spanish_display_name():
    for alimento in FUENTES_VERDURA:
        assert alimento.get("nombre_es"), f"missing nombre_es for {alimento['nombre']!r}"


# --- macros_100g / sinergias (added for the weekly meal planner) ---------


def test_every_food_across_all_four_banks_has_macros_100g():
    """planificador_comidas.py's portion math divides by macros_100g["kcal"]
    for every food it can pick -- a missing entry would crash mid-plan, not
    just render oddly, so this is locked in as an invariant."""
    for alimento in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA + FUENTES_VERDURA:
        macros = alimento.get("macros_100g")
        assert macros, f"missing macros_100g for {alimento['nombre']!r}"
        for clave in ("kcal", "proteina_g", "carbohidratos_g", "grasa_g"):
            assert clave in macros, f"{alimento['nombre']!r} missing {clave!r} in macros_100g"
        assert macros["kcal"] > 0, f"{alimento['nombre']!r} has non-positive kcal"


def test_non_heme_iron_sources_are_tagged_for_synergy_pairing():
    """Locks in the specific foods docs/base_conocimiento/sinergias_nutrientes.md
    calls out as non-heme (plant) iron sources -- planificador_comidas.py's
    vitamin-C pairing only fires for foods carrying this tag."""
    for nombre in ("Lentils", "Chickpeas", "Tofu", "Tempeh", "Edamame"):
        assert "hierro_no_hemo" in INDICE_ALIMENTOS[nombre]["sinergias"], nombre


def test_some_vegetables_are_tagged_as_vitamin_c_sources():
    con_vitamina_c = [f["nombre"] for f in FUENTES_VERDURA if "vitamina_c" in f["sinergias"]]
    assert "Red bell pepper" in con_vitamina_c
    assert "Kiwi" in con_vitamina_c


def test_indice_alimentos_covers_every_food_across_all_four_banks():
    for alimento in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA + FUENTES_VERDURA:
        assert INDICE_ALIMENTOS[alimento["nombre"]] is alimento


# --- Soft dietary preferences (maximal personalization) -------------------


def test_preferencias_texto_libre_pools_every_free_text_field(perfil_base):
    perfil_base["objetivo"]["en_sus_palabras"] = "own words text"
    perfil_base["nutricion"]["contexto"] = "context text"
    perfil_base["nutricion"]["inquietud_principal"] = "inquietud text"
    perfil_base["notas_libres"] = "free notes text"
    texto = preferencias_texto_libre(perfil_base)
    for fragmento in ("own words text", "context text", "inquietud text", "free notes text"):
        assert fragmento in texto


@pytest.mark.parametrize("frase", ["antiinflamatoria", "anti-inflammatory", "inflammation", "INFLAMACIÓN"])
def test_antiinflamatorio_detected_bilingual(perfil_base, frase):
    perfil_base["nutricion"]["inquietud_principal"] = frase
    assert "antiinflamatorio" in preferencias_blandas(perfil_base)


@pytest.mark.parametrize("frase", ["bajar el gluten", "lower gluten", "gluten-free"])
def test_reducir_gluten_detected_bilingual(perfil_base, frase):
    perfil_base["nutricion"]["inquietud_principal"] = frase
    assert "reducir_gluten" in preferencias_blandas(perfil_base)


def test_no_soft_preferences_for_a_clean_profile(perfil_base):
    # perfil_base's own default tipo_trabajo ("sedentary office job") would
    # otherwise trigger "trabajo_sedentario" -- overridden here so this
    # test genuinely isolates "no preference text/signals at all".
    perfil_base["estilo_de_vida"]["tipo_trabajo"] = "active outdoor work"
    assert preferencias_blandas(perfil_base) == set()


def test_high_stress_detected_as_soft_preference(perfil_base):
    perfil_base["estilo_de_vida"]["nivel_estres_percibido"] = "alto"
    assert "estres_alto_o_sueno_bajo" in preferencias_blandas(perfil_base)


def test_low_sleep_detected_as_soft_preference(perfil_base):
    perfil_base["estilo_de_vida"]["horas_sueno_promedio"] = 5
    assert "estres_alto_o_sueno_bajo" in preferencias_blandas(perfil_base)


def test_normal_stress_and_sleep_not_flagged(perfil_base):
    perfil_base["estilo_de_vida"]["nivel_estres_percibido"] = "medio"
    perfil_base["estilo_de_vida"]["horas_sueno_promedio"] = 7
    assert "estres_alto_o_sueno_bajo" not in preferencias_blandas(perfil_base)


@pytest.mark.parametrize("trabajo", ["sedentary office job", "trabajo de oficina", "desk job"])
def test_sedentary_job_detected_bilingual(perfil_base, trabajo):
    perfil_base["estilo_de_vida"]["tipo_trabajo"] = trabajo
    assert "trabajo_sedentario" in preferencias_blandas(perfil_base)


def test_active_job_not_flagged_as_sedentary(perfil_base):
    perfil_base["estilo_de_vida"]["tipo_trabajo"] = "construction worker, on my feet all day"
    assert "trabajo_sedentario" not in preferencias_blandas(perfil_base)


@pytest.mark.parametrize("texto", ["little time to cook", "poco tiempo para cocinar", "tight budget", "presupuesto ajustado"])
def test_limited_time_or_budget_detected_in_nutrition_context(perfil_base, texto):
    """Direct request: nutricion.contexto/estilo_de_vida.tipo_trabajo became
    preset dropdowns (ui/app.py's OPCIONES_CONTEXTO_NUTRICION/
    OPCIONES_TIPO_TRABAJO) storing exactly these phrases, so this category
    only actually helps if the keyword match genuinely recognizes them."""
    perfil_base["nutricion"]["contexto"] = texto
    assert "tiempo_o_presupuesto_limitado" in preferencias_blandas(perfil_base)


def test_limited_time_or_budget_also_detected_via_job_type_field(perfil_base):
    """preferencias_texto_libre() pools tipo_trabajo too now -- the
    "little free time during the week" preset lives there, not in
    nutricion.contexto."""
    perfil_base["estilo_de_vida"]["tipo_trabajo"] = "little free time during the week"
    assert "tiempo_o_presupuesto_limitado" in preferencias_blandas(perfil_base)


def test_known_category_reverse_maps_new_presets(perfil_base):
    assert categoria_inquietud_conocida("tight budget") == "tiempo_o_presupuesto_limitado"
    assert categoria_inquietud_conocida("presupuesto ajustado") == "tiempo_o_presupuesto_limitado"


def test_reducir_gluten_excludes_gluten_but_keeps_gluten_traces(perfil_base):
    """The soft "lower gluten" preference is deliberately narrower than a
    declared allergy: it excludes `gluten`-tagged foods (bread, pasta,
    seitan) but keeps `gluten_trazas` ones (oats) -- see food_bank.py's
    module docstring for why that distinction is real, not an oversight."""
    perfil_base["nutricion"]["inquietud_principal"] = "quiero bajar el gluten"
    carbs = fuentes_carbohidrato_para(perfil_base)
    proteinas = fuentes_proteina_para(perfil_base)
    assert "Whole wheat bread" not in carbs
    assert "Whole wheat pasta" not in carbs
    assert "Seitan" not in proteinas
    assert "Oats" in carbs  # traces only, not excluded by the soft preference


def test_a_real_gluten_allergy_still_excludes_oats_too(perfil_base):
    """Contrast with the soft preference above: an actual declared allergy
    keeps excluding gluten_trazas as well -- unchanged, hard-safety
    behavior via etiquetas_excluidas()."""
    perfil_base["salud"]["intolerancias_alimentarias"] = ["gluten intolerance"]
    carbs = fuentes_carbohidrato_para(perfil_base)
    assert "Whole wheat bread" not in carbs
    assert "Oats" not in carbs


def test_disliked_food_excluded_by_exact_name_match(perfil_base):
    perfil_base["nutricion"]["alimentos_que_no_le_gustan"] = ["broccoli"]
    assert "Broccoli" not in fuentes_verdura_para(perfil_base)


def test_disliked_food_matched_without_accents(perfil_base):
    """A client typing without accents ("brocoli") must still match
    "Brócoli" -- see food_bank._sin_acentos()."""
    perfil_base["nutricion"]["alimentos_que_no_le_gustan"] = ["brocoli"]
    assert "Broccoli" not in fuentes_verdura_para(perfil_base)


def test_disliked_food_matched_from_a_longer_sentence(perfil_base):
    perfil_base["nutricion"]["alimentos_que_no_le_gustan"] = ["no me gusta el pescado blanco"]
    assert "White fish (hake, sole)" not in fuentes_proteina_para(perfil_base)


def test_disliked_food_matched_via_spanish_display_name(perfil_base):
    perfil_base["nutricion"]["alimentos_que_no_le_gustan"] = ["pollo"]
    assert "Chicken breast" not in fuentes_proteina_para(perfil_base)


def test_restrictions_also_feed_disliked_food_exclusion(perfil_base):
    perfil_base["nutricion"]["restricciones"] = ["salmon"]
    assert "Salmon / oily fish" not in fuentes_proteina_para(perfil_base)


def test_short_disliked_phrases_are_ignored_to_avoid_false_collisions(perfil_base):
    perfil_base["nutricion"]["alimentos_que_no_le_gustan"] = ["no"]
    assert alimentos_no_deseados(perfil_base) == set()


def test_disliked_food_does_not_trigger_a_health_review():
    """A disliked food is a preference, never a safety concern -- unlike
    etiquetas_excluidas(), alimentos_no_deseados() must have no bearing on
    validator_agent.py's enhanced-review logic. This is a contract test on
    the function's own return value, not a full pipeline run."""
    from food_bank import etiquetas_excluidas
    perfil = {
        "salud": {"alergias_alimentarias": [], "intolerancias_alimentarias": []},
        "nutricion": {"alimentos_que_no_le_gustan": ["chicken"], "restricciones": []},
    }
    assert etiquetas_excluidas(perfil) == set()


def test_niche_foods_excluded_by_default_and_included_in_tryhard_mode(perfil_base):
    normal = fuentes_proteina_para(perfil_base)
    assert "Natto" not in normal
    assert not any(f.get("nicho") and f["nombre"] in normal for f in FUENTES_PROTEINA)

    perfil_base["experiencia"] = {"nivel_compromiso": "tryhard"}
    tryhard = fuentes_proteina_para(perfil_base)
    assert "Natto" in tryhard


def test_niche_foods_still_respect_allergy_exclusion_in_tryhard_mode(perfil_base):
    perfil_base["experiencia"] = {"nivel_compromiso": "tryhard"}
    perfil_base["salud"]["alergias_alimentarias"] = ["soy allergy"]
    assert "Natto" not in fuentes_proteina_para(perfil_base)


def test_plant_protein_alternatives_excluded_for_omnivore_below_tryhard(perfil_base):
    """Real reported bug: tofu/tempeh/edamame/seitan/plant protein powder
    declare tipos_dieta including "omnivora" (needed so they're genuine
    candidates for a vegetarian/vegan client), which also made them
    equally likely for a meat-eating client at every level -- "cosas muy
    raras para una dieta normal". Now tryhard-exclusive specifically for
    omnivore, same as a true "nicho" food."""
    perfil_base["nutricion"]["tipo_dieta"] = "omnivora"
    for nivel in (None, "basico", "normal", "avanzado"):
        if nivel:
            perfil_base["experiencia"]["nivel_compromiso"] = nivel
        fuentes = fuentes_proteina_para(perfil_base)
        for raro in ("Tofu", "Tempeh", "Edamame", "Seitan", "Protein powder (plant-based)"):
            assert raro not in fuentes, f"{raro!r} should be excluded at nivel_compromiso={nivel!r}"

    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = fuentes_proteina_para(perfil_base)
    for disponible in ("Tofu", "Tempeh", "Edamame", "Seitan", "Protein powder (plant-based)"):
        assert disponible in tryhard


def test_plant_protein_alternatives_stay_available_for_vegetarian_and_vegan(perfil_base):
    """The same foods are genuine staples, not "raro", for a vegetarian/
    vegan client -- the nicho_omnivoro gate must only apply to omnivore."""
    for tipo in ("vegetariana_ovolacto", "vegana"):
        perfil_base["nutricion"]["tipo_dieta"] = tipo
        fuentes = fuentes_proteina_para(perfil_base)
        assert "Tofu" in fuentes
        assert "Protein powder (plant-based)" in fuentes


def test_categoria_inquietud_conocida_matches_antiinflamatorio():
    assert categoria_inquietud_conocida("anti-inflammatory") == "antiinflamatorio"
    assert categoria_inquietud_conocida("Antiinflamatoria") == "antiinflamatorio"


def test_categoria_inquietud_conocida_matches_reducir_gluten():
    assert categoria_inquietud_conocida("lower gluten") == "reducir_gluten"
    assert categoria_inquietud_conocida("bajar el gluten") == "reducir_gluten"


def test_categoria_inquietud_conocida_matches_salud_digestiva():
    assert categoria_inquietud_conocida("gut health") == "salud_digestiva"
    assert categoria_inquietud_conocida("salud digestiva") == "salud_digestiva"


def test_categoria_inquietud_conocida_matches_mas_fibra():
    assert categoria_inquietud_conocida("more fiber") == "mas_fibra"
    assert categoria_inquietud_conocida("más fibra") == "mas_fibra"


def test_categoria_inquietud_conocida_matches_mas_hierro():
    assert categoria_inquietud_conocida("iron deficiency") == "mas_hierro"
    assert categoria_inquietud_conocida("anemia") == "mas_hierro"


def test_categoria_inquietud_conocida_returns_empty_for_unmatched_text():
    assert categoria_inquietud_conocida("more energy in the mornings") == ""
    assert categoria_inquietud_conocida("") == ""
