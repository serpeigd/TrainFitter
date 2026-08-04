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

DESIGN — "Email Sent" used to be a manual-only checkbox; now auto-checked
too: originally there was no way to detect a real Gmail send without a
broader OAuth scope than this project's deliberately minimal
`gmail.compose` (which can't read the mailbox at all). Once the project
owner explicitly opted into widening that scope (see mcp/gmail_client.py's
docstring for `verificar_envio()`), marcar_email_enviado() became possible:
the UI calls it after confirming via Gmail that a draft's thread now
contains a message with the SENT label — an on-demand check triggered by
the trainer, not a background job (this is a stateless Streamlit app with
no push infrastructure to detect a send passively).

DESIGN — "Email" is filled in at draft-creation time, not send time: the
project owner's idea was to cross-reference a "Check-ins" database by the
client's email once a Gmail draft is actually sent. *Capturing* the address
doesn't need the broader scope at all, since the trainer already types it
into the Gmail section before creating the draft (see ui/app.py). So this
module exposes actualizar_email_cliente() to backfill it onto the
already-created Notion page the moment a draft is made — the join key the
Check-ins automation needs is ready well before the automation is.

DESIGN — Check-ins is a second, append-only database, joined by email
rather than a Notion relation property: the project owner's own call — it
stays simple and would still work if something outside Notion ever needed
to match records later. This "Clients" database is the one master record
per client (overwritten in place, e.g. Email/Email Sent); "Check-ins" is
the history (one new row per interaction — a "Plan sent" row is created
automatically the moment a real send is detected, an "Adherence check-in"
row by main.py when a client's reply is parsed, and the trainer can add
further "Manual check-in" rows by hand over time). No relation property is
set between the two databases; email is the only link.

DESIGN — "Source message ID" makes crear_registro_checkin() idempotent for
main.py's use case: the Gmail inbox trigger (see main.py, mcp/gmail_client.py's
buscar_respuestas_adherencia()) re-scans the whole inbox on every scheduled
run rather than tracking "already seen" state in Gmail itself (see that
module's docstring for why) — so it needs *something* to check before
creating a duplicate row for a reply it already recorded last time. Storing
the Gmail message ID here, and querying for it first via
existe_checkin_para_mensaje(), does that without needing any new Gmail
scope or a separate state file. Only main.py's automated "Adherence
check-in" rows set it — the existing "Plan sent" (ui/app.py) and manual
rows the trainer types in Notion directly have no message ID to attach.

Setup (one-time, free, done by the project owner — never by this code):
  1. Create an integration at https://www.notion.so/my-integrations and
     copy its "Internal Integration Secret".
  2. In Notion, create a "Clients" database with these exact properties:
       Name (title), Date (date), Goal (select), Level (select),
       Verdict (select), Summary (text), Email Sent (checkbox),
       Email (email)
  3. Create a second "Check-ins" database with these properties:
       Name (title), Email (email), Type (select: "Plan sent" /
       "Manual check-in" / "Adherence check-in"), Date (date),
       Adherence notes (text), Adherence rating (select: Low/Medium/High),
       Next follow-up (date), Source message ID (text)
  4. Share both databases with the integration (the "..." menu on each
     database page -> Connections -> add the integration by name).
  5. Set NOTION_API_KEY, NOTION_DATABASE_ID, and NOTION_CHECKINS_DATABASE_ID
     in your .env (see .env.example) — each *_DATABASE_ID is the
     32-character ID in that database's URL.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# database_id -> data_source_id, populated lazily by
# _id_fuente_datos_checkins() below. A database's data source doesn't
# change during a process's lifetime, so caching it here avoids an extra
# databases.retrieve() call on every single existe_checkin_para_mensaje()
# check — main.py calls that once per candidate reply found in the inbox,
# so on a busy run this is the difference between one lookup and one per
# reply.
_CACHE_FUENTE_DATOS: dict[str, str] = {}

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
    # Credentials checked before the lazy import: if notion-client isn't
    # installed (e.g. a deployment where it's deliberately left out) AND
    # credentials aren't set either, the trainer should see the clear
    # "missing credentials" message, not an unrelated ModuleNotFoundError
    # that happens to fire first just because of statement order.
    api_key, database_id = _credenciales()

    from notion_client import Client
    from notion_client.errors import APIResponseError

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
    # Same ordering fix as guardar_registro_cliente(): check credentials
    # before the lazy import, so a missing notion-client package doesn't
    # mask the clearer "missing credentials" error.
    api_key, _ = _credenciales()

    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        cliente.pages.update(page_id=pagina_id, properties={"Email": {"email": email}})
    except APIResponseError as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc


def marcar_email_enviado(pagina_id: str) -> None:
    """
    Checks the "Email Sent" box on an already-created Clients record — called
    once ui/app.py confirms via gmail_client.verificar_envio() that the
    trainer actually hit send on the draft in Gmail, not just created it.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, _ = _credenciales()

    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        cliente.pages.update(page_id=pagina_id, properties={"Email Sent": {"checkbox": True}})
    except APIResponseError as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc


def _checkins_database_id() -> str:
    try:  # dotenv is optional, same convention as _credenciales()
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    database_id = os.environ.get("NOTION_CHECKINS_DATABASE_ID")
    if not database_id:
        raise NotionClientError(
            "Missing NOTION_CHECKINS_DATABASE_ID. Set it in your .env "
            "(see mcp/notion_connector.py's module docstring for the full setup steps)."
        )
    return database_id


def _construir_propiedades_checkin(
    email: str,
    nombre_cliente: str,
    tipo: str,
    fecha: str,
    notas: str = "",
    valoracion: str | None = None,
    id_mensaje: str | None = None,
) -> dict:
    """Builds the Notion page "properties" payload for a Check-ins row.
    Pure function: no I/O, safe to unit test without any credentials —
    same split as _construir_propiedades_pagina() for the Clients
    database."""
    propiedades = {
        "Name": {"title": [{"text": {"content": f"{nombre_cliente} — {fecha}"}}]},
        "Email": {"email": email},
        "Type": {"select": {"name": tipo}},
        "Date": {"date": {"start": fecha}},
    }
    if notas:
        propiedades["Adherence notes"] = {"rich_text": [{"text": {"content": notas[:2000]}}]}
    if valoracion:
        propiedades["Adherence rating"] = {"select": {"name": valoracion}}
    if id_mensaje:
        propiedades["Source message ID"] = {"rich_text": [{"text": {"content": id_mensaje}}]}
    return propiedades


def crear_registro_checkin(
    email: str,
    nombre_cliente: str,
    tipo: str,
    fecha: str,
    notas: str = "",
    valoracion: str | None = None,
    id_mensaje: str | None = None,
) -> dict:
    """
    Adds one row to the "Check-ins" database — the append-only interaction
    history for a client, cross-referenced to the Clients database by email
    (a plain property match, not a Notion relation — see this module's
    docstring for why).

    Args:
        email: the client's email — the join key back to their Clients record.
        nombre_cliente: only used to build a readable title for the row.
        tipo: "Plan sent" (used by ui/app.py right after verificar_envio()
            confirms a real send), "Adherence check-in" (used by main.py
            for a parsed reply — see agents/adherencia_parser.py), or
            "Manual check-in" (anything the trainer adds later by hand).
        fecha: ISO date string (YYYY-MM-DD) for the Date property.
        notas: optional adherence notes for this interaction.
        valoracion: optional "Low"/"Medium"/"High" for the Adherence
            rating select — see pdf_generador.leer_checklist_pdf().
        id_mensaje: optional Gmail message ID for the Source message ID
            property — only main.py's automated rows set this; see the
            module docstring for why it exists (idempotency, not identity).

    Returns:
        {"id": the page's Notion ID, "url": a notion.so link to it}.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure
            (e.g. the Check-ins database wasn't shared with the integration).
    """
    api_key, _ = _credenciales()
    database_id = _checkins_database_id()

    from notion_client import Client
    from notion_client.errors import APIResponseError

    propiedades = _construir_propiedades_checkin(email, nombre_cliente, tipo, fecha, notas, valoracion, id_mensaje)

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.create(parent={"database_id": database_id}, properties=propiedades)
    except APIResponseError as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return {"id": pagina["id"], "url": pagina["url"]}


def existe_checkin_para_mensaje(id_mensaje: str) -> bool:
    """
    Checks whether a Check-ins row already exists for a given Gmail message
    ID — main.py calls this before creating a new "Adherence check-in" row,
    so a scheduled run that re-scans the whole inbox doesn't duplicate a
    reply it already recorded on a previous run (see this module's
    docstring for why dedup lives here instead of in Gmail).

    Args:
        id_mensaje: the Gmail message ID (see
            mcp.gmail_client.buscar_respuestas_adherencia()).

    Returns:
        True if a row with this Source message ID already exists.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, _ = _credenciales()
    database_id = _checkins_database_id()

    from notion_client import Client
    from notion_client.errors import APIResponseError

    # databases.query() was removed from the SDK once Notion's 2025-09-03
    # API moved querying to the per-data-source endpoint (multi-source
    # databases) -- database_id is still accepted as a page *parent* for
    # backward compatibility (see crear_registro_checkin() above), but
    # querying needs the actual data_source_id, resolved via
    # databases.retrieve() and cached in _CACHE_FUENTE_DATOS (see its own
    # comment). Checked against a real workspace, not assumed from
    # changelog text -- databases.query genuinely raises AttributeError on
    # notion-client>=3.
    try:
        cliente = Client(auth=api_key)
        if database_id not in _CACHE_FUENTE_DATOS:
            base_datos = cliente.databases.retrieve(database_id=database_id)
            _CACHE_FUENTE_DATOS[database_id] = base_datos["data_sources"][0]["id"]
        resultado = cliente.data_sources.query(
            data_source_id=_CACHE_FUENTE_DATOS[database_id],
            filter={"property": "Source message ID", "rich_text": {"equals": id_mensaje}},
        )
    except APIResponseError as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return len(resultado["results"]) > 0
