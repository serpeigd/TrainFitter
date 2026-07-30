"""
Food bank for the diet rule engine.

Each protein/food source declares which diet types allow it and which
allergies/intolerances exclude it, so the profile can be filtered without
needing an LLM to "reason" about basic dietary restrictions.

Note on scope: the "nombre" (name) values are the food's CANONICAL name —
English, and deliberately never swapped for Spanish even when the UI
language is Spanish. dieta_reglas.py filters by these values, and
validator_agent.py cross-checks a draft's suggested foods against them by
exact string match; changing "nombre" based on UI language would silently
break that safety cross-check (see docs/decisiones.md). "nombre_es" is
purely a display translation, used only by ui/app.py to show a localized
name on screen — never used for filtering or matching anywhere in the
pipeline. `etiquetas_excluidas()` matches keywords against the free text in
the client's declared allergies/intolerances — it checks both Spanish and
English keywords so it keeps working regardless of which language that free
text was written in. See docs/decisiones.md.
"""

FUENTES_PROTEINA = [
    {"nombre": "Chicken breast", "nombre_es": "Pechuga de pollo", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "Turkey", "nombre_es": "Pavo", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "Lean beef", "nombre_es": "Ternera magra", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "White fish (hake, sole)", "nombre_es": "Pescado blanco (merluza, lenguado)", "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}},
    {"nombre": "Salmon / oily fish", "nombre_es": "Salmón / pescado azul", "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}},
    {"nombre": "Eggs", "nombre_es": "Huevos", "tipos_dieta": {"omnivora", "vegetariana_ovolacto"}, "etiquetas": {"huevo"}},
    {"nombre": "Greek yogurt / whipped fresh cheese", "nombre_es": "Yogur griego / queso fresco batido", "tipos_dieta": {"omnivora", "vegetariana_ovolacto"}, "etiquetas": {"lacteo"}},
    {"nombre": "Lentils", "nombre_es": "Lentejas", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"}},
    {"nombre": "Chickpeas", "nombre_es": "Garbanzos", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"}},
    {"nombre": "Tofu", "nombre_es": "Tofu", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Tempeh", "nombre_es": "Tempeh", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Edamame", "nombre_es": "Edamame", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Seitan", "nombre_es": "Seitán", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"gluten"}},
    {"nombre": "Pea protein (powder)", "nombre_es": "Proteína de guisante (en polvo)", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": set()},
]

FUENTES_CARBOHIDRATO = [
    {"nombre": "Rice", "nombre_es": "Arroz", "etiquetas": set()},
    {"nombre": "Oats", "nombre_es": "Avena", "etiquetas": {"gluten_trazas"}},
    {"nombre": "Potato / sweet potato", "nombre_es": "Patata / boniato", "etiquetas": set()},
    {"nombre": "Whole wheat bread", "nombre_es": "Pan integral", "etiquetas": {"gluten"}},
    {"nombre": "Whole wheat pasta", "nombre_es": "Pasta integral", "etiquetas": {"gluten"}},
    {"nombre": "Quinoa", "nombre_es": "Quinoa", "etiquetas": set()},
    {"nombre": "Legumes (also a carb source)", "nombre_es": "Legumbres (también fuente de carbohidrato)", "etiquetas": {"legumbre"}},
    {"nombre": "Assorted fruit", "nombre_es": "Fruta variada", "etiquetas": set()},
]

FUENTES_GRASA = [
    {"nombre": "Extra virgin olive oil", "nombre_es": "Aceite de oliva virgen extra", "etiquetas": set()},
    {"nombre": "Avocado", "nombre_es": "Aguacate", "etiquetas": set()},
    {"nombre": "Nuts (walnuts, almonds)", "nombre_es": "Frutos secos (nueces, almendras)", "etiquetas": {"frutos_secos"}},
    {"nombre": "Seeds (chia, flax)", "nombre_es": "Semillas (chía, lino)", "etiquetas": set()},
    {"nombre": "Oily fish (EPA/DHA)", "nombre_es": "Pescado azul (EPA/DHA)", "etiquetas": {"pescado"}},
]

# English name -> Spanish display name, across all three banks. Display-only
# (see module docstring): never used for filtering or the validator's
# cross-checks, only by ui/app.py to show a localized food name on screen.
NOMBRES_ES = {f["nombre"]: f["nombre_es"] for f in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA}


def nombre_mostrado(nombre: str, idioma: str) -> str:
    """English `nombre` -> localized display name. Falls back to the
    English name if idioma isn't "es" or the name isn't in any bank."""
    return NOMBRES_ES.get(nombre, nombre) if idioma == "es" else nombre


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
