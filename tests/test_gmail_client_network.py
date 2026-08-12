"""Tests for mcp/gmail_client.py's network-touching functions
(crear_borrador, verificar_envio, buscar_respuestas_adherencia), using a
mocked googleapiclient service -- no real credentials, no real network,
but real coverage of the request-building and response-handling logic
that tests/test_gmail_client.py's pure-logic-only tests don't reach.
_obtener_credenciales() is monkeypatched to skip the real OAuth flow
entirely; everything downstream of it (message building, PDF generation,
response parsing) runs for real against the mock."""

import base64
from email import message_from_bytes
from unittest.mock import MagicMock

import gmail_client
import pytest
from gmail_client import GmailClientError
from googleapiclient.errors import HttpError


class _FakeResp:
    def __init__(self, status):
        self.status = status
        self.reason = "error"


def _mock_service(monkeypatch):
    """Patches googleapiclient.discovery.build to return a MagicMock
    service (so a test can configure exactly what each chained call
    returns) and _obtener_credenciales to skip the real OAuth flow."""
    monkeypatch.setattr(gmail_client, "_obtener_credenciales", lambda: object())
    servicio = MagicMock()
    monkeypatch.setattr("googleapiclient.discovery.build", lambda *a, **k: servicio)
    return servicio


@pytest.fixture
def borrador_rutina():
    return {
        "sesiones": [{"dia": "Day 1 — Upper A"}, {"dia": "Day 2 — Lower A"}],
        "mensaje_para_el_cliente": "Hi Ana, here's your routine.",
    }


@pytest.fixture
def borrador_dieta():
    return {
        "calorias_objetivo_kcal": 2000,
        "macros": {"proteina_g": 120, "grasa_g": 60, "carbohidratos_g": 200},
        "mensaje_para_el_cliente": "Hi Ana, here's your diet.",
        "distribucion_comidas": "Spread across 4 meals.",
        "fuentes_proteina_sugeridas": ["Chicken breast"],
        "fuentes_carbohidrato_sugeridas": ["Rice"],
        "fuentes_grasa_sugeridas": ["Olive oil"],
        "consejos_sinergias": [],
    }


# --- crear_borrador() -------------------------------------------------------


def test_crear_borrador_returns_url_and_thread_id(monkeypatch, borrador_rutina, borrador_dieta):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
        "message": {"id": "draft-1", "threadId": "thread-1"}
    }
    resultado = gmail_client.crear_borrador("client@example.com", "Ana", borrador_rutina, borrador_dieta)
    assert resultado == {"url": "https://mail.google.com/mail/u/0/#drafts/draft-1", "thread_id": "thread-1"}


def test_crear_borrador_sends_the_routine_and_diet_pdfs_by_default(monkeypatch, borrador_rutina, borrador_dieta):
    """Confirms the actual request body crear_borrador() builds really
    does carry both plan PDFs (routine now always attached alongside
    diet, mirroring it -- see generar_pdf_rutina()) and, by default,
    NOT the checklist (opt-in now, see crear_borrador()'s docstring) --
    exercises the full path from the PDF generators through
    _construir_mensaje_raw() to what would be sent to the real API."""
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
        "message": {"id": "draft-1", "threadId": "thread-1"}
    }
    gmail_client.crear_borrador("client@example.com", "Ana", borrador_rutina, borrador_dieta)

    _args, kwargs = servicio.users.return_value.drafts.return_value.create.call_args
    raw = base64.urlsafe_b64decode(kwargs["body"]["message"]["raw"].encode("utf-8"))
    mensaje = message_from_bytes(raw)
    partes = mensaje.get_payload()
    nombres_adjuntos = {p.get_filename() for p in partes[1:]}
    assert nombres_adjuntos == {"routine-plan.pdf", "diet-plan.pdf"}
    assert all(p.get_content_type() == "application/pdf" for p in partes[1:])


def test_crear_borrador_attaches_the_checklist_when_requested(monkeypatch, borrador_rutina, borrador_dieta):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.drafts.return_value.create.return_value.execute.return_value = {
        "message": {"id": "draft-1", "threadId": "thread-1"}
    }
    gmail_client.crear_borrador(
        "client@example.com", "Ana", borrador_rutina, borrador_dieta, incluir_checklist=True,
    )

    _args, kwargs = servicio.users.return_value.drafts.return_value.create.call_args
    raw = base64.urlsafe_b64decode(kwargs["body"]["message"]["raw"].encode("utf-8"))
    mensaje = message_from_bytes(raw)
    partes = mensaje.get_payload()
    nombres_adjuntos = {p.get_filename() for p in partes[1:]}
    assert nombres_adjuntos == {"routine-plan.pdf", "diet-plan.pdf", "adherence-checklist.pdf"}


def test_crear_borrador_wraps_http_error(monkeypatch, borrador_rutina, borrador_dieta):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.drafts.return_value.create.return_value.execute.side_effect = HttpError(
        _FakeResp(500), b"server error"
    )
    with pytest.raises(GmailClientError):
        gmail_client.crear_borrador("client@example.com", "Ana", borrador_rutina, borrador_dieta)


# --- enviar_enlace_portal() --------------------------------------------------


def test_enviar_enlace_portal_sends_not_drafts(monkeypatch):
    """One of only two functions in this module allowed to call
    messages().send() rather than drafts().create() -- see the module
    docstring's DESIGN notes on gmail.send. Getting this wrong would mean
    a "portal link" email quietly sits as an unsent draft again, defeating
    the point."""
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "msg-1"}

    gmail_client.enviar_enlace_portal("client@example.com", "Ana", "https://trainfitter.streamlit.app/?portal_token=abc.def")

    servicio.users.return_value.messages.return_value.send.assert_called_once()
    servicio.users.return_value.drafts.return_value.create.assert_not_called()

    _args, kwargs = servicio.users.return_value.messages.return_value.send.call_args
    # send()'s body is {"raw": ...} directly -- not wrapped in an outer
    # "message" key the way drafts().create()'s is.
    assert "raw" in kwargs["body"]
    raw = base64.urlsafe_b64decode(kwargs["body"]["raw"].encode("utf-8"))
    mensaje = message_from_bytes(raw)
    assert mensaje["to"] == "client@example.com"
    assert "portal_token=abc.def" in mensaje.get_payload(decode=True).decode("utf-8")


def test_enviar_enlace_portal_wraps_http_error(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
        _FakeResp(500), b"server error"
    )
    with pytest.raises(GmailClientError):
        gmail_client.enviar_enlace_portal("client@example.com", "Ana", "https://example.com/?portal_token=abc.def")


# --- enviar_notificacion_checkin() -------------------------------------------


@pytest.fixture
def datos_checkin():
    return {
        "dias_rutina_completados": 5,
        "dias_rutina_totales": 3,
        "notas_rutina": "Felt great, added an extra session.",
        "dias_dieta_seguidos": 6,
        "dias_dieta_totales": 7,
        "notas_dieta": "",
    }


def test_enviar_notificacion_checkin_sends_not_drafts(monkeypatch, datos_checkin):
    """The other of the two functions allowed to call messages().send()
    -- this one mails the trainer's own inbox, never a client, which is
    exactly why it's allowed to fire automatically with no button (see
    the module docstring's DESIGN note)."""
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "msg-1"}

    gmail_client.enviar_notificacion_checkin("trainer@example.com", "Ana", datos_checkin, "High")

    servicio.users.return_value.messages.return_value.send.assert_called_once()
    servicio.users.return_value.drafts.return_value.create.assert_not_called()

    _args, kwargs = servicio.users.return_value.messages.return_value.send.call_args
    raw = base64.urlsafe_b64decode(kwargs["body"]["raw"].encode("utf-8"))
    mensaje = message_from_bytes(raw)
    assert mensaje["to"] == "trainer@example.com"
    assert "Ana" in mensaje["subject"]
    cuerpo_texto = mensaje.get_payload(decode=True).decode("utf-8")
    assert "5/3 sessions completed" in cuerpo_texto
    assert "progression" in cuerpo_texto.lower()  # sugerencia_seguimiento("High")


def test_enviar_notificacion_checkin_wraps_http_error(monkeypatch, datos_checkin):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
        _FakeResp(500), b"server error"
    )
    with pytest.raises(GmailClientError):
        gmail_client.enviar_notificacion_checkin("trainer@example.com", "Ana", datos_checkin, "High")


# --- verificar_envio() -------------------------------------------------------


def test_verificar_envio_true_when_sent_label_present(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.threads.return_value.get.return_value.execute.return_value = {
        "messages": [{"labelIds": ["INBOX"]}, {"labelIds": ["SENT"]}]
    }
    assert gmail_client.verificar_envio("thread-1") is True


def test_verificar_envio_false_when_no_sent_label(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.threads.return_value.get.return_value.execute.return_value = {
        "messages": [{"labelIds": ["DRAFT"]}]
    }
    assert gmail_client.verificar_envio("thread-1") is False


def test_verificar_envio_false_on_404_not_found(monkeypatch):
    """A deleted thread shouldn't raise -- verificar_envio() treats "not
    found" as "not sent yet", not an error."""
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.threads.return_value.get.return_value.execute.side_effect = HttpError(
        _FakeResp(404), b"not found"
    )
    assert gmail_client.verificar_envio("thread-1") is False


def test_verificar_envio_wraps_other_http_errors(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.threads.return_value.get.return_value.execute.side_effect = HttpError(
        _FakeResp(500), b"server error"
    )
    with pytest.raises(GmailClientError):
        gmail_client.verificar_envio("thread-1")


# --- buscar_respuestas_adherencia() -----------------------------------------


def _mensaje_gmail(headers, mimetype="multipart/mixed", parts=None, internal_date="1753900800000"):
    return {
        "id": "msg-1",
        "threadId": "thread-1",
        "internalDate": internal_date,
        "payload": {"headers": headers, "mimeType": mimetype, "parts": parts or []},
    }


def test_buscar_respuestas_adherencia_finds_a_genuine_reply(monkeypatch):
    from pdf_generador import generar_pdf_checklist

    checklist_pdf = generar_pdf_checklist(
        {"sesiones": [{"dia": "Day 1"}]}, {"calorias_objetivo_kcal": 2000, "macros": {"proteina_g": 100}}, "Ana",
    )
    adjunto_b64 = base64.urlsafe_b64encode(checklist_pdf).decode("ascii")

    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg-1"}]
    }
    servicio.users.return_value.messages.return_value.get.return_value.execute.return_value = _mensaje_gmail(
        headers=[
            {"name": "From", "value": "Ana <ana@example.com>"},
            {"name": "In-Reply-To", "value": "<original@mail.gmail.com>"},
        ],
        parts=[{"filename": "adherence-checklist.pdf", "mimeType": "application/pdf", "body": {"data": adjunto_b64}}],
    )

    respuestas = gmail_client.buscar_respuestas_adherencia()
    assert len(respuestas) == 1
    assert respuestas[0]["remitente"] == "ana@example.com"
    assert respuestas[0]["id_mensaje"] == "msg-1"
    assert respuestas[0]["id_hilo"] == "thread-1"
    assert respuestas[0]["contenido"] == checklist_pdf


def test_buscar_respuestas_adherencia_skips_the_original_non_reply_message(monkeypatch):
    """A message with no In-Reply-To header is the trainer's own original
    plan email, not a reply -- must never be misread as adherence data
    (this is the exact bug found live-testing with a self-sent email --
    see docs/decisiones.md)."""
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg-1"}]
    }
    servicio.users.return_value.messages.return_value.get.return_value.execute.return_value = _mensaje_gmail(
        headers=[{"name": "From", "value": "trainer@example.com"}],
        mimetype="text/plain",
    )
    assert gmail_client.buscar_respuestas_adherencia() == []


def test_buscar_respuestas_adherencia_skips_replies_with_no_checklist_pdf(monkeypatch):
    """A genuine reply with no attachment at all (or an unrelated one)
    has nothing parseable in it."""
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg-1"}]
    }
    servicio.users.return_value.messages.return_value.get.return_value.execute.return_value = _mensaje_gmail(
        headers=[
            {"name": "From", "value": "ana@example.com"},
            {"name": "In-Reply-To", "value": "<original@mail.gmail.com>"},
        ],
        mimetype="text/plain",
    )
    assert gmail_client.buscar_respuestas_adherencia() == []


def test_buscar_respuestas_adherencia_wraps_http_error(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.side_effect = HttpError(
        _FakeResp(500), b"server error"
    )
    with pytest.raises(GmailClientError):
        gmail_client.buscar_respuestas_adherencia()


# --- buscar_intakes_nuevos() -------------------------------------------------


def _pdf_intake_relleno(nombre_cliente: str = "Laura Fernandez") -> bytes:
    """Builds a real, filled intake PDF (reportlab to write, pypdf to
    fill) -- used as realistic attachment content in these mocked-Gmail
    tests, same approach test_gmail_client_network.py already uses for
    checklist PDFs."""
    import io

    from pdf_intake import CAMPO_NOMBRE, CAMPO_OBJETIVO, generar_pdf_intake
    from pypdf import PdfWriter

    vacio = generar_pdf_intake(idioma="en")
    writer = PdfWriter()
    writer.append(io.BytesIO(vacio))
    for pagina in writer.pages:
        writer.update_page_form_field_values(
            pagina, {CAMPO_NOMBRE: nombre_cliente, CAMPO_OBJETIVO: "salud_general"}, auto_regenerate=False,
        )
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_buscar_intakes_nuevos_finds_a_genuine_submission(monkeypatch):
    intake_pdf = _pdf_intake_relleno()
    adjunto_b64 = base64.urlsafe_b64encode(intake_pdf).decode("ascii")

    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg-1"}]
    }
    servicio.users.return_value.messages.return_value.get.return_value.execute.return_value = _mensaje_gmail(
        headers=[{"name": "From", "value": "Laura <laura@example.com>"}],
        parts=[{"filename": "trainfitter-intake-form.pdf", "mimeType": "application/pdf", "body": {"data": adjunto_b64}}],
    )

    intakes = gmail_client.buscar_intakes_nuevos()
    assert len(intakes) == 1
    assert intakes[0]["remitente"] == "laura@example.com"
    assert intakes[0]["id_mensaje"] == "msg-1"
    assert intakes[0]["perfil"]["datos_basicos"]["nombre"] == "Laura Fernandez"
    assert intakes[0]["perfil"]["objetivo"]["principal"] == "salud_general"


def test_buscar_intakes_nuevos_skips_a_blank_template(monkeypatch):
    """A blank intake form has all our expected form fields (so
    es_intake_pdf() matches) but no name -- e.g. the trainer's own copy
    sitting in Sent after emailing it to a prospect. Must never be
    mistaken for a genuine submission."""
    from pdf_intake import generar_pdf_intake

    blank_pdf = generar_pdf_intake(idioma="en")
    adjunto_b64 = base64.urlsafe_b64encode(blank_pdf).decode("ascii")

    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg-1"}]
    }
    servicio.users.return_value.messages.return_value.get.return_value.execute.return_value = _mensaje_gmail(
        headers=[{"name": "From", "value": "trainer@example.com"}],
        parts=[{"filename": "trainfitter-intake-form.pdf", "mimeType": "application/pdf", "body": {"data": adjunto_b64}}],
    )

    assert gmail_client.buscar_intakes_nuevos() == []


def test_buscar_intakes_nuevos_skips_messages_with_no_intake_pdf(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "msg-1"}]
    }
    servicio.users.return_value.messages.return_value.get.return_value.execute.return_value = _mensaje_gmail(
        headers=[{"name": "From", "value": "someone@example.com"}],
        mimetype="text/plain",
    )
    assert gmail_client.buscar_intakes_nuevos() == []


def test_buscar_intakes_nuevos_wraps_http_error(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.side_effect = HttpError(
        _FakeResp(500), b"server error"
    )
    with pytest.raises(GmailClientError):
        gmail_client.buscar_intakes_nuevos()


def test_buscar_intakes_nuevos_narrows_the_query_when_remitente_given(monkeypatch):
    """ui/app.py's "check for a reply" button passes a specific prospect's
    email -- confirms that actually reaches Gmail's search query (a
    `from:` qualifier) instead of silently scanning the whole inbox."""
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.return_value = {"messages": []}

    gmail_client.buscar_intakes_nuevos(remitente="laura@example.com")

    _args, kwargs = servicio.users.return_value.messages.return_value.list.call_args
    assert "laura@example.com" in kwargs["q"]


def test_buscar_intakes_nuevos_without_remitente_scans_the_whole_inbox(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.list.return_value.execute.return_value = {"messages": []}

    gmail_client.buscar_intakes_nuevos()

    _args, kwargs = servicio.users.return_value.messages.return_value.list.call_args
    assert "from:" not in kwargs["q"]


# --- enviar_formulario_intake() ----------------------------------------------


def test_enviar_formulario_intake_sends_not_drafts(monkeypatch):
    """The third (and, as of now, last) function allowed to call
    messages().send() -- see the module docstring's DESIGN notes."""
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "msg-1"}

    gmail_client.enviar_formulario_intake("prospect@example.com")

    servicio.users.return_value.messages.return_value.send.assert_called_once()
    servicio.users.return_value.drafts.return_value.create.assert_not_called()

    _args, kwargs = servicio.users.return_value.messages.return_value.send.call_args
    raw = base64.urlsafe_b64decode(kwargs["body"]["raw"].encode("utf-8"))
    mensaje = message_from_bytes(raw)
    assert mensaje["to"] == "prospect@example.com"
    partes = mensaje.get_payload()
    nombres_adjuntos = {p.get_filename() for p in partes[1:]}
    assert nombres_adjuntos == {"trainfitter-intake-form.pdf"}


def test_enviar_formulario_intake_attaches_the_spanish_filename_for_es(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "msg-1"}

    gmail_client.enviar_formulario_intake("prospect@example.com", idioma="es")

    _args, kwargs = servicio.users.return_value.messages.return_value.send.call_args
    raw = base64.urlsafe_b64decode(kwargs["body"]["raw"].encode("utf-8"))
    mensaje = message_from_bytes(raw)
    partes = mensaje.get_payload()
    nombres_adjuntos = {p.get_filename() for p in partes[1:]}
    assert nombres_adjuntos == {"formulario-inscripcion-trainfitter.pdf"}


def test_enviar_formulario_intake_wraps_http_error(monkeypatch):
    servicio = _mock_service(monkeypatch)
    servicio.users.return_value.messages.return_value.send.return_value.execute.side_effect = HttpError(
        _FakeResp(500), b"server error"
    )
    with pytest.raises(GmailClientError):
        gmail_client.enviar_formulario_intake("prospect@example.com")
