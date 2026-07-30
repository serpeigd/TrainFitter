"""Tests for food_bank.py — bilingual allergy/intolerance keyword matching
and diet-type filtering (the same safety-critical concern as
test_perfil_utils.py, on the nutrition side)."""

from food_bank import FUENTES_CARBOHIDRATO, FUENTES_GRASA, FUENTES_PROTEINA, etiquetas_excluidas, fuentes_proteina_para, nombre_mostrado


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


def test_allergy_removes_suggested_source_even_if_diet_allows_it(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "omnivora"
    perfil_base["salud"]["alergias_alimentarias"] = ["egg allergy"]
    fuentes = fuentes_proteina_para(perfil_base)
    assert "Eggs" not in fuentes
    assert "Chicken breast" in fuentes


def test_every_food_has_a_spanish_display_name():
    for alimento in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA:
        assert alimento.get("nombre_es"), f"missing nombre_es for {alimento['nombre']!r}"


def test_nombre_mostrado_returns_spanish_only_for_es():
    assert nombre_mostrado("Chicken breast", "es") == "Pechuga de pollo"
    assert nombre_mostrado("Chicken breast", "en") == "Chicken breast"
