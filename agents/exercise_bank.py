"""
Banco de ejercicios para el motor de reglas de rutina.

Cada ejercicio declara: grupo muscular, patrón, material necesario, tipo
(básico/aislamiento, que fija el rango de reps según el método) y qué
contraindicaciones cubre (para poder excluirlo si el cliente tiene una
lesión en esa zona). Es una simplificación deliberada: en vez de que un
LLM "entienda" qué es seguro, se declara explícitamente aquí — más lento
de mantener, pero 100% determinista y auditable, sin coste de API.
"""

# Zonas de lesión que el motor de reglas sabe reconocer (ver rutina_reglas.py).
CONTRAINDICACIONES_CONOCIDAS = {"rodilla", "hombro", "lumbar"}

EXERCISE_BANK = [
    # --- PECHO ---
    {"nombre": "Press banca con barra", "grupo": "pecho", "material": {"barras_y_discos", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Press inclinado con mancuernas", "grupo": "pecho", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Press en máquina", "grupo": "pecho", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Cruces / aperturas en polea alta", "grupo": "pecho", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Fondos en paralelas", "grupo": "pecho", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Flexiones (variante estándar)", "grupo": "pecho", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},

    # --- ESPALDA ---
    {"nombre": "Remo en polea alta (agarre cerrado)", "grupo": "espalda", "material": {"poleas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Jalón al pecho", "grupo": "espalda", "material": {"poleas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Remo con mancuerna a una mano", "grupo": "espalda", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Dominadas (asistidas si hace falta)", "grupo": "espalda", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Dorsal en polea (pullover)", "grupo": "espalda", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Face pull", "grupo": "espalda", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Remo invertido (peso corporal)", "grupo": "espalda", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},

    # --- HOMBRO ---
    {"nombre": "Press militar en máquina", "grupo": "hombro", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Press militar con mancuernas", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Elevaciones laterales con mancuernas", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Pájaros (deltoide posterior) en máquina", "grupo": "hombro", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Elevaciones frontales con mancuernas", "grupo": "hombro", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Pike push-up", "grupo": "hombro", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"hombro"}},

    # --- PIERNA (cuádriceps) ---
    {"nombre": "Sentadilla con barra", "grupo": "pierna_cuadriceps", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Sentadilla goblet con mancuerna", "grupo": "pierna_cuadriceps", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Prensa de piernas (rango controlado)", "grupo": "pierna_cuadriceps", "material": {"maquinas_guiadas"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Zancadas con mancuernas", "grupo": "pierna_cuadriceps", "material": {"mancuernas"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Extensión de cuádriceps en máquina (carga moderada)", "grupo": "pierna_cuadriceps", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Step-up bajo con mancuernas", "grupo": "pierna_cuadriceps", "material": {"mancuernas", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Sentadilla con peso corporal", "grupo": "pierna_cuadriceps", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": {"rodilla"}},
    {"nombre": "Wall sit (sentadilla isométrica en pared)", "grupo": "pierna_cuadriceps", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- PIERNA (isquios / glúteo) ---
    {"nombre": "Peso muerto rumano con barra", "grupo": "pierna_isquios_gluteo", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": {"lumbar"}},
    {"nombre": "Hip thrust con barra", "grupo": "pierna_isquios_gluteo", "material": {"barras_y_discos", "bancos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Curl femoral sentado en máquina", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Curl femoral tumbado en máquina", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Puente de glúteo a una pierna", "grupo": "pierna_isquios_gluteo", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Abductores en máquina", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Aductores en máquina", "grupo": "pierna_isquios_gluteo", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- GEMELOS ---
    {"nombre": "Elevación de gemelos de pie en máquina", "grupo": "gemelos", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Elevación de gemelos sentado", "grupo": "gemelos", "material": {"maquinas_guiadas"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- BÍCEPS ---
    {"nombre": "Curl con barra", "grupo": "biceps", "material": {"barras_y_discos"}, "tipo": "basico", "contraindicaciones": set()},
    {"nombre": "Curl con mancuernas", "grupo": "biceps", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Curl en polea", "grupo": "biceps", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Curl martillo con mancuernas", "grupo": "biceps", "material": {"mancuernas"}, "tipo": "aislamiento", "contraindicaciones": set()},

    # --- TRÍCEPS ---
    {"nombre": "Extensión de tríceps en polea (barra)", "grupo": "triceps", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Press francés con mancuernas", "grupo": "triceps", "material": {"mancuernas", "bancos"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Fondos en banco", "grupo": "triceps", "material": {"peso_corporal", "bancos"}, "tipo": "basico", "contraindicaciones": {"hombro"}},
    {"nombre": "Flexiones diamante", "grupo": "triceps", "material": {"peso_corporal"}, "tipo": "basico", "contraindicaciones": set()},

    # --- CORE ---
    {"nombre": "Plancha frontal", "grupo": "core", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Crunch en polea", "grupo": "core", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Elevación de piernas colgado / tumbado", "grupo": "core", "material": {"peso_corporal"}, "tipo": "aislamiento", "contraindicaciones": set()},
    {"nombre": "Press Pallof en polea", "grupo": "core", "material": {"poleas"}, "tipo": "aislamiento", "contraindicaciones": {"lumbar"}},
]
