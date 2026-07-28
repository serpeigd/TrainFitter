"""
Utilities for reading signals from the client profile, shared between
rutina_reglas.py and validator_agent.py (the validator reuses them to
independently re-check the profile, instead of just trusting what earlier
agents already flagged).
"""


def tags_lesiones(perfil: dict) -> set[str]:
    """Detects known injury zones from the intake form's free text.

    Matches both Spanish and English keywords, since example client profiles
    were translated to English but this matching logic is otherwise unchanged.
    """
    lesiones = perfil.get("salud", {}).get("lesiones", [])
    texto = " ".join(
        (lesion.get("zona", "") + " " + lesion.get("descripcion", "")) for lesion in lesiones
    ).lower().replace("_", " ")

    tags = set()
    if "rodilla" in texto or "knee" in texto:
        tags.add("rodilla")
    if "hombro" in texto or "shoulder" in texto:
        tags.add("hombro")
    if any(kw in texto for kw in ("lumbar", "espalda baja", "low back", "lower back")):
        tags.add("lumbar")
    return tags
