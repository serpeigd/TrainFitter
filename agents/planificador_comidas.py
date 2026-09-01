"""
Weekly meal planner for the free diet rule engine (dieta_reglas.py).

Turns the macro targets dieta_reglas.py already computes (calorias_objetivo_kcal,
macros) plus the client's own filtered food candidates (food_bank.py's
fuentes_*_para()) into an actual 7-day plan of breakfast/lunch/dinner(/snacks)
-- not just flat lists of "suggested sources" -- while staying 100% free,
deterministic *per client* (same seeded-RNG convention as variacion.py), and
never introducing a food the client's diet type or allergies would exclude.

DESIGN — portion math is a deliberate approximation, not a clinical
calculator: every food's macros_100g in food_bank.py is a standard
reference value (like a nutrition label), and each meal's kcal budget comes
from splitting the day's target across meals by a fixed weight (mains get
more than snacks). Grams are then solved directly from the day's own
protein/carb/fat kcal ratio applied to that meal's kcal budget. This is the
same "estimate first, adjust from real progress" philosophy
dieta_reglas.py's own client message already states explicitly
(docs/base_conocimiento/nutricion.md: sustainable and close-enough beats
"optimal on paper") -- it is not trying to be gram-perfect.

DESIGN — synergy pairing is mechanical, not just listed as a tip: when a
meal's protein pick carries food_bank.py's "hierro_no_hemo" tag (a plant
iron source), the vegetable/fruit slot for that same meal is filtered down
to a "vitamina_c" pick specifically, and the meal's own description says so
-- turning docs/base_conocimiento/sinergias_nutrientes.md's "non-heme iron +
vitamin C, same meal" row into something that actually happens in the
generated plan, not just a separate static tip elsewhere in the draft
(dieta_reglas.py's existing consejos_sinergias still covers the pairings
that aren't practical to force structurally, e.g. tea/coffee timing).
Dinner deliberately gets the day's largest share of fat for the same
reason -- "vitamin D/E/K and omega-3s with the day's fattiest meal."

DESIGN — the synergy pairing above (and dieta_reglas.py's own
consejos_sinergias) is gated to `experiencia.nivel_compromiso` "avanzado"/
"tryhard" (see `aplicar_sinergias` below and docs/decisiones.md) --
"basico"/"normal" still get a real, macro-matched, profile-adapted meal
(the fat-heavier-dinner WEIGHT itself is a distribution choice, not a
"synergy," so it still applies at every level), just without the
vitamin-C pairing or its explanatory sentence. `_sesgar_por_nivel_compromiso()`
is the mirror on the food-SELECTION side: "basico" leans the actual food
picks toward food_bank.py's "comun"-tagged (recognizable, everyday)
options, "avanzado" leans the other way toward the "comun": False
specialty ones (tofu, tempeh, quinoa...) -- a real middle step toward
"tryhard"'s own "nicho" foods, without touching that pool directly.
Bias, not exclusion, same "prefer, don't force" pattern as
`_sesgar_por_preferencias()` right below it.

DESIGN — vegetables/fruit are a flat, fixed portion (not solved from the
macro targets): they're a fiber/micronutrient/synergy role, not one of the
three tracked macros (method §0: protein first, fat/carb split what's
left) -- keeping them out of the gram-solving math avoids a four-way
optimization for a handful of extra kcal that "aprox_kcal" already signals
as approximate.

DESIGN — soft preferences bias selection, they never exclude on their own
(gluten is the one exception, and even that exclusion happens upstream in
food_bank.py, not here): food_bank.preferencias_blandas() detects things
like "wants an anti-inflammatory approach," "reported high stress or low
sleep," or "sedentary job" and this module narrows a food category's
candidates toward a matching sinergias tag (antiinflamatorio/magnesio/
fibra_alta) MOST of the time, not always -- see
_sesgar_por_preferencias() -- so a full week still shows some variety
instead of looping the same few foods. Falls back to the unfiltered list
whenever narrowing would leave nothing, same "prefer, don't exclude"
pattern already used for the vitamin-C pairing above.

DESIGN — safety stays with food_bank.py's existing filters, not a second
copy of them: every food this module ever picks comes from
fuentes_proteina_para(perfil)/fuentes_carbohidrato_para(perfil)/
fuentes_grasa_para(perfil)/fuentes_verdura_para(perfil) -- the exact same,
already-allergy-and-diet-type-filtered candidate pools dieta_reglas.py's
own fuentes_*_sugeridas lists are built from. There is no separate path
into the raw FUENTES_* banks here, so this module cannot suggest a food the
client's declared allergies would have excluded -- and validator_agent.py's
existing cross-check (which reads those same *_sugeridas lists) keeps
covering every food this planner could ever use, with no changes needed
there beyond adding the new vegetable list to what it checks.
"""

import math
import random

from food_bank import (
    INDICE_ALIMENTOS,
    fuentes_carbohidrato_para,
    fuentes_grasa_para,
    fuentes_proteina_para,
    fuentes_verdura_para,
    nombre_mostrado,
    preferencias_blandas,
)

DIAS_SEMANA = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "es": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"],
}

ETIQUETA_COMIDA = {
    "en": {"desayuno": "Breakfast", "comida": "Lunch", "cena": "Dinner", "snack": "Snack"},
    "es": {"desayuno": "Desayuno", "comida": "Comida", "cena": "Cena", "snack": "Snack"},
}

# One short, genuinely useful prep tip per common protein/carb -- direct
# request ("platos preparados estilo wetaca... opcional: añadir cominos
# para mejorar digestion... cualquier consejo o sinergia"). Deliberately
# NOT exhaustive (every food in food_bank.py would need one): covers the
# proteins/carbs common enough to show up often, real cooking/nutrition
# advice rather than filler, kept separate from dieta_reglas.py's own
# consejos_sinergias (which stays about macro-timing, not prep technique).
# Keyed by the canonical English "nombre" (checked before display
# translation, same convention as everywhere else in this module),
# protein checked before carb so a meal with both never shows two tips.
CONSEJOS_COCINA = {
    "Lentils": {
        "es": "añade comino al cocinarlas — ayuda a la digestión y reduce la hinchazón.",
        "en": "add cumin while cooking — it helps digestion and cuts down on bloating.",
    },
    "Chickpeas": {
        "es": "añade comino al cocinarlos — ayuda a la digestión y reduce la hinchazón.",
        "en": "add cumin while cooking — it helps digestion and cuts down on bloating.",
    },
    "Chicken breast": {
        "es": "marínala con limón y especias antes de cocinar — más sabor sin añadir calorías.",
        "en": "marinate it in lemon and spices before cooking — more flavor, no added calories.",
    },
    "Turkey": {
        "es": "marínalo con limón y especias antes de cocinar — más sabor sin añadir calorías.",
        "en": "marinate it in lemon and spices before cooking — more flavor, no added calories.",
    },
    "Salmon / oily fish": {
        "es": "un chorro de limón antes de servir realza el sabor y aporta vitamina C.",
        "en": "a squeeze of lemon before serving brings out the flavor and adds vitamin C.",
    },
    "Oily fish (EPA/DHA)": {
        "es": "un chorro de limón antes de servir realza el sabor y aporta vitamina C.",
        "en": "a squeeze of lemon before serving brings out the flavor and adds vitamin C.",
    },
    "Rice": {
        "es": "cocínalo y déjalo enfriar antes de comer — el almidón resistente que se forma cuida mejor tu microbiota.",
        "en": "cook it and let it cool before eating — the resistant starch that forms is better for your gut bacteria.",
    },
    "Potato / sweet potato": {
        "es": "cocínala y enfríala antes de comer, igual que el arroz — mismo efecto de almidón resistente.",
        "en": "cook and cool it before eating, same trick as rice — same resistant-starch effect.",
    },
    "Broccoli": {
        "es": "cocínalo al vapor en vez de hervido — conserva muchas más vitaminas.",
        "en": "steam it instead of boiling it — it keeps far more of its vitamins.",
    },
    "Spinach": {
        "es": "saltéala brevemente con un poco de aceite — ayuda a absorber mejor sus vitaminas liposolubles.",
        "en": "sauté it briefly in a little oil — helps you absorb its fat-soluble vitamins better.",
    },
    "Eggs": {
        "es": "no descartes la yema — es donde está la mayoría de las vitaminas.",
        "en": "don't skip the yolk — that's where most of the vitamins are.",
    },
    "Oats": {
        "es": "déjala en remojo toda la noche (overnight oats) — más digestiva y no hace falta cocinarla.",
        "en": "soak it overnight (overnight oats) — easier to digest and no cooking needed.",
    },
    "Quinoa": {
        "es": "enjuágala bien antes de cocinar — quita el sabor amargo natural de la saponina.",
        "en": "rinse it well before cooking — it removes the natural bitter taste from its saponins.",
    },
    "Tofu": {
        "es": "prénsalo unos minutos antes de cocinar — absorbe mucho mejor el marinado.",
        "en": "press it for a few minutes before cooking — it soaks up marinade far better.",
    },
    "Greek yogurt / whipped fresh cheese": {
        "es": "elige la versión natural sin azucarar — el sabor lo pone la fruta, no el azúcar añadido.",
        "en": "pick the plain, unsweetened version — the fruit already brings the sweetness.",
    },
    "Whole wheat pasta": {
        "es": "cocínala al dente — tiene un índice glucémico más bajo que si se pasa de cocción.",
        "en": "cook it al dente — it has a lower glycemic index than if it's overcooked.",
    },
}


def _consejo_cocina(proteina_nombre: str, carbohidrato_nombre: str, idioma: str) -> str:
    """Protein checked before carb -- a meal with a tip-worthy pick in both
    slots only ever shows one, staying a single "optional" line rather than
    stacking. Returns "" when neither ingredient has a curated tip (not
    every combination needs one -- see CONSEJOS_COCINA's own docstring)."""
    for nombre in (proteina_nombre, carbohidrato_nombre):
        if nombre in CONSEJOS_COCINA:
            return CONSEJOS_COCINA[nombre][idioma]
    return ""


# Curated, real dish names for the most common protein+carb combinations --
# same "curated, not exhaustive" convention as CONSEJOS_COCINA above. Keyed
# by (canonical English carb name, canonical English protein name), the
# same names food_bank.py uses (never displayed directly -- see module
# docstring). Direct follow-up request ("diseña platos concretos
# saludables y dale nombre a la receta"): with 10+ proteins x 10+ carbs,
# hand-authoring every combination isn't proportionate, but the pairings a
# client will actually see most often (the everyday proteins/carbs) now
# read as a genuine recipe name, not just an ingredient list with a colon
# after it. Anything outside this table still falls back to
# _nombrar_plato()'s original mechanical construction below.
NOMBRES_PLATO_CURADOS = {
    ("Rice", "Chicken breast"): {"es": "Arroz con pollo", "en": "Chicken and rice bowl"},
    ("Potato / sweet potato", "Chicken breast"): {"es": "Pollo asado con patatas", "en": "Roast chicken with potatoes"},
    ("Whole wheat pasta", "Chicken breast"): {
        "es": "Pollo salteado con pasta integral", "en": "Chicken stir-fry with whole wheat pasta",
    },
    ("Rice", "Salmon / oily fish"): {"es": "Salmón al horno con arroz", "en": "Baked salmon with rice"},
    ("Quinoa", "Salmon / oily fish"): {"es": "Bowl de salmón y quinoa", "en": "Salmon and quinoa bowl"},
    ("Potato / sweet potato", "Lean beef"): {"es": "Estofado de ternera con patatas", "en": "Beef stew with potatoes"},
    ("Rice", "Lean beef"): {"es": "Ternera salteada con arroz", "en": "Beef stir-fry with rice"},
    ("Whole wheat pasta", "Turkey"): {
        "es": "Boloñesa de pavo con pasta integral", "en": "Turkey bolognese with whole wheat pasta",
    },
    ("Rice", "Chickpeas"): {"es": "Curry de garbanzos con arroz", "en": "Chickpea curry with rice"},
    ("Rice", "Lentils"): {"es": "Guiso de lentejas con arroz", "en": "Lentil stew with rice"},
    ("Whole wheat bread", "Eggs"): {"es": "Tostada con huevos revueltos", "en": "Scrambled eggs on toast"},
    ("Oats", "Greek yogurt / whipped fresh cheese"): {
        "es": "Bowl de avena y yogur griego", "en": "Greek yogurt oat bowl",
    },
    ("Quinoa", "Tofu"): {"es": "Bowl de tofu y quinoa", "en": "Tofu and quinoa bowl"},
    ("Rice", "Tofu"): {"es": "Tofu salteado con arroz", "en": "Stir-fried tofu with rice"},
    ("Potato / sweet potato", "White fish (hake, sole)"): {
        "es": "Pescado al horno con patatas", "en": "Baked fish with potatoes",
    },
    ("Rice", "White fish (hake, sole)"): {"es": "Pescado a la plancha con arroz", "en": "Grilled fish with rice"},
    # Added alongside the "franjas" fix (see food_bank.py's own DESIGN note)
    # -- these combos only became common now that breakfast/snack protein
    # and carb picks are actually breakfast-appropriate, instead of
    # sometimes landing on something like lentils or broccoli.
    ("Assorted fruit", "Greek yogurt / whipped fresh cheese"): {
        "es": "Yogur griego con fruta", "en": "Greek yogurt with fruit",
    },
    ("Oats", "Protein powder (plant-based)"): {"es": "Porridge de avena con proteína", "en": "Protein oatmeal"},
    ("Assorted fruit", "Protein powder (plant-based)"): {
        "es": "Batido de proteína con fruta", "en": "Fruit protein shake",
    },
    ("Whole wheat pasta", "Salmon / oily fish"): {"es": "Pasta integral con salmón", "en": "Salmon pasta"},
    ("Quinoa", "Chicken breast"): {"es": "Bowl de pollo y quinoa", "en": "Chicken and quinoa bowl"},
    ("Potato / sweet potato", "Tofu"): {"es": "Tofu con boniato asado", "en": "Tofu with roasted sweet potato"},
    ("Whole wheat pasta", "Tofu"): {"es": "Pasta integral con tofu", "en": "Tofu pasta"},
    ("Rice", "Turkey"): {"es": "Pavo salteado con arroz", "en": "Turkey stir-fry with rice"},
    ("Quinoa", "Lentils"): {"es": "Quinoa con lentejas", "en": "Lentil quinoa bowl"},
    ("Potato / sweet potato", "Turkey"): {"es": "Pavo asado con patatas", "en": "Roast turkey with potatoes"},
}


def _nombrar_plato(nombre_carb_canonico: str, nombre_prot_canonico: str, idioma: str) -> str:
    """A curated real dish name for common combinations (NOMBRES_PLATO_CURADOS,
    Wetaca-style: "Arroz con pollo", not just an ingredient list) -- direct
    follow-up request. Falls back to the original mechanical "carb con
    proteína" construction (canonical names translated for display via
    nombre_mostrado()) for any combination outside that curated table, so
    every meal still gets a real name even for the long tail of less
    common pairings, and this reads naturally for those too."""
    curado = NOMBRES_PLATO_CURADOS.get((nombre_carb_canonico, nombre_prot_canonico))
    if curado:
        return curado[idioma]
    nombre_carb = nombre_mostrado(nombre_carb_canonico, idioma)
    nombre_prot = nombre_mostrado(nombre_prot_canonico, idioma)
    if idioma == "es":
        return f"{nombre_carb} con {nombre_prot.lower()}"
    return f"{nombre_prot} with {nombre_carb.lower()}"

# Relative "weight" each meal slot gets of the day's total kcal -- mains
# (breakfast/lunch/dinner) are 3x heavier than any extra snack slot, a
# simple, deterministic split rather than a fixed percentage table per
# possible comidas_al_dia value.
PESO_KCAL_PRINCIPAL = 1.5
PESO_KCAL_SNACK = 0.5

# Dinner gets the day's largest share of fat on purpose (see module
# docstring); breakfast/lunch/snacks share the rest, weighted toward lunch.
PESO_GRASA_POR_COMIDA = {"desayuno": 0.10, "comida": 0.25, "cena": 0.55, "snack": 0.10}

# Real, reported bug ("avena + lentejas" makes no sense, and a live-
# verified case of broccoli turning up as a breakfast "fruit"): a plain
# rng.choice() across each category's FULL candidate pool doesn't know a
# lentil stew isn't a breakfast food, or that broccoli isn't a fruit.
# food_bank.py's curated "franjas" tag (defaults to {"principal"} -- see
# its own DESIGN note) now governs every category uniformly. This
# replaces two narrower, category-specific fixes that used to live here
# separately: whole-cut savory proteins/fats excluded from desayuno/
# snack, and -- the actual gap that let broccoli slip in -- no filter on
# vegetables at all.
def _candidatos_para_franja(candidatos: dict, franja: str) -> dict:
    """Filters every food category (protein/carb/fat/veg) down to foods
    tagged appropriate for this meal-slot franja ("desayuno" covers both
    breakfast and snack; "principal" covers lunch and dinner). Falls back
    to the unfiltered list, per category, whenever that filter would
    leave nothing to choose from (never happens today -- every diet type
    keeps at least eggs/yogurt/protein-powder for desayuno protein and
    olive oil/avocado/nuts/seeds for desayuno fat -- but this guards a
    future food-bank entry from ever making a franja unsatisfiable)."""
    return {
        categoria: (
            [c for c in lista if franja in INDICE_ALIMENTOS[c].get("franjas", {"principal"})] or lista
        )
        for categoria, lista in candidatos.items()
    }


# A SEPARATE axis from "franjas" above -- not "is this breakfast-
# appropriate" but "is this dense enough to be a meal's PRIMARY carb
# without solving out to an absurd portion." Real, live-caught regression:
# treating "franja == desayuno" as if it meant "small kcal budget" (like
# the original comment on this exclusion assumed) was wrong -- Breakfast
# carries the same PESO_KCAL_PRINCIPAL weight as lunch/dinner, only Snack
# is actually small (PESO_KCAL_SNACK), so "Assorted fruit" as Breakfast's
# carb solved out to 400g+ again, the exact bug this was meant to prevent.
# Keyed by `tipo` itself (not `franja`), applied on top of the franja
# filter above, whenever tipo != "snack".
CARBOHIDRATOS_SOLO_SNACK = {"Assorted fruit"}


def _excluir_carbohidratos_no_densos(candidatos: dict, tipo: str) -> dict:
    if tipo == "snack":
        return candidatos
    denso = [c for c in candidatos["carbohidrato"] if c not in CARBOHIDRATOS_SOLO_SNACK]
    return {**candidatos, "carbohidrato": denso or candidatos["carbohidrato"]}


# Soft preference tag (food_bank.preferencias_blandas()) -> the sinergias
# tag to bias meal-food selection toward. "reducir_gluten" is deliberately
# absent here: that one is already a hard exclusion applied upstream by
# food_bank.py's fuentes_*_para(), not a bias -- by the time candidatos
# reaches this module, gluten-tagged foods are already gone from it.
SESGO_POR_PREFERENCIA = {
    "antiinflamatorio": "antiinflamatorio",
    "estres_alto_o_sueno_bajo": "magnesio",
    "trabajo_sedentario": "fibra_alta",
    "salud_digestiva": "probiotico",
    "mas_fibra": "fibra_alta",
    "mas_hierro": "hierro_no_hemo",
}


def _sesgar_por_preferencias(candidatos_categoria: list[str], preferencias: set[str], rng: random.Random) -> list[str]:
    """Narrows one food category's candidates toward whichever
    SESGO_POR_PREFERENCIA tags are active, most (not all) of the time --
    a consistent bias across the week rather than every single meal
    forced into the same handful of foods, which would read as
    repetitive rather than personalized. Falls back to the untouched
    list when no candidate carries any active tag (a diet-type/allergy
    combination that happens to exclude all of them for this slot)."""
    etiquetas_activas = {SESGO_POR_PREFERENCIA[p] for p in preferencias if p in SESGO_POR_PREFERENCIA}
    if not etiquetas_activas or not candidatos_categoria:
        return candidatos_categoria
    preferidos = [c for c in candidatos_categoria if INDICE_ALIMENTOS[c]["sinergias"] & etiquetas_activas]
    if preferidos and rng.random() < 0.75:
        return preferidos
    return candidatos_categoria


# Same bias strength as _sesgar_por_preferencias() above (0.75) -- a
# client-set "what are you in the mood for" answer deserves to show up
# clearly, not just occasionally, while still leaving room for variety
# (a full week that's 100% one cuisine would read as repetitive, not
# personalized).
PROBABILIDAD_PREFERIR_ESTILO_COCINA = 0.75


def _sesgar_por_estilo_cocina(candidatos_categoria: list[str], estilo: str | None, rng: random.Random) -> list[str]:
    """Narrows one food category's candidates toward food_bank.py's
    "estilo_cocina" tag matching the client's own portal answer -- see
    that module's DESIGN note. Same bias-not-force shape as
    _sesgar_por_preferencias(): falls back to the untouched list when no
    preference is set, or when none of this category's candidates happen
    to carry the requested style (most categories/slots won't -- only
    ~30 foods across the whole bank are tagged at all)."""
    if not estilo or not candidatos_categoria:
        return candidatos_categoria
    preferidos = [c for c in candidatos_categoria if estilo in INDICE_ALIMENTOS[c].get("estilo_cocina", set())]
    if preferidos and rng.random() < PROBABILIDAD_PREFERIR_ESTILO_COCINA:
        return preferidos
    return candidatos_categoria


# Same bias-not-force pattern as _sesgar_por_preferencias() above.
# "basico"'s pull toward "comun" is strong and deliberate -- it's meant to
# read as consistently simple/everyday, not just occasionally. "avanzado"
# leans the OPPOSITE direction (toward specialty items -- tofu, tempeh,
# quinoa...), a real middle step toward "tryhard"'s true "nicho" foods,
# but weaker than "basico"'s pull -- confirmed directly rather than left
# as a no-op (see docs/decisiones.md).
PROBABILIDAD_PREFERIR_COMUN = 0.85
PROBABILIDAD_PREFERIR_NO_COMUN = 0.5


def _sesgar_por_nivel_compromiso(
    candidatos_categoria: list[str], nivel_compromiso: str | None, rng: random.Random, preferencias: set[str] = frozenset(),
) -> list[str]:
    """"basico" leans this category's picks toward food_bank.py's
    "comun" entries (recognizable, everyday foods); "avanzado" leans
    toward the "comun": False ones (specialty, but still not "nicho" --
    that stays tryhard-exclusive). Both bias, never exclude: fall back to
    the untouched list when no candidate on the wanted side exists for
    this slot (e.g. a vegan client's only protein options are all
    specialty), or when nivel_compromiso is "normal"/"tryhard" (a no-op
    for both -- "tryhard" already gets true "nicho" foods separately, see
    food_bank.py's fuentes_*_para()).

    "tiempo_o_presupuesto_limitado" (food_bank.preferencias_blandas(),
    set from the "poco tiempo para cocinar"/"presupuesto ajustado" preset
    dropdowns -- see ui/app.py's nutrition-context/job-type fields) leans
    the SAME direction as "basico" -- common, everyday foods tend to also
    be the quicker and cheaper ones, since there's no separate prep-time
    or price data in food_bank.py to bias on directly. Only applies when
    nivel_compromiso isn't already pulling the opposite way ("avanzado"):
    an explicit commitment-level choice outranks an inferred lifestyle
    signal."""
    if not candidatos_categoria:
        return candidatos_categoria
    if nivel_compromiso == "basico" or (
        nivel_compromiso != "avanzado" and "tiempo_o_presupuesto_limitado" in preferencias
    ):
        comunes = [c for c in candidatos_categoria if INDICE_ALIMENTOS[c].get("comun", True)]
        if comunes and rng.random() < PROBABILIDAD_PREFERIR_COMUN:
            return comunes
    elif nivel_compromiso == "avanzado":
        no_comunes = [c for c in candidatos_categoria if not INDICE_ALIMENTOS[c].get("comun", True)]
        if no_comunes and rng.random() < PROBABILIDAD_PREFERIR_NO_COMUN:
            return no_comunes
    return candidatos_categoria


# Probability a matching liked meal actually gets reused, mirroring
# _sesgar_por_preferencias()'s own bias-not-force philosophy: a client who
# liked a meal should see it come back often, not have it locked to every
# occurrence of that slot for the rest of time (see PROBABILIDAD_REPETIR_FAVORITO
# for why "often" specifically).
PROBABILIDAD_REPETIR_FAVORITO = 0.6

# How many times _construir_comida() re-rolls a meal slot before giving up
# and accepting a disliked combo anyway -- see that function's own comment.
# Bounded so a client with a small candidate pool (e.g. strict allergies)
# who's disliked most of it still gets a real plan.
MAX_INTENTOS_EVITAR_NO_DESEADA = 5


def _sesgar_por_favoritos(tipo: str, candidatos: dict, comidas_favoritas: list[dict], rng: random.Random) -> dict | None:
    """Looks for a client-liked meal (see docs/decisiones.md's "repeat a
    meal" feature -- comidas_favoritas comes from the client portal, via
    perfil["nutricion"]["comidas_favoritas"]) matching this slot's tipo,
    whose protein/carb/fat picks are ALL still valid candidates here --
    an allergy or diet-type change since the meal was liked correctly
    drops it rather than resurrecting a now-unsafe pick, since `candidatos`
    is already food_bank.py's allergy/diet-filtered pool by the time this
    runs. Bias, not a hard lock: returns one matching favorite (picked
    jointly across categories, not independently per category -- otherwise
    the exact liked combination would rarely reappear intact) roughly
    PROBABILIDAD_REPETIR_FAVORITO of the time a match exists; None
    otherwise, so the caller falls through to its normal independent
    per-category selection."""
    candidatas = [
        fav for fav in comidas_favoritas
        if fav.get("tipo") == tipo
        and (not fav.get("proteina") or fav["proteina"] in candidatos["proteina"])
        and (not fav.get("carbohidrato") or fav["carbohidrato"] in candidatos["carbohidrato"])
        and (not fav.get("grasa") or fav["grasa"] in candidatos["grasa"])
    ]
    if not candidatas or rng.random() >= PROBABILIDAD_REPETIR_FAVORITO:
        return None
    return rng.choice(candidatas)

# Flat, fixed vegetable/fruit portions (grams) -- not solved from macros,
# see module docstring.
PORCION_VERDURA_PRINCIPAL_G = 100
PORCION_FRUTA_SNACK_G = 80


def _slots_del_dia(comidas_al_dia: int) -> list[str]:
    """Always breakfast/lunch/dinner; anything beyond 3 becomes extra snack
    slots. comidas_al_dia below 3 still gets the three mains -- a full
    day's plan needs at least that to make nutritional sense."""
    slots = ["desayuno", "comida", "cena"]
    extra = max(0, comidas_al_dia - 3)
    slots += ["snack"] * extra
    return slots


def _pesos_kcal(slots: list[str]) -> list[float]:
    """Total-kcal weight for each slot, in the same order as `slots` (a
    parallel list, not a dict -- multiple slots share the "snack" label, so
    a dict keyed by label alone couldn't keep them distinct)."""
    return [PESO_KCAL_SNACK if s == "snack" else PESO_KCAL_PRINCIPAL for s in slots]


def _pesos_grasa(slots: list[str]) -> list[float]:
    """Fat-kcal weight for each slot, in the same order as `slots` --
    separate from _pesos_kcal() on purpose (see module docstring): fat
    doesn't follow the day's overall meal-size split, dinner gets the
    lion's share regardless. When there's more than one snack slot,
    "snack"'s total PESO_GRASA_POR_COMIDA share is divided evenly across
    all of them rather than given in full to each."""
    num_snacks = slots.count("snack")
    peso_por_snack = PESO_GRASA_POR_COMIDA["snack"] / num_snacks if num_snacks else 0.0
    return [peso_por_snack if s == "snack" else PESO_GRASA_POR_COMIDA[s] for s in slots]


def _elegir_verdura_para_sinergia(candidatos: list[str], requiere_vitamina_c: bool, rng: random.Random) -> str | None:
    """Picks a vegetable/fruit for this meal. When the meal's protein pick
    is a non-heme iron source, narrows the candidates to ones tagged
    "vitamina_c" specifically (the pairing docs/base_conocimiento/
    sinergias_nutrientes.md calls out) -- falling back to any candidate if,
    for some diet/allergy combination, none of the vitamin-C-tagged ones
    are available, rather than silently dropping the vegetable slot."""
    if not candidatos:
        return None
    if requiere_vitamina_c:
        con_vitamina_c = [c for c in candidatos if "vitamina_c" in INDICE_ALIMENTOS[c]["sinergias"]]
        if con_vitamina_c:
            return rng.choice(con_vitamina_c)
    return rng.choice(candidatos)


def _describir_comida_principal(
    tipo: str, proteina: dict, carbohidrato: dict, grasa: dict, verdura: str | None,
    verdura_por_sinergia: bool, aplicar_sinergias: bool, idioma: str,
) -> str:
    # Display-only translation (food_bank.nombre_mostrado()) -- the
    # ingredient-selection/lookup logic in _construir_comida() already ran
    # against the canonical English names before this function is called;
    # only the rendered sentence itself localizes them. See
    # dieta_reglas.generar_borrador_dieta_reglas()'s docstring for why
    # plan_semanal is the one place in this schema where that's safe to do.
    nombre_prot, g_prot = nombre_mostrado(proteina["nombre"], idioma), proteina["gramos"]
    nombre_carb, g_carb = nombre_mostrado(carbohidrato["nombre"], idioma), carbohidrato["gramos"]
    nombre_grasa, g_grasa = nombre_mostrado(grasa["nombre"], idioma), grasa["gramos"]
    verdura = nombre_mostrado(verdura, idioma) if verdura else None
    consejo = _consejo_cocina(proteina["nombre"], carbohidrato["nombre"], idioma)
    plato = _nombrar_plato(carbohidrato["nombre"], proteina["nombre"], idioma)

    if idioma == "es":
        partes = [f"{g_prot}g de {nombre_prot.lower()}", f"{g_carb}g de {nombre_carb.lower()}"]
        if verdura:
            partes.append(f"{PORCION_VERDURA_PRINCIPAL_G}g de {verdura.lower()}")
        descripcion = f"{plato}: " + ", ".join(partes) + f", con {g_grasa}g de {nombre_grasa.lower()}."
        if verdura_por_sinergia:
            descripcion += f" ({verdura} aporta vitamina C para absorber mejor el hierro de {nombre_prot.lower()}.)"
        if tipo == "cena" and aplicar_sinergias:
            descripcion += " (la comida con más grasa del día — mejor momento para vitamina D/E/K y omega-3.)"
        if consejo:
            descripcion += f" Opcional: {consejo}"
        return descripcion

    partes = [f"{g_prot}g {nombre_prot.lower()}", f"{g_carb}g {nombre_carb.lower()}"]
    if verdura:
        partes.append(f"{PORCION_VERDURA_PRINCIPAL_G}g {verdura.lower()}")
    descripcion = f"{plato}: " + ", ".join(partes) + f", with {g_grasa}g {nombre_grasa.lower()}."
    if verdura_por_sinergia:
        descripcion += f" ({verdura} adds vitamin C to help absorb the iron in {nombre_prot.lower()}.)"
    if tipo == "cena" and aplicar_sinergias:
        descripcion += " (today's largest fat portion — best time for vitamin D/E/K and omega-3s.)"
    if consejo:
        descripcion += f" Optional: {consejo}"
    return descripcion


def _describir_desayuno_o_snack(
    tipo: str, proteina: dict, carbohidrato: dict, grasa: dict, fruta: str | None,
    sinergia_probiotica: bool, idioma: str,
) -> str:
    # Display-only translation -- see _describir_comida_principal()'s
    # comment above for why this is the one place plan_semanal departs
    # from "food names stay canonical English."
    nombre_prot, g_prot = nombre_mostrado(proteina["nombre"], idioma), proteina["gramos"]
    nombre_carb, g_carb = nombre_mostrado(carbohidrato["nombre"], idioma), carbohidrato["gramos"]
    nombre_grasa, g_grasa = nombre_mostrado(grasa["nombre"], idioma), grasa["gramos"]
    fruta = nombre_mostrado(fruta, idioma) if fruta else None
    consejo = _consejo_cocina(proteina["nombre"], carbohidrato["nombre"], idioma)
    plato = _nombrar_plato(carbohidrato["nombre"], proteina["nombre"], idioma)

    if idioma == "es":
        partes = [f"{g_carb}g de {nombre_carb.lower()}", f"{g_prot}g de {nombre_prot.lower()}"]
        if fruta:
            partes.append(f"{PORCION_FRUTA_SNACK_G}g de {fruta.lower()}")
        if nombre_grasa:
            partes.append(f"{g_grasa}g de {nombre_grasa.lower()}")
        descripcion = f"{plato}: " + ", ".join(partes) + "."
        if sinergia_probiotica:
            descripcion += " (combo de probióticos + fibra prebiótica.)"
        if consejo:
            descripcion += f" Opcional: {consejo}"
        return descripcion

    partes = [f"{g_carb}g {nombre_carb.lower()}", f"{g_prot}g {nombre_prot.lower()}"]
    if fruta:
        partes.append(f"{PORCION_FRUTA_SNACK_G}g {fruta.lower()}")
    if nombre_grasa:
        partes.append(f"{g_grasa}g {nombre_grasa.lower()}")
    descripcion = f"{plato}: " + ", ".join(partes) + "."
    if sinergia_probiotica:
        descripcion += " (a probiotic + prebiotic-fiber combo.)"
    if consejo:
        descripcion += f" Optional: {consejo}"
    return descripcion


def _requiere_coccion(nombres: list[str | None]) -> bool:
    """Whether this meal needs a stove/oven at all -- True unless EVERY one
    of its actual food picks (protein/carb/fat/veg, None slots skipped)
    carries food_bank.py's curated "sin_coccion" tag. Drives the portal's
    no-cook/quick-cook badge (see _construir_comida()'s "requiere_coccion"
    field) -- a coarse, honest two-tier signal, not a per-recipe prep-time
    estimate this project has no real data for. A lunch/dinner built
    around chicken or lentils still (correctly) reads as needing to cook
    even with an all-raw side salad, since those proteins/carbs aren't
    tagged "sin_coccion"."""
    return any(not INDICE_ALIMENTOS[nombre].get("sin_coccion", False) for nombre in nombres if nombre)


def _construir_comida(
    tipo: str, kcal_objetivo: float, kcal_grasa: float, ratios: dict, candidatos: dict,
    preferencias: set[str], comidas_favoritas: list[dict], comidas_no_deseadas: list[dict],
    nivel_compromiso: str | None, idioma: str, rng: random.Random,
    combos_dia_previos: set[tuple] = frozenset(), estilo_cocina: str | None = None,
) -> dict:
    """Picks foods for one meal slot and scales their portions to roughly
    hit kcal_objetivo, following the day's own protein/carb kcal ratios --
    except fat, whose kcal budget for this specific meal is passed in
    directly as `kcal_grasa` (see generar_plan_semanal()'s _pesos_grasa()
    call) rather than derived from kcal_objetivo, so dinner ends up with
    the day's largest fat portion regardless of what the day's overall fat
    ratio alone would give this one meal by size.

    combos_dia_previos: (proteina, carbohidrato, grasa) tuples already used
    earlier THIS SAME DAY (see generar_plan_semanal()) -- direct request
    ("que no te toque comer y cenar lo mismo el mismo día"). Checked
    alongside comidas_no_deseadas in the same bounded reroll loop below;
    unlike comidas_no_deseadas (which is scoped to one specific tipo), this
    check ignores tipo on purpose -- lunch and dinner landing on the exact
    same protein+carb+fat pick is the case being avoided, even though
    they're different slots."""
    aplicar_sinergias = nivel_compromiso in ("avanzado", "tryhard")
    # See _candidatos_para_franja()'s own docstring for the bug this fixes.
    # "desayuno" covers both breakfast and snack (the same "light meal"
    # bucket this module has always treated them as); everything else is
    # "principal". _excluir_carbohidratos_no_densos() is a SEPARATE,
    # size-based filter layered on top -- see its own comment for why
    # "franja" alone isn't the right axis for that one.
    franja = "desayuno" if tipo in {"desayuno", "snack"} else "principal"
    candidatos = _candidatos_para_franja(candidatos, franja)
    candidatos = _excluir_carbohidratos_no_densos(candidatos, tipo)

    # Soft-preference bias (antiinflamatorio/magnesio/fibra_alta -- see
    # SESGO_POR_PREFERENCIA) applies on top of the realism filters above,
    # to every category that can carry one of those tags. This is driven
    # by the client's own explicit request (inquietud_principal or
    # structured lifestyle signals), so it's NOT gated by nivel_compromiso
    # the way the automatic synergy pairing below is -- a client who asked
    # for an anti-inflammatory approach still gets it at "basico".
    candidatos = {
        "proteina": _sesgar_por_preferencias(candidatos["proteina"], preferencias, rng),
        "carbohidrato": _sesgar_por_preferencias(candidatos["carbohidrato"], preferencias, rng),
        "grasa": _sesgar_por_preferencias(candidatos["grasa"], preferencias, rng),
        "verdura": _sesgar_por_preferencias(candidatos["verdura"], preferencias, rng),
    }
    # The portal's own "¿Qué te apetece?" answer (see food_bank.py's
    # "estilo_cocina" DESIGN note) -- same bias-not-force treatment,
    # applied right after the health-driven preference bias above so an
    # explicit cuisine request still narrows within whatever that left.
    candidatos = {
        categoria: _sesgar_por_estilo_cocina(lista, estilo_cocina, rng) for categoria, lista in candidatos.items()
    }
    # "basico" leans every category toward common/everyday foods (see
    # _sesgar_por_nivel_compromiso()) -- applied after the preference bias
    # above so an explicit request still narrows the field first, common-
    # ness only breaks ties within whatever's left.
    candidatos = {
        categoria: _sesgar_por_nivel_compromiso(lista, nivel_compromiso, rng, preferencias)
        for categoria, lista in candidatos.items()
    }

    # A liked meal (see _sesgar_por_favoritos()) wins the protein/carb/fat
    # picks jointly, when one matches and its own dice roll says so;
    # otherwise every category is chosen independently as before.
    favorita = _sesgar_por_favoritos(tipo, candidatos, comidas_favoritas, rng)
    if favorita:
        proteina_nombre = favorita["proteina"] or rng.choice(candidatos["proteina"])
        carbohidrato_nombre = favorita["carbohidrato"] or rng.choice(candidatos["carbohidrato"])
        grasa_nombre = favorita["grasa"] or (rng.choice(candidatos["grasa"]) if candidatos["grasa"] else None)
    else:
        proteina_nombre = rng.choice(candidatos["proteina"])
        carbohidrato_nombre = rng.choice(candidatos["carbohidrato"])
        grasa_nombre = rng.choice(candidatos["grasa"]) if candidatos["grasa"] else None

    # The client's own "no me gusta" (see notion_connector.
    # agregar_comida_no_deseada()'s docstring for why an exact-combo
    # exclusion is meaningful here, not just symbolic) -- a real exclusion,
    # not a bias: re-roll independently up to MAX_INTENTOS_EVITAR_NO_DESEADA
    # times whenever the picked combo exactly matches a disliked one.
    # Bounded, not "until it's not disliked," so a client who's disliked
    # most of a small candidate pool still gets a real meal rather than an
    # infinite loop -- same "exclude, but never break generation" pattern
    # as every other safety-adjacent filter in this project.
    intentos = 0
    while intentos < MAX_INTENTOS_EVITAR_NO_DESEADA and (
        {
            "tipo": tipo, "proteina": proteina_nombre, "carbohidrato": carbohidrato_nombre, "grasa": grasa_nombre,
        } in comidas_no_deseadas
        or (proteina_nombre, carbohidrato_nombre, grasa_nombre) in combos_dia_previos
    ):
        proteina_nombre = rng.choice(candidatos["proteina"])
        carbohidrato_nombre = rng.choice(candidatos["carbohidrato"])
        grasa_nombre = rng.choice(candidatos["grasa"]) if candidatos["grasa"] else None
        intentos += 1

    kcal_proteina = kcal_objetivo * ratios["proteina"]
    kcal_carbohidrato = kcal_objetivo * ratios["carbohidrato"]

    def _porcion(nombre: str, clave_macro: str, kcal_para_esta_comida: float) -> dict:
        # "gramos" is the FOOD's own portion weight (e.g. grams of chicken
        # breast) -- what the shopping list needs. "gramos_macro" is the
        # actual macro-nutrient content of that portion (clave_macro read
        # from the same macros_100g table food_bank.py already has) -- a
        # real, live-caught bug fix: this function used to accept
        # clave_macro and never read it, so the meal dict's own
        # "proteina_g"/"carbohidrato_g"/"grasa_g" fields (added for the
        # portal's macro chart) were silently the wrong number -- e.g. 94g
        # of tofu (the portion) mislabeled as "94g of protein," when tofu
        # is only ~8g protein per 100g. See generar_lista_compra() for why
        # portion weight is still kept, under its own clearly-named field.
        macros = INDICE_ALIMENTOS[nombre]["macros_100g"]
        kcal_100g = macros["kcal"] or 1  # never actually 0 in this bank; guards a future entry that could be
        gramos = round(max(kcal_para_esta_comida, 0) / kcal_100g * 100)
        gramos_macro = round(macros[clave_macro] * gramos / 100, 1)
        return {"nombre": nombre, "gramos": gramos, "gramos_macro": gramos_macro}

    proteina = _porcion(proteina_nombre, "proteina_g", kcal_proteina)
    carbohidrato = _porcion(carbohidrato_nombre, "carbohidratos_g", kcal_carbohidrato)
    grasa = (
        _porcion(grasa_nombre, "grasa_g", kcal_grasa) if grasa_nombre
        else {"nombre": None, "gramos": 0, "gramos_macro": 0}
    )

    # Gated by aplicar_sinergias -- "basico"/"normal" still pick a valid,
    # macro-matched vegetable/fruit, just not deliberately narrowed to a
    # vitamin-C source for iron absorption (see module docstring).
    requiere_vitamina_c = aplicar_sinergias and "hierro_no_hemo" in INDICE_ALIMENTOS[proteina_nombre]["sinergias"]

    def _kcal_porcion(porcion: dict, alimento_nombre: str | None) -> float:
        if not alimento_nombre:
            return 0.0
        return INDICE_ALIMENTOS[alimento_nombre]["macros_100g"]["kcal"] * porcion["gramos"] / 100

    aprox_kcal = round(
        _kcal_porcion(proteina, proteina_nombre) + _kcal_porcion(carbohidrato, carbohidrato_nombre)
        + _kcal_porcion(grasa, grasa_nombre)
    )

    if tipo in {"desayuno", "snack"}:
        fruta = None
        if candidatos["verdura"] and rng.random() < 0.7:  # not every breakfast/snack needs fruit
            fruta = _elegir_verdura_para_sinergia(candidatos["verdura"], requiere_vitamina_c, rng)
            aprox_kcal += round(INDICE_ALIMENTOS[fruta]["macros_100g"]["kcal"] * PORCION_FRUTA_SNACK_G / 100)
        sinergia_probiotica = aplicar_sinergias and (
            "probiotico" in INDICE_ALIMENTOS[proteina_nombre]["sinergias"]
            and "prebiotico_fibra" in INDICE_ALIMENTOS[carbohidrato_nombre]["sinergias"]
        )
        descripcion = _describir_desayuno_o_snack(tipo, proteina, carbohidrato, grasa, fruta, sinergia_probiotica, idioma)
        # Unified name for the return dict below -- see its own comment for why.
        verdura_extra, gramos_verdura_extra = fruta, (PORCION_FRUTA_SNACK_G if fruta else 0)
    else:
        verdura = _elegir_verdura_para_sinergia(candidatos["verdura"], requiere_vitamina_c, rng) if candidatos["verdura"] else None
        if verdura:
            aprox_kcal += round(INDICE_ALIMENTOS[verdura]["macros_100g"]["kcal"] * PORCION_VERDURA_PRINCIPAL_G / 100)
        verdura_por_sinergia = bool(verdura) and requiere_vitamina_c and "vitamina_c" in INDICE_ALIMENTOS[verdura]["sinergias"]
        descripcion = _describir_comida_principal(
            tipo, proteina, carbohidrato, grasa, verdura, verdura_por_sinergia, aplicar_sinergias, idioma,
        )
        verdura_extra, gramos_verdura_extra = verdura, (PORCION_VERDURA_PRINCIPAL_G if verdura else 0)

    return {
        "tipo": ETIQUETA_COMIDA[idioma][tipo],
        "descripcion": descripcion,
        "aprox_kcal": aprox_kcal,
        # Structured picks, alongside the rendered "descripcion" above --
        # canonical English names (never displayed directly; see module
        # docstring), kept so a client can "like" this exact meal from the
        # portal without this project resorting to parsing food names back
        # out of rendered prose (see docs/decisiones.md). "tipo_interno" is
        # the un-numbered slot key ("snack", not "Snack 2") -- a liked
        # snack should bias ANY snack slot, not one specific position.
        "tipo_interno": tipo,
        "proteina": proteina_nombre,
        "carbohidrato": carbohidrato_nombre,
        "grasa": grasa_nombre,
        # Real macro-nutrient grams (direct request: "que la persona tenga
        # una gráfica o números de los macros... si le interesa") -- what
        # the portal's macro chart sums per day. Fixed bug: these used to
        # hold the FOOD's portion weight instead (see _porcion()'s comment
        # above for the concrete example of how wrong that read).
        "proteina_g": proteina["gramos_macro"],
        "carbohidrato_g": carbohidrato["gramos_macro"],
        "grasa_g": grasa["gramos_macro"],
        # Portion weight (grams of the actual food, e.g. grams of chicken
        # breast) -- what generar_lista_compra() aggregates into a weekly
        # shopping list. verdura_extra/gramos_verdura_extra come from
        # whichever branch above ran (fruit for desayuno/snack, vegetable
        # otherwise) -- None/0 when this meal has no vegetable/fruit slot.
        "proteina_alimento_g": proteina["gramos"],
        "carbohidrato_alimento_g": carbohidrato["gramos"],
        "grasa_alimento_g": grasa["gramos"],
        "verdura": verdura_extra,
        "verdura_alimento_g": gramos_verdura_extra,
        # Portal prep-time/difficulty badge -- direct feature idea from
        # competitor research. motor="llm" doesn't get this field (its
        # plan_semanal schema has no structured per-meal food picks to
        # check food_bank.py's "sin_coccion" tag against) -- same accepted
        # engine asymmetry as the shopping list and same-day-combo guard;
        # ui/app.py's badge rendering already degrades to "no badge" when
        # this key is absent.
        "requiere_coccion": _requiere_coccion([proteina_nombre, carbohidrato_nombre, grasa_nombre, verdura_extra]),
    }


def generar_plan_semanal(perfil: dict, necesidades: dict, comidas_al_dia: int, idioma: str, rng: random.Random) -> list[dict]:
    """Builds a 7-day meal plan (breakfast/lunch/dinner + snacks per
    comidas_al_dia) from the client's own filtered food candidates,
    scaled to roughly hit `necesidades`'s daily kcal/macro targets.

    Args:
        perfil: the client's profile (diet type/allergies -> food_bank.py's
            fuentes_*_para() filters).
        necesidades: {"calorias_objetivo_kcal": int, "macros": {"proteina_g":,
            "carbohidratos_g":, "grasa_g":}} -- dieta_reglas.py's own
            _calcular_necesidades() output.
        comidas_al_dia: from the client's nutrition preferences.
        idioma: "en" or "es" -- day names, meal labels, and descriptions.
        rng: a per-client seeded random.Random (see variacion.py) -- reused
            across all 7 days/meals so two different clients get different
            picks, but regenerating the SAME client reproduces the exact
            same week.

    Returns:
        A list of 7 {"dia": str, "comidas": [{"tipo":, "descripcion":,
        "aprox_kcal":, "tipo_interno":, "proteina":, "carbohidrato":,
        "grasa":}, ...]} dicts, Monday/Lunes first. The last four fields
        are structured (canonical English food names, never displayed
        directly) alongside "descripcion"'s rendered prose -- what lets a
        client "like" a meal from the portal and have it bias a future
        week's plan (see _sesgar_por_favoritos()) without this project
        parsing food names back out of rendered text.

        perfil["nutricion"]["comidas_favoritas"] (optional, portal-written)
        is read here to apply that bias -- absent for a new client.
        perfil["nutricion"]["estilo_cocina_preferido"] (optional, portal-
        written -- see food_bank.py's "estilo_cocina" DESIGN note) is read
        the same way, for the client's own "¿Qué te apetece?" answer.
    """
    candidatos = {
        "proteina": fuentes_proteina_para(perfil),
        "carbohidrato": fuentes_carbohidrato_para(perfil),
        "grasa": fuentes_grasa_para(perfil),
        "verdura": fuentes_verdura_para(perfil),
    }
    # No candidates in a required category (a maximally-restrictive
    # allergy/diet combination) -- return an empty plan rather than
    # crashing; dieta_reglas.py's existing fuentes_*_sugeridas lists and
    # advertencias already surface that situation to the trainer.
    if not candidatos["proteina"] or not candidatos["carbohidrato"]:
        return []

    # Soft preferences (see food_bank.preferencias_blandas()) -- gluten is
    # already excluded from `candidatos` above (a hard exclusion applied
    # by fuentes_*_para() itself), so what's left here only ever biases
    # selection, never excludes.
    preferencias = preferencias_blandas(perfil)
    # Meals the client "liked" from a previous week's plan, via the portal
    # (see docs/decisiones.md) -- absent for a brand-new client, same
    # "no field, no bias" degradation as every other optional signal here.
    comidas_favoritas = perfil.get("nutricion", {}).get("comidas_favoritas") or []
    # The client's own "no me gusta" from the portal (see
    # notion_connector.agregar_comida_no_deseada()) -- excluded, not just
    # downweighted, from this regeneration.
    comidas_no_deseadas = perfil.get("nutricion", {}).get("comidas_no_deseadas") or []
    # The portal's own "¿Qué te apetece?" answer (see food_bank.py's
    # "estilo_cocina" DESIGN note) -- absent (None) for a client who
    # hasn't answered, same "no field, no bias" degradation as every
    # other optional portal-written signal here.
    estilo_cocina = perfil.get("nutricion", {}).get("estilo_cocina_preferido")
    # Drives both _sesgar_por_nivel_compromiso() (food selection) and
    # aplicar_sinergias (pairing/explanatory text) inside _construir_comida()
    # -- read once here, same "no field, defaults to normal" degradation as
    # every other nivel_compromiso read in this project.
    nivel_compromiso = perfil.get("experiencia", {}).get("nivel_compromiso")

    kcal_dia = necesidades["calorias_objetivo_kcal"]
    macros = necesidades["macros"]
    kcal_grasa_dia = macros["grasa_g"] * 9
    ratios = {
        "proteina": (macros["proteina_g"] * 4) / kcal_dia if kcal_dia else 0.25,
        "carbohidrato": (macros["carbohidratos_g"] * 4) / kcal_dia if kcal_dia else 0.45,
    }

    slots = _slots_del_dia(comidas_al_dia)
    pesos_kcal = _pesos_kcal(slots)
    total_peso_kcal = sum(pesos_kcal)
    pesos_grasa = _pesos_grasa(slots)
    total_peso_grasa = sum(pesos_grasa) or 1  # only 0 if every fat candidate list is empty

    plan = []
    for dia in DIAS_SEMANA[idioma]:
        comidas = []
        contador_snack = 0
        # Reset per day -- direct request ("que no te toque comer y cenar
        # lo mismo el mismo día"): each meal built so far today is
        # excluded from the NEXT one's picks (see _construir_comida()'s
        # combos_dia_previos), but a Tuesday repeating Monday's lunch is
        # fine, so this never carries over across days.
        combos_dia = set()
        for tipo, peso_kcal, peso_grasa in zip(slots, pesos_kcal, pesos_grasa):
            kcal_objetivo = kcal_dia * (peso_kcal / total_peso_kcal)
            kcal_grasa = kcal_grasa_dia * (peso_grasa / total_peso_grasa)
            comida = _construir_comida(
                tipo, kcal_objetivo, kcal_grasa, ratios, candidatos, preferencias, comidas_favoritas,
                comidas_no_deseadas, nivel_compromiso, idioma, rng, combos_dia, estilo_cocina,
            )
            combos_dia.add((comida["proteina"], comida["carbohidrato"], comida["grasa"]))
            if tipo == "snack" and slots.count("snack") > 1:
                contador_snack += 1
                comida["tipo"] = f"{comida['tipo']} {contador_snack}"
            comidas.append(comida)
        plan.append({"dia": dia, "comidas": comidas})

    return plan


CATEGORIA_LISTA_COMPRA_LABEL = {
    "en": {"proteina": "Protein", "carbohidrato": "Carbs", "grasa": "Fat", "verdura": "Vegetables & fruit"},
    "es": {"proteina": "Proteína", "carbohidrato": "Carbohidratos", "grasa": "Grasa", "verdura": "Verdura y fruta"},
}

# A shopping list is bought in real-world portions, not exact
# kcal-solved grams -- rounding each total UP to the nearest 50g avoids a
# list that says "buy 483g of chicken," which nobody can actually shop for.
REDONDEO_LISTA_COMPRA_G = 50


def generar_lista_compra(plan_semanal: list[dict], idioma: str) -> list[dict]:
    """Aggregates every distinct food across a full week's plan_semanal
    into a shopping list -- direct feature idea grounded in competitor
    research (Harbiz auto-generates one from its nutrition plans, 2026-08-24).
    Reuses `_construir_comida()`'s own `*_alimento_g` portion-weight fields
    (see that function's own comment for the macro-vs-portion distinction),
    summed across every meal that used that food in that role -- e.g.
    legumes picked as the protein source in one meal and the carb source
    in another produce two separate entries (different shopping quantities
    for different purposes), not one merged line.

    Only meaningful for motor="reglas": the LLM engine's plan_semanal
    doesn't carry these structured per-meal food/gram fields (see
    diet_agent.py's tool schema) -- same accepted engine asymmetry as the
    existing meal-liking feature, not a new gap.

    Returns:
        A list of {"categoria": str, "alimento": str, "gramos_totales": int}
        dicts, sorted by category then by descending weight -- empty for a
        missing/empty plan_semanal (a record saved before this field
        existed, or a client with no diet), never raises.
    """
    totales: dict[tuple[str, str], float] = {}
    for dia in plan_semanal or []:
        for comida in dia.get("comidas", []):
            for categoria, clave_gramos in (
                ("proteina", "proteina_alimento_g"), ("carbohidrato", "carbohidrato_alimento_g"),
                ("grasa", "grasa_alimento_g"), ("verdura", "verdura_alimento_g"),
            ):
                nombre = comida.get(categoria)
                gramos = comida.get(clave_gramos) or 0
                if nombre and gramos:
                    clave = (categoria, nombre)
                    totales[clave] = totales.get(clave, 0) + gramos

    etiquetas = CATEGORIA_LISTA_COMPRA_LABEL[idioma]
    lista = [
        {
            "categoria": etiquetas[categoria],
            "alimento": nombre_mostrado(nombre, idioma),
            "gramos_totales": math.ceil(gramos / REDONDEO_LISTA_COMPRA_G) * REDONDEO_LISTA_COMPRA_G,
        }
        for (categoria, nombre), gramos in totales.items()
    ]
    lista.sort(key=lambda f: (f["categoria"], -f["gramos_totales"]))
    return lista
