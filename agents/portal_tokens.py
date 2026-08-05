"""
Signed, stateless magic-link tokens for the client-facing portal.

ui/app.py renders two different views out of the same script: the
trainer's panel (default) or a client-only "view your plan, submit a
check-in" view, switched by whether a valid `?portal_token=...` query
parameter is present. This module is what makes that token trustworthy
without needing a database of issued links.

DESIGN — stateless by construction, not looked up anywhere: the token
itself carries its own payload (the client's email, the Notion page ID
their record lives at, and an expiry timestamp), base64url-encoded, with
an HMAC-SHA256 signature appended so a client can't edit which page it
points at or extend its own expiry. Verifying a token needs no network
call and no server-side state at all -- just the same secret key used to
sign it (PORTAL_SECRET_KEY, see .env.example). This matches the project's
existing "no push infrastructure, no persistent backend beyond Notion"
constraint (see gmail_client.py's verificar_envio() docstring on why
send-detection is trainer-triggered instead of a background job) --
adding a token database would be the first piece of real backend state
this project has ever needed.

DESIGN — HMAC over a JWT library: the payload here is three fields and
the verification need is "was this issued by us and is it still valid" --
exactly what hmac+hashlib (both standard library) already do, with zero
new dependencies. A JWT library would add a dependency to solve a problem
this project doesn't have (multiple issuers, key rotation, standard
claim types).

DESIGN — no early revocation: because there's no server-side registry of
issued tokens, there is no list to remove one from either -- a portal
link stays valid until it naturally expires, even if the trainer wanted
to invalidate it sooner (e.g. sent to the wrong address). Accepted the
same way the rest of this project accepts its other minimal-infra
trade-offs; a short default validity window (7 days) bounds how long a
leaked link stays useful. Rotating PORTAL_SECRET_KEY invalidates every
outstanding link at once, as a blunt last resort.
"""

import base64
import hashlib
import hmac
import json
import os
import time

DIAS_VALIDEZ_POR_DEFECTO = 7


class PortalTokenError(Exception):
    """Raised for a missing signing key, or when verifying a malformed,
    tampered, or expired token. ui/app.py is expected to catch this and
    show a plain "this link isn't valid" message instead of crashing."""


def _clave_firma() -> bytes:
    clave = os.environ.get("PORTAL_SECRET_KEY")
    if not clave:
        raise PortalTokenError(
            "Missing PORTAL_SECRET_KEY -- set it to any long random string "
            "before generating or verifying portal links (see .env.example)."
        )
    return clave.encode("utf-8")


def generar_token_portal(email: str, id_pagina_notion: str, dias_validez: int = DIAS_VALIDEZ_POR_DEFECTO) -> str:
    """Builds a signed, self-expiring token identifying one client's
    portal session. Returns a URL-safe string meant to go straight into a
    `?portal_token=...` query parameter -- never a raw email or Notion
    page ID a client could read or edit themselves.

    Raises:
        PortalTokenError: PORTAL_SECRET_KEY isn't set.
    """
    payload = {
        "email": email,
        "pagina": id_pagina_notion,
        "exp": int(time.time()) + dias_validez * 86400,
    }
    cuerpo = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    firma = hmac.new(_clave_firma(), cuerpo.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{cuerpo}.{firma}"


def verificar_token_portal(token: str) -> dict:
    """Validates a token's signature and expiry.

    Returns:
        {"email": ..., "pagina": ...} -- the same values passed to
        generar_token_portal().

    Raises:
        PortalTokenError: PORTAL_SECRET_KEY isn't set, the token is
            malformed or its signature doesn't match (tampered, or signed
            under a different/since-rotated key), or it's expired.
    """
    try:
        cuerpo, firma = token.split(".", 1)
    except ValueError as exc:
        raise PortalTokenError("This portal link isn't valid.") from exc

    firma_esperada = hmac.new(_clave_firma(), cuerpo.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(firma, firma_esperada):
        raise PortalTokenError("This portal link isn't valid.")

    relleno = "=" * (-len(cuerpo) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(cuerpo + relleno))
    except (ValueError, UnicodeDecodeError, KeyError) as exc:
        raise PortalTokenError("This portal link isn't valid.") from exc

    if not isinstance(payload, dict) or "email" not in payload or "pagina" not in payload:
        raise PortalTokenError("This portal link isn't valid.")

    if payload.get("exp", 0) < time.time():
        raise PortalTokenError("This portal link has expired -- ask your trainer for a new one.")

    return {"email": payload["email"], "pagina": payload["pagina"]}
