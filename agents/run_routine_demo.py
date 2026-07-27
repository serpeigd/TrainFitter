"""
Routine agent demo: generates the draft for examples/cliente_ejemplo_1.json
and saves it to examples/output_rutina_1.json.

Uses the "reglas" engine by default: does NOT need ANTHROPIC_API_KEY or an
internet connection, it's free and deterministic. .env is only needed if
generar_borrador_rutina(..., motor="llm") gets called later on.

How to run it (from the repo root):
    python agents/run_routine_demo.py
"""

import json
import sys
from pathlib import Path

from routine_agent import RoutineAgentError, generar_borrador_rutina

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTE_PATH = REPO_ROOT / "examples" / "cliente_ejemplo_1.json"
OUTPUT_PATH = REPO_ROOT / "examples" / "output_rutina_1.json"


def main() -> None:
    try:  # dotenv is optional: only needed if you later use motor="llm"
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    perfil_cliente = json.loads(CLIENTE_PATH.read_text(encoding="utf-8"))
    print(f"Generating routine draft for {perfil_cliente['datos_basicos']['nombre']}...")

    try:
        borrador = generar_borrador_rutina(perfil_cliente)
    except RoutineAgentError as exc:
        print(f"\nError generating the draft: {exc}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_PATH.write_text(borrador.to_json(), encoding="utf-8")

    print(f"\nDraft saved to {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  Assumed level: {borrador.contenido['nivel_asumido']}")
    print(f"  Days/week: {borrador.contenido['dias_por_semana']}")
    print(f"  Sessions generated: {len(borrador.contenido['sesiones'])}")
    if borrador.contenido["advertencias_revision_humana"]:
        print(f"  Warnings: {borrador.contenido['advertencias_revision_humana']}")
    else:
        print("  Warnings: none")


if __name__ == "__main__":
    main()
