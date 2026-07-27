"""
Food bank for the diet rule engine.

Each protein/food source declares which diet types allow it and which
allergies/intolerances exclude it, so the profile can be filtered without
needing an LLM to "reason" about basic dietary restrictions.

Note on scope: the "nombre" (name) values are the food display names shown
to the user and were translated to English along with the rest of the
project's content. `etiquetas_excluidas()` matches keywords against the free
text in the client's declared allergies/intolerances — it checks both
Spanish and English keywords so it keeps working regardless of which
language that free text was written in (relevant now that example profiles
were translated to English too). See docs/decisiones.md.
"""

FUENTES_PROTEINA = [
    {"nombre": "Chicken breast", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "Turkey", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "Lean beef", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "White fish (hake, sole)", "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}},
    {"nombre": "Salmon / oily fish", "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}},
    {"nombre": "Eggs", "tipos_dieta": {"omnivora", "vegetariana_ovolacto"}, "etiquetas": {"huevo"}},
    {"nombre": "Greek yogurt / whipped fresh cheese", "tipos_dieta": {"omnivora", "vegetariana_ovolacto"}, "etiquetas": {"lacteo"}},
    {"nombre": "Lentils", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"}},
    {"nombre": "Chickpeas", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"}},
    {"nombre": "Tofu", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Tempeh", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Edamame", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Seitan", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"gluten"}},
    {"nombre": "Pea protein (powder)", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": set()},
]

FUENTES_CARBOHIDRATO = [
    {"nombre": "Rice", "etiquetas": set()},
    {"nombre": "Oats", "etiquetas": {"gluten_trazas"}},
    {"nombre": "Potato / sweet potato", "etiquetas": set()},
    {"nombre": "Whole wheat bread", "etiquetas": {"gluten"}},
    {"nombre": "Whole wheat pasta", "etiquetas": {"gluten"}},
    {"nombre": "Quinoa", "etiquetas": set()},
    {"nombre": "Legumes (also a carb source)", "etiquetas": {"legumbre"}},
    {"nombre": "Assorted fruit", "etiquetas": set()},
]

FUENTES_GRASA = [
    {"nombre": "Extra virgin olive oil", "etiquetas": set()},
    {"nombre": "Avocado", "etiquetas": set()},
    {"nombre": "Nuts (walnuts, almonds)", "etiquetas": {"frutos_secos"}},
    {"nombre": "Seeds (chia, flax)", "etiquetas": set()},
    {"nombre": "Oily fish (EPA/DHA)", "etiquetas": {"pescado"}},
]


def etiquetas_excluidas(perfil: dict) -> set[str]:
    """Profile allergies/intolerances translated into food-bank exclusion tags."""
    salud = perfil.get("salud", {})
    texto = " ".join(
        salud.get("alergias_alimentarias", []) + salud.get("intolerancias_alimentarias", [])
    ).lower()

    excluidas = set()
    if any(kw in texto for kw in ("lactosa", "lácteo", "lacteo", "lactose", "dairy")):
        excluidas.add("lacteo")
    if "gluten" in texto:
        excluidas.add("gluten")
        excluidas.add("gluten_trazas")
    if ("fruto" in texto and "seco" in texto) or "nut" in texto:
        excluidas.add("frutos_secos")
    if "huevo" in texto or "egg" in texto:
        excluidas.add("huevo")
    if "soja" in texto or "soy" in texto:
        excluidas.add("soja")
    if any(kw in texto for kw in ("pescado", "marisco", "fish", "seafood", "shellfish")):
        excluidas.add("pescado")
    return excluidas


def fuentes_proteina_para(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    excluidas = etiquetas_excluidas(perfil)
    return [
        f["nombre"] for f in FUENTES_PROTEINA
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & excluidas)
    ]


def fuentes_carbohidrato_para(perfil: dict) -> list[str]:
    excluidas = etiquetas_excluidas(perfil)
    return [f["nombre"] for f in FUENTES_CARBOHIDRATO if not (f["etiquetas"] & excluidas)]


def fuentes_grasa_para(perfil: dict) -> list[str]:
    excluidas = etiquetas_excluidas(perfil)
    return [f["nombre"] for f in FUENTES_GRASA if not (f["etiquetas"] & excluidas)]
