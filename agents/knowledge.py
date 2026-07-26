"""
Carga de la base de conocimiento del entrenador desde disco.

Los agentes (rutina, dieta, validador) no "saben" nada por sí mismos: todo su
criterio viene de los documentos en docs/. Este módulo centraliza cómo se leen,
para no repetir rutas ni lógica de lectura en cada agente.
"""

from pathlib import Path

# docs/ vive un nivel por encima de agents/, sea cual sea el directorio desde
# el que se ejecute el script (evita depender del cwd).
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
BASE_CONOCIMIENTO_DIR = DOCS_DIR / "base_conocimiento"


def load_metodo_entrenador() -> str:
    """Lee el documento raíz del método (criterio, filosofía, reglas de seguridad)."""
    return (DOCS_DIR / "metodo_entrenador.md").read_text(encoding="utf-8")


def load_knowledge_files(*nombres: str) -> str:
    """
    Lee y concatena notas de docs/base_conocimiento/ por nombre de archivo
    (sin extensión), p.ej. load_knowledge_files("entrenamiento", "estilo_vida_longevidad").
    """
    partes = []
    for nombre in nombres:
        ruta = BASE_CONOCIMIENTO_DIR / f"{nombre}.md"
        partes.append(f"### {ruta.name}\n\n{ruta.read_text(encoding='utf-8')}")
    return "\n\n---\n\n".join(partes)
