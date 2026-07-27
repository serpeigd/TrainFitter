"""
Full orchestrator demo on both example clients. Shows the live state trail
and the final result (verdict + draft summary). Uses the "reglas" engine:
no ANTHROPIC_API_KEY needed.

How to run it (from the repo root):
    python agents/run_pipeline_demo.py
"""

import json
from pathlib import Path

from orchestrator import ejecutar_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"


def mostrar_resultado(estado) -> None:
    print(f"\nFinal state: {estado.estado}")
    print(f"Full history: {' -> '.join(estado.historial)}")

    if estado.error:
        print(f"Error: {estado.error}")
        return

    print(f"Verdict: {estado.veredicto['veredicto']}")
    if estado.veredicto["motivos"]:
        print("Reasons:")
        for motivo in estado.veredicto["motivos"]:
            print(f"  - {motivo}")

    r = estado.borrador_rutina
    print(f"\nRoutine: '{r['split']}' split, {r['dias_por_semana']} days/week, {len(r['sesiones'])} sessions")

    d = estado.borrador_dieta
    print(f"Diet: {d['calorias_objetivo_kcal']} kcal | protein {d['macros']['proteina_g']} g")


def main() -> None:
    for numero in (1, 2):
        perfil = json.loads((EXAMPLES_DIR / f"cliente_ejemplo_{numero}.json").read_text(encoding="utf-8"))
        print("=" * 60)
        print(f"\nPipeline started for {perfil['id_cliente']} ({perfil['datos_basicos']['nombre']})")
        estado = ejecutar_pipeline(perfil)
        mostrar_resultado(estado)
        print("=" * 60)


if __name__ == "__main__":
    main()
