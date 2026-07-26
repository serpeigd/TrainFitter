"""
Demo del agente de rutina: genera el borrador para examples/cliente_ejemplo_1.json
y lo guarda en examples/output_rutina_1.json.

Usa el motor "reglas" por defecto: NO necesita ANTHROPIC_API_KEY ni conexión a
internet, es gratis y determinista. El .env solo hace falta si más adelante
se llama a generar_borrador_rutina(..., motor="llm").

Cómo ejecutarlo (desde la raíz del repo):
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
    try:  # dotenv es opcional: solo hace falta si más adelante usas motor="llm"
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    perfil_cliente = json.loads(CLIENTE_PATH.read_text(encoding="utf-8"))
    print(f"Generando borrador de rutina para {perfil_cliente['datos_basicos']['nombre']}...")

    try:
        borrador = generar_borrador_rutina(perfil_cliente)
    except RoutineAgentError as exc:
        print(f"\nError generando el borrador: {exc}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_PATH.write_text(borrador.to_json(), encoding="utf-8")

    print(f"\nBorrador guardado en {OUTPUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  Nivel asumido: {borrador.contenido['nivel_asumido']}")
    print(f"  Días/semana: {borrador.contenido['dias_por_semana']}")
    print(f"  Sesiones generadas: {len(borrador.contenido['sesiones'])}")
    if borrador.contenido["advertencias_revision_humana"]:
        print(f"  Advertencias: {borrador.contenido['advertencias_revision_humana']}")
    else:
        print("  Advertencias: ninguna")


if __name__ == "__main__":
    main()
