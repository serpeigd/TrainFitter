"""
Agente validador: comprueba coherencia con el método y señales de riesgo antes
de dar por bueno un borrador de rutina + dieta.

DISEÑO — por qué este agente es siempre reglas, nunca LLM (a diferencia de
routine_agent/diet_agent, que sí ofrecen motor="llm" como opción futura):
un validador es un GATE de seguridad. Un gate de seguridad debe ser auditable
y determinista — la misma entrada debe dar siempre el mismo veredicto, y
cualquiera debe poder leer el código y saber exactamente qué se comprueba.
Eso es justo lo contrario de lo que aporta un LLM (variabilidad, "criterio").
Por eso el validador no es "la versión gratis de un futuro validador con IA":
es una elección de diseño que se mantendría igual aunque hubiera presupuesto
ilimitado de API.

DISEÑO — defensa en profundidad, no solo agregación:
El validador no confía ciegamente en que routine_agent/diet_agent ya se
auto-marcaron correctamente. Vuelve a mirar el perfil crudo del cliente de
forma independiente, y además cruza los ejercicios/alimentos concretos de
los borradores contra las lesiones/alergias declaradas — por si algún día
un motor LLM se equivoca al autoevaluarse.
"""

from exercise_bank import EXERCISE_BANK
from food_bank import FUENTES_CARBOHIDRATO, FUENTES_GRASA, FUENTES_PROTEINA, etiquetas_excluidas
from perfil_utils import tags_lesiones


def _motivos_desde_perfil(perfil: dict) -> list[str]:
    """Relee el perfil crudo, sin depender de lo que ya marcaron rutina/dieta."""
    salud = perfil.get("salud", {})
    motivos = []

    if salud.get("lesiones"):
        zonas = ", ".join(l.get("zona", "sin especificar") for l in salud["lesiones"])
        motivos.append(f"El perfil declara {len(salud['lesiones'])} lesión(es): {zonas}.")
    if salud.get("enfermedades_o_condiciones"):
        motivos.append(
            f"El perfil declara condición(es) de salud: {', '.join(salud['enfermedades_o_condiciones'])}."
        )
    if salud.get("embarazo_o_lactancia", {}).get("aplica"):
        motivos.append("El perfil indica embarazo o lactancia.")
    if salud.get("medicacion_habitual"):
        motivos.append(f"El perfil declara medicación habitual: {', '.join(salud['medicacion_habitual'])}.")
    if salud.get("alergias_alimentarias"):
        motivos.append(
            f"El perfil declara alergia(s) alimentaria(s): {', '.join(salud['alergias_alimentarias'])}."
        )
    return motivos


def _validar_rutina_contra_lesiones(perfil: dict, borrador_rutina: dict) -> list[str]:
    """Cruza cada ejercicio del borrador contra las lesiones declaradas."""
    lesion_tags = tags_lesiones(perfil)
    if not lesion_tags:
        return []

    indice_ejercicios = {e["nombre"]: e for e in EXERCISE_BANK}
    motivos = []
    for sesion in borrador_rutina.get("sesiones", []):
        for ejercicio in sesion.get("ejercicios", []):
            info = indice_ejercicios.get(ejercicio["nombre"])
            if info is None:
                continue  # ejercicio fuera del banco (p.ej. venía del motor LLM): no se puede cruzar
            conflicto = info["contraindicaciones"] & lesion_tags
            if conflicto:
                motivos.append(
                    f"¡Revisar! '{ejercicio['nombre']}' en '{sesion['dia']}' está contraindicado "
                    f"para la lesión declarada ({', '.join(sorted(conflicto))})."
                )
    return motivos


def _validar_dieta_contra_alergias(perfil: dict, borrador_dieta: dict) -> list[str]:
    """Cruza cada alimento sugerido en el borrador contra alergias/intolerancias declaradas."""
    excluidas = etiquetas_excluidas(perfil)
    if not excluidas:
        return []

    indice_alimentos = {f["nombre"]: f["etiquetas"] for f in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA}
    sugerencias = (
        borrador_dieta.get("fuentes_proteina_sugeridas", [])
        + borrador_dieta.get("fuentes_carbohidrato_sugeridas", [])
        + borrador_dieta.get("fuentes_grasa_sugeridas", [])
    )

    motivos = []
    for nombre_alimento in sugerencias:
        etiquetas = indice_alimentos.get(nombre_alimento, set())
        conflicto = etiquetas & excluidas
        if conflicto:
            motivos.append(
                f"¡Revisar! '{nombre_alimento}' en el borrador de dieta podría chocar con una "
                f"alergia/intolerancia declarada ({', '.join(sorted(conflicto))})."
            )
    return motivos


def validar_borradores(perfil_cliente: dict, borrador_rutina: dict, borrador_dieta: dict) -> dict:
    """
    Emite el veredicto final del pipeline.

    Returns:
        {"veredicto": "aprobado_automatico" | "revision_reforzada", "motivos": [...]}
    """
    motivos = []
    motivos += _motivos_desde_perfil(perfil_cliente)
    motivos += list(borrador_rutina.get("advertencias_revision_humana", []))
    motivos += list(borrador_dieta.get("advertencias_revision_humana", []))
    motivos += _validar_rutina_contra_lesiones(perfil_cliente, borrador_rutina)
    motivos += _validar_dieta_contra_alergias(perfil_cliente, borrador_dieta)

    motivos_unicos = list(dict.fromkeys(motivos))  # dedup conservando el orden

    veredicto = "revision_reforzada" if motivos_unicos else "aprobado_automatico"
    return {"veredicto": veredicto, "motivos": motivos_unicos}
