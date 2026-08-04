"""Tests for mcp/notion_connector.py's network-touching functions, using a
mocked notion_client.Client -- no real credentials, no real workspace, but
real coverage of the request-building and response-handling logic that
tests/test_notion_connector.py's pure-logic-only tests don't reach."""

from unittest.mock import MagicMock

import httpx
import notion_connector
import pytest
from notion_client.errors import APIErrorCode, APIResponseError
from notion_connector import NotionClientError


def _api_error(message="error"):
    return APIResponseError(
        code=APIErrorCode.InternalServerError, status=500, message=message, headers=httpx.Headers({}), raw_body_text="{}",
    )


def _mock_client(monkeypatch):
    """Sets real-looking Notion env vars (never touches an actual
    workspace -- notion_client.Client itself is replaced below) and
    patches notion_client.Client to return a MagicMock, so a test can
    configure exactly what each call returns. Also clears the
    data-source-id cache so tests don't leak state into each other."""
    monkeypatch.setenv("NOTION_API_KEY", "fake-key")
    monkeypatch.setenv("NOTION_DATABASE_ID", "fake-database-id")
    monkeypatch.setenv("NOTION_CHECKINS_DATABASE_ID", "fake-checkins-database-id")
    notion_connector._CACHE_FUENTE_DATOS.clear()
    cliente = MagicMock()
    monkeypatch.setattr("notion_client.Client", lambda auth: cliente)
    return cliente


# --- guardar_registro_cliente() ---------------------------------------------


def test_guardar_registro_cliente_returns_id_and_url(monkeypatch, perfil_base):
    cliente = _mock_client(monkeypatch)
    cliente.pages.create.return_value = {"id": "page-1", "url": "https://notion.so/page-1"}
    borrador_rutina = {"resumen_enfoque": "..."}
    borrador_dieta = {"resumen_enfoque": "...", "calorias_objetivo_kcal": 2000, "macros": {"proteina_g": 100}}
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}

    resultado = notion_connector.guardar_registro_cliente(perfil_base, borrador_rutina, borrador_dieta, veredicto)

    assert resultado == {"id": "page-1", "url": "https://notion.so/page-1"}
    _args, kwargs = cliente.pages.create.call_args
    assert kwargs["parent"] == {"database_id": "fake-database-id"}


def test_guardar_registro_cliente_wraps_api_error(monkeypatch, perfil_base):
    cliente = _mock_client(monkeypatch)
    cliente.pages.create.side_effect = _api_error()
    borrador_rutina = {"resumen_enfoque": "..."}
    borrador_dieta = {"resumen_enfoque": "...", "calorias_objetivo_kcal": 2000, "macros": {"proteina_g": 100}}
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}

    with pytest.raises(NotionClientError):
        notion_connector.guardar_registro_cliente(perfil_base, borrador_rutina, borrador_dieta, veredicto)


# --- actualizar_email_cliente() / marcar_email_enviado() -------------------


def test_actualizar_email_cliente_updates_the_email_property(monkeypatch):
    cliente = _mock_client(monkeypatch)
    notion_connector.actualizar_email_cliente("page-1", "client@example.com")
    cliente.pages.update.assert_called_once_with(
        page_id="page-1", properties={"Email": {"email": "client@example.com"}}
    )


def test_actualizar_email_cliente_wraps_api_error(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.pages.update.side_effect = _api_error()
    with pytest.raises(NotionClientError):
        notion_connector.actualizar_email_cliente("page-1", "client@example.com")


def test_marcar_email_enviado_checks_the_box(monkeypatch):
    cliente = _mock_client(monkeypatch)
    notion_connector.marcar_email_enviado("page-1")
    cliente.pages.update.assert_called_once_with(page_id="page-1", properties={"Email Sent": {"checkbox": True}})


# --- crear_registro_checkin() -----------------------------------------------


def test_crear_registro_checkin_returns_id_and_url(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.pages.create.return_value = {"id": "checkin-1", "url": "https://notion.so/checkin-1"}

    resultado = notion_connector.crear_registro_checkin(
        "client@example.com", "Ana", "Adherence check-in", "2026-07-30", notas="Skipped one session.", valoracion="Medium",
    )

    assert resultado == {"id": "checkin-1", "url": "https://notion.so/checkin-1"}
    _args, kwargs = cliente.pages.create.call_args
    assert kwargs["parent"] == {"database_id": "fake-checkins-database-id"}
    assert kwargs["properties"]["Adherence rating"]["select"]["name"] == "Medium"


def test_crear_registro_checkin_wraps_api_error(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.pages.create.side_effect = _api_error()
    with pytest.raises(NotionClientError):
        notion_connector.crear_registro_checkin("client@example.com", "Ana", "Plan sent", "2026-07-30")


# --- existe_checkin_para_mensaje() / _id_fuente_datos() caching ------------


def test_existe_checkin_true_when_a_result_is_found(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.databases.retrieve.return_value = {"data_sources": [{"id": "ds-1"}]}
    cliente.data_sources.query.return_value = {"results": [{"id": "page-1"}]}

    assert notion_connector.existe_checkin_para_mensaje("msg-1") is True
    cliente.data_sources.query.assert_called_once_with(
        data_source_id="ds-1",
        filter={"property": "Source message ID", "rich_text": {"equals": "msg-1"}},
    )


def test_existe_checkin_false_when_no_results(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.databases.retrieve.return_value = {"data_sources": [{"id": "ds-1"}]}
    cliente.data_sources.query.return_value = {"results": []}

    assert notion_connector.existe_checkin_para_mensaje("msg-1") is False


def test_existe_checkin_wraps_api_error(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.databases.retrieve.side_effect = _api_error()
    with pytest.raises(NotionClientError):
        notion_connector.existe_checkin_para_mensaje("msg-1")


def test_data_source_id_is_cached_across_calls(monkeypatch):
    """databases.retrieve() should only be called once even across two
    separate lookups against the same database -- see
    _id_fuente_datos()/_CACHE_FUENTE_DATOS. main.py calls
    existe_checkin_para_mensaje() once per candidate reply found in the
    inbox; without caching, a busy run would re-fetch the same data
    source id every single time."""
    cliente = _mock_client(monkeypatch)
    cliente.databases.retrieve.return_value = {"data_sources": [{"id": "ds-1"}]}
    cliente.data_sources.query.return_value = {"results": []}

    notion_connector.existe_checkin_para_mensaje("msg-1")
    notion_connector.existe_checkin_para_mensaje("msg-2")

    assert cliente.databases.retrieve.call_count == 1
    assert cliente.data_sources.query.call_count == 2


# --- historial_checkins() ---------------------------------------------------


def test_historial_checkins_returns_rows_most_recent_first(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.databases.retrieve.return_value = {"data_sources": [{"id": "ds-1"}]}
    cliente.data_sources.query.return_value = {
        "results": [
            {
                "properties": {
                    "Date": {"date": {"start": "2026-07-28"}},
                    "Type": {"select": {"name": "Adherence check-in"}},
                    "Adherence rating": {"select": {"name": "Medium"}},
                    "Adherence notes": {"rich_text": [{"plain_text": "Skipped one session."}]},
                }
            },
        ]
    }

    historial = notion_connector.historial_checkins("client@example.com")

    assert historial == [
        {"fecha": "2026-07-28", "tipo": "Adherence check-in", "valoracion": "Medium", "notas": "Skipped one session."}
    ]
    cliente.data_sources.query.assert_called_once_with(
        data_source_id="ds-1",
        filter={"property": "Email", "email": {"equals": "client@example.com"}},
        sorts=[{"property": "Date", "direction": "descending"}],
    )


def test_historial_checkins_empty_for_a_client_with_no_rows(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.databases.retrieve.return_value = {"data_sources": [{"id": "ds-1"}]}
    cliente.data_sources.query.return_value = {"results": []}

    assert notion_connector.historial_checkins("new-client@example.com") == []


def test_historial_checkins_wraps_api_error(monkeypatch):
    cliente = _mock_client(monkeypatch)
    cliente.databases.retrieve.side_effect = _api_error()
    with pytest.raises(NotionClientError):
        notion_connector.historial_checkins("client@example.com")
