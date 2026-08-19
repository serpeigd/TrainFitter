"""Tests for agents/pdf_intake.py. Same approach as test_pdf_generador.py:
exercises the real reportlab/pypdf libraries end to end -- no credentials
or network involved, so nothing here needs mocking."""

import io

import pytest
from pdf_intake import (
    CAMPO_ALERGIAS,
    CAMPO_ALTURA,
    CAMPO_ANIOS_ENTRENANDO,
    CAMPO_DIAS_SEMANA,
    CAMPO_EDAD,
    CAMPO_EMAIL,
    CAMPO_EMBARAZO,
    CAMPO_EMBARAZO_DETALLE,
    CAMPO_INQUIETUD_PRINCIPAL,
    CAMPO_LESION_DESCRIPCION,
    CAMPO_LUGAR_ENTRENO,
    CAMPO_MINUTOS_SESION,
    CAMPO_NIVEL,
    CAMPO_NOMBRE,
    CAMPO_NOTAS_LIBRES,
    CAMPO_OBJETIVO,
    CAMPO_PASOS,
    CAMPO_PESO,
    CAMPO_SEXO,
    CAMPO_TIENE_LESION,
    CAMPO_TIPO_DIETA,
    MATERIAL_OPCIONES,
    PREFIJO_MATERIAL,
    es_intake_pdf,
    generar_pdf_intake,
    leer_intake_pdf,
)


def _llenar(pdf_bytes: bytes, valores: dict) -> bytes:
    """Simulates a client filling in the PDF form -- the same round-trip
    mechanism a real PDF viewer uses (AcroForm field values), just driven
    programmatically instead of by clicking."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.append(io.BytesIO(pdf_bytes))
    for pagina in writer.pages:
        writer.update_page_form_field_values(pagina, valores, auto_regenerate=False)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


VALORES_COMPLETOS = {
    CAMPO_NOMBRE: "Laura Fernandez",
    CAMPO_EMAIL: "laura.fernandez@example.com",
    CAMPO_EDAD: "34",
    CAMPO_SEXO: "mujer",
    CAMPO_PESO: "68",
    CAMPO_ALTURA: "170",
    CAMPO_OBJETIVO: "perdida_grasa",
    CAMPO_NIVEL: "intermedio",
    CAMPO_ANIOS_ENTRENANDO: "2",
    CAMPO_DIAS_SEMANA: "4",
    CAMPO_MINUTOS_SESION: "50",
    CAMPO_LUGAR_ENTRENO: "gimnasio_completo",
    f"{PREFIJO_MATERIAL}mancuernas": "/Yes",
    f"{PREFIJO_MATERIAL}poleas": "/Yes",
    CAMPO_TIENE_LESION: "/Yes",
    CAMPO_LESION_DESCRIPCION: "Old shoulder strain, avoid heavy overhead pressing.",
    CAMPO_ALERGIAS: "peanuts, shellfish",
    CAMPO_TIPO_DIETA: "omnivora",
    CAMPO_INQUIETUD_PRINCIPAL: "Would like a lower-gluten approach.",
    CAMPO_PASOS: "8000",
    CAMPO_NOTAS_LIBRES: "Excited to start!",
}


@pytest.fixture
def pdf_relleno():
    return _llenar(generar_pdf_intake(idioma="en"), VALORES_COMPLETOS)


def test_intake_pdf_is_a_real_multi_page_pdf():
    from pypdf import PdfReader

    pdf = generar_pdf_intake(idioma="en")
    assert pdf.startswith(b"%PDF")
    assert len(PdfReader(io.BytesIO(pdf)).pages) > 1


def test_es_intake_pdf_true_for_the_intake_form():
    assert es_intake_pdf(generar_pdf_intake(idioma="en")) is True


def test_es_intake_pdf_false_for_garbage_input():
    assert es_intake_pdf(b"not a pdf at all") is False


def test_reads_back_basic_info_correctly(pdf_relleno):
    perfil = leer_intake_pdf(pdf_relleno)
    datos = perfil["datos_basicos"]
    assert datos["nombre"] == "Laura Fernandez"
    assert datos["email"] == "laura.fernandez@example.com"
    assert datos["edad"] == 34
    assert datos["sexo"] == "mujer"
    assert datos["peso_kg"] == 68.0
    assert datos["altura_cm"] == 170.0


def test_reads_back_blank_email_as_empty_string():
    """A prospect who left the email field blank -- must degrade to ""
    rather than crash, matching every other optional text field here.
    ui/app.py's _califica_para_auto_envio() treats this as "doesn't
    qualify for auto-send," falling back to the manual approval flow."""
    pdf = _llenar(generar_pdf_intake(idioma="en"), {CAMPO_NOMBRE: "Test"})
    perfil = leer_intake_pdf(pdf)
    assert perfil["datos_basicos"]["email"] == ""


def test_reads_back_radio_selections_correctly(pdf_relleno):
    perfil = leer_intake_pdf(pdf_relleno)
    assert perfil["objetivo"]["principal"] == "perdida_grasa"
    assert perfil["experiencia"]["nivel"] == "intermedio"
    assert perfil["disponibilidad"]["lugar_entreno"] == "gimnasio_completo"
    assert perfil["nutricion"]["tipo_dieta"] == "omnivora"


def test_reads_back_equipment_checkboxes_as_a_list(pdf_relleno):
    perfil = leer_intake_pdf(pdf_relleno)
    assert set(perfil["disponibilidad"]["material_disponible"]) == {"mancuernas", "poleas"}


def test_unfilled_equipment_checkboxes_are_not_included():
    perfil = leer_intake_pdf(_llenar(generar_pdf_intake(idioma="en"), {CAMPO_NOMBRE: "Test"}))
    assert perfil["disponibilidad"]["material_disponible"] == []


def test_reads_back_comma_separated_allergy_list(pdf_relleno):
    perfil = leer_intake_pdf(pdf_relleno)
    assert perfil["salud"]["alergias_alimentarias"] == ["peanuts", "shellfish"]


def test_reads_back_main_dietary_concern(pdf_relleno):
    perfil = leer_intake_pdf(pdf_relleno)
    assert perfil["nutricion"]["inquietud_principal"] == "Would like a lower-gluten approach."


def test_blank_main_dietary_concern_is_empty_not_missing():
    perfil = leer_intake_pdf(_llenar(generar_pdf_intake(idioma="en"), {CAMPO_NOMBRE: "Test"}))
    assert perfil["nutricion"]["inquietud_principal"] == ""


def test_injury_checkbox_becomes_a_single_lesiones_entry(pdf_relleno):
    perfil = leer_intake_pdf(pdf_relleno)
    lesiones = perfil["salud"]["lesiones"]
    assert len(lesiones) == 1
    assert lesiones[0]["descripcion"] == "Old shoulder strain, avoid heavy overhead pressing."
    assert lesiones[0]["activa_actualmente"] is True


def test_no_injury_checkbox_means_no_lesiones_entries():
    perfil = leer_intake_pdf(_llenar(generar_pdf_intake(idioma="en"), {CAMPO_NOMBRE: "Test"}))
    assert perfil["salud"]["lesiones"] == []


def test_pregnancy_checkbox_and_detail(pdf_relleno):
    pdf = _llenar(generar_pdf_intake(idioma="en"), {
        CAMPO_NOMBRE: "Test", CAMPO_EMBARAZO: "/Yes", CAMPO_EMBARAZO_DETALLE: "Week 20",
    })
    perfil = leer_intake_pdf(pdf)
    assert perfil["salud"]["embarazo_o_lactancia"] == {"aplica": True, "detalle": "Week 20"}


def test_reads_back_notas_libres(pdf_relleno):
    perfil = leer_intake_pdf(pdf_relleno)
    assert perfil["notas_libres"] == "Excited to start!"


def test_blank_numeric_fields_fall_back_to_sensible_defaults_not_a_crash():
    """A client who skips a numeric field shouldn't crash the automated
    trigger -- see leer_intake_pdf()'s docstring on being best-effort."""
    perfil = leer_intake_pdf(_llenar(generar_pdf_intake(idioma="en"), {CAMPO_NOMBRE: "Test"}))
    assert perfil["datos_basicos"]["edad"] == 0
    assert perfil["disponibilidad"]["dias_por_semana"] == 3
    assert perfil["disponibilidad"]["minutos_por_sesion"] == 45


def test_perfil_from_intake_runs_through_the_real_pipeline(pdf_relleno):
    """The real end-to-end proof: a filled intake PDF's extracted profile
    must be a genuinely valid perfil_cliente the orchestrator can run,
    not just a dict that happens to look right."""
    from orchestrator import ejecutar_pipeline

    perfil = leer_intake_pdf(pdf_relleno)
    perfil["id_cliente"] = "test_intake"
    perfil["fecha_admision"] = "2026-08-04"

    estado = ejecutar_pipeline(perfil)

    assert estado.error is None
    assert estado.estado == "pendiente_revision_reforzada"  # declared injury + allergies
    assert "shoulder" in estado.veredicto["motivos"][0].lower() or any(
        "shoulder" in m.lower() for m in estado.veredicto["motivos"]
    )


def test_every_material_option_has_a_matching_field_name():
    """Locks in that PREFIJO_MATERIAL + each MATERIAL_OPCIONES value is
    exactly what generar_pdf_intake() names the checkbox and what
    leer_intake_pdf() looks for -- a typo in either list would silently
    stop that piece of equipment from ever being captured."""
    pdf = generar_pdf_intake(idioma="en")
    from pypdf import PdfReader

    campos = PdfReader(io.BytesIO(pdf)).get_fields()
    for opcion in MATERIAL_OPCIONES:
        assert f"{PREFIJO_MATERIAL}{opcion}" in campos
