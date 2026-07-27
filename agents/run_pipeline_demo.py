"""
Demo del orquestador completo sobre ambos clientes de ejemplo. Muestra el
recorrido de estados en vivo y el resultado final (veredicto + resumen de
los borradores). Usa el motor "reglas": no necesita ANTHROPIC_API_KEY.

Cómo ejecutarlo (desde la raíz del repo):
    python agents/run_pipeline_demo.py
"""

import json
from pathlib import Path

from orchestrator import ejecutar_pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"


def mostrar_resultado(estado) -> None:
    print(f"\nEstado final: {estado.estado}")
    print(f"Historial completo: {' -> '.join(estado.historial)}")

    if estado.error:
        print(f"Error: {estado.error}")
        return

    print(f"Veredicto: {estado.veredicto['veredicto']}")
    if estado.veredicto["motivos"]:
        print("Motivos:")
        for motivo in estado.veredicto["motivos"]:
            print(f"  - {motivo}")

    r = estado.borrador_rutina
    print(f"\nRutina: split '{r['split']}', {r['dias_por_semana']} días/semana, {len(r['sesiones'])} sesiones")

    d = estado.borrador_dieta
    print(f"Dieta: {d['calorias_objetivo_kcal']} kcal | proteína {d['macros']['proteina_g']} g")


def main() -> None:
    for numero in (1, 2):
        perfil = json.loads((EXAMPLES_DIR / f"cliente_ejemplo_{numero}.json").read_text(encoding="utf-8"))
        print("=" * 60)
        print(f"\nPipeline iniciado para {perfil['id_cliente']} ({perfil['datos_basicos']['nombre']})")
        estado = ejecutar_pipeline(perfil)
        mostrar_resultado(estado)
        print("=" * 60)


if __name__ == "__main__":
    main()
