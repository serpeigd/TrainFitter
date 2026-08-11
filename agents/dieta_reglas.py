"""
Rule engine that generates the diet draft WITHOUT calling any LLM.

Translates the method's values (docs/base_conocimiento/nutricion.md and
sinergias_nutrientes.md) into code: caloric needs calculation, protein by
goal, flexible dieting by diet type/allergies, and absorption-synergy tips
when applicable (e.g. vegetarian diet -> iron + vitamin C).

Same as rutina_reglas.py: free, no LLM, same output schema an equivalent
LLM engine would use (see ENTREGAR_BORRADOR_DIETA_TOOL in diet_agent.py).
Deterministic *per client* (see variacion.py) rather than 100%
deterministic outright — the numeric macros are always a direct
calculation from the client's own data, but the narrative phrasing
(distribucion_comidas, mensaje_para_el_cliente) is picked from a few
equivalent variants seeded by id_cliente, so two different clients no
longer read identical boilerplate — see docs/decisiones.md.

Also builds an actual 7-day meal plan (breakfast/lunch/dinner + snacks,
see agents/planificador_comidas.py) from the same macro targets and the
client's own filtered food candidates — "plan_semanal" below — rather
than stopping at flat "suggested sources" lists. Same per-client-seeded
determinism as the rest of this module (a dedicated RNG namespace so it
never shifts what the narrative-text RNG would have picked).
"""

from food_bank import (
    _sin_acentos,
    fuentes_carbohidrato_para,
    fuentes_grasa_para,
    fuentes_proteina_para,
    fuentes_verdura_para,
    preferencias_blandas,
)
from planificador_comidas import generar_plan_semanal
from variacion import elegir_variante, rng_para_cliente

# g of protein per kg of body weight, by goal (docs/base_conocimiento/nutricion.md,
# in turn backed by Morton et al. 2018 and the ISSN's 2017 position stand: muscle
# gain plateaus at ~1.6 g/kg/day, and the ISSN considers 1.4-2.0 g/kg/day sufficient
# for most people who train). A value within those ranges is used as a starting
# point (method §0: a reasonable default, not a fixed law).
PROTEINA_G_POR_KG = {
    "hipertrofia": 2.0,
    "recomposicion_corporal": 2.0,
    "perdida_grasa": 1.8,
    "salud_general": 1.4,  # "general health" here implies training regularly, not sedentary
}

# Caloric adjustment on top of estimated expenditure, by goal.
AJUSTE_CALORICO = {
    "hipertrofia": 0.10,        # slight surplus
    "recomposicion_corporal": -0.05,  # mild deficit
    "perdida_grasa": -0.18,     # moderate deficit, never aggressive (method §3)
    "salud_general": 0.0,       # maintenance
}

PORCENTAJE_GRASA_CALORIAS = 0.27

# Commitment-level personalization (experiencia.nivel_compromiso, added
# alongside rutina_reglas.py's own AJUSTE_SERIES_POR_COMPROMISO -- see
# docs/decisiones.md): scales AJUSTE_CALORICO's magnitude, not its sign --
# "tryhard" never turns a mild deficit into a crash diet, it pushes toward
# the more assertive end of what the method already considers moderate
# (perdida_grasa: -18% normal -> ~-23% tryhard, still short of the
# "aggressive" deficits the method explicitly warns against). "chill" is
# the mirror: a gentler, easier-to-sustain version of the same direction.
# "normal" (the default) is 1.0 -- a no-op, so existing clients are
# unaffected. salud_general's 0.0 adjustment stays 0.0 regardless (there's
# no direction to scale).
AJUSTE_COMPROMISO_MULTIPLICADOR = {"chill": 0.6, "normal": 1.0, "tryhard": 1.3}

# Display-only label for the goal, used when building the human-readable
# "resumen_enfoque" text (the schema value itself stays in Spanish — see
# docs/decisiones.md). Bilingual since generar_borrador_dieta_reglas() now
# accepts an `idioma` parameter for this narrative text.
OBJETIVO_LABELS = {
    "en": {
        "hipertrofia": "hypertrophy",
        "perdida_grasa": "fat loss",
        "recomposicion_corporal": "body recomposition",
        "salud_general": "general health",
    },
    "es": {
        "hipertrofia": "hipertrofia",
        "perdida_grasa": "pérdida de grasa",
        "recomposicion_corporal": "recomposición corporal",
        "salud_general": "salud general",
    },
}

# Equivalent phrasings picked per client via variacion.elegir_variante() —
# same reasoning as rutina_reglas.py's PROGRESION_VARIANTES: every variant
# says the same thing (flexible, no forbidden foods, built for the long
# run) in the trainer's voice, just worded differently so different
# clients don't read byte-identical text. {comidas_al_dia} is filled in
# after picking. See docs/decisiones.md.
DISTRIBUCION_VARIANTES = {
    "en": [
        "Spread these calories across {n} meals throughout the day, with protein present in "
        "all of them. They don't need to be exactly equal — just fit your actual routine.",
        "Split this total across {n} meals a day, making sure protein shows up in each one. "
        "The exact split matters less than it fitting around your actual schedule.",
        "Break this down into {n} meals over the day, protein in every one of them. Don't "
        "stress about splitting the calories evenly — build it around your real routine, not "
        "the other way around.",
        "Divide this across {n} meals, each one with some protein in it. How you split it is "
        "flexible — the only thing that matters is that it actually fits your day.",
    ],
    "es": [
        "Reparte estas calorías en {n} comidas a lo largo del día, con proteína presente en "
        "todas ellas. No hace falta que sean exactamente iguales — solo que encajen en tu "
        "rutina real.",
        "Divide este total en {n} comidas al día, asegurándote de que la proteína aparezca en "
        "cada una. El reparto exacto importa menos que encajar de verdad en tu horario real.",
        "Distribúyelo en {n} comidas durante el día, con proteína en todas ellas. No te agobies "
        "por repartir las calorías a partes iguales — que se adapte a tu rutina real, no al "
        "revés.",
        "Reparte esto en {n} comidas, cada una con algo de proteína. Cómo lo dividas es "
        "flexible — lo único que importa es que encaje de verdad en tu día.",
    ],
}

# Same idea for the closing client message: the greeting ("Hi {name}, " /
# "Hola {name}, ") stays fixed and is prepended separately, so every
# variant here starts lowercase, mid-sentence.
MENSAJE_CLIENTE_DIETA_VARIANTES = {
    "en": [
        "this is your draft diet. There's no forbidden food here: it's about amounts and "
        "context. The idea is that you can keep this up in three months, not just this week. "
        "If something doesn't fit your day-to-day, tell me and we'll swap it for something "
        "equivalent.",
        "this is your first draft diet. Nothing on here is off-limits — it's a question of how "
        "much and how often, not what. This needs to still work for you in three months, not "
        "just this week, so if anything doesn't fit your routine, tell me and we'll find an "
        "equivalent swap.",
        "here's your draft diet. No food is banned in this approach — amounts and context do "
        "the work. Judge it by whether you could still be doing this in three months, not "
        "whether it's perfect today. Anything that clashes with your day-to-day, let me know "
        "and we'll trade it for something equivalent.",
        "this is your diet draft. Think amounts and context, not forbidden foods — nothing here "
        "is off the table. What matters is whether it holds up three months from now, not just "
        "this week. If something doesn't fit your life, say so and we'll swap it for an "
        "equivalent.",
    ],
    "es": [
        "esta es tu dieta en borrador. Aquí no hay alimentos prohibidos: se trata de cantidades "
        "y contexto. La idea es que puedas mantenerla durante tres meses, no solo esta semana. "
        "Si algo no encaja en tu día a día, dímelo y lo cambiamos por algo equivalente.",
        "esta es tu primer borrador de dieta. Aquí nada está prohibido — es cuestión de cuánto "
        "y con qué frecuencia, no de qué. Tiene que seguir funcionándote dentro de tres meses, "
        "no solo esta semana, así que si algo no encaja en tu rutina, dímelo y buscamos un "
        "cambio equivalente.",
        "aquí tienes tu dieta en borrador. En este enfoque no se prohíbe ningún alimento — lo "
        "importante son las cantidades y el contexto. Júzgala por si podrías seguir así dentro "
        "de tres meses, no por si es perfecta hoy. Cualquier cosa que choque con tu día a día, "
        "dímelo y la cambiamos por algo equivalente.",
        "esta es tu dieta en borrador. Piensa en cantidades y contexto, no en alimentos "
        "prohibidos — aquí no se descarta nada. Lo que importa es si aguanta dentro de tres "
        "meses, no si es perfecta hoy. Si algo no encaja en tu vida, dímelo y lo cambiamos por "
        "algo equivalente.",
    ],
}


def _bmr(peso_kg: float, altura_cm: float, edad: int, sexo: str) -> float:
    """Mifflin-St Jeor equation (standard basal metabolic rate estimate)."""
    base = 10 * peso_kg + 6.25 * altura_cm - 5 * edad
    return base + 5 if sexo == "hombre" else base - 161


def _factor_actividad(perfil: dict) -> float:
    dias_entreno = perfil["disponibilidad"]["dias_por_semana"]
    pasos = perfil.get("estilo_de_vida", {}).get("pasos_diarios_aprox", 0)

    factor = 1.55 if dias_entreno >= 5 else 1.375 if dias_entreno >= 3 else 1.2
    if pasos >= 10000:
        factor += 0.10
    elif pasos >= 7000:
        factor += 0.05
    return factor


def _calcular_necesidades(perfil: dict) -> dict:
    datos = perfil["datos_basicos"]
    objetivo = perfil["objetivo"]["principal"]

    nivel_compromiso = perfil.get("experiencia", {}).get("nivel_compromiso", "normal")
    multiplicador_compromiso = AJUSTE_COMPROMISO_MULTIPLICADOR.get(nivel_compromiso, 1.0)

    bmr = _bmr(datos["peso_kg"], datos["altura_cm"], datos["edad"], datos["sexo"])
    tdee = bmr * _factor_actividad(perfil)
    ajuste = AJUSTE_CALORICO.get(objetivo, 0.0) * multiplicador_compromiso
    calorias_objetivo = tdee * (1 + ajuste)

    g_por_kg = PROTEINA_G_POR_KG.get(objetivo, 1.6)
    proteina_g = datos["peso_kg"] * g_por_kg
    grasa_g = (calorias_objetivo * PORCENTAJE_GRASA_CALORIAS) / 9
    calorias_restantes = calorias_objetivo - (proteina_g * 4) - (grasa_g * 9)
    carbohidratos_g = max(calorias_restantes, 0) / 4

    return {
        "calorias_objetivo_kcal": round(calorias_objetivo),
        "macros": {
            "proteina_g": round(proteina_g),
            "grasa_g": round(grasa_g),
            "carbohidratos_g": round(carbohidratos_g),
        },
    }


def _consejos_por_preferencias_blandas(perfil: dict, idioma: str = "en") -> list[str]:
    """Explains WHY the weekly plan leans a certain way whenever a soft
    preference (food_bank.preferencias_blandas()) is active -- the same
    "never a silent, unexplained adjustment" principle already applied to
    rutina_reglas.py's stress/sleep and session-length notes. Purely
    informational: these never trigger advertencias_revision_humana (see
    that function below), since none of this is a safety concern.

    The antiinflamatorio tip's own food list is diet-type aware: oily fish
    is only ever a candidate for omnivore clients (food_bank.py's
    tipos_dieta filter already excludes it for vegetarian/vegan clients),
    so naming it unconditionally would describe foods a vegetarian/vegan
    client's plan could never actually contain."""
    preferencias = preferencias_blandas(perfil)
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    if idioma == "es":
        fuentes_antiinflamatorias = (
            "pescado azul, aceite de oliva, frutos secos/semillas" if tipo_dieta == "omnivora"
            else "aceite de oliva, aguacate, frutos secos/semillas"
        )
        textos = {
            "reducir_gluten": (
                "Has pedido bajar el gluten: el pan, la pasta integral y el seitán se han dejado "
                "fuera de las fuentes sugeridas (la avena se mantiene — solo tiene trazas, no gluten "
                "en sí)."
            ),
            "antiinflamatorio": (
                f"Has pedido un enfoque antiinflamatorio: el plan prioriza {fuentes_antiinflamatorias} "
                "y verdura y fruta de colores intensos."
            ),
            "estres_alto_o_sueno_bajo": (
                "Dado el estrés/sueño que declaraste, el plan prioriza fuentes ricas en magnesio "
                "(legumbres, frutos secos, semillas, quinoa)."
            ),
            "trabajo_sedentario": (
                "Con un trabajo poco activo, el plan prioriza fuentes con más fibra (legumbres, "
                "avena, integrales, verdura) para ayudar con la saciedad y la digestión."
            ),
        }
    else:
        textos = {
            "reducir_gluten": (
                "You asked to lower gluten: bread, whole wheat pasta, and seitan were left out of "
                "the suggested sources (oats stay in — only trace amounts, not gluten itself)."
            ),
            "antiinflamatorio": (
                f"You asked for an anti-inflammatory approach: this plan leans on "
                f"{'oily fish, olive oil, nuts/seeds' if tipo_dieta == 'omnivora' else 'olive oil, avocado, nuts/seeds'}, "
                "and deeply colored vegetables and fruit."
            ),
            "estres_alto_o_sueno_bajo": (
                "Given the stress/sleep you reported, this plan leans on magnesium-rich sources "
                "(legumes, nuts, seeds, quinoa)."
            ),
            "trabajo_sedentario": (
                "With a mostly sedentary job, this plan leans on higher-fiber sources (legumes, "
                "oats, whole grains, vegetables) to help with satiety and digestion."
            ),
        }
    return [textos[p] for p in ("reducir_gluten", "antiinflamatorio", "estres_alto_o_sueno_bajo", "trabajo_sedentario") if p in preferencias]


# Evidence-based supplement tips (docs/base_conocimiento/suplementacion.md),
# only ever surfaced in "tryhard" mode (see AJUSTE_COMPROMISO_MULTIPLICADOR
# above) -- deliberately short, generic dose/timing basics, not a
# personalized protocol. The real safety-relevant check (supplements +
# medication together -> enhanced review) lives in validator_agent.py.
_SUPLEMENTOS_TRYHARD_TEXTOS = {
    "en": {
        "creatina": (
            "Creatine monohydrate, 3-5 g/day, any time, taken consistently -- the best-backed "
            "strength/muscle supplement there is."
        ),
        "proteina_polvo": (
            "A whey or plant protein powder is a convenient way to hit your protein target if food "
            "alone doesn't get you there -- not essential if it already does."
        ),
        "cafeina": (
            "3-6 mg/kg about 45-60 min before training can help performance -- avoid it too close to "
            "bedtime, since sleep is the foundation everything else depends on."
        ),
    },
    "es": {
        "creatina": (
            "Creatina monohidrato, 3-5 g/día, a cualquier hora, tomada de forma constante -- el "
            "suplemento con más respaldo para fuerza/masa muscular que existe."
        ),
        "proteina_polvo": (
            "Un suplemento de proteína (whey o vegetal) es una forma cómoda de llegar a tu objetivo "
            "de proteína si la comida sola no basta -- no es imprescindible si ya llegas."
        ),
        "cafeina": (
            "3-6 mg/kg unos 45-60 min antes de entrenar puede ayudar al rendimiento -- evítala cerca "
            "de la hora de dormir, ya que el sueño es la base de la que depende todo lo demás."
        ),
    },
}
_PALABRAS_CLAVE_SUPLEMENTO = {
    "creatina": ("creatina", "creatine"),
    "proteina_polvo": ("proteina en polvo", "protein powder", "whey", "proteina"),
    "cafeina": ("cafeina", "caffeine"),
}


def _consejos_suplementos(perfil: dict, idioma: str = "en") -> list[str]:
    """Skips any supplement the client already listed in
    salud.suplementos_actuales (bilingual, accent-insensitive match, same
    technique as food_bank.alimentos_no_deseados()) -- no point
    "recommending" creatine to someone who already takes it."""
    if perfil.get("experiencia", {}).get("nivel_compromiso") != "tryhard":
        return []

    ya_toma = _sin_acentos(" ".join(perfil.get("salud", {}).get("suplementos_actuales", [])).lower())
    return [
        _SUPLEMENTOS_TRYHARD_TEXTOS[idioma][clave]
        for clave, palabras in _PALABRAS_CLAVE_SUPLEMENTO.items()
        if not any(_sin_acentos(palabra) in ya_toma for palabra in palabras)
    ]


def _consejos_sinergias(perfil: dict, idioma: str = "en") -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")

    if idioma == "es":
        consejos = [
            "Las vitaminas D, E, K y los omega-3 se absorben mejor si se toman con la comida "
            "del día que tenga más grasa saludable (nunca en ayunas)."
        ]
        if tipo_dieta in {"vegetariana_ovolacto", "vegana"}:
            consejos.append(
                "La mayor parte de tu hierro viene de fuentes vegetales (no hemo), que se absorben "
                "peor: combina lentejas/espinacas con una fuente de vitamina C en la misma comida "
                "(pimiento rojo, limón, kiwi) — puede multiplicar la absorción de 3 a 6 veces."
            )
            consejos.append(
                "Deja pasar al menos 1-2 horas entre el café o el té y tus comidas principales ricas "
                "en hierro: los taninos reducen significativamente su absorción."
            )
        if tipo_dieta == "vegetariana_ovolacto":
            consejos.append(
                "Combinar legumbres con huevo o lácteos en la misma comida mejora cómo tu cuerpo "
                "aprovecha el zinc y el hierro."
            )
        return consejos

    consejos = [
        "Vitamins D, E, K and omega-3s are absorbed better when taken with the day's "
        "meal with the most healthy fat (never on an empty stomach)."
    ]
    if tipo_dieta in {"vegetariana_ovolacto", "vegana"}:
        consejos.append(
            "Most of your iron comes from plant sources (non-heme), which absorb less "
            "well: combine lentils/spinach with a vitamin C source in the same meal "
            "(red pepper, lemon, kiwi) — it can multiply absorption 3-6x."
        )
        consejos.append(
            "Keep coffee or tea at least 1-2 hours away from your main iron-rich meals: "
            "tannins significantly reduce iron absorption."
        )
    if tipo_dieta == "vegetariana_ovolacto":
        consejos.append(
            "Combining legumes with egg or dairy in the same meal improves how well "
            "your body can use the zinc and iron."
        )

    return consejos


def _generar_advertencias(perfil: dict, idioma: str = "en") -> list[str]:
    """Enhanced-review reasons from a nutritional standpoint (method §8)."""
    salud = perfil.get("salud", {})
    advertencias = []

    if idioma == "es":
        for alergia in salud.get("alergias_alimentarias", []):
            advertencias.append(
                f"Alergia alimentaria declarada: {alergia}. Confirma que está totalmente excluida "
                "antes de enviarse — una alergia mal gestionada puede ser grave."
            )
        for condicion in salud.get("enfermedades_o_condiciones", []):
            advertencias.append(f"Condición de salud declarada: {condicion}. Revisión reforzada antes de enviarse.")

        embarazo = salud.get("embarazo_o_lactancia", {})
        if embarazo.get("aplica"):
            advertencias.append(
                f"El/la cliente está embarazada o en periodo de lactancia ({embarazo.get('detalle', '')}). "
                "Las necesidades nutricionales cambian; requiere ajuste y el visto bueno de un profesional."
            )
        for medicacion in salud.get("medicacion_habitual", []):
            advertencias.append(f"Medicación habitual declarada: {medicacion}. Revisa posibles interacciones con la dieta.")

        notas_analitica = salud.get("analitica_adjunta", {}).get("notas", "")
        if notas_analitica and not salud.get("analitica_adjunta", {}).get("tiene"):
            advertencias.append(
                f"El cliente no ha adjuntado analítica, pero hay una nota relevante sin verificar: "
                f"\"{notas_analitica}\" — pídela en el seguimiento para poder modular la dieta con datos reales."
            )
        return advertencias

    for alergia in salud.get("alergias_alimentarias", []):
        advertencias.append(
            f"Declared food allergy: {alergia}. Confirm it's fully excluded before sending "
            "— a poorly managed allergy can be serious."
        )
    for condicion in salud.get("enfermedades_o_condiciones", []):
        advertencias.append(f"Declared health condition: {condicion}. Enhanced review before sending.")

    embarazo = salud.get("embarazo_o_lactancia", {})
    if embarazo.get("aplica"):
        advertencias.append(
            f"Client is pregnant/breastfeeding ({embarazo.get('detalle', '')}). Nutritional "
            "needs change; requires adjustment and professional sign-off."
        )
    for medicacion in salud.get("medicacion_habitual", []):
        advertencias.append(f"Declared regular medication: {medicacion}. Review possible interactions with the diet.")

    notas_analitica = salud.get("analitica_adjunta", {}).get("notas", "")
    if notas_analitica and not salud.get("analitica_adjunta", {}).get("tiene"):
        advertencias.append(
            f"The client hasn't attached bloodwork, but there's a relevant unverified note: "
            f"\"{notas_analitica}\" — ask for it at follow-up so the diet can be modulated with real data."
        )

    return advertencias


def generar_borrador_dieta_reglas(perfil_cliente: dict, idioma: str = "en") -> dict:
    """Generates the full diet draft by applying the rule engine.

    Args:
        perfil_cliente: dict with the same schema as examples/cliente_ejemplo_*.json.
        idioma: "en" (default) or "es" — language of the narrative text
            (resumen_enfoque, distribucion_comidas, mensaje_para_el_cliente,
            consejos_sinergias, advertencias). Food NAMES in
            fuentes_*_sugeridas are always the canonical English value
            regardless of `idioma` — see food_bank.py's module docstring for
            why (the validator's allergy cross-check depends on it).
            ui/app.py translates food names for on-screen display
            separately, via food_bank.nombre_mostrado(). plan_semanal's own
            prose descriptions are the one exception to "food names stay
            English": unlike fuentes_*_sugeridas, nothing safety-critical
            string-matches against plan_semanal's text (validator_agent.py
            only ever reads the flat *_sugeridas lists), so
            planificador_comidas.py translates food names for display right
            there via food_bank.nombre_mostrado() -- same helper, just
            applied a step earlier than pdf_generador.py normally would.
    """
    nombre = perfil_cliente["datos_basicos"]["nombre"]
    objetivo = perfil_cliente["objetivo"]["principal"]
    comidas_al_dia = perfil_cliente.get("nutricion", {}).get("comidas_al_dia_preferidas", 4)

    necesidades = _calcular_necesidades(perfil_cliente)

    # Same client -> same picks every time (seeded by id_cliente); a
    # different client with an otherwise-similar profile gets a different,
    # but equally on-voice, phrasing. Separate namespace from
    # rutina_reglas.py's own RNGs so the two engines' picks never correlate.
    rng_texto = rng_para_cliente(perfil_cliente, "dieta:texto")
    distribucion = elegir_variante(rng_texto, DISTRIBUCION_VARIANTES[idioma]).format(n=comidas_al_dia)
    cuerpo_mensaje = elegir_variante(rng_texto, MENSAJE_CLIENTE_DIETA_VARIANTES[idioma])

    # Separate RNG namespace from rng_texto above -- picking meals never
    # shifts which narrative-text variant gets picked, and vice versa.
    rng_plan = rng_para_cliente(perfil_cliente, "dieta:plan_semanal")
    plan_semanal = generar_plan_semanal(perfil_cliente, necesidades, comidas_al_dia, idioma, rng_plan)

    nivel_compromiso = perfil_cliente.get("experiencia", {}).get("nivel_compromiso", "normal")

    if idioma == "es":
        resumen = (
            f"Estimación de {necesidades['calorias_objetivo_kcal']} kcal/día para "
            f"{OBJETIVO_LABELS['es'].get(objetivo, objetivo.replace('_', ' '))}, "
            f"con {necesidades['macros']['proteina_g']} g de proteína como prioridad. Es un punto de "
            "partida que se ajusta según el peso y la energía reales durante las primeras semanas."
        )
        if nivel_compromiso == "tryhard":
            resumen += (
                " Modo tryhard: el ritmo hacia tu objetivo es algo más exigente, e incluye "
                "alimentos y consejos de suplementación más específicos."
            )
        elif nivel_compromiso == "chill":
            resumen += " Modo chill: el ritmo hacia tu objetivo es más suave, para que sea más fácil de sostener."
        mensaje_para_el_cliente = f"Hola {nombre.split()[0]}, {cuerpo_mensaje}"
    else:
        resumen = (
            f"Estimated {necesidades['calorias_objetivo_kcal']} kcal/day for "
            f"{OBJETIVO_LABELS['en'].get(objetivo, objetivo.replace('_', ' '))}, "
            f"with {necesidades['macros']['proteina_g']} g of protein as the priority. It's a starting point "
            "that gets adjusted based on real weight and energy over the first few weeks."
        )
        if nivel_compromiso == "tryhard":
            resumen += (
                " Tryhard mode: the pace toward your goal is a bit more demanding, and includes "
                "more specific foods and supplement tips."
            )
        elif nivel_compromiso == "chill":
            resumen += " Chill mode: the pace toward your goal is gentler, to make it easier to sustain."
        mensaje_para_el_cliente = f"Hi {nombre.split()[0]}, {cuerpo_mensaje}"

    return {
        "resumen_enfoque": resumen,
        "calorias_objetivo_kcal": necesidades["calorias_objetivo_kcal"],
        "macros": necesidades["macros"],
        "comidas_al_dia": comidas_al_dia,
        "distribucion_comidas": distribucion,
        "fuentes_proteina_sugeridas": fuentes_proteina_para(perfil_cliente),
        "fuentes_carbohidrato_sugeridas": fuentes_carbohidrato_para(perfil_cliente),
        "fuentes_grasa_sugeridas": fuentes_grasa_para(perfil_cliente),
        "fuentes_verdura_sugeridas": fuentes_verdura_para(perfil_cliente),
        "plan_semanal": plan_semanal,
        "consejos_sinergias": (
            _consejos_sinergias(perfil_cliente, idioma)
            + _consejos_por_preferencias_blandas(perfil_cliente, idioma)
            + _consejos_suplementos(perfil_cliente, idioma)
        ),
        "advertencias_revision_humana": _generar_advertencias(perfil_cliente, idioma),
        "mensaje_para_el_cliente": mensaje_para_el_cliente,
    }
