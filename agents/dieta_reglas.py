"""
Rule engine that generates the diet draft WITHOUT calling any LLM.

Translates the method's values (docs/base_conocimiento/nutricion.md and
sinergias_nutrientes.md) into code: caloric needs calculation, protein by
goal, flexible dieting by diet type/allergies, and absorption-synergy tips
when applicable (e.g. vegetarian diet -> iron + vitamin C).

Same as rutina_reglas.py: 100% deterministic, free, same output schema an
equivalent LLM engine would use (see ENTREGAR_BORRADOR_DIETA_TOOL in
diet_agent.py).
"""

from food_bank import fuentes_carbohidrato_para, fuentes_grasa_para, fuentes_proteina_para

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

# Display-only English label for the goal, used when building the
# human-readable "resumen_enfoque" text (the schema value itself stays
# in Spanish — see docs/decisiones.md).
OBJETIVO_LABELS = {
    "hipertrofia": "hypertrophy",
    "perdida_grasa": "fat loss",
    "recomposicion_corporal": "body recomposition",
    "salud_general": "general health",
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

    bmr = _bmr(datos["peso_kg"], datos["altura_cm"], datos["edad"], datos["sexo"])
    tdee = bmr * _factor_actividad(perfil)
    ajuste = AJUSTE_CALORICO.get(objetivo, 0.0)
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


def _consejos_sinergias(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
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


def _generar_advertencias(perfil: dict) -> list[str]:
    """Enhanced-review reasons from a nutritional standpoint (method §8)."""
    salud = perfil.get("salud", {})
    advertencias = []

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


def generar_borrador_dieta_reglas(perfil_cliente: dict) -> dict:
    """Generates the full diet draft by applying the rule engine."""
    nombre = perfil_cliente["datos_basicos"]["nombre"]
    objetivo = perfil_cliente["objetivo"]["principal"]
    comidas_al_dia = perfil_cliente.get("nutricion", {}).get("comidas_al_dia_preferidas", 4)

    necesidades = _calcular_necesidades(perfil_cliente)

    resumen = (
        f"Estimated {necesidades['calorias_objetivo_kcal']} kcal/day for "
        f"{OBJETIVO_LABELS.get(objetivo, objetivo.replace('_', ' '))}, "
        f"with {necesidades['macros']['proteina_g']} g of protein as the priority. It's a starting point "
        "that gets adjusted based on real weight and energy over the first few weeks."
    )

    distribucion = (
        f"Spread these calories across {comidas_al_dia} meals throughout the day, with protein present "
        "in all of them. They don't need to be exactly equal — just fit your actual routine."
    )

    mensaje_para_el_cliente = (
        f"Hi {nombre.split()[0]}, this is your draft diet. There's no forbidden food here: "
        "it's about amounts and context. The idea is that you can keep this up in three months, not just "
        "this week. If something doesn't fit your day-to-day, tell me and we'll swap it for something equivalent."
    )

    return {
        "resumen_enfoque": resumen,
        "calorias_objetivo_kcal": necesidades["calorias_objetivo_kcal"],
        "macros": necesidades["macros"],
        "comidas_al_dia": comidas_al_dia,
        "distribucion_comidas": distribucion,
        "fuentes_proteina_sugeridas": fuentes_proteina_para(perfil_cliente),
        "fuentes_carbohidrato_sugeridas": fuentes_carbohidrato_para(perfil_cliente),
        "fuentes_grasa_sugeridas": fuentes_grasa_para(perfil_cliente),
        "consejos_sinergias": _consejos_sinergias(perfil_cliente),
        "advertencias_revision_humana": _generar_advertencias(perfil_cliente),
        "mensaje_para_el_cliente": mensaje_para_el_cliente,
    }
