"""
Utilidades para leer señales del perfil del cliente, compartidas entre
rutina_reglas.py y validator_agent.py (el validador las reutiliza para volver
a comprobar el perfil de forma independiente, no solo confiar en lo que ya
marcaron los agentes anteriores).
"""


def tags_lesiones(perfil: dict) -> set[str]:
    """Detecta zonas de lesión conocidas a partir del texto libre de la ficha."""
    lesiones = perfil.get("salud", {}).get("lesiones", [])
    texto = " ".join(
        (l.get("zona", "") + " " + l.get("descripcion", "")) for l in lesiones
    ).lower().replace("_", " ")

    tags = set()
    if "rodilla" in texto:
        tags.add("rodilla")
    if "hombro" in texto:
        tags.add("hombro")
    if "lumbar" in texto or "espalda baja" in texto:
        tags.add("lumbar")
    return tags
