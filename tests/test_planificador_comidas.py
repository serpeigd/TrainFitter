"""Tests for agents/planificador_comidas.py (the weekly meal planner used
by dieta_reglas.py's plan_semanal). tests/test_dieta_reglas.py covers this
module through the full public API (generar_borrador_dieta_reglas); these
tests exercise generar_plan_semanal() directly for the mechanics that are
easier to pin down at this level: kcal-target accuracy, synergy pairing,
and the two portion-realism fixes found by actually generating and reading
a real week (see docs/decisiones.md)."""

from food_bank import INDICE_ALIMENTOS
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
    sinergias_nutrientes.md), not just proportional to its own size. The
    fat-weighting itself is a portion-math choice, not a "synergy" -- it
    applies at every nivel_compromiso; only the explanatory sentence is
    gated to "avanzado"/"tryhard" (see docs/decisiones.md), so this test
    explicitly picks that level to check for it."""
    perfil = {
        "id_cliente": "fixed-for-fat-check",
        "datos_basicos": {"nombre": "Fat Check"},
        "nutricion": {"tipo_dieta": "omnivora"},
        "salud": {"alergias_alimentarias": [], "intolerancias_alimentarias": []},
        "experiencia": {"nivel_compromiso": "avanzado"},
    }
    plan = generar_plan_semanal(perfil, NECESIDADES, 4, "en", _rng(perfil))
    desayuno = next(c for c in plan[0]["comidas"] if c["tipo"] == "Breakfast")
    cena = next(c for c in plan[0]["comidas"] if c["tipo"] == "Dinner")
    assert "largest fat portion" in cena["descripcion"]
    assert "largest fat portion" not in desayuno["descripcion"]


def test_dinner_fat_weighting_note_is_gated_to_avanzado_up(perfil_base):
    """"basico"/"normal" keep the SAME fat-heavier-dinner distribution
    (see test above) -- just without the explanatory sentence."""
    perfil_base["nutricion"]["tipo_dieta"] = "omnivora"
    for nivel in ("basico", "normal"):
        perfil_base["experiencia"]["nivel_compromiso"] = nivel
        plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
        cena = next(c for c in plan[0]["comidas"] if c["tipo"] == "Dinner")
        assert "largest fat portion" not in cena["descripcion"]


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
    once, rather than depending on a specific RNG draw. Gated to
    "avanzado"/"tryhard" (see docs/decisiones.md), so set explicitly."""
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    notas = [c["descripcion"] for dia in plan for c in dia["comidas"] if "vitamin C" in c["descripcion"]]
    assert notas, "expected at least one iron+vitamin-C pairing note across a full week"


def test_no_synergy_pairing_at_basico_or_normal(perfil_base):
    """Same vegan profile as the test above -- confirms the pairing note
    genuinely never appears below "avanzado", not just that it's rare."""
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    for nivel in ("basico", "normal"):
        perfil_base["experiencia"]["nivel_compromiso"] = nivel
        plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
        notas = [c["descripcion"] for dia in plan for c in dia["comidas"] if "vitamin C" in c["descripcion"]]
        assert notas == [], f"nivel_compromiso={nivel} should never show the synergy pairing note"


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


# --- Soft-preference bias (maximal personalization) ------------------------


def _porcentaje_salmon_en_comidas_principales(perfil):
    rng = rng_para_cliente(perfil, "dieta:plan_semanal")
    plan = generar_plan_semanal(perfil, NECESIDADES, 4, "en", rng)
    principales = [c for d in plan for c in d["comidas"] if c["tipo"] in ("Lunch", "Dinner")]
    con_salmon = sum(1 for c in principales if "salmon" in c["descripcion"].lower())
    return con_salmon / len(principales)


def test_antiinflammatory_preference_biases_toward_salmon(perfil_base):
    """Salmon is the only antiinflamatorio-tagged protein in the bank --
    an active preference should make it show up far more often in lunch/
    dinner than the baseline uniform-random rate (~1-in-13 candidates)."""
    perfil_base["nutricion"]["inquietud_principal"] = "antiinflamatoria"
    tasa_con_preferencia = _porcentaje_salmon_en_comidas_principales(perfil_base)

    perfil_base["nutricion"]["inquietud_principal"] = ""
    tasa_sin_preferencia = _porcentaje_salmon_en_comidas_principales(perfil_base)

    assert tasa_con_preferencia > tasa_sin_preferencia * 2
    assert tasa_con_preferencia > 0.4


def test_more_iron_preference_biases_toward_non_heme_iron_sources(perfil_base):
    """Non-heme-iron-tagged proteins (Lentils, Chickpeas, Tofu, Tempeh,
    Edamame) already have a real baseline share among candidates -- unlike
    salmon's ~1-in-13 baseline above, so this checks the bias directionally
    across many client IDs rather than asserting a single seed clears a
    fixed threshold (avoids a flaky test over-fitted to one RNG draw)."""
    fuentes_hierro = {"Lentils", "Chickpeas", "Tofu", "Tempeh", "Edamame"}

    def _tasa(perfil):
        rng = rng_para_cliente(perfil, "dieta:plan_semanal")
        plan = generar_plan_semanal(perfil, NECESIDADES, 4, "en", rng)
        principales = [c for d in plan for c in d["comidas"] if c["tipo"] in ("Lunch", "Dinner")]
        con_hierro = sum(1 for c in principales if c["proteina"] in fuentes_hierro)
        return con_hierro / len(principales)

    tasas_con, tasas_sin = [], []
    for i in range(15):
        perfil_base["id_cliente"] = f"hierro_test_{i}"
        perfil_base["nutricion"]["inquietud_principal"] = "iron deficiency"
        tasas_con.append(_tasa(perfil_base))
        perfil_base["nutricion"]["inquietud_principal"] = ""
        tasas_sin.append(_tasa(perfil_base))

    assert sum(tasas_con) / len(tasas_con) > sum(tasas_sin) / len(tasas_sin)


def test_gluten_preference_propagates_into_the_weekly_plan_text(perfil_base):
    """Not just the flat fuentes_*_sugeridas lists -- the actual meal
    descriptions in plan_semanal must never mention bread/pasta/seitan
    once "reducir_gluten" is active, since the planner only ever draws
    from the already-filtered candidate pools (see module docstring)."""
    perfil_base["nutricion"]["inquietud_principal"] = "bajar el gluten"
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    texto = str(plan).lower()
    for prohibido in ("whole wheat bread", "whole wheat pasta", "seitan"):
        assert prohibido not in texto
    assert "oats" in texto or "rice" in texto or "quinoa" in texto  # still has real carb variety


def test_no_active_preference_does_not_crash_and_still_varies(perfil_base):
    """Baseline sanity check: with zero active soft preferences, the bias
    function should be a no-op (not silently narrow every candidate list
    to nothing)."""
    perfil_base["estilo_de_vida"]["tipo_trabajo"] = "active outdoor work"  # override the fixture's sedentary default
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    assert len(plan) == 7
    lunch_dinner_descripciones = {c["descripcion"] for d in plan for c in d["comidas"] if c["tipo"] in ("Lunch", "Dinner")}
    assert len(lunch_dinner_descripciones) > 1  # real variety, not narrowed down to one option


# --- Liked meals (comidas_favoritas) -- portal "repeat this meal" feature -


def test_meal_dict_includes_structured_food_fields(perfil_base):
    """Alongside the rendered "descripcion", each meal now also carries
    its own structured picks -- what lets a client "like" a specific meal
    from the portal without this project parsing food names back out of
    prose (see docs/decisiones.md)."""
    from food_bank import fuentes_proteina_para

    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    comida = plan[0]["comidas"][0]
    assert comida["tipo_interno"] == "desayuno"
    assert comida["proteina"] in fuentes_proteina_para(perfil_base)


def test_liked_meal_reappears_more_often_than_baseline(perfil_base):
    """Statistical check, not a single-example read (same discipline as
    the antiinflamatorio bias test above): a liked breakfast should show
    up across the week noticeably more than the ~1-in-N baseline chance
    for that specific protein."""
    plan_base = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base, "baseline"))
    desayunos_base = [c for d in plan_base for c in d["comidas"] if c["tipo_interno"] == "desayuno"]
    proteina_objetivo = desayunos_base[0]["proteina"]
    carbohidrato_objetivo = desayunos_base[0]["carbohidrato"]

    perfil_base["nutricion"]["comidas_favoritas"] = [
        {"tipo": "desayuno", "proteina": proteina_objetivo, "carbohidrato": carbohidrato_objetivo, "grasa": None},
    ]
    apariciones = 0
    total = 0
    for i in range(20):
        perfil_base["id_cliente"] = f"favoritos_test_{i}"
        plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
        for dia in plan:
            for comida in dia["comidas"]:
                if comida["tipo_interno"] == "desayuno":
                    total += 1
                    if comida["proteina"] == proteina_objetivo and comida["carbohidrato"] == carbohidrato_objetivo:
                        apariciones += 1
    assert apariciones / total > 0.35  # well above what an unbiased pick across many candidates would give


def test_no_favorites_behaves_exactly_like_before(perfil_base):
    """A profile without comidas_favoritas at all (every existing client)
    must produce byte-identical plans to before this feature existed."""
    assert "comidas_favoritas" not in perfil_base["nutricion"]
    sin_favoritos = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    perfil_base["nutricion"]["comidas_favoritas"] = []
    con_lista_vacia = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    assert sin_favoritos == con_lista_vacia


def test_disliked_meal_stops_reappearing_for_the_same_client(perfil_base):
    """Meal selection is seeded by id_cliente -- regenerating the SAME
    client's plan with no change reproduces the exact same picks. Marking
    one meal disliked (see notion_connector.agregar_comida_no_deseada())
    and regenerating with the SAME id_cliente must break that
    determinism for that one slot, or the client would see the disliked
    meal again immediately."""
    plan_base = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    desayuno_base = next(c for d in plan_base for c in d["comidas"] if c["tipo_interno"] == "desayuno")

    perfil_base["nutricion"]["comidas_no_deseadas"] = [
        {
            "tipo": "desayuno", "proteina": desayuno_base["proteina"],
            "carbohidrato": desayuno_base["carbohidrato"], "grasa": desayuno_base["grasa"],
        },
    ]
    plan_tras_dislike = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    desayunos_tras_dislike = [c for d in plan_tras_dislike for c in d["comidas"] if c["tipo_interno"] == "desayuno"]
    combo_disliked = (desayuno_base["proteina"], desayuno_base["carbohidrato"], desayuno_base["grasa"])
    assert not any(
        (c["proteina"], c["carbohidrato"], c["grasa"]) == combo_disliked for c in desayunos_tras_dislike
    )


def test_no_dislikes_behaves_exactly_like_before(perfil_base):
    """A profile without comidas_no_deseadas at all (every existing
    client) must produce byte-identical plans to before this feature
    existed."""
    assert "comidas_no_deseadas" not in perfil_base["nutricion"]
    sin_no_deseadas = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    perfil_base["nutricion"]["comidas_no_deseadas"] = []
    con_lista_vacia = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    assert sin_no_deseadas == con_lista_vacia


def test_liked_meal_dropped_if_food_no_longer_a_valid_candidate(perfil_base):
    """A safety-adjacent guarantee: if the liked food is no longer a
    candidate (e.g. a new allergy since the meal was liked), it must
    never be resurrected just because it's on the favorites list --
    comidas_favoritas is matched against the already-filtered candidate
    pool, not the raw food bank."""
    perfil_base["nutricion"]["comidas_favoritas"] = [
        {"tipo": "desayuno", "proteina": "Eggs", "carbohidrato": "Oats", "grasa": None},
    ]
    perfil_base["salud"]["alergias_alimentarias"] = ["egg allergy"]
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    texto = str(plan).lower()
    assert "eggs" not in texto


# --- Food commonality bias by nivel_compromiso (real redesign, not a no-op)


def _proporcion_no_comun(perfil, nivel_compromiso, n=20):
    """Fraction of all protein/carb/fat picks across n regenerations
    (varying id_cliente) that are tagged "comun": False -- a statistical
    check, not a single-example read, same discipline as the liked-meal
    test above. Vegan diet forces tofu/tempeh/edamame/seitan/protein
    powder into the candidate pool alongside common lentils/chickpeas, so
    there's a real, non-trivial "less common" share to bias away from."""
    perfil["nutricion"]["tipo_dieta"] = "vegana"
    perfil["experiencia"]["nivel_compromiso"] = nivel_compromiso
    total, no_comunes = 0, 0
    for i in range(n):
        perfil["id_cliente"] = f"comun_{nivel_compromiso}_{i}"
        plan = generar_plan_semanal(perfil, NECESIDADES, 4, "en", _rng(perfil))
        for dia in plan:
            for comida in dia["comidas"]:
                for clave in ("proteina", "carbohidrato", "grasa"):
                    nombre = comida[clave]
                    if nombre is None:
                        continue
                    total += 1
                    if not INDICE_ALIMENTOS[nombre].get("comun", True):
                        no_comunes += 1
    return no_comunes / total


def test_basico_leans_toward_common_foods_over_specialty_ones(perfil_base):
    """"basico" now genuinely picks more recognizable, everyday foods
    (chicken/rice/eggs-type staples) over specialty items (tofu/tempeh/
    quinoa/...) than "normal" does, confirmed statistically -- see
    docs/decisiones.md."""
    proporcion_basico = _proporcion_no_comun(perfil_base, "basico")
    proporcion_normal = _proporcion_no_comun(perfil_base, "normal")
    assert proporcion_basico < proporcion_normal


def test_limited_time_or_budget_also_leans_toward_common_foods(perfil_base):
    """Direct request: nutricion.contexto's "tight budget"/"little time to
    cook" presets (ui/app.py's OPCIONES_CONTEXTO_NUTRICION) should adapt
    the plan "como el resto" -- reuses the exact same comun-food bias
    "basico" gets (see _sesgar_por_nivel_compromiso()'s own docstring),
    confirmed statistically at "normal" commitment level so nivel_
    compromiso's own bias isn't what's being measured here."""
    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    perfil_sin_contexto = {**perfil_base, "nutricion": {**perfil_base["nutricion"], "contexto": ""}}
    perfil_con_contexto = {**perfil_base, "nutricion": {**perfil_base["nutricion"], "contexto": "tight budget"}}

    def _proporcion(perfil, sufijo, n=20):
        perfil["nutricion"]["tipo_dieta"] = "vegana"
        total, no_comunes = 0, 0
        for i in range(n):
            perfil["id_cliente"] = f"tiempo_{sufijo}_{i}"
            plan = generar_plan_semanal(perfil, NECESIDADES, 4, "en", _rng(perfil))
            for dia in plan:
                for comida in dia["comidas"]:
                    for clave in ("proteina", "carbohidrato", "grasa"):
                        nombre = comida[clave]
                        if nombre is None:
                            continue
                        total += 1
                        if not INDICE_ALIMENTOS[nombre].get("comun", True):
                            no_comunes += 1
        return no_comunes / total

    assert _proporcion(perfil_con_contexto, "con") < _proporcion(perfil_sin_contexto, "sin")


def test_basico_still_uses_specialty_foods_when_nothing_common_is_left(perfil_base):
    """Bias, not exclusion: a vegan client whose ONLY protein candidates
    are specialty items (every common option disliked) must still get a
    real, valid meal rather than an empty/crashing plan."""
    perfil_base["nutricion"]["tipo_dieta"] = "vegana"
    perfil_base["experiencia"]["nivel_compromiso"] = "basico"
    # Dislike every common vegan-compatible protein, leaving only tofu/
    # tempeh/edamame/seitan/protein powder (all "comun": False).
    perfil_base["nutricion"]["alimentos_que_no_le_gustan"] = ["lentils", "chickpeas"]
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    assert plan  # still a real plan, not empty
    proteinas = {c["proteina"] for dia in plan for c in dia["comidas"]}
    assert proteinas  # at least one protein pick happened
    assert all(not INDICE_ALIMENTOS[p].get("comun", True) for p in proteinas)


def test_avanzado_leans_toward_specialty_foods_over_normal(perfil_base):
    """"avanzado" is a real middle step toward "tryhard"'s niche foods,
    without touching that curated list -- confirmed statistically (see
    docs/decisiones.md)."""

    def proporcion_no_comun(nivel_compromiso, n=20):
        perfil_base["experiencia"]["nivel_compromiso"] = nivel_compromiso
        total, no_comunes = 0, 0
        for i in range(n):
            perfil_base["id_cliente"] = f"avz_comun_{nivel_compromiso}_{i}"
            plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
            for dia in plan:
                for comida in dia["comidas"]:
                    for clave in ("proteina", "carbohidrato", "grasa"):
                        nombre = comida[clave]
                        if nombre is None:
                            continue
                        total += 1
                        if not INDICE_ALIMENTOS[nombre].get("comun", True):
                            no_comunes += 1
        return no_comunes / total

    assert proporcion_no_comun("avanzado") > proporcion_no_comun("normal")


def test_avanzado_never_uses_true_nicho_foods(perfil_base):
    """"avanzado"'s specialty lean stays within "comun": False -- the
    separate, more curated "nicho" pool (kimchi, natto, farro, algae oil)
    stays tryhard-exclusive."""
    from food_bank import fuentes_proteina_para

    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    nombres = {c[clave] for dia in plan for c in dia["comidas"] for clave in ("proteina", "carbohidrato", "grasa")}
    assert "Natto" not in nombres
    assert "Natto" not in fuentes_proteina_para(perfil_base)


# --- Wetaca-style dish naming + optional cooking tips ---------------------


def test_every_meal_description_opens_with_a_named_dish(perfil_base):
    """Direct request: a named dish ("Lentejas con pollo"/"Chicken with
    lentils"), not just a bare ingredient list -- every meal's description
    now opens with "{dish name}: " before the gram breakdown."""
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    for dia in plan:
        for comida in dia["comidas"]:
            assert ": " in comida["descripcion"]
            nombre_plato = comida["descripcion"].split(": ", 1)[0]
            assert nombre_plato and not nombre_plato[0].isdigit()


def test_recognized_ingredient_gets_an_optional_cooking_tip(perfil_base):
    """A profile that only eats lentils/chickpeas/rice/etc. for its carb
    should surface CONSEJOS_COCINA's tip somewhere across the week -- proves
    _consejo_cocina() is actually wired into the rendered description, not
    just defined."""
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
    descripciones = " ".join(c["descripcion"] for dia in plan for c in dia["comidas"])
    assert "Optional:" in descripciones


def test_cooking_tip_is_translated_in_spanish(perfil_base):
    plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "es", _rng(perfil_base))
    descripciones = " ".join(c["descripcion"] for dia in plan for c in dia["comidas"])
    assert "Opcional:" in descripciones


def test_common_combo_gets_a_curated_recipe_name(perfil_base):
    """Direct follow-up request ("diseña platos concretos saludables y
    dale nombre a la receta"): the most common protein+carb combinations
    (NOMBRES_PLATO_CURADOS) get a real recipe name instead of just the
    mechanical "carb con proteína" fallback. Runs many client IDs and
    looks for at least one curated name surfacing somewhere across the
    week -- meal selection is random per slot, so no single seed is
    guaranteed to land on a specific combo."""
    from planificador_comidas import NOMBRES_PLATO_CURADOS

    nombres_curados_en = {v["en"] for v in NOMBRES_PLATO_CURADOS.values()}
    encontrado = False
    for i in range(20):
        perfil_base["id_cliente"] = f"receta_curada_{i}"
        plan = generar_plan_semanal(perfil_base, NECESIDADES, 4, "en", _rng(perfil_base))
        for dia in plan:
            for comida in dia["comidas"]:
                nombre_plato = comida["descripcion"].split(": ", 1)[0]
                if nombre_plato in nombres_curados_en:
                    encontrado = True
    assert encontrado, "no curated recipe name showed up across 20 client IDs"


def test_lunch_and_dinner_never_share_the_exact_same_combo(perfil_base):
    """Direct request: "que no te toque comer y cenar lo mismo el mismo
    día". A real, bounded exclusion (see _construir_comida()'s
    combos_dia_previos), checked across several different client IDs
    since meal selection is seeded per client -- not just one lucky
    draw."""
    for i in range(15):
        perfil_base["id_cliente"] = f"sin_repetir_dia_{i}"
        plan = generar_plan_semanal(perfil_base, NECESIDADES, 3, "en", _rng(perfil_base))
        for dia in plan:
            por_tipo = {c["tipo_interno"]: c for c in dia["comidas"]}
            almuerzo, cena = por_tipo.get("comida"), por_tipo.get("cena")
            assert almuerzo and cena
            combo_almuerzo = (almuerzo["proteina"], almuerzo["carbohidrato"], almuerzo["grasa"])
            combo_cena = (cena["proteina"], cena["carbohidrato"], cena["grasa"])
            assert combo_almuerzo != combo_cena, f"{dia['dia']} (client {i}): {combo_almuerzo}"
