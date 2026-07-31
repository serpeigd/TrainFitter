"""
Gmail connector: turns an approved plan into a Gmail **draft** — never a
sent email. This is the real-world version of the UI's "simulated approval"
step, and it's built to preserve the exact same safety principle as the rest
of the pipeline: TrainFitter never contacts a client on its own.

DESIGN — draft-only, by construction, not just by convention: the OAuth
scope requested (`gmail.compose`) physically cannot send or read mail —
Google's own API rejects a send call under this scope. This isn't a
"we chose not to call send()" promise, it's "the authorized account
couldn't send even if the code tried to." That matters specifically because
this app has a public demo (trainfitter.streamlit.app): anyone could type
any email address into the client-email field, so the one thing that must
never happen is an email actually leaving the dedicated Gmail account
without the trainer reviewing it first in their own Gmail draft folder.

DESIGN — `gmail.readonly` replaced the narrower `gmail.metadata`: this
project's inbox trigger (see main.py) needs to actually read a client's
reply — the checklist attachment they send back with what they really
did — not just its labels/headers. `gmail.metadata` (the scope this used
to request, back when the only read need was "was this thread sent?")
can't see message bodies or attachments at all, so it had to go.
`gmail.readonly` is a real jump: a compromised token could read anything
in that mailbox, not just TrainFitter's own threads — Gmail's API has no
finer-grained scope for "read only these specific threads." Accepted
deliberately, on a dedicated account (trainfitter.official@gmail.com) used
for nothing else. Adding/widening a scope means any existing token.json
(authorized under the old scope list only) stops being sufficient — Google
enforces scope at the API call, not just locally — so re-running the OAuth
consent flow (deleting token.json first) is required once, both locally
and on any deployment.

DESIGN — pure logic separated from network/auth: _construir_mensaje_raw()
and _construir_cuerpo_email() are plain functions with no I/O, fully unit
tested without any credentials. Only crear_borrador() and verificar_envio()
touch the network, and only when actually called — the
google-api-python-client / google-auth-oauthlib packages are lazy imports,
same convention as `anthropic` for motor="llm" and `pdfplumber` for the
bloodwork parser: the free pipeline never needs them installed.

DESIGN — verificar_envio() is trainer-triggered, not a background job: this
is a stateless Streamlit app with no persistent backend or push
infrastructure, so "detecting" a send means checking on demand (a button in
ui/app.py) whether the draft's thread now contains a message with the SENT
label — not passively noticing the moment it happens.

DESIGN — the adherence checklist rides along as a plain-text attachment,
not a second email: crear_borrador() now always attaches a small
`.txt` checklist (built by _construir_checklist_adherencia(), pure logic,
no I/O) listing each routine day as a `[ ]` checkbox plus a couple of
free-answer prompts for the diet — something the client can mark up and
send straight back in their reply, rather than needing to describe
adherence in prose from scratch.

DESIGN — dedup via Notion, not a Gmail label: buscar_respuestas_adherencia()
finds candidate replies by search query alone (inbox, has an attachment,
subject matches a plan email) and returns all of them, every run — it
doesn't mark anything as "read" or apply a label in Gmail. main.py is the
one that skips messages it's already turned into a Check-ins row (by
message ID, via notion_connector.existe_checkin_para_mensaje()). Avoids
needing gmail.modify (a scope this project doesn't otherwise need) just to
track which replies were already processed.

Setup (one-time, free, done by the project owner — never by this code):
  1. Create a Google Cloud project and enable the Gmail API.
  2. Create an OAuth 2.0 Client ID (type: Desktop app) and download it as
     credentials.json into the repo root (gitignored — never committed).
  3. In the OAuth consent screen's "Data Access" section, add both scopes
     below (gmail.compose and gmail.readonly) to the app's registered scope
     list — Google rejects a token request for a scope the app doesn't have
     registered, even in testing mode.
  4. First call to crear_borrador(), verificar_envio(), or
     buscar_respuestas_adherencia() opens a browser consent screen; the
     resulting token is cached to token.json (also gitignored) so it isn't
     repeated on every run. If token.json already exists from before
     gmail.readonly was added, delete it first so the consent screen
     re-runs and grants the new scope.
"""

import base64
import re
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUTA_CREDENCIALES = REPO_ROOT / "credentials.json"
RUTA_TOKEN = REPO_ROOT / "token.json"

# gmail.compose: create drafts, physically can't send (see module
# docstring). gmail.readonly: read the inbox to find a client's adherence
# reply and its attachment — the narrowest scope Gmail offers that can
# actually see a message body/attachment, not just labels/headers.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]

# Shared between crear_borrador() (builds the subject) and
# buscar_respuestas_adherencia() (searches for replies to it) so the two
# can never drift apart -- a subject typo in only one of them would
# silently break reply detection.
ASUNTO_PLAN_EN = "Your plan from TrainFitter"
ASUNTO_PLAN_ES = "Tu plan de TrainFitter"


class GmailClientError(Exception):
    """Raised for anything that stops a draft from being created — missing
    credentials, an invalid recipient, or an API-side failure. The UI is
    expected to catch this and show a clear message instead of crashing."""


def _validar_destinatario(destinatario: str) -> str:
    destinatario = destinatario.strip()
    if not destinatario or "@" not in destinatario or destinatario.startswith("@") or destinatario.endswith("@"):
        raise GmailClientError(f"'{destinatario}' doesn't look like a valid email address.")
    return destinatario


def _construir_cuerpo_email(nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict, idioma: str = "en") -> str:
    """Plain-text email body summarizing the approved plan. Pure formatting —
    no network, no auth, trivially unit-testable.

    idioma only affects this template's own wrapper text (greeting, section
    dividers, footer note) — borrador_rutina/borrador_dieta's own narrative
    fields (mensaje_para_el_cliente, resumen_enfoque) were already generated
    in whichever language the trainer had selected when the plan was
    created (see rutina_reglas.py/dieta_reglas.py), so this just needs to
    match that, not translate anything itself."""
    if idioma == "es":
        return (
            f"Hola {nombre_cliente},\n\n"
            f"{borrador_rutina['mensaje_para_el_cliente']}\n\n"
            f"--- Rutina ---\n"
            f"{borrador_rutina['resumen_enfoque']}\n\n"
            f"{borrador_dieta['mensaje_para_el_cliente']}\n\n"
            f"--- Dieta ---\n"
            f"{borrador_dieta['resumen_enfoque']}\n"
            f"Objetivo: {borrador_dieta['calorias_objetivo_kcal']} kcal/día, "
            f"{borrador_dieta['macros']['proteina_g']} g de proteína.\n\n"
            f"Dentro de unas semanas, márcame en el archivo adjunto lo que "
            f"realmente hayas hecho y respóndeme este email con él — así "
            f"ajustamos lo que haga falta.\n\n"
            f"(Este es un borrador preparado por TrainFitter — revisado y enviado por tu entrenador/a, nunca de forma automática.)"
        )

    return (
        f"Hi {nombre_cliente},\n\n"
        f"{borrador_rutina['mensaje_para_el_cliente']}\n\n"
        f"--- Routine ---\n"
        f"{borrador_rutina['resumen_enfoque']}\n\n"
        f"{borrador_dieta['mensaje_para_el_cliente']}\n\n"
        f"--- Diet ---\n"
        f"{borrador_dieta['resumen_enfoque']}\n"
        f"Target: {borrador_dieta['calorias_objetivo_kcal']} kcal/day, "
        f"{borrador_dieta['macros']['proteina_g']} g protein.\n\n"
        f"In a few weeks, mark up the attached file with what you actually "
        f"did and reply to this email with it — that's how we'll adjust "
        f"anything that needs it.\n\n"
        f"(This is a draft prepared by TrainFitter — reviewed and sent by your trainer, never automatically.)"
    )


# Fixed at a week regardless of the routine's own training frequency
# (3, 4, 5 days/week...) -- diet adherence is tracked daily, not just on
# training days, so it needs its own constant rather than reusing
# len(sesiones).
DIAS_SEMANA_DIETA = 7


def _construir_checklist_adherencia(nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict, idioma: str = "en") -> str:
    """Plain-text adherence checklist attached to the plan email (see
    crear_borrador()) -- something the client can mark up with what they
    actually did and send straight back, instead of describing adherence
    in prose from scratch. Pure formatting, no I/O.

    The three bracket tags ([ROUTINE NOTES BELOW], [DIET DAYS FOLLOWED,
    out of N], [DIET NOTES BELOW]) are deliberately identical regardless of
    idioma: agents/adherencia_parser.py anchors on them verbatim to find
    the client's free-text answers, so translating them would silently
    break parsing -- only the human sentence explaining each one is
    translated, same principle as exercise/food names staying canonical
    English for validator_agent.py's safety cross-check (see
    docs/decisiones.md)."""
    casillas_dias = "\n".join(f"[ ] {sesion['dia']}" for sesion in borrador_rutina["sesiones"])

    if idioma == "es":
        return (
            f"TrainFitter — Seguimiento de {nombre_cliente}\n\n"
            f"Responde a este email con este mismo archivo editado, marcando lo que "
            f"realmente hiciste. Nada de esto se califica: cuanto más honesto sea, "
            f"mejor podremos ajustar tu próximo plan.\n\n"
            f"== RUTINA ==\n"
            f"Marca con una [x] cada día que completaste. Déjalo como [ ] si te lo saltaste.\n\n"
            f"{casillas_dias}\n\n"
            f"¿Algo sobre la rutina que debamos saber (dolor, ejercicios que cambiaste, "
            f"series/repeticiones que no cuadraron, días que moviste)?\n"
            f"[ROUTINE NOTES BELOW]\n>\n\n"
            f"== DIETA ==\n"
            f"Objetivo: {borrador_dieta['calorias_objetivo_kcal']} kcal/día, "
            f"{borrador_dieta['macros']['proteina_g']} g de proteína.\n"
            f"De los últimos {DIAS_SEMANA_DIETA} días, ¿cuántos dirías que seguiste el plan?\n"
            f"[DIET DAYS FOLLOWED, out of {DIAS_SEMANA_DIETA}]\n>\n\n"
            f"¿Algo sobre la dieta que debamos saber (antojos, días fuera del plan, "
            f"comidas que no te funcionaron)?\n"
            f"[DIET NOTES BELOW]\n>\n"
        )

    return (
        f"TrainFitter — Adherence check-in for {nombre_cliente}\n\n"
        f"Reply to this email with this same file edited, marking what you actually "
        f"did. Nothing here is graded: the more honest it is, the better your next "
        f"plan can be adjusted.\n\n"
        f"== ROUTINE ==\n"
        f"Mark each day you completed with an [x]. Leave it as [ ] if you skipped it.\n\n"
        f"{casillas_dias}\n\n"
        f"Anything about the routine we should know (pain, exercises you swapped, "
        f"sets/reps that felt off, days you moved around)?\n"
        f"[ROUTINE NOTES BELOW]\n>\n\n"
        f"== DIET ==\n"
        f"Target: {borrador_dieta['calorias_objetivo_kcal']} kcal/day, "
        f"{borrador_dieta['macros']['proteina_g']} g protein.\n"
        f"Out of the last {DIAS_SEMANA_DIETA} days, how many would you say you followed the plan?\n"
        f"[DIET DAYS FOLLOWED, out of {DIAS_SEMANA_DIETA}]\n>\n\n"
        f"Anything about the diet we should know (cravings, days off-plan, foods "
        f"that didn't work for you)?\n"
        f"[DIET NOTES BELOW]\n>\n"
    )


def _construir_mensaje_raw(
    destinatario: str,
    asunto: str,
    cuerpo_texto: str,
    nombre_adjunto: str | None = None,
    contenido_adjunto: str | None = None,
) -> dict:
    """Builds the base64url-encoded RFC 2822 message the Gmail API expects.
    Pure function: no I/O, safe to unit test without any credentials.

    nombre_adjunto/contenido_adjunto are both optional and both-or-neither:
    when given, the message becomes a multipart email with a plain-text
    attachment (the adherence checklist -- see crear_borrador()) instead of
    a bare MIMEText, otherwise unchanged from before that feature existed."""
    destinatario = _validar_destinatario(destinatario)

    if nombre_adjunto and contenido_adjunto is not None:
        mensaje = MIMEMultipart()
        mensaje.attach(MIMEText(cuerpo_texto))
        adjunto = MIMEText(contenido_adjunto)
        adjunto.add_header("Content-Disposition", "attachment", filename=nombre_adjunto)
        mensaje.attach(adjunto)
    else:
        mensaje = MIMEText(cuerpo_texto)

    mensaje["to"] = destinatario
    mensaje["subject"] = asunto
    raw = base64.urlsafe_b64encode(mensaje.as_bytes()).decode("utf-8")
    return {"message": {"raw": raw}}


def _obtener_credenciales():
    """Lazy-imports the Google client libraries and runs (or reuses) the
    OAuth flow. Only called from the network-touching functions below
    (crear_borrador(), verificar_envio(), buscar_respuestas_adherencia()),
    never at module import time — see the module docstring.

    Checks for *some* usable setup (either file) before importing anything:
    on a deployment with neither file present (e.g. the public demo without
    Gmail configured) and google-auth-oauthlib not installed either, this
    raises the clear "missing credentials.json" message instead of a bare
    ModuleNotFoundError — same fix applied to notion_connector.py after CI
    caught the equivalent bug there (a lazy import running before the
    credentials check it should have deferred to)."""
    if not RUTA_TOKEN.exists() and not RUTA_CREDENCIALES.exists():
        raise GmailClientError(
            f"Missing {RUTA_CREDENCIALES.name}. Create an OAuth Desktop-app "
            "credential in Google Cloud Console and save it at the repo root "
            "(see mcp/gmail_client.py's module docstring for the full steps)."
        )

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credenciales = None
    if RUTA_TOKEN.exists():
        credenciales = Credentials.from_authorized_user_file(str(RUTA_TOKEN), SCOPES)

    if not credenciales or not credenciales.valid:
        if credenciales and credenciales.expired and credenciales.refresh_token:
            credenciales.refresh(Request())
        else:
            if not RUTA_CREDENCIALES.exists():
                raise GmailClientError(
                    f"Missing {RUTA_CREDENCIALES.name}. Create an OAuth Desktop-app "
                    "credential in Google Cloud Console and save it at the repo root "
                    "(see mcp/gmail_client.py's module docstring for the full steps)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(RUTA_CREDENCIALES), SCOPES)
            credenciales = flow.run_local_server(port=0)
        RUTA_TOKEN.write_text(credenciales.to_json(), encoding="utf-8")

    return credenciales


def crear_borrador(
    destinatario: str, nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict, idioma: str = "en",
) -> dict:
    """
    Creates a Gmail draft (never sends it) with the approved plan, with a
    plain-text adherence checklist attached (see
    _construir_checklist_adherencia()) for the client to mark up and send
    back once they've actually started the plan.

    Args:
        destinatario, nombre_cliente, borrador_rutina, borrador_dieta: same as before.
        idioma: "en" (default) or "es" — language of this email's own
            wrapper text (subject, greeting, section dividers); see
            _construir_cuerpo_email()'s docstring.

    Returns:
        {"url": a gmail.com link to the created draft, "thread_id": the
        underlying thread's ID}. thread_id is what verificar_envio() needs
        later — Gmail keeps a sent message in the same thread as the draft
        it came from, which is how a real send gets detected.

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials
            the user needs to re-authorize, or a Gmail API failure.
    """
    asunto = f"{ASUNTO_PLAN_ES} — {nombre_cliente}" if idioma == "es" else f"{ASUNTO_PLAN_EN} — {nombre_cliente}"
    cuerpo = _construir_mensaje_raw(
        destinatario,
        asunto=asunto,
        cuerpo_texto=_construir_cuerpo_email(nombre_cliente, borrador_rutina, borrador_dieta, idioma),
        nombre_adjunto="adherencia.txt" if idioma == "es" else "adherence-checklist.txt",
        contenido_adjunto=_construir_checklist_adherencia(nombre_cliente, borrador_rutina, borrador_dieta, idioma),
    )

    # Resolved before importing googleapiclient: _obtener_credenciales()
    # checks whether Gmail is set up at all first (see its docstring), so a
    # deployment with neither file nor any Google package installed raises
    # the clear "missing credentials.json" message rather than whichever
    # import happens to fail first.
    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        borrador = servicio.users().drafts().create(userId="me", body=cuerpo).execute()
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc

    return {
        "url": f"https://mail.google.com/mail/u/0/#drafts/{borrador['message']['id']}",
        "thread_id": borrador["message"]["threadId"],
    }


def verificar_envio(id_hilo: str) -> bool:
    """
    Checks whether the draft's thread now contains a message with the SENT
    label — i.e. whether the trainer actually opened the draft in Gmail and
    hit send, not just created it. Uses format="metadata" explicitly: this
    only ever needs labels and headers, never the message body, even though
    the scope now granted (gmail.readonly) could read more (see module
    docstring for why the scope grew regardless).

    Args:
        id_hilo: the thread_id returned by crear_borrador().

    Returns:
        True if a sent message exists in this thread, False if it's still
        just a draft (or the thread was deleted).

    Raises:
        GmailClientError: missing/expired credentials the user needs to
            re-authorize, or a Gmail API failure other than "not found".
    """
    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        hilo = servicio.users().threads().get(userId="me", id=id_hilo, format="metadata").execute()
    except HttpError as exc:
        if exc.resp.status == 404:
            return False
        raise GmailClientError(f"Gmail API error: {exc}") from exc

    return any("SENT" in mensaje.get("labelIds", []) for mensaje in hilo.get("messages", []))


def _extraer_remitente(cabeceras: list[dict]) -> str:
    """Pulls a bare email address out of a raw "From" header, which is
    usually "Display Name <address@example.com>" but sometimes just the
    bare address. Pure function, no I/O."""
    valor = next((c["value"] for c in cabeceras if c["name"].lower() == "from"), "")
    coincidencia = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", valor)
    return coincidencia.group(0) if coincidencia else valor.strip()


def _extraer_adjunto_texto(servicio, id_mensaje: str, parte: dict) -> str | None:
    """Walks a message's MIME part tree (it's recursive: a multipart part
    contains further "parts") looking for the first plain-text attachment,
    and returns its decoded content. Small attachment data sometimes comes
    back inline on the part itself (body.data); anything larger comes back
    as just a body.attachmentId that needs a second API call to fetch —
    both are handled here so callers don't need to know which case
    applies."""
    if parte.get("filename") and parte.get("mimeType", "").startswith("text/"):
        cuerpo = parte.get("body", {})
        if cuerpo.get("data"):
            return base64.urlsafe_b64decode(cuerpo["data"]).decode("utf-8", errors="replace")
        if cuerpo.get("attachmentId"):
            adjunto = (
                servicio.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=id_mensaje, id=cuerpo["attachmentId"])
                .execute()
            )
            return base64.urlsafe_b64decode(adjunto["data"]).decode("utf-8", errors="replace")

    for subparte in parte.get("parts", []):
        contenido = _extraer_adjunto_texto(servicio, id_mensaje, subparte)
        if contenido is not None:
            return contenido
    return None


def buscar_respuestas_adherencia() -> list[dict]:
    """
    Searches the inbox for client replies to a plan email that carry an
    attachment — candidate adherence checklists. Returns every match found
    on every call; it doesn't mark anything as read or apply a label (see
    module docstring for why: dedup against already-processed replies is
    main.py's job, via Notion, not this function's).

    Returns:
        A list of {"id_mensaje", "id_hilo", "remitente", "fecha"
        (YYYY-MM-DD), "contenido"} dicts, one per matching message with a
        readable text attachment. Messages that matched the search but had
        no plain-text attachment (e.g. the client attached a photo instead)
        are silently skipped — there's nothing parseable in them.

    Raises:
        GmailClientError: missing/expired credentials the user needs to
            re-authorize, or a Gmail API failure.
    """
    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    consulta = f'in:inbox has:attachment (subject:"{ASUNTO_PLAN_EN}" OR subject:"{ASUNTO_PLAN_ES}")'

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        resultado = servicio.users().messages().list(userId="me", q=consulta).execute()

        respuestas = []
        for referencia in resultado.get("messages", []):
            mensaje = (
                servicio.users().messages().get(userId="me", id=referencia["id"], format="full").execute()
            )
            contenido = _extraer_adjunto_texto(servicio, referencia["id"], mensaje["payload"])
            if contenido is None:
                continue

            fecha = datetime.fromtimestamp(int(mensaje["internalDate"]) / 1000, tz=timezone.utc).date().isoformat()
            respuestas.append(
                {
                    "id_mensaje": mensaje["id"],
                    "id_hilo": mensaje["threadId"],
                    "remitente": _extraer_remitente(mensaje["payload"]["headers"]),
                    "fecha": fecha,
                    "contenido": contenido,
                }
            )
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc

    return respuestas
