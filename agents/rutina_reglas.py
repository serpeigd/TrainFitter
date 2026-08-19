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

# Mandatory, always-on warm-up per session type -- a real, direct request
# ("añade un calentamiento obligatorio rapido siempre para evitar
# lesiones"), grounded in the RAMP protocol (Raise, Activate, Mobilize,
# Potentiate) standard in strength coaching, not invented. Named exercises
# instead of vague "mobility": banded external/internal rotation is the
# standard rotator-cuff activation drill before any pressing/pulling work
# (shoulder-day sessions), and hip circles/leg swings/glute bridges are the
# standard hip-activation drills before squatting/hinging (leg-day
# sessions) -- both are cheap, fast (under 5-10 min), and target the two
# joints most warm-up research flags for injury risk under load. Every
# PLANTILLAS_DIA key has an entry so this is unconditionally set on every
# session (see generar_borrador_rutina_reglas() below), never optional; also
# rendered in the PDF (pdf_generador.py) and the trainer/portal panels.
#
# Two sentences per entry (mobility drills, then warm-up sets), not one
# long "+"-joined sentence -- so gmail_client.dividir_en_puntos() (which
# splits on sentence-ending punctuation) can bullet this the same way it
# already does for progresion, instead of returning it as one unsplittable
# fragment.
CALENTAMIENTO_POR_DIA = {
    "en": {
        "Full Body": (
            "5-10 min of light cardio to raise your heart rate, hip circles and leg swings for the "
            "hips, and banded external rotations plus arm circles for the rotator cuff. "
            "Finish with 1-2 light sets of the first exercise."
        ),
        "Upper A": (
            "5 min of arm circles, banded external/internal rotations for rotator-cuff activation, "
            "and wrist circles. Then warm-up sets on the first exercise."
        ),
        "Upper B": (
            "5 min of arm circles, banded external/internal rotations for rotator-cuff activation, "
            "and wrist circles. Then warm-up sets on the first exercise."
        ),
        "Lower A": (
            "5-10 min of hip circles, leg swings (front-back and side-to-side), bodyweight glute "
            "bridges, and ankle circles. Then warm-up sets before the working load."
        ),
        "Lower B": (
            "5-10 min of hip circles, leg swings (front-back and side-to-side), bodyweight glute "
            "bridges, and ankle circles. Then warm-up sets before the working load."
        ),
        "Push": (
            "5 min of banded external/internal rotations for rotator-cuff activation, arm circles, "
            "and scapular push-ups. Then warm-up sets on the first exercise."
        ),
        "Pull": (
            "5 min of banded external/internal rotations for rotator-cuff activation, scapular "
            "retractions, and arm circles. Then warm-up sets on the first exercise."
        ),
        "Legs": (
            "5-10 min of hip circles, leg swings (front-back and side-to-side), bodyweight glute "
            "bridges, and ankle circles. Then warm-up sets before the working load."
        ),
    },
    "es": {
        "Full Body": (
            "5-10 min de cardio suave para elevar el pulso, círculos de cadera y balanceos de "
            "pierna para la cadera, y rotaciones externas con goma más círculos de brazo para el "
            "manguito rotador. Termina con 1-2 series ligeras del primer ejercicio."
        ),
        "Upper A": (
            "5 min de círculos de brazo, rotaciones externas/internas con goma para activar el "
            "manguito rotador, y círculos de muñeca. Después, series de calentamiento en el "
            "primer ejercicio."
        ),
        "Upper B": (
            "5 min de círculos de brazo, rotaciones externas/internas con goma para activar el "
            "manguito rotador, y círculos de muñeca. Después, series de calentamiento en el "
            "primer ejercicio."
        ),
        "Lower A": (
            "5-10 min de círculos de cadera, balanceos de pierna (adelante-atrás y lateral), "
            "puente de glúteo sin peso, y círculos de tobillo. Después, series de calentamiento "
            "antes de la carga de trabajo."
        ),
        "Lower B": (
            "5-10 min de círculos de cadera, balanceos de pierna (adelante-atrás y lateral), "
            "puente de glúteo sin peso, y círculos de tobillo. Después, series de calentamiento "
            "antes de la carga de trabajo."
        ),
        "Push": (
            "5 min de rotaciones externas/internas con goma para activar el manguito rotador, "
            "círculos de brazo, y flexiones escapulares. Después, series de calentamiento en el "
            "primer ejercicio."
        ),
        "Pull": (
            "5 min de rotaciones externas/internas con goma para activar el manguito rotador, "
            "retracciones escapulares, y círculos de brazo. Después, series de calentamiento en "
            "el primer ejercicio."
        ),
        "Legs": (
            "5-10 min de círculos de cadera, balanceos de pierna (adelante-atrás y lateral), "
            "puente de glúteo sin peso, y círculos de tobillo. Después, series de calentamiento "
            "antes de la carga de trabajo."
        ),
    },
}

# Equivalent phrasings of the same guidance (progressive overload; technique
# first, weight later; tell me if something actually hurts) — picked per
# client via variacion.elegir_variante() instead of always using the first
# one, so different clients don't all read byte-identical boilerplate. Every
# variant says the same thing in the trainer's documented voice (see
# docs/metodo_entrenador.md): adherence and safety before raw progress,
# plain and pedagogical, never a rigid rule. See docs/decisiones.md.
#
# Direct follow-up ("escritas como bullet points mejor", with a pasted
# example: "Sube a más repeticiones antes de progresar con el peso"):
# rewritten from explanatory prose into short, imperative sentences --
# each one a single action, no "here's the rule" framing -- so
# gmail_client.dividir_en_puntos() (already applied wherever this renders)
# produces three punchy bullets instead of three long ones. Same content,
# same 4-variant pool for per-client variety, same trainer voice.
PROGRESION_VARIANTES = {
    "en": [
        "Add reps before you add weight. Once every set of an exercise hits the top of its "
        "range, add a little weight and drop back to the bottom. Don't change the routine "
        "every week — repeating the same scheme is what drives progress.",
        "The rule is simple: reps first, weight second. Once every set tops out its range, "
        "add some load and start back at the bottom. Swapping exercises weekly feels "
        "productive but doesn't build progress — repeating them does.",
        "Progress in small, boring steps: one more rep, same weight, same technique. Add load "
        "only once every set tops out its range. Don't switch exercises constantly — "
        "consistency on the same movements is what drives results.",
        "Think reps first, not the number on the bar. Add reps before you add weight, then "
        "reset to the bottom of the range once you add load. Sticking with the same routine "
        "week after week is what actually moves the numbers.",
    ],
    "es": [
        "Sube a más repeticiones antes de subir el peso. Cuando completes el máximo de "
        "repeticiones en todas las series de un ejercicio, añade algo de peso y vuelve al "
        "mínimo. No cambies la rutina cada semana — repetir el mismo esquema es lo que "
        "impulsa el progreso.",
        "La regla es sencilla: primero repeticiones, después peso. Cuando agotes el rango en "
        "todas las series de un ejercicio, añade carga y vuelve a empezar por abajo. Cambiar "
        "de ejercicios cada semana parece productivo, pero no genera progreso — repetirlos sí.",
        "Progresa en pasos pequeños y aburridos: una repetición más, mismo peso, misma "
        "técnica. Añade carga solo cuando agotes el rango en todas las series. No cambies de "
        "ejercicios constantemente — la constancia sobre los mismos movimientos es lo que "
        "empuja.",
        "Piensa en repeticiones, no en el peso de la barra. Suma repeticiones primero; añade "
        "peso solo cuando agotes el rango en todas las series de un ejercicio. Mantener la "
        "misma rutina semana tras semana es lo que mueve los números.",
    ],
}

# Real follow-up to a direct complaint: PROGRESION_VARIANTES above (the
# "add a rep, then add weight" rule) is beginner-level guidance that an
# avanzado/tryhard client -- who explicitly asked for more detail, not
# less -- already knows. Gated the same way dieta_reglas.py's own
# _consejos_sinergias() is (avanzado/tryhard only; basico/normal keep the
# generic rule above, which is genuinely the right level for them), and
# grounded in the same evidence docs/base_conocimiento/entrenamiento.md
# already cites (RP Strength's MEV/MAV/MRV landmarks, the RIR/RPE
# autoregulation section, frequency) rather than invented content.
PROGRESION_AVANZADA_VARIANTES = {
    "en": [
        "Progress in blocks, not sessions: start each block near your minimum effective volume "
        "(MEV) and add a set to a lift every week or two as you're able to recover from it, "
        "working up toward your maximum adaptive range (MAV) — then take a deload week (much "
        "lighter, lower volume) before you'd hit the point where you can't recover between "
        "sessions (MRV). Don't wait for performance to actually drop to take that week.",
        "Reps in reserve (RIR) is what should calibrate every set, not just \"add a rep\": leave "
        "1-2 reps in the tank on compound lifts, and get a bit closer to failure (0-1 RIR) on "
        "isolation work. Training every set to the same RIR consistently — not just chasing a "
        "number on the page — is what makes \"add a rep, then add weight\" actually mean the "
        "same thing week to week.",
        "Frequency matters as much as total weekly volume: hitting a muscle group twice a week "
        "with moderate volume per session usually beats cramming the same total volume into one "
        "session — each set arrives fresher, so more of your working sets actually count.",
    ],
    "es": [
        "Progresa por bloques, no por sesión: empieza cada bloque cerca de tu volumen mínimo "
        "efectivo (MEV) y añade una serie a un ejercicio cada semana o dos según lo vayas "
        "recuperando, acercándote a tu rango máximo adaptativo (MAV) — y haz una semana de "
        "descarga (mucho más ligera, menos volumen) antes de llegar al punto de no recuperar "
        "entre sesiones (MRV). No esperes a que el rendimiento baje de verdad para hacerla.",
        "Las repeticiones en reserva (RIR) son lo que debería calibrar cada serie, no solo "
        "\"añade una repetición\": deja 1-2 repeticiones en el tanque en los ejercicios básicos, "
        "y acércate algo más al fallo (0-1 RIR) en los de aislamiento. Entrenar cada serie al "
        "mismo RIR de forma consistente — no solo perseguir un número en el papel — es lo que "
        "hace que \"una repetición más, luego más peso\" signifique lo mismo semana a semana.",
        "La frecuencia importa tanto como el volumen semanal total: entrenar un grupo muscular "
        "dos veces por semana con volumen moderado en cada sesión suele funcionar mejor que meter "
        "el mismo volumen total en una sola sesión — cada serie llega más fresca, así que más de "
        "tus series de trabajo cuentan de verdad.",
    ],
}

# Same idea for the closing client message: the greeting ("Hi {name}, " /
# "Hola {name}, ") stays fixed and is prepended separately, so every
# variant here starts lowercase, mid-sentence.
MENSAJE_CLIENTE_RUTINA_VARIANTES = {
    "en": [
        "here's your first draft routine. Let's go step by step: technique first, weight later "
        "— you learn the movement before you load it. It doesn't need to be perfect the first "
        "week; what matters is that you can repeat it. If you have any questions, or if "
        "something hurts (not just feels tough), let me know and we'll adjust it.",
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

# One goal-specific sentence on the actual training approach, appended after
# the generic MENSAJE_CLIENTE_RUTINA_VARIANTES text above -- direct request
# ("mensajes adaptados segun objetivos... propon un plan de inicio"). Kept to
# training-side framing only (diet's own version lives in dieta_reglas.py's
# PLAN_INICIO_DIETA) so the two never repeat each other's point when both
# land in the same email/portal view. Keys match objetivo.principal exactly
# (see OBJETIVO_LABELS).
PLAN_INICIO_RUTINA = {
    "en": {
        "perdida_grasa": (
            "Lifting stays the priority — it's what protects your muscle while you're eating "
            "less — with some cardio added around it to speed things up, not to replace it."
        ),
        "hipertrofia": (
            "The focus is raising training volume little by little while eating enough to "
            "support it — without that, the work in the gym doesn't turn into new muscle."
        ),
        "recomposicion_corporal": (
            "The priority is strength and technique on the basic lifts — that drives "
            "recomposition far more than volume or cardio does."
        ),
        "salud_general": (
            "The goal here is consistency, not maximum performance — training regularly and "
            "without injury is what actually makes the difference long-term."
        ),
    },
    "es": {
        "perdida_grasa": (
            "El peso sigue siendo la prioridad — es lo que protege tu músculo mientras comes "
            "menos — y añadimos algo de cardio alrededor para acelerar el proceso, no para "
            "sustituirlo."
        ),
        "hipertrofia": (
            "El foco está en subir el volumen de entrenamiento poco a poco y comer lo "
            "suficiente para sostenerlo — sin eso, el trabajo en el gimnasio no se traduce en "
            "músculo nuevo."
        ),
        "recomposicion_corporal": (
            "La prioridad es la fuerza y la técnica en los ejercicios básicos — es lo que "
            "impulsa la recomposición mucho más que el volumen o el cardio."
        ),
        "salud_general": (
            "El objetivo aquí es la consistencia, no el rendimiento máximo — entrenar de forma "
            "regular y sin lesiones es lo que marca la diferencia a largo plazo."
        ),
    },
}

# One genuinely useful, evidence-grounded note per session (not just an
# exercise list) -- requested directly: "useful info for each session, key
# points." Reps-in-reserve (RIR) is a real training variable independent of
# the rep-count range itself; see docs/base_conocimiento/entrenamiento.md's
# "Effort and proximity to failure" section for the underlying systematic
# review this operationalizes -- basic/compound work stays a couple of reps
# short of failure (lower fatigue cost, still enough stimulus), isolation
# work at the end of a session can push closer to it (bigger local
# hypertrophy signal, cheaper systemically). Session-level rather than
# per-exercise: PLANTILLAS_DIA always mixes both types within a session, so
# one note covering the whole session reads better than repeating it on
# every row.
NOTA_ESFUERZO_SESION = {
    "en": (
        "Effort cue: leave 1-2 reps in the tank (RIR) on the compound/basic lifts -- "
        "you should feel you could do 1-2 more with good form. The isolation work at "
        "the end of the session can go closer to failure (0-1 reps left)."
    ),
    "es": (
        "Guía de esfuerzo: en los ejercicios básicos/compuestos deja 1-2 repeticiones "
        "de margen (RIR) — deberías notar que podrías hacer 1-2 más con buena técnica. "
        "El trabajo de aislamiento al final de la sesión puede ir más cerca del fallo "
        "(0-1 repeticiones de margen)."
    ),
}


def _material_cliente(perfil: dict) -> set[str]:
    disponibilidad = perfil.get("disponibilidad", {})
    lugar = disponibilidad.get("lugar_entreno")
    # Defense-in-depth, same reasoning as validator_agent.py re-deriving
    # risk from the raw profile instead of trusting an upstream flag: a
    # client training at home with no equipment can't have gym-style
    # equipment on file, regardless of what material_disponible says (stale
    # UI state, a hand-built profile, a parsed intake PDF, or a loaded
    # revision) -- lugar_entreno is the authoritative signal, not the
    # equipment list. ui/app.py's form also prevents this contradiction at
    # entry (see _formulario_ficha_nueva()), but that's a UX nicety, not
    # the safety net.
    material = set() if lugar == "casa_sin_material" else set(disponibilidad.get("material_disponible", []))
    material.add("peso_corporal")  # the body is always available
    if lugar in ("casa_con_material", "casa_sin_material"):
        # Household objects (water jugs, a loaded backpack, a towel) are
        # always available for a client training at home -- see
        # exercise_bank.py's "objetos_caseros"-tagged entries. Not exposed
        # as a manual MATERIAL_OPCIONES pick in ui/app.py: like
        # peso_corporal, it's implied by training location, not something
        # the trainer selects.
        material.add("objetos_caseros")
    if lugar in ("gimnasio_completo", "gimnasio_pequeno"):
        # A pull-up bar / dip station is close to universal gym equipment,
        # unlike a genuine home setup -- see exercise_bank.py's
        # "estructura_fija" DESIGN note for the real bug this fixes
        # (pull-ups/dips were being suggested to clients with no bar or
        # dip station at home, since "peso_corporal" alone doesn't capture
        # needing something to hang or push off of).
        material.add("estructura_fija")
    return material


def _candidatos(
    grupo: str, tipo: str, material_cliente: set[str], lesion_tags: set[str], incluir_nicho: bool = False,
) -> list[dict]:
    return [
        ej for ej in EXERCISE_BANK
        if ej["grupo"] == grupo
        and ej["tipo"] == tipo
        and ej["material"] <= material_cliente
        and not (ej["contraindicaciones"] & lesion_tags)
        and (incluir_nicho or not ej.get("nicho", False))
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


def _preferir_alta_complejidad_primero(candidatos: list[dict]) -> list[dict]:
    """The mirror of _preferir_baja_complejidad_primero(), for "tryhard"
    nivel_compromiso (see generar_borrador_rutina_reglas()) -- reorders
    toward more technically demanding variants first, same stable-sort-
    within-an-already-shuffled-list behavior. Never applied to a genuine
    beginner (nivel == "principiante") regardless of nivel_compromiso --
    training experience is a safety-relevant signal that wins over a
    detail-level preference, so a beginner who picks "tryhard" still gets
    the low-complexity-first bias instead (see the call site)."""
    orden = {"baja": 2, "media": 1, "alta": 0}
    return sorted(candidatos, key=lambda ej: orden[_complejidad(ej)])


def _preferir_complejidad_media_primero(candidatos: list[dict]) -> list[dict]:
    """A genuine middle step between the two functions above, for
    "avanzado" -- dumbbell-level variants first, then barbell, then
    bodyweight/machine last. Confirmed directly: "avanzado" should read
    as a real step between "normal" and "tryhard", not just "normal" plus
    unrelated supplement tips (see docs/decisiones.md)."""
    orden = {"media": 0, "alta": 1, "baja": 2}
    return sorted(candidatos, key=lambda ej: orden[_complejidad(ej)])


# Same bias-not-force philosophy and same probability as
# planificador_comidas.PROBABILIDAD_REPETIR_FAVORITO -- a client who liked
# an exercise should see it come back often, not have it locked into every
# occurrence of that slot for the rest of time.
PROBABILIDAD_REPETIR_FAVORITO = 0.6


def _sesgar_por_favoritos(
    grupo: str, tipo: str, candidatos: list[dict], ejercicios_favoritos: list[dict], rng,
) -> dict | None:
    """Looks for a client-liked exercise (see docs/decisiones.md's "repeat
    an exercise" feature -- ejercicios_favoritos comes from the client
    portal, via perfil["experiencia"]["ejercicios_favoritos"]) matching
    this slot's (grupo, tipo), whose name is still among `candidatos` --
    equipment no longer available or a new injury since it was liked
    correctly drops it rather than resurrecting a now-unsafe pick, since
    `candidatos` is already _candidatos()'s equipment/injury-filtered pool
    by the time this runs. Bias, not a hard lock: returns one matching
    favorite roughly PROBABILIDAD_REPETIR_FAVORITO of the time a match
    exists; None otherwise, so the caller falls through to its normal
    rotation-based selection."""
    nombres_candidatos = {ej["nombre"] for ej in candidatos}
    candidatas = [
        fav for fav in ejercicios_favoritos
        if fav.get("grupo") == grupo and fav.get("tipo") == tipo and fav.get("nombre") in nombres_candidatos
    ]
    if not candidatas or rng.random() >= PROBABILIDAD_REPETIR_FAVORITO:
        return None
    nombre_elegido = rng.choice(candidatas)["nombre"]
    return next(ej for ej in candidatos if ej["nombre"] == nombre_elegido)


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

# Commitment-level personalization (experiencia.nivel_compromiso, added
# alongside dieta_reglas.py's own AJUSTE_COMPROMISO_MULTIPLICADOR -- see
# docs/decisiones.md): a client-chosen "how much detail/guidance do you
# want" dial, separate from nivel (training experience, which the client
# doesn't get to just pick), and renamed from an earlier "how demanding"
# framing to this one (basico/normal/avanzado/tryhard -- see
# docs/decisiones.md for why). "basico" trims a set for the simplest,
# easiest-to-sustain session -- the fewest moving parts, matching "I want
# the essentials, nothing extra" at this end of the scale. "avanzado" (the
# level between normal and tryhard) is a no-op here on purpose: more
# detail/guidance shows up in dieta_reglas.py's supplement tips, not in
# training volume -- detail and physical intensity are different axes,
# and conflating them would mean inventing a training-volume justification
# this project has no real backing for. "tryhard" is the literal ceiling:
# it adds a set AND unlocks the small "nicho" pool of more technically
# demanding exercise variants (see exercise_bank.py) -- the most this
# project can currently offer. "normal" (the default) is a no-op, so
# existing clients are unaffected. Stacks with (doesn't replace) the
# level/stress-sleep adjustments above, all clamped together by the same
# SERIES_MINIMAS floor.
AJUSTE_SERIES_POR_COMPROMISO = {"basico": -1, "normal": 0, "avanzado": 0, "tryhard": 1}

# Trainer-driven routine adjustments (experiencia.ajustes_rutina, a
# searchable multiselect in ui/app.py) -- the routine-side twin of
# dieta_reglas.py's own ajustes_dieta() design (see food_bank.
# ajustes_dieta()'s docstring for the full "why a dropdown, not free
# text" reasoning). Each is a small, bounded nudge stacked on top of the
# existing level/stress-sleep/compromiso adjustments, never a
# re-derivation of the whole routine from scratch.
AJUSTE_SERIES_POR_AJUSTE_RUTINA = {"mas_volumen": 1, "menos_volumen": -1}
AJUSTE_DESCANSO_SEG = {"mas_descanso": 30, "menos_descanso": -30}
DESCANSO_MINIMO_SEG = 30

# Bilingual labels for the resumen_enfoque transparency note (see
# generar_borrador_rutina_reglas()) and ui/app.py's multiselect options --
# same "a label added here is the option's own display text" pattern as
# dieta_reglas.ETIQUETAS_AJUSTE_DIETA.
ETIQUETAS_AJUSTE_RUTINA = {
    "es": {
        "mas_volumen": "más volumen", "menos_volumen": "menos volumen",
        "mas_descanso": "más descanso entre series", "menos_descanso": "menos descanso entre series",
        "mas_cardio": "más cardio", "menos_cardio": "sin cardio",
        "evitar_barra": "evitar barra libre", "preferir_maquinas": "priorizar máquinas",
    },
    "en": {
        "mas_volumen": "more volume", "menos_volumen": "less volume",
        "mas_descanso": "more rest between sets", "menos_descanso": "less rest between sets",
        "mas_cardio": "more cardio", "menos_cardio": "no cardio",
        "evitar_barra": "avoid barbell", "preferir_maquinas": "prefer machines",
    },
}


def ajustes_rutina(perfil: dict) -> set[str]:
    """Trainer-driven routine adjustments -- see the ETIQUETAS_AJUSTE_RUTINA
    comment above for the full design. Absent/empty for a profile that
    predates this field, same "no key = selected none" degradation as
    dieta_reglas.ajustes_dieta()."""
    return set(perfil.get("experiencia", {}).get("ajustes_rutina") or [])


def _filtrar_evitar_barra(candidatos: list[dict]) -> list[dict]:
    """"evitar_barra" (ajustes_rutina) -- soft-excludes barbell-only
    candidates, a trainer preference rather than a safety exclusion (unlike
    lesion-driven contraindicaciones). Never leaves a slot with zero
    candidates over a soft preference: falls back to the unfiltered list
    if every remaining candidate for this slot needs a barbell."""
    sin_barra = [ej for ej in candidatos if "barras_y_discos" not in ej["material"]]
    return sin_barra or candidatos


def _preferir_maquinas_primero(candidatos: list[dict]) -> list[dict]:
    """"preferir_maquinas" (ajustes_rutina) -- reorders machine-equipped
    candidates first within an already-shuffled/complexity-biased list,
    same stable-sort pattern as _preferir_baja_complejidad_primero() and
    friends. A trainer preference, applied after whichever complexity
    bias already ran, not instead of it."""
    return sorted(candidatos, key=lambda ej: 0 if "maquinas_guiadas" in ej["material"] else 1)


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
    nivel_compromiso = perfil_cliente.get("experiencia", {}).get("nivel_compromiso", "normal")
    incluir_nicho = nivel_compromiso == "tryhard"

    material_cliente = _material_cliente(perfil_cliente)
    lesion_tags = tags_lesiones(perfil_cliente)
    split, secuencia_dias = _elegir_split_y_secuencia(disponibilidad["dias_por_semana"])

    ajuste_nivel = AJUSTE_SERIES_POR_NIVEL.get(nivel, AJUSTE_SERIES_POR_NIVEL["intermedio"])
    ajuste_estilo_vida = _ajuste_series_por_estilo_de_vida(perfil_cliente)
    ajuste_compromiso = AJUSTE_SERIES_POR_COMPROMISO.get(nivel_compromiso, 0)
    recorte_sesion = _num_slots_a_recortar(disponibilidad["minutos_por_sesion"])

    ajustes_rutina_cliente = ajustes_rutina(perfil_cliente)
    ajuste_volumen_extra = sum(
        delta for clave, delta in AJUSTE_SERIES_POR_AJUSTE_RUTINA.items() if clave in ajustes_rutina_cliente
    )
    ajuste_descanso_extra = sum(
        delta for clave, delta in AJUSTE_DESCANSO_SEG.items() if clave in ajustes_rutina_cliente
    )

    # Exercises the client "liked" from a previous week's routine, via the
    # portal (see docs/decisiones.md) -- absent for a brand-new client,
    # same "no field, no bias" degradation as dieta_reglas.py's own
    # comidas_favoritas.
    ejercicios_favoritos = perfil_cliente.get("experiencia", {}).get("ejercicios_favoritos") or []

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
                candidatos = _candidatos(grupo, tipo, material_cliente, lesion_tags, incluir_nicho)
                rng_ejercicios.shuffle(candidatos)
                # Reorders across complexity tiers (doesn't re-shuffle
                # within a tier) -- a beginner still gets exercise variety
                # from the client-seeded shuffle above, just biased toward
                # machine/bodyweight/dumbbell options over barbell
                # compound lifts when both are available for this slot.
                # nivel_compromiso="basico" stacks the same low-complexity
                # bias on top of (never instead of) the beginner one --
                # "keep it simple" applies regardless of raw experience.
                # "avanzado"/"tryhard" lean the other way, a real 4-step
                # progression (baja -> no bias -> media -> alta), but only
                # for a client who isn't a genuine beginner (see
                # _preferir_alta_complejidad_primero()'s own docstring).
                if nivel == "principiante" or nivel_compromiso == "basico":
                    candidatos = _preferir_baja_complejidad_primero(candidatos)
                elif nivel_compromiso == "avanzado":
                    candidatos = _preferir_complejidad_media_primero(candidatos)
                elif nivel_compromiso == "tryhard":
                    candidatos = _preferir_alta_complejidad_primero(candidatos)
                # Trainer-driven preferences (ajustes_rutina) apply on top
                # of whichever complexity bias just ran, not instead of
                # it -- "evitar_barra" narrows the pool first (falling
                # back to the unfiltered list if nothing survives), then
                # "preferir_maquinas" reorders what's left.
                if "evitar_barra" in ajustes_rutina_cliente:
                    candidatos = _filtrar_evitar_barra(candidatos)
                if "preferir_maquinas" in ajustes_rutina_cliente:
                    candidatos = _preferir_maquinas_primero(candidatos)
                candidatos_por_slot[clave] = candidatos
            candidatos = candidatos_por_slot[clave]
            if not candidatos:
                continue  # no equipment/safe options for this slot: skip it instead of failing
            # A liked exercise (see _sesgar_por_favoritos()) wins this slot
            # when one matches and its own dice roll says so; otherwise the
            # normal rotation picks as before. The rotation counter still
            # advances either way, so a later non-favorite occurrence of
            # this same slot doesn't skip ahead.
            favorito = _sesgar_por_favoritos(grupo, tipo, candidatos, ejercicios_favoritos, rng_ejercicios)
            rotacion = contador_rotacion[clave]
            ejercicio = favorito or candidatos[rotacion % len(candidatos)]
            contador_rotacion[clave] += 1

            parametros_base = PARAMETROS_POR_TIPO[tipo]
            series = max(
                SERIES_MINIMAS,
                parametros_base["series"] + ajuste_nivel[tipo] + ajuste_estilo_vida + ajuste_compromiso
                + ajuste_volumen_extra,
            )
            descanso_seg = max(DESCANSO_MINIMO_SEG, parametros_base["descanso_seg"] + ajuste_descanso_extra)
            parametros = {**parametros_base, "series": series, "descanso_seg": descanso_seg}
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
                "grupo": grupo,
                "tipo": tipo,
                "series": parametros["series"],
                "repeticiones": parametros["repeticiones"],
                "descanso_seg": parametros["descanso_seg"],
                "notas": notas,
            })

        dia_label = f"Día {indice} — {TIPO_DIA_LABELS['es'][tipo_dia]}" if idioma == "es" else f"Day {indice} — {tipo_dia}"
        # "mas_cardio"/"menos_cardio" (ajustes_rutina) override the
        # default "only the last session of the week" placement --
        # "mas_cardio" adds it to every session instead, "menos_cardio"
        # drops it outright regardless of which session this is.
        if "menos_cardio" in ajustes_rutina_cliente:
            incluye_cardio = False
        elif "mas_cardio" in ajustes_rutina_cliente:
            incluye_cardio = True
        else:
            incluye_cardio = indice == len(secuencia_dias)
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
            "cardio_opcional": cardio_label if incluye_cardio else "",
            "nota_esfuerzo": NOTA_ESFUERZO_SESION[idioma],
        })

    # Same client -> same picks every time (seeded by id_cliente); a
    # different client with an otherwise-similar profile gets a different,
    # but equally on-voice, phrasing. Separate namespace from the
    # exercise-selection RNG above so picking one doesn't shift the other.
    rng_texto = rng_para_cliente(perfil_cliente, "rutina:texto")
    if nivel_compromiso in ("avanzado", "tryhard"):
        progresion = elegir_variante(rng_texto, PROGRESION_AVANZADA_VARIANTES[idioma])
    else:
        progresion = elegir_variante(rng_texto, PROGRESION_VARIANTES[idioma])
    cuerpo_mensaje = elegir_variante(rng_texto, MENSAJE_CLIENTE_RUTINA_VARIANTES[idioma])
    plan_inicio = PLAN_INICIO_RUTINA[idioma].get(objetivo, "")
    if plan_inicio:
        cuerpo_mensaje = f"{cuerpo_mensaje} {plan_inicio}"

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
        if nivel_compromiso == "tryhard":
            resumen += " Modo tryhard: una serie extra por ejercicio y variantes más exigentes cuando el material lo permite."
        elif nivel_compromiso == "basico":
            resumen += " Modo básico: una serie menos por ejercicio, para quedarte solo con lo esencial."
        elif nivel_compromiso == "avanzado":
            resumen += (
                " Modo avanzado: mismo volumen que el modo normal, con variantes de mancuerna que piden algo "
                "más de control técnico y guía de progresión más detallada."
            )
        if ajustes_rutina_cliente:
            etiquetas_ajustes = sorted(ETIQUETAS_AJUSTE_RUTINA["es"].get(a, a) for a in ajustes_rutina_cliente)
            resumen += f" Ajustes del entrenador aplicados: {', '.join(etiquetas_ajustes)}."

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
        if nivel_compromiso == "tryhard":
            resumen += " Tryhard mode: one extra set per exercise, and more demanding variants where equipment allows."
        elif nivel_compromiso == "basico":
            resumen += " Basic mode: one fewer set per exercise, to keep it down to just the essentials."
        elif nivel_compromiso == "avanzado":
            resumen += (
                " Advanced mode: same volume as normal mode, leaning toward dumbbell variants that ask a "
                "bit more technical control, with more detailed progression guidance."
            )
        if ajustes_rutina_cliente:
            etiquetas_ajustes = sorted(ETIQUETAS_AJUSTE_RUTINA["en"].get(a, a) for a in ajustes_rutina_cliente)
            resumen += f" Trainer adjustments applied: {', '.join(etiquetas_ajustes)}."

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
