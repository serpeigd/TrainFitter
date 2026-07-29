"""
Notion connector: saves a lightweight, persistent record of each generated
plan to a Notion database — the trainer's own workspace, not the client's.

DESIGN — why this exists at all: every other part of the pipeline lives and
dies within one Streamlit session (reload the page, everything's gone unless
you downloaded the JSON). This isn't a communication channel like Gmail —
nothing here ever reaches the client — it's a lightweight CRM: one row per
client so the trainer has something to search through later.

DESIGN — summarized record, not the full plan: this saves name, date, goal,
level, verdict, and a short combined summary — not every exercise or food
source. Enough to find and recognize a case later; the full JSON is already
downloadable from the UI for anyone who needs the complete draft.

DESIGN — fires automatically, scoped to real intakes only: unlike the Gmail
draft (an explicit button — creating a real, addressed message deserves a
deliberate click), saving a summary row to the trainer's *own* private
workspace doesn't need one. It still only fires for the "New Client" section
(ui/app.py), not the "Example client" one — a visitor to the public demo
clicking through the example clients shouldn't clutter the trainer's actual
Notion database with demo runs.

DESIGN — no OAuth flow: Notion's "internal integration" tokens are a static
secret (like an API key), not a three-legged OAuth flow like Gmail's — no
browser consent screen, no token refresh cycle. Simpler setup, same secret-
handling discipline (env var, never committed — see .env.example).

DESIGN — "Email Sent" is a manual checkbox, not an automated one: it's
initialized to False here so the trainer has a follow-up flag to tick
themselves, in Notion, once they've actually hit send on the Gmail draft
(see mcp/gmail_client.py). Automatically detecting a real send would need
either a broader Gmail OAuth scope than the deliberately minimal
`gmail.compose` this project uses (which can't read the mailbox at all —
see gmail_client.py's docstring), or push-notification infrastructure that
doesn't fit a Streamlit app with no persistent backend. Deliberately not
built — the manual checkbox gets the actual follow-up value (a filterable
"who's still pending" view in Notion) without weakening the send-scope
guarantee that was a considered trade-off elsewhere in this project.

DESIGN — "Email" is filled in at draft-creation time, not send time: the
project owner's next idea was to cross-reference a future "Check-ins"
database by the client's email once a Gmail draft is actually sent. The
"actually sent" part is still blocked on the same broader-OAuth-scope
trade-off as "Email Sent" above — but *capturing* the address doesn't need
that at all, since the trainer already types it into the Gmail section
before creating the draft (see ui/app.py). So this module exposes
actualizar_email_cliente() to backfill it onto the already-created Notion
page the moment a draft is made, well ahead of when "detect a real send"
becomes possible — the join key future automation would need is ready
before the automation itself is.

Setup (one-time, free, done by the project owner — never by this code):
  1. Create an integration at https://www.notion.so/my-integrations and
     copy its "Internal Integration Secret".
  2. In Notion, create a database with these exact properties:
       Name (title), Date (date), Goal (select), Level (select),
       Verdict (select), Summary (text), Email Sent (checkbox),
       Email (email)
  3. Share that database with the integration (the "..." menu on the
     database page -> Connections -> add the integration by name).
  4. Set NOTION_API_KEY and NOTION_DATABASE_ID in your .env (see
     .env.example) — NOTION_DATABASE_ID is the 32-character ID in the
     database's URL.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Display-only English labels for schema values that stay in Spanish
# internally (see docs/decisiones.md) — same convention as ui/app.py's
# OPTION_LABELS, kept local here since this is the only other place that
# turns raw profile values into human-readable text for an external system.
OBJETIVO_LABELS = {
    "hipertrofia": "Hypertrophy",
    "perdida_grasa": "Fat loss",
    "recomposicion_corporal": "Recomposition",
    "salud_general": "General health",
}
NIVEL_LABELS = {"principiante": "Beginner", "intermedio": "Intermediate", "avanzado": "Advanced"}
VEREDICTO_LABELS = {"aprobado_automatico": "Approved", "revision_reforzada": "Enhanced review"}


class NotionClientError(Exception):
    """Raised for anything that stops the record from being saved — missing
    credentials or a Notion API failure. The UI is expected to catch this
    and skip silently rather than interrupt the trainer's flow over a
    best-effort background save."""


def _construir_resumen(borrador_rutina: dict, borrador_dieta: dict) -> str:
    """Short combined summary. Pure formatting — no network, no auth,
    trivially unit-testable. Truncated to Notion's 2000-char rich_text
    limit per block."""
    resumen = (
        f"Routine: {borrador_rutina['resumen_enfoque']} "
        f"Diet: {borrador_dieta['resumen_enfoque']} "
        f"({borrador_dieta['calorias_objetivo_kcal']} kcal/day, "
        f"{borrador_dieta['macros']['proteina_g']} g protein)"
    )
    return resumen[:2000]


def _construir_propiedades_pagina(
    perfil_cliente: dict, borrador_rutina: dict, borrador_dieta: dict, veredicto: dict
) -> dict:
    """Builds the Notion page "properties" payload matching the database
    schema documented in this module's docstring. Pure function: no I/O,
    safe to unit test without any credentials."""
    datos = perfil_cliente["datos_basicos"]
    objetivo = perfil_cliente["objetivo"]["principal"]
    nivel = perfil_cliente["experiencia"]["nivel"]

    return {
        "Name": {"title": [{"text": {"content": datos["nombre"]}}]},
        "Date": {"date": {"start": perfil_cliente.get("fecha_admision")}},
        "Goal": {"select": {"name": OBJETIVO_LABELS.get(objetivo, objetivo)}},
        "Level": {"select": {"name": NIVEL_LABELS.get(nivel, nivel)}},
        "Verdict": {"select": {"name": VEREDICTO_LABELS.get(veredicto["veredicto"], veredicto["veredicto"])}},
        "Summary": {"rich_text": [{"text": {"content": _construir_resumen(borrador_rutina, borrador_dieta)}}]},
        "Email Sent": {"checkbox": False},
    }


def _credenciales() -> tuple[str, str]:
    try:  # dotenv is optional, same convention as agents/run_routine_demo.py
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    api_key = os.environ.get("NOTION_API_KEY")
    database_id = os.environ.get("NOTION_DATABASE_ID")
    if not api_key or not database_id:
        raise NotionClientError(
            "Missing NOTION_API_KEY and/or NOTION_DATABASE_ID. Set them in your .env "
            "(see mcp/notion_connector.py's module docstring for the full setup steps)."
        )
    return api_key, database_id


def guardar_registro_cliente(
    perfil_cliente: dict, borrador_rutina: dict, borrador_dieta: dict, veredicto: dict
) -> dict:
    """
    Saves a summarized record of this client's plan as a new page in the
    trainer's Notion database.

    Returns:
        {"id": the page's Notion ID, "url": a notion.so link to it}. The ID
        is what actualizar_email_cliente() needs later — the URL alone
        isn't enough to address a follow-up API call.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure
            (e.g. the database wasn't shared with the integration).
    """
    from notion_client import Client
    from notion_client.errors import APIResponseError

    api_key, database_id = _credenciales()
    propiedades = _construir_propiedades_pagina(perfil_cliente, borrador_rutina, borrador_dieta, veredicto)

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.create(parent={"database_id": database_id}, properties=propiedades)
    except APIResponseError as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return {"id": pagina["id"], "url": pagina["url"]}


def actualizar_email_cliente(pagina_id: str, email: str) -> None:
    """
    Backfills the "Email" property on an already-created record — called
    once a Gmail draft is created for that same client (see ui/app.py),
    since the recipient address isn't known yet at guardar_registro_cliente()
    time (approval happens before the trainer has necessarily typed it in).

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    from notion_client import Client
    from notion_client.errors import APIResponseError

    api_key, _ = _credenciales()

    try:
        cliente = Client(auth=api_key)
        cliente.pages.update(page_id=pagina_id, properties={"Email": {"email": email}})
    except APIResponseError as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc
