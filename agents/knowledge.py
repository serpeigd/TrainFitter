"""
Loads the trainer's knowledge base from disk.

The agents (routine, diet, validator) don't "know" anything on their own: all
of their judgment comes from the documents in docs/. This module centralizes
how they're read, so the reading logic and paths aren't duplicated in every
agent.
"""

from pathlib import Path

# docs/ lives one level above agents/, regardless of which directory the
# script is run from (avoids depending on cwd).
DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"
BASE_CONOCIMIENTO_DIR = DOCS_DIR / "base_conocimiento"


def load_metodo_entrenador() -> str:
    """Reads the method's root document (judgment, philosophy, safety rules)."""
    return (DOCS_DIR / "metodo_entrenador.md").read_text(encoding="utf-8")


def load_knowledge_files(*nombres: str) -> str:
    """
    Reads and concatenates notes from docs/base_conocimiento/ by filename
    (without the extension), e.g. load_knowledge_files("entrenamiento", "estilo_vida_longevidad").
    """
    partes = []
    for nombre in nombres:
        ruta = BASE_CONOCIMIENTO_DIR / f"{nombre}.md"
        partes.append(f"### {ruta.name}\n\n{ruta.read_text(encoding='utf-8')}")
    return "\n\n---\n\n".join(partes)
