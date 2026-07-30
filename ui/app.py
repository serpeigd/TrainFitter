"""
Trainer's panel — TrainFitter's Streamlit interface.

Turns the pipeline (previously only accessible via CLI) into something a
non-technical trainer could use: pick or create an intake, generate the
plan, watch the state trail live, review routine + diet, approve, and
optionally create a real Gmail draft (never auto-sent — see
mcp/gmail_client.py) for the trainer to review and send themselves.

Includes an EN/ES language toggle for the UI chrome (labels, buttons, help
text). The generated plan content itself (exercise names, messages) is
produced in English by the underlying rule engine regardless of the UI
language — see docs/decisiones.md for that scoping decision.

How to run it (from the repo root):
    pip install streamlit
    streamlit run ui/app.py
"""

import base64
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent

try:  # dotenv is optional, same convention as agents/run_routine_demo.py
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass


def _materializar_secretos_gmail() -> None:
    """Streamlit Cloud's "Secrets" panel only stores plain key/value pairs
    (TOML), not uploadable files — but mcp/gmail_client.py expects
    credentials.json/token.json as actual files on disk (deliberately kept
    framework-agnostic: it doesn't import Streamlit at all, and shouldn't
    have to just to run locally). Bridges the two here, in the UI layer,
    instead of teaching gmail_client.py about Streamlit: if the JSON
    content is present under GMAIL_CREDENTIALS_JSON / GMAIL_TOKEN_JSON in
    st.secrets, write it out to the paths gmail_client.py already reads —
    but only if that file doesn't already exist, so a real local
    credentials.json/token.json from running this on your own machine is
    never clobbered by (typically absent, since this only matters on a
    deployment) Streamlit secrets."""
    # st.secrets doesn't raise on the attribute access itself when there's
    # no secrets.toml anywhere (plain local dev, the common case) -- it's
    # lazy, so the actual StreamlitSecretNotFoundError only fires on first
    # real use (e.g. the `in` check below). Wrapping just the assignment
    # doesn't catch it; the whole block needs to be inside the try.
    try:
        secretos = st.secrets
        for nombre_archivo, clave_secreto in (
            ("credentials.json", "GMAIL_CREDENTIALS_JSON"),
            ("token.json", "GMAIL_TOKEN_JSON"),
        ):
            ruta = REPO_ROOT / nombre_archivo
            if clave_secreto in secretos and not ruta.exists():
                ruta.write_text(secretos[clave_secreto], encoding="utf-8")
    except Exception:
        return  # no secrets.toml at all -- nothing to bridge, nothing to do


_materializar_secretos_gmail()

# Gates the "Approve" button (and, by extension, Notion/Gmail — both only
# unlock after approval) behind a shared password on deployments where it's
# set. Deliberately an env var / Streamlit secret, never hardcoded here:
# this file is in a public repo, so a literal password in the source would
# be readable by anyone on GitHub the moment it's committed. Unset (the
# default for local dev) means the gate is simply off — nothing to check
# against, matching how every other optional credential in this project
# degrades to "off" rather than "broken" when not configured.
APPROVAL_PASSWORD = os.environ.get("APP_APPROVAL_PASSWORD")
AGENTS_DIR = REPO_ROOT / "agents"
MCP_DIR = REPO_ROOT / "mcp"
EXAMPLES_DIR = REPO_ROOT / "examples"
# Two distinct assets: ICON_PATH is the clean square mark (favicon, sidebar
# — needs to read clearly at ~30-120px), BANNER_PATH is the wider "hero"
# photo-style image (assets/logo.jpg, JPEG since it's photographic content —
# a PNG of the same image was ~9x heavier for no visible quality gain at web
# sizes) used as a big cover image, not as an icon anywhere.
ICON_PATH = REPO_ROOT / "assets" / "icon.png"
BANNER_PATH = REPO_ROOT / "assets" / "logo.jpg"

# Sampled from assets/icon.png (teal leaf, orange dumbbell) — see
# .streamlit/config.toml for the same palette applied to Streamlit's own
# theme engine (buttons, sliders, links, and the dark base itself). These
# are for the extra styling config.toml can't reach: the hero banner, and
# color-coding the routine (orange, the dumbbell half of the mark) versus
# the diet (teal, the leaf half) so the plan's two halves read as a matched
# pair. Tuned for the dark background in .streamlit/config.toml — Streamlit
# doesn't expose its theme colors as reusable CSS variables in this version
# (checked directly in the browser), so switching the base theme means
# these need to stay in sync by hand, not automatically.
COLOR_TEAL = "#05A081"
COLOR_TEAL_BRIGHT = "#5EEAD4"
COLOR_ORANGE = "#F8802A"
COLOR_BG_ELEVATED = "#141F33"
COLOR_BORDER = "rgba(255, 255, 255, 0.10)"
COLOR_TEXT_BRIGHT = "#F8FAFC"
COLOR_TEXT_MUTED = "#94A3B8"

# agents/ and mcp/ modules import each other as "flat" packages (import
# knowledge, import routine_agent...), so they need to be on sys.path just
# like when their own run_*_demo.py scripts are executed.
sys.path.insert(0, str(AGENTS_DIR))
sys.path.insert(0, str(MCP_DIR))

from analytics_parser import analizar_pdf_analitica  # noqa: E402
from gmail_client import GmailClientError, crear_borrador  # noqa: E402
from notion_connector import NotionClientError, actualizar_email_cliente, guardar_registro_cliente  # noqa: E402
from orchestrator import ejecutar_pipeline  # noqa: E402

st.set_page_config(
    page_title="TrainFitter",
    page_icon=str(ICON_PATH) if ICON_PATH.exists() else "💪",
    layout="wide",
)


@st.cache_data
def _logo_base64() -> str:
    """Base64-embedding the icon lets it sit inside the custom-HTML hero
    below — Streamlit has no built-in way to mix a local image into an
    st.markdown(unsafe_allow_html=True) block otherwise. Cached since the
    ~700 KB file would otherwise be re-encoded on every rerun."""
    return base64.b64encode(ICON_PATH.read_bytes()).decode("ascii") if ICON_PATH.exists() else ""


@st.cache_data
def _banner_base64() -> str:
    """Same embedding approach as _logo_base64(), for the wider cover-style
    banner (assets/logo.jpg) shown above the hero."""
    return base64.b64encode(BANNER_PATH.read_bytes()).decode("ascii") if BANNER_PATH.exists() else ""


def _inyectar_estilos() -> None:
    """CSS on top of .streamlit/config.toml's dark theme — covers what the
    theme engine can't reach: the hero banner, section color-coding, card/
    button polish, and a few extra dark-mode-specific touches (glow instead
    of flat shadow, a subtle background vignette, brighter link/scrollbar
    accents for readability on a dark background). Targets Streamlit's
    documented data-testid attributes (stable across releases), not its
    auto-generated emotion-cache classes."""
    st.markdown(
        f"""
        <style>
        /* Subtle brand-colored vignette instead of a flat black background —
        adds depth without competing with the content on top of it. */
        [data-testid="stMain"] {{
            background:
                radial-gradient(circle at 15% 0%, rgba(5, 160, 129, 0.10) 0%, transparent 45%),
                radial-gradient(circle at 100% 20%, rgba(248, 128, 42, 0.06) 0%, transparent 40%);
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, rgba(5, 160, 129, 0.16) 0%, {COLOR_BG_ELEVATED} 260px);
            border-right: 1px solid {COLOR_BORDER};
        }}
        [data-testid="stSidebar"] img {{
            border-radius: 14px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        }}

        .tf-banner {{
            width: 100%;
            border-radius: 16px;
            display: block;
            margin-bottom: 1.25rem;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.45);
            animation: tf-fade-in 0.5s ease-out;
        }}

        .tf-hero {{
            display: flex;
            align-items: center;
            gap: 1.1rem;
            margin-bottom: 0.2rem;
            animation: tf-fade-in 0.4s ease-out;
        }}
        .tf-hero img {{
            width: 60px;
            height: 60px;
            border-radius: 14px;
            flex-shrink: 0;
            box-shadow: 0 4px 20px rgba(5, 160, 129, 0.35);
        }}
        .tf-hero-title {{
            font-size: 2rem;
            font-weight: 800;
            margin: 0;
            line-height: 1.15;
            color: {COLOR_TEXT_BRIGHT};
        }}
        .tf-hero-subtitle {{
            margin: 0.2rem 0 0 0;
            color: {COLOR_TEXT_MUTED};
            font-style: italic;
            font-size: 0.95rem;
        }}
        .tf-hero-bar {{
            height: 4px;
            border-radius: 4px;
            margin: 1rem 0 1.5rem 0;
            background: linear-gradient(90deg, {COLOR_TEAL} 0%, {COLOR_ORANGE} 100%);
            box-shadow: 0 0 12px rgba(5, 160, 129, 0.45);
        }}
        @keyframes tf-fade-in {{
            from {{ opacity: 0; transform: translateY(-6px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Routine = orange (the mark's dumbbell half), Diet = teal (its leaf
        half) — the plan's two halves echo the logo's own two-tone split. */
        .tf-section-rutina, .tf-section-dieta {{
            border-left: 4px solid transparent;
            padding-left: 0.8rem;
            margin-bottom: 0.4rem;
        }}
        .tf-section-rutina {{ border-color: {COLOR_ORANGE}; }}
        .tf-section-dieta {{ border-color: {COLOR_TEAL}; }}
        .tf-section-rutina h3, .tf-section-dieta h3 {{ margin: 0; }}

        /* Bordered st.container() cards (routine/diet/approval) */
        [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {{
            transition: border-color 0.15s ease-in-out, box-shadow 0.15s ease-in-out;
        }}
        [data-testid="stExpander"] {{
            border: 1px solid {COLOR_BORDER};
            border-radius: 12px;
        }}

        hr {{
            height: 2px;
            border: none;
            border-radius: 2px;
            background: linear-gradient(90deg, {COLOR_TEAL} 0%, transparent 70%);
            opacity: 0.5;
        }}

        [data-testid="stBaseButton-primary"] {{
            border-radius: 10px;
            font-weight: 600;
            box-shadow: 0 0 0 rgba(5, 160, 129, 0);
            transition: transform 0.05s ease-in-out, box-shadow 0.15s ease-in-out;
        }}
        [data-testid="stBaseButton-primary"]:hover {{
            transform: translateY(-1px);
            box-shadow: 0 0 16px rgba(5, 160, 129, 0.55);
        }}
        [data-testid="stBaseButton-secondary"] {{
            border-radius: 10px;
            border-color: {COLOR_BORDER};
        }}
        [data-testid="stBaseButton-secondary"]:hover {{
            border-color: {COLOR_TEAL};
            color: {COLOR_TEAL_BRIGHT};
        }}

        [data-testid="stMetricValue"] {{
            color: {COLOR_ORANGE};
            font-weight: 700;
        }}
        [data-testid="stMetricLabel"] {{
            color: {COLOR_TEAL_BRIGHT};
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-size: 0.75rem;
        }}

        [data-testid="stAlertContainer"] {{
            border-radius: 10px;
        }}

        /* Segmented control (New Client / Example client) selected state */
        [data-testid="stBaseButton-primary"] p {{
            color: inherit;
        }}

        ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{
            background: rgba(5, 160, 129, 0.45);
            border-radius: 8px;
        }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(5, 160, 129, 0.7); }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# i18n — UI chrome translations (EN default, ES available via the toggle)
# ---------------------------------------------------------------------------

TRANSLATIONS = {
    "en": {
        "app_title": "TrainFitter — Trainer's panel",
        "app_motto": '"Teach your body that your mind is in charge."',
        "lang_picker_label": "🌐 Language / Idioma",
        "tab_example": "📋 Example client",
        "tab_new_intake": "📝 New Client",
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
        "routine_header": "🏋️ Routine",
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
        "diet_header": "🍽️ Diet",
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
        "approval_dialog_title": "Trainer's approval",
        "approval_password_label": "Password (required to approve on this deployment)",
        "approval_password_wrong": "Incorrect password.",
        "approve_button": "✅ Approve and mark as ready to send",
        "approved_success": "Marked as approved at {time}.",
        "gmail_section_header": "### ✉️ Email the plan",
        "gmail_requires_approval": "Approve the plan above first — the Gmail draft unlocks once you do.",
        "client_email_label": "Client's email",
        "create_draft_button": "Create Gmail draft",
        "draft_created_success": "Draft created — [open it in Gmail]({url}).",
        "draft_error": "Could not create the draft: {error}",
        "notion_saved_note": "📋 Saved to Notion — [open it]({url}).",
        "notion_error_note": "📋 Not saved to Notion: {error}",
    },
    "es": {
        "app_title": "TrainFitter — Panel del entrenador",
        "app_motto": '"Enseña a tu cuerpo que quien manda es tu mente."',
        "lang_picker_label": "🌐 Language / Idioma",
        "tab_example": "📋 Cliente de ejemplo",
        "tab_new_intake": "📝 Cliente nuevo",
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
        "routine_header": "🏋️ Rutina",
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
        "diet_header": "🍽️ Dieta",
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
        "approval_dialog_title": "Aprobación del entrenador",
        "approval_password_label": "Contraseña (necesaria para aprobar en este despliegue)",
        "approval_password_wrong": "Contraseña incorrecta.",
        "approve_button": "✅ Aprobar y marcar como listo para enviar",
        "approved_success": "Marcado como aprobado a las {time}.",
        "gmail_section_header": "### ✉️ Enviar el plan por email",
        "gmail_requires_approval": "Aprueba primero el plan de arriba — el borrador de Gmail se desbloquea al hacerlo.",
        "client_email_label": "Email del cliente",
        "create_draft_button": "Crear borrador en Gmail",
        "draft_created_success": "Borrador creado — [ábrelo en Gmail]({url}).",
        "draft_error": "No se pudo crear el borrador: {error}",
        "notion_saved_note": "📋 Guardado en Notion — [ábrelo]({url}).",
        "notion_error_note": "📋 No se guardó en Notion: {error}",
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


# A selectbox/multiselect's already-rendered collapsed label doesn't refresh
# on its own when only format_func's output changes on a rerun (a known
# Streamlit/BaseWeb limitation) — confirmed while building the language
# toggle: switching language left previously-selected options (e.g. the
# equipment multiselect's default chips) showing their old-language text.
# Suffixing the widget's key with the current language forces a remount,
# which does pick up the new labels; these helpers carry the previously
# chosen raw value across that key swap so switching language mid-form
# doesn't reset the trainer's in-progress selection back to the default.
def _clave_selectbox(nombre_base: str, opciones: list[str], por_defecto: str) -> tuple[str, int]:
    clave_valor = f"{nombre_base}_valor"
    clave_widget = f"{nombre_base}_{st.session_state.lang}"
    if clave_widget in st.session_state:
        st.session_state[clave_valor] = st.session_state[clave_widget]
    valor_actual = st.session_state.get(clave_valor, por_defecto)
    indice = opciones.index(valor_actual) if valor_actual in opciones else 0
    return clave_widget, indice


def _clave_multiselect(nombre_base: str, por_defecto: list[str]) -> tuple[str, list[str]]:
    clave_valor = f"{nombre_base}_valor"
    clave_widget = f"{nombre_base}_{st.session_state.lang}"
    if clave_widget in st.session_state:
        st.session_state[clave_valor] = st.session_state[clave_widget]
    return clave_widget, st.session_state.get(clave_valor, por_defecto)


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
    clave_sexo, indice_sexo = _clave_selectbox("sexo", ["mujer", "hombre"], "hombre")
    sexo = c3.selectbox(t("sex"), ["mujer", "hombre"], format_func=opt, index=indice_sexo, key=clave_sexo)
    c4, c5 = st.columns(2)
    peso_kg = c4.number_input(t("weight_kg"), min_value=30.0, max_value=250.0, value=70.0, step=0.5, key="peso")
    altura_cm = c5.number_input(t("height_cm"), min_value=120, max_value=230, value=170, key="altura")

    st.subheader(t("sec_goal"))
    clave_objetivo, indice_objetivo = _clave_selectbox("objetivo", OBJETIVOS, OBJETIVOS[0])
    principal = st.selectbox(t("goal_main"), OBJETIVOS, format_func=opt, index=indice_objetivo, key=clave_objetivo)
    en_sus_palabras = st.text_area(t("goal_in_words"), key="en_sus_palabras")

    st.subheader(t("sec_experience"))
    c6, c7 = st.columns(2)
    niveles = ["principiante", "intermedio", "avanzado"]
    clave_nivel, indice_nivel = _clave_selectbox("nivel", niveles, "principiante")
    nivel = c6.selectbox(t("level"), niveles, format_func=opt, index=indice_nivel, key=clave_nivel)
    anios_entrenando = c7.number_input(t("years_training"), min_value=0.0, max_value=50.0, value=0.5, step=0.5, key="anios")
    detalle_experiencia = st.text_area(t("experience_details"), key="detalle_experiencia")

    st.subheader(t("sec_availability"))
    c8, c9 = st.columns(2)
    dias_por_semana = c8.slider(t("days_per_week"), 1, 6, 4, key="dias")
    minutos_por_sesion = c9.number_input(t("minutes_per_session"), min_value=15, max_value=180, value=60, step=5, key="minutos")
    lugares_entreno = ["gimnasio_completo", "gimnasio_pequeno", "casa_con_material", "casa_sin_material"]
    clave_lugar, indice_lugar = _clave_selectbox("lugar_entreno", lugares_entreno, lugares_entreno[0])
    lugar_entreno = st.selectbox(
        t("training_location"), lugares_entreno, format_func=opt, index=indice_lugar, key=clave_lugar,
    )
    clave_material, valor_material = _clave_multiselect("material", MATERIAL_OPCIONES)
    material_disponible = st.multiselect(
        t("available_equipment"), MATERIAL_OPCIONES, default=valor_material, format_func=opt, key=clave_material,
    )

    st.subheader(t("sec_health"))
    st.caption(t("sec_health_caption"))
    tiene_lesion = st.checkbox(t("has_injury"), key="tiene_lesion")
    zona_lesion = descripcion_lesion = ""
    estado_lesion = "antigua_controlada"
    if tiene_lesion:
        zona_lesion = st.text_input(t("injury_area"), key="zona_lesion")
        descripcion_lesion = st.text_area(t("injury_description"), key="descripcion_lesion")
        estados_lesion = ["antigua_controlada", "activa"]
        clave_estado_lesion, indice_estado_lesion = _clave_selectbox("estado_lesion", estados_lesion, estados_lesion[0])
        estado_lesion = st.selectbox(
            t("injury_status"), estados_lesion, format_func=opt, index=indice_estado_lesion, key=clave_estado_lesion,
        )

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
    tipos_dieta = ["omnivora", "vegetariana_ovolacto", "vegana"]
    clave_tipo_dieta, indice_tipo_dieta = _clave_selectbox("tipo_dieta", tipos_dieta, "omnivora")
    tipo_dieta = st.selectbox(t("diet_type"), tipos_dieta, format_func=opt, index=indice_tipo_dieta, key=clave_tipo_dieta)
    c14, c15 = st.columns(2)
    restricciones_texto = c14.text_input(t("additional_restrictions"), key="restricciones")
    no_le_gustan_texto = c15.text_input(t("disliked_foods"), key="no_le_gustan")
    comidas_al_dia = st.number_input(t("meals_per_day"), min_value=2, max_value=6, value=3, key="comidas")
    contexto_nutricion = st.text_area(t("nutrition_context"), key="contexto")

    st.subheader(t("sec_lifestyle"))
    c16, c17, c18 = st.columns(3)
    horas_sueno = c16.number_input(t("avg_sleep"), min_value=3.0, max_value=12.0, value=7.0, step=0.5, key="sueno")
    niveles_estres = ["bajo", "medio", "alto"]
    clave_estres, indice_estres = _clave_selectbox("estres", niveles_estres, "medio")
    estres = c17.selectbox(t("stress_level"), niveles_estres, format_func=opt, index=indice_estres, key=clave_estres)
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
    marcadores_analitica = (
        analizar_pdf_analitica(analitica_pdf.getvalue())["marcadores"] if analitica_pdf is not None else []
    )
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
                "marcadores": marcadores_analitica,
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

@st.cache_data
def _cargar_clientes_ejemplo() -> dict[str, dict]:
    """{filename: profile} for every example/test client on disk. Cached the
    same way as _logo_base64(): these files don't change while the app is
    running, so re-reading and re-parsing them on every rerun is wasted work."""
    rutas = sorted(EXAMPLES_DIR.glob("cliente_ejemplo_*.json")) + sorted(EXAMPLES_DIR.glob("cliente_prueba_*.json"))
    return {ruta.name: json.loads(ruta.read_text(encoding="utf-8")) for ruta in rutas}


def _selector_cliente_ejemplo() -> dict | None:
    perfiles = _cargar_clientes_ejemplo()
    if not perfiles:
        st.info(t("no_example_clients"))
        return None

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

def _ejecutar_y_mostrar(perfil: dict, guardar_en_notion: bool = False) -> None:
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
    with col_rutina, st.container(border=True):
        _mostrar_rutina(estado.borrador_rutina)
    with col_dieta, st.container(border=True):
        _mostrar_dieta(estado.borrador_dieta)

    st.divider()
    with st.container(border=True):
        _panel_aprobacion(estado, guardar_en_notion=guardar_en_notion)


def _mostrar_veredicto(veredicto: dict) -> None:
    if veredicto["veredicto"] == "revision_reforzada":
        st.warning(t("enhanced_review_warning"))
        for motivo in veredicto["motivos"]:
            st.markdown(f"- {motivo}")
    else:
        st.success(t("no_review_reasons_success"))


def _mostrar_rutina(rutina: dict) -> None:
    st.markdown(f'<div class="tf-section-rutina"><h3>{t("routine_header")}</h3></div>', unsafe_allow_html=True)
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
    st.markdown(f'<div class="tf-section-dieta"><h3>{t("diet_header")}</h3></div>', unsafe_allow_html=True)
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


def _ejecutar_aprobacion(estado, guardar_en_notion: bool) -> None:
    """The actual approval side-effects (unlock Gmail, save to Notion) —
    factored out so both the no-password path (direct button click) and the
    password-dialog path (confirm inside the popup) run identical logic.

    Results are written to session_state rather than shown directly here:
    the password-dialog path calls st.rerun() right after this to close the
    popup, which would otherwise wipe out any st.success()/st.caption() from
    this same script run before the trainer ever saw it — a real bug found
    while investigating a "Notion never saves" report, where a save that was
    actually failing on the deployment did so completely silently. Reading
    these back in _panel_aprobacion() on the next run makes the outcome
    persist on the main page instead."""
    perfil = estado.perfil_cliente

    # Tracked in session_state (keyed by id(perfil), stable for this exact
    # submission — see st.session_state["ultimo_perfil"]) so the Gmail
    # section stays unlocked across reruns after this click, not just
    # during the one rerun the click happened on.
    st.session_state["aprobado_para"] = id(perfil)
    st.session_state["aprobado_hora"] = datetime.now().strftime("%H:%M:%S")

    # Saved on approval, not on generation: a trainer might regenerate a few
    # times while tweaking before settling on one — only the plan they
    # actually approve is worth a permanent Notion record. Guards against a
    # double-click creating two rows for the same approval the same way the
    # old auto-save guarded against duplicate reruns.
    if guardar_en_notion and st.session_state.get("notion_guardado_para") != id(perfil):
        try:
            resultado = guardar_registro_cliente(perfil, estado.borrador_rutina, estado.borrador_dieta, estado.veredicto)
            st.session_state["notion_guardado_para"] = id(perfil)
            # Kept for the Gmail section below: it can't know the Notion
            # page to backfill the client's email onto otherwise, since the
            # trainer usually hasn't typed it in yet at approval time.
            st.session_state["notion_pagina_id"] = resultado["id"]
            st.session_state["notion_resultado_url"] = resultado["url"]
            st.session_state["notion_error"] = None
        except (NotionClientError, ImportError, ModuleNotFoundError) as exc:
            # Unlike the old silent auto-save, this is now a direct result
            # of a click the trainer just made — worth a visible (but
            # non-blocking) note instead of failing silently, so "why
            # didn't this show up in Notion" has an answer on screen.
            st.session_state["notion_error"] = str(exc)


@st.dialog(t("approval_dialog_title"))
def _dialogo_aprobacion(estado, guardar_en_notion: bool) -> None:
    """Popup shown instead of approving directly, on any deployment where
    APPROVAL_PASSWORD is set — keeps a public demo visitor from writing to
    the trainer's real Notion/Gmail just by clicking through the app.
    Streamlit gotcha: a dialog's *open* state has to live in session_state,
    not just "was the trigger button clicked this rerun" — typing in the
    password field below is itself a rerun, and on that rerun the trigger
    button is no longer True, so without the session_state flag the modal
    would appear to vanish the moment you start typing.

    The decorator's title argument is re-evaluated on every script rerun
    (Streamlit re-executes the whole module top to bottom each time), so
    t("approval_header") here does track the language toggle correctly —
    it's not frozen at first import the way a module-level constant would be."""
    password_ingresada = st.text_input(t("approval_password_label"), type="password", key="approval_password_dialog")
    if st.button(t("approve_button"), type="primary"):
        if password_ingresada != APPROVAL_PASSWORD:
            st.error(t("approval_password_wrong"))
            return
        _ejecutar_aprobacion(estado, guardar_en_notion)
        st.session_state["mostrar_dialogo_aprobacion"] = False
        st.rerun()


def _panel_aprobacion(estado, guardar_en_notion: bool = False) -> None:
    perfil = estado.perfil_cliente

    st.markdown(t("approval_header"))

    if APPROVAL_PASSWORD:
        if st.button(t("approve_button"), type="primary"):
            st.session_state["mostrar_dialogo_aprobacion"] = True
        if st.session_state.get("mostrar_dialogo_aprobacion"):
            _dialogo_aprobacion(estado, guardar_en_notion)
    elif st.button(t("approve_button"), type="primary"):
        _ejecutar_aprobacion(estado, guardar_en_notion)

    # Gmail is locked until this exact plan has been approved above — a
    # trainer could otherwise create a real, addressed draft for a plan
    # they never actually signed off on. Re-checked on every rerun (not
    # just remembered from the click) via the same id(perfil) key so a
    # freshly generated/regenerated plan starts locked again.
    aprobado = st.session_state.get("aprobado_para") == id(perfil)

    # Read back from session_state (not shown directly at approval time) so
    # this survives the st.rerun() that closes the password dialog — see
    # _ejecutar_aprobacion()'s docstring.
    if aprobado:
        st.success(t("approved_success").format(time=st.session_state.get("aprobado_hora", "")))
        if guardar_en_notion and st.session_state.get("notion_guardado_para") == id(perfil):
            st.caption(t("notion_saved_note").format(url=st.session_state.get("notion_resultado_url", "")))
        elif guardar_en_notion and st.session_state.get("notion_error"):
            st.caption(t("notion_error_note").format(error=st.session_state["notion_error"]))

    st.markdown(t("gmail_section_header"))
    if not aprobado:
        st.info(t("gmail_requires_approval"))
    email_cliente = st.text_input(t("client_email_label"), key="email_cliente", disabled=not aprobado)
    if st.button(t("create_draft_button"), disabled=not aprobado):
        try:
            url = crear_borrador(
                email_cliente,
                perfil["datos_basicos"]["nombre"],
                estado.borrador_rutina,
                estado.borrador_dieta,
            )
            st.success(t("draft_created_success").format(url=url))

            # Backfills the client's email onto their Notion record, ahead
            # of the (still-blocked, see docs/decisiones.md) future "detect
            # a real send and cross-reference the Check-ins database by
            # email" automation — the join key needs to exist before the
            # automation that will use it does. Best-effort: a trainer using
            # this without Notion configured (or where the approval-time
            # save failed) shouldn't see an error over a background update
            # for a feature they may not even have set up.
            #
            # Gated on notion_guardado_para matching *this* perfil, not just
            # "is notion_pagina_id set" — otherwise approving a real client
            # (saved to Notion), then switching to the Example client
            # section and creating a draft there, would silently backfill
            # the example client's email onto the real client's Notion page:
            # notion_pagina_id is a single session-wide slot that only ever
            # gets written for "New Client" plans, so without this check
            # it'd still be holding the previous real client's page ID.
            if st.session_state.get("notion_guardado_para") == id(perfil):
                pagina_id = st.session_state.get("notion_pagina_id")
                try:
                    actualizar_email_cliente(pagina_id, email_cliente)
                except (NotionClientError, ImportError, ModuleNotFoundError):
                    pass
        except (GmailClientError, ImportError, ModuleNotFoundError) as exc:
            # Never crash the app over this: a missing google-api-python-client
            # (e.g. on the public demo, where it's deliberately not installed)
            # or missing/expired credentials are expected, recoverable states,
            # not bugs — same "best-effort, never blocks" spirit as the
            # bloodwork parser.
            st.error(t("draft_error").format(error=str(exc)))


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

with st.sidebar:
    if ICON_PATH.exists():
        st.image(str(ICON_PATH), width=120)
    lang_choice = st.radio(
        "🌐 Language / Idioma",
        ["en", "es"],
        format_func=lambda k: "English" if k == "en" else "Español",
        index=0 if st.session_state.lang == "en" else 1,
        key="lang_radio",
        horizontal=True,
    )
    st.session_state.lang = lang_choice

_inyectar_estilos()

# Cover banner (assets/logo.jpg) — kept in its original Spanish tagline
# regardless of the EN/ES toggle below: it's baked into the image itself,
# not translatable text, a deliberate trade-off for the visual (see
# docs/decisiones.md).
_banner_b64 = _banner_base64()
if _banner_b64:
    st.markdown(
        f'<img class="tf-banner" src="data:image/jpeg;base64,{_banner_b64}" alt="TrainFitter">',
        unsafe_allow_html=True,
    )

_logo_b64 = _logo_base64()
_logo_html = f'<img src="data:image/png;base64,{_logo_b64}" alt="TrainFitter logo">' if _logo_b64 else ""
st.markdown(
    f"""
    <div class="tf-hero">
        {_logo_html}
        <div>
            <p class="tf-hero-title">{t("app_title")}</p>
            <p class="tf-hero-subtitle">{t("app_motto")}</p>
        </div>
    </div>
    <div class="tf-hero-bar"></div>
    """,
    unsafe_allow_html=True,
)

# st.tabs() is deliberately NOT used here: its labels double as its React
# identity, so translating them on a language switch remounts the whole
# component and resets the view to the first tab — reproduced and confirmed
# while building this. st.segmented_control's value is decoupled from its
# displayed text (format_func), exactly like the selectboxes elsewhere in
# this file, so the active section survives a language switch untouched.
SECCIONES = ["nueva", "ejemplo"]  # "New Client" first, per the trainer's workflow
seccion_activa = st.segmented_control(
    "navigation",
    SECCIONES,
    format_func=lambda k: t("tab_new_intake") if k == "nueva" else t("tab_example"),
    default="nueva",
    key="seccion_activa",
    label_visibility="collapsed",
)

# The generated plan is rendered *inside* whichever section produced it,
# tagged with "ultimo_origen" — otherwise it would stay visible after
# switching to the other section, which has nothing to do with it.
if seccion_activa == "nueva":
    perfil_nuevo = _formulario_ficha_nueva()
    if perfil_nuevo is not None:
        st.session_state["ultimo_perfil"] = perfil_nuevo
        st.session_state["ultimo_origen"] = "nueva"
    if st.session_state.get("ultimo_origen") == "nueva":
        # Notion auto-save only fires for real new-client intakes, never for
        # the example-client demo below — a public-demo visitor clicking
        # through the sample clients shouldn't clutter the trainer's actual
        # Notion database.
        _ejecutar_y_mostrar(st.session_state["ultimo_perfil"], guardar_en_notion=True)

elif seccion_activa == "ejemplo":
    perfil_ejemplo = _selector_cliente_ejemplo()
    if perfil_ejemplo is not None:
        st.session_state["ultimo_perfil"] = perfil_ejemplo
        st.session_state["ultimo_origen"] = "ejemplo"
    if st.session_state.get("ultimo_origen") == "ejemplo":
        _ejecutar_y_mostrar(st.session_state["ultimo_perfil"])
