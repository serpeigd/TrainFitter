"""
Automatic inbox trigger, two independent jobs in one scheduled run:

1. Adherence check-ins: scans the inbox for filled-in checklist PDFs
   clients have sent back after actually starting their plan (see
   mcp/gmail_client.py's buscar_respuestas_adherencia()), reads each
   one's form fields (agents/pdf_generador.py's leer_checklist_pdf()),
   and logs a new "Adherence check-in" row in Notion's Check-ins
   database for every reply not already recorded.

2. New-client intakes: scans the inbox for filled-in intake PDFs a
   prospective client has emailed back (see mcp/gmail_client.py's
   buscar_intakes_nuevos()), runs the full pipeline on each one
   (agents/orchestrator.py's ejecutar_pipeline()) — no trainer typing
   required — and saves a summary record to Notion's Clients database.
   This never creates a Gmail draft or sends anything: the trainer still
   reviews and approves every plan through ui/app.py exactly as before,
   just by uploading the same intake PDF there (a file_uploader alongside
   the manual form) instead of retyping it. This record is purely an
   early heads-up so the trainer knows a submission is waiting without
   checking email.

Both jobs dedupe by Gmail message ID against Notion (Check-ins/Clients'
own "Source message ID" property) rather than marking anything as read in
Gmail — see mcp/gmail_client.py's docstring for why. See these modules'
docstrings for the full design rationale (why gmail.readonly, why a
fillable PDF instead of plain text or free-form parsing).

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

from adherencia_parser import resumir_adherencia  # noqa: E402
from gmail_client import GmailClientError, buscar_intakes_nuevos, buscar_respuestas_adherencia  # noqa: E402
from notion_connector import (  # noqa: E402
    NotionClientError,
    crear_registro_checkin,
    existe_checkin_para_mensaje,
    existe_cliente_para_mensaje,
    guardar_registro_cliente,
)
from orchestrator import ejecutar_pipeline  # noqa: E402
from pdf_generador import leer_checklist_pdf  # noqa: E402


def procesar_adherencia() -> None:
    try:
        respuestas = buscar_respuestas_adherencia()
    except GmailClientError as exc:
        print(f"Gmail error (adherence): {exc}")
        return

    print(f"Found {len(respuestas)} candidate adherence repl{'y' if len(respuestas) == 1 else 'ies'} in the inbox.")

    nuevos_registros = 0
    for respuesta in respuestas:
        try:
            if existe_checkin_para_mensaje(respuesta["id_mensaje"]):
                continue
        except NotionClientError as exc:
            print(f"Notion error checking {respuesta['id_mensaje']}: {exc}")
            continue

        datos = leer_checklist_pdf(respuesta["contenido"])
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

    print(f"Adherence: {nuevos_registros} new check-in(s) logged.")


def procesar_intakes_nuevos() -> None:
    try:
        intakes = buscar_intakes_nuevos()
    except GmailClientError as exc:
        print(f"Gmail error (intakes): {exc}")
        return

    print(f"Found {len(intakes)} candidate new intake{'s' if len(intakes) != 1 else ''} in the inbox.")

    nuevos_registros = 0
    for intake in intakes:
        try:
            if existe_cliente_para_mensaje(intake["id_mensaje"]):
                continue
        except NotionClientError as exc:
            print(f"Notion error checking {intake['id_mensaje']}: {exc}")
            continue

        perfil = intake["perfil"]
        # id_cliente/fecha_admision aren't in the PDF -- leer_intake_pdf()
        # deliberately leaves them for the caller (see its docstring).
        # Derived from the message itself, not invented, so re-running
        # this against the same email always assigns the same id.
        perfil["id_cliente"] = f"auto_{intake['id_mensaje'][:12]}"
        perfil["fecha_admision"] = intake["fecha"]

        estado = ejecutar_pipeline(perfil)
        if estado.error:
            print(f"Pipeline error for {intake['id_mensaje']} ({perfil['datos_basicos']['nombre']!r}): {estado.error}")
            continue

        try:
            registro = guardar_registro_cliente(
                perfil, estado.borrador_rutina, estado.borrador_dieta, estado.veredicto, id_mensaje=intake["id_mensaje"],
            )
        except NotionClientError as exc:
            print(f"Notion error saving {intake['id_mensaje']}: {exc}")
            continue

        nuevos_registros += 1
        print(
            f"Logged new intake for {perfil['datos_basicos']['nombre']} "
            f"({estado.veredicto['veredicto']}): {registro['url']}"
        )

    print(f"Intakes: {nuevos_registros} new client(s) processed.")


def main() -> None:
    procesar_adherencia()
    procesar_intakes_nuevos()


if __name__ == "__main__":
    main()
