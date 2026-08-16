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

DESIGN — "Language" records which UI language (en/es) a plan was actually
generated in, straight from st.session_state.lang at save time: the
client portal used to always render its own chrome in English regardless
of what language the client's routine/diet text itself was written in
(real complaint from live use), because a fresh client browser session
has no way to know which language the trainer used. Read back by
_vista_portal_cliente() to set the page's own language before rendering
anything, exactly like the trainer's own language toggle already does for
the rest of this file's translated strings. Defaults to "en" for older
records saved before this property existed, matching this project's
existing "en" default everywhere idioma is threaded through.

DESIGN — generar_referencia_portal()/resolver_referencia_portal() replaced
agents/portal_tokens.py's stateless, signed HMAC token entirely: that
design encoded the client's email + Notion page ID + expiry directly into
the URL, base64'd and hex-signed, which produced a genuinely unusable
~250-character link (real complaint from live use — "queda algo raro").
The fix trades the "verifiable with zero network calls" property for a
short, opaque ~8-character code (`secrets.token_urlsafe`) stored on the
client's own Clients record ("Portal Reference"/"Portal Reference
Expires") and resolved with one Notion lookup — a real trade against the
project's general "avoid new backend state" bias, but a narrow one: no
new database, just two more properties on a record that already exists
per client, and the portal already makes a Notion call immediately after
resolving the link anyway (obtener_registro_cliente()), so "zero network
calls to verify" was never actually saving a round trip in practice.
Tamper-resistance doesn't need a signature here either — the code is
random and opaque, not a payload a client could edit to point elsewhere;
guessing another valid code is exactly as hard as guessing a signed
token of comparable length. Genuine trade-offs, disclosed rather than
glossed over: (1) a portal link sent under the old format stops working
the moment this shipped — no backward-compat shim, a fresh link is one
click away; (2) the trainer can now revoke a link early by clearing the
Notion property by hand, something the old design explicitly couldn't do.

DESIGN — "Routine Message"/"Diet Message" bring concrete, client-facing
content back into the portal, direct follow-up after "Aplica esto
también al portal": the portal had shown a technical "resumen_enfoque"
summary, then nothing at all once that was cut for being unreadable
prose (see the reference-link DESIGN note above). What's stored here
ISN'T the raw mensaje_para_el_cliente (the trainer's generic warm note,
e.g. "aquí tienes tu borrador... cuéntamelo y lo solucionamos") -- a
second, same-day cut removed that from every client-facing surface,
after bulleting the whole message still read as "MUY generales y mucho
texto" against a real pasted example. gmail_client.obtener_texto_cliente()
computes the same minimal, concrete text the plan email itself now
shows (a real tip -- progresion/consejos_sinergias -- or, only if no tip
exists, the message's own first sentence) and this stores THAT, so
_vista_portal_cliente() renders the identical bullets the email does via
dividir_en_puntos(), not a second, looser summary. Already
greeting-stripped and reduced at save time (unlike an earlier version of
this property, which stored the raw message and stripped it at render
time) -- notion_connector.py needing the client's name for that is why
this whole function takes `idioma` and reads `datos["nombre"]` before
building "Routine Message"/"Diet Message". Plain rich_text, no chunking
(see _dividir_bloques_notion() above) -- this is always well under the
2000-char block limit, unlike "Full Profile (JSON)".

DESIGN — obtener_registro_cliente() feeds the client portal without
needing the full profile: a client following their own magic link (see
generar_referencia_portal() above) only ever needs to see a short "your plan"
summary, so it reads back the same summarized fields
guardar_registro_cliente() already saved for the trainer's own panel —
nothing client-facing reads "Full Profile (JSON)" (below), and it never
will. That's a deliberately narrower read than what's now actually stored
(see the next note).

DESIGN — "Full Profile (JSON)" makes a client genuinely revisable, at
the cost of a real, requested trade-off: every Clients record now also
carries the complete perfil_cliente as a chunked rich_text property
(see _dividir_bloques_notion()/_unir_bloques_notion() — a single 2000-
char rich_text block isn't enough for a full profile, so it's split
across several and reassembled on read). This reverses this module's
original "no second copy of the plan anywhere" stance from when the
client portal was first built — deliberately, on the project owner's own
explicit choice between the lighter option (just log weight, retype a
fresh intake by hand to regenerate) and this one (persist enough to
actually reload and edit an existing client). obtener_perfil_completo()
and buscar_cliente_por_email() are trainer-only — reachable from
ui/app.py's "Revise client" section, never from the client portal, which
still only ever reads the summarized fields above.

DESIGN — "Weekly Meal Plan (JSON)"/"Liked Meals (JSON)" reverse an
explicit "the portal doesn't need a second copy of the full plan"
stance, the same way "Full Profile (JSON)" reversed the original
summary-only design above — this time so the client portal can show the
client their own current week's meals and let them mark one to repeat
(see agents/planificador_comidas.py's _sesgar_por_favoritos()). Kept as
two separate properties from "Full Profile (JSON)" on purpose:
"Weekly Meal Plan" is trainer-written, read-only from the portal (same
as the rest of what obtener_registro_cliente() exposes); "Liked Meals"
is the one property the portal ever WRITES to (agregar_comida_favorita()
below), scoped to exactly that field via its own read-modify-write so a
client marking a favorite can never race with or clobber a trainer's
concurrent edit to the rest of the profile.

DESIGN — "Weekly Routine (JSON)"/"Liked Exercises (JSON)" are the exact
same pair, mirrored for the routine side: the portal shows the client
their current week's sessions and lets them mark an exercise to repeat
(see agents/rutina_reglas.py's own _sesgar_por_favoritos()). Same split
for the same reason — "Weekly Routine" trainer-written/portal-read,
"Liked Exercises" the one field the portal ever writes, via its own
scoped read-modify-write (agregar_ejercicio_favorito() below).

DESIGN — actualizar_registro_cliente() updates the existing page in
place rather than creating a new one: the "one master record per client"
principle stated below (Check-ins is the append-only history; Clients is
not) applies just as much to a revision as it does to Email/Email Sent —
revising a client's plan corrects that same record, it doesn't create a
second one alongside it. It deliberately leaves "Email Sent" untouched
(unlike guardar_registro_cliente(), which always initializes it to
False) — revising a client doesn't undo what the trainer already
confirmed about the original plan's send status.

DESIGN — "Weight (kg)" on Check-ins closes a loop the rule engines
already claimed existed: dieta_reglas.py's own generated message tells
the client their plan "gets adjusted based on real weight and energy
over the first few weeks" — but until this property existed, there was
no path for that real weight to ever reach anywhere. The portal's
check-in form (ui/app.py) can now log it optionally alongside the usual
adherence numbers, visible in the same "Adherence history" view the
trainer already has, and included in the trainer notification email
(see mcp/gmail_client.py's enviar_notificacion_checkin()).

Setup (one-time, free, done by the project owner — never by this code):
  1. Create an integration at https://www.notion.so/my-integrations and
     copy its "Internal Integration Secret".
  2. In Notion, create a "Clients" database with these exact properties:
       Name (title), Date (date), Goal (select), Level (select),
       Verdict (select), Summary (text), Email Sent (checkbox),
       Email (email), Source message ID (text),
       Full Profile (JSON) (text), Weekly Meal Plan (JSON) (text),
       Liked Meals (JSON) (text), Weekly Routine (JSON) (text),
       Liked Exercises (JSON) (text), Portal Reference (text),
       Portal Reference Expires (date), Language (select: en/es),
       Routine Message (text), Diet Message (text)
  3. Create a second "Check-ins" database with these properties:
       Name (title), Email (email), Type (select: "Plan sent" /
       "Manual check-in" / "Adherence check-in"), Date (date),
       Adherence notes (text), Adherence rating (select: Low/Medium/High),
       Next follow-up (date), Source message ID (text), Weight (kg) (number)
  4. Share both databases with the integration (the "..." menu on each
     database page -> Connections -> add the integration by name).
  5. Set NOTION_API_KEY, NOTION_DATABASE_ID, and NOTION_CHECKINS_DATABASE_ID
     in your .env (see .env.example) — each *_DATABASE_ID is the
     32-character ID in that database's URL.
"""

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DIAS_VALIDEZ_REFERENCIA_POR_DEFECTO = 7

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
# Reverse of OBJETIVO_LABELS -- lets a portal-safe read (the "Goal" select
# property, not remotely as sensitive as the rest of "Full Profile (JSON)")
# hand back the internal Spanish key agents/adherencia_parser.py's
# tendencia_peso() expects, instead of every caller needing its own copy
# of this mapping.
_LABEL_A_OBJETIVO = {etiqueta: clave for clave, etiqueta in OBJETIVO_LABELS.items()}
NIVEL_LABELS = {"principiante": "Beginner", "intermedio": "Intermediate", "avanzado": "Advanced"}
VEREDICTO_LABELS = {"aprobado_automatico": "Approved", "revision_reforzada": "Enhanced review"}


class NotionClientError(Exception):
    """Raised for anything that stops the record from being saved — missing
    credentials or a Notion API failure. The UI is expected to catch this
    and skip silently rather than interrupt the trainer's flow over a
    best-effort background save."""


class PortalTokenError(Exception):
    """Raised when a client portal link's reference code doesn't resolve --
    missing, mistyped, unknown, or expired. ui/app.py is expected to catch
    this and show a plain "this link isn't valid" message instead of
    crashing. Lives here (not in a dedicated module) because resolving a
    reference now IS a Notion lookup -- see generar_referencia_portal()'s
    docstring for why the earlier stateless-signed-token design (agents/
    portal_tokens.py, removed) was replaced."""


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


LIMITE_BLOQUE_NOTION = 1900  # headroom under the API's real 2000-char-per-rich_text-block limit


def _dividir_bloques_notion(texto: str) -> list[dict]:
    """Splits a long string into Notion rich_text blocks, each safely
    under the API's 2000-char-per-block limit -- needed for "Full Profile
    (JSON)" below, which routinely exceeds that in a single block. Pure
    function, no I/O. Always returns at least one block (an empty one for
    empty input), matching the shape every other rich_text property in
    this module already uses."""
    if not texto:
        return [{"text": {"content": ""}}]
    return [
        {"text": {"content": texto[i:i + LIMITE_BLOQUE_NOTION]}}
        for i in range(0, len(texto), LIMITE_BLOQUE_NOTION)
    ]


def _unir_bloques_notion(propiedad: dict) -> str:
    """Reassembles a chunked rich_text property back into one string --
    the inverse of _dividir_bloques_notion(). Pure function, no I/O.
    Reads "plain_text" (what a real API response carries), not "text"
    (what a request body carries) -- the two are asymmetric, same as
    every other rich_text reader already in this module
    (_fila_checkin_desde_pagina() etc.)."""
    return "".join(bloque["plain_text"] for bloque in propiedad.get("rich_text", []))


def _construir_propiedades_pagina(
    perfil_cliente: dict, borrador_rutina: dict, borrador_dieta: dict, veredicto: dict, id_mensaje: str | None = None,
    idioma: str = "en",
) -> dict:
    """Builds the Notion page "properties" payload matching the database
    schema documented in this module's docstring. Pure function: no I/O,
    safe to unit test without any credentials.

    id_mensaje: optional Gmail message ID, set only when main.py's
    automated intake trigger creates this record (see
    mcp.gmail_client.buscar_intakes_nuevos()) -- lets
    existe_cliente_para_mensaje() dedupe a re-scanned inbox the same way
    Check-ins already does for adherence replies. A trainer approving a
    plan manually through ui/app.py never sets this.

    idioma: "en" (default) or "es" -- the UI language the plan was
    generated in (see this module's "Language" DESIGN note above)."""
    from gmail_client import obtener_texto_cliente

    datos = perfil_cliente["datos_basicos"]
    objetivo = perfil_cliente["objetivo"]["principal"]
    nivel = perfil_cliente["experiencia"]["nivel"]
    tips_dieta = borrador_dieta.get("consejos_sinergias") or []
    texto_rutina = obtener_texto_cliente(
        borrador_rutina.get("mensaje_para_el_cliente", ""), datos["nombre"], idioma, borrador_rutina.get("progresion", ""),
    )
    texto_dieta = obtener_texto_cliente(
        borrador_dieta.get("mensaje_para_el_cliente", ""), datos["nombre"], idioma, tips_dieta[0] if tips_dieta else "",
    )

    propiedades = {
        "Name": {"title": [{"text": {"content": datos["nombre"]}}]},
        "Date": {"date": {"start": perfil_cliente.get("fecha_admision")}},
        "Goal": {"select": {"name": OBJETIVO_LABELS.get(objetivo, objetivo)}},
        "Level": {"select": {"name": NIVEL_LABELS.get(nivel, nivel)}},
        "Verdict": {"select": {"name": VEREDICTO_LABELS.get(veredicto["veredicto"], veredicto["veredicto"])}},
        "Summary": {"rich_text": [{"text": {"content": _construir_resumen(borrador_rutina, borrador_dieta)}}]},
        "Language": {"select": {"name": idioma}},
        "Email Sent": {"checkbox": False},
        "Full Profile (JSON)": {
            "rich_text": _dividir_bloques_notion(json.dumps(perfil_cliente, ensure_ascii=False))
        },
        "Weekly Meal Plan (JSON)": {
            "rich_text": _dividir_bloques_notion(
                json.dumps(borrador_dieta.get("plan_semanal") or [], ensure_ascii=False)
            )
        },
        "Weekly Routine (JSON)": {
            "rich_text": _dividir_bloques_notion(
                json.dumps(borrador_rutina.get("sesiones") or [], ensure_ascii=False)
            )
        },
        "Routine Message": {"rich_text": [{"text": {"content": texto_rutina[:2000]}}]},
        "Diet Message": {"rich_text": [{"text": {"content": texto_dieta[:2000]}}]},
    }
    if id_mensaje:
        propiedades["Source message ID"] = {"rich_text": [{"text": {"content": id_mensaje}}]}
    return propiedades


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
    perfil_cliente: dict, borrador_rutina: dict, borrador_dieta: dict, veredicto: dict, id_mensaje: str | None = None,
    idioma: str = "en",
) -> dict:
    """
    Saves a summarized record of this client's plan as a new page in the
    trainer's Notion database.

    Args:
        perfil_cliente, borrador_rutina, borrador_dieta, veredicto: same as before.
        id_mensaje: optional Gmail message ID — only main.py's automated
            intake trigger sets this (see
            mcp.gmail_client.buscar_intakes_nuevos()); ui/app.py's manual
            approval flow never does. See
            _construir_propiedades_pagina()'s docstring for why it exists.
        idioma: "en" (default) or "es" — passed straight to
            _construir_propiedades_pagina() (see this module's "Language"
            DESIGN note).

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

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    propiedades = _construir_propiedades_pagina(
        perfil_cliente, borrador_rutina, borrador_dieta, veredicto, id_mensaje, idioma,
    )

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.create(parent={"database_id": database_id}, properties=propiedades)
    except (APIResponseError, HTTPError) as exc:
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

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        cliente.pages.update(page_id=pagina_id, properties={"Email": {"email": email}})
    except (APIResponseError, HTTPError) as exc:
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

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        cliente.pages.update(page_id=pagina_id, properties={"Email Sent": {"checkbox": True}})
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc


def actualizar_registro_cliente(
    pagina_id: str, perfil_cliente: dict, borrador_rutina: dict, borrador_dieta: dict, veredicto: dict,
    idioma: str = "en",
) -> dict:
    """
    Overwrites an existing Clients record in place with a revised plan --
    used when the trainer edits and re-approves a client loaded via
    buscar_cliente_por_email() (see ui/app.py's "Revise client" section),
    instead of guardar_registro_cliente() creating a brand-new row. See
    this module's docstring for why a revision updates the same record
    rather than duplicating it.

    Deliberately does NOT reset "Email Sent" to False, unlike a fresh
    guardar_registro_cliente() call -- revising a client doesn't undo
    whatever the trainer already confirmed about the original plan's
    send status.

    idioma: "en" (default) or "es" — same as guardar_registro_cliente();
    a revision regenerated in a different language updates "Language" too.

    Returns:
        {"id": the page's Notion ID, "url": a notion.so link to it} --
        same shape as guardar_registro_cliente(), so callers (e.g. the
        Gmail-draft email backfill in ui/app.py) don't need to know which
        one ran.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, _ = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    propiedades = _construir_propiedades_pagina(perfil_cliente, borrador_rutina, borrador_dieta, veredicto, idioma=idioma)
    del propiedades["Email Sent"]

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.update(page_id=pagina_id, properties=propiedades)
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return {"id": pagina["id"], "url": pagina["url"]}


def _fila_registro_cliente_desde_pagina(pagina: dict) -> dict:
    """Extracts the fields the client portal needs to show from a raw
    Clients page object. Pure function: no I/O, safe to unit test with a
    hand-built page dict instead of a real API response -- same pattern as
    _fila_checkin_desde_pagina() below.

    "plan_semanal"/"sesiones" default to [] (not an error) for a record
    saved before "Weekly Meal Plan (JSON)"/"Weekly Routine (JSON)"
    existed, or one whose JSON is somehow corrupt -- the rest of the
    portal page (routine/diet summary, history) still renders; the
    "this week's meals"/"this week's routine" section just has nothing to
    show, same degrade-gracefully spirit as this module's other
    best-effort reads. "mensaje_rutina"/"mensaje_dieta" default to ""
    the same way, for a record saved before "Routine Message"/"Diet
    Message" existed.

    "objetivo" is the internal Spanish key (via _LABEL_A_OBJETIVO), not
    the raw "Goal" select label -- a client's goal is already effectively
    visible in "resumen"'s own prose ("geared toward fat loss," etc.), so
    exposing the structured value too isn't a new disclosure, just a
    usable one: ui/app.py's portal check-in flow needs it to call
    agents/adherencia_parser.py's tendencia_peso(). None if the page has
    no recognized Goal value (an older record, or the select was cleared)."""
    propiedades = pagina["properties"]
    nombre = "".join(t["plain_text"] for t in propiedades.get("Name", {}).get("title", []))
    resumen = "".join(t["plain_text"] for t in propiedades.get("Summary", {}).get("rich_text", []))
    veredicto = (propiedades.get("Verdict", {}).get("select") or {}).get("name")
    fecha = (propiedades.get("Date", {}).get("date") or {}).get("start")
    objetivo_label = (propiedades.get("Goal", {}).get("select") or {}).get("name")
    objetivo = _LABEL_A_OBJETIVO.get(objetivo_label)
    # Defaults to "en" for a record saved before "Language" existed --
    # matches every other idioma default in this project.
    idioma = (propiedades.get("Language", {}).get("select") or {}).get("name") or "en"
    texto_plan = _unir_bloques_notion(propiedades.get("Weekly Meal Plan (JSON)", {}))
    try:
        plan_semanal = json.loads(texto_plan) if texto_plan else []
    except ValueError:
        plan_semanal = []
    texto_rutina = _unir_bloques_notion(propiedades.get("Weekly Routine (JSON)", {}))
    try:
        sesiones = json.loads(texto_rutina) if texto_rutina else []
    except ValueError:
        sesiones = []
    mensaje_rutina = _unir_bloques_notion(propiedades.get("Routine Message", {}))
    mensaje_dieta = _unir_bloques_notion(propiedades.get("Diet Message", {}))
    return {
        "nombre": nombre, "resumen": resumen, "veredicto": veredicto, "fecha": fecha,
        "objetivo": objetivo, "plan_semanal": plan_semanal, "sesiones": sesiones, "idioma": idioma,
        "mensaje_rutina": mensaje_rutina, "mensaje_dieta": mensaje_dieta,
    }


def generar_referencia_portal(
    pagina_id: str, email: str, dias_validez: int = DIAS_VALIDEZ_REFERENCIA_POR_DEFECTO,
) -> str:
    """
    Issues a short, opaque reference code identifying one client's portal
    session, stored on their own Clients record -- the short-link
    replacement for agents/portal_tokens.py's removed signed-token design
    (see this module's DESIGN note above for the full reasoning). Returns
    a URL-safe string meant to go straight into a `?ref=...` query param.

    Also backfills the "Email" property (the same write
    actualizar_email_cliente() already does elsewhere) so
    resolver_referencia_portal() can always read it back -- the trainer
    has already typed this address into the panel section that triggers
    this call, regardless of whether a Gmail draft was ever created for
    this client.

    Raises:
        NotionClientError: missing credentials, a Notion API failure, or
            (astronomically unlikely with 48 bits of entropy) 5
            consecutive collisions against existing codes.
    """
    api_key, database_id = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        data_source_id = _id_fuente_datos(cliente, database_id)

        codigo = None
        for _intento in range(5):
            candidato = secrets.token_urlsafe(6)
            resultado = cliente.data_sources.query(
                data_source_id=data_source_id,
                filter={"property": "Portal Reference", "rich_text": {"equals": candidato}},
                page_size=1,
            )
            if not resultado["results"]:
                codigo = candidato
                break
        if codigo is None:
            raise NotionClientError("Could not generate a unique portal reference after 5 attempts.")

        expira = (datetime.now(timezone.utc) + timedelta(days=dias_validez)).isoformat()
        cliente.pages.update(
            page_id=pagina_id,
            properties={
                "Email": {"email": email},
                "Portal Reference": {"rich_text": [{"text": {"content": codigo}}]},
                "Portal Reference Expires": {"date": {"start": expira}},
            },
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return codigo


def resolver_referencia_portal(codigo: str) -> dict:
    """
    Resolves a client portal reference code (from a `?ref=...` query
    param) back to the client's email and Notion page ID -- the read side
    of generar_referencia_portal() above, and the direct replacement for
    agents/portal_tokens.py's removed verificar_token_portal().

    Returns:
        {"email": ..., "pagina": the Notion page ID}.

    Raises:
        PortalTokenError: the code doesn't match any record, the matching
            record has no reference expiry on file, or it's expired.
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, database_id = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        resultado = cliente.data_sources.query(
            data_source_id=_id_fuente_datos(cliente, database_id),
            filter={"property": "Portal Reference", "rich_text": {"equals": codigo}},
            page_size=1,
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    if not resultado["results"]:
        raise PortalTokenError("This portal link isn't valid.")

    propiedades = resultado["results"][0]["properties"]
    expira_str = (propiedades.get("Portal Reference Expires", {}).get("date") or {}).get("start")
    if not expira_str or datetime.fromisoformat(expira_str) < datetime.now(timezone.utc):
        raise PortalTokenError("This portal link has expired -- ask your trainer for a new one.")

    email = (propiedades.get("Email", {}) or {}).get("email")
    if not email:
        raise PortalTokenError("This portal link isn't valid.")

    return {"email": email, "pagina": resultado["results"][0]["id"]}


def obtener_registro_cliente(pagina_id: str) -> dict:
    """
    Reads back a Clients record's client-facing fields -- what the portal
    (a client following their own magic link, see
    generar_referencia_portal()/resolver_referencia_portal() above) shows
    as "your plan". Reads the routine+diet summary (name, verdict,
    admission date, "Summary"'s 2000-char truncated content -- see this
    module's docstring) PLUS the full "Weekly Meal Plan (JSON)"/"Weekly
    Routine (JSON)" -- a deliberate, later reversal of this function's
    original "no second copy of the full plan" design, made so the portal
    can show the client's actual current week's meals/sessions and let
    them mark one to repeat (see this module's docstring,
    agents/planificador_comidas.py's _sesgar_por_favoritos(), and
    agents/rutina_reglas.py's own). Still never reads "Full Profile
    (JSON)" -- the client's declared injuries/allergies/medication stay
    trainer-only.

    Args:
        pagina_id: the Notion page ID returned by guardar_registro_cliente()
            (resolved from the magic link's reference code via
            resolver_referencia_portal(), never typed by the client).

    Returns:
        {"nombre", "resumen", "veredicto", "fecha", "plan_semanal", "sesiones",
        "idioma", "mensaje_rutina", "mensaje_dieta"}.

    Raises:
        NotionClientError: missing credentials, the page doesn't exist
            (e.g. a stale link to a record that got deleted), or another
            Notion API failure.
    """
    api_key, _ = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.retrieve(page_id=pagina_id)
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return _fila_registro_cliente_desde_pagina(pagina)


def agregar_comida_favorita(pagina_id: str, comida: dict) -> None:
    """
    Appends one liked meal to a client's "Liked Meals (JSON)" property --
    called from the client portal when they mark a meal from their
    current week's plan (obtener_registro_cliente()'s "plan_semanal") as
    one they'd like to see again. agents/planificador_comidas.py's
    _sesgar_por_favoritos() reads this back (via _perfil_desde_propiedades()
    merging it into perfil["nutricion"]["comidas_favoritas"]) the next
    time a plan is regenerated for this client.

    Its own narrow property, deliberately separate from "Full Profile
    (JSON)": a read-modify-write that only ever touches this one field,
    so a client marking a favorite from the portal can never race with
    (or clobber) a trainer's own concurrent edit to the rest of the
    profile. Dedupes by exact match (same tipo/proteina/carbohidrato/
    grasa) -- liking the same meal twice doesn't inflate its odds of
    reappearing.

    Args:
        pagina_id: the Notion page ID (from the portal's signed token).
        comida: {"tipo": "desayuno"|"comida"|"cena"|"snack",
            "proteina": str | None, "carbohidrato": str | None,
            "grasa": str | None} -- matches plan_semanal's own
            "tipo_interno" (renamed to "tipo" here)/"proteina"/
            "carbohidrato"/"grasa" fields.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, _ = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.retrieve(page_id=pagina_id)
        texto_actual = _unir_bloques_notion(pagina["properties"].get("Liked Meals (JSON)", {}))
        try:
            favoritas = json.loads(texto_actual) if texto_actual else []
        except ValueError:
            favoritas = []  # corrupt existing data -- start fresh rather than blocking the like
        if comida not in favoritas:
            favoritas.append(comida)
        cliente.pages.update(
            page_id=pagina_id,
            properties={
                "Liked Meals (JSON)": {
                    "rich_text": _dividir_bloques_notion(json.dumps(favoritas, ensure_ascii=False))
                }
            },
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc


def agregar_ejercicio_favorito(pagina_id: str, ejercicio: dict) -> None:
    """
    Appends one liked exercise to a client's "Liked Exercises (JSON)"
    property -- called from the client portal when they mark an exercise
    from their current week's routine (obtener_registro_cliente()'s
    "sesiones") as one they'd like to see again. agents/rutina_reglas.py's
    _sesgar_por_favoritos() reads this back (via _perfil_desde_propiedades()
    merging it into perfil["experiencia"]["ejercicios_favoritos"]) the
    next time a routine is regenerated for this client.

    Same shape as agregar_comida_favorita() above, mirrored: its own
    narrow property, a read-modify-write that only ever touches this one
    field, so a client marking a favorite from the portal can never race
    with (or clobber) a trainer's own concurrent edit to the rest of the
    profile. Dedupes by exact match (same grupo/tipo/nombre) -- liking the
    same exercise twice doesn't inflate its odds of reappearing.

    Args:
        pagina_id: the Notion page ID (from the portal's signed token).
        ejercicio: {"grupo": str, "tipo": "basico"|"aislamiento",
            "nombre": str} -- matches sesiones' own exercise entries'
            "grupo"/"tipo"/"nombre" fields.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, _ = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.retrieve(page_id=pagina_id)
        texto_actual = _unir_bloques_notion(pagina["properties"].get("Liked Exercises (JSON)", {}))
        try:
            favoritos = json.loads(texto_actual) if texto_actual else []
        except ValueError:
            favoritos = []  # corrupt existing data -- start fresh rather than blocking the like
        if ejercicio not in favoritos:
            favoritos.append(ejercicio)
        cliente.pages.update(
            page_id=pagina_id,
            properties={
                "Liked Exercises (JSON)": {
                    "rich_text": _dividir_bloques_notion(json.dumps(favoritos, ensure_ascii=False))
                }
            },
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc


def obtener_perfil_completo(pagina_id: str) -> dict:
    """
    Reads back a Clients record's FULL perfil_cliente -- trainer-only
    (see ui/app.py's "Revise client" section), never exposed to the
    client portal (obtener_registro_cliente() above stays deliberately
    limited to the client-facing summary fields; this function's result
    is never sent anywhere near a client). Lets the trainer load an
    existing client's complete intake to edit and regenerate, instead of
    retyping it from scratch.

    Args:
        pagina_id: the Notion page ID to load.

    Returns:
        The perfil_cliente dict exactly as originally saved by
        guardar_registro_cliente()/actualizar_registro_cliente().

    Raises:
        NotionClientError: missing credentials, the page doesn't exist,
            it predates this property existing (an older record with no
            "Full Profile (JSON)" saved), the saved JSON is corrupt, or
            another Notion API failure.
    """
    api_key, _ = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.retrieve(page_id=pagina_id)
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return _perfil_desde_propiedades(pagina["properties"])


def _perfil_desde_propiedades(propiedades: dict) -> dict:
    """Shared by obtener_perfil_completo() and buscar_cliente_por_email()
    -- both need to reassemble and parse the same "Full Profile (JSON)"
    property, just starting from a page fetched two different ways
    (retrieve vs. query). Pure function, no I/O.

    Also merges in "Liked Meals (JSON)"/"Liked Exercises (JSON)"
    (client-portal-written, see agregar_comida_favorita()/
    agregar_ejercicio_favorito()) as perfil["nutricion"]
    ["comidas_favoritas"]/perfil["experiencia"]["ejercicios_favoritos"]
    -- so a client's likes automatically flow into the trainer's "Revise
    client" load and, from there, into the next generar_plan_semanal()/
    generar_borrador_rutina_reglas() call, with no extra wiring needed
    anywhere else. Best-effort: missing or corrupt liked data never
    blocks loading the rest of a real, valid profile over it."""
    texto = _unir_bloques_notion(propiedades.get("Full Profile (JSON)", {}))
    if not texto:
        raise NotionClientError(
            "This record has no saved profile to revise (it predates the 'Full Profile (JSON)' property)."
        )
    try:
        perfil = json.loads(texto)
    except ValueError as exc:
        raise NotionClientError(f"Could not parse the saved profile: {exc}") from exc

    texto_favoritos = _unir_bloques_notion(propiedades.get("Liked Meals (JSON)", {}))
    if texto_favoritos:
        try:
            perfil.setdefault("nutricion", {})["comidas_favoritas"] = json.loads(texto_favoritos)
        except ValueError:
            pass

    texto_ejercicios_favoritos = _unir_bloques_notion(propiedades.get("Liked Exercises (JSON)", {}))
    if texto_ejercicios_favoritos:
        try:
            perfil.setdefault("experiencia", {})["ejercicios_favoritos"] = json.loads(texto_ejercicios_favoritos)
        except ValueError:
            pass

    return perfil


def buscar_cliente_por_email(email: str) -> dict | None:
    """
    Finds a client's most recent Clients record by email -- ui/app.py's
    "Revise client" section uses this to locate a record to load and
    (later, on re-approval) update, since the trainer only has the
    client's email handy, not a Notion page ID.

    Args:
        email: the client's email (the "Email" property, same join key
            historial_checkins()/crear_registro_checkin() already use).

    Returns:
        {"id": the page's Notion ID, "perfil": the full perfil_cliente
        dict} for the most recently admitted matching record, or None if
        no record has this email.

    Raises:
        NotionClientError: missing credentials, a matching record was
            found but has no saved profile (see
            _perfil_desde_propiedades()), or another Notion API failure.
    """
    api_key, database_id = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        resultado = cliente.data_sources.query(
            data_source_id=_id_fuente_datos(cliente, database_id),
            filter={"property": "Email", "email": {"equals": email}},
            sorts=[{"property": "Date", "direction": "descending"}],
            page_size=1,
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    if not resultado["results"]:
        return None

    pagina = resultado["results"][0]
    return {"id": pagina["id"], "perfil": _perfil_desde_propiedades(pagina["properties"])}


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
    peso_kg: float | None = None,
) -> dict:
    """Builds the Notion page "properties" payload for a Check-ins row.
    Pure function: no I/O, safe to unit test without any credentials —
    same split as _construir_propiedades_pagina() for the Clients
    database.

    peso_kg: optional -- only the client portal's check-in form
    (ui/app.py) ever sets this, when the client chose to share it; see
    this module's docstring on why "Weight (kg)" exists at all."""
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
    if peso_kg is not None:
        propiedades["Weight (kg)"] = {"number": peso_kg}
    return propiedades


def crear_registro_checkin(
    email: str,
    nombre_cliente: str,
    tipo: str,
    fecha: str,
    notas: str = "",
    valoracion: str | None = None,
    id_mensaje: str | None = None,
    peso_kg: float | None = None,
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
        peso_kg: optional current weight in kg — only the portal's
            check-in form sets this, when the client chose to share it.

    Returns:
        {"id": the page's Notion ID, "url": a notion.so link to it}.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure
            (e.g. the Check-ins database wasn't shared with the integration).
    """
    api_key, _ = _credenciales()
    database_id = _checkins_database_id()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    propiedades = _construir_propiedades_checkin(
        email, nombre_cliente, tipo, fecha, notas, valoracion, id_mensaje, peso_kg,
    )

    try:
        cliente = Client(auth=api_key)
        pagina = cliente.pages.create(parent={"database_id": database_id}, properties=propiedades)
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return {"id": pagina["id"], "url": pagina["url"]}


def _id_fuente_datos(cliente, database_id: str) -> str:
    """Resolves (and caches, see _CACHE_FUENTE_DATOS) the data_source_id a
    database_id maps to -- databases.query() was removed from the SDK once
    Notion's 2025-09-03 API moved querying to the per-data-source endpoint
    (multi-source databases); database_id is still accepted as a page
    *parent* for backward compatibility (see crear_registro_checkin()), but
    querying needs the actual data_source_id. Checked against a real
    workspace, not assumed from changelog text -- databases.query()
    genuinely raises AttributeError on notion-client>=3. Shared by
    existe_checkin_para_mensaje() and historial_checkins() so the fix
    (and the cache) only lives in one place."""
    if database_id not in _CACHE_FUENTE_DATOS:
        base_datos = cliente.databases.retrieve(database_id=database_id)
        _CACHE_FUENTE_DATOS[database_id] = base_datos["data_sources"][0]["id"]
    return _CACHE_FUENTE_DATOS[database_id]


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

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        resultado = cliente.data_sources.query(
            data_source_id=_id_fuente_datos(cliente, database_id),
            filter={"property": "Source message ID", "rich_text": {"equals": id_mensaje}},
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return len(resultado["results"]) > 0


def existe_cliente_para_mensaje(id_mensaje: str) -> bool:
    """
    Checks whether a Clients row already exists for a given Gmail message
    ID — main.py's automated intake trigger calls this before running the
    pipeline and creating a new record, so a scheduled run that re-scans
    the whole inbox doesn't process the same intake submission twice.
    Same dedup pattern as existe_checkin_para_mensaje(), against the
    Clients database instead of Check-ins.

    Args:
        id_mensaje: the Gmail message ID (see
            mcp.gmail_client.buscar_intakes_nuevos()).

    Returns:
        True if a row with this Source message ID already exists.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, database_id = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        resultado = cliente.data_sources.query(
            data_source_id=_id_fuente_datos(cliente, database_id),
            filter={"property": "Source message ID", "rich_text": {"equals": id_mensaje}},
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return len(resultado["results"]) > 0


def _fila_checkin_desde_pagina(pagina: dict) -> dict:
    """Extracts the fields ui/app.py's adherence history view needs from a
    raw Check-ins page object. Pure function: no I/O, safe to unit test
    with a hand-built page dict instead of a real API response."""
    propiedades = pagina["properties"]
    fecha = (propiedades.get("Date", {}).get("date") or {}).get("start")
    tipo = (propiedades.get("Type", {}).get("select") or {}).get("name")
    valoracion = (propiedades.get("Adherence rating", {}).get("select") or {}).get("name")
    notas = "".join(t["plain_text"] for t in propiedades.get("Adherence notes", {}).get("rich_text", []))
    peso_kg = (propiedades.get("Weight (kg)") or {}).get("number")
    return {"fecha": fecha, "tipo": tipo, "valoracion": valoracion, "notas": notas, "peso_kg": peso_kg}


def historial_checkins(email: str) -> list[dict]:
    """
    Returns every Check-ins row for a client, most recent first — lets
    ui/app.py show adherence history directly in the trainer's panel
    instead of that data only ever being visible inside Notion itself.

    Args:
        email: the client's email — same join key crear_registro_checkin()
            uses (a plain property match, not a Notion relation — see this
            module's docstring for why).

    Returns:
        A list of {"fecha", "tipo", "valoracion", "notas", "peso_kg"}
        dicts, most recent first (peso_kg is None on any row where the
        client didn't share it — only some portal check-ins ever set it).
        Empty list if the client has no check-ins yet (not an error — a
        brand-new client legitimately has none).

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, _ = _credenciales()
    database_id = _checkins_database_id()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        resultado = cliente.data_sources.query(
            data_source_id=_id_fuente_datos(cliente, database_id),
            filter={"property": "Email", "email": {"equals": email}},
            sorts=[{"property": "Date", "direction": "descending"}],
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return [_fila_checkin_desde_pagina(pagina) for pagina in resultado["results"]]


def _fila_cliente_lista_desde_pagina(pagina: dict) -> dict:
    """Extracts the fields ui/app.py's "Clients" overview needs from a raw
    Clients page object -- a superset of _fila_registro_cliente_desde_pagina()
    (which stays as-is, scoped to only what the client portal needs) since
    this is trainer-only and the overview table has room for more columns.
    Pure function, no I/O."""
    propiedades = pagina["properties"]
    nombre = "".join(t["plain_text"] for t in propiedades.get("Name", {}).get("title", []))
    email = propiedades.get("Email", {}).get("email")
    fecha = (propiedades.get("Date", {}).get("date") or {}).get("start")
    objetivo = (propiedades.get("Goal", {}).get("select") or {}).get("name")
    nivel = (propiedades.get("Level", {}).get("select") or {}).get("name")
    veredicto = (propiedades.get("Verdict", {}).get("select") or {}).get("name")
    email_enviado = propiedades.get("Email Sent", {}).get("checkbox", False)
    return {
        "id": pagina["id"],
        "nombre": nombre,
        "email": email,
        "fecha": fecha,
        "objetivo": objetivo,
        "nivel": nivel,
        "veredicto": veredicto,
        "email_enviado": email_enviado,
    }


def listar_clientes(limite: int = 100) -> list[dict]:
    """
    Returns every Clients record, most recently admitted first -- feeds
    ui/app.py's "Clients" overview, the first place in this project a
    trainer can see every client at a glance instead of looking each one
    up individually by email (see _cargar_ficha_para_revisar()/
    historial_checkins(), both one-client-at-a-time by design).

    Args:
        limite: max rows returned. Notion's own per-request page_size cap
            is 100; this project has never needed pagination past that
            for a portfolio-scale client list, so a second "load more"
            request was left out rather than built for a case that
            doesn't come up yet.

    Returns:
        A list of {"id", "nombre", "email", "fecha", "objetivo", "nivel",
        "veredicto", "email_enviado"} dicts.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, database_id = _credenciales()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        resultado = cliente.data_sources.query(
            data_source_id=_id_fuente_datos(cliente, database_id),
            sorts=[{"property": "Date", "direction": "descending"}],
            page_size=limite,
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    return [_fila_cliente_lista_desde_pagina(pagina) for pagina in resultado["results"]]


def ultimo_checkin_por_cliente(limite: int = 100) -> dict[str, dict]:
    """
    Returns each client's single most recent Check-ins row, keyed by
    email -- lets ui/app.py's "Clients" overview show an at-a-glance
    adherence signal per client (who needs attention right now) without
    one query per client. A single query against the whole Check-ins
    database, sorted newest first, grouped by email in Python -- Notion's
    API has no native "latest row per group" query, and this project's
    scale doesn't justify anything fancier.

    Args:
        limite: max Check-ins rows scanned (see listar_clientes()'s
            docstring on why 100 is the practical ceiling here -- a
            client with many check-ins further back than the scanned
            window just doesn't show up in this particular view; their
            full history is still there via historial_checkins()).

    Returns:
        {email: {"fecha", "tipo", "valoracion", "notas", "peso_kg"}} for
        whichever clients have at least one Check-ins row within the
        scanned window. A client with no check-ins at all simply has no
        key -- not an error, a brand-new client legitimately has none.

    Raises:
        NotionClientError: missing credentials, or a Notion API failure.
    """
    api_key, _ = _credenciales()
    database_id = _checkins_database_id()

    from httpx import HTTPError
    from notion_client import Client
    from notion_client.errors import APIResponseError

    try:
        cliente = Client(auth=api_key)
        resultado = cliente.data_sources.query(
            data_source_id=_id_fuente_datos(cliente, database_id),
            sorts=[{"property": "Date", "direction": "descending"}],
            page_size=limite,
        )
    except (APIResponseError, HTTPError) as exc:
        raise NotionClientError(f"Notion API error: {exc}") from exc

    ultimos: dict[str, dict] = {}
    for pagina in resultado["results"]:
        email = (pagina["properties"].get("Email") or {}).get("email")
        if not email or email in ultimos:
            continue  # a less recent row for this client -- results are newest-first, so skip it
        ultimos[email] = _fila_checkin_desde_pagina(pagina)
    return ultimos
