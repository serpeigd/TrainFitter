"""
Adherence parser: reads the plain-text checklist a client sends back (see
mcp/gmail_client.py's _construir_checklist_adherencia()) after actually
starting their plan, and extracts what they really did — which routine
days they completed, how many of the last week's days they followed the
diet, and their free-text notes on both.

DESIGN — anchored on fixed bracket tags, not on the surrounding sentence:
the checklist's human-readable questions are translated (English/Spanish,
matching whatever idioma the plan was generated in), but the three tags
this parser looks for ([ROUTINE NOTES BELOW], [DIET DAYS FOLLOWED, out of
N], [DIET NOTES BELOW]) are always emitted verbatim regardless of idioma —
see that function's docstring for why. This module never has to know or
guess which language a given reply is in.

DESIGN — best-effort, not strict: a client editing a plain-text email by
hand can delete a tag, reorder sections, or leave an answer blank. Missing
pieces come back as None/empty rather than raising — same principle as
analytics_parser.py's bloodwork extraction (a marker the parser can't find
is just skipped, never blocks the rest of the pipeline). main.py is
expected to still record whatever partial data came back.

DESIGN — the rating is a simple heuristic, not a judgment: `valoracion`
looks only at the completion ratios and is meant purely to give the
trainer a quick sort/filter signal in Notion — it never influences
anything else. The trainer's own read of the free-text notes always
matters more than this number.
"""

import re

TAG_NOTAS_RUTINA = "[ROUTINE NOTES BELOW]"
TAG_NOTAS_DIETA = "[DIET NOTES BELOW]"
PATRON_DIAS_DIETA = re.compile(r"^\[DIET DAYS FOLLOWED, out of (\d+)\]\s*$", re.MULTILINE)
PATRON_CASILLA = re.compile(r"^\[([ xX])\]\s*(.+)$", re.MULTILINE)


def _capturar_bloque(texto: str, desde: int) -> str:
    """Returns the free-text answer starting right after a tag line (at
    character offset `desde`, already past the tag itself) up to whichever
    comes first: the next bracket-tag line, the next "==" section header,
    or the end of the text. Strips a leading "> " prompt per line, since
    that's what the template ships with, and blank lines around the answer
    -- pure text manipulation, no I/O."""
    resto = texto[desde:]
    candidatos = [i for i in (resto.find("\n["), resto.find("\n==")) if i != -1]
    bloque = resto if not candidatos else resto[: min(candidatos)]
    lineas = [linea[1:].strip() if linea.strip().startswith(">") else linea for linea in bloque.splitlines()]
    return "\n".join(linea for linea in lineas if linea.strip()).strip()


def _valoracion(ratios: list[float]) -> str:
    """Averages whichever completion ratios are actually available (routine
    and/or diet -- a reply missing one of them still gets rated on the
    other) into a coarse Low/Medium/High signal. English labels regardless
    of the reply's language, matching every other Notion select value in
    this project (see notion_connector.py's OBJETIVO_LABELS etc.)."""
    promedio = sum(ratios) / len(ratios)
    if promedio >= 0.8:
        return "High"
    if promedio >= 0.5:
        return "Medium"
    return "Low"


def analizar_adherencia(texto_checklist: str) -> dict:
    """
    Parses a client's returned adherence checklist into structured data.

    Args:
        texto_checklist: the raw text content of the attachment the client
            sent back (see mcp.gmail_client.buscar_respuestas_adherencia()).

    Returns:
        {
            "dias_rutina_completados": int, "dias_rutina_totales": int,
            "notas_rutina": str,
            "dias_dieta_seguidos": int | None, "dias_dieta_totales": int | None,
            "notas_dieta": str,
            "valoracion": "Low" | "Medium" | "High" | None (None only when
                neither routine checkboxes nor a diet days-followed answer
                could be found at all -- an unparseable reply),
        }
    """
    casillas = PATRON_CASILLA.findall(texto_checklist)
    dias_rutina_totales = len(casillas)
    dias_rutina_completados = sum(1 for marca, _dia in casillas if marca.lower() == "x")

    notas_rutina = ""
    coincidencia = re.search(rf"^{re.escape(TAG_NOTAS_RUTINA)}\s*$", texto_checklist, re.MULTILINE)
    if coincidencia:
        notas_rutina = _capturar_bloque(texto_checklist, coincidencia.end())

    dias_dieta_totales = None
    dias_dieta_seguidos = None
    coincidencia_dieta = PATRON_DIAS_DIETA.search(texto_checklist)
    if coincidencia_dieta:
        dias_dieta_totales = int(coincidencia_dieta.group(1))
        respuesta = _capturar_bloque(texto_checklist, coincidencia_dieta.end())
        numero = re.search(r"\d+", respuesta)
        if numero:
            dias_dieta_seguidos = min(int(numero.group(0)), dias_dieta_totales)

    notas_dieta = ""
    coincidencia = re.search(rf"^{re.escape(TAG_NOTAS_DIETA)}\s*$", texto_checklist, re.MULTILINE)
    if coincidencia:
        notas_dieta = _capturar_bloque(texto_checklist, coincidencia.end())

    ratios = []
    if dias_rutina_totales:
        ratios.append(dias_rutina_completados / dias_rutina_totales)
    # Only counted when the client actually gave a number -- a blank
    # answer (tag found, nothing filled in) isn't the same as "followed 0
    # days" and shouldn't drag the rating down as if it were.
    if dias_dieta_totales and dias_dieta_seguidos is not None:
        ratios.append(dias_dieta_seguidos / dias_dieta_totales)

    return {
        "dias_rutina_completados": dias_rutina_completados,
        "dias_rutina_totales": dias_rutina_totales,
        "notas_rutina": notas_rutina,
        "dias_dieta_seguidos": dias_dieta_seguidos,
        "dias_dieta_totales": dias_dieta_totales,
        "notas_dieta": notas_dieta,
        "valoracion": _valoracion(ratios) if ratios else None,
    }


def resumir_adherencia(datos: dict) -> str:
    """Turns analizar_adherencia()'s structured output into the short plain-
    text summary main.py saves as a Check-ins "Adherence notes" property.
    Pure formatting, no I/O."""
    partes = [f"Routine: {datos['dias_rutina_completados']}/{datos['dias_rutina_totales']} sessions completed."]
    if datos["notas_rutina"]:
        partes.append(f"Routine notes: {datos['notas_rutina']}")

    if datos["dias_dieta_totales"]:
        seguidos = datos["dias_dieta_seguidos"] if datos["dias_dieta_seguidos"] is not None else "?"
        partes.append(f"Diet: {seguidos}/{datos['dias_dieta_totales']} days followed.")
    if datos["notas_dieta"]:
        partes.append(f"Diet notes: {datos['notas_dieta']}")

    return " ".join(partes)[:2000]  # Notion rich_text limit, same truncation as notion_connector.py
