"""
Gmail connector: turns an approved plan into either a Gmail **draft**
(crear_borrador()) or, since the DESIGN note below on enviar_plan(), a real
**sent** email — which one depends on whether the validator's own verdict
says a human needs to look first. This is the real-world version of the
UI's "simulated approval" step. The safety principle it preserves is no
longer "TrainFitter never contacts a client on its own" unconditionally —
that's still true for every "revision_reforzada" plan (always a draft, a
human always reviews and sends it) — but for a plan the validator itself
marked "aprobado_automatico" (no reason found for a human to look first),
ui/app.py now calls enviar_plan() directly, no draft, no click. See that
function's own DESIGN note for the full reasoning and how this was scoped.

DESIGN — draft-only was originally by construction, not just convention:
`gmail.compose` alone physically cannot send mail — Google's own API
rejects a send call under that scope. That's why gmail.send had to be
requested as a separate, additional scope for every function below that
actually calls messages().send() — none of them could work under
gmail.compose alone. On the public demo (trainfitter.streamlit.app),
where anyone can type any email address into the client-email field, the
scope alone no longer stops a real send the way it originally did (see
enviar_plan()'s DESIGN note below) — APP_APPROVAL_PASSWORD is what
stands in that gap now, required as one confirmation step before
enviar_plan() fires on any deployment where it's set.

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

DESIGN — gmail.send started as a deliberate, narrow exception to "never
sends automatically", scoped to three functions, each one either
trainer-triggered with fixed, non-improvised content, or aimed at the
trainer's own inbox rather than a client's — never a client receiving
unsolicited, trainer-unreviewed content. enviar_plan() (below) is a
fourth, genuinely different case — a client DOES receive trainer-
unreviewed content now, by explicit design, when the validator itself
already vouched for the plan. Read that function's own DESIGN note
first; the three below predate it. enviar_enlace_portal() sends a
real message (via messages().send(), not drafts().create()) containing
nothing but a magic link (see mcp/notion_connector.py's
generar_referencia_portal()) to the client portal — never plan content,
never anything the trainer hasn't
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

DESIGN — enviar_formulario_intake() is the third of the three
"predates enviar_plan()" functions allowed to call messages().send():
requested directly, to let a trainer email a prospective client the
blank intake form (see agents/pdf_intake.py) straight from the panel
instead of attaching it by hand from their own mail client. The
narrowest of the three by content: its template has NO variable slots at
all, not even the prospect's name (nothing about them is known yet at
this point in the funnel) — the only thing that ever varies between
calls is which of two fixed, code-defined PDF/text pairs (EN/ES) gets
attached. Same gating as enviar_enlace_portal(): one explicit button,
behind APP_APPROVAL_PASSWORD on deployments where it's set (this is the
one action in the "New Client" tab that touches a real inbox before any
client data exists yet, so it needs the same protection the rest of that
tab's write actions already have).

DESIGN — enviar_plan() is the fourth function allowed to call
messages().send(), and the one genuine reversal of "TrainFitter never
contacts a client on its own": requested directly by the project owner
-- when a plan needs no enhanced review (validator verdict
"aprobado_automatico"), waiting for the trainer to manually approve,
create a draft, and send it from Gmail is pure friction with no safety
benefit, since nothing about that review step would actually change
whether the plan goes out. Scoped narrowly on purpose: only reachable
from ui/app.py's own auto-send flow, which checks the verdict itself
before ever calling this (a "revision_reforzada" plan always goes
through crear_borrador() instead, no matter what) -- this function has
no verdict-checking logic of its own, so that check living correctly in
exactly one call site matters. On the public demo
(APP_APPROVAL_PASSWORD set), ui/app.py still requires that password once
as a real confirmation step immediately before calling this -- the
scope-level protection draft-only used to provide (see the DESIGN note
above) doesn't apply to a function that calls messages().send() by
design, so the password is what keeps a random visitor from making this
app email an arbitrary address for free. On a private deployment (no
password configured), it fires with zero clicks, exactly as requested.
Shares its content-building (attachments, body) with crear_borrador() via
_preparar_envio_plan() -- the two differ only in the one Gmail API call
at the end.

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


def dividir_en_puntos(texto: str) -> list[str]:
    """Splits a trainer-written paragraph into individual sentences, for
    rendering as bullet points instead of a wall of prose -- real,
    direct feedback ("que sean como bullet points... si hay mucho texto
    nadie se lo lee") on top of the earlier "less AI-sounding" pass.
    Public (not underscore-prefixed) and deliberately kept here rather
    than duplicated: ui/app.py's client portal imports this too, so the
    plan email and the portal render the trainer's message the same way.

    Splits on sentence-ending punctuation followed by whitespace -- safe
    for this project's generated text (mensaje_para_el_cliente/
    progresion/consejos_sinergias), which never uses periods for
    abbreviations or decimals. Each fragment's first letter is
    capitalized -- the very first one is often the tail of a greeting
    stripped off by quitar_saludo() (e.g. "aquí tienes tu rutina..."),
    which would otherwise open a bullet list lowercase. Returns plain
    sentence strings, no bullet marker -- callers prefix however fits
    their medium ("• " for a plain-text email, "- " for Streamlit
    markdown)."""
    fragmentos = re.split(r"(?<=[.!?])\s+", texto.strip())
    return [f[:1].upper() + f[1:] for f in (frag.strip() for frag in fragmentos) if f]


def quitar_saludo(mensaje: str, nombre_cliente: str, idioma: str) -> str:
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


def obtener_texto_cliente(mensaje_para_el_cliente: str, nombre_cliente: str, idioma: str, tip: str = "") -> str:
    """The minimal, concrete text that should represent one plan section
    (routine or diet) to the client -- `tip` itself if given (e.g.
    borrador_rutina["progresion"], the diet's first consejos_sinergias
    entry), otherwise the first sentence of the generic
    mensaje_para_el_cliente (greeting-stripped). A section should never
    show zero content, but the generic warm note is dropped whenever a
    real, specific tip exists -- it's tone, not information (real,
    pointed feedback: bulleting the whole message still read as "MUY
    generales y mucho texto").

    Shared by _construir_cuerpo_email() (the plan email) and
    mcp/notion_connector.py (so the client portal shows the identical
    content, not a second, looser summary) -- "aplica esto también al
    portal" was a direct follow-up request. May still be multiple
    sentences (a tip like `progresion` usually is) -- callers split it
    further with dividir_en_puntos() for their own bullet rendering."""
    if tip:
        return tip
    mensaje = quitar_saludo(mensaje_para_el_cliente, nombre_cliente, idioma)
    puntos = dividir_en_puntos(mensaje)
    return puntos[0] if puntos else ""


def _construir_cuerpo_email(
    nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict, idioma: str = "en",
    incluir_checklist: bool = False, url_portal: str | None = None, semana: int | None = None,
) -> str:
    """Brief, scannable plain-text email body -- the plan's own detail
    lives in the attached PDFs now (see agents/pdf_generador.py), not
    inlined here. Pure formatting -- no network, no auth, trivially
    unit-testable.

    DESIGN -- content was cut hard a second time, same day, after the
    first "bullet the whole message" pass still read as "MUY generales y
    mucho texto" against a pasted real example. The generic warm note
    (mensaje_para_el_cliente -- "aquí tienes tu borrador... cuéntamelo y
    lo solucionamos") is dropped from this email ENTIRELY now, not
    bulleted: it's not information, it's tone, and the client already
    gets tone from a short, direct email rather than from restating it.
    What's left is ONLY the concrete, specific content -- progresion
    (routine) and the diet's first consejos_sinergias entry -- each split
    into bullet points via dividir_en_puntos(). Falls back to the first
    sentence of mensaje_para_el_cliente (greeting-stripped) ONLY if that
    tip is genuinely empty (e.g. "normal"/"basico" diets, where synergy
    tips are gated off -- see dieta_reglas.py), so a section is never
    left with zero bullets. Section labels dropped their 🏋️/🍽️ emoji too,
    matching the exact plain-text example given.

    DESIGN -- third cut, same reasoning again: the fixed "I've attached
    the PDFs..."/"If your mail or Drive preview won't let you type..."
    closing was removed outright, direct request ("quita este texto").
    Every mail client already shows its own attachment indicator, so
    stating "I've attached X" added a sentence without adding
    information; the PDF-viewer caveat covered a real but now-untold
    fraction of readers, at the cost of a paragraph shown to everyone.
    Nothing replaces it -- the email just ends after the bullets unless
    a checklist is attached, in which case its own reply-instructions
    paragraph is still needed (genuinely functional, not filler: without
    it, a client's reply carries no attachment for main.py to parse) and
    now names the checklist itself ("el checklist que te adjunto" /
    "the attached checklist") so it reads standalone.

    Args:
        incluir_checklist: whether the adherence checklist PDF was
            attached this time (see crear_borrador()'s own docstring --
            opt-in, default False now that the client portal is the
            intended default way to log adherence). Only affects whether
            the reply-instructions paragraph is appended at all.
        url_portal: optional -- when given, appends one short paragraph
            with a fresh portal link. Used by the check-in-driven
            regeneration flow (ui/app.py's _vista_portal_cliente()): a
            client's plan is rebuilt after they log adherence, and rather
            than a second, separate email just for the new portal link,
            it rides along in the same draft as the regenerated plan --
            "dentro del mismo correo," a direct request. None (default)
            for the normal new-plan draft, which has no reason to repeat
            a link the trainer sends separately via enviar_enlace_portal().
        semana: optional -- the check-in count (1-indexed) that triggered
            this regeneration, e.g. 2 for a client's second submitted
            check-in. Only meaningful together with url_portal (a client's
            very first plan has no "week" yet); prepends a short "Week N:"
            header so a client who's re-reading this email later has an
            immediate sense of which update it is, direct request.

    idioma only affects this template's own wrapper text (greeting, section
    labels, attachment list) — mensaje_para_el_cliente/progresion/
    consejos_sinergias were already generated in whichever language the
    trainer had selected when the plan was created (see
    rutina_reglas.py/dieta_reglas.py), so this just needs to match that,
    not translate anything itself."""
    primer_nombre = nombre_cliente.split()[0] if nombre_cliente.strip() else nombre_cliente
    tips_dieta = borrador_dieta.get("consejos_sinergias") or []
    texto_rutina = obtener_texto_cliente(
        borrador_rutina["mensaje_para_el_cliente"], nombre_cliente, idioma, borrador_rutina.get("progresion", ""),
    )
    texto_dieta = obtener_texto_cliente(
        borrador_dieta["mensaje_para_el_cliente"], nombre_cliente, idioma, tips_dieta[0] if tips_dieta else "",
    )
    bullets_rutina = "\n".join(f"• {p}" for p in dividir_en_puntos(texto_rutina))
    bullets_dieta = "\n".join(f"• {p}" for p in dividir_en_puntos(texto_dieta))

    cabecera_semana = ""
    if semana and url_portal:
        cabecera_semana = f"Semana {semana}:\n\n" if idioma == "es" else f"Week {semana}:\n\n"

    if idioma == "es":
        cuerpo = f"{cabecera_semana}Hola {primer_nombre},\n\nRutina:\n{bullets_rutina}\n\nDieta:\n{bullets_dieta}\n"
        if incluir_checklist:
            cuerpo += (
                "\n\nDentro de unas semanas, cuando ya hayas arrancado, rellena el checklist que te "
                "adjunto y respóndeme a este mismo correo con el PDF adjunto otra vez (al responder "
                "no se adjunta solo, así que tendrás que volver a añadirlo tú)."
            )
        if url_portal:
            cuerpo += f"\n\nTu enlace al portal, actualizado:\n{url_portal}"
        return cuerpo

    cuerpo = f"{cabecera_semana}Hi {primer_nombre},\n\nRoutine:\n{bullets_rutina}\n\nDiet:\n{bullets_dieta}\n"
    if incluir_checklist:
        cuerpo += (
            "\n\nIn a few weeks, once you've actually started, fill in the attached checklist and "
            "reply to this same email with the PDF attached again (replying doesn't carry the "
            "attachment over automatically, so you'll need to add it back yourself)."
        )
    if url_portal:
        cuerpo += f"\n\nYour updated portal link:\n{url_portal}"
    return cuerpo


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

    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credenciales = None
    if RUTA_TOKEN.exists():
        credenciales = Credentials.from_authorized_user_file(str(RUTA_TOKEN), SCOPES)

    if not credenciales or not credenciales.valid:
        if credenciales and credenciales.expired and credenciales.refresh_token:
            try:
                credenciales.refresh(Request())
            except RefreshError as exc:
                # A revoked/expired refresh token (Google access revoked,
                # password change, >6 months unused) surfaces as this raw
                # exception -- previously uncaught here, so it propagated
                # past ui/app.py's narrow `except (GmailClientError,
                # ImportError, ModuleNotFoundError)` and crashed the whole
                # app instead of just failing the draft/send action. Wrapped
                # into the one exception type the caller already handles,
                # same fix shape as the PDF-generation bug documented above
                # crear_borrador(). Re-authorizing needs a real human (the
                # OAuth consent screen), not something this function can do
                # on its own -- see this module's docstring for the steps.
                raise GmailClientError(
                    "Gmail access has expired or been revoked -- re-authorize locally "
                    f"(delete {RUTA_TOKEN.name} and rerun the OAuth flow) and, on "
                    "Streamlit Cloud, update the GMAIL_TOKEN_JSON secret with the new token."
                ) from exc
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


def _preparar_envio_plan(
    nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict, idioma: str, incluir_checklist: bool,
    url_portal: str | None, semana: int | None = None,
) -> tuple[str, list[tuple[str, bytes]], str]:
    """Shared by crear_borrador() (draft) and enviar_plan() (real send) --
    both build the exact same subject/attachments/body, they only differ
    in the one Gmail API call at the end (drafts().create() vs
    messages().send()). Pure rendering, no network -- raises
    GmailClientError on a PDF/body-build failure, same contract both
    callers already documented before this was factored out.

    Returns: (asunto, adjuntos, cuerpo_texto)."""
    # Lazy import, same convention as googleapiclient below: reportlab (the
    # actual heavy dependency, imported inside pdf_generador.py's own
    # functions) never needs to be installed for the default free pipeline.
    from pdf_generador import (
        NOMBRE_PDF_CHECKLIST_EN,
        NOMBRE_PDF_CHECKLIST_ES,
        NOMBRE_PDF_DIETA_EN,
        NOMBRE_PDF_DIETA_ES,
        NOMBRE_PDF_RUTINA_EN,
        NOMBRE_PDF_RUTINA_ES,
        generar_pdf_checklist,
        generar_pdf_dieta,
        generar_pdf_rutina,
    )

    asunto = f"{ASUNTO_PLAN_ES} — {nombre_cliente}" if idioma == "es" else f"{ASUNTO_PLAN_EN} — {nombre_cliente}"
    nombre_pdf_dieta = NOMBRE_PDF_DIETA_ES if idioma == "es" else NOMBRE_PDF_DIETA_EN
    nombre_pdf_rutina = NOMBRE_PDF_RUTINA_ES if idioma == "es" else NOMBRE_PDF_RUTINA_EN

    # Building the PDFs/email body is local rendering, not a Gmail API call,
    # but every caller only ever expects GmailClientError out of this (see
    # their own except clauses) -- a bug in reportlab/pypdf rendering
    # against some real client's actual data (malformed field, an edge
    # case none of the example clients happen to hit) must not surface as
    # an unhandled TypeError/ValueError/etc. that crashes the whole app.
    # Wrapped once here rather than in every pdf_generador.py function, so
    # that module's own functions/tests stay exception-neutral.
    try:
        adjuntos = [
            (nombre_pdf_rutina, generar_pdf_rutina(borrador_rutina, nombre_cliente, idioma)),
            (nombre_pdf_dieta, generar_pdf_dieta(borrador_dieta, nombre_cliente, idioma)),
        ]
        if incluir_checklist:
            nombre_pdf_checklist = NOMBRE_PDF_CHECKLIST_ES if idioma == "es" else NOMBRE_PDF_CHECKLIST_EN
            adjuntos.append(
                (nombre_pdf_checklist, generar_pdf_checklist(borrador_rutina, borrador_dieta, nombre_cliente, idioma)),
            )
        cuerpo_texto = _construir_cuerpo_email(
            nombre_cliente, borrador_rutina, borrador_dieta, idioma, incluir_checklist, url_portal, semana,
        )
    except Exception as exc:
        raise GmailClientError(f"Could not build the plan PDFs/email body: {exc}") from exc

    return asunto, adjuntos, cuerpo_texto


def crear_borrador(
    destinatario: str, nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict, idioma: str = "en",
    incluir_checklist: bool = False, url_portal: str | None = None, semana: int | None = None,
) -> dict:
    """
    Creates a Gmail draft (never sends it) with the approved plan: a brief
    note (see _construir_cuerpo_email()) plus the two PDFs generated by
    agents/pdf_generador.py that describe the plan itself -- the full
    routine and the full diet, always attached, mirroring each other.

    Used for the "revision_reforzada" path (needs a real human look
    before anything goes out) and, in ui/app.py, as the recovery path if
    enviar_plan() below fails on the auto-send flow.

    Args:
        destinatario, nombre_cliente, borrador_rutina, borrador_dieta: same as before.
        idioma: "en" (default) or "es" — language of this email's own
            wrapper text and the PDFs' own labels; see
            _construir_cuerpo_email()'s docstring.
        incluir_checklist: default False. When True, also attaches the
            fillable adherence checklist (agents/pdf_generador.py's
            generar_pdf_checklist()) for the client to mark up and send
            back. Opt-in rather than automatic, per the project owner's
            own call: the client portal (see enviar_enlace_portal()) is
            now the intended default way to log adherence, in-app rather
            than via a PDF round-trip -- the checklist stays available
            for the specific case a trainer still wants it (e.g. a client
            without portal access, or who prefers paper/PDF), triggered
            from ui/app.py's own checkbox next to "Create draft," not
            included by default.
        url_portal: optional -- see _construir_cuerpo_email()'s own
            docstring. Rides along in this same draft rather than a
            second email; None (default) for the normal approval-flow draft.
        semana: optional -- see _construir_cuerpo_email()'s own docstring.

    Returns:
        {"url": a gmail.com link to the created draft, "thread_id": the
        underlying thread's ID}. thread_id is what verificar_envio() needs
        later — Gmail keeps a sent message in the same thread as the draft
        it came from, which is how a real send gets detected.

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials
            the user needs to re-authorize, or a Gmail API failure.
    """
    asunto, adjuntos, cuerpo_texto = _preparar_envio_plan(
        nombre_cliente, borrador_rutina, borrador_dieta, idioma, incluir_checklist, url_portal, semana,
    )
    cuerpo = _construir_mensaje_raw(destinatario, asunto=asunto, cuerpo_texto=cuerpo_texto, adjuntos=adjuntos)

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


def enviar_plan(
    destinatario: str, nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict, idioma: str = "en",
    incluir_checklist: bool = False, url_portal: str | None = None,
) -> dict:
    """
    Actually SENDS (not drafts) the plan email -- same content
    crear_borrador() builds (see _preparar_envio_plan()), one Gmail API
    call different (messages().send() instead of drafts().create()).

    A real, deliberate widening of the gmail.send exception (see this
    module's docstring): the earlier two uses (enviar_enlace_portal(),
    enviar_formulario_intake()) were fixed, single-variable-slot
    templates with no attachments -- this one sends the full plan (two
    PDFs, the trainer's own generated content) with no draft/review step
    at all. Confirmed directly with the project owner before being built,
    same as every other exception to "TrainFitter always drafts, never
    sends" -- ui/app.py only calls this for a plan whose validator
    verdict is "aprobado_automatico" (no reason for a human to look
    first), never for "revision_reforzada". See docs/decisiones.md.

    Args: same as crear_borrador().

    Returns:
        {"message_id": the sent message's ID, "thread_id": its thread ID}
        -- no "url" (there's no draft to link to); the thread ID is kept
        for symmetry with crear_borrador()'s return shape even though
        nothing currently reads it back (a real send needs no later
        verificar_envio() check -- it's confirmed the moment this
        function returns without raising).

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials
            the user needs to re-authorize, or a Gmail API failure.
    """
    asunto, adjuntos, cuerpo_texto = _preparar_envio_plan(
        nombre_cliente, borrador_rutina, borrador_dieta, idioma, incluir_checklist, url_portal,
    )
    cuerpo = _construir_mensaje_raw(destinatario, asunto=asunto, cuerpo_texto=cuerpo_texto, adjuntos=adjuntos)

    credenciales = _obtener_credenciales()

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        # Real, reported production bug: messages().send()'s body is the
        # {"raw": ...} envelope directly -- unlike drafts().create(), it
        # isn't wrapped in an outer "message" key (see
        # enviar_enlace_portal()'s own comment on this exact distinction,
        # which this function failed to follow). Passing the wrapped dict
        # straight through made Gmail's API reject every real send with
        # "'raw' RFC822 payload message string ... required" -- the
        # aprobado_automatico zero-click path and the revision_reforzada
        # "send directly" button both call this function, so both were
        # broken. Missed by this project's own mocked-network tests
        # because the mock never validated the real API's body shape --
        # see tests/test_gmail_client_network.py's matching fix.
        mensaje = servicio.users().messages().send(userId="me", body=cuerpo["message"]).execute()
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc

    return {"message_id": mensaje["id"], "thread_id": mensaje["threadId"]}


ASUNTO_PORTAL_EN = "Your TrainFitter client portal link"
ASUNTO_PORTAL_ES = "Tu enlace al portal de TrainFitter"


def _construir_cuerpo_portal(nombre_cliente: str, url_portal: str, idioma: str = "en") -> str:
    """Fixed, code-defined template with exactly one variable slot (the
    link itself) -- see the module docstring's DESIGN note on gmail.send
    for why that matters specifically for this one function. Pure
    formatting, no I/O, trivially unit-testable.

    Greets by first name only, same as _construir_cuerpo_email() -- real
    feedback that every client-facing email should read less formal/
    automated, more like one person writing to another."""
    primer_nombre = nombre_cliente.split()[0] if nombre_cliente.strip() else nombre_cliente
    if idioma == "es":
        return (
            f"Hola {primer_nombre},\n\n"
            f"Aquí tienes tu enlace personal al portal de TrainFitter, donde "
            f"puedes ver tu plan de esta semana y contarme cómo te va:\n\n"
            f"{url_portal}\n\n"
            f"Es solo tuyo, así que mejor no lo compartas. Caduca pasados "
            f"unos días — si deja de funcionar, pídeme uno nuevo."
        )
    return (
        f"Hi {primer_nombre},\n\n"
        f"Here's your personal link to the TrainFitter client portal, where "
        f"you can see this week's plan and let me know how it's going:\n\n"
        f"{url_portal}\n\n"
        f"It's just for you, so best not to share it. It expires after a "
        f"few days — if it stops working, just ask me for a new one."
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
            mcp/notion_connector.py's generar_referencia_portal() + ui/app.py
            for how it's assembled).
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
    tendencia: str | None = None,
) -> str:
    """Pure formatting, no I/O. resumen/sugerencia/tendencia are already-
    formatted strings (from agents/adherencia_parser.py's
    resumir_adherencia()/sugerencia_seguimiento()/tendencia_peso()) --
    this function only wraps them in a short email, it doesn't reimplement
    that formatting. peso_kg, when the client chose to share it, is the
    one piece of data this email adds on top of what resumir_adherencia()
    already covers -- see mcp/notion_connector.py's docstring on why
    "Weight (kg)" exists. tendencia is optional and only ever present for
    a goal with an unambiguous expected weight direction (fat loss/
    hypertrophy) with enough real trend data behind it -- see
    tendencia_peso()'s own docstring for why it's silent otherwise."""
    linea_peso = ""
    if peso_kg is not None:
        linea_peso = f"Peso actual: {peso_kg} kg\n\n" if idioma == "es" else f"Current weight: {peso_kg} kg\n\n"
    linea_tendencia = f"⚠️ {tendencia}\n\n" if tendencia else ""

    if idioma == "es":
        return (
            f"{nombre_cliente} acaba de enviar un check-in desde el portal de cliente:\n\n"
            f"{resumen}\n\n"
            f"{linea_peso}"
            f"{linea_tendencia}"
            f"Siguiente paso sugerido: {sugerencia}\n\n"
            f"(Notificación automática del portal de TrainFitter.)"
        )
    return (
        f"{nombre_cliente} just submitted a check-in via the client portal:\n\n"
        f"{resumen}\n\n"
        f"{linea_peso}"
        f"{linea_tendencia}"
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
    historial: list[dict] | None = None,
    objetivo: str | None = None,
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
        historial, objetivo: optional -- when both are given, this
            function also runs agents/adherencia_parser.py's
            tendencia_peso() and includes its result if it flags
            anything. Omit either (the default) to skip the weight-trend
            check entirely, e.g. when the caller doesn't have a fresh
            history handy.

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials,
            or a Gmail API failure. ui/app.py is expected to catch this
            and swallow it (best-effort) rather than let a notification
            failure block the actual Notion check-in from being saved.
    """
    from adherencia_parser import resumir_adherencia, sugerencia_seguimiento, tendencia_peso

    resumen = resumir_adherencia(datos_checkin)
    sugerencia = sugerencia_seguimiento(valoracion)
    tendencia = tendencia_peso(historial, objetivo, idioma) if historial is not None else None
    asunto = (
        f"Nuevo check-in: {nombre_cliente}" if idioma == "es" else f"New check-in: {nombre_cliente}"
    )
    cuerpo = _construir_mensaje_raw(
        destinatario, asunto=asunto,
        cuerpo_texto=_construir_cuerpo_notificacion_checkin(
            nombre_cliente, resumen, sugerencia, peso_kg, idioma, tendencia,
        ),
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
    Searches the inbox for client replies to a plan email that carry a
    PDF attachment — candidate filled-in checklists. Returns every match
    found on every call; it doesn't mark anything as read or apply a label
    (see module docstring for why: dedup against already-processed
    replies is main.py's job, via Notion, not this function's).

    Accepts both a genuine in-thread reply (In-Reply-To header set) AND a
    forward from someone other than the trainer's own account -- closing a
    real, previously disclosed gap (see docs/decisiones.md): a client who
    hits Forward instead of Reply used to never be picked up at all, since
    a forward carries no In-Reply-To header either, identical in that
    respect to the trainer's own original sent copy. What actually needed
    excluding was never "not a reply" — it was specifically "the trainer's
    own sent copy of the still-blank original showing up in its own
    self-search." Checking the sender against the authenticated account's
    own address (via users().getProfile()) draws that exact line instead:
    a forward from the client's own address now gets through. The other
    half of the original worry -- a blank-but-structurally-intact
    checklist reading as a false "Low" (leer_checklist_pdf() only returns
    valoracion=None when a PDF has none of the expected fields at all, not
    when they're merely unfilled) -- is caught by main.py's own,
    independent adherencia_parser.checklist_tiene_contenido_real() gate,
    which every candidate this function returns still has to pass before
    it's ever logged to Notion.

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
    # just the original. The actual signal checked below is the sender's
    # address against the authenticated account's own (see docstring).
    consulta = f'has:attachment filename:pdf (subject:"{ASUNTO_PLAN_EN}" OR subject:"{ASUNTO_PLAN_ES}")'

    try:
        servicio = build("gmail", "v1", credentials=credenciales)
        # Best-effort: if getProfile() ever fails to return an address (it
        # shouldn't, for a successfully authenticated account), email_propio
        # stays "" and the `and email_propio` guard below just skips the
        # self-copy check entirely rather than raising -- the In-Reply-To
        # path alone still catches every genuine reply either way.
        email_propio = servicio.users().getProfile(userId="me").execute().get("emailAddress", "").lower()
        resultado = servicio.users().messages().list(userId="me", q=consulta).execute()

        respuestas = []
        for referencia in resultado.get("messages", []):
            mensaje = (
                servicio.users().messages().get(userId="me", id=referencia["id"], format="full").execute()
            )
            cabeceras = mensaje["payload"]["headers"]
            es_respuesta_en_hilo = any(c["name"] == "In-Reply-To" for c in cabeceras)
            remitente = _extraer_remitente(cabeceras)
            if not es_respuesta_en_hilo and email_propio and remitente.lower() == email_propio:
                continue  # the trainer's own sent copy of the original, not a client submission

            contenido = _extraer_checklist_pdf(servicio, referencia["id"], mensaje["payload"])
            if contenido is None:
                continue

            fecha = datetime.fromtimestamp(int(mensaje["internalDate"]) / 1000, tz=timezone.utc).date().isoformat()
            respuestas.append(
                {
                    "id_mensaje": mensaje["id"],
                    "id_hilo": mensaje["threadId"],
                    "remitente": remitente,
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
