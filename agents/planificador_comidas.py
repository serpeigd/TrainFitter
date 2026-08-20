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


def _nombrar_plato(nombre_carb: str, nombre_prot: str, idioma: str) -> str:
    """Wetaca-style named dish ("Lentejas con pollo") instead of just a
    flat ingredient list -- direct request. Mechanical (carb + protein,
    already-translated display names), not a hand-authored name per
    combination: with 10+ proteins x 10+ carbs across 2 languages, a real
    per-combination name database isn't a proportionate build here, and
    this reads naturally for the vast majority of real combinations."""
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

# Whole-cut savory proteins/fats read oddly as a "breakfast" or "snack"
# item (a plain rng.choice() across the full candidate pool picked "salmon
# + potato + salad" for a snack while this module was being built -- not
# unsafe, just an unrealistic-looking suggestion). Excluded from
# desayuno/snack's own candidate pool specifically, falling back to the
# unfiltered pool only if that exclusion would leave nothing to choose
# from (never happens today -- every diet type always keeps at least
# eggs/yogurt/legumes/tofu for protein and olive oil/avocado/nuts/seeds
# for fat -- but this guards a future food-bank entry from ever making
# desayuno/snack unsatisfiable).
PROTEINAS_POCO_TIPICAS_PARA_COMIDA_LIGERA = {
    "Chicken breast", "Turkey", "Lean beef", "White fish (hake, sole)", "Salmon / oily fish",
}
GRASAS_POCO_TIPICAS_PARA_COMIDA_LIGERA = {"Oily fish (EPA/DHA)"}

# The reverse problem, caught by generating a real week and looking at it
# (not by reading the code): "Assorted fruit" is low enough in kcal/100g
# that solving for lunch/dinner's carb kcal budget from it alone produced
# absurd portions (500g+ of fruit as a dinner side). Excluded from
# comida/cena's own carb candidate pool specifically -- it stays available
# for desayuno/snack, where the smaller kcal budget keeps its portion
# plausible (closer to a real piece or two of fruit).
CARBOHIDRATOS_POCO_DENSOS_PARA_COMIDA_PRINCIPAL = {"Assorted fruit"}


def _candidatos_para_comida_principal(candidatos: dict) -> dict:
    carbohidrato_denso = [c for c in candidatos["carbohidrato"] if c not in CARBOHIDRATOS_POCO_DENSOS_PARA_COMIDA_PRINCIPAL]
    return {**candidatos, "carbohidrato": carbohidrato_denso or candidatos["carbohidrato"]}


def _candidatos_para_comida_ligera(candidatos: dict) -> dict:
    proteina_ligera = [c for c in candidatos["proteina"] if c not in PROTEINAS_POCO_TIPICAS_PARA_COMIDA_LIGERA]
    grasa_ligera = [c for c in candidatos["grasa"] if c not in GRASAS_POCO_TIPICAS_PARA_COMIDA_LIGERA]
    return {
        **candidatos,
        "proteina": proteina_ligera or candidatos["proteina"],
        "grasa": grasa_ligera or candidatos["grasa"],
    }


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
    plato = _nombrar_plato(nombre_carb, nombre_prot, idioma)

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
    plato = _nombrar_plato(nombre_carb, nombre_prot, idioma)

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


def _construir_comida(
    tipo: str, kcal_objetivo: float, kcal_grasa: float, ratios: dict, candidatos: dict,
    preferencias: set[str], comidas_favoritas: list[dict], comidas_no_deseadas: list[dict],
    nivel_compromiso: str | None, idioma: str, rng: random.Random,
) -> dict:
    """Picks foods for one meal slot and scales their portions to roughly
    hit kcal_objetivo, following the day's own protein/carb kcal ratios --
    except fat, whose kcal budget for this specific meal is passed in
    directly as `kcal_grasa` (see generar_plan_semanal()'s _pesos_grasa()
    call) rather than derived from kcal_objetivo, so dinner ends up with
    the day's largest fat portion regardless of what the day's overall fat
    ratio alone would give this one meal by size."""
    aplicar_sinergias = nivel_compromiso in ("avanzado", "tryhard")
    # Both filters are about kcal *budget* size, not meal identity: a snack
    # (small budget) is the only slot small enough that "Assorted fruit"
    # alone still yields a plausible portion as its carb pick, so
    # _candidatos_para_comida_principal() applies to every OTHER slot,
    # breakfast included -- the same 500g-of-fruit-for-breakfast problem
    # showed up there too before this covered it. _candidatos_para_comida_
    # ligera() is the opposite split: only breakfast/snack are "light"
    # meals, lunch/dinner keep the full protein/fat pool.
    if tipo in {"desayuno", "snack"}:
        candidatos = _candidatos_para_comida_ligera(candidatos)
    if tipo != "snack":
        candidatos = _candidatos_para_comida_principal(candidatos)

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
    while intentos < MAX_INTENTOS_EVITAR_NO_DESEADA and {
        "tipo": tipo, "proteina": proteina_nombre, "carbohidrato": carbohidrato_nombre, "grasa": grasa_nombre,
    } in comidas_no_deseadas:
        proteina_nombre = rng.choice(candidatos["proteina"])
        carbohidrato_nombre = rng.choice(candidatos["carbohidrato"])
        grasa_nombre = rng.choice(candidatos["grasa"]) if candidatos["grasa"] else None
        intentos += 1

    kcal_proteina = kcal_objetivo * ratios["proteina"]
    kcal_carbohidrato = kcal_objetivo * ratios["carbohidrato"]

    def _porcion(nombre: str, clave_macro: str, kcal_para_esta_comida: float) -> dict:
        macros = INDICE_ALIMENTOS[nombre]["macros_100g"]
        kcal_100g = macros["kcal"] or 1  # never actually 0 in this bank; guards a future entry that could be
        gramos = round(max(kcal_para_esta_comida, 0) / kcal_100g * 100)
        return {"nombre": nombre, "gramos": gramos}

    proteina = _porcion(proteina_nombre, "proteina_g", kcal_proteina)
    carbohidrato = _porcion(carbohidrato_nombre, "carbohidratos_g", kcal_carbohidrato)
    grasa = _porcion(grasa_nombre, "grasa_g", kcal_grasa) if grasa_nombre else {"nombre": None, "gramos": 0}

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
    else:
        verdura = _elegir_verdura_para_sinergia(candidatos["verdura"], requiere_vitamina_c, rng) if candidatos["verdura"] else None
        if verdura:
            aprox_kcal += round(INDICE_ALIMENTOS[verdura]["macros_100g"]["kcal"] * PORCION_VERDURA_PRINCIPAL_G / 100)
        verdura_por_sinergia = bool(verdura) and requiere_vitamina_c and "vitamina_c" in INDICE_ALIMENTOS[verdura]["sinergias"]
        descripcion = _describir_comida_principal(
            tipo, proteina, carbohidrato, grasa, verdura, verdura_por_sinergia, aplicar_sinergias, idioma,
        )

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
        # Grams alongside the bare names above -- direct request ("que la
        # persona tenga una gráfica o números de los macros... si le
        # interesa"): the portal has no other way to total up real protein/
        # carb/fat for a day, since these are the same grams already solved
        # for kcal_objetivo/kcal_grasa above, just not previously surfaced
        # on the returned dict.
        "proteina_g": proteina["gramos"],
        "carbohidrato_g": carbohidrato["gramos"],
        "grasa_g": grasa["gramos"],
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
        for tipo, peso_kcal, peso_grasa in zip(slots, pesos_kcal, pesos_grasa):
            kcal_objetivo = kcal_dia * (peso_kcal / total_peso_kcal)
            kcal_grasa = kcal_grasa_dia * (peso_grasa / total_peso_grasa)
            comida = _construir_comida(
                tipo, kcal_objetivo, kcal_grasa, ratios, candidatos, preferencias, comidas_favoritas,
                comidas_no_deseadas, nivel_compromiso, idioma, rng,
            )
            if tipo == "snack" and slots.count("snack") > 1:
                contador_snack += 1
                comida["tipo"] = f"{comida['tipo']} {contador_snack}"
            comidas.append(comida)
        plan.append({"dia": dia, "comidas": comidas})

    return plan
