"""Tests for food_bank.py — bilingual allergy/intolerance keyword matching
and diet-type filtering (the same safety-critical concern as
test_perfil_utils.py, on the nutrition side)."""

from food_bank import (
    FUENTES_CARBOHIDRATO,
    FUENTES_GRASA,
    FUENTES_PROTEINA,
    FUENTES_VERDURA,
    INDICE_ALIMENTOS,
    etiquetas_excluidas,
    fuentes_carbohidrato_para,
    fuentes_grasa_para,
    fuentes_proteina_para,
    fuentes_verdura_para,
    nombre_mostrado,
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
