"""
Automatic inbox trigger: scans the trainer's Gmail inbox for adherence
checklists clients have sent back after actually starting their plan (see
mcp/gmail_client.py's buscar_respuestas_adherencia()), parses each one
(agents/adherencia_parser.py), and logs a new "Adherence check-in" row in
Notion's Check-ins database for every reply not already recorded — skipping
duplicates by Gmail message ID (mcp/notion_connector.py's
existe_checkin_para_mensaje()). See both modules' docstrings for the full
design rationale (why gmail.readonly, why dedup lives in Notion rather than
a Gmail label).

Meant to run on a schedule via GitHub Actions
(.github/workflows/inbox_trigger.yml), free of charge — same spirit as the
rest of this project: no paid service, just polling on a timer. Can also be
run by hand, same setup as ui/app.py's Gmail/Notion connectors
(credentials.json/token.json at the repo root, NOTION_* in your .env):

    python main.py
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "agents"))
sys.path.insert(0, str(REPO_ROOT / "mcp"))

from adherencia_parser import analizar_adherencia, resumir_adherencia  # noqa: E402
from gmail_client import GmailClientError, buscar_respuestas_adherencia  # noqa: E402
from notion_connector import NotionClientError, crear_registro_checkin, existe_checkin_para_mensaje  # noqa: E402


def main() -> None:
    try:
        respuestas = buscar_respuestas_adherencia()
    except GmailClientError as exc:
        print(f"Gmail error: {exc}")
        return

    print(f"Found {len(respuestas)} candidate repl{'y' if len(respuestas) == 1 else 'ies'} in the inbox.")

    nuevos_registros = 0
    for respuesta in respuestas:
        try:
            if existe_checkin_para_mensaje(respuesta["id_mensaje"]):
                continue
        except NotionClientError as exc:
            print(f"Notion error checking {respuesta['id_mensaje']}: {exc}")
            continue

        datos = analizar_adherencia(respuesta["contenido"])
        if datos["valoracion"] is None:
            print(f"Skipping {respuesta['id_mensaje']} from {respuesta['remitente']}: nothing parseable in it.")
            continue

        # Gmail only gives us the sender's address here, not the name on
        # file in Notion's Clients database -- the address is still a
        # perfectly fine row title, and it's the actual join key back to
        # that record either way (see notion_connector.py's docstring).
        try:
            registro = crear_registro_checkin(
                email=respuesta["remitente"],
                nombre_cliente=respuesta["remitente"],
                tipo="Adherence check-in",
                fecha=respuesta["fecha"],
                notas=resumir_adherencia(datos),
                valoracion=datos["valoracion"],
                id_mensaje=respuesta["id_mensaje"],
            )
        except NotionClientError as exc:
            print(f"Notion error saving {respuesta['id_mensaje']}: {exc}")
            continue

        nuevos_registros += 1
        print(f"Logged adherence check-in for {respuesta['remitente']} ({datos['valoracion']}): {registro['url']}")

    print(f"Done. {nuevos_registros} new check-in(s) logged.")


if __name__ == "__main__":
    main()
