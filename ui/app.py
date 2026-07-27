"""
Trainer's panel — TrainFitter's Streamlit interface.

Turns the pipeline (previously only accessible via CLI) into something a
non-technical trainer could use: pick or create an intake, generate the
plan, watch the state trail live, review routine + diet, and "approve"
(simulated — real sending arrives with Gmail integration).

Includes an EN/ES language toggle for the UI chrome (labels, buttons, help
text). The generated plan content itself (exercise names, messages) is
produced in English by the underlying rule engine regardless of the UI
language — see docs/decisiones.md for that scoping decision.

How to run it (from the repo root):
    pip install streamlit
    streamlit run ui/app.py
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
EXAMPLES_DIR = REPO_ROOT / "examples"

# agents/ modules import each other as "flat" packages (import knowledge,
# import routine_agent...), so they need agents/ on sys.path just like when
# their own run_*_demo.py scripts are executed.
sys.path.insert(0, str(AGENTS_DIR))

from orchestrator import ejecutar_pipeline  # noqa: E402

st.set_page_config(
    page_title="TrainFitter",
    page_icon="💪",
    layout="wide",
)

# ---------------------------------------------------------------------------
# i18n — UI chrome translations (EN default, ES available via the toggle)
# ---------------------------------------------------------------------------

TRANSLATIONS = {
    "en": {
        "app_title": "💪 TrainFitter — Trainer's panel",
        "app_motto": '"Teach your body that your mind is in charge."',
        "app_intro": (
            "Generate a draft routine and diet from a client's intake. "
            "**Everything you see here is a draft**: nothing is sent without your approval."
        ),
        "lang_picker_label": "🌐 Language / Idioma",
        "tab_example": "📋 Example client",
        "tab_new_intake": "📝 New intake",
        "sec_basic_info": "1. Basic info",
        "full_name": "Full name",
        "age": "Age",
        "sex": "Sex",
        "weight_kg": "Current weight (kg)",
        "height_cm": "Height (cm)",
        "sec_goal": "2. Goal",
        "goal_main": "Main goal",
        "goal_in_words": "In their own words (optional)",
        "sec_experience": "3. Training experience",
        "level": "Level",
        "years_training": "Years training (approx.)",
        "experience_details": "Details on their experience (optional)",
        "sec_availability": "4. Availability",
        "days_per_week": "Days available per week",
        "minutes_per_session": "Minutes per session",
        "training_location": "Where they train",
        "available_equipment": "Available equipment",
        "sec_health": "5. Health",
        "sec_health_caption": "None of this closes any doors — the more we know, the better we can look after the plan.",
        "has_injury": "Do they have any injury (current or old)?",
        "injury_area": "Injury area (e.g. left knee)",
        "injury_description": "Description (what happened, whether it currently hurts)",
        "injury_status": "Status",
        "conditions": "Diseases or conditions (comma-separated)",
        "medications": "Regular medication (comma-separated)",
        "pregnant_label": "Are they pregnant or breastfeeding?",
        "detail_label": "Detail",
        "allergies": "Food allergies (comma-separated)",
        "intolerances": "Food intolerances (comma-separated)",
        "bloodwork_upload": "Bloodwork (PDF, optional)",
        "sec_nutrition": "6. Nutrition",
        "diet_type": "Diet type",
        "additional_restrictions": "Additional restrictions (comma-separated)",
        "disliked_foods": "Foods they don't like (comma-separated)",
        "meals_per_day": "Preferred meals per day",
        "nutrition_context": "Context (cooking, time, budget...)",
        "sec_lifestyle": "7. Lifestyle",
        "avg_sleep": "Average sleep hours",
        "stress_level": "Perceived stress level",
        "daily_steps": "Approx. daily steps",
        "job_type": "Type of job / day-to-day",
        "sec_notes": "8. Free notes",
        "other_notes": "Anything else they'd like to share",
        "submit_button": "Create intake and generate plan",
        "name_required_error": "Name is required.",
        "no_example_clients": "No example clients in examples/.",
        "example_client_label": "Example client",
        "view_full_intake": "View full intake (JSON)",
        "generate_plan_button": "Generate plan for this client",
        "generating_status": "Generating the plan...",
        "plan_generated_status": "Plan generated",
        "plan_error_status": "Error generating the plan",
        "could_not_generate": "Could not generate the plan: {error}",
        "enhanced_review_warning": "⚠️ **Enhanced review** — this case needs your attention before approving.",
        "no_review_reasons_success": (
            "✅ **No reasons for enhanced review.** It still needs your approval "
            "before sending — TrainFitter never sends anything on its own."
        ),
        "routine_header": "### 🏋️ Routine",
        "split_label": "**Split:**",
        "days_week_label": "**Days/week:**",
        "duration_label": "**Duration:**",
        "col_exercise": "Exercise",
        "col_sets": "Sets",
        "col_reps": "Reps",
        "col_rest": "Rest",
        "col_notes": "Notes",
        "cardio_label": "Cardio:",
        "progression_and_message": "Progression and message for the client",
        "progression_label": "**Progression:**",
        "for_client_label": "**For the client:**",
        "download_routine": "Download routine (JSON)",
        "diet_header": "### 🍽️ Diet",
        "kcal_day": "Kcal/day",
        "protein_label": "Protein",
        "fat_label": "Fat",
        "carbs_label": "Carbohydrates",
        "protein_sources_label": "**Protein**\n",
        "carb_sources_label": "**Carbohydrate**\n",
        "fat_sources_label": "**Fat**\n",
        "synergy_tips_header": "Nutritional synergy tips",
        "client_message_header": "Message for the client",
        "download_diet": "Download diet (JSON)",
        "approval_header": "### Trainer's approval",
        "approval_caption": (
            "This button simulates your approval within this demo. Actually sending it to the "
            "client (an email draft) arrives with Gmail integration — not implemented yet."
        ),
        "approve_button": "✅ Approve and mark as ready to send",
        "approved_success": (
            "Marked as approved at {time}. In a version connected to Gmail, this would leave an "
            "email draft waiting for you to send manually."
        ),
    },
    "es": {
        "app_title": "💪 TrainFitter — Panel del entrenador",
        "app_motto": '"Enseña a tu cuerpo que quien manda es tu mente."',
        "app_intro": (
            "Genera un borrador de rutina y dieta a partir de la ficha de un cliente. "
            "**Todo lo que ves aquí es un borrador**: nada se envía sin tu aprobación."
        ),
        "lang_picker_label": "🌐 Language / Idioma",
        "tab_example": "📋 Cliente de ejemplo",
        "tab_new_intake": "📝 Nueva ficha",
        "sec_basic_info": "1. Datos básicos",
        "full_name": "Nombre completo",
        "age": "Edad",
        "sex": "Sexo",
        "weight_kg": "Peso actual (kg)",
        "height_cm": "Altura (cm)",
        "sec_goal": "2. Objetivo",
        "goal_main": "Objetivo principal",
        "goal_in_words": "En sus propias palabras (opcional)",
        "sec_experience": "3. Experiencia entrenando",
        "level": "Nivel",
        "years_training": "Años entrenando (aprox.)",
        "experience_details": "Detalle de su experiencia (opcional)",
        "sec_availability": "4. Disponibilidad",
        "days_per_week": "Días disponibles a la semana",
        "minutes_per_session": "Minutos por sesión",
        "training_location": "Dónde entrena",
        "available_equipment": "Material disponible",
        "sec_health": "5. Salud",
        "sec_health_caption": "Nada de esto le cierra puertas — cuanto más sepamos, mejor podemos cuidar el plan.",
        "has_injury": "¿Tiene alguna lesión (actual o antigua)?",
        "injury_area": "Zona de la lesión (p. ej. rodilla izquierda)",
        "injury_description": "Descripción (qué pasó, si duele actualmente)",
        "injury_status": "Estado",
        "conditions": "Enfermedades o condiciones (separadas por coma)",
        "medications": "Medicación habitual (separada por coma)",
        "pregnant_label": "¿Está embarazada o en periodo de lactancia?",
        "detail_label": "Detalle",
        "allergies": "Alergias alimentarias (separadas por coma)",
        "intolerances": "Intolerancias alimentarias (separadas por coma)",
        "bloodwork_upload": "Analítica de sangre (PDF, opcional)",
        "sec_nutrition": "6. Alimentación",
        "diet_type": "Tipo de dieta",
        "additional_restrictions": "Restricciones adicionales (coma)",
        "disliked_foods": "Alimentos que no le gustan (coma)",
        "meals_per_day": "Comidas al día preferidas",
        "nutrition_context": "Contexto (cocina, tiempo, presupuesto...)",
        "sec_lifestyle": "7. Estilo de vida",
        "avg_sleep": "Horas de sueño promedio",
        "stress_level": "Nivel de estrés percibido",
        "daily_steps": "Pasos diarios aprox.",
        "job_type": "Tipo de trabajo / día a día",
        "sec_notes": "8. Notas libres",
        "other_notes": "Cualquier otra cosa que quiera contarnos",
        "submit_button": "Crear ficha y generar plan",
        "name_required_error": "El nombre es obligatorio.",
        "no_example_clients": "No hay clientes de ejemplo en examples/.",
        "example_client_label": "Cliente de ejemplo",
        "view_full_intake": "Ver ficha completa (JSON)",
        "generate_plan_button": "Generar plan para este cliente",
        "generating_status": "Generando el plan...",
        "plan_generated_status": "Plan generado",
        "plan_error_status": "Error al generar el plan",
        "could_not_generate": "No se pudo generar el plan: {error}",
        "enhanced_review_warning": "⚠️ **Revisión reforzada** — este caso necesita tu atención antes de aprobar.",
        "no_review_reasons_success": (
            "✅ **Sin motivos de revisión reforzada.** Aun así, sigue esperando tu aprobación "
            "antes de enviarse — TrainFitter nunca envía nada por su cuenta."
        ),
        "routine_header": "### 🏋️ Rutina",
        "split_label": "**Split:**",
        "days_week_label": "**Días/semana:**",
        "duration_label": "**Duración:**",
        "col_exercise": "Ejercicio",
        "col_sets": "Series",
        "col_reps": "Reps",
        "col_rest": "Descanso",
        "col_notes": "Notas",
        "cardio_label": "Cardio:",
        "progression_and_message": "Progresión y mensaje para el cliente",
        "progression_label": "**Progresión:**",
        "for_client_label": "**Para el cliente:**",
        "download_routine": "Descargar rutina (JSON)",
        "diet_header": "### 🍽️ Dieta",
        "kcal_day": "Kcal/día",
        "protein_label": "Proteína",
        "fat_label": "Grasa",
        "carbs_label": "Carbohidratos",
        "protein_sources_label": "**Proteína**\n",
        "carb_sources_label": "**Carbohidrato**\n",
        "fat_sources_label": "**Grasa**\n",
        "synergy_tips_header": "Consejos de sinergias nutricionales",
        "client_message_header": "Mensaje para el cliente",
        "download_diet": "Descargar dieta (JSON)",
        "approval_header": "### Aprobación del entrenador",
        "approval_caption": (
            "Este botón simula tu aprobación dentro de esta demo. El envío real al cliente "
            "(borrador de email) llega con la integración de Gmail — todavía no implementada."
        ),
        "approve_button": "✅ Aprobar y marcar como listo para enviar",
        "approved_success": (
            "Marcado como aprobado a las {time}. En una versión conectada a Gmail, esto dejaría "
            "un borrador de email esperando tu envío manual."
        ),
    },
}

# Labels for schema values (which stay in Spanish internally — see
# docs/decisiones.md) shown to the user in either language via format_func.
OPTION_LABELS = {
    "en": {
        "mujer": "Female", "hombre": "Male",
        "hipertrofia": "Build muscle (hypertrophy)", "perdida_grasa": "Lose fat",
        "recomposicion_corporal": "Recomposition (lose fat & build muscle)", "salud_general": "General health",
        "principiante": "Beginner", "intermedio": "Intermediate", "avanzado": "Advanced",
        "gimnasio_completo": "Full gym", "gimnasio_pequeno": "Small gym / limited equipment",
        "casa_con_material": "Home with some equipment", "casa_sin_material": "Home with no equipment",
        "maquinas_guiadas": "Guided machines", "poleas": "Cables", "barras_y_discos": "Barbell & plates",
        "mancuernas": "Dumbbells", "bancos": "Benches", "bicicleta_estatica": "Stationary bike",
        "antigua_controlada": "Old, under control", "activa": "Active",
        "omnivora": "Omnivorous", "vegetariana_ovolacto": "Vegetarian", "vegana": "Vegan",
        "bajo": "Low", "medio": "Medium", "alto": "High",
    },
    "es": {
        "mujer": "Mujer", "hombre": "Hombre",
        "hipertrofia": "Ganar músculo (hipertrofia)", "perdida_grasa": "Perder grasa",
        "recomposicion_corporal": "Recomposición (perder grasa y ganar músculo)", "salud_general": "Salud general",
        "principiante": "Principiante", "intermedio": "Intermedio", "avanzado": "Avanzado",
        "gimnasio_completo": "Gimnasio completo", "gimnasio_pequeno": "Gimnasio pequeño / material limitado",
        "casa_con_material": "Casa con algo de material", "casa_sin_material": "Casa sin material",
        "maquinas_guiadas": "Máquinas guiadas", "poleas": "Poleas", "barras_y_discos": "Barras y discos",
        "mancuernas": "Mancuernas", "bancos": "Bancos", "bicicleta_estatica": "Bicicleta estática",
        "antigua_controlada": "Antigua, controlada", "activa": "Activa",
        "omnivora": "Omnívora", "vegetariana_ovolacto": "Vegetariana", "vegana": "Vegana",
        "bajo": "Bajo", "medio": "Medio", "alto": "Alto",
    },
}

ETIQUETAS_ESTADO = {
    "en": {
        "rutina_generada": "Routine generated",
        "dieta_generada": "Diet generated",
        "validado": "Validated",
        "pendiente_aprobacion_humana": "Ready for your approval",
        "pendiente_revision_reforzada": "Needs enhanced review",
        "error": "Error generating the plan",
    },
    "es": {
        "rutina_generada": "Rutina generada",
        "dieta_generada": "Dieta generada",
        "validado": "Validado",
        "pendiente_aprobacion_humana": "Listo para tu aprobación",
        "pendiente_revision_reforzada": "Necesita revisión reforzada",
        "error": "Error al generar el plan",
    },
}

if "lang" not in st.session_state:
    st.session_state.lang = "en"


def t(key: str) -> str:
    return TRANSLATIONS[st.session_state.lang][key]


def opt(key: str) -> str:
    return OPTION_LABELS[st.session_state.lang].get(key, key)


OBJETIVOS = ["hipertrofia", "perdida_grasa", "recomposicion_corporal", "salud_general"]
MATERIAL_OPCIONES = [
    "maquinas_guiadas", "poleas", "barras_y_discos", "mancuernas", "bancos", "bicicleta_estatica",
]


def _lista_desde_texto(texto: str) -> list[str]:
    """'a, b,, c' -> ['a', 'b', 'c']. Empty or blank -> []."""
    if not texto:
        return []
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "cliente"


# ---------------------------------------------------------------------------
# Building the profile from the new-intake form
# ---------------------------------------------------------------------------

def _formulario_ficha_nueva() -> dict | None:
    # st.form is deliberately NOT used here: inside a form, Streamlit doesn't
    # rerun the script until the submit button is pressed, so a checkbox
    # ("has an injury?") can't reveal conditional fields — manual testing
    # confirmed that with st.form, the "injury area" field never showed up.
    # With standalone widgets, every interaction reruns the script and the
    # UI can react immediately.
    st.subheader(t("sec_basic_info"))
    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input(t("full_name"), key="nombre")
    edad = c2.number_input(t("age"), min_value=14, max_value=100, value=30, key="edad")
    sexo = c3.selectbox(t("sex"), ["mujer", "hombre"], format_func=opt, key="sexo")
    c4, c5 = st.columns(2)
    peso_kg = c4.number_input(t("weight_kg"), min_value=30.0, max_value=250.0, value=70.0, step=0.5, key="peso")
    altura_cm = c5.number_input(t("height_cm"), min_value=120, max_value=230, value=170, key="altura")

    st.subheader(t("sec_goal"))
    principal = st.selectbox(t("goal_main"), OBJETIVOS, format_func=opt, key="objetivo")
    en_sus_palabras = st.text_area(t("goal_in_words"), key="en_sus_palabras")

    st.subheader(t("sec_experience"))
    c6, c7 = st.columns(2)
    nivel = c6.selectbox(t("level"), ["principiante", "intermedio", "avanzado"], format_func=opt, key="nivel")
    anios_entrenando = c7.number_input(t("years_training"), min_value=0.0, max_value=50.0, value=0.5, step=0.5, key="anios")
    detalle_experiencia = st.text_area(t("experience_details"), key="detalle_experiencia")

    st.subheader(t("sec_availability"))
    c8, c9 = st.columns(2)
    dias_por_semana = c8.slider(t("days_per_week"), 1, 6, 4, key="dias")
    minutos_por_sesion = c9.number_input(t("minutes_per_session"), min_value=15, max_value=180, value=60, step=5, key="minutos")
    lugar_entreno = st.selectbox(
        t("training_location"),
        ["gimnasio_completo", "gimnasio_pequeno", "casa_con_material", "casa_sin_material"],
        format_func=opt,
        key="lugar_entreno",
    )
    material_disponible = st.multiselect(t("available_equipment"), MATERIAL_OPCIONES, default=MATERIAL_OPCIONES, format_func=opt, key="material")

    st.subheader(t("sec_health"))
    st.caption(t("sec_health_caption"))
    tiene_lesion = st.checkbox(t("has_injury"), key="tiene_lesion")
    zona_lesion = descripcion_lesion = ""
    estado_lesion = "antigua_controlada"
    if tiene_lesion:
        zona_lesion = st.text_input(t("injury_area"), key="zona_lesion")
        descripcion_lesion = st.text_area(t("injury_description"), key="descripcion_lesion")
        estado_lesion = st.selectbox(t("injury_status"), ["antigua_controlada", "activa"], format_func=opt, key="estado_lesion")

    c10, c11 = st.columns(2)
    enfermedades_texto = c10.text_input(t("conditions"), key="enfermedades")
    medicacion_texto = c11.text_input(t("medications"), key="medicacion")

    embarazo = st.checkbox(t("pregnant_label"), key="embarazo")
    detalle_embarazo = st.text_input(t("detail_label"), key="detalle_embarazo") if embarazo else ""

    c12, c13 = st.columns(2)
    alergias_texto = c12.text_input(t("allergies"), key="alergias")
    intolerancias_texto = c13.text_input(t("intolerances"), key="intolerancias")

    analitica_pdf = st.file_uploader(t("bloodwork_upload"), type=["pdf"], key="analitica")

    st.subheader(t("sec_nutrition"))
    tipo_dieta = st.selectbox(t("diet_type"), ["omnivora", "vegetariana_ovolacto", "vegana"], format_func=opt, key="tipo_dieta")
    c14, c15 = st.columns(2)
    restricciones_texto = c14.text_input(t("additional_restrictions"), key="restricciones")
    no_le_gustan_texto = c15.text_input(t("disliked_foods"), key="no_le_gustan")
    comidas_al_dia = st.number_input(t("meals_per_day"), min_value=2, max_value=6, value=4, key="comidas")
    contexto_nutricion = st.text_area(t("nutrition_context"), key="contexto")

    st.subheader(t("sec_lifestyle"))
    c16, c17, c18 = st.columns(3)
    horas_sueno = c16.number_input(t("avg_sleep"), min_value=3.0, max_value=12.0, value=7.0, step=0.5, key="sueno")
    estres = c17.selectbox(t("stress_level"), ["bajo", "medio", "alto"], format_func=opt, key="estres")
    pasos = c18.number_input(t("daily_steps"), min_value=0, max_value=30000, value=6000, step=500, key="pasos")
    tipo_trabajo = st.text_input(t("job_type"), key="tipo_trabajo")

    st.subheader(t("sec_notes"))
    notas_libres = st.text_area(t("other_notes"), key="notas_libres")

    enviado = st.button(t("submit_button"), type="primary", key="enviar_ficha")

    if not enviado:
        return None

    if not nombre.strip():
        st.error(t("name_required_error"))
        return None

    ahora = datetime.now(timezone.utc)
    perfil = {
        "id_cliente": f"cliente_ui_{_slug(nombre)}",
        "fecha_admision": ahora.date().isoformat(),
        "datos_basicos": {
            "nombre": nombre.strip(),
            "edad": int(edad),
            "sexo": sexo,
            "peso_kg": float(peso_kg),
            "altura_cm": float(altura_cm),
        },
        "objetivo": {"principal": principal, "en_sus_palabras": en_sus_palabras.strip()},
        "experiencia": {
            "nivel": nivel,
            "anios_entrenando": float(anios_entrenando),
            "detalle": detalle_experiencia.strip(),
        },
        "disponibilidad": {
            "dias_por_semana": int(dias_por_semana),
            "minutos_por_sesion": int(minutos_por_sesion),
            "lugar_entreno": lugar_entreno,
            "material_disponible": material_disponible,
        },
        "salud": {
            "lesiones": (
                [{
                    "zona": zona_lesion.strip() or "not specified",
                    "descripcion": descripcion_lesion.strip(),
                    "estado": estado_lesion,
                    "activa_actualmente": estado_lesion == "activa",
                }] if tiene_lesion else []
            ),
            "enfermedades_o_condiciones": _lista_desde_texto(enfermedades_texto),
            "embarazo_o_lactancia": {"aplica": embarazo, "detalle": detalle_embarazo.strip()},
            "medicacion_habitual": _lista_desde_texto(medicacion_texto),
            "alergias_alimentarias": _lista_desde_texto(alergias_texto),
            "intolerancias_alimentarias": _lista_desde_texto(intolerancias_texto),
            "analitica_adjunta": {
                "tiene": analitica_pdf is not None,
                "archivo": analitica_pdf.name if analitica_pdf is not None else None,
                "fecha": ahora.date().isoformat() if analitica_pdf is not None else None,
                "notas": "",
            },
        },
        "nutricion": {
            "tipo_dieta": tipo_dieta,
            "restricciones": _lista_desde_texto(restricciones_texto),
            "alimentos_que_no_le_gustan": _lista_desde_texto(no_le_gustan_texto),
            "comidas_al_dia_preferidas": int(comidas_al_dia),
            "contexto": contexto_nutricion.strip(),
        },
        "estilo_de_vida": {
            "horas_sueno_promedio": float(horas_sueno),
            "nivel_estres_percibido": estres,
            "tipo_trabajo": tipo_trabajo.strip(),
            "pasos_diarios_aprox": int(pasos),
        },
        "notas_libres": notas_libres.strip(),
    }
    return perfil


# ---------------------------------------------------------------------------
# Example client selection
# ---------------------------------------------------------------------------

def _selector_cliente_ejemplo() -> dict | None:
    rutas = sorted(EXAMPLES_DIR.glob("cliente_ejemplo_*.json")) + sorted(EXAMPLES_DIR.glob("cliente_prueba_*.json"))
    if not rutas:
        st.info(t("no_example_clients"))
        return None

    perfiles = {ruta.name: json.loads(ruta.read_text(encoding="utf-8")) for ruta in rutas}
    etiquetas = {
        nombre: f"{perfil['datos_basicos']['nombre']} ({nombre})" for nombre, perfil in perfiles.items()
    }
    seleccion = st.selectbox(t("example_client_label"), list(perfiles), format_func=lambda k: etiquetas[k])
    perfil = perfiles[seleccion]

    with st.expander(t("view_full_intake")):
        st.json(perfil)

    return perfil if st.button(t("generate_plan_button"), type="primary") else None


# ---------------------------------------------------------------------------
# Pipeline execution + result
# ---------------------------------------------------------------------------

def _ejecutar_y_mostrar(perfil: dict) -> None:
    with st.status(t("generating_status"), expanded=True) as status:
        def _al_transicionar(_cliente_id: str, nuevo_estado: str) -> None:
            status.write(f"✅ {ETIQUETAS_ESTADO[st.session_state.lang].get(nuevo_estado, nuevo_estado)}")

        estado = ejecutar_pipeline(perfil, on_transition=_al_transicionar)
        status.update(
            label=t("plan_generated_status") if not estado.error else t("plan_error_status"),
            state="error" if estado.error else "complete",
        )

    if estado.error:
        st.error(t("could_not_generate").format(error=estado.error))
        return

    st.divider()
    _mostrar_veredicto(estado.veredicto)

    col_rutina, col_dieta = st.columns(2)
    with col_rutina:
        _mostrar_rutina(estado.borrador_rutina)
    with col_dieta:
        _mostrar_dieta(estado.borrador_dieta)

    st.divider()
    _panel_aprobacion(estado)


def _mostrar_veredicto(veredicto: dict) -> None:
    if veredicto["veredicto"] == "revision_reforzada":
        st.warning(t("enhanced_review_warning"))
        for motivo in veredicto["motivos"]:
            st.markdown(f"- {motivo}")
    else:
        st.success(t("no_review_reasons_success"))


def _mostrar_rutina(rutina: dict) -> None:
    st.markdown(t("routine_header"))
    st.caption(rutina["resumen_enfoque"])
    st.markdown(
        f"{t('split_label')} {rutina['split'].replace('_', ' ')} · "
        f"{t('days_week_label')} {rutina['dias_por_semana']} · "
        f"{t('duration_label')} {rutina['duracion_sesion_min']} min"
    )

    for sesion in rutina["sesiones"]:
        with st.expander(sesion["dia"]):
            st.caption(sesion["calentamiento"])
            filas = [
                {
                    t("col_exercise"): e["nombre"],
                    t("col_sets"): e["series"],
                    t("col_reps"): e["repeticiones"],
                    t("col_rest"): f"{e['descanso_seg']}s",
                    t("col_notes"): e["notas"],
                }
                for e in sesion["ejercicios"]
            ]
            st.table(filas)
            if sesion.get("cardio_opcional"):
                st.caption(f"{t('cardio_label')} {sesion['cardio_opcional']}")

    with st.expander(t("progression_and_message")):
        st.markdown(f"{t('progression_label')} {rutina['progresion']}")
        st.markdown(f"{t('for_client_label')} {rutina['mensaje_para_el_cliente']}")

    st.download_button(
        t("download_routine"),
        data=json.dumps(rutina, ensure_ascii=False, indent=2),
        file_name="routine.json",
        mime="application/json",
    )


def _mostrar_dieta(dieta: dict) -> None:
    st.markdown(t("diet_header"))
    st.caption(dieta["resumen_enfoque"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t("kcal_day"), dieta["calorias_objetivo_kcal"])
    m2.metric(t("protein_label"), f"{dieta['macros']['proteina_g']} g")
    m3.metric(t("fat_label"), f"{dieta['macros']['grasa_g']} g")
    m4.metric(t("carbs_label"), f"{dieta['macros']['carbohidratos_g']} g")

    st.caption(dieta["distribucion_comidas"])

    c1, c2, c3 = st.columns(3)
    c1.markdown(t("protein_sources_label") + "\n".join(f"- {f}" for f in dieta["fuentes_proteina_sugeridas"]))
    c2.markdown(t("carb_sources_label") + "\n".join(f"- {f}" for f in dieta["fuentes_carbohidrato_sugeridas"]))
    c3.markdown(t("fat_sources_label") + "\n".join(f"- {f}" for f in dieta["fuentes_grasa_sugeridas"]))

    if dieta["consejos_sinergias"]:
        with st.expander(t("synergy_tips_header")):
            for consejo in dieta["consejos_sinergias"]:
                st.markdown(f"- {consejo}")

    with st.expander(t("client_message_header")):
        st.markdown(dieta["mensaje_para_el_cliente"])

    st.download_button(
        t("download_diet"),
        data=json.dumps(dieta, ensure_ascii=False, indent=2),
        file_name="diet.json",
        mime="application/json",
    )


def _panel_aprobacion(estado) -> None:
    st.markdown(t("approval_header"))
    st.caption(t("approval_caption"))
    if st.button(t("approve_button"), type="primary"):
        st.success(t("approved_success").format(time=datetime.now().strftime("%H:%M:%S")))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

with st.sidebar:
    lang_choice = st.radio(
        "🌐 Language / Idioma",
        ["en", "es"],
        format_func=lambda k: "English" if k == "en" else "Español",
        index=0 if st.session_state.lang == "en" else 1,
        key="lang_radio",
        horizontal=True,
    )
    st.session_state.lang = lang_choice

st.title(t("app_title"))
st.caption(t("app_motto"))
st.markdown(t("app_intro"))

tab_ejemplo, tab_nueva = st.tabs([t("tab_example"), t("tab_new_intake")])

# Both tabs' bodies run on every script execution (Streamlit only hides the
# inactive one client-side, it doesn't skip it) — so the generated plan must
# be rendered *inside* the tab that produced it, tagged with "ultimo_origen",
# or it ends up glued to the bottom of the page regardless of which tab is
# selected. This also makes switching tabs reset what's visible: the other
# tab simply has no matching origin to show yet.
with tab_ejemplo:
    perfil_ejemplo = _selector_cliente_ejemplo()
    if perfil_ejemplo is not None:
        st.session_state["ultimo_perfil"] = perfil_ejemplo
        st.session_state["ultimo_origen"] = "ejemplo"
    if st.session_state.get("ultimo_origen") == "ejemplo":
        _ejecutar_y_mostrar(st.session_state["ultimo_perfil"])

with tab_nueva:
    perfil_nuevo = _formulario_ficha_nueva()
    if perfil_nuevo is not None:
        st.session_state["ultimo_perfil"] = perfil_nuevo
        st.session_state["ultimo_origen"] = "nueva"
    if st.session_state.get("ultimo_origen") == "nueva":
        _ejecutar_y_mostrar(st.session_state["ultimo_perfil"])
