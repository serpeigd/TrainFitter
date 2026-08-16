"""Tests for mcp/notion_connector.py's pure logic (page-properties building,
credential validation) — no network, no real Notion workspace needed. The
network-touching functions themselves (guardar_registro_cliente(),
crear_registro_checkin(), historial_checkins(), etc.) are covered
separately in test_notion_connector_network.py, against a mocked
notion_client.Client rather than a real, shared workspace."""

import json

import pytest
from notion_connector import (
    NotionClientError,
    _construir_propiedades_checkin,
    _construir_propiedades_pagina,
    _construir_resumen,
    _credenciales,
    _dividir_bloques_notion,
    _fila_checkin_desde_pagina,
    _fila_cliente_lista_desde_pagina,
    _fila_registro_cliente_desde_pagina,
    _perfil_desde_propiedades,
    _unir_bloques_notion,
    actualizar_email_cliente,
    actualizar_registro_cliente,
    buscar_cliente_por_email,
    crear_registro_checkin,
    existe_checkin_para_mensaje,
    historial_checkins,
    listar_clientes,
    marcar_email_enviado,
    obtener_perfil_completo,
    obtener_registro_cliente,
    ultimo_checkin_por_cliente,
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

    assert set(propiedades) == {
        "Name", "Date", "Goal", "Level", "Verdict", "Summary", "Language", "Email Sent",
        "Full Profile (JSON)", "Weekly Meal Plan (JSON)", "Weekly Routine (JSON)",
        "Routine Message", "Diet Message",
    }
    assert propiedades["Name"]["title"][0]["text"]["content"] == "Ana Test"
    assert propiedades["Date"]["date"]["start"] == "2026-01-15"
    assert propiedades["Goal"]["select"]["name"] == "Hypertrophy"
    assert propiedades["Level"]["select"]["name"] == "Intermediate"
    assert propiedades["Verdict"]["select"]["name"] == "Approved"
    # Defaults to "en", matching every other idioma default in this project.
    assert propiedades["Language"]["select"]["name"] == "en"
    # New records always start unsent -- "Email Sent" is a manual follow-up
    # flag the trainer ticks themselves in Notion after actually sending the
    # Gmail draft (see the module docstring for why this isn't automated).
    assert propiedades["Email Sent"]["checkbox"] is False


def test_page_properties_use_the_given_language(perfil_base, borrador_rutina, borrador_dieta):
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto, idioma="es")
    assert propiedades["Language"]["select"]["name"] == "es"


def test_page_properties_save_the_concrete_tip_per_section(perfil_base, borrador_dieta):
    """The client portal now shows the same minimal, concrete content the
    plan email does (real feedback: bulleting the whole generic message
    still read as "MUY generales") -- a real tip (progresion/
    consejos_sinergias) takes priority over mensaje_para_el_cliente when
    one exists. See this module's "Routine Message"/"Diet Message"
    DESIGN note."""
    borrador_rutina = {
        "resumen_enfoque": "...",
        "mensaje_para_el_cliente": "Hi Test, here's your generic routine note.",
        "progresion": "Add one rep before adding weight.",
    }
    borrador_dieta["mensaje_para_el_cliente"] = "Hi Test, here's your generic diet note."
    borrador_dieta["consejos_sinergias"] = ["Pair plant iron with vitamin C."]
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    assert propiedades["Routine Message"]["rich_text"][0]["text"]["content"] == "Add one rep before adding weight."
    assert propiedades["Diet Message"]["rich_text"][0]["text"]["content"] == "Pair plant iron with vitamin C."


def test_page_properties_fall_back_to_the_message_when_no_tip_exists(perfil_base, borrador_dieta):
    """A "normal"/"basico" diet has no consejos_sinergias at all (synergy
    tips are gated to avanzado+) -- falls back to the message's own
    first, greeting-stripped sentence rather than saving nothing."""
    borrador_rutina = {
        "resumen_enfoque": "...",
        "mensaje_para_el_cliente": "Hi Test, first sentence. Second sentence.",
    }
    borrador_dieta["mensaje_para_el_cliente"] = "Hi Test, diet first sentence. Diet second sentence."
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    assert propiedades["Routine Message"]["rich_text"][0]["text"]["content"] == "First sentence."
    assert propiedades["Diet Message"]["rich_text"][0]["text"]["content"] == "Diet first sentence."


def test_page_properties_message_defaults_to_empty_string_when_missing(perfil_base, borrador_rutina, borrador_dieta):
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    assert propiedades["Routine Message"]["rich_text"][0]["text"]["content"] == ""
    assert propiedades["Diet Message"]["rich_text"][0]["text"]["content"] == ""


def test_page_properties_full_profile_round_trips_through_json(perfil_base, borrador_rutina, borrador_dieta):
    """The whole point of "Full Profile (JSON)" -- see
    ui/app.py's "Revise client" section -- is getting perfil_cliente back
    out exactly as it went in. Simulates the request -> real API response
    shape change (_unir_bloques_notion() reads "plain_text", a request
    body has "text" -- see that function's docstring)."""
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)

    propiedad_respuesta = {
        "rich_text": [{"plain_text": b["text"]["content"]} for b in propiedades["Full Profile (JSON)"]["rich_text"]]
    }
    guardado = json.loads(_unir_bloques_notion(propiedad_respuesta))
    assert guardado == perfil_base


def test_page_properties_include_the_weekly_meal_plan(perfil_base, borrador_rutina, borrador_dieta):
    borrador_dieta["plan_semanal"] = [{"dia": "Monday", "comidas": [{"tipo": "Breakfast"}]}]
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)

    propiedad_respuesta = {
        "rich_text": [
            {"plain_text": b["text"]["content"]} for b in propiedades["Weekly Meal Plan (JSON)"]["rich_text"]
        ]
    }
    guardado = json.loads(_unir_bloques_notion(propiedad_respuesta))
    assert guardado == borrador_dieta["plan_semanal"]


def test_page_properties_weekly_meal_plan_defaults_to_empty_list(perfil_base, borrador_rutina, borrador_dieta):
    assert "plan_semanal" not in borrador_dieta
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    propiedad_respuesta = {
        "rich_text": [
            {"plain_text": b["text"]["content"]} for b in propiedades["Weekly Meal Plan (JSON)"]["rich_text"]
        ]
    }
    assert json.loads(_unir_bloques_notion(propiedad_respuesta)) == []


def test_perfil_desde_propiedades_merges_liked_meals(perfil_base, borrador_rutina, borrador_dieta):
    """Liked Meals (JSON) (client-portal-written) merges into
    perfil["nutricion"]["comidas_favoritas"] with no extra wiring needed
    by ui/app.py's "Revise client" -- both obtener_perfil_completo() and
    buscar_cliente_por_email() share this same reassembly function."""
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    propiedades["Full Profile (JSON)"] = {
        "rich_text": [{"plain_text": b["text"]["content"]} for b in propiedades["Full Profile (JSON)"]["rich_text"]]
    }
    favoritas = [{"tipo": "desayuno", "proteina": "Eggs", "carbohidrato": "Oats", "grasa": None}]
    propiedades["Liked Meals (JSON)"] = {"rich_text": [{"plain_text": json.dumps(favoritas)}]}

    perfil = _perfil_desde_propiedades(propiedades)
    assert perfil["nutricion"]["comidas_favoritas"] == favoritas


def test_perfil_desde_propiedades_without_liked_meals_has_no_key(perfil_base, borrador_rutina, borrador_dieta):
    """A record saved before this property existed (or a client who's
    never liked anything) must load exactly as before -- no crash, no
    invented empty key that could be mistaken for "explicitly no
    favorites" vs. "this feature didn't exist yet"."""
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    propiedades["Full Profile (JSON)"] = {
        "rich_text": [{"plain_text": b["text"]["content"]} for b in propiedades["Full Profile (JSON)"]["rich_text"]]
    }
    perfil = _perfil_desde_propiedades(propiedades)
    assert "comidas_favoritas" not in perfil["nutricion"]


def test_perfil_desde_propiedades_merges_liked_exercises(perfil_base, borrador_rutina, borrador_dieta):
    """Same as test_perfil_desde_propiedades_merges_liked_meals above, for
    the routine side -- Liked Exercises (JSON) merges into
    perfil["experiencia"]["ejercicios_favoritos"]."""
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    propiedades["Full Profile (JSON)"] = {
        "rich_text": [{"plain_text": b["text"]["content"]} for b in propiedades["Full Profile (JSON)"]["rich_text"]]
    }
    favoritos = [{"grupo": "pecho", "tipo": "basico", "nombre": "Barbell Bench Press"}]
    propiedades["Liked Exercises (JSON)"] = {"rich_text": [{"plain_text": json.dumps(favoritos)}]}

    perfil = _perfil_desde_propiedades(propiedades)
    assert perfil["experiencia"]["ejercicios_favoritos"] == favoritos


def test_perfil_desde_propiedades_without_liked_exercises_has_no_key(perfil_base, borrador_rutina, borrador_dieta):
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    propiedades["Full Profile (JSON)"] = {
        "rich_text": [{"plain_text": b["text"]["content"]} for b in propiedades["Full Profile (JSON)"]["rich_text"]]
    }
    perfil = _perfil_desde_propiedades(propiedades)
    assert "ejercicios_favoritos" not in perfil["experiencia"]


def test_dividir_bloques_notion_splits_long_text_under_the_block_limit():
    texto = "x" * 5000
    bloques = _dividir_bloques_notion(texto)
    assert all(len(b["text"]["content"]) <= 2000 for b in bloques)
    assert "".join(b["text"]["content"] for b in bloques) == texto


def test_dividir_bloques_notion_handles_empty_string():
    assert _dividir_bloques_notion("") == [{"text": {"content": ""}}]


def test_unir_bloques_notion_round_trips_with_dividir(perfil_base):
    """Round-trips through the shape a real API response uses
    ("plain_text") rather than the shape a request body uses ("text") --
    _dividir_bloques_notion() builds a request body, so this simulates
    what Notion would hand back for it."""
    texto_original = json.dumps(perfil_base)
    bloques_peticion = _dividir_bloques_notion(texto_original)
    propiedad_respuesta = {
        "rich_text": [{"plain_text": b["text"]["content"]} for b in bloques_peticion]
    }
    assert _unir_bloques_notion(propiedad_respuesta) == texto_original


def test_enhanced_review_verdict_label(perfil_base, borrador_rutina, borrador_dieta):
    veredicto = {"veredicto": "revision_reforzada", "motivos": ["some reason"]}
    propiedades = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    assert propiedades["Verdict"]["select"]["name"] == "Enhanced review"


def test_page_properties_include_source_message_id_only_for_automated_intakes(
    perfil_base, borrador_rutina, borrador_dieta
):
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}

    propiedades_manual = _construir_propiedades_pagina(perfil_base, borrador_rutina, borrador_dieta, veredicto)
    assert "Source message ID" not in propiedades_manual

    propiedades_auto = _construir_propiedades_pagina(
        perfil_base, borrador_rutina, borrador_dieta, veredicto, id_mensaje="msg-123",
    )
    assert propiedades_auto["Source message ID"]["rich_text"][0]["text"]["content"] == "msg-123"


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


def test_actualizar_registro_cliente_missing_credentials_raises(monkeypatch, tmp_path, perfil_base):
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    veredicto = {"veredicto": "aprobado_automatico", "motivos": []}
    with pytest.raises(NotionClientError):
        actualizar_registro_cliente(
            "some-page-id", perfil_base, {"resumen_enfoque": "..."},
            {"resumen_enfoque": "...", "calorias_objetivo_kcal": 2000, "macros": {"proteina_g": 100}}, veredicto,
        )


def test_obtener_perfil_completo_missing_credentials_raises(monkeypatch, tmp_path):
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        obtener_perfil_completo("some-page-id")


def test_buscar_cliente_por_email_missing_credentials_raises(monkeypatch, tmp_path):
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        buscar_cliente_por_email("client@example.com")


def test_listar_clientes_missing_credentials_raises(monkeypatch, tmp_path):
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        listar_clientes()


def test_ultimo_checkin_por_cliente_missing_credentials_raises(monkeypatch, tmp_path):
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        ultimo_checkin_por_cliente()


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
    assert "Weight (kg)" not in propiedades


def test_checkin_properties_include_weight_when_given():
    """Only the portal's check-in form ever sets peso_kg -- see this
    module's docstring on why "Weight (kg)" exists at all."""
    propiedades = _construir_propiedades_checkin(
        "client@example.com", "Ana Test", "Adherence check-in", "2026-07-30", peso_kg=71.5,
    )
    assert propiedades["Weight (kg)"]["number"] == 71.5


def test_checkin_properties_weight_of_zero_is_not_treated_as_missing():
    """0.0 is a real (if unlikely) weight, not "not provided" -- only
    None should be treated as absent, guarding against a `if peso_kg:`
    bug that would silently drop a falsy-but-real value."""
    propiedades = _construir_propiedades_checkin(
        "client@example.com", "Ana Test", "Adherence check-in", "2026-07-30", peso_kg=0.0,
    )
    assert propiedades["Weight (kg)"]["number"] == 0.0


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


def test_historial_checkins_missing_credentials_raises(monkeypatch, tmp_path):
    """Same credential-checking path -- ui/app.py's adherence history
    expander needs to fail the same clean way when Notion isn't
    configured, not raise an unrelated import error."""
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.delenv("NOTION_CHECKINS_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        historial_checkins("client@example.com")


def test_obtener_registro_cliente_missing_credentials_raises(monkeypatch, tmp_path):
    """Same credential-checking path as every other network call in this
    module -- the portal view needs to fail the same clean way when
    Notion isn't configured, not raise an unrelated import error."""
    import notion_connector

    monkeypatch.delenv("NOTION_API_KEY", raising=False)
    monkeypatch.delenv("NOTION_DATABASE_ID", raising=False)
    monkeypatch.setattr(notion_connector, "REPO_ROOT", tmp_path)
    with pytest.raises(NotionClientError):
        obtener_registro_cliente("some-page-id")


def test_fila_registro_cliente_extracts_expected_fields():
    pagina = {
        "properties": {
            "Name": {"title": [{"plain_text": "Laura Fernandez"}]},
            "Summary": {"rich_text": [{"plain_text": "Routine: full body. "}, {"plain_text": "Diet: 2000 kcal."}]},
            "Verdict": {"select": {"name": "Auto-approved"}},
            "Date": {"date": {"start": "2026-08-01"}},
        }
    }
    fila = _fila_registro_cliente_desde_pagina(pagina)
    assert fila == {
        "nombre": "Laura Fernandez",
        "resumen": "Routine: full body. Diet: 2000 kcal.",
        "veredicto": "Auto-approved",
        "fecha": "2026-08-01",
        "objetivo": None,
        "plan_semanal": [],
        "sesiones": [],
        "idioma": "en",
        "mensaje_rutina": "",
        "mensaje_dieta": "",
    }


def test_fila_registro_cliente_reads_the_saved_language():
    pagina = {
        "properties": {
            "Name": {"title": [{"plain_text": "Laura Fernandez"}]},
            "Summary": {"rich_text": []},
            "Verdict": {"select": {"name": "Auto-approved"}},
            "Date": {"date": {"start": "2026-08-01"}},
            "Language": {"select": {"name": "es"}},
        }
    }
    fila = _fila_registro_cliente_desde_pagina(pagina)
    assert fila["idioma"] == "es"


def test_fila_registro_cliente_reads_the_saved_messages():
    pagina = {
        "properties": {
            "Name": {"title": [{"plain_text": "Laura Fernandez"}]},
            "Summary": {"rich_text": []},
            "Verdict": {"select": {"name": "Auto-approved"}},
            "Date": {"date": {"start": "2026-08-01"}},
            "Routine Message": {"rich_text": [{"plain_text": "Hi Laura, here's your routine."}]},
            "Diet Message": {"rich_text": [{"plain_text": "Hi Laura, here's your diet."}]},
        }
    }
    fila = _fila_registro_cliente_desde_pagina(pagina)
    assert fila["mensaje_rutina"] == "Hi Laura, here's your routine."
    assert fila["mensaje_dieta"] == "Hi Laura, here's your diet."


def test_fila_registro_cliente_maps_the_goal_label_back_to_the_internal_key():
    pagina = {
        "properties": {
            "Name": {"title": [{"plain_text": "Laura Fernandez"}]},
            "Summary": {"rich_text": []},
            "Verdict": {"select": {"name": "Auto-approved"}},
            "Date": {"date": {"start": "2026-08-01"}},
            "Goal": {"select": {"name": "Fat loss"}},
        }
    }
    fila = _fila_registro_cliente_desde_pagina(pagina)
    assert fila["objetivo"] == "perdida_grasa"


def test_fila_cliente_lista_extracts_expected_fields():
    pagina = {
        "id": "page-1",
        "properties": {
            "Name": {"title": [{"plain_text": "Laura Fernandez"}]},
            "Email": {"email": "laura@example.com"},
            "Date": {"date": {"start": "2026-08-01"}},
            "Goal": {"select": {"name": "Hypertrophy"}},
            "Level": {"select": {"name": "Intermediate"}},
            "Verdict": {"select": {"name": "Approved"}},
            "Email Sent": {"checkbox": True},
        }
    }
    fila = _fila_cliente_lista_desde_pagina(pagina)
    assert fila == {
        "id": "page-1",
        "nombre": "Laura Fernandez",
        "email": "laura@example.com",
        "fecha": "2026-08-01",
        "objetivo": "Hypertrophy",
        "nivel": "Intermediate",
        "veredicto": "Approved",
        "email_enviado": True,
    }


def test_fila_cliente_lista_handles_missing_optional_properties():
    """A record without an email typed in yet (see actualizar_email_cliente()'s
    docstring on when that gets backfilled) shouldn't crash the overview."""
    pagina = {"id": "page-2", "properties": {"Name": {"title": [{"plain_text": "New Client"}]}}}
    fila = _fila_cliente_lista_desde_pagina(pagina)
    assert fila == {
        "id": "page-2",
        "nombre": "New Client",
        "email": None,
        "fecha": None,
        "objetivo": None,
        "nivel": None,
        "veredicto": None,
        "email_enviado": False,
    }


def test_fila_checkin_extracts_expected_fields():
    pagina = {
        "properties": {
            "Date": {"date": {"start": "2026-07-28"}},
            "Type": {"select": {"name": "Adherence check-in"}},
            "Adherence rating": {"select": {"name": "Medium"}},
            "Adherence notes": {"rich_text": [{"plain_text": "Skipped day 4. "}, {"plain_text": "Struggled with diet."}]},
            "Weight (kg)": {"number": 71.5},
        }
    }
    fila = _fila_checkin_desde_pagina(pagina)
    assert fila == {
        "fecha": "2026-07-28",
        "tipo": "Adherence check-in",
        "valoracion": "Medium",
        "notas": "Skipped day 4. Struggled with diet.",
        "peso_kg": 71.5,
    }


def test_fila_checkin_handles_missing_optional_properties():
    """A "Plan sent" row (see crear_registro_checkin()) never sets
    Adherence rating/notes -- reading it back shouldn't raise just because
    those properties are absent (Notion omits unset select/rich_text
    properties entirely rather than returning them as null)."""
    pagina = {
        "properties": {
            "Date": {"date": {"start": "2026-07-20"}},
            "Type": {"select": {"name": "Plan sent"}},
        }
    }
    fila = _fila_checkin_desde_pagina(pagina)
    assert fila == {"fecha": "2026-07-20", "tipo": "Plan sent", "valoracion": None, "notas": "", "peso_kg": None}
