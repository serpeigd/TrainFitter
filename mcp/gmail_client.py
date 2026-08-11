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

DESIGN — gmail.send is a deliberate, narrow exception to "never sends
automatically", scoped to exactly three functions, each one either
trainer-triggered with fixed, non-improvised content, or aimed at the
trainer's own inbox rather than a client's — never a client receiving
unsolicited, trainer-unreviewed content: enviar_enlace_portal() sends a
real message (via messages().send(), not drafts().create()) containing
nothing but a signed magic link (see agents/portal_tokens.py) to the
client portal — never plan content, never anything the trainer hasn't
already approved. This is a real, considered trade-off against the
draft-only principle above, made explicitly by the project owner (not a
default), because a magic link is only useful if it actually reaches the
client's inbox — a draft the trainer would have to open and manually
forward defeats the point of a self-serve portal. The blast radius is
kept as small as this scope allows: reachable only from one explicit
button in ui/app.py's approval panel (gated the same way draft creation
already is — behind an approved plan, and behind APP_APPROVAL_PASSWORD on
the public demo), sending a fixed, code-defined template with exactly one
variable slot (the link itself) — never free text a trainer or client
could inject content into.

DESIGN — enviar_notificacion_checkin() is the second function allowed to
call messages().send(): unlike enviar_enlace_portal(), this one is
genuinely automatic (fired the moment a client submits the portal's own
check-in form, no button click at all) — but it mails the *trainer's own*
inbox (TRAINER_NOTIFICATION_EMAIL, see ui/app.py), never a client, so it
can't violate "TrainFitter never contacts a client on its own" no matter
how it fires. Best-effort by design: a failure here (missing config,
expired credentials, an API error) must never block the actual check-in
from being saved to Notion — ui/app.py swallows exceptions from this call
the same way it already does for actualizar_email_cliente()/
marcar_email_enviado(), since a trainer notification email is a
convenience layered on top of the real record, not the record itself.

DESIGN — enviar_formulario_intake() is the third (and, as of now, last)
function allowed to call messages().send(): requested directly, to let a
trainer email a prospective client the blank intake form (see
agents/pdf_intake.py) straight from the panel instead of attaching it by
hand from their own mail client. The narrowest of the three by content:
its template has NO variable slots at all, not even the prospect's name
(nothing about them is known yet at this point in the funnel) — the only
thing that ever varies between calls is which of two fixed, code-defined
PDF/text pairs (EN/ES) gets attached. Same gating as
enviar_enlace_portal(): one explicit button, behind APP_APPROVAL_PASSWORD
on deployments where it's set (this is the one action in the "New Client"
tab that touches a real inbox before any client data exists yet, so it
needs the same protection the rest of that tab's write actions already
have).

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

DESIGN — two PDFs attached, not the plan text inlined in the email body:
crear_borrador() now sends a short note (see _construir_cuerpo_email())
plus two files generated by agents/pdf_generador.py — a plain diet PDF and
a fillable checklist PDF. Replaced an earlier design where the full plan
was inlined in the email body and the checklist was a plain-text
attachment; see docs/decisiones.md for why (a .txt file gives the client
no signal that it's meant to be filled in and returned, and a fillable PDF
form is natively editable in essentially any PDF viewer without needing a
specific app). The body's own instructions are deliberately explicit about
re-attaching the checklist to the reply: mail clients don't carry
attachments over automatically when you hit "Reply" (only "Forward"
does, and inconsistently even then), so a client who doesn't realize that
would send back an empty-handed reply main.py has nothing to parse.

DESIGN — dedup via Notion, not a Gmail label: buscar_respuestas_adherencia()
finds candidate replies by search query alone (has an attachment, subject
matches a plan email, actually a reply — see that function for how) and
returns all of them, every run — it doesn't mark anything as "read" or
apply a label in Gmail. main.py is the one that skips messages it's
already turned into a Check-ins row (by message ID, via
notion_connector.existe_checkin_para_mensaje()). Avoids needing
gmail.modify (a scope this project doesn't otherwise need) just to track
which replies were already processed. buscar_intakes_nuevos() (a filled-in
*intake* PDF a prospective client emailed back, not a checklist reply) uses
the exact same dedup approach, against Notion's Clients database instead
(notion_connector.existe_cliente_para_mensaje()) — see agents/pdf_intake.py
for why the intake itself is a fillable form rather than free text.

DESIGN — buscar_intakes_nuevos() couldn't be fully verified against a real
inbox: injecting a synthetic incoming message to test it end-to-end needs
messages().insert(), which returns 403 Insufficient Permission under this
project's deliberately narrow gmail.compose scope (that scope creates
drafts, not arbitrary mailbox inserts — see the DESIGN note above on why
the scope isn't wider). Rather than widen the scope just to make one test
more realistic, this is covered by mocked-network tests
(tests/test_gmail_client_network.py) plus real-credentials coverage of the
structurally identical buscar_respuestas_adherencia() search/parse path —
a disclosed limitation, not a hidden gap; see docs/decisiones.md.

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
from email.mime.application import MIMEApplication
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
# gmail.send: the one deliberate exception to "never sends automatically"
# — enviar_enlace_portal() actually sends (see its own docstring for why,
# and the guardrails around when it's allowed to fire).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
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


def _quitar_saludo(mensaje: str, nombre_cliente: str, idioma: str) -> str:
    """rutina_reglas.py/dieta_reglas.py each bake their own "Hi {first_name}, "
    / "Hola {first_name}, " greeting directly into mensaje_para_el_cliente --
    by design, so the message reads naturally when shown standalone (the
    trainer's UI panel, the diet PDF -- see those modules' own docstrings).

    This email shows BOTH messages together under one shared greeting, so
    without this the client's own name would open three separate lines in a
    row. Strips a matching leading greeting back off; leaves the message
    untouched if the prefix doesn't match exactly (e.g. a hand-edited
    message), since silently mangling text is worse than an occasional
    harmless repeat."""
    primer_nombre = nombre_cliente.split()[0] if nombre_cliente.strip() else nombre_cliente
    saludo = f"Hola {primer_nombre}, " if idioma == "es" else f"Hi {primer_nombre}, "
    return mensaje[len(saludo):] if mensaje.startswith(saludo) else mensaje


def _construir_cuerpo_email(nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict, idioma: str = "en") -> str:
    """Brief plain-text email body -- the plan's own detail lives in the two
    attached PDFs now (see agents/pdf_generador.py), not inlined here. Pure
    formatting -- no network, no auth, trivially unit-testable.

    Keeps borrador_rutina/borrador_dieta's own mensaje_para_el_cliente (the
    trainer's personal, warm note, varied per client -- see
    agents/variacion.py) but drops resumen_enfoque/macros, which now live in
    the diet PDF instead of being duplicated in the email body. Each
    message's own baked-in greeting is stripped (see _quitar_saludo()) and
    replaced by one shared greeting up top, and the two are set under short
    section labels instead of run together as one wall of text -- a real
    fix, not cosmetic: the client's name used to open three lines in a row.

    idioma only affects this template's own wrapper text (greeting, section
    labels, attachment explanation) — mensaje_para_el_cliente was already
    generated in whichever language the trainer had selected when the plan
    was created (see rutina_reglas.py/dieta_reglas.py), so this just needs
    to match that, not translate anything itself."""
    mensaje_rutina = _quitar_saludo(borrador_rutina["mensaje_para_el_cliente"], nombre_cliente, idioma)
    mensaje_dieta = _quitar_saludo(borrador_dieta["mensaje_para_el_cliente"], nombre_cliente, idioma)

    if idioma == "es":
        return (
            f"Hola {nombre_cliente},\n\n"
            f"🏋️ Tu rutina\n{mensaje_rutina}\n\n"
            f"🍽️ Tu dieta\n{mensaje_dieta}\n\n"
            f"Adjunto van tu dieta en PDF y un formulario rellenable para ir "
            f"marcando tu rutina. Dentro de unas semanas, cuando ya hayas "
            f"empezado, rellénalo y RESPONDE A ESTE EMAIL con el formulario "
            f"adjunto de nuevo — al responder, el archivo no se adjunta "
            f"solo, así que tendrás que volver a adjuntarlo tú. Si el "
            f"visor de tu correo/Drive no te deja escribir en los campos, "
            f"descarga el PDF y ábrelo con Adobe Acrobat Reader (gratis) u "
            f"otra app de PDF."
        )

    return (
        f"Hi {nombre_cliente},\n\n"
        f"🏋️ Your routine\n{mensaje_rutina}\n\n"
        f"🍽️ Your diet\n{mensaje_dieta}\n\n"
        f"Attached are two files: your diet as a PDF, and a fillable form "
        f"to check off your routine. In a few weeks, once you've actually "
        f"started, fill it in and REPLY TO THIS EMAIL with the form "
        f"attached again — replying doesn't carry the attachment over "
        f"automatically, so you'll need to attach it yourself. If your "
        f"mail/Drive preview won't let you type into the fields, download "
        f"the PDF and open it in Adobe Acrobat Reader (free) or another "
        f"PDF app."
    )


def _construir_mensaje_raw(
    destinatario: str,
    asunto: str,
    cuerpo_texto: str,
    adjuntos: list[tuple[str, bytes]] | None = None,
) -> dict:
    """Builds the base64url-encoded RFC 2822 message the Gmail API expects.
    Pure function: no I/O, safe to unit test without any credentials.

    adjuntos: an optional list of (filename, raw_bytes) pairs -- the diet
    and checklist PDFs (see crear_borrador()). Every filename here is
    expected to end in ".pdf" (that's all this project ever attaches), so
    the MIME subtype is derived from the extension rather than taken as a
    separate parameter -- one less thing for a caller to get wrong."""
    destinatario = _validar_destinatario(destinatario)

    if adjuntos:
        mensaje = MIMEMultipart()
        mensaje.attach(MIMEText(cuerpo_texto))
        for nombre_archivo, contenido in adjuntos:
            subtipo = nombre_archivo.rsplit(".", 1)[-1] if "." in nombre_archivo else "octet-stream"
            parte = MIMEApplication(contenido, _subtype=subtipo)
            parte.add_header("Content-Disposition", "attachment", filename=nombre_archivo)
            mensaje.attach(parte)
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
    Creates a Gmail draft (never sends it) with the approved plan: a brief
    note (see _construir_cuerpo_email()) plus two PDFs generated by
    agents/pdf_generador.py -- the diet plan, and a fillable checklist for
    the client to mark up and send back once they've actually started.

    Args:
        destinatario, nombre_cliente, borrador_rutina, borrador_dieta: same as before.
        idioma: "en" (default) or "es" — language of this email's own
            wrapper text and the two PDFs' own labels; see
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
    # Lazy import, same convention as googleapiclient below: reportlab (the
    # actual heavy dependency, imported inside pdf_generador.py's own
    # functions) never needs to be installed for the default free pipeline.
    from pdf_generador import (
        NOMBRE_PDF_CHECKLIST_EN,
        NOMBRE_PDF_CHECKLIST_ES,
        NOMBRE_PDF_DIETA_EN,
        NOMBRE_PDF_DIETA_ES,
        generar_pdf_checklist,
        generar_pdf_dieta,
    )

    asunto = f"{ASUNTO_PLAN_ES} — {nombre_cliente}" if idioma == "es" else f"{ASUNTO_PLAN_EN} — {nombre_cliente}"
    nombre_pdf_dieta = NOMBRE_PDF_DIETA_ES if idioma == "es" else NOMBRE_PDF_DIETA_EN
    nombre_pdf_checklist = NOMBRE_PDF_CHECKLIST_ES if idioma == "es" else NOMBRE_PDF_CHECKLIST_EN
    cuerpo = _construir_mensaje_raw(
        destinatario,
        asunto=asunto,
        cuerpo_texto=_construir_cuerpo_email(nombre_cliente, borrador_rutina, borrador_dieta, idioma),
        adjuntos=[
            (nombre_pdf_dieta, generar_pdf_dieta(borrador_dieta, nombre_cliente, idioma)),
            (nombre_pdf_checklist, generar_pdf_checklist(borrador_rutina, borrador_dieta, nombre_cliente, idioma)),
        ],
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


ASUNTO_PORTAL_EN = "Your TrainFitter client portal link"
ASUNTO_PORTAL_ES = "Tu enlace al portal de TrainFitter"


def _construir_cuerpo_portal(nombre_cliente: str, url_portal: str, idioma: str = "en") -> str:
    """Fixed, code-defined template with exactly one variable slot (the
    link itself) -- see the module docstring's DESIGN note on gmail.send
    for why that matters specifically for this one function. Pure
    formatting, no I/O, trivially unit-testable."""
    if idioma == "es":
        return (
            f"Hola {nombre_cliente},\n\n"
            f"Aquí tienes tu enlace personal al portal de TrainFitter, donde "
            f"puedes ver un resumen de tu plan y registrar cómo te va:\n\n"
            f"{url_portal}\n\n"
            f"Este enlace es solo tuyo — no lo compartas. Caduca pasados unos "
            f"días; si deja de funcionar, pídele a tu entrenador/a uno nuevo."
        )
    return (
        f"Hi {nombre_cliente},\n\n"
        f"Here's your personal link to the TrainFitter client portal, where "
        f"you can see a summary of your plan and log how it's going:\n\n"
        f"{url_portal}\n\n"
        f"This link is just for you — please don't share it. It expires "
        f"after a few days; ask your trainer for a new one if it stops "
        f"working."
    )


def enviar_enlace_portal(destinatario: str, nombre_cliente: str, url_portal: str, idioma: str = "en") -> None:
    """
    Actually SENDS (not drafts) a short email containing only the client
    portal's magic link. See the module docstring's DESIGN note on
    gmail.send for why this one function is allowed to do what nothing
    else in this module does, and what keeps it narrow.

    Args:
        destinatario: the client's email.
        nombre_cliente: used only for the greeting.
        url_portal: the full, already-built portal URL (see
            agents/portal_tokens.py + ui/app.py for how it's assembled).
        idioma: "en" (default) or "es" — this email's own wrapper text.

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials
            (including a token.json still scoped under the old
            gmail.compose/gmail.readonly-only list -- re-authorizing is
            required once after gmail.send was added, same as every prior
            scope change; see the module docstring's Setup section), or a
            Gmail API failure.
    """
    asunto = ASUNTO_PORTAL_ES if idioma == "es" else ASUNTO_PORTAL_EN
    cuerpo = _construir_mensaje_raw(
        destinatario, asunto=asunto, cuerpo_texto=_construir_cuerpo_portal(nombre_cliente, url_portal, idioma),
    )

    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        # messages().send()'s body is the {"raw": ...} envelope directly --
        # unlike drafts().create(), it isn't wrapped in an outer "message"
        # key. _construir_mensaje_raw() builds the drafts() shape (shared
        # with crear_borrador()), so that one key is unwrapped here.
        servicio.users().messages().send(userId="me", body=cuerpo["message"]).execute()
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc


def _construir_cuerpo_notificacion_checkin(
    nombre_cliente: str, resumen: str, sugerencia: str, peso_kg: float | None = None, idioma: str = "en",
) -> str:
    """Pure formatting, no I/O. resumen/sugerencia are already-formatted
    strings (from agents/adherencia_parser.py's resumir_adherencia()/
    sugerencia_seguimiento()) -- this function only wraps them in a short
    email, it doesn't reimplement that formatting. peso_kg, when the
    client chose to share it, is the one piece of data this email adds on
    top of what resumir_adherencia() already covers -- see
    mcp/notion_connector.py's docstring on why "Weight (kg)" exists."""
    linea_peso = ""
    if peso_kg is not None:
        linea_peso = f"Peso actual: {peso_kg} kg\n\n" if idioma == "es" else f"Current weight: {peso_kg} kg\n\n"

    if idioma == "es":
        return (
            f"{nombre_cliente} acaba de enviar un check-in desde el portal de cliente:\n\n"
            f"{resumen}\n\n"
            f"{linea_peso}"
            f"Siguiente paso sugerido: {sugerencia}\n\n"
            f"(Notificación automática del portal de TrainFitter.)"
        )
    return (
        f"{nombre_cliente} just submitted a check-in via the client portal:\n\n"
        f"{resumen}\n\n"
        f"{linea_peso}"
        f"Suggested next step: {sugerencia}\n\n"
        f"(Automatic notification from the TrainFitter client portal.)"
    )


def enviar_notificacion_checkin(
    destinatario: str,
    nombre_cliente: str,
    datos_checkin: dict,
    valoracion: str | None,
    peso_kg: float | None = None,
    idioma: str = "en",
) -> None:
    """
    Actually SENDS (not drafts) a short email to the TRAINER's own inbox
    the moment a client submits a check-in via the portal -- see the
    module docstring's DESIGN note on why this is the second (and only
    other) function allowed to call messages().send(), and why mailing
    the trainer specifically keeps it outside the "never contacts a
    client automatically" guarantee.

    Args:
        destinatario: the trainer's own notification address
            (TRAINER_NOTIFICATION_EMAIL, see ui/app.py) -- never the
            client's.
        nombre_cliente: whose check-in this is.
        datos_checkin, valoracion: same shape leer_checklist_pdf()
            produces / main.py's adherence loop already uses -- formatted
            here via agents/adherencia_parser.py's resumir_adherencia()/
            sugerencia_seguimiento(), not reimplemented.
        peso_kg: optional current weight, when the client chose to share
            it in the portal's check-in form.
        idioma: "en" (default) or "es".

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials,
            or a Gmail API failure. ui/app.py is expected to catch this
            and swallow it (best-effort) rather than let a notification
            failure block the actual Notion check-in from being saved.
    """
    from adherencia_parser import resumir_adherencia, sugerencia_seguimiento

    resumen = resumir_adherencia(datos_checkin)
    sugerencia = sugerencia_seguimiento(valoracion)
    asunto = (
        f"Nuevo check-in: {nombre_cliente}" if idioma == "es" else f"New check-in: {nombre_cliente}"
    )
    cuerpo = _construir_mensaje_raw(
        destinatario, asunto=asunto,
        cuerpo_texto=_construir_cuerpo_notificacion_checkin(nombre_cliente, resumen, sugerencia, peso_kg, idioma),
    )

    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        servicio.users().messages().send(userId="me", body=cuerpo["message"]).execute()
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc


ASUNTO_INTAKE_EN = "Your TrainFitter intake form"
ASUNTO_INTAKE_ES = "Tu ficha de admisión de TrainFitter"


def _construir_cuerpo_formulario_intake(idioma: str = "en") -> str:
    """Fixed, code-defined template with no variable slots at all -- not
    even a name, since at this point in the funnel the prospect isn't a
    client yet and nothing about them is known. Pure formatting, no I/O."""
    if idioma == "es":
        return (
            "Hola,\n\n"
            "Adjunta va tu ficha de admisión de TrainFitter. Rellénala y "
            "RESPONDE A ESTE EMAIL con el formulario adjunto de nuevo — al "
            "responder, el archivo no se adjunta solo, así que tendrás que "
            "volver a adjuntarlo tú.\n\n"
            "¡Gracias!"
        )
    return (
        "Hi,\n\n"
        "Attached is your TrainFitter intake form. Please fill it in and "
        "REPLY TO THIS EMAIL with the form attached again — replying "
        "doesn't carry the attachment over automatically, so you'll need "
        "to attach it yourself.\n\n"
        "Thanks!"
    )


def enviar_formulario_intake(destinatario: str, idioma: str = "en") -> None:
    """
    Actually SENDS (not drafts) a blank intake form PDF to a prospective
    client -- a third, narrow addition to the gmail.send exception (see the
    module docstring's DESIGN note): a trainer starting a new-client
    conversation used to have to attach agents/pdf_intake.py's blank form
    by hand from their own mail client; this does it from the panel
    directly. Kept as narrow as the two existing send-capable functions:
    a fixed, code-defined template with NO variable slots (not even the
    prospect's name -- nothing about them is known yet), and the one PDF
    attached is always the same freshly-generated blank template, never
    anything a trainer or client could inject content into.

    Args:
        destinatario: the prospective client's email.
        idioma: "en" (default) or "es" -- both the email's own text and the
            attached form's own labels.

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials
            (gmail.send was already required for enviar_enlace_portal(), so
            no further re-authorization is needed on top of that), or a
            Gmail API failure.
    """
    from pdf_intake import NOMBRE_PDF_INTAKE_EN, NOMBRE_PDF_INTAKE_ES, generar_pdf_intake

    asunto = ASUNTO_INTAKE_ES if idioma == "es" else ASUNTO_INTAKE_EN
    nombre_pdf = NOMBRE_PDF_INTAKE_ES if idioma == "es" else NOMBRE_PDF_INTAKE_EN
    cuerpo = _construir_mensaje_raw(
        destinatario,
        asunto=asunto,
        cuerpo_texto=_construir_cuerpo_formulario_intake(idioma),
        adjuntos=[(nombre_pdf, generar_pdf_intake(idioma))],
    )

    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        servicio.users().messages().send(userId="me", body=cuerpo["message"]).execute()
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc


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


def _recolectar_adjuntos_pdf(servicio, id_mensaje: str, parte: dict) -> list[tuple[str, bytes]]:
    """Walks a message's MIME part tree (it's recursive: a multipart part
    contains further "parts") collecting every PDF attachment as
    (filename, raw bytes) pairs. "Looks like a PDF" checks the filename
    extension as well as the declared MIME type — some mail clients don't
    reliably preserve application/pdf on forwarded/re-attached files.
    Small attachment data sometimes comes back inline on the part itself
    (body.data); anything larger comes back as just a body.attachmentId
    that needs a second API call to fetch — both are handled here so
    callers don't need to know which case applies."""
    encontrados = []
    nombre_archivo = parte.get("filename", "")
    parece_pdf = parte.get("mimeType") == "application/pdf" or nombre_archivo.lower().endswith(".pdf")
    if nombre_archivo and parece_pdf:
        cuerpo = parte.get("body", {})
        contenido = None
        if cuerpo.get("data"):
            contenido = base64.urlsafe_b64decode(cuerpo["data"])
        elif cuerpo.get("attachmentId"):
            adjunto = (
                servicio.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=id_mensaje, id=cuerpo["attachmentId"])
                .execute()
            )
            contenido = base64.urlsafe_b64decode(adjunto["data"])
        if contenido is not None:
            encontrados.append((nombre_archivo, contenido))

    for subparte in parte.get("parts", []):
        encontrados.extend(_recolectar_adjuntos_pdf(servicio, id_mensaje, subparte))
    return encontrados


def _extraer_checklist_pdf(servicio, id_mensaje: str, parte: dict) -> bytes | None:
    """Picks the checklist PDF out of a message's attachments. A reply
    could carry more than one PDF (e.g. the client forwarded the whole
    original chain, re-attaching the diet PDF alongside the checklist) —
    only the checklist actually has form fields worth reading. Prefers a
    filename match (NOMBRE_PDF_CHECKLIST_EN/ES); if the client renamed the
    file, falls back to checking each PDF's actual form fields via
    pdf_generador.es_checklist_pdf(). Returns None if nothing found — a
    stray PDF that isn't our checklist (like the diet PDF on its own) has
    nothing parseable in it."""
    from pdf_generador import NOMBRE_PDF_CHECKLIST_EN, NOMBRE_PDF_CHECKLIST_ES, es_checklist_pdf

    adjuntos = _recolectar_adjuntos_pdf(servicio, id_mensaje, parte)
    for nombre_archivo, contenido in adjuntos:
        if nombre_archivo in (NOMBRE_PDF_CHECKLIST_EN, NOMBRE_PDF_CHECKLIST_ES):
            return contenido
    for _nombre_archivo, contenido in adjuntos:
        if es_checklist_pdf(contenido):
            return contenido
    return None


def buscar_respuestas_adherencia() -> list[dict]:
    """
    Searches the inbox for client replies to a plan email that carry an
    PDF attachment — candidate filled-in checklists. Returns every match
    found on every call; it doesn't mark anything as read or apply a label
    (see module docstring for why: dedup against already-processed
    replies is main.py's job, via Notion, not this function's).

    Returns:
        A list of {"id_mensaje", "id_hilo", "remitente", "fecha"
        (YYYY-MM-DD), "contenido"} dicts, one per matching message with a
        readable checklist PDF -- "contenido" is that PDF's raw bytes (see
        agents/pdf_generador.py's leer_checklist_pdf()). Messages that
        matched the search but had no recognizable checklist PDF (e.g. the
        client attached a photo instead, or only re-sent the diet PDF) are
        silently skipped — there's nothing parseable in them.

    Raises:
        GmailClientError: missing/expired credentials the user needs to
            re-authorize, or a Gmail API failure.
    """
    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    # Deliberately not scoped to in:inbox: a trainer who archives mail as
    # they process it would otherwise stop getting a client's reply picked
    # up the moment they file it away, well before a once-daily cron gets
    # to it. Gmail's default search scope (no in: qualifier) already
    # excludes Spam/Trash on its own.
    #
    # Not filtered by -in:sent/-in:drafts either, even though this query
    # would otherwise also match the trainer's OWN copy of the original
    # plan email (same subject, same attachment names): tried that first,
    # but it breaks the moment the trainer tests this by emailing
    # themselves, since Gmail labels a self-to-self reply as BOTH SENT and
    # INBOX -- excluding "sent" would wrongly exclude that reply too, not
    # just the original. The reliable, label-independent signal for "is
    # this actually a reply" is the standard In-Reply-To header (RFC 5322):
    # it's set on every genuine reply and absent from an original message,
    # regardless of which mailbox sent either one -- checked below, once
    # per candidate, after fetching its headers.
    consulta = f'has:attachment filename:pdf (subject:"{ASUNTO_PLAN_EN}" OR subject:"{ASUNTO_PLAN_ES}")'

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        resultado = servicio.users().messages().list(userId="me", q=consulta).execute()

        respuestas = []
        for referencia in resultado.get("messages", []):
            mensaje = (
                servicio.users().messages().get(userId="me", id=referencia["id"], format="full").execute()
            )
            cabeceras = mensaje["payload"]["headers"]
            if not any(c["name"] == "In-Reply-To" for c in cabeceras):
                continue  # the original plan email itself, not a reply to it

            contenido = _extraer_checklist_pdf(servicio, referencia["id"], mensaje["payload"])
            if contenido is None:
                continue

            fecha = datetime.fromtimestamp(int(mensaje["internalDate"]) / 1000, tz=timezone.utc).date().isoformat()
            respuestas.append(
                {
                    "id_mensaje": mensaje["id"],
                    "id_hilo": mensaje["threadId"],
                    "remitente": _extraer_remitente(cabeceras),
                    "fecha": fecha,
                    "contenido": contenido,
                }
            )
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc

    return respuestas


def _extraer_intake_pdf(servicio, id_mensaje: str, parte: dict) -> bytes | None:
    """Picks the intake PDF out of a message's attachments -- same
    filename-first, form-fields-fallback approach as
    _extraer_checklist_pdf(), against agents.pdf_intake's own filename
    constants and es_intake_pdf() instead."""
    from pdf_intake import NOMBRE_PDF_INTAKE_EN, NOMBRE_PDF_INTAKE_ES, es_intake_pdf

    adjuntos = _recolectar_adjuntos_pdf(servicio, id_mensaje, parte)
    for nombre_archivo, contenido in adjuntos:
        if nombre_archivo in (NOMBRE_PDF_INTAKE_EN, NOMBRE_PDF_INTAKE_ES):
            return contenido
    for _nombre_archivo, contenido in adjuntos:
        if es_intake_pdf(contenido):
            return contenido
    return None


def buscar_intakes_nuevos(remitente: str | None = None) -> list[dict]:
    """
    Searches the inbox for new-client intake PDF submissions — a
    prospective client filling in and emailing back the form generated by
    agents.pdf_intake.generar_pdf_intake(). Returns every genuinely filled
    submission found on every call; like buscar_respuestas_adherencia(),
    it doesn't mark anything as read or apply a label — main.py's job is
    to skip ones it's already turned into a Clients row (by message ID,
    via notion_connector.existe_cliente_para_mensaje()).

    Args:
        remitente: optional -- when given, narrows the search to messages
            from this exact address (adds Gmail's own `from:` operator to
            the query below) instead of scanning the whole inbox. Used by
            ui/app.py's "check for a reply" button next to the form-sending
            flow (see enviar_formulario_intake()): the trainer already
            knows which prospect they're checking on, so there's no reason
            to make them wait on (or wade through) every other PDF
            attachment in the mailbox. main.py's own scheduled call passes
            nothing, matching its original scan-everything behavior.

    Unlike an adherence reply, an intake submission is never a reply to
    anything -- there's no In-Reply-To signal to anchor on here. Two other
    signals do the same job instead: es_intake_pdf() confirms the PDF has
    this project's own form fields (a coincidental match on an unrelated
    PDF is structurally implausible), and requiring a non-empty parsed
    name rules out the trainer's own blank template sitting somewhere in
    the mailbox (e.g. Sent, after emailing it to a prospect) from ever
    being mistaken for a real submission.

    Returns:
        A list of {"id_mensaje", "remitente", "fecha" (YYYY-MM-DD),
        "perfil"} dicts, one per matching message with a genuinely filled
        intake PDF. "perfil" is a perfil_cliente-shaped dict missing
        id_cliente/fecha_admision (see
        agents.pdf_intake.leer_intake_pdf()) -- main.py assigns those.

    Raises:
        GmailClientError: missing/expired credentials the user needs to
            re-authorize, or a Gmail API failure.
    """
    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from pdf_intake import leer_intake_pdf

    consulta = "has:attachment filename:pdf"
    if remitente:
        consulta += f' from:"{_validar_destinatario(remitente)}"'

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        resultado = servicio.users().messages().list(userId="me", q=consulta).execute()

        intakes = []
        for referencia in resultado.get("messages", []):
            mensaje = (
                servicio.users().messages().get(userId="me", id=referencia["id"], format="full").execute()
            )
            contenido = _extraer_intake_pdf(servicio, referencia["id"], mensaje["payload"])
            if contenido is None:
                continue

            perfil = leer_intake_pdf(contenido)
            if not perfil["datos_basicos"]["nombre"]:
                continue  # a blank template, not a genuine submission

            fecha = datetime.fromtimestamp(int(mensaje["internalDate"]) / 1000, tz=timezone.utc).date().isoformat()
            intakes.append(
                {
                    "id_mensaje": mensaje["id"],
                    "remitente": _extraer_remitente(mensaje["payload"]["headers"]),
                    "fecha": fecha,
                    "perfil": perfil,
                }
            )
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc

    return intakes
