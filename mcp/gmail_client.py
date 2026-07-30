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

DESIGN — `gmail.metadata` added alongside `gmail.compose`, deliberately not
`gmail.readonly`: once the project owner explicitly opted into detecting a
real send (for the Notion Check-ins database — see notion_connector.py),
the narrowest scope that can answer "was this thread actually sent?" is
`gmail.metadata` — it exposes labels and headers, never message bodies or
attachments. `gmail.readonly` would also work but grants full mailbody read
access this feature doesn't need, so it was deliberately not requested.
Adding a new scope means any existing token.json (authorized under the old
scope list only) stops being sufficient — Google enforces scope at the API
call, not just locally — so re-running the OAuth consent flow (deleting
token.json first) is required once, both locally and on any deployment.

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

Setup (one-time, free, done by the project owner — never by this code):
  1. Create a Google Cloud project and enable the Gmail API.
  2. Create an OAuth 2.0 Client ID (type: Desktop app) and download it as
     credentials.json into the repo root (gitignored — never committed).
  3. In the OAuth consent screen's "Data Access" section, add both scopes
     below (gmail.compose and gmail.metadata) to the app's registered scope
     list — Google rejects a token request for a scope the app doesn't have
     registered, even in testing mode.
  4. First call to crear_borrador() or verificar_envio() opens a browser
     consent screen; the resulting token is cached to token.json (also
     gitignored) so it isn't repeated on every run. If token.json already
     exists from before gmail.metadata was added, delete it first so the
     consent screen re-runs and grants the new scope.
"""

import base64
from email.mime.text import MIMEText
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUTA_CREDENCIALES = REPO_ROOT / "credentials.json"
RUTA_TOKEN = REPO_ROOT / "token.json"

# Draft-only plus read-only label/header access (see module docstring) —
# the narrowest scopes that cover both "create a draft" and "check whether
# it was actually sent" without ever granting message-body read access.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.metadata",
]


class GmailClientError(Exception):
    """Raised for anything that stops a draft from being created — missing
    credentials, an invalid recipient, or an API-side failure. The UI is
    expected to catch this and show a clear message instead of crashing."""


def _validar_destinatario(destinatario: str) -> str:
    destinatario = destinatario.strip()
    if not destinatario or "@" not in destinatario or destinatario.startswith("@") or destinatario.endswith("@"):
        raise GmailClientError(f"'{destinatario}' doesn't look like a valid email address.")
    return destinatario


def _construir_cuerpo_email(nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict) -> str:
    """Plain-text email body summarizing the approved plan. Pure formatting —
    no network, no auth, trivially unit-testable."""
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
        f"(This is a draft prepared by TrainFitter — reviewed and sent by your trainer, never automatically.)"
    )


def _construir_mensaje_raw(destinatario: str, asunto: str, cuerpo_texto: str) -> dict:
    """Builds the base64url-encoded RFC 2822 message the Gmail API expects.
    Pure function: no I/O, safe to unit test without any credentials."""
    destinatario = _validar_destinatario(destinatario)
    mensaje = MIMEText(cuerpo_texto)
    mensaje["to"] = destinatario
    mensaje["subject"] = asunto
    raw = base64.urlsafe_b64encode(mensaje.as_bytes()).decode("utf-8")
    return {"message": {"raw": raw}}


def _obtener_credenciales():
    """Lazy-imports the Google client libraries and runs (or reuses) the
    OAuth flow. Only called from crear_borrador(), never at module import
    time — see the module docstring.

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


def crear_borrador(destinatario: str, nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict) -> dict:
    """
    Creates a Gmail draft (never sends it) with the approved plan.

    Returns:
        {"url": a gmail.com link to the created draft, "thread_id": the
        underlying thread's ID}. thread_id is what verificar_envio() needs
        later — Gmail keeps a sent message in the same thread as the draft
        it came from, which is how a real send gets detected.

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials
            the user needs to re-authorize, or a Gmail API failure.
    """
    cuerpo = _construir_mensaje_raw(
        destinatario,
        asunto=f"Your plan from TrainFitter — {nombre_cliente}",
        cuerpo_texto=_construir_cuerpo_email(nombre_cliente, borrador_rutina, borrador_dieta),
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
    hit send, not just created it. Uses format="metadata" explicitly: the
    gmail.metadata scope this needs only ever authorizes reading labels and
    headers, never the message body (see module docstring).

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
