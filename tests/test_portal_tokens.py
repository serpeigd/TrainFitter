"""Tests for agents/portal_tokens.py -- pure logic, standard library only
(hmac/hashlib/base64/json/time), no network and no credentials needed."""

import time

import pytest
from portal_tokens import PortalTokenError, generar_token_portal, verificar_token_portal


@pytest.fixture(autouse=True)
def _clave_de_prueba(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET_KEY", "test-signing-key-not-for-real-use")


def test_round_trip_returns_the_same_payload():
    token = generar_token_portal("client@example.com", "notion-page-123")
    assert verificar_token_portal(token) == {"email": "client@example.com", "pagina": "notion-page-123"}


def test_tampering_with_the_payload_is_rejected():
    """Editing even one character of the encoded payload must invalidate
    the signature -- this is what stops a client from, say, changing
    which Notion page ID their link points at."""
    token = generar_token_portal("client@example.com", "notion-page-123")
    cuerpo, firma = token.split(".", 1)
    cuerpo_alterado = cuerpo[:-1] + ("A" if cuerpo[-1] != "A" else "B")
    with pytest.raises(PortalTokenError):
        verificar_token_portal(f"{cuerpo_alterado}.{firma}")


def test_tampering_with_the_signature_is_rejected():
    token = generar_token_portal("client@example.com", "notion-page-123")
    cuerpo, firma = token.split(".", 1)
    firma_alterada = firma[:-1] + ("a" if firma[-1] != "a" else "b")
    with pytest.raises(PortalTokenError):
        verificar_token_portal(f"{cuerpo}.{firma_alterada}")


def test_malformed_token_is_rejected():
    with pytest.raises(PortalTokenError):
        verificar_token_portal("not-a-real-token-at-all")


def test_token_signed_under_a_different_key_is_rejected(monkeypatch):
    """Simulates a rotated PORTAL_SECRET_KEY -- see the module docstring's
    DESIGN note on rotation as a blunt last-resort revocation mechanism."""
    token = generar_token_portal("client@example.com", "notion-page-123")
    monkeypatch.setenv("PORTAL_SECRET_KEY", "a-different-key")
    with pytest.raises(PortalTokenError):
        verificar_token_portal(token)


def test_expired_token_is_rejected():
    token = generar_token_portal("client@example.com", "notion-page-123", dias_validez=-1)
    with pytest.raises(PortalTokenError):
        verificar_token_portal(token)


def test_default_validity_window_is_seven_days():
    """Locks in the DIAS_VALIDEZ_POR_DEFECTO=7 default mentioned in the
    module docstring by decoding the token's own embedded expiry --
    gray-box, but the alternative (waiting 7 real days) isn't practical."""
    import base64
    import json

    antes = time.time()
    token = generar_token_portal("client@example.com", "notion-page-123")
    cuerpo, _firma = token.split(".", 1)
    relleno = "=" * (-len(cuerpo) % 4)
    payload = json.loads(base64.urlsafe_b64decode(cuerpo + relleno))

    esperado = antes + 7 * 86400
    assert abs(payload["exp"] - esperado) < 5  # a few seconds of test-run slack


def test_missing_secret_key_raises_on_generate(monkeypatch):
    monkeypatch.delenv("PORTAL_SECRET_KEY", raising=False)
    with pytest.raises(PortalTokenError):
        generar_token_portal("client@example.com", "notion-page-123")


def test_missing_secret_key_raises_on_verify(monkeypatch):
    token = generar_token_portal("client@example.com", "notion-page-123")
    monkeypatch.delenv("PORTAL_SECRET_KEY", raising=False)
    with pytest.raises(PortalTokenError):
        verificar_token_portal(token)


def test_different_clients_get_different_tokens():
    token_a = generar_token_portal("a@example.com", "page-a")
    token_b = generar_token_portal("b@example.com", "page-b")
    assert token_a != token_b


def test_token_is_url_safe():
    """Meant to go straight into a ?portal_token=... query parameter --
    shouldn't contain characters that need percent-encoding."""
    token = generar_token_portal("client@example.com", "notion-page-123")
    assert all(c.isalnum() or c in "-_." for c in token)


def test_a_still_valid_but_soon_to_expire_token_still_verifies():
    """dias_validez=0.0001 (~a few seconds) should still be valid right
    after issuing it -- confirms expiry is a real ">" comparison against
    wall-clock time, not an off-by-one that rejects same-second tokens."""
    token = generar_token_portal("client@example.com", "notion-page-123", dias_validez=0.0001)
    assert verificar_token_portal(token)["email"] == "client@example.com"
