"""
Motor de reglas para generar el borrador de rutina SIN llamar a ningún LLM.

Es la versión "gratuita" del agente de rutina: 100% determinista, sin coste,
sin clave de API. Traduce a código los valores por defecto del método
(docs/base_conocimiento/entrenamiento.md) — split según nivel/días, rangos de
reps básico=5-8 / aislamiento=10-15 — y adapta la selección de ejercicios al
material disponible y a las lesiones declaradas.

Devuelve un dict con el mismo esquema que espera el resto del pipeline
(ENTREGAR_BORRADOR_RUTINA_TOOL en routine_agent.py), para que sea intercambiable
con el motor LLM sin que el resto del sistema note la diferencia.
"""

from collections import defaultdict

from exercise_bank import EXERCISE_BANK
from perfil_utils import tags_lesiones

# Series/descanso por tipo de ejercicio, según docs/base_conocimiento/entrenamiento.md.
PARAMETROS_POR_TIPO = {
    "basico": {"series": 4, "repeticiones": "5-8", "descanso_seg": 150},
    "aislamiento": {"series": 3, "repeticiones": "10-15", "descanso_seg": 60},
}

# Qué grupos musculares se trabajan cada tipo de día, y si cada slot debe ser
# básico o aislamiento (orden = orden en que aparecen en la sesión).
PLANTILLAS_DIA = {
    "Full Body": [
        ("pierna_cuadriceps", "basico"), ("pecho", "basico"), ("espalda", "basico"),
        ("pierna_isquios_gluteo", "aislamiento"), ("hombro", "aislamiento"), ("core", "aislamiento"),
    ],
    "Torso A": [
        ("pecho", "basico"), ("espalda", "basico"), ("hombro", "basico"),
        ("triceps", "aislamiento"), ("biceps", "aislamiento"),
    ],
    "Torso B": [
        ("espalda", "basico"), ("pecho", "basico"), ("hombro", "aislamiento"),
        ("biceps", "aislamiento"), ("triceps", "aislamiento"),
    ],
    "Pierna A": [
        ("pierna_cuadriceps", "basico"), ("pierna_isquios_gluteo", "basico"),
        ("pierna_cuadriceps", "aislamiento"), ("pierna_isquios_gluteo", "aislamiento"), ("core", "aislamiento"),
    ],
    "Pierna B": [
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

CALENTAMIENTO_POR_DIA = {
    "Full Body": "5-10 min de movilidad general (cadera, hombro, tobillo) + 1-2 series ligeras del primer ejercicio.",
    "Torso A": "5 min de movilidad de hombro y muñeca + series de aproximación en el primer ejercicio.",
    "Torso B": "5 min de movilidad de hombro y muñeca + series de aproximación en el primer ejercicio.",
    "Pierna A": "5-10 min de movilidad de cadera, rodilla y tobillo + series de aproximación antes de la carga de trabajo.",
    "Pierna B": "5-10 min de movilidad de cadera, rodilla y tobillo + series de aproximación antes de la carga de trabajo.",
    "Push": "5 min de movilidad de hombro + series de aproximación en el primer ejercicio.",
    "Pull": "5 min de movilidad de hombro y escápula + series de aproximación en el primer ejercicio.",
    "Legs": "5-10 min de movilidad de cadera, rodilla y tobillo + series de aproximación antes de la carga de trabajo.",
}


def _material_cliente(perfil: dict) -> set[str]:
    material = set(perfil.get("disponibilidad", {}).get("material_disponible", []))
    material.add("peso_corporal")  # el cuerpo siempre está disponible
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
        return "torso_pierna", ["Torso A", "Pierna A", "Torso B", "Pierna B"]
    ciclo = ["Push", "Pull", "Legs"]
    return "push_pull_legs", [ciclo[i % 3] for i in range(dias)]


def _generar_advertencias(perfil: dict) -> list[str]:
    """Traduce señales de salud del perfil en motivos de revisión reforzada (método §8)."""
    salud = perfil.get("salud", {})
    advertencias = []

    for lesion in salud.get("lesiones", []):
        advertencias.append(
            f"Lesión declarada ({lesion.get('zona', 'zona no especificada')}): "
            f"{lesion.get('descripcion', '')} — ejercicios de riesgo excluidos o adaptados; "
            "requiere el visto bueno del entrenador antes de enviar."
        )
    for condicion in salud.get("enfermedades_o_condiciones", []):
        advertencias.append(f"Condición de salud declarada: {condicion}. Revisión reforzada antes de enviar.")

    embarazo = salud.get("embarazo_o_lactancia", {})
    if embarazo.get("aplica"):
        advertencias.append(
            f"Cliente en embarazo/lactancia ({embarazo.get('detalle', '')}). "
            "Requiere adaptación y visto bueno profesional antes de enviar."
        )
    for medicacion in salud.get("medicacion_habitual", []):
        advertencias.append(f"Medicación habitual declarada: {medicacion}. Revisar posibles interacciones antes de enviar.")

    return advertencias


def generar_borrador_rutina_reglas(perfil_cliente: dict) -> dict:
    """Genera el borrador de rutina completo aplicando el motor de reglas."""
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
                continue  # sin material/opciones seguras para este hueco: se omite en vez de fallar
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
            # Nota de rodilla informada por guías de rehabilitación de LCA: restringir
            # carga alta a rango de flexión ~0-80° y dosificar por esfuerzo percibido
            # (RPE), no al fallo — ver docs/base_conocimiento/seguridad_poblaciones_especiales.md
            notas_por_tag = {
                "rodilla": (
                    "Seleccionado por tolerar mejor tu lesión de rodilla. Trabaja en rango "
                    "controlado (evita flexión muy profunda) y a esfuerzo moderado (podrías "
                    "hacer 2-3 repeticiones más de las indicadas); para si notas dolor articular, "
                    "no solo fatiga muscular."
                ),
                "hombro": "Seleccionado por ser más tolerable para tu hombro; controla el rango de movimiento y para si notas dolor.",
                "lumbar": "Seleccionado por ser más tolerable para tu zona lumbar; prioriza técnica sobre carga y para si notas dolor.",
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
            "dia": f"Día {indice} — {tipo_dia}",
            "grupos_musculares": sorted({grupo for grupo, _ in PLANTILLAS_DIA[tipo_dia]}),
            "calentamiento": CALENTAMIENTO_POR_DIA[tipo_dia],
            "ejercicios": ejercicios,
            "cardio_opcional": (
                "Cardio Zona 2 (ritmo cómodo, puedes hablar sin ahogarte), 30-40 min."
                if indice == len(secuencia_dias) else ""
            ),
        })

    resumen = (
        f"Split '{split.replace('_', ' ')}' para nivel {nivel}, {disponibilidad['dias_por_semana']} "
        f"días/semana, orientado a {objetivo.replace('_', ' ')}. Ejercicios seleccionados según el "
        "material disponible del cliente"
    )
    if lesion_tags:
        resumen += f" y adaptados por lesión declarada en: {', '.join(sorted(lesion_tags))}."
    else:
        resumen += "."

    progresion = (
        "Sobrecarga progresiva: en cada sesión, intenta sumar una repetición más manteniendo la "
        "técnica. Cuando completes el tope del rango en todas las series de un ejercicio, sube "
        "el peso ligeramente y vuelve al rango bajo. Nada de cambiar la rutina cada semana — "
        "la constancia con el mismo esquema es lo que produce el progreso."
    )

    mensaje_para_el_cliente = (
        f"Hola {nombre.split()[0]}, aquí tienes tu primer borrador de rutina. Vamos poco a poco: "
        "primero técnica, luego peso — tu cuerpo aprende antes de forzar. No hace falta que salga "
        "perfecto la primera semana, lo importante es que puedas repetirlo. Cualquier duda o si algo "
        "duele (no solo molesta), dímelo y lo ajustamos."
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
