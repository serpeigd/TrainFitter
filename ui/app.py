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
    st.secrets, write it out to the paths gmail_client.py already reads.

    Writes only when the file is missing OR its content doesn't match the
    secret — not unconditionally on every run. A real local
    credentials.json/token.json from running this on your own machine stays
    protected (its content will never happen to match a Cloud secret). But
    a deployment's own on-disk copy, once written, must still update itself
    when the secret changes later (e.g. re-authorizing Gmail for a new
    OAuth scope) — Streamlit Cloud's container filesystem persists across a
    secrets-only restart, so an earlier "only if missing" version of this
    function left a stale token.json in place forever after the first
    write, silently ignoring every subsequent secret update. Caught when
    widening the Gmail scope: the new secret was saved correctly, but the
    app kept using the old (now-insufficient) token from disk regardless."""
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
            if clave_secreto not in secretos:
                continue
            contenido_secreto = secretos[clave_secreto]
            if not ruta.exists() or ruta.read_text(encoding="utf-8") != contenido_secreto:
                ruta.write_text(contenido_secreto, encoding="utf-8")
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
# Needed to build a full, clickable portal URL (generar_token_portal() only
# returns the token itself) -- defaults to local dev's own address; set to
# the real deployed URL (e.g. https://trainfitter.streamlit.app) via env
# var / Streamlit secret on any real deployment, same pattern as every
# other optional secret here.
PORTAL_BASE_URL = os.environ.get("PORTAL_BASE_URL", "http://localhost:8501")
# Optional -- the trainer's own inbox, notified automatically the moment a
# client submits a portal check-in (see gmail_client.py's DESIGN note on
# enviar_notificacion_checkin(): the one other function allowed to
# actually send, safe to fire without a button because it always mails
# the trainer, never a client). Unset means the notification is simply
# skipped, same "degrades to off" convention as every other optional
# secret here.
TRAINER_NOTIFICATION_EMAIL = os.environ.get("TRAINER_NOTIFICATION_EMAIL")
AGENTS_DIR = REPO_ROOT / "agents"
MCP_DIR = REPO_ROOT / "mcp"
EXAMPLES_DIR = REPO_ROOT / "examples"
# Two purpose-built crops, both sourced from the project owner's own studio
# logo shoot (assets/logo.jpg is the original, kept only as the source
# archive — see docs/decisiones.md). ICON_PATH is a square crop of just the
# glowing leaf+dumbbell mark (no wordmark), background keyed to transparent
# (alpha from pixel brightness, since the source is shot on near-black) so
# it sits on the app's own dark background instead of a mismatched
# flat-color square. Used at ~30-120px (favicon, sidebar, .tf-hero).
# BANNER_PATH is a separately hand-cropped wide frame (assets/Cropped.jpg)
# that keeps the full mark + "TrainFitter" wordmark roughly centered in
# frame — CSS still crops it further to a short strip for the cover banner
# (see .tf-banner-wrap), but starting from a frame that's already centered
# on the logo means less of it gets cut off than cropping the original
# full-scene photo would.
ICON_PATH = REPO_ROOT / "assets" / "icon.png"
BANNER_PATH = REPO_ROOT / "assets" / "Cropped.jpg"

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

from adherencia_parser import resumir_adherencia, valoracion_desde_ratios  # noqa: E402
from analytics_parser import analizar_pdf_analitica  # noqa: E402
from exercise_bank import nombre_mostrado as ejercicio_mostrado  # noqa: E402
from food_bank import nombre_mostrado as alimento_mostrado  # noqa: E402
from gmail_client import (  # noqa: E402
    GmailClientError,
    crear_borrador,
    enviar_enlace_portal,
    enviar_notificacion_checkin,
    verificar_envio,
)
from notion_connector import (  # noqa: E402
    NotionClientError,
    actualizar_email_cliente,
    actualizar_registro_cliente,
    buscar_cliente_por_email,
    crear_registro_checkin,
    guardar_registro_cliente,
    historial_checkins,
    listar_clientes,
    marcar_email_enviado,
    obtener_registro_cliente,
    ultimo_checkin_por_cliente,
)
from orchestrator import ejecutar_pipeline  # noqa: E402
from pdf_generador import DIAS_SEMANA_DIETA  # noqa: E402
from pdf_intake import es_intake_pdf, leer_intake_pdf  # noqa: E402
from portal_tokens import PortalTokenError, generar_token_portal, verificar_token_portal  # noqa: E402

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
        /* A colored neon glow behind the sidebar mark, echoing the same
        two-tone treatment .tf-hero img already gets below — a plain dark
        drop shadow alone (the pre-existing rule) reads as flat next to the
        glowing artwork inside the image itself. */
        [data-testid="stSidebar"] img {{
            border-radius: 14px;
            box-shadow:
                0 4px 16px rgba(0, 0, 0, 0.4),
                0 0 34px rgba(5, 160, 129, 0.40),
                0 0 60px rgba(248, 128, 42, 0.18);
        }}

        /* Cover banner: shown exactly as the source photo (assets/Cropped.jpg)
        was hand-composed — the project owner cropped and centered that
        frame externally specifically for this spot, so CSS shouldn't
        re-crop it again on top. `aspect-ratio` matched to the file's own
        1200x487 ratio (instead of a fixed `height`) means `object-fit:
        cover` never actually needs to crop anything: the box is always
        exactly the image's shape, just scaled. `max-width` caps it at the
        source's native resolution so it never upscales past its real
        pixels on an ultra-wide monitor, and centers it instead of
        stretching edge-to-edge — the "too intrusive" complaint that led to
        the earlier compact-strip version was about a banner spanning the
        full page width, not about its height, so capping width solves
        that without cropping content. No bottom gradient fade here (the
        old compact-strip version had one): the wordmark sits low in this
        frame (~80-97% of its height), which a fade in that zone would
        have obscured. */
        .tf-banner-wrap {{
            position: relative;
            width: 100%;
            max-width: 1200px;
            aspect-ratio: 1200 / 487;
            overflow: hidden;
            border-radius: 16px;
            margin: 0 auto 1.25rem auto;
        }}
        /* !important on the fit properties specifically: Streamlit's own
        emotion-generated CSS applies "img" object-fit: scale-down rules
        scoped to a markdown-container class to every <img> rendered via
        st.markdown(unsafe_allow_html=True) — including this one — and
        that compound selector (one class + one type) outranks .tf-banner
        alone on specificity, so it silently won regardless of source
        order. Confirmed by reading the actual CSSOM (matching rules don't
        always show up searching <style> textContent — Streamlit inserts
        some of its own via insertRule()), not by guessing from the
        symptom. */
        .tf-banner {{
            width: 100%;
            height: 100%;
            object-fit: cover !important;
            object-position: center !important;
            display: block;
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

        /* Bordered st.container() cards (routine/diet/approval) — subtle
        lift + glow on hover so the two-column layout feels tactile instead
        of static. Targets the "st-key-*" class Streamlit generates from
        st.container(key=...) (see the call sites) — the
        "stVerticalBlockBorderWrapper" testid from older Streamlit versions
        doesn't exist in this one; the border lands directly on the shared
        stVerticalBlock element instead, which has no way to distinguish
        "this one has a border" from any other vertical block via testid
        alone. */
        .st-key-tf-card-rutina, .st-key-tf-card-dieta, .st-key-tf-card-aprobacion {{
            transition: border-color 0.2s ease-out, box-shadow 0.2s ease-out, transform 0.2s ease-out;
            border-radius: 14px !important;
        }}
        .st-key-tf-card-rutina:hover, .st-key-tf-card-dieta:hover, .st-key-tf-card-aprobacion:hover {{
            border-color: rgba(5, 160, 129, 0.45);
            box-shadow: 0 10px 32px rgba(0, 0, 0, 0.4);
            transform: translateY(-2px);
        }}
        [data-testid="stExpander"] {{
            border: 1px solid {COLOR_BORDER};
            border-radius: 12px;
            transition: border-color 0.2s ease-out;
        }}
        [data-testid="stExpander"]:hover {{
            border-color: rgba(5, 160, 129, 0.4);
        }}

        /* Pipeline stepper — mirrors the orchestrator's own state machine
        (agents/orchestrator.py) and the approval/Gmail/Check-ins flow, so
        the same visual language represents "what the AI pipeline did" and
        "what the trainer still needs to do." */
        .tf-stepper {{
            display: flex;
            align-items: flex-start;
            margin: 0.75rem 0 1.5rem 0;
            animation: tf-fade-in 0.4s ease-out;
        }}
        .tf-step {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.4rem;
            flex: 0 1 auto;
        }}
        .tf-step-dot {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.85rem;
            font-weight: 700;
            background: {COLOR_BG_ELEVATED};
            border: 2px solid {COLOR_BORDER};
            color: {COLOR_TEXT_MUTED};
            transition: all 0.35s ease-out;
            flex-shrink: 0;
        }}
        .tf-step-dot.tf-done {{
            background: linear-gradient(135deg, {COLOR_TEAL} 0%, {COLOR_TEAL_BRIGHT} 100%);
            border-color: {COLOR_TEAL};
            color: #06251F;
            box-shadow: 0 0 14px rgba(5, 160, 129, 0.55);
        }}
        .tf-step-dot.tf-warn {{
            background: linear-gradient(135deg, {COLOR_ORANGE} 0%, #FDBA74 100%);
            border-color: {COLOR_ORANGE};
            color: #3A1B02;
            box-shadow: 0 0 14px rgba(248, 128, 42, 0.55);
        }}
        .tf-step-label {{
            font-size: 0.68rem;
            color: {COLOR_TEXT_MUTED};
            text-transform: uppercase;
            letter-spacing: 0.03em;
            text-align: center;
            white-space: nowrap;
        }}
        .tf-step.tf-done .tf-step-label, .tf-step.tf-warn .tf-step-label {{
            color: {COLOR_TEXT_BRIGHT};
        }}
        .tf-step-line {{
            flex: 1 1 auto;
            height: 2px;
            background: {COLOR_BORDER};
            margin: 15px 0.4rem 0 0.4rem;
            position: relative;
            overflow: hidden;
            min-width: 12px;
        }}
        .tf-step-line.tf-done {{
            background: linear-gradient(90deg, {COLOR_TEAL} 0%, {COLOR_ORANGE} 100%);
        }}

        /* Exercise table — replaces the flat default st.table look with
        something that reads as "the routine half" (warm orange accents). */
        [data-testid="stTable"] table {{
            border-collapse: separate;
            border-spacing: 0;
        }}
        [data-testid="stTable"] thead th {{
            background: rgba(248, 128, 42, 0.14) !important;
            color: {COLOR_ORANGE} !important;
            text-transform: uppercase;
            font-size: 0.68rem;
            letter-spacing: 0.04em;
        }}
        [data-testid="stTable"] tbody tr:nth-child(even) td {{
            background: rgba(255, 255, 255, 0.025);
        }}
        [data-testid="stTable"] tbody tr {{
            transition: background 0.15s ease-out;
        }}
        [data-testid="stTable"] tbody tr:hover td {{
            background: rgba(5, 160, 129, 0.10) !important;
        }}

        hr {{
            height: 2px;
            border: none;
            border-radius: 2px;
            background: linear-gradient(90deg, {COLOR_TEAL} 0%, transparent 70%);
            opacity: 0.5;
        }}

        /* Primary buttons share the brand's teal->orange gradient — one
        consistent "this is the main action" visual language across the
        whole app (generate, approve, create draft, the segmented control's
        selected pill...) instead of a flat theme color. */
        [data-testid="stBaseButton-primary"] {{
            background: linear-gradient(135deg, {COLOR_TEAL} 0%, {COLOR_ORANGE} 100%);
            border: none;
            border-radius: 10px;
            font-weight: 700;
            color: #06120E;
            box-shadow: 0 2px 12px rgba(5, 160, 129, 0.25);
            transition: transform 0.15s ease-out, box-shadow 0.15s ease-out, filter 0.15s ease-out;
        }}
        [data-testid="stBaseButton-primary"]:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 26px rgba(248, 128, 42, 0.45);
            filter: brightness(1.08);
        }}
        [data-testid="stBaseButton-primary"]:active {{
            transform: translateY(0);
            filter: brightness(0.96);
        }}
        [data-testid="stBaseButton-primary"] p {{
            color: inherit;
            font-weight: 700;
        }}
        [data-testid="stBaseButton-primary"]:disabled {{
            background: {COLOR_BG_ELEVATED};
            color: {COLOR_TEXT_MUTED};
            box-shadow: none;
        }}
        [data-testid="stBaseButton-secondary"] {{
            border-radius: 10px;
            border-color: {COLOR_BORDER};
            transition: border-color 0.15s ease-out, color 0.15s ease-out, transform 0.15s ease-out;
        }}
        [data-testid="stBaseButton-secondary"]:hover {{
            border-color: {COLOR_TEAL};
            color: {COLOR_TEAL_BRIGHT};
            transform: translateY(-1px);
        }}

        [data-testid="stMetric"] {{
            background: rgba(255, 255, 255, 0.025);
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 0.6rem 0.8rem 0.4rem 0.8rem;
            transition: border-color 0.2s ease-out;
        }}
        [data-testid="stMetric"]:hover {{
            border-color: rgba(248, 128, 42, 0.4);
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

        /* Alerts get a left accent bar + soft glow matching their meaning,
        instead of Streamlit's flat default box. */
        [data-testid="stAlertContainer"] {{
            border-radius: 10px;
            border-left: 4px solid {COLOR_BORDER};
            transition: box-shadow 0.2s ease-out;
        }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {{
            border-left-color: {COLOR_TEAL};
            box-shadow: 0 0 20px rgba(5, 160, 129, 0.12);
        }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {{
            border-left-color: {COLOR_ORANGE};
            box-shadow: 0 0 20px rgba(248, 128, 42, 0.12);
        }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {{
            border-left-color: {COLOR_TEAL_BRIGHT};
        }}
        [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {{
            border-left-color: #F87171;
        }}

        ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{
            background: rgba(5, 160, 129, 0.45);
            border-radius: 8px;
        }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(5, 160, 129, 0.7); }}

        .tf-sidebar-tagline {{
            color: {COLOR_TEXT_MUTED};
            font-size: 0.68rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            text-align: center;
            margin: 0.6rem 0 1.1rem 0;
        }}
        .tf-sidebar-tagline span {{ color: {COLOR_TEAL_BRIGHT}; }}

        /* Sidebar layout: the icon/tagline/language block centered, an
        "about" card filling the middle, and a footer pinned to the bottom
        of the viewport via flex — instead of everything stacked at the top
        with a large empty gap below, which is how this looked before.
        Targets the direct-child chain confirmed via live DOM inspection
        (stSidebarUserContent > an unnamed wrapper div > the actual
        stVerticalBlock holding every sidebar element) rather than a bare
        descendant selector, which would also match unrelated nested
        vertical blocks several levels deeper inside individual widgets. */
        [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {{
            display: flex;
            flex-direction: column;
            min-height: 88vh;
        }}
        [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"]
            > [data-testid="stElementContainer"]:last-child {{
            margin-top: auto;
        }}
        /* Centering has to land on stFullScreenFrame, not stImageContainer:
        stImageContainer shrink-wraps to the image's own rendered width
        (120px), so a justify-content on it has nothing to center within.
        stFullScreenFrame is the ancestor that actually spans the sidebar's
        full column width — confirmed via live getBoundingClientRect() on
        each link in the chain, not assumed from testid naming. */
        [data-testid="stSidebarUserContent"] [data-testid="stFullScreenFrame"] {{
            display: flex;
            justify-content: center;
        }}
        [data-testid="stSidebarUserContent"] [data-testid="stRadioGroup"] {{
            justify-content: center;
        }}

        .tf-sidebar-about {{
            margin: 0.4rem 0 1rem 0;
            padding: 0.9rem 1.1rem;
            background: rgba(255, 255, 255, 0.025);
            border: 1px solid {COLOR_BORDER};
            border-radius: 12px;
        }}
        .tf-sidebar-about-title {{
            font-size: 0.68rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: {COLOR_TEAL_BRIGHT};
            margin: 0 0 0.6rem 0;
            font-weight: 700;
        }}
        .tf-sidebar-about ul {{
            margin: 0;
            padding: 0;
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        .tf-sidebar-about li {{
            font-size: 0.82rem;
            color: {COLOR_TEXT_BRIGHT};
        }}

        .tf-sidebar-footer {{
            padding-top: 1.5rem;
            text-align: center;
        }}
        .tf-sidebar-github {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            font-size: 0.75rem;
            color: {COLOR_TEXT_MUTED};
            text-decoration: none;
            padding: 0.45rem 0.9rem;
            border: 1px solid {COLOR_BORDER};
            border-radius: 999px;
            transition: color 0.2s ease-out, border-color 0.2s ease-out, box-shadow 0.2s ease-out;
        }}
        .tf-sidebar-github:hover {{
            color: {COLOR_TEXT_BRIGHT};
            border-color: {COLOR_TEAL};
            box-shadow: 0 0 14px rgba(5, 160, 129, 0.3);
        }}
        .tf-sidebar-github svg {{ width: 14px; height: 14px; fill: currentColor; flex-shrink: 0; }}

        /* Segmented control (New Client / Example client): unselected pills
        stay subtle so the gradient-filled selected one reads clearly as
        "you are here," echoing the stepper's own filled/unfilled contrast. */
        [data-testid="stButtonGroup"] [data-testid="stBaseButton-secondary"] {{
            background: transparent;
        }}

        /* Small screens: the two-column routine/diet layout and the wide
        hero title need to breathe differently on a phone. */
        @media (max-width: 640px) {{
            .tf-hero-title {{ font-size: 1.4rem; }}
            .tf-hero img {{ width: 46px; height: 46px; }}
            .tf-banner-wrap {{ border-radius: 10px; }}
            .tf-step-label {{ font-size: 0.6rem; }}
            .tf-step-dot {{ width: 26px; height: 26px; font-size: 0.7rem; }}
        }}
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
        "sidebar_tagline": "Train · <span>Nourish</span> · Evolve",
        "sidebar_about_header": "How it works",
        "sidebar_about_routine": "🏋️ Draft routine",
        "sidebar_about_diet": "🍽️ Draft diet",
        "sidebar_about_safety": "✅ Safety cross-checked",
        "sidebar_about_approval": "✍️ You always approve",
        "sidebar_footer_github": "View source on GitHub",
        "lang_picker_label": "🌐 Language / Idioma",
        "tab_example": "📋 Example client",
        "tab_new_intake": "📝 New Client",
        "tab_revise_client": "🔄 Revise client",
        "tab_clients": "👥 Clients",
        "clients_gate_info": (
            "This deployment requires the trainer's password to view real clients' personal data "
            "(email, health details)."
        ),
        "clients_gate_password_label": "Password",
        "clients_gate_unlock_button": "Unlock",
        "clients_panel_header": "### 👥 All clients",
        "clients_panel_caption": "Every client at a glance, with their most recent check-in — see who needs attention.",
        "clients_panel_error": "Could not load the client list: {error}",
        "clients_panel_empty": "No clients saved yet.",
        "clients_col_name": "Name",
        "clients_col_email": "Email",
        "clients_col_date": "Admitted",
        "clients_col_goal": "Goal",
        "clients_col_level": "Level",
        "clients_col_verdict": "Verdict",
        "clients_col_email_sent": "Email Sent",
        "clients_col_last_checkin": "Last check-in",
        "clients_col_last_rating": "Last rating",
        "revise_client_header": "🔎 Load an existing client to revise",
        "revise_client_caption": (
            "Find a past client by email, edit anything below, and regenerate their plan — "
            "updates their existing record instead of creating a new one."
        ),
        "revise_client_email_label": "Client's email",
        "revise_client_password_label": "Trainer password (required to load a client's data on this deployment)",
        "revise_client_load_button": "Load",
        "revise_client_error": "Could not look up this client: {error}",
        "revise_client_not_found": "No client found with that email.",
        "revise_client_loaded": "Loaded **{nombre}** — edit anything below and regenerate.",
        "intake_pdf_upload_header": "📤 Upload a filled intake PDF (skip the form below)",
        "intake_pdf_upload_caption": (
            "If the client emailed back a filled-in intake form, upload it here instead of retyping everything."
        ),
        "intake_pdf_upload_label": "Filled intake PDF",
        "intake_pdf_upload_invalid": "This doesn't look like a TrainFitter intake PDF.",
        "intake_pdf_upload_empty": "The name field is empty — looks like a blank template, not a filled-in form.",
        "intake_pdf_upload_loaded": "Loaded intake for **{nombre}**.",
        "intake_pdf_upload_confirm": "Use this data and generate the plan",
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
        "bloodwork_kept_on_file": "📋 Keeping the bloodwork markers already on file (from {fecha}) — upload a new PDF only to replace them.",
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
        "step_routine": "Routine",
        "step_diet": "Diet",
        "step_validation": "Validation",
        "step_ready": "Ready",
        "step_ready_warn": "Enhanced review",
        "mini_step_approve": "Approve",
        "mini_step_email": "Email",
        "mini_step_confirm": "Confirm",
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
        "veg_sources_label": "**Vegetables & fruit**\n",
        "weekly_plan_header": "📅 Weekly meal plan",
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
        "notion_error_note": "📋 Not saved to Notion: {error}",
        "check_send_status_button": "Check if it was sent",
        "checkin_confirmed_send": "✅ Confirmed sent — logged in Check-ins.",
        "checkin_not_sent_yet": "Still just a draft in Gmail — not sent yet.",
        "checkin_error": "Could not check send status: {error}",
        "adherence_history_header": "📈 Adherence history",
        "adherence_history_empty": "No check-ins logged for this email yet.",
        "adherence_history_error": "Could not load adherence history: {error}",
        "history_chart_weight": "Weight over time",
        "history_chart_adherence": "Adherence trend (1 = Low, 2 = Medium, 3 = High)",
        "portal_section_header": "### 🔗 Client portal",
        "portal_section_caption": (
            "Sends a real email (not a draft) with a private link where the client can see a plan summary "
            "and log their own check-ins — no PDF back-and-forth needed."
        ),
        "send_portal_link_button": "Send portal link",
        "portal_link_sent_success": "✅ Portal link sent.",
        "portal_link_error": "Could not send the portal link: {error}",
        "portal_invalid_link": "This portal link isn't valid or has expired: {error}",
        "portal_load_error": "Could not load your plan: {error}",
        "portal_welcome": "Hi {nombre} 👋",
        "portal_since_label": "Client since {fecha}",
        "portal_history_header": "📈 Your check-in history",
        "portal_checkin_header": "How's it going?",
        "portal_checkin_intro": "A quick check-in for your trainer — no need to fill in a PDF.",
        "portal_routine_section_title": "🏋️ Routine",
        "portal_diet_section_title": "🍽️ Diet",
        "portal_routine_completed_label": "Sessions completed",
        "portal_routine_total_label": "Sessions planned this week",
        "portal_routine_more_than_planned_label": "I trained more than planned",
        "portal_routine_notes_label": "Anything about your routine (optional)",
        "portal_diet_completed_label": "Days you followed the diet",
        "portal_diet_total_label": "Out of how many days",
        "portal_diet_notes_label": "Anything about your diet (optional)",
        "portal_weight_section_title": "📏 Weight (optional)",
        "portal_share_weight_label": "Share your current weight",
        "portal_weight_label": "Current weight (kg)",
        "portal_submit_button": "Send check-in",
        "portal_submit_success": "✅ Thanks — your trainer will see this.",
        "portal_submit_error": "Could not send your check-in: {error}",
    },
    "es": {
        "app_title": "TrainFitter — Panel del entrenador",
        "app_motto": '"Enseña a tu cuerpo que quien manda es tu mente."',
        "sidebar_tagline": "Entrena · <span>Nutre</span> · Evoluciona",
        "sidebar_about_header": "Cómo funciona",
        "sidebar_about_routine": "🏋️ Rutina en borrador",
        "sidebar_about_diet": "🍽️ Dieta en borrador",
        "sidebar_about_safety": "✅ Revisado de seguridad",
        "sidebar_about_approval": "✍️ Siempre lo apruebas tú",
        "sidebar_footer_github": "Ver código en GitHub",
        "lang_picker_label": "🌐 Language / Idioma",
        "tab_example": "📋 Cliente de ejemplo",
        "tab_new_intake": "📝 Cliente nuevo",
        "tab_revise_client": "🔄 Revisar cliente",
        "tab_clients": "👥 Clientes",
        "clients_gate_info": (
            "Este despliegue requiere la contraseña del entrenador para ver datos personales reales de "
            "clientes (email, datos de salud)."
        ),
        "clients_gate_password_label": "Contraseña",
        "clients_gate_unlock_button": "Desbloquear",
        "clients_panel_header": "### 👥 Todos los clientes",
        "clients_panel_caption": "Todos tus clientes de un vistazo, con su check-in más reciente — ve quién necesita atención.",
        "clients_panel_error": "No se pudo cargar la lista de clientes: {error}",
        "clients_panel_empty": "Todavía no hay clientes guardados.",
        "clients_col_name": "Nombre",
        "clients_col_email": "Email",
        "clients_col_date": "Admitido",
        "clients_col_goal": "Objetivo",
        "clients_col_level": "Nivel",
        "clients_col_verdict": "Veredicto",
        "clients_col_email_sent": "Email enviado",
        "clients_col_last_checkin": "Último check-in",
        "clients_col_last_rating": "Última valoración",
        "revise_client_header": "🔎 Cargar un cliente existente para revisar",
        "revise_client_caption": (
            "Busca un cliente anterior por email, edita lo que necesites y regenera su plan — "
            "actualiza su registro existente en vez de crear uno nuevo."
        ),
        "revise_client_email_label": "Email del cliente",
        "revise_client_password_label": "Contraseña del entrenador (necesaria para cargar datos de un cliente en este despliegue)",
        "revise_client_load_button": "Cargar",
        "revise_client_error": "No se pudo buscar a este cliente: {error}",
        "revise_client_not_found": "No se ha encontrado ningún cliente con ese email.",
        "revise_client_loaded": "Cargado **{nombre}** — edita lo que necesites y regenera.",
        "intake_pdf_upload_header": "📤 Subir una ficha PDF rellenada (te saltas el formulario de abajo)",
        "intake_pdf_upload_caption": (
            "Si el cliente respondió por email con la ficha de admisión rellenada, súbela aquí en vez de "
            "volver a escribirlo todo."
        ),
        "intake_pdf_upload_label": "PDF de ficha rellenado",
        "intake_pdf_upload_invalid": "Esto no parece un PDF de ficha de TrainFitter.",
        "intake_pdf_upload_empty": "El campo de nombre está vacío — parece una plantilla en blanco, no una ficha rellenada.",
        "intake_pdf_upload_loaded": "Ficha cargada para **{nombre}**.",
        "intake_pdf_upload_confirm": "Usar estos datos y generar el plan",
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
        "bloodwork_kept_on_file": "📋 Se mantienen los marcadores de la analítica ya guardada (de {fecha}) — sube un PDF nuevo solo para sustituirlos.",
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
        "step_routine": "Rutina",
        "step_diet": "Dieta",
        "step_validation": "Validación",
        "step_ready": "Listo",
        "step_ready_warn": "Revisión reforzada",
        "mini_step_approve": "Aprobar",
        "mini_step_email": "Enviar",
        "mini_step_confirm": "Confirmar",
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
        "veg_sources_label": "**Verduras y fruta**\n",
        "weekly_plan_header": "📅 Plan semanal de comidas",
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
        "notion_error_note": "📋 No se guardó en Notion: {error}",
        "check_send_status_button": "Comprobar si se envió",
        "checkin_confirmed_send": "✅ Confirmado como enviado — registrado en Check-ins.",
        "checkin_not_sent_yet": "Sigue siendo solo un borrador en Gmail — aún no se ha enviado.",
        "checkin_error": "No se pudo comprobar el envío: {error}",
        "adherence_history_header": "📈 Historial de adherencia",
        "adherence_history_empty": "Todavía no hay check-ins registrados para este email.",
        "adherence_history_error": "No se pudo cargar el historial de adherencia: {error}",
        "history_chart_weight": "Peso a lo largo del tiempo",
        "history_chart_adherence": "Tendencia de adherencia (1 = Baja, 2 = Media, 3 = Alta)",
        "portal_section_header": "### 🔗 Portal del cliente",
        "portal_section_caption": (
            "Envía un email real (no un borrador) con un enlace privado donde el cliente puede ver un resumen "
            "de su plan y registrar sus propios check-ins — sin ida y vuelta de PDFs."
        ),
        "send_portal_link_button": "Enviar enlace del portal",
        "portal_link_sent_success": "✅ Enlace del portal enviado.",
        "portal_link_error": "No se pudo enviar el enlace del portal: {error}",
        "portal_invalid_link": "Este enlace del portal no es válido o ha caducado: {error}",
        "portal_load_error": "No se pudo cargar tu plan: {error}",
        "portal_welcome": "Hola {nombre} 👋",
        "portal_since_label": "Cliente desde {fecha}",
        "portal_history_header": "📈 Tu historial de check-ins",
        "portal_checkin_header": "¿Cómo va todo?",
        "portal_checkin_intro": "Un check-in rápido para tu entrenador/a — sin rellenar ningún PDF.",
        "portal_routine_section_title": "🏋️ Rutina",
        "portal_diet_section_title": "🍽️ Dieta",
        "portal_routine_completed_label": "Sesiones completadas",
        "portal_routine_total_label": "Sesiones previstas esta semana",
        "portal_routine_more_than_planned_label": "Entrené más de lo planeado",
        "portal_routine_notes_label": "Algo sobre tu rutina (opcional)",
        "portal_diet_completed_label": "Días que has seguido la dieta",
        "portal_diet_total_label": "De cuántos días",
        "portal_diet_notes_label": "Algo sobre tu dieta (opcional)",
        "portal_weight_section_title": "📏 Peso (opcional)",
        "portal_share_weight_label": "Comparte tu peso actual",
        "portal_weight_label": "Peso actual (kg)",
        "portal_submit_button": "Enviar check-in",
        "portal_submit_success": "✅ Gracias — tu entrenador/a lo verá.",
        "portal_submit_error": "No se pudo enviar tu check-in: {error}",
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
        "full_body": "full body", "upper_lower": "upper lower", "push_pull_legs": "push pull legs",
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
        "full_body": "cuerpo completo", "upper_lower": "torso-pierna", "push_pull_legs": "empuje-tracción-pierna",
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
# Building the profile from an uploaded, already-filled intake PDF
# ---------------------------------------------------------------------------

def _cargar_ficha_desde_pdf() -> dict | None:
    """Alternative to _formulario_ficha_nueva(): lets the trainer load a
    filled agents/pdf_intake.py form (e.g. one a prospect emailed back)
    instead of retyping the whole intake by hand. Same id_cliente/
    fecha_admision convention as the manual form below, and the same
    "only return once the trainer explicitly confirms" pattern -- so a
    stale upload left in the widget doesn't silently regenerate a plan
    on every unrelated rerun of this page."""
    with st.expander(t("intake_pdf_upload_header")):
        st.caption(t("intake_pdf_upload_caption"))
        pdf_subido = st.file_uploader(t("intake_pdf_upload_label"), type=["pdf"], key="intake_pdf_subido")
        if pdf_subido is None:
            return None

        contenido_pdf = pdf_subido.getvalue()
        if not es_intake_pdf(contenido_pdf):
            st.error(t("intake_pdf_upload_invalid"))
            return None

        perfil = leer_intake_pdf(contenido_pdf)
        nombre = perfil["datos_basicos"]["nombre"]
        if not nombre:
            st.warning(t("intake_pdf_upload_empty"))
            return None

        perfil["id_cliente"] = f"cliente_ui_{_slug(nombre)}"
        perfil["fecha_admision"] = datetime.now(timezone.utc).date().isoformat()

        st.success(t("intake_pdf_upload_loaded").format(nombre=nombre))
        if not st.button(t("intake_pdf_upload_confirm"), type="primary", key="confirmar_intake_pdf"):
            return None
        return perfil


def _campos_formulario_desde_perfil(perfil: dict) -> dict:
    """Maps a full perfil_cliente dict (as loaded from Notion's "Full
    Profile (JSON)" via notion_connector.buscar_cliente_por_email()) to
    the exact session_state keys _formulario_ficha_nueva()'s widgets
    read. Pre-seeding session_state with this mapping's output BEFORE
    that form renders is the standard Streamlit pattern for a
    programmatic default value -- see _cargar_ficha_para_revisar(), the
    only caller. Pure function, no Streamlit calls, easy to unit test
    independent of any live app.

    One real limitation, worked around rather than left broken:
    analitica_pdf (the bloodwork upload) has no Streamlit API for
    pre-seeding a file_uploader with a file, so a revision can't re-attach
    the original PDF -- but it doesn't need to. The already-extracted
    markers (salud.analitica_adjunta) are mapped here too, under
    "analitica_previa", which _formulario_ficha_nueva() falls back to
    when no new PDF is uploaded -- no re-analysis, no silently losing a
    known deficiency just because the trainer didn't re-upload the same
    file. A genuinely new bloodwork PDF uploaded during a revision still
    takes priority and replaces it."""
    datos = perfil["datos_basicos"]
    objetivo = perfil["objetivo"]
    experiencia = perfil["experiencia"]
    disponibilidad = perfil["disponibilidad"]
    salud = perfil["salud"]
    nutricion = perfil["nutricion"]
    estilo = perfil["estilo_de_vida"]
    lesiones = salud.get("lesiones") or []
    primera_lesion = lesiones[0] if lesiones else {}
    embarazo = salud.get("embarazo_o_lactancia") or {}

    return {
        "nombre": datos["nombre"],
        "edad": datos["edad"],
        "sexo_valor": datos["sexo"],
        "peso": datos["peso_kg"],
        "altura": datos["altura_cm"],
        "objetivo_valor": objetivo["principal"],
        "en_sus_palabras": objetivo.get("en_sus_palabras", ""),
        "nivel_valor": experiencia["nivel"],
        "anios": experiencia.get("anios_entrenando", 0.5),
        "detalle_experiencia": experiencia.get("detalle", ""),
        "dias": disponibilidad["dias_por_semana"],
        "minutos": disponibilidad["minutos_por_sesion"],
        "lugar_entreno_valor": disponibilidad["lugar_entreno"],
        "material_valor": disponibilidad.get("material_disponible", []),
        "tiene_lesion": bool(lesiones),
        "zona_lesion": primera_lesion.get("zona", ""),
        "descripcion_lesion": primera_lesion.get("descripcion", ""),
        "estado_lesion_valor": "activa" if primera_lesion.get("activa_actualmente") else "antigua_controlada",
        "enfermedades": ", ".join(salud.get("enfermedades_o_condiciones", [])),
        "medicacion": ", ".join(salud.get("medicacion_habitual", [])),
        "embarazo": bool(embarazo.get("aplica")),
        "detalle_embarazo": embarazo.get("detalle", ""),
        "alergias": ", ".join(salud.get("alergias_alimentarias", [])),
        "intolerancias": ", ".join(salud.get("intolerancias_alimentarias", [])),
        "tipo_dieta_valor": nutricion["tipo_dieta"],
        "restricciones": ", ".join(nutricion.get("restricciones", [])),
        "no_le_gustan": ", ".join(nutricion.get("alimentos_que_no_le_gustan", [])),
        "comidas": nutricion.get("comidas_al_dia_preferidas", 3),
        "contexto": nutricion.get("contexto", ""),
        "sueno": estilo.get("horas_sueno_promedio", 7.0),
        "estres_valor": estilo.get("nivel_estres_percibido", "medio"),
        "pasos": estilo.get("pasos_diarios_aprox", 6000),
        "tipo_trabajo": estilo.get("tipo_trabajo", ""),
        "notas_libres": perfil.get("notas_libres", ""),
        "analitica_previa": salud.get("analitica_adjunta"),
    }


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
    # A "Revise client" load (see _cargar_ficha_para_revisar()) pre-seeds
    # analitica_previa with whatever markers were already extracted and
    # saved for this client -- no re-upload, no re-analysis needed just to
    # regenerate a plan with everything else the same. Only surfaced when
    # relevant: a brand-new intake never has this key set.
    analitica_previa = st.session_state.get("analitica_previa")
    if analitica_previa and analitica_previa.get("tiene") and analitica_pdf is None:
        st.caption(t("bloodwork_kept_on_file").format(fecha=analitica_previa.get("fecha") or "?"))

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
    if analitica_pdf is not None:
        # A new upload always wins -- e.g. a follow-up blood test during a
        # revision is meant to supersede whatever was on file before.
        analitica_adjunta = {
            "tiene": True,
            "archivo": analitica_pdf.name,
            "fecha": ahora.date().isoformat(),
            "notas": "",
            "marcadores": analizar_pdf_analitica(analitica_pdf.getvalue())["marcadores"],
        }
    else:
        # No new upload this submission -- carry forward whatever was
        # already extracted and saved for this client (see
        # _cargar_ficha_para_revisar()/_campos_formulario_desde_perfil())
        # rather than silently discarding it just because file_uploader
        # can't be pre-seeded with a file. A brand-new client with no
        # bloodwork on file gets the same empty default as before.
        analitica_adjunta = st.session_state.get("analitica_previa") or {
            "tiene": False, "archivo": None, "fecha": None, "notas": "", "marcadores": [],
        }
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
            "analitica_adjunta": analitica_adjunta,
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
# Building the profile for the "Revise client" flow
# ---------------------------------------------------------------------------

def _cargar_ficha_para_revisar() -> dict | None:
    """A third front door into _formulario_ficha_nueva() (alongside the
    blank form and the PDF-upload path above): instead of starting from
    scratch, the trainer looks up an existing client by email
    (buscar_cliente_por_email(), which reads back the full profile
    guardar_registro_cliente()/actualizar_registro_cliente() now persist
    -- see docs/decisiones.md for why that's a real, requested schema
    change) and edits/regenerates from there. Reuses
    _formulario_ficha_nueva() completely unmodified: loading a profile
    just pre-seeds the same session_state keys those widgets already
    read (_campos_formulario_desde_perfil()), the standard Streamlit
    pattern for a programmatic default value -- st.rerun() right after
    guarantees the form's own widgets are instantiated fresh against
    that pre-seeded state, rather than relying on same-run ordering.

    Sets st.session_state["revisar_pagina_id"] on a successful load --
    read by the dispatch block below to correlate the eventual submitted
    profile back to the record to UPDATE rather than create.

    On top of _gate_datos_clientes()'s session-level unlock for this whole
    section, the actual lookup re-checks APPROVAL_PASSWORD every single
    time it runs (like _dialogo_aprobacion's per-click check, not a
    one-time flag) -- the session unlock only proves the trainer knew the
    password *once*; without this, anyone at an already-unlocked session
    (a shared screen, a laptop left open) could pull up *any* client's
    full health profile just by knowing their email, with nothing tying
    that specific lookup back to the trainer. Skipped entirely when
    APPROVAL_PASSWORD is unset, same "off" degradation as everywhere
    else -- local dev stays exactly as friction-free as before."""
    with st.expander(t("revise_client_header")):
        st.caption(t("revise_client_caption"))
        email_buscar = st.text_input(t("revise_client_email_label"), key="revisar_email")
        password_buscar = (
            st.text_input(t("revise_client_password_label"), type="password", key="revisar_password")
            if APPROVAL_PASSWORD else None
        )
        if email_buscar and st.button(t("revise_client_load_button"), key="revisar_cargar"):
            if APPROVAL_PASSWORD and password_buscar != APPROVAL_PASSWORD:
                # Deliberately doesn't call buscar_cliente_por_email() at all on a
                # wrong password -- falls through to the same, unmodified
                # _formulario_ficha_nueva() at the bottom of this function instead
                # of returning early, so a mistyped password never leaves the
                # trainer stuck without a form.
                st.error(t("approval_password_wrong"))
            else:
                try:
                    registro = buscar_cliente_por_email(email_buscar.strip())
                except (NotionClientError, ImportError, ModuleNotFoundError) as exc:
                    st.error(t("revise_client_error").format(error=str(exc)))
                    registro = None

                if registro is None:
                    st.warning(t("revise_client_not_found"))
                else:
                    for clave, valor in _campos_formulario_desde_perfil(registro["perfil"]).items():
                        st.session_state[clave] = valor
                    st.session_state["revisar_pagina_id"] = registro["id"]
                    st.session_state["revisar_cargado_nombre"] = registro["perfil"]["datos_basicos"]["nombre"]
                    st.rerun()

        if st.session_state.get("revisar_cargado_nombre"):
            st.success(t("revise_client_loaded").format(nombre=st.session_state["revisar_cargado_nombre"]))

    return _formulario_ficha_nueva()


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

def _render_stepper(pasos: list[tuple[str, bool]], advertencia: bool = False) -> None:
    """Horizontal step-progress indicator. `pasos` is [(label, completed),
    ...]; `advertencia` colors completed dots orange instead of teal (used
    for the enhanced-review pipeline outcome). Reused for both the
    orchestrator's own pipeline stages and the approve/email/confirm human
    workflow — one visual language for "what the AI did" and "what's left
    for the trainer to do."""
    clase = "tf-warn" if advertencia else "tf-done"
    nodos = []
    for indice, (etiqueta, hecho) in enumerate(pasos):
        if indice > 0:
            clase_linea = clase if pasos[indice - 1][1] else ""
            nodos.append(f'<div class="tf-step-line {clase_linea}"></div>')
        clase_nodo = clase if hecho else ""
        icono = "✓" if hecho else str(indice + 1)
        nodos.append(
            f'<div class="tf-step {clase_nodo}">'
            f'<span class="tf-step-dot {clase_nodo}">{icono}</span>'
            f'<span class="tf-step-label">{etiqueta}</span></div>'
        )
    st.markdown(f'<div class="tf-stepper">{"".join(nodos)}</div>', unsafe_allow_html=True)


def _ejecutar_y_mostrar(perfil: dict, guardar_en_notion: bool = False) -> None:
    with st.status(t("generating_status"), expanded=True) as status:
        def _al_transicionar(_cliente_id: str, nuevo_estado: str) -> None:
            status.write(f"✅ {ETIQUETAS_ESTADO[st.session_state.lang].get(nuevo_estado, nuevo_estado)}")

        estado = ejecutar_pipeline(perfil, on_transition=_al_transicionar, idioma=st.session_state.lang)
        status.update(
            label=t("plan_generated_status") if not estado.error else t("plan_error_status"),
            state="error" if estado.error else "complete",
        )

    if estado.error:
        st.error(t("could_not_generate").format(error=estado.error))
        return

    es_revision_reforzada = estado.veredicto["veredicto"] == "revision_reforzada"
    _render_stepper(
        [
            (t("step_routine"), "rutina_generada" in estado.historial),
            (t("step_diet"), "dieta_generada" in estado.historial),
            (t("step_validation"), "validado" in estado.historial),
            (t("step_ready_warn") if es_revision_reforzada else t("step_ready"), estado.estado.startswith("pendiente_")),
        ],
        advertencia=es_revision_reforzada,
    )

    st.divider()
    _mostrar_veredicto(estado.veredicto)

    col_rutina, col_dieta = st.columns(2)
    # Explicit `key=` gives Streamlit a stable "st-key-*" CSS class to target
    # (see _inyectar_estilos()) — the alternative, a data-testid on the
    # border wrapper, doesn't exist in this Streamlit version (the border is
    # applied directly to the shared stVerticalBlock element instead).
    with col_rutina, st.container(border=True, key="tf-card-rutina"):
        _mostrar_rutina(estado.borrador_rutina)
    with col_dieta, st.container(border=True, key="tf-card-dieta"):
        _mostrar_dieta(estado.borrador_dieta)

    st.divider()
    with st.container(border=True, key="tf-card-aprobacion"):
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
        f"{t('split_label')} {opt(rutina['split'])} · "
        f"{t('days_week_label')} {rutina['dias_por_semana']} · "
        f"{t('duration_label')} {rutina['duracion_sesion_min']} min"
    )

    for sesion in rutina["sesiones"]:
        with st.expander(sesion["dia"]):
            st.caption(sesion["calentamiento"])
            filas = [
                {
                    # Exercise "nombre" stays canonical English in the underlying
                    # dict (validator/JSON/email/Notion all rely on that — see
                    # exercise_bank.py's docstring); translated here for display only.
                    t("col_exercise"): ejercicio_mostrado(e["nombre"], st.session_state.lang),
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

    # Food "nombre" values stay canonical English in the underlying dict
    # (validator/JSON/email/Notion all rely on that — see food_bank.py's
    # docstring); translated here for display only.
    idioma = st.session_state.lang
    fuentes_verdura = dieta.get("fuentes_verdura_sugeridas", [])
    columnas = st.columns(4 if fuentes_verdura else 3)
    columnas[0].markdown(t("protein_sources_label") + "\n".join(f"- {alimento_mostrado(f, idioma)}" for f in dieta["fuentes_proteina_sugeridas"]))
    columnas[1].markdown(t("carb_sources_label") + "\n".join(f"- {alimento_mostrado(f, idioma)}" for f in dieta["fuentes_carbohidrato_sugeridas"]))
    columnas[2].markdown(t("fat_sources_label") + "\n".join(f"- {alimento_mostrado(f, idioma)}" for f in dieta["fuentes_grasa_sugeridas"]))
    if fuentes_verdura:
        columnas[3].markdown(t("veg_sources_label") + "\n".join(f"- {alimento_mostrado(f, idioma)}" for f in fuentes_verdura))

    if dieta["consejos_sinergias"]:
        with st.expander(t("synergy_tips_header")):
            for consejo in dieta["consejos_sinergias"]:
                st.markdown(f"- {consejo}")

    # plan_semanal is optional -- absent for a draft generated before this
    # field existed (or a hand-built one), same "degrades gracefully"
    # convention as every other optional field in this dict.
    if dieta.get("plan_semanal"):
        with st.expander(t("weekly_plan_header")):
            for dia_info in dieta["plan_semanal"]:
                st.markdown(f"**{dia_info['dia']}**")
                for comida in dia_info["comidas"]:
                    st.markdown(f"- *{comida['tipo']}* ({comida['aprox_kcal']} kcal): {comida['descripcion']}")

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
        # A profile submitted through the "Revise client" section updates
        # that same existing page instead of creating a new one — see
        # actualizar_registro_cliente()'s docstring on why Clients stays
        # one master record per client even for a revision.
        es_revision = st.session_state.get("revisar_perfil_id") == id(perfil)
        try:
            if es_revision:
                resultado = actualizar_registro_cliente(
                    st.session_state["revisar_pagina_id"], perfil, estado.borrador_rutina, estado.borrador_dieta,
                    estado.veredicto,
                )
            else:
                resultado = guardar_registro_cliente(
                    perfil, estado.borrador_rutina, estado.borrador_dieta, estado.veredicto,
                )
            st.session_state["notion_guardado_para"] = id(perfil)
            # Kept for the Gmail section below: it can't know the Notion
            # page to backfill the client's email onto otherwise, since the
            # trainer usually hasn't typed it in yet at approval time.
            st.session_state["notion_pagina_id"] = resultado["id"]
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


# English labels regardless of UI language, matching every Notion select
# value this project ever writes (see notion_connector.py's
# OBJETIVO_LABELS etc.) -- valoracion itself always comes back in English
# from Notion, so mapping from it stays in English too.
VALORACION_A_NUMERO = {"Low": 1, "Medium": 2, "High": 3}


def _render_grafico_tendencia(historial: list[dict]) -> None:
    """A simple trend chart from the same rows the list view below
    already renders -- no new query. historial is newest-first (that
    list view's own natural order); reversed once here for a
    left-to-right timeline. Weight and adherence rating are independent
    series -- a check-in missing one still contributes to the other,
    only rendered once there's an actual trend to show (2+ points; a
    single check-in has nothing to trend).

    st.line_chart() needs Altair to actually draw. streamlit's own
    package metadata declares it as a dependency, but a real, live
    instance of this app hit ModuleNotFoundError here anyway and
    crashed the whole page a client was on -- caught by live-testing,
    not assumed safe just because it "should" be there. Altair is now
    also an explicit, declared dependency of this project (see
    requirements.txt) rather than relying on it arriving transitively,
    and this still catches the import failure defensively on top of
    that, same "never crash over an optional visual" pattern already
    used for reportlab/pypdf/pdfplumber elsewhere in this project -- a
    missing chart library degrades to no chart, never a broken page."""
    cronologico = list(reversed(historial))

    filas_peso = [f for f in cronologico if f.get("peso_kg") is not None and f["fecha"]]
    filas_valoracion = [f for f in cronologico if f["valoracion"] in VALORACION_A_NUMERO and f["fecha"]]

    try:
        # Lazy import, same convention as reportlab/pypdf/pdfplumber
        # elsewhere in this project: the free rule-engine pipeline (and
        # every other section of this app) never needs pandas installed,
        # only these two chart-rendering paths do.
        import pandas as pd

        if len(filas_peso) >= 2:
            st.caption(t("history_chart_weight"))
            st.line_chart(pd.DataFrame({"kg": [f["peso_kg"] for f in filas_peso]}, index=[f["fecha"] for f in filas_peso]))

        if len(filas_valoracion) >= 2:
            st.caption(t("history_chart_adherence"))
            st.line_chart(
                pd.DataFrame(
                    {"adherence": [VALORACION_A_NUMERO[f["valoracion"]] for f in filas_valoracion]},
                    index=[f["fecha"] for f in filas_valoracion],
                )
            )
    except (ImportError, ModuleNotFoundError):
        pass


def _render_historial_checkins(email: str) -> None:
    """Renders a client's Check-ins history (a trend chart when there's
    enough data, then each row with rating/weight/notes, most recent
    first) -- shared by the trainer's own "Adherence history" expander in
    _panel_aprobacion() and the client portal's own history view in
    _vista_portal_cliente() below, so the row-formatting logic (and the
    "how it degrades on error" behavior) only lives in one place.
    Best-effort: a Notion failure shows a caption, never crashes
    whichever page called this."""
    try:
        historial = historial_checkins(email)
    except (NotionClientError, ImportError, ModuleNotFoundError) as exc:
        st.caption(t("adherence_history_error").format(error=str(exc)))
        return

    if not historial:
        st.caption(t("adherence_history_empty"))
        return

    _render_grafico_tendencia(historial)

    for fila in historial:
        etiqueta_valoracion = f" — {fila['valoracion']}" if fila["valoracion"] else ""
        etiqueta_peso = f" · {fila['peso_kg']} kg" if fila.get("peso_kg") is not None else ""
        st.markdown(f"**{fila['fecha'] or '?'}** · {fila['tipo'] or '?'}{etiqueta_valoracion}{etiqueta_peso}")
        if fila["notas"]:
            st.caption(fila["notas"])


def _panel_aprobacion(estado, guardar_en_notion: bool = False) -> None:
    perfil = estado.perfil_cliente

    # Gmail is locked until this exact plan has been approved above — a
    # trainer could otherwise create a real, addressed draft for a plan
    # they never actually signed off on. Re-checked on every rerun (not
    # just remembered from the click) via the same id(perfil) key so a
    # freshly generated/regenerated plan starts locked again.
    aprobado = st.session_state.get("aprobado_para") == id(perfil)

    st.markdown(t("approval_header"))
    _render_stepper([
        (t("mini_step_approve"), aprobado),
        (t("mini_step_email"), st.session_state.get("gmail_hilo_para") == id(perfil)),
        (t("mini_step_confirm"), st.session_state.get("checkin_registrado_para") == id(perfil)),
    ])

    if APPROVAL_PASSWORD:
        if st.button(t("approve_button"), type="primary"):
            st.session_state["mostrar_dialogo_aprobacion"] = True
        if st.session_state.get("mostrar_dialogo_aprobacion"):
            _dialogo_aprobacion(estado, guardar_en_notion)
    elif st.button(t("approve_button"), type="primary"):
        _ejecutar_aprobacion(estado, guardar_en_notion)

    # Read back from session_state (not shown directly at approval time) so
    # this survives the st.rerun() that closes the password dialog — see
    # _ejecutar_aprobacion()'s docstring.
    if aprobado:
        st.success(t("approved_success").format(time=st.session_state.get("aprobado_hora", "")))
        if guardar_en_notion and st.session_state.get("notion_error"):
            st.caption(t("notion_error_note").format(error=st.session_state["notion_error"]))

    st.markdown(t("gmail_section_header"))
    if not aprobado:
        st.info(t("gmail_requires_approval"))
    email_cliente = st.text_input(t("client_email_label"), key="email_cliente", disabled=not aprobado)
    if st.button(t("create_draft_button"), disabled=not aprobado):
        try:
            resultado_borrador = crear_borrador(
                email_cliente,
                perfil["datos_basicos"]["nombre"],
                estado.borrador_rutina,
                estado.borrador_dieta,
                idioma=st.session_state.lang,
            )
            st.success(t("draft_created_success").format(url=resultado_borrador["url"]))
            # Kept for the "check if sent" button below — same single-slot,
            # owner-checked pattern as notion_pagina_id/notion_guardado_para.
            st.session_state["gmail_hilo_id"] = resultado_borrador["thread_id"]
            st.session_state["gmail_hilo_para"] = id(perfil)
            st.session_state["checkin_registrado_para"] = None

            # Backfills the client's email onto their Notion record, ahead
            # of the "detect a real send" check below — the join key needs
            # to exist before the automation that will use it does.
            # Best-effort: a trainer using this without Notion configured
            # (or where the approval-time save failed) shouldn't see an
            # error over a background update for a feature they may not
            # even have set up.
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

    # "Check if sent" is trainer-triggered, not automatic: this is a
    # stateless Streamlit app with no push infrastructure to notice a send
    # passively (see gmail_client.py's docstring). Only shown once a draft
    # exists for *this* plan — same owner-check pattern as the Notion email
    # backfill above, so switching to a different client's plan doesn't
    # offer to check a thread that belongs to someone else.
    if st.session_state.get("gmail_hilo_para") == id(perfil):
        if st.button(t("check_send_status_button")):
            try:
                enviado = verificar_envio(st.session_state["gmail_hilo_id"])
            except (GmailClientError, ImportError, ModuleNotFoundError) as exc:
                st.error(t("checkin_error").format(error=str(exc)))
            else:
                if not enviado:
                    st.info(t("checkin_not_sent_yet"))
                elif st.session_state.get("checkin_registrado_para") != id(perfil):
                    # Guards against a repeated click after already logging
                    # this send from creating a second Check-ins row for the
                    # same event.
                    hoy = datetime.now().date().isoformat()
                    if st.session_state.get("notion_guardado_para") == id(perfil):
                        try:
                            marcar_email_enviado(st.session_state["notion_pagina_id"])
                        except (NotionClientError, ImportError, ModuleNotFoundError):
                            pass
                    try:
                        crear_registro_checkin(
                            email_cliente, perfil["datos_basicos"]["nombre"], "Plan sent", hoy,
                        )
                        st.session_state["checkin_registrado_para"] = id(perfil)
                        st.success(t("checkin_confirmed_send"))
                    except (NotionClientError, ImportError, ModuleNotFoundError) as exc:
                        st.error(t("checkin_error").format(error=str(exc)))
                else:
                    st.success(t("checkin_confirmed_send"))

    # Client portal: sends a real email (gmail.send, the one deliberate
    # exception to draft-only -- see gmail_client.py's module docstring)
    # with a magic link the client can follow to view a plan summary and
    # submit their own check-ins, without a PDF at all. Needs a Notion
    # page to point at (the portal reads obtener_registro_cliente() by
    # page ID), so it's only offered once *this* plan has actually been
    # saved there -- same owner-check pattern as everything else in this
    # function that depends on notion_pagina_id.
    if st.session_state.get("notion_guardado_para") == id(perfil):
        st.markdown(t("portal_section_header"))
        st.caption(t("portal_section_caption"))
        if st.button(t("send_portal_link_button"), disabled=not (aprobado and email_cliente)):
            try:
                token = generar_token_portal(email_cliente, st.session_state["notion_pagina_id"])
                url_portal = f"{PORTAL_BASE_URL}?portal_token={token}"
                enviar_enlace_portal(
                    email_cliente, perfil["datos_basicos"]["nombre"], url_portal, idioma=st.session_state.lang,
                )
                st.success(t("portal_link_sent_success"))
            except (GmailClientError, PortalTokenError, ImportError, ModuleNotFoundError) as exc:
                st.error(t("portal_link_error").format(error=str(exc)))

    # Independent of the Gmail draft state above: once an email is typed
    # in, the trainer can check what *this* client has already reported
    # over time, not just what happens with the plan just generated (a
    # returning client's history matters even when today's session is
    # about a brand new draft for them). Best-effort, same pattern as
    # every other optional Notion read/write in this panel.
    if email_cliente:
        with st.expander(t("adherence_history_header")):
            _render_historial_checkins(email_cliente)


def _vista_portal_cliente(token: str) -> None:
    """The entire page for a client who followed their own magic link
    (?portal_token=..., see agents/portal_tokens.py) -- rendered instead
    of the trainer's whole panel (sidebar, New Client/Example Client
    sections, approval password gate) when that query param is present.
    A client here never sees any of that; this function is a dead end,
    not a sub-section of the trainer's page."""
    st.title("TrainFitter")

    try:
        carga = verificar_token_portal(token)
    except PortalTokenError as exc:
        st.error(t("portal_invalid_link").format(error=str(exc)))
        return

    try:
        registro = obtener_registro_cliente(carga["pagina"])
    except (NotionClientError, ImportError, ModuleNotFoundError) as exc:
        st.error(t("portal_load_error").format(error=str(exc)))
        return

    nombre = registro["nombre"] or carga["email"]
    st.header(t("portal_welcome").format(nombre=nombre))
    if registro["fecha"]:
        st.caption(t("portal_since_label").format(fecha=registro["fecha"]))
    if registro["resumen"]:
        st.markdown(registro["resumen"])

    # Same row-formatting logic the trainer's own panel already uses (see
    # _render_historial_checkins()) -- a client only ever sees their own
    # history (carga["email"] comes from the signed token, never typed in),
    # same best-effort degrade-on-error behavior as everywhere else here.
    with st.expander(t("portal_history_header")):
        _render_historial_checkins(carga["email"])

    st.divider()
    st.subheader(t("portal_checkin_header"))
    st.caption(t("portal_checkin_intro"))

    # Standalone widgets, not st.form -- "completed" needs to react live
    # to whatever the client just set "total" to, and a form doesn't
    # rerun until submit, so that clamp wouldn't take effect until after
    # the fact. Same trade-off _formulario_ficha_nueva() already makes
    # above, for the same reason. Each "total"/checkbox widget is placed
    # -- and its value read -- BEFORE its matching "completed" widget, in
    # both code and visual order this time (no more side-by-side columns,
    # which read backwards: "completed" appeared before "total" was even
    # set). Sliders instead of bare number boxes -- a visual fill showing
    # where "completed" sits relative to "total" reads faster than two
    # unrelated-looking number fields, and st.progress() below adds an
    # explicit fraction for the same reason.
    st.markdown(f"**{t('portal_routine_section_title')}**")
    totales_rutina = st.slider(
        t("portal_routine_total_label"), min_value=1, max_value=14, value=7, key="portal_totales_rutina",
    )
    # Sessions completed is deliberately NOT capped at "planned" the way
    # diet days is below -- a client can genuinely train more than the
    # plan called for (an extra session), unlike "days I followed the
    # diet" which can't exceed the days actually in the check-in period.
    # The checkbox is an explicit, discoverable way to say "yes, really
    # more than planned" rather than silently allowing any number by
    # default, which would make a typo too easy to enter unnoticed.
    mas_de_lo_planeado = st.checkbox(t("portal_routine_more_than_planned_label"), key="portal_mas_de_lo_planeado")
    max_completados_rutina = 30 if mas_de_lo_planeado else int(totales_rutina)
    completados_rutina = st.slider(
        t("portal_routine_completed_label"), min_value=0, max_value=max_completados_rutina, value=0,
        key="portal_completados_rutina",
    )
    st.progress(
        min(completados_rutina / totales_rutina, 1.0), text=f"{completados_rutina}/{totales_rutina}",
    )
    notas_rutina = st.text_area(t("portal_routine_notes_label"), key="portal_notas_rutina")

    st.markdown(f"**{t('portal_diet_section_title')}**")
    totales_dieta = st.slider(
        t("portal_diet_total_label"), min_value=1, max_value=14, value=DIAS_SEMANA_DIETA, key="portal_totales_dieta",
    )
    # Diet days followed, unlike sessions above, IS hard-capped at the
    # total -- a real, definitional bound (you can't follow a diet for
    # more days than exist in the check-in period), not a target a client
    # might exceed. No override checkbox here on purpose.
    seguidos_dieta = st.slider(
        t("portal_diet_completed_label"), min_value=0, max_value=int(totales_dieta), value=0,
        key="portal_seguidos_dieta",
    )
    st.progress(min(seguidos_dieta / totales_dieta, 1.0), text=f"{seguidos_dieta}/{totales_dieta}")
    notas_dieta = st.text_area(t("portal_diet_notes_label"), key="portal_notas_dieta")

    # Optional, checkbox-gated like every other "share something extra"
    # field in this project (the injury/pregnancy detail fields in
    # _formulario_ficha_nueva()) -- closes a real loop the rule engines
    # already claim exists: dieta_reglas.py's own generated message tells
    # the client the plan "gets adjusted based on real weight ... over the
    # first few weeks", but until this field existed there was no path for
    # that number to ever reach anywhere (see mcp/notion_connector.py's
    # docstring on "Weight (kg)").
    st.markdown(f"**{t('portal_weight_section_title')}**")
    compartir_peso = st.checkbox(t("portal_share_weight_label"), key="portal_compartir_peso")
    peso_actual = None
    if compartir_peso:
        peso_actual = st.number_input(
            t("portal_weight_label"), min_value=30.0, max_value=250.0, value=70.0, step=0.5, key="portal_peso_actual",
        )

    enviado = st.button(t("portal_submit_button"), type="primary")

    if not enviado:
        return

    # Same data shape leer_checklist_pdf() produces (see
    # agents/pdf_generador.py) -- reuses resumir_adherencia()/
    # valoracion_desde_ratios() rather than reimplementing that
    # formatting a second time for this second submission channel.
    datos = {
        "dias_rutina_completados": int(completados_rutina),
        "dias_rutina_totales": int(totales_rutina),
        "notas_rutina": notas_rutina.strip(),
        "dias_dieta_seguidos": int(seguidos_dieta),
        "dias_dieta_totales": int(totales_dieta),
        "notas_dieta": notas_dieta.strip(),
    }
    ratios = []
    if datos["dias_rutina_totales"]:
        ratios.append(datos["dias_rutina_completados"] / datos["dias_rutina_totales"])
    if datos["dias_dieta_totales"]:
        ratios.append(datos["dias_dieta_seguidos"] / datos["dias_dieta_totales"])

    peso_kg = float(peso_actual) if compartir_peso else None
    valoracion = valoracion_desde_ratios(ratios)
    try:
        crear_registro_checkin(
            carga["email"], nombre, "Adherence check-in", datetime.now(timezone.utc).date().isoformat(),
            notas=resumir_adherencia(datos), valoracion=valoracion, peso_kg=peso_kg,
        )
    except (NotionClientError, ImportError, ModuleNotFoundError) as exc:
        st.error(t("portal_submit_error").format(error=str(exc)))
        return

    st.success(t("portal_submit_success"))

    # Best-effort, same spirit as actualizar_email_cliente()/
    # marcar_email_enviado() elsewhere in this file: the trainer
    # notification is a convenience on top of the real record (the
    # Notion row just saved above), never a reason to make the client's
    # own submission look like it failed if this part doesn't work.
    if TRAINER_NOTIFICATION_EMAIL:
        try:
            enviar_notificacion_checkin(
                TRAINER_NOTIFICATION_EMAIL, nombre, datos, valoracion, peso_kg, idioma=st.session_state.lang,
            )
        except (GmailClientError, ImportError, ModuleNotFoundError):
            pass


def _etiqueta_atencion(valoracion: str | None) -> str:
    """A quick visual flag for a client whose most recent check-in rated
    Low -- see _panel_todos_los_clientes()'s docstring on why this
    overview exists at all. Pure function, no I/O."""
    if valoracion == "Low":
        return f"⚠️ {valoracion}"
    return valoracion or ""


def _datos_clientes_desbloqueados() -> bool:
    """Whether the trainer has already unlocked the sections that expose
    real clients' personal data this browser session. Unset
    APPROVAL_PASSWORD means there's nothing to unlock -- same "off"
    degradation as every other optional secret in this file (local dev,
    the common case, is never gated)."""
    return (not APPROVAL_PASSWORD) or st.session_state.get("clientes_desbloqueado", False)


def _gate_datos_clientes() -> bool:
    """Password gate in front of "Revise client" and "Clients" -- unlike
    every other section, both put a real client's personal data on
    screen (at minimum an email; Revise client's lookup surfaces the
    full profile, including injuries/allergies/weight) just by clicking
    a tab, with no button-click consequence to gate the way Approve's
    own APPROVAL_PASSWORD dialog (_dialogo_aprobacion) does. On a public
    demo, anyone could otherwise browse real clients' contact info and
    health data. Reuses that same APPROVAL_PASSWORD rather than adding a
    second secret -- one password, two things it protects; unset (local
    dev) means both sections render exactly as before.

    Unlocking is a session-level flag, not per-view like the approval
    dialog: browsing a roster is a "look around" action repeated many
    times, not one consequential click, so re-prompting on every rerun
    would be friction with no real safety benefit once the trainer has
    proven who they are once this session. Returns True (nothing left to
    render) once unlocked, False while the prompt itself is still
    showing."""
    if _datos_clientes_desbloqueados():
        return True
    st.info(t("clients_gate_info"))
    password_ingresada = st.text_input(
        t("clients_gate_password_label"), type="password", key="clientes_password_gate",
    )
    if st.button(t("clients_gate_unlock_button"), key="clientes_desbloquear_boton"):
        if password_ingresada == APPROVAL_PASSWORD:
            st.session_state["clientes_desbloqueado"] = True
            st.rerun()
        else:
            st.error(t("approval_password_wrong"))
    return False


def _panel_todos_los_clientes() -> None:
    """The trainer's client roster: every real "New Client"/"Revise
    client" record at a glance, joined with each client's most recent
    Check-ins row so a client who needs attention (a Low adherence
    rating, or no check-in at all) stands out without opening Notion or
    looking each client up individually by email -- the only way to see
    this before now. Read-only: this section never generates or saves
    anything, only lists what's already there. Two separate,
    independently best-effort queries (see listar_clientes()/
    ultimo_checkin_por_cliente()'s own docstrings): a failure in the
    second one still leaves the roster itself useful, just without the
    adherence column."""
    st.markdown(t("clients_panel_header"))
    st.caption(t("clients_panel_caption"))

    try:
        clientes = listar_clientes()
    except (NotionClientError, ImportError, ModuleNotFoundError) as exc:
        st.error(t("clients_panel_error").format(error=str(exc)))
        return

    if not clientes:
        st.caption(t("clients_panel_empty"))
        return

    try:
        ultimos_checkins = ultimo_checkin_por_cliente()
    except (NotionClientError, ImportError, ModuleNotFoundError):
        ultimos_checkins = {}

    filas = []
    for cliente in clientes:
        ultimo = ultimos_checkins.get(cliente["email"] or "")
        filas.append({
            t("clients_col_name"): cliente["nombre"],
            t("clients_col_email"): cliente["email"] or "",
            t("clients_col_date"): cliente["fecha"] or "",
            t("clients_col_goal"): cliente["objetivo"] or "",
            t("clients_col_level"): cliente["nivel"] or "",
            t("clients_col_verdict"): cliente["veredicto"] or "",
            t("clients_col_email_sent"): "✅" if cliente["email_enviado"] else "",
            t("clients_col_last_checkin"): (ultimo["fecha"] if ultimo else "") or "",
            t("clients_col_last_rating"): _etiqueta_atencion(ultimo["valoracion"]) if ultimo else "",
        })

    # A plain list of dicts, not pd.DataFrame(filas) -- st.dataframe()
    # already accepts one natively, so this whole section never needs
    # pandas at all (unlike the trend charts above, which genuinely do).
    st.dataframe(filas, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

# A client following their own magic link gets ONLY this view -- never the
# trainer's sidebar, New Client/Example Client sections, or anything
# behind APP_APPROVAL_PASSWORD. Checked before any of that renders, not
# nested inside it, so there's no path where a client's browser ever
# builds the trainer-facing DOM at all.
_token_portal = st.query_params.get("portal_token")
if _token_portal:
    _vista_portal_cliente(_token_portal)
    st.stop()

with st.sidebar:
    if ICON_PATH.exists():
        st.image(str(ICON_PATH), width=120)

    # Reserves this slot in the visual order right here (between the icon
    # and the language radio below), but is only filled in *after*
    # st.session_state.lang is updated by the radio -- otherwise this
    # tagline would render one rerun stale relative to everything below it,
    # since a plain st.markdown() call here would read the *old* language
    # value (the assignment happens later in the script on this same run).
    tagline_slot = st.empty()

    lang_choice = st.radio(
        "🌐 Language / Idioma",
        ["en", "es"],
        format_func=lambda k: "English" if k == "en" else "Español",
        index=0 if st.session_state.lang == "en" else 1,
        key="lang_radio",
        horizontal=True,
    )
    st.session_state.lang = lang_choice
    tagline_slot.markdown(f'<p class="tf-sidebar-tagline">{t("sidebar_tagline")}</p>', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="tf-sidebar-about">
            <p class="tf-sidebar-about-title">{t("sidebar_about_header")}</p>
            <ul>
                <li>{t("sidebar_about_routine")}</li>
                <li>{t("sidebar_about_diet")}</li>
                <li>{t("sidebar_about_safety")}</li>
                <li>{t("sidebar_about_approval")}</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="tf-sidebar-footer">
            <a class="tf-sidebar-github" href="https://github.com/serpeigd/TrainFitter" target="_blank" rel="noopener">
                <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
                0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58
                1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
                -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82
                2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48
                0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path></svg>
                {t("sidebar_footer_github")}
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )

_inyectar_estilos()

# Cover banner (assets/Cropped.jpg) — the wordmark baked into the photo is
# just "TrainFitter" (no language-specific copy), so unlike the old
# logo.jpg crop there's no EN/ES mismatch to worry about here; the
# translatable title/subtitle right below it in .tf-hero cover that.
# Always rendered, no session_state involved — a permanent fixture shown
# at its own aspect ratio (see .tf-banner-wrap in _inyectar_estilos())
# rather than a one-time splash. Two animated versions were tried and
# abandoned before this one: scroll-linked (broken by Streamlit Cloud's
# iframe) and a timed reveal-then-vanish (functional, but the project
# owner preferred it just staying put).
_banner_b64 = _banner_base64()
if _banner_b64:
    st.markdown(
        f'<div class="tf-banner-wrap">'
        f'<img class="tf-banner" src="data:image/jpeg;base64,{_banner_b64}" alt="TrainFitter"></div>',
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
SECCIONES = ["nueva", "revisar", "clientes", "ejemplo"]  # "New Client" first, per the trainer's workflow
seccion_activa = st.segmented_control(
    "navigation",
    SECCIONES,
    format_func=lambda k: {
        "nueva": t("tab_new_intake"), "revisar": t("tab_revise_client"),
        "clientes": t("tab_clients"), "ejemplo": t("tab_example"),
    }[k],
    default="nueva",
    key="seccion_activa",
    label_visibility="collapsed",
)

# The generated plan is rendered *inside* whichever section produced it,
# tagged with "ultimo_origen" — otherwise it would stay visible after
# switching to the other section, which has nothing to do with it.
if seccion_activa == "nueva":
    perfil_nuevo = _cargar_ficha_desde_pdf()
    if perfil_nuevo is None:
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

elif seccion_activa == "revisar":
    if _gate_datos_clientes():
        perfil_revisado = _cargar_ficha_para_revisar()
        if perfil_revisado is not None:
            st.session_state["ultimo_perfil"] = perfil_revisado
            st.session_state["ultimo_origen"] = "revisar"
            # Correlates THIS exact submission to the Clients page being
            # revised -- id() is stable for this specific dict object across
            # reruns once stored in ultimo_perfil (same pattern
            # notion_guardado_para/aprobado_para etc. already use below), and
            # is captured at the one moment this dict is actually created, so
            # it can't be confused with a different profile that happens to
            # be submitted later in the same session.
            st.session_state["revisar_perfil_id"] = id(perfil_revisado)
        if st.session_state.get("ultimo_origen") == "revisar":
            _ejecutar_y_mostrar(st.session_state["ultimo_perfil"], guardar_en_notion=True)

elif seccion_activa == "clientes":
    if _gate_datos_clientes():
        _panel_todos_los_clientes()

elif seccion_activa == "ejemplo":
    perfil_ejemplo = _selector_cliente_ejemplo()
    if perfil_ejemplo is not None:
        st.session_state["ultimo_perfil"] = perfil_ejemplo
        st.session_state["ultimo_origen"] = "ejemplo"
    if st.session_state.get("ultimo_origen") == "ejemplo":
        _ejecutar_y_mostrar(st.session_state["ultimo_perfil"])
