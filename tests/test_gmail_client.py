"""Tests for mcp/gmail_client.py's pure logic (message building, recipient
validation, MIME-tree attachment collection) — no network, no OAuth, no
credentials needed. The network-touching functions themselves
(crear_borrador(), verificar_envio(), buscar_respuestas_adherencia()) are
covered separately in test_gmail_client_network.py, against a mocked
googleapiclient service rather than a real, authorized Gmail account."""

import base64
from email import message_from_bytes

import pytest
from gmail_client import (
    SCOPES,
    GmailClientError,
    _construir_cuerpo_email,
    _construir_cuerpo_formulario_intake,
    _construir_cuerpo_notificacion_checkin,
    _construir_cuerpo_portal,
    _construir_mensaje_raw,
    _extraer_checklist_pdf,
    _extraer_intake_pdf,
    _extraer_remitente,
    _quitar_saludo,
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


def test_email_body_always_lists_both_the_routine_and_diet_pdfs():
    """Real gap fixed directly: the routine used to have no standalone
    document at all, unlike the diet -- both are now always attached and
    always listed, regardless of the checklist opt-in below."""
    borrador_rutina = {"mensaje_para_el_cliente": "..."}
    borrador_dieta = {"mensaje_para_el_cliente": "..."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert "Your routine (PDF)" in cuerpo
    assert "Your diet (PDF)" in cuerpo


def test_email_body_omits_the_checklist_by_default():
    """The checklist PDF is opt-in now (see crear_borrador()'s docstring)
    -- the client portal is the intended default way to log adherence."""
    borrador_rutina = {"mensaje_para_el_cliente": "..."}
    borrador_dieta = {"mensaje_para_el_cliente": "..."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert "checklist" not in cuerpo.lower()
    assert "reply to this email" not in cuerpo.lower()


def test_email_body_explains_re_attaching_the_checklist_when_included():
    """Real-world lesson (see docs/decisiones.md): replying in Gmail
    doesn't carry the original attachment over automatically, so the body
    needs to say so explicitly or a client's reply arrives with nothing to
    parse -- but only when the checklist was actually attached."""
    borrador_rutina = {"mensaje_para_el_cliente": "..."}
    borrador_dieta = {"mensaje_para_el_cliente": "..."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta, incluir_checklist=True)
    assert "Adherence checklist (PDF, fillable)" in cuerpo
    assert "doesn't carry the attachment over automatically" in cuerpo


def test_email_body_includes_the_top_routine_and_diet_tips():
    """A real, easy-to-skim key point per section straight from the plan
    itself, instead of making the client open a PDF to see it."""
    borrador_rutina = {"mensaje_para_el_cliente": "...", "progresion": "Add one rep before adding weight."}
    borrador_dieta = {
        "mensaje_para_el_cliente": "...",
        "consejos_sinergias": ["Pair plant iron with vitamin C.", "Second tip, not included."],
    }
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert "Add one rep before adding weight." in cuerpo
    assert "Pair plant iron with vitamin C." in cuerpo
    assert "Second tip, not included." not in cuerpo


def test_email_body_tolerates_missing_tips():
    """A minimal/older borrador (no progresion/consejos_sinergias key at
    all) must still render, just without the 👉 lines."""
    borrador_rutina = {"mensaje_para_el_cliente": "..."}
    borrador_dieta = {"mensaje_para_el_cliente": "..."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert "👉" not in cuerpo


def test_email_body_does_not_repeat_the_clients_name_in_the_greeting():
    """Real bug: rutina_reglas.py/dieta_reglas.py each bake their own "Hi
    {name}, " greeting into mensaje_para_el_cliente (by design, so it reads
    naturally shown standalone -- see their own docstrings). Combining both
    messages under this email's own greeting used to open three lines in a
    row with the client's name; this locks in that it no longer does."""
    borrador_rutina = {"mensaje_para_el_cliente": "Hi Ana, here's your routine."}
    borrador_dieta = {"mensaje_para_el_cliente": "Hi Ana, here's your diet."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert cuerpo.count("Hi Ana") == 1


def test_email_body_has_a_labeled_section_per_message():
    """Structure fix alongside the greeting dedup above -- two full
    paragraphs run together read as one wall of text."""
    borrador_rutina = {"mensaje_para_el_cliente": "Hi Ana, here's your routine."}
    borrador_dieta = {"mensaje_para_el_cliente": "Hi Ana, here's your diet."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta)
    assert "Your routine" in cuerpo
    assert "Your diet" in cuerpo


def test_quitar_saludo_strips_a_matching_greeting():
    assert _quitar_saludo("Hi Ana, here's your routine.", "Ana", "en") == "here's your routine."
    assert _quitar_saludo("Hola Ana, aquí tienes tu rutina.", "Ana", "es") == "aquí tienes tu rutina."


def test_quitar_saludo_uses_only_the_first_name():
    assert _quitar_saludo("Hi Ana, here's your routine.", "Ana García", "en") == "here's your routine."


def test_quitar_saludo_leaves_message_untouched_if_greeting_does_not_match():
    """Defensive: a hand-edited or unexpected message shouldn't get silently
    mangled just because it doesn't start with the exact expected prefix."""
    mensaje = "Coach's note: keep it light this week."
    assert _quitar_saludo(mensaje, "Ana", "en") == mensaje


def test_email_body_wrapper_text_translates_for_spanish():
    """idioma="es" only needs to translate this template's own wrapper text
    (greeting, attachment list, footer) -- mensaje_para_el_cliente is
    already in whichever language it was generated in (see
    rutina_reglas.py/dieta_reglas.py), so this test uses Spanish content for
    it too, matching a real idioma="es" pipeline run."""
    borrador_rutina = {"mensaje_para_el_cliente": "Hola Ana, aquí tienes tu rutina."}
    borrador_dieta = {"mensaje_para_el_cliente": "Hola Ana, aquí tienes tu dieta."}
    cuerpo = _construir_cuerpo_email("Ana", borrador_rutina, borrador_dieta, idioma="es", incluir_checklist=True)
    assert cuerpo.startswith("Hola Ana,")
    assert "aquí tienes tu rutina" in cuerpo
    assert "responde a este email" in cuerpo.lower()


def test_scopes_include_send_for_the_portal_link_exception():
    """gmail.send is the one deliberate exception to draft-only (see the
    module docstring's DESIGN note) -- locks in that it's actually
    requested, since without it enviar_enlace_portal() would fail with a
    confusing 403 instead of the clear "needs re-authorization" story."""
    assert "https://www.googleapis.com/auth/gmail.send" in SCOPES


def test_portal_email_body_contains_only_the_link_as_variable_content():
    """The one function in this module allowed to actually send (see the
    module docstring) uses a fixed template with exactly one variable
    slot -- the link itself, never free text a trainer or client could
    inject content into."""
    cuerpo = _construir_cuerpo_portal("Ana", "https://trainfitter.streamlit.app/?portal_token=abc.def")
    assert "https://trainfitter.streamlit.app/?portal_token=abc.def" in cuerpo
    assert "Ana" in cuerpo


def test_portal_email_body_wrapper_text_translates_for_spanish():
    cuerpo = _construir_cuerpo_portal("Ana", "https://example.com/?portal_token=abc.def", idioma="es")
    assert cuerpo.startswith("Hola Ana,")
    assert "https://example.com/?portal_token=abc.def" in cuerpo


def test_intake_form_email_body_has_no_variable_content():
    """The narrowest of the three gmail.send-capable templates (see the
    module docstring): not even a name, since nothing about the prospect
    is known yet at this point in the funnel."""
    cuerpo = _construir_cuerpo_formulario_intake()
    assert "reply" in cuerpo.lower()
    assert "attach" in cuerpo.lower()


def test_intake_form_email_body_translates_for_spanish():
    cuerpo = _construir_cuerpo_formulario_intake(idioma="es")
    assert "responde a este email" in cuerpo.lower()


def test_checkin_notification_body_includes_summary_and_suggestion():
    """This is the *trainer's* notification, not the client's -- it should
    carry the client's name plus whatever resumir_adherencia()/
    sugerencia_seguimiento() already produced, not reimplement either."""
    cuerpo = _construir_cuerpo_notificacion_checkin(
        "Ana", "Routine: 5/3 sessions completed.", "Adherence looks strong -- consider a small progression.",
    )
    assert "Ana" in cuerpo
    assert "Routine: 5/3 sessions completed." in cuerpo
    assert "Adherence looks strong -- consider a small progression." in cuerpo


def test_checkin_notification_body_translates_for_spanish():
    cuerpo = _construir_cuerpo_notificacion_checkin("Ana", "Rutina: 5/3.", "Sugerencia.", idioma="es")
    assert "check-in desde el portal de cliente" in cuerpo
    assert "Rutina: 5/3." in cuerpo


def test_checkin_notification_body_includes_weight_when_given():
    """peso_kg is the one piece of data this email adds on top of what
    resumir_adherencia() already covers -- see
    mcp/notion_connector.py's docstring on why "Weight (kg)" exists."""
    cuerpo = _construir_cuerpo_notificacion_checkin("Ana", "Routine: 5/3.", "Suggestion.", peso_kg=71.5)
    assert "71.5 kg" in cuerpo


def test_checkin_notification_body_omits_weight_when_not_given():
    cuerpo = _construir_cuerpo_notificacion_checkin("Ana", "Routine: 5/3.", "Suggestion.")
    assert "kg" not in cuerpo


def test_checkin_notification_body_includes_weight_trend_when_given():
    cuerpo = _construir_cuerpo_notificacion_checkin(
        "Ana", "Routine: 5/3.", "Suggestion.", tendencia="Weight hasn't trended down over the last 14 days.",
    )
    assert "Weight hasn't trended down over the last 14 days." in cuerpo


def test_checkin_notification_body_omits_weight_trend_when_not_given():
    cuerpo = _construir_cuerpo_notificacion_checkin("Ana", "Routine: 5/3.", "Suggestion.")
    assert "⚠️" not in cuerpo


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


def test_recolectar_adjuntos_pdf_fetches_large_attachments_by_id():
    """Gmail only inlines small attachment data on the message part itself
    (see the other tests above, which pass servicio=None); anything larger
    comes back as just an attachmentId needing a second API call -- this
    was a real, untested branch until a coverage report (pyproject.toml's
    [tool.coverage.run]) surfaced it."""
    from unittest.mock import MagicMock

    parte = {"filename": "adherence-checklist.pdf", "mimeType": "application/pdf", "body": {"attachmentId": "att-1"}}
    servicio = MagicMock()
    contenido_b64 = base64.urlsafe_b64encode(b"%PDF-large-bytes").decode("ascii")
    servicio.users.return_value.messages.return_value.attachments.return_value.get.return_value.execute.return_value = {
        "data": contenido_b64
    }

    resultado = _recolectar_adjuntos_pdf(servicio, "msg-1", parte)

    assert resultado == [("adherence-checklist.pdf", b"%PDF-large-bytes")]
    servicio.users.return_value.messages.return_value.attachments.return_value.get.assert_called_once_with(
        userId="me", messageId="msg-1", id="att-1",
    )


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


def test_extraer_intake_pdf_falls_back_to_field_detection_when_renamed():
    """Same fallback pattern as _extraer_checklist_pdf() above, for the
    intake PDF's own filename-first/form-fields-fallback logic -- was
    only ever exercised indirectly (via buscar_intakes_nuevos()'s network
    tests, which all use the known filename) until a coverage report
    surfaced this branch specifically as untested."""
    from pdf_intake import generar_pdf_intake

    intake_real = generar_pdf_intake(idioma="en")
    parte = {
        "mimeType": "multipart/mixed",
        "parts": [_parte_adjunto("my-renamed-intake.pdf", "application/pdf", intake_real)],
    }
    assert _extraer_intake_pdf(None, "msg-1", parte) == intake_real


def test_extraer_intake_pdf_returns_none_with_no_recognizable_pdf():
    parte = {
        "mimeType": "multipart/mixed",
        "parts": [_parte_adjunto("random.pdf", "application/pdf", b"%PDF-not-an-intake-form")],
    }
    assert _extraer_intake_pdf(None, "msg-1", parte) is None
