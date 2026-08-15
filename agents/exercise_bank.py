"""
Exercise bank for the routine rule engine.

Each exercise declares: muscle group, required equipment, type
(basic/isolation, which sets the rep range according to the method), and
which contraindications it covers (so it can be excluded if the client has
an injury in that area). This is a deliberate simplification: instead of
having an LLM "understand" what's safe, it's declared explicitly here —
slower to maintain, but 100% deterministic, auditable, and free of API cost.

DESIGN — "nicho" (niche/tryhard exercises, added for the commitment-level
personalization, see docs/decisiones.md): a small, curated set of more
technically demanding variants (Bulgarian split squat, Nordic hamstring
curl, weighted pull-up...) that are only ever candidates for a client whose
`experiencia.nivel_compromiso` is `"tryhard"` — see rutina_reglas.py's
`_candidatos()`. Absent (defaults to `False` via `.get("nicho", False)`) on
every pre-existing entry, so "basico"/"normal" (the default) behave exactly
as before this was added.

DESIGN — "objetos_caseros" (household-object equipment, added for home
training): a handful of exercises using improvised weights any client
training at home is assumed to have (water jugs/bottles, a loaded
backpack, a towel), one per muscle group, so a home client's routine isn't
pure bodyweight-only. rutina_reglas.py's `_material_cliente()` auto-adds
this tag whenever `lugar_entreno` is "casa_con_material" or
"casa_sin_material" — the same always-available handling as
"peso_corporal", never a manual pick in ui/app.py's MATERIAL_OPCIONES.
None of these are "nicho": they're meant to add variety at every
commitment level, not gate behind "tryhard".

Note on scope: the "nombre" (name) values are the exercise's CANONICAL
name — English, and deliberately never swapped for Spanish even when the UI
language is Spanish. rutina_reglas.py selects exercises by this value, and
validator_agent.py cross-checks a draft's exercises against it by exact
string match; changing it based on UI language would silently break that
safety cross-check (see docs/decisiones.md). "nombre_es" is purely a display
translation, used only by ui/app.py to show a localized name on screen —
never used for lookups anywhere in the pipeline. The
"grupo"/"material"/"tipo"/"contraindicaciones" keys and values are internal
tags matched elsewhere in the code (rutina_reglas.py, perfil_utils.py) and
were deliberately left in Spanish — see docs/decisiones.md.
"""

# Injury zones the rule engine knows how to recognize (see rutina_reglas.py).
CONTRAINDICACIONES_CONOCIDAS = {"rodilla", "hombro", "lumbar"}

EXERCISE_BANK = [
    # --- CHEST ---
    {"nombre": "Barbell bench press", "nombre_es": "Press de banca con barra", "grupo": "pecho", "material": {"barras_y_discos", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Incline dumbbell press", "nombre_es": "Press inclinado con mancuernas", "grupo": "pecho", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Machine chest press", "nombre_es": "Press de pecho en máquina", "grupo": "pecho", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "High cable crossover / flye", "nombre_es": "Cruce de poleas altas / aperturas", "grupo": "pecho", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Parallel bar dips", "nombre_es": "Fondos en paralelas", "grupo": "pecho", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Push-ups (standard)", "nombre_es": "Flexiones (estándar)", "grupo": "pecho", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Deficit push-up", "nombre_es": "Flexión en déficit", "grupo": "pecho", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}, "nicho": True},
    {"nombre": "Water jug floor press", "nombre_es": "Press de suelo con garrafas de agua", "grupo": "pecho", "material": {"objetos_caseros"}, "tipo": "basico", "contraindicaciones": set()},

    # --- BACK ---
    {"nombre": "High cable row (close grip)", "nombre_es": "Remo en polea alta (agarre cerrado)", "grupo": "espalda", "material": {"poleas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Lat pulldown", "nombre_es": "Jalón al pecho", "grupo": "espalda", "material": {"poleas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "One-arm dumbbell row", "nombre_es": "Remo a una mano con mancuerna", "grupo": "espalda", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Pull-ups (assisted if needed)", "nombre_es": "Dominadas (asistidas si hace falta)", "grupo": "espalda", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Cable pullover", "nombre_es": "Pullover en polea", "grupo": "espalda", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Face pull", "nombre_es": "Face pull (jalón a la cara)", "grupo": "espalda", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Inverted row (bodyweight)", "nombre_es": "Remo invertido (peso corporal)", "grupo": "espalda", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Weighted pull-up", "nombre_es": "Dominada lastrada", "grupo": "espalda", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}, "nicho": True},
    {"nombre": "Loaded backpack row", "nombre_es": "Remo con mochila cargada", "grupo": "espalda", "material": {"objetos_caseros"}, "tipo": "basico", "contraindicaciones": set()},

    # --- SHOULDERS ---
    {"nombre": "Machine shoulder press", "nombre_es": "Press de hombro en máquina", "grupo": "hombro", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Dumbbell shoulder press", "nombre_es": "Press de hombro con mancuernas", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Dumbbell lateral raise", "nombre_es": "Elevaciones laterales con mancuernas", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Machine reverse fly (rear delt)", "nombre_es": "Apertura posterior en máquina (deltoide posterior)", "grupo": "hombro", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Dumbbell front raise", "nombre_es": "Elevaciones frontales con mancuernas", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Pike push-up", "nombre_es": "Flexión pike (en V)", "grupo": "hombro", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Single-arm dumbbell push press", "nombre_es": "Push press a una mano con mancuerna", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"hombro"}, "nicho": True},
    {"nombre": "Water jug lateral raise", "nombre_es": "Elevación lateral con garrafas de agua", "grupo": "hombro", "material": {"objetos_caseros"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- LEGS (quads) ---
    {"nombre": "Barbell squat", "nombre_es": "Sentadilla con barra", "grupo": "pierna_cuadriceps", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Goblet squat", "nombre_es": "Sentadilla goblet", "grupo": "pierna_cuadriceps", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Leg press (controlled range)", "nombre_es": "Prensa de piernas (rango controlado)", "grupo": "pierna_cuadriceps", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Dumbbell lunges", "nombre_es": "Zancadas con mancuernas", "grupo": "pierna_cuadriceps", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Machine leg extension (moderate load)", "nombre_es": "Extensión de cuádriceps en máquina (carga moderada)", "grupo": "pierna_cuadriceps", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Low step-up with dumbbells", "nombre_es": "Step-up bajo con mancuernas", "grupo": "pierna_cuadriceps", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Bodyweight squat", "nombre_es": "Sentadilla con peso corporal", "grupo": "pierna_cuadriceps", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Wall sit (isometric squat)", "nombre_es": "Sentadilla en pared (isométrica)", "grupo": "pierna_cuadriceps", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Bulgarian split squat", "nombre_es": "Sentadilla búlgara", "grupo": "pierna_cuadriceps", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": {"rodilla"}, "nicho": True},
    {"nombre": "Loaded backpack goblet squat", "nombre_es": "Sentadilla goblet con mochila cargada", "grupo": "pierna_cuadriceps", "material": {"objetos_caseros"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},

    # --- LEGS (hamstrings / glutes) ---
    {"nombre": "Barbell Romanian deadlift", "nombre_es": "Peso muerto rumano con barra", "grupo": "pierna_isquios_gluteo", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": {"lumbar"}},
    {"nombre": "Barbell hip thrust", "nombre_es": "Hip thrust con barra (empuje de cadera)", "grupo": "pierna_isquios_gluteo", "material": {"barras_y_discos", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Seated leg curl (machine)", "nombre_es": "Curl femoral sentado (máquina)", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Lying leg curl (machine)", "nombre_es": "Curl femoral tumbado (máquina)", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Single-leg glute bridge", "nombre_es": "Puente de glúteo a una pierna", "grupo": "pierna_isquios_gluteo", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Machine hip abduction", "nombre_es": "Abducción de cadera en máquina", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Machine hip adduction", "nombre_es": "Aducción de cadera en máquina", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Nordic hamstring curl", "nombre_es": "Curl femoral nórdico", "grupo": "pierna_isquios_gluteo", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": {"rodilla"}, "nicho": True},
    {"nombre": "Water jug Romanian deadlift", "nombre_es": "Peso muerto rumano con garrafas de agua", "grupo": "pierna_isquios_gluteo", "material": {"objetos_caseros"}, "tipo": "basico", "contraindicaciones": {"lumbar"}},

    # --- CALVES ---
    {"nombre": "Standing machine calf raise", "nombre_es": "Elevación de gemelo de pie en máquina", "grupo": "gemelos", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Seated calf raise", "nombre_es": "Elevación de gemelo sentado", "grupo": "gemelos", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Loaded backpack calf raise", "nombre_es": "Elevación de gemelo con mochila cargada", "grupo": "gemelos", "material": {"objetos_caseros"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- BICEPS ---
    {"nombre": "Barbell curl", "nombre_es": "Curl de bíceps con barra", "grupo": "biceps", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Dumbbell curl", "nombre_es": "Curl de bíceps con mancuernas", "grupo": "biceps", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Cable curl", "nombre_es": "Curl de bíceps en polea", "grupo": "biceps", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Dumbbell hammer curl", "nombre_es": "Curl martillo con mancuernas", "grupo": "biceps", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Water jug curl", "nombre_es": "Curl de bíceps con garrafas de agua", "grupo": "biceps", "material": {"objetos_caseros"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- TRICEPS ---
    {"nombre": "Cable triceps pushdown (bar)", "nombre_es": "Extensión de tríceps en polea (barra)", "grupo": "triceps", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Dumbbell skull crusher", "nombre_es": "Press francés con mancuernas", "grupo": "triceps", "material": {"mancuernas", "bancos"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Bench dips", "nombre_es": "Fondos en banco", "grupo": "triceps", "material": {"peso_corporal", "bancos"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Diamond push-ups", "nombre_es": "Flexiones diamante", "grupo": "triceps", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Water jug overhead triceps extension", "nombre_es": "Extensión de tríceps por encima de la cabeza con garrafa de agua", "grupo": "triceps", "material": {"objetos_caseros"}, "tipo": "aislamiento", "contraindicaciones": {"hombro"}},

    # --- CORE ---
    {"nombre": "Front plank", "nombre_es": "Plancha frontal", "grupo": "core", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Cable crunch", "nombre_es": "Crunch en polea", "grupo": "core", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Hanging / lying leg raise", "nombre_es": "Elevación de piernas (colgado o tumbado)", "grupo": "core", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Cable Pallof press", "nombre_es": "Pallof press en polea", "grupo": "core", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": {"lumbar"}},
    {"nombre": "Dragon flag", "nombre_es": "Dragon flag", "grupo": "core", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": {"lumbar"}, "nicho": True},
    {"nombre": "Towel sliding mountain climbers", "nombre_es": "Escaladores con toalla deslizante", "grupo": "core", "material": {"objetos_caseros"}, "tipo": "aislamiento", "contraindicaciones": set()},
]

# English name -> Spanish display name. Display-only (see module docstring):
# never used for selection or the validator's cross-checks, only by
# ui/app.py to show a localized exercise name on screen.
NOMBRES_ES = {e["nombre"]: e["nombre_es"] for e in EXERCISE_BANK}


def nombre_mostrado(nombre: str, idioma: str) -> str:
    """English `nombre` -> localized display name. Falls back to the
    English name if idioma isn't "es" or the name isn't in the bank (e.g. a
    future motor="llm" exercise not in this catalog)."""
    return NOMBRES_ES.get(nombre, nombre) if idioma == "es" else nombre
