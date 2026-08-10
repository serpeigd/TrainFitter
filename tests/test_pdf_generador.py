"""Tests for agents/pdf_generador.py. Unlike most of this project's
network-touching modules, these exercise the real reportlab/pypdf
libraries end to end -- no credentials or network involved, both
libraries do genuine local work, so there's nothing here that needs
mocking (see docs/decisiones.md)."""

import io

import pytest
from pdf_generador import (
    CAMPO_DIAS_DIETA,
    CAMPO_NOTAS_DIETA,
    CAMPO_NOTAS_RUTINA,
    DIAS_SEMANA_DIETA,
    PREFIJO_CAMPO_SESION,
    es_checklist_pdf,
    generar_pdf_checklist,
    generar_pdf_dieta,
    leer_checklist_pdf,
)


@pytest.fixture
def borrador_rutina():
    return {
        "sesiones": [
            {"dia": "Day 1 — Upper A"},
            {"dia": "Day 2 — Lower A"},
            {"dia": "Day 3 — Upper B"},
            {"dia": "Day 4 — Lower B"},
        ]
    }


@pytest.fixture
def borrador_dieta():
    return {
        "calorias_objetivo_kcal": 2125,
        "macros": {"proteina_g": 136, "grasa_g": 64, "carbohidratos_g": 252},
        "mensaje_para_el_cliente": "Hi Marta, this is your draft diet.",
        "distribucion_comidas": "Spread these calories across 4 meals.",
        "fuentes_proteina_sugeridas": ["Chicken breast", "Lentils"],
        "fuentes_carbohidrato_sugeridas": ["Rice", "Oats"],
        "fuentes_grasa_sugeridas": ["Extra virgin olive oil"],
        "consejos_sinergias": ["Vitamins D, E, K and omega-3s are absorbed better with fat."],
    }


def _llenar_checklist(pdf_bytes: bytes, valores: dict) -> bytes:
    """Simulates a client filling in the PDF form -- the same round-trip
    mechanism a real PDF viewer uses (AcroForm field values), just driven
    programmatically instead of by a human clicking checkboxes."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.append(io.BytesIO(pdf_bytes))
    writer.update_page_form_field_values(writer.pages[0], valores, auto_regenerate=False)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# --- generar_pdf_dieta() ---------------------------------------------------


def test_diet_pdf_is_a_real_pdf(borrador_dieta):
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    assert pdf.startswith(b"%PDF")


def test_diet_pdf_contains_the_macros_and_food_sources(borrador_dieta):
    from pypdf import PdfReader

    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "2125" in texto
    assert "Chicken breast" in texto
    assert "absorbed better" in texto


def test_diet_pdf_translates_food_names_for_spanish(borrador_dieta):
    """Matches ui/app.py's on-screen behavior: food source names are
    translated for display via food_bank.nombre_mostrado(), the canonical
    English values inside borrador_dieta stay untouched."""
    from pypdf import PdfReader

    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="es")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "Pechuga de pollo" in texto
    assert "Chicken breast" not in texto


def test_diet_pdf_never_includes_trainer_only_warnings(borrador_dieta):
    """advertencias_revision_humana are enhanced-review flags for the
    trainer -- must never leak into a document the client receives."""
    from pypdf import PdfReader

    borrador_dieta["advertencias_revision_humana"] = ["Client mentioned feeling tired, flag for follow-up."]
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "flag for follow-up" not in texto


def test_diet_pdf_without_weekly_plan_still_renders(borrador_dieta):
    """borrador_dieta (the fixture above) has no "plan_semanal" key --
    matches a draft built before that field existed, or a hand-built test
    fixture. Must degrade to no weekly-plan section, never crash."""
    from pypdf import PdfReader

    assert "plan_semanal" not in borrador_dieta
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "Weekly meal plan" not in texto


def test_diet_pdf_renders_the_weekly_plan_when_present(borrador_dieta):
    from pypdf import PdfReader

    borrador_dieta["plan_semanal"] = [
        {
            "dia": "Monday",
            "comidas": [
                {"tipo": "Breakfast", "descripcion": "150g oats, 200g greek yogurt.", "aprox_kcal": 420},
                {"tipo": "Lunch", "descripcion": "150g chicken breast, 200g rice, with 15g olive oil.", "aprox_kcal": 650},
            ],
        },
        {
            "dia": "Tuesday",
            "comidas": [
                {"tipo": "Breakfast", "descripcion": "100g oats, 150g eggs.", "aprox_kcal": 380},
            ],
        },
    ]
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "Weekly meal plan" in texto
    assert "Monday" in texto
    assert "Tuesday" in texto
    assert "Breakfast" in texto
    assert "150g chicken breast" in texto
    assert "650" in texto


def test_diet_pdf_translates_weekly_plan_section_header_for_spanish(borrador_dieta):
    from pypdf import PdfReader

    borrador_dieta["plan_semanal"] = [
        {"dia": "Lunes", "comidas": [{"tipo": "Desayuno", "descripcion": "100g de avena.", "aprox_kcal": 300}]},
    ]
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="es")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "Plan semanal de comidas" in texto
    assert "Lunes" in texto


def test_diet_pdf_shows_vegetable_sources_when_present(borrador_dieta):
    from pypdf import PdfReader

    borrador_dieta["fuentes_verdura_sugeridas"] = ["Broccoli", "Spinach"]
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "Suggested vegetables" in texto
    assert "Broccoli" in texto


def test_diet_pdf_omits_vegetable_section_when_absent(borrador_dieta):
    """No "fuentes_verdura_sugeridas" key at all (matches a pre-existing
    draft) -- the section header shouldn't render with nothing under it."""
    from pypdf import PdfReader

    assert "fuentes_verdura_sugeridas" not in borrador_dieta
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "Suggested vegetables" not in texto


# --- generar_pdf_checklist() / es_checklist_pdf() ---------------------------


def test_checklist_pdf_is_a_real_pdf(borrador_rutina, borrador_dieta):
    pdf = generar_pdf_checklist(borrador_rutina, borrador_dieta, "Marta", idioma="en")
    assert pdf.startswith(b"%PDF")


def test_checklist_pdf_has_one_checkbox_per_routine_session(borrador_rutina, borrador_dieta):
    from pypdf import PdfReader

    pdf = generar_pdf_checklist(borrador_rutina, borrador_dieta, "Marta", idioma="en")
    campos = PdfReader(io.BytesIO(pdf)).get_fields()
    casillas = [n for n in campos if n.startswith(PREFIJO_CAMPO_SESION)]
    assert len(casillas) == len(borrador_rutina["sesiones"])


def test_checklist_pdf_includes_the_diet_target_for_context(borrador_rutina, borrador_dieta):
    from pypdf import PdfReader

    pdf = generar_pdf_checklist(borrador_rutina, borrador_dieta, "Marta", idioma="en")
    texto = "".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(pdf)).pages)
    assert "2125" in texto
    assert "136" in texto


def test_es_checklist_pdf_true_for_the_checklist(borrador_rutina, borrador_dieta):
    pdf = generar_pdf_checklist(borrador_rutina, borrador_dieta, "Marta", idioma="en")
    assert es_checklist_pdf(pdf) is True


def test_es_checklist_pdf_false_for_the_diet_pdf(borrador_dieta):
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    assert es_checklist_pdf(pdf) is False


def test_es_checklist_pdf_false_for_garbage_input():
    assert es_checklist_pdf(b"not a pdf at all") is False


# --- leer_checklist_pdf() ---------------------------------------------------


def test_reads_back_filled_checkboxes_and_notes(borrador_rutina, borrador_dieta):
    pdf = generar_pdf_checklist(borrador_rutina, borrador_dieta, "Marta", idioma="en")
    lleno = _llenar_checklist(pdf, {
        f"{PREFIJO_CAMPO_SESION}1": "/Yes",
        f"{PREFIJO_CAMPO_SESION}2": "/Yes",
        f"{PREFIJO_CAMPO_SESION}3": "/Yes",
        CAMPO_DIAS_DIETA: "5",
        CAMPO_NOTAS_RUTINA: "Skipped day 4, knee felt off.",
        CAMPO_NOTAS_DIETA: "Struggled on weekends.",
    })
    datos = leer_checklist_pdf(lleno)
    assert datos["dias_rutina_completados"] == 3
    assert datos["dias_rutina_totales"] == 4
    assert datos["notas_rutina"] == "Skipped day 4, knee felt off."
    assert datos["dias_dieta_seguidos"] == 5
    assert datos["dias_dieta_totales"] == DIAS_SEMANA_DIETA
    assert datos["notas_dieta"] == "Struggled on weekends."
    assert datos["valoracion"] == "Medium"


def test_unfilled_checklist_reads_as_zero_completed_with_no_diet_answer(borrador_rutina, borrador_dieta):
    """An unfilled reply (client sent the PDF back untouched) should record
    dias_dieta_seguidos as None, not 0 -- an absent answer isn't the same
    claim as "I followed 0 days"."""
    pdf = generar_pdf_checklist(borrador_rutina, borrador_dieta, "Marta", idioma="en")
    datos = leer_checklist_pdf(pdf)
    assert datos["dias_rutina_completados"] == 0
    assert datos["dias_rutina_totales"] == 4
    assert datos["dias_dieta_seguidos"] is None
    assert datos["dias_dieta_totales"] == DIAS_SEMANA_DIETA
    assert datos["notas_rutina"] == ""
    assert datos["notas_dieta"] == ""
    # Routine-only rating: 0/4 -> Low (no diet ratio counted, blank answer).
    assert datos["valoracion"] == "Low"


def test_diet_days_followed_answer_is_capped_at_the_stated_total(borrador_rutina, borrador_dieta):
    """A client typing something like "7 out of 7, maybe more!" shouldn't
    produce an adherence ratio above 100%."""
    pdf = generar_pdf_checklist(borrador_rutina, borrador_dieta, "Marta", idioma="en")
    lleno = _llenar_checklist(pdf, {CAMPO_DIAS_DIETA: "12"})
    datos = leer_checklist_pdf(lleno)
    assert datos["dias_dieta_seguidos"] == 7


def test_reads_non_checklist_pdf_as_unparseable(borrador_dieta):
    """The diet PDF has no session_*/diet_days fields at all -- reading it
    with leer_checklist_pdf() (e.g. if gmail_client.py's disambiguation
    were ever bypassed) should come back empty, not raise."""
    pdf = generar_pdf_dieta(borrador_dieta, "Marta", idioma="en")
    datos = leer_checklist_pdf(pdf)
    assert datos["dias_rutina_totales"] == 0
    assert datos["dias_dieta_totales"] is None
    assert datos["valoracion"] is None


def test_reads_garbage_bytes_as_unparseable_without_raising():
    datos = leer_checklist_pdf(b"not a pdf at all")
    assert datos["dias_rutina_totales"] == 0
    assert datos["dias_dieta_totales"] is None
    assert datos["valoracion"] is None
