"""
PDF generation and reading for the two files attached to a plan email (see
mcp/gmail_client.py's crear_borrador()): a plain informational diet PDF,
and a fillable checklist PDF the client marks up and sends back with what
they actually did.

DESIGN — a fillable PDF form instead of a plain-text attachment: the
project owner's own call, after the original plain-text checklist ran into
a real problem — nothing in a .txt file's own content signals "this is
meant to be filled in and returned," and mail clients don't universally
preserve it as editable-feeling either. A PDF form's checkboxes and text
fields are natively fillable in essentially any PDF viewer (Adobe Reader,
Preview, most browsers), on desktop or mobile, without the client needing
a specific app. See docs/decisiones.md for the fuller comparison against
.docx and Google Docs, and why those lost out.

DESIGN — reportlab to write, pypdf to read: reportlab's `acroForm` API
(canvas-level, not the higher-level Platypus flowables used for the plain
diet PDF) is the standard, mature way to author AcroForm fields in Python.
pypdf's `PdfReader.get_fields()` reads them back as a flat {field_name:
{"/V": value, ...}} dict — checkboxes come back as the string "/Yes" or
"/Off", text fields as their plain string value. Both are free, pure
Python, lazily imported (same convention as pdfplumber for
analytics_parser.py, google-api-python-client for gmail_client.py): the
default rule-engine pipeline never needs either installed.

DESIGN — client-facing content only: the diet PDF never includes
`advertencias_revision_humana` -- those are enhanced-review flags for the
*trainer*, not something a client should see unreviewed in their own
inbox. Only ui/app.py's trainer-facing panel shows that field.

DESIGN — the checklist's routine section only needs a total/completed
count, not which specific day was skipped: same as the plain-text version
it replaced, main.py's downstream Notion row records "X/Y sessions
completed", not a per-day breakdown -- so each checkbox field is just
named session_1..session_N with no day label encoded in the field name
itself (the printed label next to it is what the client actually reads).
"""

import io
import re

from adherencia_parser import valoracion_desde_ratios

# Shared between generar_pdf_dieta()/generar_pdf_checklist() (name the
# files) and gmail_client.py (never needs these directly, but keeps every
# filename decision in one place, same pattern as gmail_client.py's own
# ASUNTO_PLAN_*/NOMBRE_ADJUNTO_* constants).
NOMBRE_PDF_DIETA_EN = "diet-plan.pdf"
NOMBRE_PDF_DIETA_ES = "plan-dieta.pdf"
NOMBRE_PDF_CHECKLIST_EN = "adherence-checklist.pdf"
NOMBRE_PDF_CHECKLIST_ES = "checklist-adherencia.pdf"

# Fixed at a week regardless of the routine's own training frequency (3, 4,
# 5 days/week...) -- diet adherence is tracked daily, not just on training
# days, so it needs its own constant rather than reusing len(sesiones).
# The checklist PDF always prints "out of N" using this value, so reading
# a reply back never needs to parse it -- it's known by construction.
DIAS_SEMANA_DIETA = 7

# AcroForm field names, shared between generar_pdf_checklist() (creates
# them) and leer_checklist_pdf() (reads them back) so the two can never
# drift apart.
PREFIJO_CAMPO_SESION = "session_"
CAMPO_NOTAS_RUTINA = "routine_notes"
CAMPO_DIAS_DIETA = "diet_days"
CAMPO_NOTAS_DIETA = "diet_notes"


def generar_pdf_dieta(borrador_dieta: dict, nombre_cliente: str, idioma: str = "en") -> bytes:
    """
    Renders the diet draft as a plain, read-only PDF -- calories/macros,
    meal distribution, suggested food sources, and synergy tips. Never
    includes advertencias_revision_humana (see module docstring).

    Args:
        borrador_dieta: same schema as agents/dieta_reglas.py's output.
        nombre_cliente: for the title and greeting.
        idioma: "en" (default) or "es" -- language of this document's own
            labels/headings. Food source names are translated for display
            via food_bank.nombre_mostrado(), same as ui/app.py does on
            screen -- the canonical English values inside borrador_dieta
            itself are untouched.

    Returns:
        The PDF file's raw bytes.
    """
    from food_bank import nombre_mostrado
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle("Titulo", parent=estilos["Title"], spaceAfter=6)
    estilo_cuerpo = ParagraphStyle("Cuerpo", parent=estilos["BodyText"], spaceAfter=10)
    estilo_seccion = ParagraphStyle("Seccion", parent=estilos["Heading2"], spaceBefore=12, spaceAfter=6)
    estilo_item = ParagraphStyle("Item", parent=estilos["BodyText"], spaceAfter=2)

    m = borrador_dieta["macros"]
    if idioma == "es":
        textos = {
            "titulo": f"Tu dieta — {nombre_cliente}",
            "objetivos": "Objetivos diarios",
            "objetivos_texto": (
                f"{borrador_dieta['calorias_objetivo_kcal']} kcal — "
                f"{m['proteina_g']} g proteína · {m['grasa_g']} g grasa · {m['carbohidratos_g']} g carbohidratos"
            ),
            "reparto": "Reparto de comidas",
            "proteina": "Fuentes de proteína sugeridas",
            "carbohidrato": "Fuentes de carbohidrato sugeridas",
            "grasa": "Fuentes de grasa sugeridas",
            "consejos": "Consejos",
            "pie": "Borrador preparado por TrainFitter — revisado y enviado por tu entrenador/a.",
        }
    else:
        textos = {
            "titulo": f"Your diet — {nombre_cliente}",
            "objetivos": "Daily targets",
            "objetivos_texto": (
                f"{borrador_dieta['calorias_objetivo_kcal']} kcal — "
                f"{m['proteina_g']} g protein · {m['grasa_g']} g fat · {m['carbohidratos_g']} g carbs"
            ),
            "reparto": "Meal distribution",
            "proteina": "Suggested protein sources",
            "carbohidrato": "Suggested carbohydrate sources",
            "grasa": "Suggested fat sources",
            "consejos": "Tips",
            "pie": "Draft prepared by TrainFitter — reviewed and sent by your trainer.",
        }

    contenido = [
        Paragraph(textos["titulo"], estilo_titulo),
        Paragraph(borrador_dieta["mensaje_para_el_cliente"], estilo_cuerpo),
        Paragraph(textos["objetivos"], estilo_seccion),
        Paragraph(textos["objetivos_texto"], estilo_cuerpo),
        Paragraph(textos["reparto"], estilo_seccion),
        Paragraph(borrador_dieta["distribucion_comidas"], estilo_cuerpo),
    ]

    for clave, fuentes in (
        ("proteina", borrador_dieta["fuentes_proteina_sugeridas"]),
        ("carbohidrato", borrador_dieta["fuentes_carbohidrato_sugeridas"]),
        ("grasa", borrador_dieta["fuentes_grasa_sugeridas"]),
    ):
        contenido.append(Paragraph(textos[clave], estilo_seccion))
        contenido.append(
            ListFlowable(
                [ListItem(Paragraph(nombre_mostrado(f, idioma), estilo_item)) for f in fuentes],
                bulletType="bullet",
            )
        )

    if borrador_dieta["consejos_sinergias"]:
        contenido.append(Paragraph(textos["consejos"], estilo_seccion))
        contenido.append(
            ListFlowable(
                [ListItem(Paragraph(c, estilo_item)) for c in borrador_dieta["consejos_sinergias"]],
                bulletType="bullet",
            )
        )

    contenido.append(Spacer(1, 16))
    contenido.append(Paragraph(textos["pie"], ParagraphStyle("Pie", parent=estilos["Italic"], fontSize=8)))

    buffer = io.BytesIO()
    SimpleDocTemplate(
        buffer, pagesize=letter, topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    ).build(contenido)
    return buffer.getvalue()


def generar_pdf_checklist(borrador_rutina: dict, borrador_dieta: dict, nombre_cliente: str, idioma: str = "en") -> bytes:
    """
    Renders a fillable PDF form: one checkbox per routine session, a text
    field for how many of the last DIAS_SEMANA_DIETA days the diet was
    followed, and two multi-line text fields for free-form notes on the
    routine and diet. The client fills it in with any PDF viewer and
    replies with it attached (see gmail_client.py's crear_borrador() for
    the instructions sent alongside it).

    Args:
        borrador_rutina, borrador_dieta: same schemas as
            rutina_reglas.py's/dieta_reglas.py's output.
        nombre_cliente: for the title.
        idioma: "en" (default) or "es" -- language of the printed labels.
            Field *names* (session_1, diet_days, ...) never change with
            idioma -- leer_checklist_pdf() reads them back by name, not by
            the label text next to them.

    Returns:
        The PDF file's raw bytes.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    objetivo_dieta = (
        f"{borrador_dieta['calorias_objetivo_kcal']} kcal, "
        f"{borrador_dieta['macros']['proteina_g']} g protein"
        if idioma != "es" else
        f"{borrador_dieta['calorias_objetivo_kcal']} kcal, "
        f"{borrador_dieta['macros']['proteina_g']} g de proteína"
    )

    if idioma == "es":
        textos = {
            "titulo": f"Seguimiento — {nombre_cliente}",
            "instrucciones": [
                "Marca lo que hayas completado y responde a este email con este mismo",
                "archivo adjunto. Nada de esto se califica: cuanto más honesto, mejor.",
            ],
            "rutina": "RUTINA",
            "dieta": "DIETA",
            "objetivo_dieta": f"Objetivo: {objetivo_dieta}.",
            "dias_dieta": f"De los últimos {DIAS_SEMANA_DIETA} días, ¿cuántos seguiste el plan?",
            "notas_rutina": "¿Algo sobre la rutina que debamos saber?",
            "notas_dieta": "¿Algo sobre la dieta que debamos saber?",
        }
    else:
        textos = {
            "titulo": f"Adherence check-in — {nombre_cliente}",
            "instrucciones": [
                "Mark off what you completed and reply to this email with this same",
                "file attached. Nothing here is graded: the more honest it is, the better.",
            ],
            "rutina": "ROUTINE",
            "dieta": "DIET",
            "objetivo_dieta": f"Target: {objetivo_dieta}.",
            "dias_dieta": f"Out of the last {DIAS_SEMANA_DIETA} days, how many did you follow the plan?",
            "notas_rutina": "Anything about the routine we should know?",
            "notas_dieta": "Anything about the diet we should know?",
        }

    ancho, alto = letter
    margen = 50
    ancho_util = ancho - 2 * margen
    y = alto - margen

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    form = c.acroForm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(margen, y, textos["titulo"])
    y -= 22

    c.setFont("Helvetica", 10)
    for linea in textos["instrucciones"]:
        c.drawString(margen, y, linea)
        y -= 14
    y -= 10

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, textos["rutina"])
    y -= 20

    c.setFont("Helvetica", 10)
    for indice, sesion in enumerate(borrador_rutina["sesiones"], start=1):
        form.checkbox(
            name=f"{PREFIJO_CAMPO_SESION}{indice}", x=margen, y=y - 3,
            buttonStyle="check", borderStyle="solid", size=12, checked=False,
        )
        c.drawString(margen + 20, y, sesion["dia"])
        y -= 22

    y -= 6
    c.drawString(margen, y, textos["notas_rutina"])
    y -= 16
    form.textfield(
        name=CAMPO_NOTAS_RUTINA, x=margen, y=y - 64, width=ancho_util, height=64,
        fieldFlags="multiline", borderStyle="solid", value="",
    )
    y -= 80

    c.setFont("Helvetica-Bold", 12)
    c.drawString(margen, y, textos["dieta"])
    y -= 20

    c.setFont("Helvetica", 10)
    c.drawString(margen, y, textos["objetivo_dieta"])
    y -= 18

    c.drawString(margen, y, textos["dias_dieta"])
    form.textfield(name=CAMPO_DIAS_DIETA, x=margen + ancho_util - 50, y=y - 3, width=50, height=16, borderStyle="solid", value="")
    y -= 26

    c.drawString(margen, y, textos["notas_dieta"])
    y -= 16
    form.textfield(
        name=CAMPO_NOTAS_DIETA, x=margen, y=y - 64, width=ancho_util, height=64,
        fieldFlags="multiline", borderStyle="solid", value="",
    )

    c.save()
    return buffer.getvalue()


def es_checklist_pdf(contenido_pdf: bytes) -> bool:
    """
    Whether a PDF attachment looks like this project's own checklist form
    -- used by gmail_client.py to pick the right attachment out of a reply
    when the filename alone isn't a reliable enough signal (e.g. the
    client renamed the file, or the diet PDF got attached to the reply
    too). True if it has an AcroForm with at least one of our known field
    names.

    Args:
        contenido_pdf: raw PDF bytes.

    Returns:
        False for anything that isn't a readable PDF with our fields --
        never raises on a malformed/unrelated PDF.
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        campos = PdfReader(io.BytesIO(contenido_pdf)).get_fields() or {}
    except PdfReadError:
        return False
    return CAMPO_DIAS_DIETA in campos or any(nombre.startswith(PREFIJO_CAMPO_SESION) for nombre in campos)


def leer_checklist_pdf(contenido_pdf: bytes) -> dict:
    """
    Reads a filled-in checklist PDF's form field values back into
    structured data -- the PDF-based replacement for what the old
    text-tag-based adherencia_parser.analizar_adherencia() used to do,
    same output shape so main.py and resumir_adherencia() don't need to
    change.

    Args:
        contenido_pdf: raw PDF bytes (see
            mcp.gmail_client.buscar_respuestas_adherencia()).

    Returns:
        {
            "dias_rutina_completados": int, "dias_rutina_totales": int,
            "notas_rutina": str,
            "dias_dieta_seguidos": int | None, "dias_dieta_totales": int | None,
            "notas_dieta": str,
            "valoracion": "Low" | "Medium" | "High" | None (None only when
                the PDF has none of our expected fields at all -- not a
                checklist we generated, or too corrupted to read).
        }
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        campos = PdfReader(io.BytesIO(contenido_pdf)).get_fields() or {}
    except PdfReadError:
        campos = {}

    casillas_sesion = {nombre: valor for nombre, valor in campos.items() if nombre.startswith(PREFIJO_CAMPO_SESION)}
    dias_rutina_totales = len(casillas_sesion)
    dias_rutina_completados = sum(1 for valor in casillas_sesion.values() if str(valor.get("/V", "")) == "/Yes")

    notas_rutina = str((campos.get(CAMPO_NOTAS_RUTINA) or {}).get("/V", "") or "").strip()
    notas_dieta = str((campos.get(CAMPO_NOTAS_DIETA) or {}).get("/V", "") or "").strip()

    dias_dieta_totales = DIAS_SEMANA_DIETA if CAMPO_DIAS_DIETA in campos else None
    dias_dieta_seguidos = None
    if dias_dieta_totales is not None:
        valor_bruto = str((campos.get(CAMPO_DIAS_DIETA) or {}).get("/V", "") or "")
        numero = re.search(r"\d+", valor_bruto)
        if numero:
            dias_dieta_seguidos = min(int(numero.group(0)), dias_dieta_totales)

    ratios = []
    if dias_rutina_totales:
        ratios.append(dias_rutina_completados / dias_rutina_totales)
    # Only counted when the client actually gave a number -- a blank
    # answer isn't the same as "followed 0 days" and shouldn't drag the
    # rating down as if it were.
    if dias_dieta_totales and dias_dieta_seguidos is not None:
        ratios.append(dias_dieta_seguidos / dias_dieta_totales)

    return {
        "dias_rutina_completados": dias_rutina_completados,
        "dias_rutina_totales": dias_rutina_totales,
        "notas_rutina": notas_rutina,
        "dias_dieta_seguidos": dias_dieta_seguidos,
        "dias_dieta_totales": dias_dieta_totales,
        "notas_dieta": notas_dieta,
        "valoracion": valoracion_desde_ratios(ratios),
    }
