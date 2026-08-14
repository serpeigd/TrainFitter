"""
Validator agent: checks consistency with the method and risk signals before
signing off on a routine + diet draft.

DESIGN — why this agent is always rule-based, never LLM (unlike
routine_agent/diet_agent, which do offer motor="llm" as a future option): a
validator is a safety GATE. A safety gate should be auditable and
deterministic — the same input should always produce the same verdict, and
anyone should be able to read the code and know exactly what's being
checked. That's the exact opposite of what an LLM brings (variability,
"judgment"). That's why the validator isn't "the free version of a future
AI-powered validator": it's a design choice that would stay the same even
with unlimited API budget.

DESIGN — defense in depth, not just aggregation:
The validator doesn't blindly trust that routine_agent/diet_agent already
flagged themselves correctly. It re-reads the client's raw profile
independently, and it also cross-checks the drafts' actual exercises/foods
against the declared injuries/allergies — in case a future LLM engine ever
gets its self-assessment wrong. Same reasoning applies to
`suplementos_actuales`: this project doesn't attempt a real, exhaustive
supplement-drug interaction database (out of scope, and a false sense of
completeness would be worse than none), so declaring both supplements AND
regular medication together always forces enhanced review regardless —
docs/base_conocimiento/suplementacion.md's own "Safety rule" section is
explicit that any possible interaction should be flagged for a human,
never silently allowed through. `suplementos_interacciones.
pares_interaccion_declarados()` ADDS a more specific, named explanation
on top of that coarse check when the declared supplement/medication pair
matches one of a curated set of well-documented pairs (see that module's
own docstring and the knowledge base's "Known interaction pairs" table)
— it never replaces the coarse check, so an unrecognized combination is
still always flagged, just without the extra detail.
"""

from exercise_bank import EXERCISE_BANK
from food_bank import FUENTES_CARBOHIDRATO, FUENTES_GRASA, FUENTES_PROTEINA, FUENTES_VERDURA, etiquetas_excluidas
from perfil_utils import tags_lesiones
from suplementos_interacciones import pares_interaccion_declarados


def _motivos_desde_perfil(perfil: dict, idioma: str = "en") -> list[str]:
    """Re-reads the raw profile, without relying on what routine/diet already flagged."""
    salud = perfil.get("salud", {})
    motivos = []

    if idioma == "es":
        if salud.get("lesiones"):
            zonas = ", ".join(lesion.get("zona", "sin especificar") for lesion in salud["lesiones"])
            motivos.append(f"El perfil declara {len(salud['lesiones'])} lesión(es): {zonas}.")
        if salud.get("enfermedades_o_condiciones"):
            motivos.append(
                f"El perfil declara condición(es) de salud: {', '.join(salud['enfermedades_o_condiciones'])}."
            )
        if salud.get("embarazo_o_lactancia", {}).get("aplica"):
            motivos.append("El perfil indica embarazo o periodo de lactancia.")
        if salud.get("medicacion_habitual"):
            motivos.append(f"El perfil declara medicación habitual: {', '.join(salud['medicacion_habitual'])}.")
        if salud.get("suplementos_actuales") and salud.get("medicacion_habitual"):
            motivos.append(
                f"El perfil declara suplementos ({', '.join(salud['suplementos_actuales'])}) junto con "
                "medicación habitual — posible interacción, revisar antes de recomendar nada más."
            )
            motivos += pares_interaccion_declarados(perfil, idioma)
        for marcador in salud.get("analitica_adjunta", {}).get("marcadores", []):
            if marcador.get("fuera_de_rango"):
                motivos.append(
                    f"Marcador de analítica fuera de rango: {marcador['nombre']} = {marcador['valor']} "
                    f"{marcador['unidad']} (rango normal: {marcador['rango_normal']})."
                )
        return motivos

    if salud.get("lesiones"):
        zonas = ", ".join(lesion.get("zona", "not specified") for lesion in salud["lesiones"])
        motivos.append(f"The profile declares {len(salud['lesiones'])} injury(ies): {zonas}.")
    if salud.get("enfermedades_o_condiciones"):
        motivos.append(
            f"The profile declares health condition(s): {', '.join(salud['enfermedades_o_condiciones'])}."
        )
    if salud.get("embarazo_o_lactancia", {}).get("aplica"):
        motivos.append("The profile indicates pregnancy or breastfeeding.")
    if salud.get("medicacion_habitual"):
        motivos.append(f"The profile declares regular medication: {', '.join(salud['medicacion_habitual'])}.")
    if salud.get("suplementos_actuales") and salud.get("medicacion_habitual"):
        motivos.append(
            f"The profile declares supplements ({', '.join(salud['suplementos_actuales'])}) alongside "
            "regular medication — possible interaction, review before recommending anything further."
        )
        motivos += pares_interaccion_declarados(perfil, idioma)
    if salud.get("alergias_alimentarias"):
        motivos.append(
            f"The profile declares food allerg(y/ies): {', '.join(salud['alergias_alimentarias'])}."
        )
    for marcador in salud.get("analitica_adjunta", {}).get("marcadores", []):
        if marcador.get("fuera_de_rango"):
            motivos.append(
                f"Bloodwork marker out of range: {marcador['nombre']} = {marcador['valor']} "
                f"{marcador['unidad']} (normal range: {marcador['rango_normal']})."
            )
    return motivos


def _validar_rutina_contra_lesiones(perfil: dict, borrador_rutina: dict, idioma: str = "en") -> list[str]:
    """Cross-checks every exercise in the draft against the declared injuries."""
    lesion_tags = tags_lesiones(perfil)
    if not lesion_tags:
        return []

    indice_ejercicios = {e["nombre"]: e for e in EXERCISE_BANK}
    motivos = []
    for sesion in borrador_rutina.get("sesiones", []):
        for ejercicio in sesion.get("ejercicios", []):
            info = indice_ejercicios.get(ejercicio["nombre"])
            if info is None:
                continue  # exercise not in the bank (e.g. came from the LLM engine): can't be cross-checked
            conflicto = info["contraindicaciones"] & lesion_tags
            if conflicto:
                if idioma == "es":
                    motivos.append(
                        f"¡Revisión necesaria! '{ejercicio['nombre']}' en '{sesion['dia']}' está "
                        f"contraindicado para la lesión declarada ({', '.join(sorted(conflicto))})."
                    )
                else:
                    motivos.append(
                        f"Review needed! '{ejercicio['nombre']}' in '{sesion['dia']}' is contraindicated "
                        f"for the declared injury ({', '.join(sorted(conflicto))})."
                    )
    return motivos


def _validar_dieta_contra_alergias(perfil: dict, borrador_dieta: dict, idioma: str = "en") -> list[str]:
    """Cross-checks every food suggested in the draft against declared
    allergies/intolerances -- including plan_semanal's meals, since every
    food agents/planificador_comidas.py ever picks is drawn from these same
    four *_sugeridas lists (see that module's docstring), so checking the
    lists themselves already covers the weekly plan with no separate
    free-text parsing needed."""
    excluidas = etiquetas_excluidas(perfil)
    if not excluidas:
        return []

    indice_alimentos = {
        f["nombre"]: f["etiquetas"] for f in FUENTES_PROTEINA + FUENTES_CARBOHIDRATO + FUENTES_GRASA + FUENTES_VERDURA
    }
    sugerencias = (
        borrador_dieta.get("fuentes_proteina_sugeridas", [])
        + borrador_dieta.get("fuentes_carbohidrato_sugeridas", [])
        + borrador_dieta.get("fuentes_grasa_sugeridas", [])
        + borrador_dieta.get("fuentes_verdura_sugeridas", [])
    )

    motivos = []
    for nombre_alimento in sugerencias:
        etiquetas = indice_alimentos.get(nombre_alimento, set())
        conflicto = etiquetas & excluidas
        if conflicto:
            if idioma == "es":
                motivos.append(
                    f"¡Revisión necesaria! '{nombre_alimento}' en la dieta en borrador podría chocar "
                    f"con una alergia/intolerancia declarada ({', '.join(sorted(conflicto))})."
                )
            else:
                motivos.append(
                    f"Review needed! '{nombre_alimento}' in the diet draft might clash with a "
                    f"declared allergy/intolerance ({', '.join(sorted(conflicto))})."
                )
    return motivos


def validar_borradores(perfil_cliente: dict, borrador_rutina: dict, borrador_dieta: dict, idioma: str = "en") -> dict:
    """
    Issues the pipeline's final verdict.

    Args:
        perfil_cliente, borrador_rutina, borrador_dieta: same as before.
        idioma: "en" (default) or "es" — language of the "motivos" reason
            strings shown to the trainer. Purely a display-language choice;
            the verdict logic itself is identical regardless of `idioma`.

    Returns:
        {"veredicto": "aprobado_automatico" | "revision_reforzada", "motivos": [...]}
    """
    motivos = []
    motivos += _motivos_desde_perfil(perfil_cliente, idioma)
    motivos += list(borrador_rutina.get("advertencias_revision_humana", []))
    motivos += list(borrador_dieta.get("advertencias_revision_humana", []))
    motivos += _validar_rutina_contra_lesiones(perfil_cliente, borrador_rutina, idioma)
    motivos += _validar_dieta_contra_alergias(perfil_cliente, borrador_dieta, idioma)

    motivos_unicos = list(dict.fromkeys(motivos))  # dedup while keeping order

    veredicto = "revision_reforzada" if motivos_unicos else "aprobado_automatico"
    return {"veredicto": veredicto, "motivos": motivos_unicos}
