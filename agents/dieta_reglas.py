"""
Motor de reglas para generar el borrador de dieta SIN llamar a ningún LLM.

Traduce a código los valores del método (docs/base_conocimiento/nutricion.md y
sinergias_nutrientes.md): cálculo de necesidades calóricas, proteína por
objetivo, dieta flexible según tipo de dieta/alergias, y consejos de sinergias
de absorción cuando aplican (p.ej. dieta vegetariana -> hierro + vitamina C).

Igual que rutina_reglas.py: 100% determinista, gratis, mismo esquema de salida
que usaría un motor LLM equivalente (ver ENTREGAR_BORRADOR_DIETA_TOOL en
diet_agent.py).
"""

from food_bank import fuentes_carbohidrato_para, fuentes_grasa_para, fuentes_proteina_para

# g de proteína por kg de peso corporal, según objetivo (docs/base_conocimiento/nutricion.md).
# Se toma un valor intermedio del rango del método como punto de partida (método §0:
# esto es un default razonable, no ley fija).
PROTEINA_G_POR_KG = {
    "hipertrofia": 2.0,
    "recomposicion_corporal": 2.0,
    "perdida_grasa": 1.8,
    "salud_general": 1.2,
}

# Ajuste calórico sobre el gasto estimado, según objetivo.
AJUSTE_CALORICO = {
    "hipertrofia": 0.10,        # superávit ligero
    "recomposicion_corporal": -0.05,  # déficit suave
    "perdida_grasa": -0.18,     # déficit moderado, nunca agresivo (método §3)
    "salud_general": 0.0,       # mantenimiento
}

PORCENTAJE_GRASA_CALORIAS = 0.27


def _bmr(peso_kg: float, altura_cm: float, edad: int, sexo: str) -> float:
    """Ecuación de Mifflin-St Jeor (estimación estándar del metabolismo basal)."""
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
        "Vitamina D, E, K y omega-3 se absorben mejor si los tomas con la comida que "
        "más grasa saludable tenga del día (nunca en ayunas)."
    ]

    if tipo_dieta in {"vegetariana_ovolacto", "vegana"}:
        consejos.append(
            "Tu hierro viene sobre todo de fuentes vegetales (no-hemo), que se absorbe peor: "
            "combina lentejas/espinacas con una fuente de vitamina C en el mismo plato "
            "(pimiento rojo, limón, kiwi) — puede multiplicar la absorción hasta 3-6 veces."
        )
        consejos.append(
            "Separa el café o el té de tus comidas principales con hierro al menos 1-2 horas: "
            "los taninos reducen mucho su absorción."
        )
    if tipo_dieta == "vegetariana_ovolacto":
        consejos.append(
            "Combinar legumbres con huevo o un lácteo en la misma comida mejora el "
            "aprovechamiento del zinc y del hierro."
        )

    return consejos


def _generar_advertencias(perfil: dict) -> list[str]:
    """Motivos de revisión reforzada desde la óptica nutricional (método §8)."""
    salud = perfil.get("salud", {})
    advertencias = []

    for alergia in salud.get("alergias_alimentarias", []):
        advertencias.append(
            f"Alergia alimentaria declarada: {alergia}. Confirmar exclusión total antes de enviar "
            "— una alergia mal gestionada puede ser grave."
        )
    for condicion in salud.get("enfermedades_o_condiciones", []):
        advertencias.append(f"Condición de salud declarada: {condicion}. Revisión reforzada antes de enviar.")

    embarazo = salud.get("embarazo_o_lactancia", {})
    if embarazo.get("aplica"):
        advertencias.append(
            f"Cliente en embarazo/lactancia ({embarazo.get('detalle', '')}). Las necesidades "
            "nutricionales cambian; requiere ajuste y visto bueno profesional."
        )
    for medicacion in salud.get("medicacion_habitual", []):
        advertencias.append(f"Medicación habitual declarada: {medicacion}. Revisar posibles interacciones con la dieta.")

    notas_analitica = salud.get("analitica_adjunta", {}).get("notas", "")
    if notas_analitica and not salud.get("analitica_adjunta", {}).get("tiene"):
        advertencias.append(
            f"El cliente no adjunta analítica pero hay una nota relevante sin verificar: "
            f"\"{notas_analitica}\" — pídesela en el seguimiento para poder modular la dieta con datos reales."
        )

    return advertencias


def generar_borrador_dieta_reglas(perfil_cliente: dict) -> dict:
    """Genera el borrador de dieta completo aplicando el motor de reglas."""
    nombre = perfil_cliente["datos_basicos"]["nombre"]
    objetivo = perfil_cliente["objetivo"]["principal"]
    comidas_al_dia = perfil_cliente.get("nutricion", {}).get("comidas_al_dia_preferidas", 4)

    necesidades = _calcular_necesidades(perfil_cliente)

    resumen = (
        f"Estimación de {necesidades['calorias_objetivo_kcal']} kcal/día para {objetivo.replace('_', ' ')}, "
        f"con {necesidades['macros']['proteina_g']} g de proteína como prioridad. Es un punto de partida "
        "que se ajusta con el peso y la energía reales de las primeras semanas."
    )

    distribucion = (
        f"Reparte estas calorías en {comidas_al_dia} comidas a lo largo del día, con proteína presente "
        "en todas ellas. No hace falta que sean exactamente iguales — que encajen con tu rutina real."
    )

    mensaje_para_el_cliente = (
        f"Hola {nombre.split()[0]}, este es tu borrador de dieta. No hay alimentos prohibidos aquí: "
        "hay cantidades y contexto. La idea es que puedas mantener esto dentro de tres meses, no solo "
        "esta semana. Si algo no encaja con tu día a día, dímelo y lo cambiamos por algo equivalente."
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
