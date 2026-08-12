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

DESIGN — soft dietary preferences (added for maximal personalization, see
docs/decisiones.md): unlike allergies/intolerances (a hard, safety-relevant
exclusion via `etiquetas`/`etiquetas_excluidas()`), a client can express a
*preference* -- "I want to eat anti-inflammatory," "I'd like to lower my
gluten," a food they simply don't like -- that should shape the plan
without ever being treated as a declared allergy (no
`revision_reforzada`, no cross-check warning; see
validator_agent.py, which deliberately never reads these).
`preferencias_texto_libre()` pools every free-text field a client might
have expressed this in (goal in their own words, nutrition context, the
new `inquietud_principal` field, free notes) so a preference mentioned
anywhere gets picked up, not just in one specific box.
`preferencias_blandas()` turns that pooled text plus two *structured*
lifestyle fields (perceived stress, sleep hours) into a small set of tags:
"reducir_gluten" (soft-excludes `gluten`-tagged foods from suggestions --
deliberately NOT `gluten_trazas`/traces, e.g. oats: a real, common
distinction between "lower gluten" and an actual gluten allergy/intolerance,
which still excludes both), "antiinflamatorio" (bias meal selection toward
foods tagged "antiinflamatorio" below -- oily fish, olive oil, nuts/seeds,
colorful vegetables/fruit), and "estres_alto_o_sueno_bajo" (bias toward
"magnesio"-tagged foods -- magnesium at night is one of
docs/base_conocimiento/nutricion.md's four longevity-focus blocks, and
docs/base_conocimiento/sinergias_nutrientes.md's own timing section calls
out magnesium specifically). `alimentos_no_deseados()` is a separate,
per-food (not per-tag) soft exclusion: it matches a client's disliked-foods/
restrictions free text directly against each food's own name (English or
Spanish) -- unlike a synergy/preference tag, "I don't like broccoli" is
about one specific food, not a category.

DESIGN — "nicho" (niche/tryhard foods, added for the commitment-level
personalization, see docs/decisiones.md): a handful of specialty/fermented
entries (kimchi, natto, farro, algae oil) that are only ever candidates for
a client whose `experiencia.nivel_compromiso` is `"tryhard"` -- these are
curated by the trainer/project, not something a client types in freely
(see `fuentes_*_para()`'s own `tryhard` gate). Absent (defaults to `False`
via `.get("nicho", False)`) on every pre-existing entry, so "chill"/
"normal" (the default) behave exactly as before this was added.
"""

import unicodedata

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
        "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}, "sinergias": {"antiinflamatorio"},
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
        "sinergias": {"hierro_no_hemo", "magnesio"},
        "macros_100g": {"kcal": 116, "proteina_g": 9, "carbohidratos_g": 20, "grasa_g": 0.4},
    },
    {
        "nombre": "Chickpeas", "nombre_es": "Garbanzos",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"},
        "sinergias": {"hierro_no_hemo", "magnesio"},
        "macros_100g": {"kcal": 164, "proteina_g": 9, "carbohidratos_g": 27, "grasa_g": 2.6},
    },
    {
        "nombre": "Tofu", "nombre_es": "Tofu",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"},
        "sinergias": {"hierro_no_hemo", "magnesio"},
        "macros_100g": {"kcal": 144, "proteina_g": 15, "carbohidratos_g": 3, "grasa_g": 8},
    },
    {
        "nombre": "Tempeh", "nombre_es": "Tempeh",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"},
        "sinergias": {"hierro_no_hemo", "magnesio"},
        "macros_100g": {"kcal": 192, "proteina_g": 20, "carbohidratos_g": 8, "grasa_g": 11},
    },
    {
        "nombre": "Edamame", "nombre_es": "Edamame",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"},
        "sinergias": {"hierro_no_hemo", "magnesio"},
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
    {
        "nombre": "Natto", "nombre_es": "Natto",
        "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"},
        "sinergias": {"probiotico", "magnesio"}, "nicho": True,
        "macros_100g": {"kcal": 212, "proteina_g": 18, "carbohidratos_g": 14, "grasa_g": 11},
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
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"gluten_trazas"},
        "sinergias": {"prebiotico_fibra", "magnesio", "fibra_alta"},
        "macros_100g": {"kcal": 389, "proteina_g": 16.9, "carbohidratos_g": 66, "grasa_g": 6.9},
    },
    {
        "nombre": "Potato / sweet potato", "nombre_es": "Patata / boniato",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"beta_caroteno"},
        "macros_100g": {"kcal": 87, "proteina_g": 2, "carbohidratos_g": 20, "grasa_g": 0.1},
    },
    {
        "nombre": "Whole wheat bread", "nombre_es": "Pan integral",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"gluten"}, "sinergias": {"fibra_alta"},
        "macros_100g": {"kcal": 247, "proteina_g": 13, "carbohidratos_g": 41, "grasa_g": 3.4},
    },
    {
        "nombre": "Whole wheat pasta", "nombre_es": "Pasta integral",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"gluten"}, "sinergias": {"fibra_alta"},
        "macros_100g": {"kcal": 124, "proteina_g": 5, "carbohidratos_g": 25, "grasa_g": 1.1},
    },
    {
        "nombre": "Quinoa", "nombre_es": "Quinoa",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"magnesio"},
        "macros_100g": {"kcal": 120, "proteina_g": 4.4, "carbohidratos_g": 21, "grasa_g": 1.9},
    },
    {
        "nombre": "Legumes (also a carb source)", "nombre_es": "Legumbres (también fuente de carbohidrato)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"legumbre"},
        "sinergias": {"hierro_no_hemo", "magnesio", "fibra_alta"},
        "macros_100g": {"kcal": 132, "proteina_g": 8.9, "carbohidratos_g": 24, "grasa_g": 0.5},
    },
    {
        "nombre": "Assorted fruit", "nombre_es": "Fruta variada",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c"},
        "macros_100g": {"kcal": 60, "proteina_g": 0.5, "carbohidratos_g": 15, "grasa_g": 0.2},
    },
    {
        "nombre": "Farro", "nombre_es": "Farro",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"gluten"}, "sinergias": {"fibra_alta"}, "nicho": True,
        "macros_100g": {"kcal": 170, "proteina_g": 6, "carbohidratos_g": 34, "grasa_g": 1.1},
    },
]

FUENTES_GRASA = [
    {
        "nombre": "Extra virgin olive oil", "nombre_es": "Aceite de oliva virgen extra",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"antiinflamatorio"},
        "macros_100g": {"kcal": 884, "proteina_g": 0, "carbohidratos_g": 0, "grasa_g": 100},
    },
    {
        "nombre": "Avocado", "nombre_es": "Aguacate",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"antiinflamatorio", "fibra_alta"},
        "macros_100g": {"kcal": 160, "proteina_g": 2, "carbohidratos_g": 8.5, "grasa_g": 15},
    },
    {
        "nombre": "Nuts (walnuts, almonds)", "nombre_es": "Frutos secos (nueces, almendras)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": {"frutos_secos"},
        "sinergias": {"antiinflamatorio", "magnesio"},
        "macros_100g": {"kcal": 600, "proteina_g": 20, "carbohidratos_g": 15, "grasa_g": 52},
    },
    {
        "nombre": "Seeds (chia, flax)", "nombre_es": "Semillas (chía, lino)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"antiinflamatorio", "magnesio"},
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
        "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}, "sinergias": {"antiinflamatorio"},
        "macros_100g": {"kcal": 208, "proteina_g": 20, "carbohidratos_g": 0, "grasa_g": 13},
    },
    {
        "nombre": "Algae oil (vegan omega-3)", "nombre_es": "Aceite de algas (omega-3 vegano)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"antiinflamatorio"}, "nicho": True,
        "macros_100g": {"kcal": 884, "proteina_g": 0, "carbohidratos_g": 0, "grasa_g": 100},
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
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(),
        "sinergias": {"vitamina_c", "antiinflamatorio", "fibra_alta"},
        "macros_100g": {"kcal": 35, "proteina_g": 2.4, "carbohidratos_g": 7, "grasa_g": 0.4},
    },
    {
        "nombre": "Spinach", "nombre_es": "Espinacas",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(),
        "sinergias": {"hierro_no_hemo", "antiinflamatorio", "magnesio"},
        "macros_100g": {"kcal": 23, "proteina_g": 2.9, "carbohidratos_g": 3.6, "grasa_g": 0.4},
    },
    {
        "nombre": "Red bell pepper", "nombre_es": "Pimiento rojo",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c", "antiinflamatorio"},
        "macros_100g": {"kcal": 31, "proteina_g": 1, "carbohidratos_g": 6, "grasa_g": 0.3},
    },
    {
        "nombre": "Tomato", "nombre_es": "Tomate",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(),
        "sinergias": {"vitamina_c", "beta_caroteno", "antiinflamatorio"},
        "macros_100g": {"kcal": 18, "proteina_g": 0.9, "carbohidratos_g": 3.9, "grasa_g": 0.2},
    },
    {
        "nombre": "Carrot", "nombre_es": "Zanahoria",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"beta_caroteno", "fibra_alta"},
        "macros_100g": {"kcal": 41, "proteina_g": 0.9, "carbohidratos_g": 10, "grasa_g": 0.2},
    },
    {
        "nombre": "Mixed salad greens", "nombre_es": "Ensalada variada",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"fibra_alta"},
        "macros_100g": {"kcal": 20, "proteina_g": 1.5, "carbohidratos_g": 3.5, "grasa_g": 0.2},
    },
    {
        "nombre": "Kiwi", "nombre_es": "Kiwi",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c", "antiinflamatorio"},
        "macros_100g": {"kcal": 61, "proteina_g": 1.1, "carbohidratos_g": 15, "grasa_g": 0.5},
    },
    {
        "nombre": "Citrus (orange, lemon)", "nombre_es": "Cítricos (naranja, limón)",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(), "sinergias": {"vitamina_c", "antiinflamatorio"},
        "macros_100g": {"kcal": 47, "proteina_g": 0.9, "carbohidratos_g": 12, "grasa_g": 0.1},
    },
    {
        "nombre": "Kimchi", "nombre_es": "Kimchi",
        "tipos_dieta": _TODAS_LAS_DIETAS, "etiquetas": set(),
        "sinergias": {"probiotico", "vitamina_c"}, "nicho": True,
        "macros_100g": {"kcal": 15, "proteina_g": 1.1, "carbohidratos_g": 2.4, "grasa_g": 0.5},
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
    """Profile allergies/intolerances translated into food-bank exclusion
    tags -- a hard, safety-relevant exclusion (see validator_agent.py's
    cross-check). Never mixed with the soft preferences below: an allergy
    excludes both `gluten` and `gluten_trazas`; a soft "lower gluten"
    preference (see preferencias_blandas()) only excludes `gluten`,
    deliberately keeping trace-amount foods like oats available."""
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


# Bilingual keyword -> soft-preference tag, checked against the pooled free
# text preferencias_texto_libre() builds. Deliberately small and easy to
# extend -- these are the two the project owner named explicitly; see
# docs/decisiones.md for why this stays keyword matching rather than real
# language understanding (the project's free-only guardrail).
_PALABRAS_CLAVE_PREFERENCIA_BLANDA = {
    "reducir_gluten": (
        "bajar el gluten", "menos gluten", "reducir gluten", "reducir el gluten",
        "lower gluten", "less gluten", "reduce gluten", "gluten-free", "gluten free",
    ),
    "antiinflamatorio": (
        "antiinflamatoria", "antiinflamatorio", "anti-inflamatoria", "anti-inflamatorio",
        "anti-inflammatory", "anti inflammatory", "inflamacion", "inflamación", "inflammation",
    ),
    "salud_digestiva": (
        "salud digestiva", "salud intestinal", "digestion", "digestión", "microbiota",
        "gut health", "digestive health", "gut",
    ),
    "mas_fibra": (
        "mas fibra", "más fibra", "alta en fibra", "rica en fibra",
        "high fiber", "high-fiber", "more fiber", "fiber-rich",
    ),
    "mas_hierro": (
        "mas hierro", "más hierro", "deficit de hierro", "déficit de hierro", "anemia",
        "more iron", "iron deficiency", "low iron", "iron-rich",
    ),
}


def preferencias_texto_libre(perfil: dict) -> str:
    """Pools every free-text field a client might have expressed a dietary
    preference in -- their goal in their own words, the nutrition context
    box, the dedicated `inquietud_principal` field, and general free
    notes -- into one lowercased string, so a preference mentioned in any
    one of them gets picked up rather than only a single specific box."""
    objetivo = perfil.get("objetivo", {})
    nutricion = perfil.get("nutricion", {})
    partes = [
        objetivo.get("en_sus_palabras") or "",
        nutricion.get("contexto") or "",
        nutricion.get("inquietud_principal") or "",
        perfil.get("notas_libres") or "",
    ]
    return " ".join(partes).lower()


def categoria_inquietud_conocida(texto: str) -> str:
    """Maps free text to one of _PALABRAS_CLAVE_PREFERENCIA_BLANDA's known
    categories ("antiinflamatorio"/"reducir_gluten"/"salud_digestiva"/
    "mas_fibra"/"mas_hierro"), or "" if it doesn't match any -- the
    reverse direction of the same keyword lists
    preferencias_blandas() already matches against, exposed publicly so
    ui/app.py's preset dropdown for `nutricion.inquietud_principal` (see
    docs/decisiones.md) can pre-select a known category when loading a
    saved client for revision, falling back to its free-text "Other"
    option for anything this project doesn't have a preset for."""
    texto = texto.lower()
    for categoria, palabras in _PALABRAS_CLAVE_PREFERENCIA_BLANDA.items():
        if any(palabra in texto for palabra in palabras):
            return categoria
    return ""


def preferencias_blandas(perfil: dict) -> set[str]:
    """Soft dietary preferences -- never a safety/allergy concern, never
    surfaced to validator_agent.py, just a bias applied to suggestions.
    Combines keyword-matched free text (see
    _PALABRAS_CLAVE_PREFERENCIA_BLANDA -- "reducir_gluten"/
    "antiinflamatorio"/"salud_digestiva" [probiotic-tagged foods]/
    "mas_fibra"/"mas_hierro" [non-heme iron, paired with vitamin C the
    same way the anemia/iron-deficiency concern already is]) with two
    structured lifestyle signals: high perceived stress or under 6h
    average sleep ("estres_alto_o_sueno_bajo" -- biases toward
    magnesium-tagged foods, see docs/base_conocimiento/nutricion.md's
    longevity-focus blocks and sinergias_nutrientes.md's timing section)
    and a sedentary job ("trabajo_sedentario" -- biases toward
    high-fiber foods)."""
    texto = preferencias_texto_libre(perfil)
    preferencias = {
        etiqueta for etiqueta, palabras in _PALABRAS_CLAVE_PREFERENCIA_BLANDA.items()
        if any(palabra in texto for palabra in palabras)
    }

    estilo = perfil.get("estilo_de_vida", {})
    estres = estilo.get("nivel_estres_percibido")
    sueno = estilo.get("horas_sueno_promedio")
    if estres == "alto" or (isinstance(sueno, (int, float)) and sueno < 6):
        preferencias.add("estres_alto_o_sueno_bajo")

    trabajo = (estilo.get("tipo_trabajo") or "").lower()
    if any(kw in trabajo for kw in ("sedentari", "sedentary", "oficina", "office", "desk", "escritorio")):
        preferencias.add("trabajo_sedentario")

    return preferencias


def _sin_acentos(texto: str) -> str:
    """Strips diacritics (á->a, í->i, ...) so "brocoli" (a client typing
    without accents, common in casual text) still matches "Brócoli" --
    unlike the fixed category keyword lists in etiquetas_excluidas()/
    _PALABRAS_CLAVE_PREFERENCIA_BLANDA (which can afford to just list both
    accented/unaccented variants by hand), alimentos_no_deseados() matches
    against every food name in the bank, so it needs to handle this
    generically. Standard library only (unicodedata), no new dependency."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _nombres_para_coincidencia(alimento: dict) -> tuple[str, ...]:
    """Every name form a disliked-food phrase might reasonably match
    against for this food -- English and Spanish names, each also
    stripped of any parenthetical qualifier ("White fish (hake, sole)" ->
    also "white fish"), since a client writing "no me gusta el pescado
    blanco" won't also name the specific fish types in parentheses. Accent-
    insensitive (see _sin_acentos())."""
    nombres = {alimento["nombre"], alimento["nombre_es"]}
    nombres |= {n.split("(")[0].strip() for n in nombres if "(" in n}
    return tuple(_sin_acentos(n.lower()) for n in nombres if n)


def alimentos_no_deseados(perfil: dict) -> set[str]:
    """Canonical food NAMES to soft-exclude because the client said they
    don't want them -- disliked foods and additional restrictions, matched
    directly against each food's own name (English or Spanish, see
    _nombres_para_coincidencia()) rather than a category tag, since "I
    don't like broccoli" is about one specific food, not a whole food
    group. Substring matching both ways (the disliked phrase inside the
    food name, or the food name inside a longer disliked phrase) so both a
    single word ("brócoli") and a fuller sentence ("no me gusta el pescado
    blanco") can match, accent-insensitive. Phrases under 3 characters are
    skipped to avoid accidental short-word collisions."""
    nutricion = perfil.get("nutricion", {})
    frases = [
        _sin_acentos(frase.lower().strip())
        for frase in (nutricion.get("alimentos_que_no_le_gustan", []) + nutricion.get("restricciones", []))
        if len(frase.strip()) >= 3
    ]
    if not frases:
        return set()

    no_deseados = set()
    for alimento in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA + FUENTES_VERDURA:
        nombres = _nombres_para_coincidencia(alimento)
        if any(frase in nombre or nombre in frase for frase in frases for nombre in nombres):
            no_deseados.add(alimento["nombre"])
    return no_deseados


def _etiquetas_a_evitar(perfil: dict) -> set[str]:
    """etiquetas_excluidas() (hard, allergy-driven) plus, when the
    "reducir_gluten" soft preference is active, `gluten` alone -- NOT
    `gluten_trazas`, see preferencias_blandas()'s docstring for why that
    distinction matters."""
    evitar = etiquetas_excluidas(perfil)
    if "reducir_gluten" in preferencias_blandas(perfil):
        evitar = evitar | {"gluten"}
    return evitar


def _tryhard(perfil: dict) -> bool:
    return perfil.get("experiencia", {}).get("nivel_compromiso") == "tryhard"


def fuentes_proteina_para(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    evitar = _etiquetas_a_evitar(perfil)
    no_deseados = alimentos_no_deseados(perfil)
    tryhard = _tryhard(perfil)
    return [
        f["nombre"] for f in FUENTES_PROTEINA
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & evitar) and f["nombre"] not in no_deseados
        and (tryhard or not f.get("nicho", False))
    ]


def fuentes_carbohidrato_para(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    evitar = _etiquetas_a_evitar(perfil)
    no_deseados = alimentos_no_deseados(perfil)
    tryhard = _tryhard(perfil)
    return [
        f["nombre"] for f in FUENTES_CARBOHIDRATO
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & evitar) and f["nombre"] not in no_deseados
        and (tryhard or not f.get("nicho", False))
    ]


def fuentes_grasa_para(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    evitar = _etiquetas_a_evitar(perfil)
    no_deseados = alimentos_no_deseados(perfil)
    tryhard = _tryhard(perfil)
    return [
        f["nombre"] for f in FUENTES_GRASA
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & evitar) and f["nombre"] not in no_deseados
        and (tryhard or not f.get("nicho", False))
    ]


def fuentes_verdura_para(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    evitar = _etiquetas_a_evitar(perfil)
    no_deseados = alimentos_no_deseados(perfil)
    tryhard = _tryhard(perfil)
    return [
        f["nombre"] for f in FUENTES_VERDURA
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & evitar) and f["nombre"] not in no_deseados
        and (tryhard or not f.get("nicho", False))
    ]
