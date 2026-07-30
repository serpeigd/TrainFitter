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

# Display-only labels for schema values that stay in Spanish internally
# (see docs/decisiones.md) — used just when building the human-readable
# "resumen_enfoque"/"dia" text, not the returned field values that other
# code matches against (nivel, split, contraindicaciones tags, etc. are
# untouched). Bilingual since generar_borrador_rutina_reglas() now accepts
# an `idioma` parameter for this narrative text — see that function.
NIVEL_LABELS = {
    "en": {"principiante": "beginner", "intermedio": "intermediate", "avanzado": "advanced"},
    "es": {"principiante": "principiante", "intermedio": "intermedio", "avanzado": "avanzado"},
}
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
LESION_TAG_LABELS = {
    "en": {"rodilla": "knee", "hombro": "shoulder", "lumbar": "lower back"},
    "es": {"rodilla": "rodilla", "hombro": "hombro", "lumbar": "zona lumbar"},
}
SPLIT_LABELS = {
    "en": {"full_body": "full body", "upper_lower": "upper lower", "push_pull_legs": "push pull legs"},
    "es": {"full_body": "cuerpo completo", "upper_lower": "torso-pierna", "push_pull_legs": "empuje-tracción-pierna"},
}
TIPO_DIA_LABELS = {
    "en": {tipo: tipo for tipo in PLANTILLAS_DIA},
    "es": {
        "Full Body": "Cuerpo completo", "Upper A": "Tren superior A", "Upper B": "Tren superior B",
        "Lower A": "Tren inferior A", "Lower B": "Tren inferior B", "Push": "Empuje", "Pull": "Tracción",
        "Legs": "Pierna",
    },
}

CALENTAMIENTO_POR_DIA = {
    "en": {
        "Full Body": "5-10 min of general mobility (hips, shoulders, ankles) + 1-2 light sets of the first exercise.",
        "Upper A": "5 min of shoulder and wrist mobility + warm-up sets on the first exercise.",
        "Upper B": "5 min of shoulder and wrist mobility + warm-up sets on the first exercise.",
        "Lower A": "5-10 min of hip, knee, and ankle mobility + warm-up sets before the working load.",
        "Lower B": "5-10 min of hip, knee, and ankle mobility + warm-up sets before the working load.",
        "Push": "5 min of shoulder mobility + warm-up sets on the first exercise.",
        "Pull": "5 min of shoulder and scapular mobility + warm-up sets on the first exercise.",
        "Legs": "5-10 min of hip, knee, and ankle mobility + warm-up sets before the working load.",
    },
    "es": {
        "Full Body": "5-10 min de movilidad general (cadera, hombros, tobillos) + 1-2 series ligeras del primer ejercicio.",
        "Upper A": "5 min de movilidad de hombro y muñeca + series de calentamiento en el primer ejercicio.",
        "Upper B": "5 min de movilidad de hombro y muñeca + series de calentamiento en el primer ejercicio.",
        "Lower A": "5-10 min de movilidad de cadera, rodilla y tobillo + series de calentamiento antes de la carga de trabajo.",
        "Lower B": "5-10 min de movilidad de cadera, rodilla y tobillo + series de calentamiento antes de la carga de trabajo.",
        "Push": "5 min de movilidad de hombro + series de calentamiento en el primer ejercicio.",
        "Pull": "5 min de movilidad de hombro y escápula + series de calentamiento en el primer ejercicio.",
        "Legs": "5-10 min de movilidad de cadera, rodilla y tobillo + series de calentamiento antes de la carga de trabajo.",
    },
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


def _generar_advertencias(perfil: dict, idioma: str = "en") -> list[str]:
    """Translates health signals in the profile into enhanced-review reasons (method §8)."""
    salud = perfil.get("salud", {})
    advertencias = []

    if idioma == "es":
        for lesion in salud.get("lesiones", []):
            advertencias.append(
                f"Lesión declarada ({lesion.get('zona', 'zona no especificada')}): "
                f"{lesion.get('descripcion', '')} — se excluyeron o adaptaron ejercicios de riesgo; "
                "requiere el visto bueno del entrenador antes de enviarse."
            )
        for condicion in salud.get("enfermedades_o_condiciones", []):
            advertencias.append(f"Condición de salud declarada: {condicion}. Revisión reforzada antes de enviarse.")

        embarazo = salud.get("embarazo_o_lactancia", {})
        if embarazo.get("aplica"):
            advertencias.append(
                f"El/la cliente está embarazada o en periodo de lactancia ({embarazo.get('detalle', '')}). "
                "Requiere adaptación y el visto bueno de un profesional antes de enviarse."
            )
        for medicacion in salud.get("medicacion_habitual", []):
            advertencias.append(f"Medicación habitual declarada: {medicacion}. Revisa posibles interacciones antes de enviar.")
        return advertencias

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


def generar_borrador_rutina_reglas(perfil_cliente: dict, idioma: str = "en") -> dict:
    """Generates the full routine draft by applying the rule engine.

    Args:
        perfil_cliente: dict with the same schema as examples/cliente_ejemplo_*.json.
        idioma: "en" (default) or "es" — language of the narrative text
            (resumen_enfoque, progresion, mensaje_para_el_cliente, warmups,
            day labels, advertencias). Exercise NAMES inside `sesiones` are
            always the canonical English value regardless of `idioma` — see
            exercise_bank.py's module docstring for why (the validator's
            safety cross-check depends on it). ui/app.py translates exercise
            names for on-screen display separately, via
            exercise_bank.nombre_mostrado().
    """
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
                "en": {
                    "rodilla": (
                        "Chosen because it's more tolerable for your knee injury. Work in a "
                        "controlled range (avoid very deep flexion) at a moderate effort (you "
                        "could probably do 2-3 more reps than listed); stop if you feel joint "
                        "pain, not just muscle fatigue."
                    ),
                    "hombro": "Chosen because it's more tolerable for your shoulder; control the range of motion and stop if it hurts.",
                    "lumbar": "Chosen because it's more tolerable for your lower back; prioritize technique over load and stop if it hurts.",
                },
                "es": {
                    "rodilla": (
                        "Elegido porque es más tolerable para tu lesión de rodilla. Trabaja en un "
                        "rango controlado (evita la flexión muy profunda) a un esfuerzo moderado "
                        "(probablemente podrías hacer 2-3 repeticiones más de las indicadas); "
                        "detente si notas dolor articular, no solo fatiga muscular."
                    ),
                    "hombro": "Elegido porque es más tolerable para tu hombro; controla el rango de movimiento y detente si duele.",
                    "lumbar": "Elegido porque es más tolerable para tu zona lumbar; prioriza la técnica sobre la carga y detente si duele.",
                },
            }
            tags_aplicables = [tag for tag in lesion_tags if grupo in grupos_afectados.get(tag, set())]
            if tags_aplicables:
                notas = notas_por_tag[idioma][tags_aplicables[0]]
            ejercicios.append({
                "nombre": ejercicio["nombre"],
                "series": parametros["series"],
                "repeticiones": parametros["repeticiones"],
                "descanso_seg": parametros["descanso_seg"],
                "notas": notas,
            })

        dia_label = f"Día {indice} — {TIPO_DIA_LABELS['es'][tipo_dia]}" if idioma == "es" else f"Day {indice} — {tipo_dia}"
        cardio_label = (
            "Cardio en zona 2 (ritmo cómodo, puedes mantener una conversación), 30-40 min."
            if idioma == "es" else
            "Zone 2 cardio (comfortable pace, you can hold a conversation), 30-40 min."
        )
        sesiones.append({
            "dia": dia_label,
            "grupos_musculares": sorted({grupo for grupo, _ in PLANTILLAS_DIA[tipo_dia]}),
            "calentamiento": CALENTAMIENTO_POR_DIA[idioma][tipo_dia],
            "ejercicios": ejercicios,
            "cardio_opcional": cardio_label if indice == len(secuencia_dias) else "",
        })

    if idioma == "es":
        resumen = (
            f"Reparto '{SPLIT_LABELS['es'].get(split, split)}' para nivel {NIVEL_LABELS['es'].get(nivel, nivel)}, "
            f"{disponibilidad['dias_por_semana']} días/semana, orientado a "
            f"{OBJETIVO_LABELS['es'].get(objetivo, objetivo.replace('_', ' '))}. Ejercicios seleccionados según "
            "el material disponible del cliente"
        )
        if lesion_tags:
            etiquetas_legibles = sorted(LESION_TAG_LABELS["es"].get(tag, tag) for tag in lesion_tags)
            resumen += f" y adaptados para una lesión declarada en: {', '.join(etiquetas_legibles)}."
        else:
            resumen += "."

        progresion = (
            "Sobrecarga progresiva: en cada sesión, intenta añadir una repetición más manteniendo "
            "buena técnica. Cuando llegues al máximo del rango en todas las series de un ejercicio, "
            "añade un poco de peso y vuelve al mínimo del rango. No cambies la rutina cada semana "
            "— mantener el mismo esquema es lo que realmente impulsa el progreso."
        )

        mensaje_para_el_cliente = (
            f"Hola {nombre.split()[0]}, aquí tienes el primer borrador de tu rutina. Vamos paso a "
            "paso: primero la técnica, después el peso — tu cuerpo aprende antes de forzar. No tiene "
            "que salir perfecta la primera semana; lo importante es que puedas repetirla. Si tienes "
            "alguna duda, o si algo te duele (no solo cuesta), dímelo y lo ajustamos."
        )
    else:
        resumen = (
            f"'{SPLIT_LABELS['en'].get(split, split.replace('_', ' '))}' split for "
            f"{NIVEL_LABELS['en'].get(nivel, nivel)} level, "
            f"{disponibilidad['dias_por_semana']} days/week, geared toward "
            f"{OBJETIVO_LABELS['en'].get(objetivo, objetivo.replace('_', ' '))}. Exercises selected based on "
            "the client's available equipment"
        )
        if lesion_tags:
            etiquetas_legibles = sorted(LESION_TAG_LABELS["en"].get(tag, tag) for tag in lesion_tags)
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
        "advertencias_revision_humana": _generar_advertencias(perfil_cliente, idioma),
        "sesiones": sesiones,
        "progresion": progresion,
        "mensaje_para_el_cliente": mensaje_para_el_cliente,
    }
