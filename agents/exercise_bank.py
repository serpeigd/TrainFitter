"""
Exercise bank for the routine rule engine.

Each exercise declares: muscle group, required equipment, type
(basic/isolation, which sets the rep range according to the method), and
which contraindications it covers (so it can be excluded if the client has
an injury in that area). This is a deliberate simplification: instead of
having an LLM "understand" what's safe, it's declared explicitly here —
slower to maintain, but 100% deterministic, auditable, and free of API cost.

Note on scope: the "nombre" (name) values are the exercise display names
shown to the user and were translated to English along with the rest of the
project's content. The "grupo"/"material"/"tipo"/"contraindicaciones" keys
and values are internal tags matched elsewhere in the code (rutina_reglas.py,
perfil_utils.py) and were deliberately left in Spanish — see docs/decisiones.md.
"""

# Injury zones the rule engine knows how to recognize (see rutina_reglas.py).
CONTRAINDICACIONES_CONOCIDAS = {"rodilla", "hombro", "lumbar"}

EXERCISE_BANK = [
    # --- CHEST ---
    {"nombre": "Barbell bench press", "grupo": "pecho", "material": {"barras_y_discos", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Incline dumbbell press", "grupo": "pecho", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Machine chest press", "grupo": "pecho", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "High cable crossover / flye", "grupo": "pecho", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Parallel bar dips", "grupo": "pecho", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Push-ups (standard)", "grupo": "pecho", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},

    # --- BACK ---
    {"nombre": "High cable row (close grip)", "grupo": "espalda", "material": {"poleas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Lat pulldown", "grupo": "espalda", "material": {"poleas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "One-arm dumbbell row", "grupo": "espalda", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Pull-ups (assisted if needed)", "grupo": "espalda", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Cable pullover", "grupo": "espalda", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Face pull", "grupo": "espalda", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Inverted row (bodyweight)", "grupo": "espalda", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},

    # --- SHOULDERS ---
    {"nombre": "Machine shoulder press", "grupo": "hombro", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Dumbbell shoulder press", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Dumbbell lateral raise", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Machine reverse fly (rear delt)", "grupo": "hombro", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Dumbbell front raise", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Pike push-up", "grupo": "hombro", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},

    # --- LEGS (quads) ---
    {"nombre": "Barbell squat", "grupo": "pierna_cuadriceps", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Goblet squat", "grupo": "pierna_cuadriceps", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Leg press (controlled range)", "grupo": "pierna_cuadriceps", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Dumbbell lunges", "grupo": "pierna_cuadriceps", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Machine leg extension (moderate load)", "grupo": "pierna_cuadriceps", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Low step-up with dumbbells", "grupo": "pierna_cuadriceps", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Bodyweight squat", "grupo": "pierna_cuadriceps", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Wall sit (isometric squat)", "grupo": "pierna_cuadriceps", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- LEGS (hamstrings / glutes) ---
    {"nombre": "Barbell Romanian deadlift", "grupo": "pierna_isquios_gluteo", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": {"lumbar"}},
    {"nombre": "Barbell hip thrust", "grupo": "pierna_isquios_gluteo", "material": {"barras_y_discos", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Seated leg curl (machine)", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Lying leg curl (machine)", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Single-leg glute bridge", "grupo": "pierna_isquios_gluteo", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Machine hip abduction", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Machine hip adduction", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- CALVES ---
    {"nombre": "Standing machine calf raise", "grupo": "gemelos", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Seated calf raise", "grupo": "gemelos", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- BICEPS ---
    {"nombre": "Barbell curl", "grupo": "biceps", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Dumbbell curl", "grupo": "biceps", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Cable curl", "grupo": "biceps", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Dumbbell hammer curl", "grupo": "biceps", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- TRICEPS ---
    {"nombre": "Cable triceps pushdown (bar)", "grupo": "triceps", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Dumbbell skull crusher", "grupo": "triceps", "material": {"mancuernas", "bancos"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Bench dips", "grupo": "triceps", "material": {"peso_corporal", "bancos"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Diamond push-ups", "grupo": "triceps", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},

    # --- CORE ---
    {"nombre": "Front plank", "grupo": "core", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Cable crunch", "grupo": "core", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Hanging / lying leg raise", "grupo": "core", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Cable Pallof press", "grupo": "core", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": {"lumbar"}},
]
