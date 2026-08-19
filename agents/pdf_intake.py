"""
Automated new-client intake: a fillable PDF form mirroring
admission/ficha_cliente_template.md, and a reader that turns a filled
copy back into a perfil_cliente dict — the schema
agents/orchestrator.py's ejecutar_pipeline() expects.

DESIGN — a PDF form here too, not free-text parsing: the adherence
checklist (agents/pdf_generador.py) already established why a fillable
PDF beats a plain-text attachment for this project. For intake
specifically there's a second, stronger reason: perfil_cliente feeds
validator_agent.py's safety cross-check directly (injuries, allergies,
pregnancy, medication). Parsing free-form prose into that schema
reliably, without an LLM, is a much harder problem than the checklist's
simple checkbox counting — a misparse here risks silently dropping a
declared injury or allergy, exactly the failure mode the whole
defense-in-depth design exists to prevent. A form's fields are
unambiguous by construction; there's nothing to guess.

DESIGN — some structured fields are deliberately flattened to free text:
perfil_cliente's `lesiones` is a list of {zona, descripcion, estado,
activa_actualmente} objects — a real repeating structure a static PDF
form can't represent cleanly. The intake form instead has one "do they
have an injury" checkbox plus one free-text description field; a checked
box becomes a single lesiones entry with activa_actualmente=True and the
whole free-text answer as descripcion. This loses per-injury granularity
a trainer typing directly into ui/app.py could capture, but keeps the
property that actually matters to validator_agent.py: a declared injury
of any kind still triggers revision_reforzada, and the trainer reads the
real description text either way.

DESIGN — comma-separated free text for list fields (condiciones,
medicacion, alergias, intolerancias, restricciones, disliked foods):
same convention ui/app.py's manual intake form already uses for these
exact fields (see _lista_desde_texto()) -- the PDF reader mirrors it
rather than inventing a different convention for the same data shape.

DESIGN — datos_basicos.email: added alongside ui/app.py's own auto-send
flow (see mcp/gmail_client.py's enviar_plan()) -- a plan that needs no
human review now sends itself the moment it's generated, which means the
recipient address has to be known at intake time instead of typed in
later at approval. A blank value here (an older intake, or a prospect
who left it empty) just means that specific submission can't qualify for
auto-send; it never blocks the free-text description of the rest of the
form or the plan generation itself.
"""

import io

NOMBRE_PDF_INTAKE_EN = "trainfitter-intake-form.pdf"
NOMBRE_PDF_INTAKE_ES = "formulario-inscripcion-trainfitter.pdf"

# AcroForm field names, shared between generar_pdf_intake() (creates them)
# and leer_intake_pdf() (reads them back) so the two can never drift apart.
# "__" marks nesting in the reconstructed perfil_cliente dict (e.g.
# "datos_basicos__nombre" -> perfil["datos_basicos"]["nombre"]).
CAMPO_NOMBRE = "datos_basicos__nombre"
CAMPO_EMAIL = "datos_basicos__email"
CAMPO_EDAD = "datos_basicos__edad"
CAMPO_SEXO = "datos_basicos__sexo"
CAMPO_PESO = "datos_basicos__peso_kg"
CAMPO_ALTURA = "datos_basicos__altura_cm"
CAMPO_OBJETIVO = "objetivo__principal"
CAMPO_OBJETIVO_TEXTO = "objetivo__en_sus_palabras"
CAMPO_NIVEL = "experiencia__nivel"
CAMPO_NIVEL_COMPROMISO = "experiencia__nivel_compromiso"
CAMPO_ANIOS_ENTRENANDO = "experiencia__anios_entrenando"
CAMPO_EXPERIENCIA_DETALLE = "experiencia__detalle"
CAMPO_DIAS_SEMANA = "disponibilidad__dias_por_semana"
CAMPO_MINUTOS_SESION = "disponibilidad__minutos_por_sesion"
CAMPO_LUGAR_ENTRENO = "disponibilidad__lugar_entreno"
PREFIJO_MATERIAL = "material__"
MATERIAL_OPCIONES = ["maquinas_guiadas", "poleas", "barras_y_discos", "mancuernas", "bancos", "bicicleta_estatica"]
CAMPO_TIENE_LESION = "salud__tiene_lesion"
CAMPO_LESION_DESCRIPCION = "salud__lesion_descripcion"
CAMPO_CONDICIONES = "salud__enfermedades_o_condiciones"
CAMPO_EMBARAZO = "salud__embarazo"
CAMPO_EMBARAZO_DETALLE = "salud__embarazo_detalle"
CAMPO_MEDICACION = "salud__medicacion_habitual"
CAMPO_SUPLEMENTOS = "salud__suplementos_actuales"
CAMPO_ALERGIAS = "salud__alergias_alimentarias"
CAMPO_INTOLERANCIAS = "salud__intolerancias_alimentarias"
CAMPO_TIPO_DIETA = "nutricion__tipo_dieta"
CAMPO_RESTRICCIONES = "nutricion__restricciones"
CAMPO_NO_LE_GUSTA = "nutricion__alimentos_que_no_le_gustan"
CAMPO_INQUIETUD_PRINCIPAL = "nutricion__inquietud_principal"
CAMPO_COMIDAS_DIA = "nutricion__comidas_al_dia_preferidas"
CAMPO_CONTEXTO_NUTRICION = "nutricion__contexto"
CAMPO_HORAS_SUENO = "estilo_de_vida__horas_sueno_promedio"
CAMPO_ESTRES = "estilo_de_vida__nivel_estres_percibido"
CAMPO_TRABAJO = "estilo_de_vida__tipo_trabajo"
CAMPO_PASOS = "estilo_de_vida__pasos_diarios_aprox"
CAMPO_NOTAS_LIBRES = "notas_libres"

# All the radio-group field names, mapped to a stable marker so
# leer_intake_pdf() knows which fields are radios (value is the selected
# option's own string) vs. plain text fields (value is free text).
_CAMPOS_RADIO = {
    CAMPO_SEXO, CAMPO_OBJETIVO, CAMPO_NIVEL, CAMPO_NIVEL_COMPROMISO, CAMPO_LUGAR_ENTRENO, CAMPO_TIPO_DIETA,
    CAMPO_ESTRES,
}
_CAMPOS_ENTERO = {
    CAMPO_EDAD, CAMPO_DIAS_SEMANA, CAMPO_MINUTOS_SESION, CAMPO_COMIDAS_DIA, CAMPO_HORAS_SUENO, CAMPO_PASOS,
}
_CAMPOS_LISTA = {
    CAMPO_CONDICIONES, CAMPO_MEDICACION, CAMPO_SUPLEMENTOS, CAMPO_ALERGIAS, CAMPO_INTOLERANCIAS,
    CAMPO_RESTRICCIONES, CAMPO_NO_LE_GUSTA,
}


class _EscritorFormulario:
    """Small layout helper wrapping a reportlab canvas + acroForm: tracks a
    vertical cursor, adds an automatic page break when a field wouldn't
    fit, and resets font state after each break (reportlab's showPage()
    clears graphics state, including the font -- easy to forget and get a
    blank page). Keeps generar_pdf_intake() itself readable as a flat list
    of "add this field" calls instead of manual y-arithmetic repeated
    ~30 times."""

    def __init__(self, canvas_obj, margen=50):
        from reportlab.lib.pagesizes import letter

        self.c = canvas_obj
        self.form = canvas_obj.acroForm
        self.margen = margen
        self.ancho, self.alto_pagina = letter
        self.ancho_util = self.ancho - 2 * margen
        self.y = self.alto_pagina - margen
        self.c.setFont("Helvetica", 10)

    def _salto_si_necesario(self, alto_necesario):
        if self.y - alto_necesario < self.margen:
            self.c.showPage()
            self.y = self.alto_pagina - self.margen
            self.c.setFont("Helvetica", 10)

    def titulo(self, texto):
        self.c.setFont("Helvetica-Bold", 16)
        self.c.drawString(self.margen, self.y, texto)
        self.y -= 26
        self.c.setFont("Helvetica", 10)

    def seccion(self, texto):
        self._salto_si_necesario(34)
        self.c.setFont("Helvetica-Bold", 12)
        self.c.drawString(self.margen, self.y, texto)
        self.y -= 20
        self.c.setFont("Helvetica", 10)

    def texto(self, nombre_campo, etiqueta, multiline=False):
        alto_caja = 45 if multiline else 16
        self._salto_si_necesario(alto_caja + 24)
        self.c.drawString(self.margen, self.y, etiqueta)
        self.y -= 16
        self.form.textfield(
            name=nombre_campo, x=self.margen, y=self.y - alto_caja, width=self.ancho_util, height=alto_caja,
            borderStyle="solid", value="", fieldFlags="multiline" if multiline else "",
        )
        self.y -= alto_caja + 14

    def radio(self, nombre_campo, etiqueta, opciones):
        """opciones: list of (value, label) pairs."""
        self._salto_si_necesario(36)
        self.c.drawString(self.margen, self.y, etiqueta)
        self.y -= 18
        x = self.margen
        for valor, label in opciones:
            self.form.radio(name=nombre_campo, value=valor, x=x, y=self.y - 2, buttonStyle="circle", size=10, selected=False)
            self.c.drawString(x + 15, self.y, label)
            x += 15 + self.c.stringWidth(label, "Helvetica", 10) + 22
        self.y -= 24

    def checkbox_con_texto(self, campo_checkbox, etiqueta, campo_texto, etiqueta_texto):
        """A yes/no checkbox followed by a free-text field for detail --
        used for injury and pregnancy, where the checkbox is the
        safety-critical signal and the text is context for the trainer."""
        self._salto_si_necesario(80)
        self.form.checkbox(name=campo_checkbox, x=self.margen, y=self.y - 2, buttonStyle="check", borderStyle="solid", size=12, checked=False)
        self.c.drawString(self.margen + 20, self.y, etiqueta)
        self.y -= 18
        self.texto(campo_texto, etiqueta_texto, multiline=True)

    def casillas_multiples(self, prefijo, opciones):
        """opciones: list of (value, label) pairs, wrapped into rows that
        fit the page width."""
        self._salto_si_necesario(24)
        x = self.margen
        for valor, label in opciones:
            ancho_item = 16 + self.c.stringWidth(label, "Helvetica", 9) + 18
            if x + ancho_item > self.margen + self.ancho_util:
                x = self.margen
                self.y -= 20
                self._salto_si_necesario(20)
            self.form.checkbox(name=f"{prefijo}{valor}", x=x, y=self.y - 2, buttonStyle="check", borderStyle="solid", size=10, checked=False)
            self.c.setFont("Helvetica", 9)
            self.c.drawString(x + 14, self.y, label)
            self.c.setFont("Helvetica", 10)
            x += ancho_item
        self.y -= 24


def generar_pdf_intake(idioma: str = "en") -> bytes:
    """
    Renders a blank, fillable intake form mirroring
    admission/ficha_cliente_template.md -- a prospective client fills it
    in and emails it back; main.py's automated intake trigger reads it
    with leer_intake_pdf() and runs the full pipeline, no trainer typing
    required.

    Args:
        idioma: "en" (default) or "es" -- language of the printed labels.
            Field *names* never change with idioma -- leer_intake_pdf()
            reads them back by name, not by the label text next to them.

    Returns:
        The PDF file's raw bytes.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    if idioma == "es":
        t = {
            "titulo": "TrainFitter — Formulario de inscripción",
            "sec_basico": "1. Datos básicos",
            "nombre": "Nombre completo", "email": "Email", "edad": "Edad", "sexo": "Sexo",
            "peso": "Peso actual (kg)", "altura": "Altura (cm)",
            "sec_objetivo": "2. Objetivo",
            "objetivo": "Objetivo principal",
            "objetivo_texto": "Cuéntamelo con tus propias palabras (opcional)",
            "sec_experiencia": "3. Experiencia de entrenamiento",
            "nivel": "Nivel", "anios": "Años entrenando (aprox.)",
            "exp_detalle": "Cuéntame un poco más (opcional)",
            "nivel_compromiso": "¿Cuánto detalle quieres en el plan?",
            "sec_disponibilidad": "4. Disponibilidad",
            "dias": "Días disponibles por semana", "minutos": "Minutos por sesión",
            "lugar": "Dónde entrenarás", "material": "Material disponible",
            "sec_salud": "5. Salud",
            "lesion": "¿Alguna lesión (actual o antigua)?",
            "lesion_desc": "Descríbela (zona, qué pasó, si duele ahora)",
            "condiciones": "Enfermedades o condiciones (separadas por comas)",
            "embarazo": "¿Estás embarazada o en periodo de lactancia?",
            "embarazo_detalle": "Cuéntame en qué momento estás",
            "medicacion": "Medicación habitual (separada por comas)",
            "suplementos": "Suplementos que tomas ahora (separados por comas)",
            "alergias": "Alergias alimentarias (separadas por comas)",
            "intolerancias": "Intolerancias alimentarias (separadas por comas)",
            "sec_nutricion": "6. Nutrición",
            "tipo_dieta": "Tipo de dieta",
            "restricciones": "Restricciones adicionales (separadas por comas)",
            "no_gusta": "Alimentos que no te gustan (separados por comas)",
            "inquietud": "Enfoque o inquietud principal de dieta (opcional, ej. antiinflamatoria, bajar el gluten...)",
            "comidas": "Comidas al día preferidas",
            "contexto": "Tu contexto (cocinas tú, tiempo, presupuesto...)",
            "sec_estilo": "7. Estilo de vida",
            "sueno": "Horas de sueño promedio", "estres": "Nivel de estrés percibido",
            "trabajo": "Tipo de trabajo / día a día", "pasos": "Pasos diarios aprox.",
            "sec_notas": "8. Notas libres",
            "notas": "Cualquier otra cosa que quieras contarme",
        }
        opciones_sexo = [("mujer", "Mujer"), ("hombre", "Hombre")]
        opciones_objetivo = [
            ("hipertrofia", "Ganar músculo"), ("perdida_grasa", "Perder grasa"),
            ("recomposicion_corporal", "Recomposición"), ("salud_general", "Salud general"),
        ]
        opciones_nivel = [("principiante", "Principiante"), ("intermedio", "Intermedio"), ("avanzado", "Avanzado")]
        opciones_compromiso = [
            ("basico", "Básico (solo lo esencial)"), ("normal", "Normal"),
            ("avanzado", "Avanzado (más detalle)"), ("tryhard", "Tryhard (lo más completo)"),
        ]
        opciones_lugar = [
            ("gimnasio_completo", "Gimnasio completo"), ("gimnasio_pequeno", "Gimnasio pequeño"),
            ("casa_con_material", "Casa con material"), ("casa_sin_material", "Casa sin material"),
        ]
        opciones_material = [
            ("maquinas_guiadas", "Máquinas guiadas"), ("poleas", "Poleas"), ("barras_y_discos", "Barras y discos"),
            ("mancuernas", "Mancuernas"), ("bancos", "Bancos"), ("bicicleta_estatica", "Bicicleta estática"),
        ]
        opciones_dieta = [("omnivora", "Omnívora"), ("vegetariana_ovolacto", "Vegetariana"), ("vegana", "Vegana")]
        opciones_estres = [("bajo", "Bajo"), ("medio", "Medio"), ("alto", "Alto")]
    else:
        t = {
            "titulo": "TrainFitter — Client Intake Form",
            "sec_basico": "1. Basic info",
            "nombre": "Full name", "email": "Email", "edad": "Age", "sexo": "Sex",
            "peso": "Current weight (kg)", "altura": "Height (cm)",
            "sec_objetivo": "2. Goal",
            "objetivo": "Main goal",
            "objetivo_texto": "Tell me in your own words (optional)",
            "sec_experiencia": "3. Training experience",
            "nivel": "Level", "anios": "Years training (approx.)",
            "exp_detalle": "Tell me a bit more (optional)",
            "nivel_compromiso": "How much detail do you want in the plan?",
            "sec_disponibilidad": "4. Availability",
            "dias": "Days available per week", "minutos": "Minutes per session",
            "lugar": "Where you'll train", "material": "Available equipment",
            "sec_salud": "5. Health",
            "lesion": "Any injury (current or old)?",
            "lesion_desc": "Describe it (area, what happened, if it hurts now)",
            "condiciones": "Diseases or conditions (comma-separated)",
            "embarazo": "Are you pregnant or breastfeeding?",
            "embarazo_detalle": "Tell me where you're at",
            "medicacion": "Regular medication (comma-separated)",
            "suplementos": "Supplements you currently take (comma-separated)",
            "alergias": "Food allergies (comma-separated)",
            "intolerancias": "Food intolerances (comma-separated)",
            "sec_nutricion": "6. Nutrition",
            "tipo_dieta": "Diet type",
            "restricciones": "Additional restrictions (comma-separated)",
            "no_gusta": "Foods you don't like (comma-separated)",
            "inquietud": "Main dietary concern or approach (optional, e.g. anti-inflammatory, lower gluten...)",
            "comidas": "Preferred meals per day",
            "contexto": "Your context (do you cook, time, budget...)",
            "sec_estilo": "7. Lifestyle",
            "sueno": "Average sleep hours", "estres": "Perceived stress level",
            "trabajo": "Type of job / day-to-day", "pasos": "Approx. daily steps",
            "sec_notas": "8. Free notes",
            "notas": "Anything else you'd like to share",
        }
        opciones_sexo = [("mujer", "Female"), ("hombre", "Male")]
        opciones_objetivo = [
            ("hipertrofia", "Build muscle"), ("perdida_grasa", "Lose fat"),
            ("recomposicion_corporal", "Recomposition"), ("salud_general", "General health"),
        ]
        opciones_nivel = [("principiante", "Beginner"), ("intermedio", "Intermediate"), ("avanzado", "Advanced")]
        opciones_compromiso = [
            ("basico", "Basic (essentials only)"), ("normal", "Normal"),
            ("avanzado", "Advanced (more detail)"), ("tryhard", "Tryhard (most complete)"),
        ]
        opciones_lugar = [
            ("gimnasio_completo", "Full gym"), ("gimnasio_pequeno", "Small gym"),
            ("casa_con_material", "Home with equipment"), ("casa_sin_material", "Home, no equipment"),
        ]
        opciones_material = [
            ("maquinas_guiadas", "Guided machines"), ("poleas", "Cables"), ("barras_y_discos", "Barbell & plates"),
            ("mancuernas", "Dumbbells"), ("bancos", "Benches"), ("bicicleta_estatica", "Stationary bike"),
        ]
        opciones_dieta = [("omnivora", "Omnivore"), ("vegetariana_ovolacto", "Vegetarian"), ("vegana", "Vegan")]
        opciones_estres = [("bajo", "Low"), ("medio", "Medium"), ("alto", "High")]

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    f = _EscritorFormulario(c)

    f.titulo(t["titulo"])

    f.seccion(t["sec_basico"])
    f.texto(CAMPO_NOMBRE, t["nombre"])
    f.texto(CAMPO_EMAIL, t["email"])
    f.texto(CAMPO_EDAD, t["edad"])
    f.radio(CAMPO_SEXO, t["sexo"], opciones_sexo)
    f.texto(CAMPO_PESO, t["peso"])
    f.texto(CAMPO_ALTURA, t["altura"])

    f.seccion(t["sec_objetivo"])
    f.radio(CAMPO_OBJETIVO, t["objetivo"], opciones_objetivo)
    f.texto(CAMPO_OBJETIVO_TEXTO, t["objetivo_texto"], multiline=True)
    # Lives here, not in "Training experience" below -- it's about how
    # much detail/guidance the GOAL should come with, not about training
    # background. Moved per direct request; see ui/app.py's matching move.
    f.radio(CAMPO_NIVEL_COMPROMISO, t["nivel_compromiso"], opciones_compromiso)

    f.seccion(t["sec_experiencia"])
    f.radio(CAMPO_NIVEL, t["nivel"], opciones_nivel)
    f.texto(CAMPO_ANIOS_ENTRENANDO, t["anios"])
    f.texto(CAMPO_EXPERIENCIA_DETALLE, t["exp_detalle"], multiline=True)

    f.seccion(t["sec_disponibilidad"])
    f.texto(CAMPO_DIAS_SEMANA, t["dias"])
    f.texto(CAMPO_MINUTOS_SESION, t["minutos"])
    f.radio(CAMPO_LUGAR_ENTRENO, t["lugar"], opciones_lugar)
    f.casillas_multiples(PREFIJO_MATERIAL, opciones_material)

    f.seccion(t["sec_salud"])
    f.checkbox_con_texto(CAMPO_TIENE_LESION, t["lesion"], CAMPO_LESION_DESCRIPCION, t["lesion_desc"])
    f.texto(CAMPO_CONDICIONES, t["condiciones"])
    f.checkbox_con_texto(CAMPO_EMBARAZO, t["embarazo"], CAMPO_EMBARAZO_DETALLE, t["embarazo_detalle"])
    f.texto(CAMPO_MEDICACION, t["medicacion"])
    f.texto(CAMPO_SUPLEMENTOS, t["suplementos"])
    f.texto(CAMPO_ALERGIAS, t["alergias"])
    f.texto(CAMPO_INTOLERANCIAS, t["intolerancias"])

    f.seccion(t["sec_nutricion"])
    f.radio(CAMPO_TIPO_DIETA, t["tipo_dieta"], opciones_dieta)
    f.texto(CAMPO_RESTRICCIONES, t["restricciones"])
    f.texto(CAMPO_NO_LE_GUSTA, t["no_gusta"])
    f.texto(CAMPO_INQUIETUD_PRINCIPAL, t["inquietud"])
    f.texto(CAMPO_COMIDAS_DIA, t["comidas"])
    f.texto(CAMPO_CONTEXTO_NUTRICION, t["contexto"], multiline=True)

    f.seccion(t["sec_estilo"])
    f.texto(CAMPO_HORAS_SUENO, t["sueno"])
    f.radio(CAMPO_ESTRES, t["estres"], opciones_estres)
    f.texto(CAMPO_TRABAJO, t["trabajo"])
    f.texto(CAMPO_PASOS, t["pasos"])

    f.seccion(t["sec_notas"])
    f.texto(CAMPO_NOTAS_LIBRES, t["notas"], multiline=True)

    c.save()
    return buffer.getvalue()


def es_intake_pdf(contenido_pdf: bytes) -> bool:
    """Whether a PDF attachment looks like this project's own intake form
    -- same field-based detection approach as
    pdf_generador.es_checklist_pdf(), used by gmail_client.py to identify
    a new-client submission."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        campos = PdfReader(io.BytesIO(contenido_pdf)).get_fields() or {}
    except PdfReadError:
        return False
    return CAMPO_NOMBRE in campos and CAMPO_OBJETIVO in campos


def _valor_campo(campos: dict, nombre: str) -> str:
    valor = (campos.get(nombre) or {}).get("/V") or ""
    return str(valor).lstrip("/").strip()


def _lista_desde_texto(texto: str) -> list[str]:
    """Same convention as ui/app.py's own _lista_desde_texto() for the
    identical comma-separated free-text fields -- mirrored here rather
    than reinvented, so a value typed in the PDF form behaves exactly
    like the same field typed into the manual panel."""
    if not texto:
        return []
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


def leer_intake_pdf(contenido_pdf: bytes) -> dict:
    """
    Reads a filled-in intake PDF's form field values back into a
    perfil_cliente dict -- the schema agents/orchestrator.py's
    ejecutar_pipeline() expects. Best-effort on numeric fields (a blank
    or non-numeric answer becomes 0 rather than raising -- an incomplete
    intake shouldn't crash the automated trigger; the trainer reviewing
    the result will notice an implausible 0 easily enough).

    Does NOT set id_cliente or fecha_admision -- the caller (main.py)
    assigns those, since this function has no natural source for either
    (there's no client ID yet, and "today" isn't this module's business
    to decide).

    Args:
        contenido_pdf: raw PDF bytes (see
            mcp.gmail_client.buscar_intakes_nuevos()).

    Returns:
        A perfil_cliente-shaped dict (missing id_cliente/fecha_admision).
    """
    from pypdf import PdfReader

    campos = PdfReader(io.BytesIO(contenido_pdf)).get_fields() or {}

    def entero(nombre: str, por_defecto: int = 0) -> int:
        valor = _valor_campo(campos, nombre)
        try:
            return int(float(valor))
        except ValueError:
            return por_defecto

    def flotante(nombre: str, por_defecto: float = 0.0) -> float:
        valor = _valor_campo(campos, nombre)
        try:
            return float(valor)
        except ValueError:
            return por_defecto

    def marcado(nombre: str) -> bool:
        return _valor_campo(campos, nombre).lower() == "yes"

    material_disponible = [
        opcion for opcion in MATERIAL_OPCIONES if marcado(f"{PREFIJO_MATERIAL}{opcion}")
    ]

    lesiones = []
    if marcado(CAMPO_TIENE_LESION):
        lesiones.append({
            "zona": "",
            "descripcion": _valor_campo(campos, CAMPO_LESION_DESCRIPCION),
            "estado": "activa",
            "activa_actualmente": True,
        })

    return {
        "datos_basicos": {
            "nombre": _valor_campo(campos, CAMPO_NOMBRE),
            "email": _valor_campo(campos, CAMPO_EMAIL),
            "edad": entero(CAMPO_EDAD),
            "sexo": _valor_campo(campos, CAMPO_SEXO) or "hombre",
            "peso_kg": flotante(CAMPO_PESO),
            "altura_cm": flotante(CAMPO_ALTURA),
        },
        "objetivo": {
            "principal": _valor_campo(campos, CAMPO_OBJETIVO) or "salud_general",
            "en_sus_palabras": _valor_campo(campos, CAMPO_OBJETIVO_TEXTO),
        },
        "experiencia": {
            "nivel": _valor_campo(campos, CAMPO_NIVEL) or "principiante",
            "nivel_compromiso": _valor_campo(campos, CAMPO_NIVEL_COMPROMISO) or "normal",
            "anios_entrenando": flotante(CAMPO_ANIOS_ENTRENANDO),
            "detalle": _valor_campo(campos, CAMPO_EXPERIENCIA_DETALLE),
        },
        "disponibilidad": {
            "dias_por_semana": entero(CAMPO_DIAS_SEMANA, por_defecto=3),
            "minutos_por_sesion": entero(CAMPO_MINUTOS_SESION, por_defecto=45),
            "lugar_entreno": _valor_campo(campos, CAMPO_LUGAR_ENTRENO) or "gimnasio_completo",
            "material_disponible": material_disponible,
        },
        "salud": {
            "lesiones": lesiones,
            "enfermedades_o_condiciones": _lista_desde_texto(_valor_campo(campos, CAMPO_CONDICIONES)),
            "embarazo_o_lactancia": {
                "aplica": marcado(CAMPO_EMBARAZO),
                "detalle": _valor_campo(campos, CAMPO_EMBARAZO_DETALLE),
            },
            "medicacion_habitual": _lista_desde_texto(_valor_campo(campos, CAMPO_MEDICACION)),
            "suplementos_actuales": _lista_desde_texto(_valor_campo(campos, CAMPO_SUPLEMENTOS)),
            "alergias_alimentarias": _lista_desde_texto(_valor_campo(campos, CAMPO_ALERGIAS)),
            "intolerancias_alimentarias": _lista_desde_texto(_valor_campo(campos, CAMPO_INTOLERANCIAS)),
            "analitica_adjunta": {"tiene": False, "archivo": None, "fecha": None, "notas": ""},
        },
        "nutricion": {
            "tipo_dieta": _valor_campo(campos, CAMPO_TIPO_DIETA) or "omnivora",
            "restricciones": _lista_desde_texto(_valor_campo(campos, CAMPO_RESTRICCIONES)),
            "alimentos_que_no_le_gustan": _lista_desde_texto(_valor_campo(campos, CAMPO_NO_LE_GUSTA)),
            "inquietud_principal": _valor_campo(campos, CAMPO_INQUIETUD_PRINCIPAL),
            "comidas_al_dia_preferidas": entero(CAMPO_COMIDAS_DIA, por_defecto=4),
            "contexto": _valor_campo(campos, CAMPO_CONTEXTO_NUTRICION),
        },
        "estilo_de_vida": {
            "horas_sueno_promedio": flotante(CAMPO_HORAS_SUENO, por_defecto=7),
            "nivel_estres_percibido": _valor_campo(campos, CAMPO_ESTRES) or "medio",
            "tipo_trabajo": _valor_campo(campos, CAMPO_TRABAJO),
            "pasos_diarios_aprox": entero(CAMPO_PASOS),
        },
        "notas_libres": _valor_campo(campos, CAMPO_NOTAS_LIBRES),
    }
