"""
Rule engine that generates the routine draft WITHOUT calling any LLM.

This is the "free" version of the routine agent: 100% deterministic, no
cost, no API key. It translates the method's default values
(docs/base_conocimiento/entrenamiento.md) into code — split by level/days,
rep ranges basic=5-8 / isolation=10-15 — and adapts exercise selection to
the client's available equipment and declared injuries.

Returns a dict with the same schema the rest of the pipeline expects
(ENTREGAR_BORRADOR_RUTINA_TOOL in routine_agent.py), so it's interchangeable
with the LLM engine without the rest of the system noticing the difference.
"""

from collections import defaultdict

from exercise_bank import EXERCISE_BANK
from perfil_utils import tags_lesiones

# Sets/rest per exercise type, per docs/base_conocimiento/entrenamiento.md.
PARAMETROS_POR_TIPO = {
    "basico": {"series": 4, "repeticiones": "5-8", "descanso_seg": 150},
    "aislamiento": {"series": 3, "repeticiones": "10-15", "descanso_seg": 60},
}

# Which muscle groups get trained on each day type, and whether each slot
# should be basic or isolation (order = order in which they appear in the
# session).
PLANTILLAS_DIA = {
    "Full Body": [
        ("pierna_cuadriceps", "basico"), ("pecho", "basico"), ("espalda", "basico"),
        ("pierna_isquios_gluteo", "aislamiento"), ("hombro", "aislamiento"), ("core", "aislamiento"),
    ],
    "Upper A": [
        ("pecho", "basico"), ("espalda", "basico"), ("hombro", "basico"),
        ("triceps", "aislamiento"), ("biceps", "aislamiento"),
    ],
    "Upper B": [
        ("espalda", "basico"), ("pecho", "basico"), ("hombro", "aislamiento"),
        ("biceps", "aislamiento"), ("triceps", "aislamiento"),
    ],
    "Lower A": [
        ("pierna_cuadriceps", "basico"), ("pierna_isquios_gluteo", "basico"),
        ("pierna_cuadriceps", "aislamiento"), ("pierna_isquios_gluteo", "aislamiento"), ("core", "aislamiento"),
    ],
    "Lower B": [
        ("pierna_isquios_gluteo", "basico"), ("pierna_cuadriceps", "basico"),
        ("gemelos", "aislamiento"), ("core", "aislamiento"),
    ],
    "Push": [
        ("pecho", "basico"), ("hombro", "basico"), ("pecho", "aislamiento"),
        ("triceps", "aislamiento"), ("triceps", "aislamiento"),
    ],
    "Pull": [
        ("espalda", "basico"), ("espalda", "basico"), ("espalda", "aislamiento"),
        ("biceps", "aislamiento"), ("biceps", "aislamiento"),
    ],
    "Legs": [
        ("pierna_cuadriceps", "basico"), ("pierna_isquios_gluteo", "basico"),
        ("pierna_cuadriceps", "aislamiento"), ("pierna_isquios_gluteo", "aislamiento"), ("core", "aislamiento"),
    ],
}

# Display-only English labels for schema values that stay in Spanish
# internally (see docs/decisiones.md) — used just when building the
# human-readable "resumen_enfoque" text, not the returned field values.
NIVEL_LABELS = {"principiante": "beginner", "intermedio": "intermediate", "avanzado": "advanced"}
OBJETIVO_LABELS = {
    "hipertrofia": "hypertrophy",
    "perdida_grasa": "fat loss",
    "recomposicion_corporal": "body recomposition",
    "salud_general": "general health",
}
LESION_TAG_LABELS = {"rodilla": "knee", "hombro": "shoulder", "lumbar": "lower back"}

CALENTAMIENTO_POR_DIA = {
    "Full Body": "5-10 min of general mobility (hips, shoulders, ankles) + 1-2 light sets of the first exercise.",
    "Upper A": "5 min of shoulder and wrist mobility + warm-up sets on the first exercise.",
    "Upper B": "5 min of shoulder and wrist mobility + warm-up sets on the first exercise.",
    "Lower A": "5-10 min of hip, knee, and ankle mobility + warm-up sets before the working load.",
    "Lower B": "5-10 min of hip, knee, and ankle mobility + warm-up sets before the working load.",
    "Push": "5 min of shoulder mobility + warm-up sets on the first exercise.",
    "Pull": "5 min of shoulder and scapular mobility + warm-up sets on the first exercise.",
    "Legs": "5-10 min of hip, knee, and ankle mobility + warm-up sets before the working load.",
}


def _material_cliente(perfil: dict) -> set[str]:
    material = set(perfil.get("disponibilidad", {}).get("material_disponible", []))
    material.add("peso_corporal")  # the body is always available
    return material


def _candidatos(grupo: str, tipo: str, material_cliente: set[str], lesion_tags: set[str]) -> list[dict]:
    return [
        ej for ej in EXERCISE_BANK
        if ej["grupo"] == grupo
        and ej["tipo"] == tipo
        and ej["material"] <= material_cliente
        and not (ej["contraindicaciones"] & lesion_tags)
    ]


def _elegir_split_y_secuencia(dias_por_semana: int) -> tuple[str, list[str]]:
    dias = max(1, min(dias_por_semana, 6))
    if dias <= 3:
        return "full_body", ["Full Body"] * dias
    if dias == 4:
        return "upper_lower", ["Upper A", "Lower A", "Upper B", "Lower B"]
    ciclo = ["Push", "Pull", "Legs"]
    return "push_pull_legs", [ciclo[i % 3] for i in range(dias)]


def _generar_advertencias(perfil: dict) -> list[str]:
    """Translates health signals in the profile into enhanced-review reasons (method §8)."""
    salud = perfil.get("salud", {})
    advertencias = []

    for lesion in salud.get("lesiones", []):
        advertencias.append(
            f"Declared injury ({lesion.get('zona', 'area not specified')}): "
            f"{lesion.get('descripcion', '')} — risky exercises excluded or adapted; "
            "requires the trainer's sign-off before sending."
        )
    for condicion in salud.get("enfermedades_o_condiciones", []):
        advertencias.append(f"Declared health condition: {condicion}. Enhanced review before sending.")

    embarazo = salud.get("embarazo_o_lactancia", {})
    if embarazo.get("aplica"):
        advertencias.append(
            f"Client is pregnant/breastfeeding ({embarazo.get('detalle', '')}). "
            "Requires adaptation and professional sign-off before sending."
        )
    for medicacion in salud.get("medicacion_habitual", []):
        advertencias.append(f"Declared regular medication: {medicacion}. Review possible interactions before sending.")

    return advertencias


def generar_borrador_rutina_reglas(perfil_cliente: dict) -> dict:
    """Generates the full routine draft by applying the rule engine."""
    disponibilidad = perfil_cliente["disponibilidad"]
    objetivo = perfil_cliente["objetivo"]["principal"]
    nivel = perfil_cliente["experiencia"]["nivel"]
    nombre = perfil_cliente["datos_basicos"]["nombre"]

    material_cliente = _material_cliente(perfil_cliente)
    lesion_tags = tags_lesiones(perfil_cliente)
    split, secuencia_dias = _elegir_split_y_secuencia(disponibilidad["dias_por_semana"])

    contador_rotacion: dict[tuple, int] = defaultdict(int)
    sesiones = []
    for indice, tipo_dia in enumerate(secuencia_dias, start=1):
        ejercicios = []
        for grupo, tipo in PLANTILLAS_DIA[tipo_dia]:
            candidatos = _candidatos(grupo, tipo, material_cliente, lesion_tags)
            if not candidatos:
                continue  # no equipment/safe options for this slot: skip it instead of failing
            rotacion = contador_rotacion[(grupo, tipo)]
            ejercicio = candidatos[rotacion % len(candidatos)]
            contador_rotacion[(grupo, tipo)] += 1

            parametros = PARAMETROS_POR_TIPO[tipo]
            notas = ""
            grupos_afectados = {
                "rodilla": {"pierna_cuadriceps", "pierna_isquios_gluteo", "gemelos"},
                "hombro": {"pecho", "espalda", "hombro", "triceps"},
                "lumbar": {"pierna_isquios_gluteo", "core"},
            }
            # Knee note informed by ACL rehab guidelines: restrict high load to
            # a ~0-80° flexion range and dose by perceived effort (RPE), not to
            # failure — see docs/base_conocimiento/seguridad_poblaciones_especiales.md
            notas_por_tag = {
                "rodilla": (
                    "Chosen because it's more tolerable for your knee injury. Work in a "
                    "controlled range (avoid very deep flexion) at a moderate effort (you "
                    "could probably do 2-3 more reps than listed); stop if you feel joint "
                    "pain, not just muscle fatigue."
                ),
                "hombro": "Chosen because it's more tolerable for your shoulder; control the range of motion and stop if it hurts.",
                "lumbar": "Chosen because it's more tolerable for your lower back; prioritize technique over load and stop if it hurts.",
            }
            tags_aplicables = [tag for tag in lesion_tags if grupo in grupos_afectados.get(tag, set())]
            if tags_aplicables:
                notas = notas_por_tag[tags_aplicables[0]]
            ejercicios.append({
                "nombre": ejercicio["nombre"],
                "series": parametros["series"],
                "repeticiones": parametros["repeticiones"],
                "descanso_seg": parametros["descanso_seg"],
                "notas": notas,
            })

        sesiones.append({
            "dia": f"Day {indice} — {tipo_dia}",
            "grupos_musculares": sorted({grupo for grupo, _ in PLANTILLAS_DIA[tipo_dia]}),
            "calentamiento": CALENTAMIENTO_POR_DIA[tipo_dia],
            "ejercicios": ejercicios,
            "cardio_opcional": (
                "Zone 2 cardio (comfortable pace, you can hold a conversation), 30-40 min."
                if indice == len(secuencia_dias) else ""
            ),
        })

    resumen = (
        f"'{split.replace('_', ' ')}' split for {NIVEL_LABELS.get(nivel, nivel)} level, "
        f"{disponibilidad['dias_por_semana']} days/week, geared toward "
        f"{OBJETIVO_LABELS.get(objetivo, objetivo.replace('_', ' '))}. Exercises selected based on "
        "the client's available equipment"
    )
    if lesion_tags:
        etiquetas_legibles = sorted(LESION_TAG_LABELS.get(tag, tag) for tag in lesion_tags)
        resumen += f" and adapted for a declared injury in: {', '.join(etiquetas_legibles)}."
    else:
        resumen += "."

    progresion = (
        "Progressive overload: each session, try to add one more rep while keeping good "
        "technique. Once you hit the top of the range on every set of an exercise, add a "
        "little weight and go back to the bottom of the range. No changing the routine every "
        "week — sticking with the same scheme is what actually drives progress."
    )

    mensaje_para_el_cliente = (
        f"Hi {nombre.split()[0]}, here's your first draft routine. Let's go step by step: "
        "technique first, weight later — your body learns before it forces. It doesn't need "
        "to be perfect the first week; what matters is that you can repeat it. If you have any "
        "questions, or if something hurts (not just feels tough), let me know and we'll adjust it."
    )

    return {
        "resumen_enfoque": resumen,
        "nivel_asumido": nivel,
        "split": split,
        "dias_por_semana": disponibilidad["dias_por_semana"],
        "duracion_sesion_min": disponibilidad["minutos_por_sesion"],
        "advertencias_revision_humana": _generar_advertencias(perfil_cliente),
        "sesiones": sesiones,
        "progresion": progresion,
        "mensaje_para_el_cliente": mensaje_para_el_cliente,
    }
