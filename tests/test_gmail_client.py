"""Tests for mcp/gmail_client.py's pure logic (message building, recipient
validation, MIME-tree attachment collection) — no network, no OAuth, no
credentials needed. crear_borrador() itself (the part that actually talks
to the Gmail API) is intentionally not covered here: it requires a real,
authorized Gmail account, same reasoning as motor="llm" never being
exercised against the real Anthropic API in this suite (see
docs/decisiones.md)."""

import base64
from email import message_from_bytes

import pytest
from gmail_client import (
    GmailClientError,
    _construir_cuerpo_email,
    _construir_mensaje_raw,
    _extraer_checklist_pdf,
    _extraer_remitente,
    _recolectar_adjuntos_pdf,
    _validar_destinatario,
)


def _parte_adjunto(filename: str, mime_type: str, contenido: bytes) -> dict:
    """Builds a fake Gmail API message-part dict with inline attachment
    data (body.data), matching the shape buscar_respuestas_adherencia()
    parses -- small enough that Gmail always inlines it, so no
    attachmentId/second API call is involved, which is what makes this
    path testable without a real service object."""
    return {
        "filename": filename,
        "mimeType": mime_type,
        "body": {"data": base64.urlsafe_b64encode(contenido).decode("ascii")},
    }


def test_valid_email_passes_through_stripped():
    assert _validar_destinatario("  client@example.com  ") == "client@example.com"


@pytest.mark.parametrize("destinatario", ["not-an-email", "", "   ", "@example.com", "client@"])
def test_invalid_email_raises(destinatario):
    with pytest.raises(GmailClientError):
        _validar_destinatario(destinatario)


def test_email_body_includes_the_clients_personal_messages():
    """The email body is deliberately brief now (see
    _construir_cuerpo_email()'s docstring) -- the plan's own detail lives
    in the two attached PDFs, not inlined here. Only mensaje_para_el_cliente
    (the trainer's personal note) survives into the body."""
    borrador_rutina = {"mensaje_para_el_cliente": "Hi Ana, here's your routine."}
    borrador_dieta = {"mensaje_para_el_cliente": "Hi Ana, here's your diet."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert "here's your routine" in cuerpo
    assert "here's your diet" in cuerpo


def test_email_body_explains_re_attaching_the_checklist():
    """Real-world lesson (see docs/decisiones.md): replying in Gmail
    doesn't carry the original attachment over automatically, so the body
    needs to say so explicitly or a client's reply arrives with nothing to
    parse."""
    borrador_rutina = {"mensaje_para_el_cliente": "..."}
    borrador_dieta = {"mensaje_para_el_cliente": "..."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert "attach" in cuerpo.lower()
    assert "doesn't carry the attachment over automatically" in cuerpo


def test_email_body_wrapper_text_translates_for_spanish():
    """idioma="es" only needs to translate this template's own wrapper text
    (greeting, attachment explanation, footer) -- mensaje_para_el_cliente is
    already in whichever language it was generated in (see
    rutina_reglas.py/dieta_reglas.py), so this test uses Spanish content for
    it too, matching a real idioma="es" pipeline run."""
    borrador_rutina = {"mensaje_para_el_cliente": "Hola Ana, aquí tienes tu rutina."}
    borrador_dieta = {"mensaje_para_el_cliente": "Hola Ana, aquí tienes tu dieta."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta, idioma="es")
    assert cuerpo.startswith("Hola Ana,")
    assert "aquí tienes tu rutina" in cuerpo
    assert "responde a este email" in cuerpo.lower()


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


def test_raw_message_with_attachments_is_multipart_and_carries_both_files():
    payload = _construir_mensaje_raw(
        "client@example.com", "Your plan", "Body text here.",
        adjuntos=[("diet-plan.pdf", b"%PDF-diet-bytes"), ("adherence-checklist.pdf", b"%PDF-checklist-bytes")],
    )
    decoded = base64.urlsafe_b64decode(payload["message"]["raw"].encode("utf-8"))
    mensaje = message_from_bytes(decoded)

    assert mensaje.is_multipart()
    partes = mensaje.get_payload()
    assert "Body text here." in partes[0].get_payload()
    assert partes[1].get_filename() == "diet-plan.pdf"
    assert partes[1].get_content_type() == "application/pdf"
    assert partes[1].get_payload(decode=True) == b"%PDF-diet-bytes"
    assert partes[2].get_filename() == "adherence-checklist.pdf"
    assert partes[2].get_payload(decode=True) == b"%PDF-checklist-bytes"


def test_extraer_remitente_pulls_bare_address_from_display_name():
    cabeceras = [{"name": "From", "value": "Ana Pérez <ana@example.com>"}]
    assert _extraer_remitente(cabeceras) == "ana@example.com"


def test_extraer_remitente_handles_bare_address_with_no_display_name():
    cabeceras = [{"name": "From", "value": "ana@example.com"}]
    assert _extraer_remitente(cabeceras) == "ana@example.com"


def test_recolectar_adjuntos_pdf_reads_inline_data():
    parte = _parte_adjunto("adherence-checklist.pdf", "application/pdf", b"%PDF-bytes")
    assert _recolectar_adjuntos_pdf(None, "msg-1", parte) == [("adherence-checklist.pdf", b"%PDF-bytes")]


def test_recolectar_adjuntos_pdf_accepts_pdf_extension_sent_as_octet_stream():
    """Some mail clients don't reliably preserve application/pdf on a
    forwarded/re-attached file -- relying on mimeType alone would silently
    drop those replies (see the function's docstring for why the extension
    is checked too)."""
    parte = _parte_adjunto("adherence-checklist.pdf", "application/octet-stream", b"%PDF-bytes")
    assert _recolectar_adjuntos_pdf(None, "msg-1", parte) == [("adherence-checklist.pdf", b"%PDF-bytes")]


def test_recolectar_adjuntos_pdf_ignores_non_pdf_attachments():
    parte = {
        "mimeType": "multipart/mixed",
        "parts": [_parte_adjunto("photo.jpg", "image/jpeg", b"not a pdf")],
    }
    assert _recolectar_adjuntos_pdf(None, "msg-1", parte) == []


def test_extraer_checklist_pdf_prefers_the_known_checklist_filename():
    """A reply could carry more than one PDF (e.g. the client forwarded the
    whole original chain, re-attaching the diet PDF too) -- the one
    matching this project's own checklist filename should win without even
    needing to inspect form fields."""
    parte = {
        "mimeType": "multipart/mixed",
        "parts": [
            _parte_adjunto("diet-plan.pdf", "application/pdf", b"%PDF-diet"),
            _parte_adjunto("adherence-checklist.pdf", "application/pdf", b"%PDF-checklist"),
        ],
    }
    assert _extraer_checklist_pdf(None, "msg-1", parte) == b"%PDF-checklist"


def test_extraer_checklist_pdf_falls_back_to_field_detection_when_renamed():
    """If the client renamed the file, fall back to checking each PDF's
    actual form fields via pdf_generador.es_checklist_pdf() -- uses a real
    generated checklist PDF here, not a fake byte string, since that
    detection genuinely needs to parse the PDF."""
    from pdf_generador import generar_pdf_checklist

    checklist_real = generar_pdf_checklist(
        {"sesiones": [{"dia": "Day 1"}]},
        {"calorias_objetivo_kcal": 2000, "macros": {"proteina_g": 100}},
        "Ana",
    )
    parte = {
        "mimeType": "multipart/mixed",
        "parts": [_parte_adjunto("my-renamed-file.pdf", "application/pdf", checklist_real)],
    }
    assert _extraer_checklist_pdf(None, "msg-1", parte) == checklist_real


def test_extraer_checklist_pdf_returns_none_when_only_the_diet_pdf_is_present():
    """The diet PDF has no form fields at all -- shouldn't be mistaken for
    a checklist just because it's a PDF attachment on a matching reply."""
    from pdf_generador import generar_pdf_dieta

    dieta_real = generar_pdf_dieta({
        "calorias_objetivo_kcal": 2000, "macros": {"proteina_g": 100, "grasa_g": 60, "carbohidratos_g": 200},
        "mensaje_para_el_cliente": "Hi.", "distribucion_comidas": "...",
        "fuentes_proteina_sugeridas": [], "fuentes_carbohidrato_sugeridas": [], "fuentes_grasa_sugeridas": [],
        "consejos_sinergias": [],
    }, "Ana")
    parte = {
        "mimeType": "multipart/mixed",
        "parts": [_parte_adjunto("diet-plan.pdf", "application/pdf", dieta_real)],
    }
    assert _extraer_checklist_pdf(None, "msg-1", parte) is None


def test_extraer_checklist_pdf_returns_none_with_no_pdf_attachments():
    parte = {"mimeType": "multipart/mixed", "parts": []}
    assert _extraer_checklist_pdf(None, "msg-1", parte) is None
