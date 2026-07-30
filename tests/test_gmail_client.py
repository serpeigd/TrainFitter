"""Tests for mcp/gmail_client.py's pure logic (message building, recipient
validation) — no network, no OAuth, no credentials needed. crear_borrador()
itself (the part that actually talks to the Gmail API) is intentionally not
covered here: it requires a real, authorized Gmail account, same reasoning
as motor="llm" never being exercised against the real Anthropic API in this
suite (see docs/decisiones.md)."""

import base64
from email import message_from_bytes

import pytest
from gmail_client import GmailClientError, _construir_cuerpo_email, _construir_mensaje_raw, _validar_destinatario


def test_valid_email_passes_through_stripped():
    assert _validar_destinatario("  client@example.com  ") == "client@example.com"


@pytest.mark.parametrize("destinatario", ["not-an-email", "", "   ", "@example.com", "client@"])
def test_invalid_email_raises(destinatario):
    with pytest.raises(GmailClientError):
        _validar_destinatario(destinatario)


def test_email_body_includes_client_message_and_macros():
    borrador_rutina = {
        "mensaje_para_el_cliente": "Hi Ana, here's your routine.",
        "resumen_enfoque": "'upper lower' split for intermediate level.",
    }
    borrador_dieta = {
        "mensaje_para_el_cliente": "Hi Ana, here's your diet.",
        "resumen_enfoque": "Estimated 2125 kcal/day.",
        "calorias_objetivo_kcal": 2125,
        "macros": {"proteina_g": 136},
    }
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert "here's your routine" in cuerpo
    assert "here's your diet" in cuerpo
    assert "2125 kcal/day" in cuerpo
    assert "136 g protein" in cuerpo


def test_email_body_wrapper_text_translates_for_spanish():
    """idioma="es" only needs to translate this template's own wrapper text
    (greeting, dividers, footer) -- the plan's own narrative fields are
    already in whichever language they were generated in (see
    rutina_reglas.py/dieta_reglas.py), so this test uses Spanish content for
    those too, matching a real idioma="es" pipeline run."""
    borrador_rutina = {
        "mensaje_para_el_cliente": "Hola Ana, aquí tienes tu rutina.",
        "resumen_enfoque": "Reparto 'torso-pierna' para nivel intermedio.",
    }
    borrador_dieta = {
        "mensaje_para_el_cliente": "Hola Ana, aquí tienes tu dieta.",
        "resumen_enfoque": "Estimación de 2125 kcal/día.",
        "calorias_objetivo_kcal": 2125,
        "macros": {"proteina_g": 136},
    }
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta, idioma="es")
    assert cuerpo.startswith("Hola Ana,")
    assert "--- Rutina ---" in cuerpo
    assert "--- Dieta ---" in cuerpo
    assert "136 g de proteína" in cuerpo


def test_raw_message_is_valid_base64url_rfc2822():
    payload = _construir_mensaje_raw("client@example.com", "Your plan", "Body text here.")
    raw = payload["message"]["raw"]

    decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
    mensaje = message_from_bytes(decoded)

    assert mensaje["to"] == "client@example.com"
    assert mensaje["subject"] == "Your plan"
    assert "Body text here." in mensaje.get_payload()


def test_raw_message_rejects_invalid_recipient():
    with pytest.raises(GmailClientError):
        _construir_mensaje_raw("not-an-email", "Subject", "Body")
