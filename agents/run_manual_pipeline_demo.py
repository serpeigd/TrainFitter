"""
Demo del pipeline manual (sin orquestador todavía): rutina -> dieta -> validador,
ejecutado por separado sobre cada cliente de ejemplo. Usa el motor "reglas" en
ambos agentes: no necesita ANTHROPIC_API_KEY.

Guarda, por cliente, examples/output_rutina_<n>.json, output_dieta_<n>.json y
output_validacion_<n>.json.

Cómo ejecutarlo (desde la raíz del repo):
    python agents/run_manual_pipeline_demo.py
"""

import json
from pathlib import Path

from diet_agent import generar_borrador_dieta
from routine_agent import generar_borrador_rutina
from validator_agent import validar_borradores

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"


def procesar_cliente(numero: int) -> None:
    perfil = json.loads((EXAMPLES_DIR / f"cliente_ejemplo_{numero}.json").read_text(encoding="utf-8"))
    nombre = perfil["datos_basicos"]["nombre"]
    print(f"\n{'=' * 60}\nCliente {numero}: {nombre}\n{'=' * 60}")

    print("-> Generando rutina...")
    rutina = generar_borrador_rutina(perfil)
    (EXAMPLES_DIR / f"output_rutina_{numero}.json").write_text(rutina.to_json(), encoding="utf-8")

    print("-> Generando dieta...")
    dieta = generar_borrador_dieta(perfil)
    (EXAMPLES_DIR / f"output_dieta_{numero}.json").write_text(dieta.to_json(), encoding="utf-8")

    print("-> Validando...")
    veredicto = validar_borradores(perfil, rutina.contenido, dieta.contenido)
    (EXAMPLES_DIR / f"output_validacion_{numero}.json").write_text(
        json.dumps(veredicto, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\nVEREDICTO: {veredicto['veredicto']}")
    if veredicto["motivos"]:
        print("Motivos:")
        for motivo in veredicto["motivos"]:
            print(f"  - {motivo}")
    else:
        print("Sin motivos de revisión reforzada.")


def main() -> None:
    for numero in (1, 2):
        procesar_cliente(numero)


if __name__ == "__main__":
    main()
