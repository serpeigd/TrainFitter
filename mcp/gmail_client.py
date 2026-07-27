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

DESIGN — pure logic separated from network/auth: _construir_mensaje_raw()
and _construir_cuerpo_email() are plain functions with no I/O, fully unit
tested without any credentials. Only crear_borrador() touches the network,
and only when actually called — the google-api-python-client /
google-auth-oauthlib packages are lazy imports, same convention as
`anthropic` for motor="llm" and `pdfplumber` for the bloodwork parser: the
free pipeline never needs them installed.

Setup (one-time, free, done by the project owner — never by this code):
  1. Create a Google Cloud project and enable the Gmail API.
  2. Create an OAuth 2.0 Client ID (type: Desktop app) and download it as
     credentials.json into the repo root (gitignored — never committed).
  3. First call to crear_borrador() opens a browser consent screen; the
     resulting token is cached to token.json (also gitignored) so it isn't
     repeated on every run.
"""

import base64
from email.mime.text import MIMEText
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUTA_CREDENCIALES = REPO_ROOT / "credentials.json"
RUTA_TOKEN = REPO_ROOT / "token.json"

# Draft-only, by design (see module docstring) — this is the narrowest scope
# the Gmail API offers for composing mail.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


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
    time — see the module docstring."""
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


def crear_borrador(destinatario: str, nombre_cliente: str, borrador_rutina: dict, borrador_dieta: dict) -> str:
    """
    Creates a Gmail draft (never sends it) with the approved plan.

    Returns:
        A gmail.com link to the created draft, so the trainer can jump
        straight to it.

    Raises:
        GmailClientError: invalid recipient, missing/expired credentials
            the user needs to re-authorize, or a Gmail API failure.
    """
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    cuerpo = _construir_mensaje_raw(
        destinatario,
        asunto=f"Your plan from TrainFitter — {nombre_cliente}",
        cuerpo_texto=_construir_cuerpo_email(nombre_cliente, borrador_rutina, borrador_dieta),
    )

    try:
        servicio = build("gmail", "v1", credentials=_obtener_credenciales())
        borrador = servicio.users().drafts().create(userId="me", body=cuerpo).execute()
    except HttpError as exc:
        raise GmailClientError(f"Gmail API error: {exc}") from exc

    return f"https://mail.google.com/mail/u/0/#drafts/{borrador['message']['id']}"
