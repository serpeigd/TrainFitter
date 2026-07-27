"""Tests for agents/analytics_parser.py — bloodwork marker extraction.

Marker-matching logic is tested directly on text (fast, no PDF I/O). The two
fixture PDFs (tests/fixtures/*.pdf, entirely fictional data — see
docs/decisiones.md) exercise the actual PDF-extraction layer end-to-end."""

from pathlib import Path

from analytics_parser import analizar_pdf_analitica, analizar_texto_analitica

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_detects_marker_bilingual_spanish():
    resultados = analizar_texto_analitica("Glucosa en ayunas: 88 mg/dL")
    assert len(resultados) == 1
    assert resultados[0]["nombre"] == "Fasting glucose"
    assert resultados[0]["valor"] == 88.0
    assert resultados[0]["fuera_de_rango"] is False


def test_detects_marker_bilingual_english():
    resultados = analizar_texto_analitica("Glucose (fasting): 118 mg/dL")
    assert resultados[0]["valor"] == 118.0
    assert resultados[0]["fuera_de_rango"] is True


def test_flags_value_outside_normal_range():
    resultados = analizar_texto_analitica("TSH: 6.8 mIU/L")
    assert resultados[0]["fuera_de_rango"] is True


def test_does_not_flag_value_inside_normal_range():
    resultados = analizar_texto_analitica("TSH: 2.1 mIU/L")
    assert resultados[0]["fuera_de_rango"] is False


def test_ldl_and_hdl_do_not_cross_match():
    resultados = analizar_texto_analitica("LDL cholesterol: 160 mg/dL\nHDL cholesterol: 38 mg/dL")
    por_nombre = {r["nombre"]: r for r in resultados}
    assert por_nombre["LDL cholesterol"]["valor"] == 160.0
    assert por_nombre["HDL cholesterol"]["valor"] == 38.0
    assert por_nombre["LDL cholesterol"]["fuera_de_rango"] is True   # high LDL
    assert por_nombre["HDL cholesterol"]["fuera_de_rango"] is True   # low HDL


def test_unrecognized_text_yields_no_markers():
    assert analizar_texto_analitica("This report contains no lab values at all.") == []


def test_partial_report_only_returns_markers_actually_present():
    resultados = analizar_texto_analitica("Ferritin: 75 ng/mL")
    assert len(resultados) == 1
    assert resultados[0]["nombre"] == "Ferritin"


def test_normal_bloodwork_pdf_flags_nothing():
    pdf_bytes = (FIXTURES_DIR / "analitica_normal.pdf").read_bytes()
    resultado = analizar_pdf_analitica(pdf_bytes)
    assert len(resultado["marcadores"]) == 9
    assert not any(m["fuera_de_rango"] for m in resultado["marcadores"])


def test_out_of_range_bloodwork_pdf_flags_expected_markers():
    pdf_bytes = (FIXTURES_DIR / "analitica_fuera_rango.pdf").read_bytes()
    resultado = analizar_pdf_analitica(pdf_bytes)
    fuera_de_rango = {m["nombre"] for m in resultado["marcadores"] if m["fuera_de_rango"]}
    assert fuera_de_rango == {
        "Fasting glucose", "HbA1c", "Total cholesterol", "LDL cholesterol",
        "HDL cholesterol", "Triglycerides", "Vitamin D (25-OH)", "TSH",
    }
    # Ferritin was deliberately left in range in this fixture.
    en_rango = {m["nombre"] for m in resultado["marcadores"] if not m["fuera_de_rango"]}
    assert en_rango == {"Ferritin"}


def test_corrupted_pdf_bytes_returns_no_markers_instead_of_raising():
    assert analizar_pdf_analitica(b"not a real pdf") == {"marcadores": []}
