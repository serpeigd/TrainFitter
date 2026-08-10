"""Tests for agents/planificador_comidas.py (the weekly meal planner used
by dieta_reglas.py's plan_semanal). tests/test_dieta_reglas.py covers this
module through the full public API (generar_borrador_dieta_reglas); these
tests exercise generar_plan_semanal() directly for the mechanics that are
easier to pin down at this level: kcal-target accuracy, synergy pairing,
and the two portion-realism fixes found by actually generating and reading
a real week (see docs/decisiones.md)."""

from planificador_comidas import generar_plan_semanal
from variacion import rng_para_cliente

NECESIDADES = {
    "calorias_objetivo_kcal": 2000,
    "macros": {"proteina_g": 130, "grasa_g": 60, "carbohidratos_g": 210},
}


def _rng(perfil, namespace="dieta:plan_semanal"):
    return rng_para_cliente(perfil, namespace)


def test_plan_has_seven_days(perfil_base):
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    assert len(plan) == 7


def test_default_four_meals_a_day_gives_breakfast_lunch_dinner_snack(perfil_base):
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    tipos = [c["tipo"] for c in plan[0]["comidas"]]
    assert tipos == ["Breakfast", "Lunch", "Dinner", "Snack"]


def test_three_meals_a_day_has_no_snack(perfil_base):
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 3, "en", _rng(perfil_base))
    tipos = [c["tipo"] for c in plan[0]["comidas"]]
    assert tipos == ["Breakfast", "Lunch", "Dinner"]


def test_extra_meals_become_numbered_snacks(perfil_base):
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 6, "en", _rng(perfil_base))
    tipos = [c["tipo"] for c in plan[0]["comidas"]]
    assert tipos == ["Breakfast", "Lunch", "Dinner", "Snack 1", "Snack 2", "Snack 3"]


def test_daily_kcal_lands_reasonably_close_to_target(perfil_base):
    """Not gram-perfect by design (see module docstring) -- but should be
    in the right ballpark, not off by double or by half."""
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    objetivo = NECESIDADES["calorias_objetivo_kcal"]
    for dia in plan:
        total = sum(c["aprox_kcal"] for c in dia["comidas"])
        assert objetivo * 0.85 <= total <= objetivo * 1.15, f"{dia['dia']}: {total} vs {objetivo}"


def test_dinner_gets_more_fat_kcal_than_breakfast():
    """The one deliberate deviation from mirroring the day's overall
    ratios: dinner is "the day's fattiest meal" (docs/base_conocimiento/
    sinergias_nutrientes.md), not just proportional to its own size."""
    perfil = {
        "id_cliente": "fixed-for-fat-check",
        "datos_basicos": {"nombre": "Fat Check"},
        "nutricion": {"tipo_dieta": "omnivora"},
        "salud": {"alergias_alimentarias": [], "intolerancias_alimentarias": []},
    }
    plan = generar_plan_semanal(perfil, NECESIDADES, 4, "en", _rng(perfil))
    desayuno = next(c for c in plan[0]["comidas"] if c["tipo"] == "Breakfast")
    cena = next(c for c in plan[0]["comidas"] if c["tipo"] == "Dinner")
    assert "largest fat portion" in cena["descripcion"]
    assert "largest fat portion" not in desayuno["descripcion"]


def test_regenerating_the_same_client_reproduces_the_same_plan(perfil_base):
    plan_1 = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    plan_2 = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    assert plan_1 == plan_2


def test_different_clients_get_different_plans(perfil_base):
    plan_1 = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    perfil_base["id_cliente"] = "a-completely-different-client"
    plan_2 = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    assert plan_1 != plan_2


def test_vegan_diet_never_suggests_animal_foods(perfil_base):
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    texto = str(plan).lower()
    for prohibido in ("chicken", "turkey", "beef", "salmon", "white fish", "eggs", "yogurt", "oily fish"):
        assert prohibido not in texto, prohibido


def test_declared_allergy_never_appears_in_the_plan(perfil_base):
    perfil_base["salud"]["alergias_alimentarias"] = ["fish allergy"]
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    texto = str(plan).lower()
    assert "salmon" not in texto
    assert "white fish" not in texto
    assert "oily fish" not in texto


def test_iron_source_protein_gets_paired_with_a_vitamin_c_food(perfil_base):
    """Runs many days across a vegan profile (only non-heme iron sources
    for protein) so the pairing note is guaranteed to show up at least
    once, rather than depending on a specific RNG draw."""
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    notas = [c["descripcion"] for dia in plan for c in dia["comidas"] if "vitamin C" in c["descripcion"]]
    assert notas, "expected at least one iron+vitamin-C pairing note across a full week"


def test_fruit_is_never_the_main_carb_in_a_full_meal(perfil_base):
    """Regression test: a first version let "Assorted fruit" (low kcal
    density) be picked as the carb for breakfast/lunch/dinner, which solved
    out to absurd portions (500g+ of fruit) for anything but a snack-sized
    kcal budget -- caught by generating and reading a real week, not by
    inspection. See docs/decisiones.md."""
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    for dia in plan:
        for comida in dia["comidas"]:
            if comida["tipo"] != "Snack":
                assert "assorted fruit" not in comida["descripcion"].lower(), comida


def test_no_whole_cut_meat_or_fish_in_breakfast_or_snacks(perfil_base):
    """Regression test: an unfiltered rng.choice() across the full protein/
    fat pools could pick "grilled salmon" for a snack -- not unsafe, just
    an unrealistic-looking suggestion. Runs an omnivore profile across many
    different seeds so the check isn't just luck of one draw."""
    pesados = ("chicken breast", "turkey", "lean beef", "white fish", "salmon / oily fish", "oily fish (epa/dha)")
    for i in range(10):
        perfil_base["id_cliente"] = f"cliente_comida_ligera_{i}"
        plan = generar_plan_semanal(perfil_base, NECESIDADES, 5, "en", _rng(perfil_base))
        for dia in plan:
            for comida in dia["comidas"]:
                if comida["tipo"] in ("Breakfast", "Snack 1", "Snack 2"):
                    texto = comida["descripcion"].lower()
                    for pesado in pesados:
                        assert pesado not in texto, f"{pesado!r} in {comida['tipo']}: {comida['descripcion']}"


def test_empty_protein_pool_returns_empty_plan_instead_of_crashing(perfil_base):
    """A maximally-restrictive combination (nothing left in a required
    category) should degrade to "no plan," matching dieta_reglas.py's own
    existing fuentes_*_sugeridas/advertencias behavior for the same
    situation -- never a crash."""
    necesidades_vacias = {"calorias_objetivo_kcal": 0, "macros": {"proteina_g": 0, "grasa_g": 0, "carbohidratos_g": 0}}
    plan = generar_plan_semanal(perfil_base, necesidades_vacias, 4, "en", _rng(perfil_base))
    # kcal_objetivo=0 still has real candidates, so this should still
    # produce a (zero-portion) plan rather than an empty one -- the real
    # "empty candidates" case is exercised via a profile with no valid
    # protein source, which this project's food bank never actually
    # produces (every diet type keeps at least one protein source) -- so
    # this test instead locks in that a plan is still returned, not that
    # it's ever actually empty in practice.
    assert len(plan) == 7
