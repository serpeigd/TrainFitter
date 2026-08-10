"""
Food bank for the diet rule engine.

Each protein/carb/fat/vegetable source declares which diet types allow it
and which allergies/intolerances exclude it, so the profile can be
filtered without needing an LLM to "reason" about basic dietary
restrictions.

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

DESIGN — "macros_100g" and weekly meal planning (added alongside
agents/planificador_comidas.py): every entry across all four banks now also
carries approximate kcal/protein/carb/fat per 100g (cooked/prepared basis
where that matters — e.g. dry oats, cooked rice/legumes/pasta), standard
reference values in the same spirit as any nutrition-label lookup, not a
clinical lab measurement. planificador_comidas.py uses these to scale
portions so a generated week of meals roughly lands on the client's own
daily kcal/macro targets — "roughly," on purpose: the trainer's method
(docs/base_conocimiento/nutricion.md) is explicit that sustainable and
"close enough, adjusted from real progress" beats a number that's precise
on paper but doesn't survive contact with an actual kitchen.

DESIGN — "sinergias": a separate tag set from "etiquetas" (which is only
ever about exclusion/safety). These mark which absorption-synergy role a
food can play, grounded in
docs/base_conocimiento/sinergias_nutrientes.md's own table: "hierro_no_hemo"
(non-heme plant iron — pair with a "vitamina_c" food in the same meal),
"vitamina_c" (the pairing partner above; also boosts non-heme iron
absorption on its own merits), "beta_caroteno" (better absorbed with
dietary fat, which every meal that includes a FUENTES_GRASA pick already
has), "probiotico"/"prebiotico_fibra" (yogurt + oats/fruit in the same
meal). planificador_comidas.py reads these tags to decide which foods to
pair *within the same meal*, not just list separately -- see that module's
own docstring for how.
"""

FUENTES_PROTEINA = [
    {
        "nombre": "Chicken breast", "nombre_es": "Pechuga de pollo",
        "tipos_dieta": {"omnivora"}, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 165, "proteina_g": 31, "carbohidratos_g": 0, "grasa_g": 3.6},
    },
    {
        "nombre": "Turkey", "nombre_es": "Pavo",
        "tipos_dieta": {"omnivora"}, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 135, "proteina_g": 30, "carbohidratos_g": 0, "grasa_g": 1},
    },
    {
        "nombre": "Lean beef", "nombre_es": "Ternera magra",
        "tipos_dieta": {"omnivora"}, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 205, "proteina_g": 27, "carbohidratos_g": 0, "grasa_g": 10},
    },
    {
        "nombre": "White fish (hake, sole)", "nombre_es": "Pescado blanco (merluza, lenguado)",
        "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}, "sinergias": set(),
        "macros_100g": {"kcal": 90, "proteina_g": 19, "carbohidratos_g": 0, "grasa_g": 1},
    },
    {
        "nombre": "Salmon / oily fish", "nombre_es": "Salmón / pescado azul",
        "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}, "sinergias": set(),
        "macros_100g": {"kcal": 208, "proteina_g": 20, "carbohidratos_g": 0, "grasa_g": 13},
    },
    {
        "nombre": "Eggs", "nombre_es": "Huevos",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto"}, "etiquetas": {"huevo"}, "sinergias": set(),
        "macros_100g": {"kcal": 155, "proteina_g": 13, "carbohidratos_g": 1.1, "grasa_g": 11},
    },
    {
        "nombre": "Greek yogurt / whipped fresh cheese", "nombre_es": "Yogur griego / queso fresco batido",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto"}, "etiquetas": {"lacteo"}, "sinergias": {"probiotico"},
        "macros_100g": {"kcal": 59, "proteina_g": 10, "carbohidratos_g": 3.6, "grasa_g": 0.4},
    },
    {
        "nombre": "Lentils", "nombre_es": "Lentejas",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"},
        "sinergias": {"hierro_no_hemo"},
        "macros_100g": {"kcal": 116, "proteina_g": 9, "carbohidratos_g": 20, "grasa_g": 0.4},
    },
    {
        "nombre": "Chickpeas", "nombre_es": "Garbanzos",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"},
        "sinergias": {"hierro_no_hemo"},
        "macros_100g": {"kcal": 164, "proteina_g": 9, "carbohidratos_g": 27, "grasa_g": 2.6},
    },
    {
        "nombre": "Tofu", "nombre_es": "Tofu",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"},
        "sinergias": {"hierro_no_hemo"},
        "macros_100g": {"kcal": 144, "proteina_g": 15, "carbohidratos_g": 3, "grasa_g": 8},
    },
    {
        "nombre": "Tempeh", "nombre_es": "Tempeh",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"},
        "sinergias": {"hierro_no_hemo"},
        "macros_100g": {"kcal": 192, "proteina_g": 20, "carbohidratos_g": 8, "grasa_g": 11},
    },
    {
        "nombre": "Edamame", "nombre_es": "Edamame",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"},
        "sinergias": {"hierro_no_hemo"},
        "macros_100g": {"kcal": 121, "proteina_g": 12, "carbohidratos_g": 10, "grasa_g": 5},
    },
    {
        "nombre": "Seitan", "nombre_es": "Seitán",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"gluten"}, "sinergias": set(),
        "macros_100g": {"kcal": 370, "proteina_g": 75, "carbohidratos_g": 14, "grasa_g": 1.9},
    },
    {
        "nombre": "Pea protein (powder)", "nombre_es": "Proteína de guisante (en polvo)",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 373, "proteina_g": 78, "carbohidratos_g": 6, "grasa_g": 6},
    },
]

# All entries here happen to contain no meat/fish/dairy/eggs, so every one
# is available to every diet type today -- "tipos_dieta" is still declared
# explicitly (not just left off) so that stays a checked fact instead of
# an assumption: adding a future entry that *isn't* universally
# compatible (e.g. a dairy-based carb source) is filtered correctly by
# fuentes_carbohidrato_para() automatically, rather than silently slipping
# through the way "Oily fish" did in FUENTES_GRASA below before this was
# fixed (see docs/decisiones.md).
_TODAS_LAS_DIETAS = {"omnivora", "vegetariana_ovolacto", "vegana"}

FUENTES_CARBOHIDRATO = [
    {
        "nombre": "Rice", "nombre_es": "Arroz",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 130, "proteina_g": 2.7, "carbohidratos_g": 28, "grasa_g": 0.3},
    },
    {
        "nombre": "Oats", "nombre_es": "Avena",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"gluten_trazas"}, "sinergias": {"prebiotico_fibra"},
        "macros_100g": {"kcal": 389, "proteina_g": 16.9, "carbohidratos_g": 66, "grasa_g": 6.9},
    },
    {
        "nombre": "Potato / sweet potato", "nombre_es": "Patata / boniato",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"beta_caroteno"},
        "macros_100g": {"kcal": 87, "proteina_g": 2, "carbohidratos_g": 20, "grasa_g": 0.1},
    },
    {
        "nombre": "Whole wheat bread", "nombre_es": "Pan integral",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"gluten"}, "sinergias": set(),
        "macros_100g": {"kcal": 247, "proteina_g": 13, "carbohidratos_g": 41, "grasa_g": 3.4},
    },
    {
        "nombre": "Whole wheat pasta", "nombre_es": "Pasta integral",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"gluten"}, "sinergias": set(),
        "macros_100g": {"kcal": 124, "proteina_g": 5, "carbohidratos_g": 25, "grasa_g": 1.1},
    },
    {
        "nombre": "Quinoa", "nombre_es": "Quinoa",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 120, "proteina_g": 4.4, "carbohidratos_g": 21, "grasa_g": 1.9},
    },
    {
        "nombre": "Legumes (also a carb source)", "nombre_es": "Legumbres (también fuente de carbohidrato)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"legumbre"}, "sinergias": {"hierro_no_hemo"},
        "macros_100g": {"kcal": 132, "proteina_g": 8.9, "carbohidratos_g": 24, "grasa_g": 0.5},
    },
    {
        "nombre": "Assorted fruit", "nombre_es": "Fruta variada",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c"},
        "macros_100g": {"kcal": 60, "proteina_g": 0.5, "carbohidratos_g": 15, "grasa_g": 0.2},
    },
]

FUENTES_GRASA = [
    {
        "nombre": "Extra virgin olive oil", "nombre_es": "Aceite de oliva virgen extra",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 884, "proteina_g": 0, "carbohidratos_g": 0, "grasa_g": 100},
    },
    {
        "nombre": "Avocado", "nombre_es": "Aguacate",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 160, "proteina_g": 2, "carbohidratos_g": 8.5, "grasa_g": 15},
    },
    {
        "nombre": "Nuts (walnuts, almonds)", "nombre_es": "Frutos secos (nueces, almendras)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"frutos_secos"}, "sinergias": set(),
        "macros_100g": {"kcal": 600, "proteina_g": 20, "carbohidratos_g": 15, "grasa_g": 52},
    },
    {
        "nombre": "Seeds (chia, flax)", "nombre_es": "Semillas (chía, lino)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 500, "proteina_g": 18, "carbohidratos_g": 34, "grasa_g": 34},
    },
    # The one entry that ISN'T universally compatible -- omnivore only.
    # Finding this required actually building a vegan example client and
    # looking at its real suggested fat sources, not just reading the
    # code (see docs/decisiones.md): fuentes_grasa_para() below had no
    # diet-type filter at all until this fix, so a vegan/vegetarian
    # client's diet draft was suggesting fish as a fat source.
    {
        "nombre": "Oily fish (EPA/DHA)", "nombre_es": "Pescado azul (EPA/DHA)",
        "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}, "sinergias": set(),
        "macros_100g": {"kcal": 208, "proteina_g": 20, "carbohidratos_g": 0, "grasa_g": 13},
    },
]

# Vegetables/fiber-and-micronutrient sources -- not tracked as a macro
# priority the way protein/carb/fat are (method §0: protein first, fat/carb
# from what's left), but a real weekly diet needs them for fiber, volume,
# and the vitamin-C/beta-carotene synergy roles docs/base_conocimiento/
# sinergias_nutrientes.md calls out by name ("Lentils/spinach + lemon, red
# pepper, or kiwi"; "Carrot/tomato + olive oil"). Same filtering discipline
# as the other three banks (tipos_dieta/etiquetas declared explicitly, run
# through etiquetas_excluidas()) and the same validator cross-check (see
# validator_agent.py's _validar_dieta_contra_alergias()) -- adding a new
# food category was NOT allowed to quietly open a hole in that safety net.
FUENTES_VERDURA = [
    {
        "nombre": "Broccoli", "nombre_es": "Brócoli",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c"},
        "macros_100g": {"kcal": 35, "proteina_g": 2.4, "carbohidratos_g": 7, "grasa_g": 0.4},
    },
    {
        "nombre": "Spinach", "nombre_es": "Espinacas",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"hierro_no_hemo"},
        "macros_100g": {"kcal": 23, "proteina_g": 2.9, "carbohidratos_g": 3.6, "grasa_g": 0.4},
    },
    {
        "nombre": "Red bell pepper", "nombre_es": "Pimiento rojo",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c"},
        "macros_100g": {"kcal": 31, "proteina_g": 1, "carbohidratos_g": 6, "grasa_g": 0.3},
    },
    {
        "nombre": "Tomato", "nombre_es": "Tomate",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c", "beta_caroteno"},
        "macros_100g": {"kcal": 18, "proteina_g": 0.9, "carbohidratos_g": 3.9, "grasa_g": 0.2},
    },
    {
        "nombre": "Carrot", "nombre_es": "Zanahoria",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"beta_caroteno"},
        "macros_100g": {"kcal": 41, "proteina_g": 0.9, "carbohidratos_g": 10, "grasa_g": 0.2},
    },
    {
        "nombre": "Mixed salad greens", "nombre_es": "Ensalada variada",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": set(),
        "macros_100g": {"kcal": 20, "proteina_g": 1.5, "carbohidratos_g": 3.5, "grasa_g": 0.2},
    },
    {
        "nombre": "Kiwi", "nombre_es": "Kiwi",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c"},
        "macros_100g": {"kcal": 61, "proteina_g": 1.1, "carbohidratos_g": 15, "grasa_g": 0.5},
    },
    {
        "nombre": "Citrus (orange, lemon)", "nombre_es": "Cítricos (naranja, limón)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c"},
        "macros_100g": {"kcal": 47, "proteina_g": 0.9, "carbohidratos_g": 12, "grasa_g": 0.1},
    },
]

# English name -> Spanish display name, across all four banks. Display-only
# (see module docstring): never used for filtering or the validator's
# cross-checks, only by ui/app.py to show a localized food name on screen.
NOMBRES_ES = {
    f["nombre"]: f["nombre_es"]
    for f in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA + FUENTES_VERDURA
}

# name -> full entry, across all four banks -- planificador_comidas.py's
# single lookup point for a food's macros_100g/sinergias once
# fuentes_*_para() has already filtered a candidate name list. Built once
# at import time rather than re-scanning the banks per lookup.
INDICE_ALIMENTOS = {
    f["nombre"]: f for f in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA + FUENTES_VERDURA
}


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
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    excluidas = etiquetas_excluidas(perfil)
    return [
        f["nombre"] for f in FUENTES_CARBOHIDRATO
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & excluidas)
    ]


def fuentes_grasa_para(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    excluidas = etiquetas_excluidas(perfil)
    return [
        f["nombre"] for f in FUENTES_GRASA
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & excluidas)
    ]


def fuentes_verdura_para(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    excluidas = etiquetas_excluidas(perfil)
    return [
        f["nombre"] for f in FUENTES_VERDURA
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & excluidas)
    ]
