"""
Bloodwork parser: best-effort extraction of common clinical markers from an
attached PDF, so the pipeline can react to real clinical data instead of just
the trainer's free-text notes about it.

DESIGN — parsing is separate from judgment: this module only extracts
numbers and flags whether each one falls inside a standard adult reference
range. It never diagnoses, never adjusts the diet directly, and never
decides on its own whether the case needs enhanced review — validator_agent.py
re-reads the parsed markers independently and is the one that turns an
out-of-range marker into `revision_reforzada`, exactly like it already does
for declared injuries and allergies (defense in depth, not a new exception
to that pattern).

DESIGN — best-effort, not strict: lab reports vary wildly in layout and
language between providers. A marker that isn't recognized is simply
skipped (not an error) — the trainer still sees the raw PDF and can flag
anything the parser missed. A PDF that fails to open at all (corrupted,
scanned image without OCR, password-protected) returns no markers rather
than raising, since the rest of the intake must never be blocked by this.

Reference ranges below are standard, unisex, non-personalized adult ranges
meant for a portfolio-scale demo — not a substitute for lab-specific ranges,
which vary by instrument/assay and by the patient's age, sex, and pregnancy
status. Sources: ADA Standards of Medical Care in Diabetes (fasting glucose,
HbA1c); NCEP ATP III / AHA lipid panel guidance (total/LDL/HDL cholesterol,
triglycerides); Endocrine Society Clinical Practice Guideline (vitamin D);
typical unisex reference intervals for ferritin and TSH as reported by major
clinical laboratories.
"""

import re

# Each marker: bilingual (ES/EN) name patterns to search for in the raw PDF
# text, immediately followed by the first number found within a short
# window — matches how lab reports actually print results ("Glucosa: 88
# mg/dL", "Glucose 88 mg/dL"). rango_normal is a simplified adult range;
# a value outside it is flagged, not diagnosed.
MARCADORES = [
    {
        "clave": "glucosa",
        "nombre_display": "Fasting glucose",
        "patrones": [r"gluc(?:osa|ose)(?:\s+en\s+ayunas|\s+\(?fasting\)?)?"],
        "unidad": "mg/dL",
        "rango_normal": (70, 99),
    },
    {
        "clave": "hba1c",
        "nombre_display": "HbA1c",
        "patrones": [r"hba1c", r"hemoglobina\s+glic(?:osilada|ada)", r"glycated\s+hemoglobin"],
        "unidad": "%",
        "rango_normal": (4.0, 5.6),
    },
    {
        "clave": "colesterol_total",
        "nombre_display": "Total cholesterol",
        "patrones": [r"colesterol\s+total", r"total\s+cholesterol"],
        "unidad": "mg/dL",
        "rango_normal": (125, 200),
    },
    {
        "clave": "ldl",
        "nombre_display": "LDL cholesterol",
        "patrones": [r"(?:colesterol\s+)?ldl(?:\s+cholesterol)?"],
        "unidad": "mg/dL",
        "rango_normal": (0, 129),
    },
    {
        "clave": "hdl",
        "nombre_display": "HDL cholesterol",
        "patrones": [r"(?:colesterol\s+)?hdl(?:\s+cholesterol)?"],
        "unidad": "mg/dL",
        "rango_normal": (40, 999),
    },
    {
        "clave": "trigliceridos",
        "nombre_display": "Triglycerides",
        "patrones": [r"triglic[eé]ridos", r"triglycerides"],
        "unidad": "mg/dL",
        "rango_normal": (0, 149),
    },
    {
        "clave": "ferritina",
        "nombre_display": "Ferritin",
        "patrones": [r"ferritina", r"ferritin"],
        "unidad": "ng/mL",
        "rango_normal": (15, 200),
    },
    {
        "clave": "vitamina_d",
        "nombre_display": "Vitamin D (25-OH)",
        "patrones": [r"vitamina\s+d(?:\s*\(?25-?oh\)?)?", r"vitamin\s+d(?:\s*\(?25-?oh\)?)?", r"25-?\(?oh\)?d"],
        "unidad": "ng/mL",
        "rango_normal": (30, 100),
    },
    {
        "clave": "tsh",
        "nombre_display": "TSH",
        "patrones": [r"tsh", r"tirotropina", r"thyroid[\s-]stimulating\s+hormone"],
        "unidad": "mIU/L",
        "rango_normal": (0.4, 4.0),
    },
]


def _buscar_valor(texto: str, patrones: list[str]) -> float | None:
    """Finds the first number following any of the marker's name patterns."""
    for patron in patrones:
        coincidencia = re.search(patron + r"[^\d\n]{0,25}(\d{1,4}(?:[.,]\d+)?)", texto, re.IGNORECASE)
        if coincidencia:
            return float(coincidencia.group(1).replace(",", "."))
    return None


def analizar_texto_analitica(texto: str) -> list[dict]:
    """Extracts whichever known markers appear in the given text (already
    extracted from a PDF, or passed directly for testing)."""
    resultados = []
    for marcador in MARCADORES:
        valor = _buscar_valor(texto, marcador["patrones"])
        if valor is None:
            continue
        minimo, maximo = marcador["rango_normal"]
        resultados.append({
            "nombre": marcador["nombre_display"],
            "valor": valor,
            "unidad": marcador["unidad"],
            "rango_normal": f"{minimo}-{maximo} {marcador['unidad']}",
            "fuera_de_rango": not (minimo <= valor <= maximo),
        })
    return resultados


def extraer_texto_pdf(pdf_bytes: bytes) -> str:
    """Extracts raw text from a PDF's bytes. Lazy import: pdfplumber is an
    optional dependency (see requirements.txt), just like the anthropic SDK
    is for motor="llm" — the rest of the pipeline never needs it."""
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)


def analizar_pdf_analitica(pdf_bytes: bytes) -> dict:
    """
    Full pipeline: PDF bytes -> extracted, range-checked markers.

    Never raises: a PDF this parser can't read (corrupted, scanned image,
    unrecognized layout) simply yields no markers instead of blocking the
    rest of the intake.

    Returns:
        {"marcadores": [...]}  — see analizar_texto_analitica() for the
        shape of each entry. Empty list if nothing was recognized.
    """
    try:
        texto = extraer_texto_pdf(pdf_bytes)
    except Exception:
        return {"marcadores": []}
    return {"marcadores": analizar_texto_analitica(texto)}
