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
from variacion import elegir_variante, rng_para_cliente

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

# Equivalent phrasings of the same guidance (progressive overload; technique
# first, weight later; tell me if something actually hurts) — picked per
# client via variacion.elegir_variante() instead of always using the first
# one, so different clients don't all read byte-identical boilerplate. Every
# variant says the same thing in the trainer's documented voice (see
# docs/metodo_entrenador.md): adherence and safety before raw progress,
# plain and pedagogical, never a rigid rule. See docs/decisiones.md.
PROGRESION_VARIANTES = {
    "en": [
        "Progressive overload: each session, try to add one more rep while keeping good "
        "technique. Once you hit the top of the range on every set of an exercise, add a "
        "little weight and go back to the bottom of the range. No changing the routine every "
        "week — sticking with the same scheme is what actually drives progress.",
        "The rule is simple: chase one more rep before you chase more weight. Once every set "
        "of an exercise hits the top of its range with good technique, add a bit of load and "
        "start back at the bottom. Swapping exercises every week feels productive but isn't — "
        "repeating the same scheme long enough is what actually builds progress.",
        "Progress here means small, boring, repeatable steps: one extra rep, same weight, same "
        "technique. Only once you're topping out every set of an exercise do you add load and "
        "reset to the bottom of the range. Resist the urge to change things up constantly — "
        "consistency on the same movements is the actual driver.",
        "Think in terms of the rep range, not the weight on the bar. Add reps first; once "
        "you're maxing out every set for an exercise, then add a little weight and drop back to "
        "the bottom of the range. Sticking with the same routine week after week — not "
        "switching it up — is what makes the numbers move.",
    ],
    "es": [
        "Sobrecarga progresiva: en cada sesión, intenta añadir una repetición más manteniendo "
        "buena técnica. Cuando llegues al máximo del rango en todas las series de un ejercicio, "
        "añade un poco de peso y vuelve al mínimo del rango. No cambies la rutina cada semana "
        "— mantener el mismo esquema es lo que realmente impulsa el progreso.",
        "La regla es sencilla: primero persigue una repetición más, después más peso. Cuando "
        "todas las series de un ejercicio lleguen al máximo del rango con buena técnica, añade "
        "algo de carga y vuelve a empezar por el mínimo. Cambiar de ejercicios cada semana "
        "parece productivo, pero no lo es — repetir el mismo esquema el tiempo suficiente es lo "
        "que de verdad genera progreso.",
        "Aquí el progreso son pasos pequeños, aburridos y repetibles: una repetición más, mismo "
        "peso, misma técnica. Solo cuando agotes el rango en todas las series de un ejercicio "
        "añades carga y reinicias desde el mínimo. Resiste la tentación de cambiarlo todo "
        "constantemente — la constancia sobre los mismos movimientos es lo que realmente empuja.",
        "Piensa en el rango de repeticiones, no en el peso de la barra. Primero suma "
        "repeticiones; cuando agotes el rango en todas las series de un ejercicio, añade algo de "
        "peso y vuelve al mínimo. Mantener la misma rutina semana tras semana — no cambiarla — "
        "es lo que mueve los números.",
    ],
}

# Same idea for the closing client message: the greeting ("Hi {name}, " /
# "Hola {name}, ") stays fixed and is prepended separately, so every
# variant here starts lowercase, mid-sentence.
MENSAJE_CLIENTE_RUTINA_VARIANTES = {
    "en": [
        "here's your first draft routine. Let's go step by step: technique first, weight later "
        "— your body learns before it forces. It doesn't need to be perfect the first week; "
        "what matters is that you can repeat it. If you have any questions, or if something "
        "hurts (not just feels tough), let me know and we'll adjust it.",
        "here's your first draft routine. Nothing here is set in stone — think of it as a "
        "starting point we'll shape together. The first week is about learning the movements, "
        "not chasing weight; if something feels off, especially any real pain rather than just "
        "effort, tell me and we'll change it.",
        "here's your first routine draft. Go easy on yourself the first couple of sessions — "
        "getting the technique right matters far more than the number on the plates right now. "
        "Any questions, or anything that actually hurts rather than just feels hard, come to me "
        "and we'll sort it out.",
        "here's your first draft routine. Take it one session at a time: learn the movement, "
        "then load it up — in that order. You don't need to nail it this week, just be able to "
        "repeat it. And if anything hurts rather than just feeling like effort, tell me right "
        "away so we can adjust.",
    ],
    "es": [
        "aquí tienes el primer borrador de tu rutina. Vamos paso a paso: primero la técnica, "
        "después el peso — tu cuerpo aprende antes de forzar. No tiene que salir perfecta la "
        "primera semana; lo importante es que puedas repetirla. Si tienes alguna duda, o si "
        "algo te duele (no solo cuesta), dímelo y lo ajustamos.",
        "aquí tienes el primer borrador de tu rutina. Nada de esto es definitivo — piénsalo "
        "como un punto de partida que iremos ajustando juntos. La primera semana es para "
        "aprender los movimientos, no para perseguir peso; si algo no te cuadra, sobre todo si "
        "es dolor de verdad y no solo esfuerzo, dímelo y lo cambiamos.",
        "aquí tienes tu primer borrador de rutina. Ve con calma las primeras sesiones: ahora "
        "mismo importa mucho más la técnica que el peso en el disco. Cualquier duda, o "
        "cualquier cosa que te duela de verdad y no solo cueste, cuéntamelo y lo solucionamos.",
        "aquí tienes el primer borrador de tu rutina. Tómatelo sesión a sesión: primero "
        "aprende el movimiento, luego cárgalo — en ese orden. No hace falta que te salga "
        "perfecta esta semana, solo que puedas repetirla. Y si algo te duele de verdad, no "
        "solo cuesta, dímelo cuanto antes para ajustarlo.",
    ],
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


# Technical-demand heuristic derived from an exercise's own required
# equipment (exercise_bank.py doesn't carry a separate "complexity" field
# to maintain by hand) -- a free barbell lift asks more of technique/
# stability than the machine-guided or bodyweight equivalent covering the
# same muscle group. Used only to REORDER candidates within a slot for
# beginners (see _preferir_baja_complejidad_primero()), never to exclude:
# a beginner training only with a barbell still needs a full session.
def _complejidad(ejercicio: dict) -> str:
    material = ejercicio["material"]
    if "barras_y_discos" in material:
        return "alta"
    if "mancuernas" in material:
        return "media"
    return "baja"  # maquinas_guiadas, poleas, peso_corporal, bicicleta_estatica


def _preferir_baja_complejidad_primero(candidatos: list[dict]) -> list[dict]:
    """Stable sort so lower-complexity exercises come first within an
    already-shuffled candidate list -- the client-seeded shuffle upstream
    still decides which specific exercise wins among equally-complex
    options, this only reorders across complexity tiers."""
    orden = {"baja": 0, "media": 1, "alta": 2}
    return sorted(candidatos, key=lambda ej: orden[_complejidad(ej)])


# Volume adjustment by level (method §2 + docs/base_conocimiento/
# entrenamiento.md's "Adaptation by level" and "Volume: landmarks" — a
# beginner sits nearer MEV, technique before load, near-linear progression;
# an advanced trainee has more room toward MAV before diminishing returns).
# Isolation work stays closer to constant across levels on purpose -- it's
# already low-fatigue-cost, so there's less headroom to cut for a beginner
# and less need to add for an advanced trainee the way compound volume has.
AJUSTE_SERIES_POR_NIVEL = {
    "principiante": {"basico": -1, "aislamiento": 0},
    "intermedio": {"basico": 0, "aislamiento": 0},
    "avanzado": {"basico": 1, "aislamiento": 1},
}
SERIES_MINIMAS = 2  # never go below this regardless of how many adjustments stack


def _ajuste_series_por_estilo_de_vida(perfil: dict) -> int:
    """A conservative -1 to basic-exercise series when the client reported
    high stress or under 6h average sleep -- recovery capacity is part of
    what MRV (max recoverable volume) actually depends on
    (docs/base_conocimiento/entrenamiento.md), not just training age.
    Stacks with (doesn't replace) the level-based adjustment above; both
    are clamped by SERIES_MINIMAS together, not separately."""
    estilo = perfil.get("estilo_de_vida", {})
    estres = estilo.get("nivel_estres_percibido")
    sueno = estilo.get("horas_sueno_promedio")
    if estres == "alto" or (isinstance(sueno, (int, float)) and sueno < 6):
        return -1
    return 0


# Session-length-aware trimming (docs/base_conocimiento/entrenamiento.md:
# "availability and equipment rule everything"): the routine used to
# ignore minutos_por_sesion entirely once past the resumen label,
# regularly prescribing a 5-6 exercise session to someone who only has 30
# minutes. Trims the LAST slots off each day's template (the earlier
# slots are the day's main compound lifts -- see PLANTILLAS_DIA's own
# ordering -- so a shortened session keeps the highest-priority work).
def _num_slots_a_recortar(minutos_por_sesion: int) -> int:
    if minutos_por_sesion < 30:
        return 2
    if minutos_por_sesion < 45:
        return 1
    return 0


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

    ajuste_nivel = AJUSTE_SERIES_POR_NIVEL.get(nivel, AJUSTE_SERIES_POR_NIVEL["intermedio"])
    ajuste_estilo_vida = _ajuste_series_por_estilo_de_vida(perfil_cliente)
    recorte_sesion = _num_slots_a_recortar(disponibilidad["minutos_por_sesion"])

    # Candidates for a given (grupo, tipo) slot are shuffled once per client
    # (seeded by id_cliente, so it's the same shuffle every time this same
    # client's plan is regenerated) and cached here — two clients with
    # identical material/injuries no longer land on the same exercise every
    # time just because it happened to be first in exercise_bank.py, while
    # the existing rotation counter below still cycles through that
    # client's own shuffled order across repeated slots in the same plan
    # (e.g. Push/Pull/Legs needing "pecho" twice). See docs/decisiones.md.
    rng_ejercicios = rng_para_cliente(perfil_cliente, "rutina:ejercicios")
    candidatos_por_slot: dict[tuple, list[dict]] = {}
    contador_rotacion: dict[tuple, int] = defaultdict(int)
    sesiones = []
    for indice, tipo_dia in enumerate(secuencia_dias, start=1):
        ejercicios = []
        plantilla_dia = PLANTILLAS_DIA[tipo_dia]
        # Trim the LAST slots for a short session (see
        # _num_slots_a_recortar()) -- the earlier slots are the day's main
        # compound lifts (PLANTILLAS_DIA's own ordering), so a shortened
        # session keeps the highest-priority work rather than an arbitrary
        # subset. Never trims below 2 exercises: an empty/near-empty
        # session isn't a useful draft even at 20 minutes.
        if recorte_sesion:
            plantilla_dia = plantilla_dia[: max(2, len(plantilla_dia) - recorte_sesion)]
        for grupo, tipo in plantilla_dia:
            clave = (grupo, tipo)
            if clave not in candidatos_por_slot:
                candidatos = _candidatos(grupo, tipo, material_cliente, lesion_tags)
                rng_ejercicios.shuffle(candidatos)
                # Reorders across complexity tiers (doesn't re-shuffle
                # within a tier) -- a beginner still gets exercise variety
                # from the client-seeded shuffle above, just biased toward
                # machine/bodyweight/dumbbell options over barbell
                # compound lifts when both are available for this slot.
                if nivel == "principiante":
                    candidatos = _preferir_baja_complejidad_primero(candidatos)
                candidatos_por_slot[clave] = candidatos
            candidatos = candidatos_por_slot[clave]
            if not candidatos:
                continue  # no equipment/safe options for this slot: skip it instead of failing
            rotacion = contador_rotacion[clave]
            ejercicio = candidatos[rotacion % len(candidatos)]
            contador_rotacion[clave] += 1

            parametros_base = PARAMETROS_POR_TIPO[tipo]
            series = max(
                SERIES_MINIMAS, parametros_base["series"] + ajuste_nivel[tipo] + ajuste_estilo_vida,
            )
            parametros = {**parametros_base, "series": series}
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

    # Same client -> same picks every time (seeded by id_cliente); a
    # different client with an otherwise-similar profile gets a different,
    # but equally on-voice, phrasing. Separate namespace from the
    # exercise-selection RNG above so picking one doesn't shift the other.
    rng_texto = rng_para_cliente(perfil_cliente, "rutina:texto")
    progresion = elegir_variante(rng_texto, PROGRESION_VARIANTES[idioma])
    cuerpo_mensaje = elegir_variante(rng_texto, MENSAJE_CLIENTE_RUTINA_VARIANTES[idioma])

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
        if ajuste_estilo_vida < 0:
            resumen += (
                " Volumen algo más conservador esta primera etapa, dado el estrés/sueño que declaraste "
                "— lo iremos subiendo según cómo lo vayas notando."
            )
        if recorte_sesion:
            resumen += f" Ajustado a menos ejercicios por sesión para caber en tus {disponibilidad['minutos_por_sesion']} minutos disponibles."

        mensaje_para_el_cliente = f"Hola {nombre.split()[0]}, {cuerpo_mensaje}"
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
        if ajuste_estilo_vida < 0:
            resumen += (
                " Volume kept a bit more conservative for this first block, given the stress/sleep "
                "you reported — we'll build it back up based on how you're actually recovering."
            )
        if recorte_sesion:
            resumen += f" Trimmed to fewer exercises per session to fit your {disponibilidad['minutos_por_sesion']}-minute window."

        mensaje_para_el_cliente = f"Hi {nombre.split()[0]}, {cuerpo_mensaje}"

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
