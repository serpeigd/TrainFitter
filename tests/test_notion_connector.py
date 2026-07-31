"""Tests for mcp/notion_connector.py's pure logic (page-properties building,
credential validation) — no network, no real Notion workspace needed.
guardar_registro_cliente() itself (the part that actually talks to the
Notion API) is intentionally not covered here: it requires a real, shared
database, same reasoning as motor="llm" and the Gmail draft creation never
being exercised against their real APIs in this suite (see
docs/decisiones.md)."""

import pytest
from notion_connector import (
    NotionClientError,
    _construir_propiedades_checkin,
    _construir_propiedades_pagina,
    _construir_resumen,
    _credenciales,
    actualizar_email_cliente,
    crear_registro_checkin,
    existe_checkin_para_mensaje,
    marcar_email_enviado,
)


@pytest.fixture
def borrador_rutina():
    return {"resumen_enfoque": "'upper lower' split for intermediate level."}


@pytest.fixture
def borrador_dieta():
    return {
        "resumen_enfoque": "Estimated 2125 kcal/day.",
        "calorias_objetivo_kcal": 2125,
        "macros": {"proteina_g": 136},
    }


def test_summary_combines_routine_and_diet(borrador_rutina, borrador_dieta):
    resumen = _construir_resumen(borrador_rutina, borrador_dieta)
    assert "upper lower" in resumen
    assert "2125 kcal/day" in resumen
    assert "136 g protein" in resumen


def test_summary_is_truncated_to_notion_rich_text_limit(borrador_rutina):
    borrador_dieta_largo = {
        "resumen_enfoque": "x" * 3000,
        "calorias_objetivo_kcal": 2000,
        "macros": {"proteina_g": 100},
    }
    resumen = _construir_resumen(borrador_rutina, borrador_dieta_largo)
    assert len(resumen) == 2000


def test_page_properties_match_the_documented_database_schema(perfil_base, borrador_rutina, borrador_dieta):
    perfil_base["datos_basicos"]["nombre"] = "Ana Test"
    perfil_base["objetivo"]["principal"] = "hipertrofia"
    perfil_base["experiencia"]["nivel"] = "intermedio"
    perfil_base["fecha_admision"] = "2026-01-15"
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}

    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)

    assert set(propiedades) == {"Name", "Date", "Goal", "Level", "Verdict", "Summary", "Email Sent"}
    assert propiedades["Name"]["title"][0]["text"]["content"] == "Ana Test"
    assert propiedades["Date"]["date"]["start"] == "2026-01-15"
    assert propiedades["Goal"]["select"]["name"] == "Hypertrophy"
    assert propiedades["Level"]["select"]["name"] == "Intermediate"
    assert propiedades["Verdict"]["select"]["name"] == "Approved"
    # New records always start unsent -- "Email Sent" is a manual follow-up
    # flag the trainer ticks themselves in Notion after actually sending the
    # Gmail draft (see the module docstring for why this isn't automated).
    assert propiedades["Email Sent"]["checkbox"] is False


def test_enhanced_review_verdict_label(perfil_base, borrador_rutina, borrador_dieta):
    veredicto = {"veredicto": "revision_reforzada", "motivos": ["some reason"]}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    assert propiedades["Verdict"]["select"]["name"] == "Enhanced review"


def test_missing_credentials_raises_clear_error(monkeypatch, tmp_path):
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    # Point at an empty directory so a real local .env (if the trainer has
    # since set up real Notion credentials for actual use) can't leak into
    # this test and make it flaky depending on the machine it runs on.
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        _credenciales()


def test_actualizar_email_missing_credentials_raises(monkeypatch, tmp_path):
    """actualizar_email_cliente() backfills the client's email onto an
    already-created record once a Gmail draft is made (see
    docs/decisiones.md) -- same credential-checking path as
    guardar_registro_cliente(), so it fails the same clean way when unset."""
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        actualizar_email_cliente("some-page-id", "client@example.com")


def test_marcar_email_enviado_missing_credentials_raises(monkeypatch, tmp_path):
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        marcar_email_enviado("some-page-id")


def test_crear_registro_checkin_missing_credentials_raises(monkeypatch, tmp_path):
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.delenv("NOTION_CHECKINS_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        crear_registro_checkin("client@example.com", "Ana Test", "Plan sent", "2026-07-30")


def test_checkin_properties_include_optional_rating_and_message_id():
    propiedades = _construir_propiedades_checkin(
        "client@example.com", "Ana Test", "Adherence check-in", "2026-07-30",
        notas="Skipped one session.", valoracion="Medium", id_mensaje="msg-123",
    )
    assert propiedades["Type"]["select"]["name"] == "Adherence check-in"
    assert propiedades["Adherence notes"]["rich_text"][0]["text"]["content"] == "Skipped one session."
    assert propiedades["Adherence rating"]["select"]["name"] == "Medium"
    assert propiedades["Source message ID"]["rich_text"][0]["text"]["content"] == "msg-123"


def test_checkin_properties_omit_optional_fields_when_not_given():
    propiedades = _construir_propiedades_checkin("client@example.com", "Ana Test", "Plan sent", "2026-07-30")
    assert "Adherence notes" not in propiedades
    assert "Adherence rating" not in propiedades
    assert "Source message ID" not in propiedades


def test_crear_registro_checkin_missing_checkins_database_id_raises(monkeypatch, tmp_path):
    """Same credentials-before-import ordering as every other network call in
    this module (see docs/decisiones.md's CI-caught bug): a set
    NOTION_API_KEY/NOTION_DATABASE_ID but missing NOTION_CHECKINS_DATABASE_ID
    should fail with a clear NotionClientError, not a bare
    ModuleNotFoundError if notion-client isn't installed either."""
    import notion_connector

    monkeypatch.setenv("NOTION_API_KEY", "fake-key")
    monkeypatch.setenv("NOTION_DATABASE_ID", "fake-database-id")
    monkeypatch.delenv("NOTION_CHECKINS_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        crear_registro_checkin("client@example.com", "Ana Test", "Plan sent", "2026-07-30")


def test_existe_checkin_missing_credentials_raises(monkeypatch, tmp_path):
    """Same credential-checking path as crear_registro_checkin() -- main.py
    calls this first, before creating any new row, so it needs to fail the
    same clean way when Notion isn't configured."""
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.delenv("NOTION_CHECKINS_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        existe_checkin_para_mensaje("msg-123")
