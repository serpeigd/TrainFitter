"""
Adherence summary formatting: turns the structured data read back from a
client's filled-in checklist PDF (see agents/pdf_generador.py's
leer_checklist_pdf()) into the short plain-text summary main.py saves on a
Notion Check-ins row, plus the shared Low/Medium/High rating heuristic both
that module and this one use.

DESIGN — the rating is a simple heuristic, not a judgment: `valoracion`
looks only at the completion ratios and is meant purely to give the
trainer a quick sort/filter signal in Notion — it never influences
anything else. The trainer's own read of the free-text notes always
matters more than this number. See
docs/base_conocimiento/adherencia_y_cambio_de_conducta.md: this whole
loop exists because self-monitoring's real value shows up in what a
*human* does with it afterward, not in the number itself.

Note: this module used to also parse a plain-text, tag-anchored checklist
(the client's reply was a .txt attachment). That format was replaced by a
fillable PDF form (see docs/decisiones.md) — pdf_generador.py now owns
extracting structured data from a reply, this module just formats it.
"""

from datetime import date


def valoracion_desde_ratios(ratios: list[float]) -> str | None:
    """Averages whichever completion ratios are actually available (routine
    and/or diet -- a reply missing one of them still gets rated on the
    other) into a coarse Low/Medium/High signal. English labels regardless
    of the reply's language, matching every other Notion select value in
    this project (see notion_connector.py's OBJETIVO_LABELS etc.). Returns
    None when given no ratios at all -- an unparseable reply with nothing
    to rate."""
    if not ratios:
        return None
    promedio = sum(ratios) / len(ratios)
    if promedio >= 0.8:
        return "High"
    if promedio >= 0.5:
        return "Medium"
    return "Low"


def sugerencia_seguimiento(valoracion: str | None) -> str:
    """A short, rule-based "what to consider next" line for the trainer --
    used by ui/app.py's portal check-in notification email
    (see mcp/gmail_client.py's enviar_notificacion_checkin()). Same
    heuristic spirit as valoracion_desde_ratios(): a quick, deterministic
    signal to prompt the trainer's own judgment, never a replacement for
    it -- see docs/base_conocimiento/adherencia_y_cambio_de_conducta.md,
    the same evidence already backing this whole check-in loop's design
    (Lally et al. 2010 on a missed day not being a failure state is why
    "Low" reads as "worth a conversation", not "the client failed")."""
    if valoracion == "High":
        return "Adherence looks strong -- a good moment to consider a small progression next cycle."
    if valoracion == "Medium":
        return "Decent adherence, but worth a quick check-in to see what's getting in the way before adding difficulty."
    if valoracion == "Low":
        return "Adherence is low -- treat this as a signal to simplify the plan or address a real barrier, not to push progress."
    return "Not enough data in this check-in to gauge adherence -- consider following up directly."


def checklist_tiene_contenido_real(datos: dict) -> bool:
    """Whether a parsed checklist shows any real sign of having been
    filled in, as opposed to being structurally intact but blank.
    leer_checklist_pdf()'s `valoracion` only comes back None when a PDF
    has none of the expected fields at all -- a genuinely blank checklist
    (the trainer's own sent original, or a client forwarding it unfilled)
    still has every checkbox/text field present, just empty/unchecked,
    which computes to a real "Low" rating rather than None. This is the
    second, independent safety net that makes it safe for
    mcp.gmail_client.buscar_respuestas_adherencia() to accept forwards
    (not just in-thread replies) without risking a false adherence entry
    -- see that function's own docstring and docs/decisiones.md.

    Args:
        datos: same shape as pdf_generador.leer_checklist_pdf()'s return
            value.
    """
    if datos["dias_rutina_completados"] > 0:
        return True
    if datos["notas_rutina"] or datos["notas_dieta"]:
        return True
    # Explicitly answered (even "0 days") is real signal; None means the
    # question was left blank, not that the answer was zero.
    if datos["dias_dieta_seguidos"] is not None:
        return True
    return False


def resumir_adherencia(datos: dict) -> str:
    """Turns leer_checklist_pdf()'s structured output into the short plain-
    text summary main.py saves as a Check-ins "Adherence notes" property.
    Pure formatting, no I/O.

    Args:
        datos: {"dias_rutina_completados", "dias_rutina_totales",
            "notas_rutina", "dias_dieta_seguidos", "dias_dieta_totales",
            "notas_dieta"} -- see pdf_generador.leer_checklist_pdf().
    """
    partes = []
    # dias_rutina_totales == 0 means no routine checkboxes were found at
    # all (e.g. the checklist PDF's routine section was left completely
    # untouched in a way that couldn't be read) -- "0/0 sessions completed"
    # would misleadingly read as "did zero sessions" rather than "no
    # routine data in this reply", so the line is skipped entirely instead,
    # same as the diet line already does below.
    if datos["dias_rutina_totales"]:
        partes.append(f"Routine: {datos['dias_rutina_completados']}/{datos['dias_rutina_totales']} sessions completed.")
    if datos["notas_rutina"]:
        partes.append(f"Routine notes: {datos['notas_rutina']}")

    if datos["dias_dieta_totales"]:
        seguidos = datos["dias_dieta_seguidos"] if datos["dias_dieta_seguidos"] is not None else "?"
        partes.append(f"Diet: {seguidos}/{datos['dias_dieta_totales']} days followed.")
    if datos["notas_dieta"]:
        partes.append(f"Diet notes: {datos['notas_dieta']}")

    return " ".join(partes)[:2000]  # Notion rich_text limit, same truncation as notion_connector.py


# Only goals with an unambiguous expected weight direction get a trend
# check at all -- deliberately excludes "recomposicion_corporal" (fat
# loss + muscle gain can net to ~stable weight, so weight alone says very
# little) and "salud_general" (no specific weight target). Same "don't
# flag what you can't actually interpret" discipline as this project's
# dietary-concern presets (see docs/decisiones.md) -- a guess dressed up
# as a signal is worse than no signal.
_DIRECCION_ESPERADA = {"perdida_grasa": "abajo", "hipertrofia": "arriba"}

# Smaller than this over the whole window reads as normal day-to-day
# weight noise (water, food timing, bathroom trips), not a real trend
# either way -- not worth telling the trainer "no progress" over half a
# kilo of noise.
UMBRAL_KG_TENDENCIA = 0.3
# Shorter than this, weight fluctuation alone can't distinguish a real
# trend from noise -- same reasoning as the kg threshold above, just on
# the time axis.
DIAS_MINIMOS_TENDENCIA = 10


def tendencia_peso(historial: list[dict], objetivo: str | None, idioma: str = "en") -> str | None:
    """Flags a real mismatch between a client's logged weight trend and
    their goal's expected direction -- e.g. weight not trending down
    despite a fat-loss goal. Returns None (nothing worth flagging) when:
    the goal has no clear expected direction (see _DIRECCION_ESPERADA),
    fewer than two check-ins actually logged a weight, the two furthest-
    apart ones span under DIAS_MINIMOS_TENDENCIA days, or the trend
    already matches the goal.

    Deliberately just a nudge for the trainer to look at, never anything
    that touches the diet's own calorie math automatically -- this
    project's "the trainer always reviews before anything changes"
    principle applies here exactly as everywhere else; see
    dieta_reglas.AJUSTE_CALORICO, which this function never calls.

    Args:
        historial: notion_connector.historial_checkins()'s own return
            shape ({"fecha", "tipo", "valoracion", "notas", "peso_kg"}
            dicts, any order -- this function sorts by fecha itself).
        objetivo: perfil_cliente["objetivo"]["principal"], or the
            notion_connector-resolved equivalent (see
            notion_connector._fila_registro_cliente_desde_pagina()'s
            "objetivo" -- the portal-safe read this function is meant to
            be usable with, never needing the full profile).
        idioma: "en" (default) or "es" -- language of the returned
            sentence, matching every other trainer/client-facing string
            in this project.
    """
    direccion = _DIRECCION_ESPERADA.get(objetivo)
    if direccion is None:
        return None

    con_peso = sorted(
        (
            (fila["fecha"], fila["peso_kg"])
            for fila in historial
            if fila.get("peso_kg") is not None and fila.get("fecha")
        ),
        key=lambda par: par[0],
    )
    if len(con_peso) < 2:
        return None

    primera_fecha, primer_peso = con_peso[0]
    ultima_fecha, ultimo_peso = con_peso[-1]
    try:
        dias = (date.fromisoformat(ultima_fecha) - date.fromisoformat(primera_fecha)).days
    except ValueError:
        return None  # malformed date string somewhere -- degrade to "nothing to flag", not a crash

    if dias < DIAS_MINIMOS_TENDENCIA:
        return None

    cambio_kg = round(ultimo_peso - primer_peso, 1)
    tendencia_va_bien = (direccion == "abajo" and cambio_kg <= -UMBRAL_KG_TENDENCIA) or (
        direccion == "arriba" and cambio_kg >= UMBRAL_KG_TENDENCIA
    )
    if tendencia_va_bien:
        return None

    if idioma == "es":
        meta = "un objetivo de pérdida de grasa" if direccion == "abajo" else "un objetivo de hipertrofia"
        return (
            f"El peso no ha bajado en los últimos {dias} días" if direccion == "abajo"
            else f"El peso no ha subido en los últimos {dias} días"
        ) + (
            f" ({primer_peso}kg -> {ultimo_peso}kg) pese a {meta} — merece la pena comprobar si se está "
            "siguiendo la dieta de verdad, o revisar el objetivo calórico en la próxima revisión."
        )

    meta = "a fat-loss goal" if direccion == "abajo" else "a hypertrophy goal"
    return (
        f"Weight hasn't trended {('down' if direccion == 'abajo' else 'up')} over the last {dias} days "
        f"({primer_peso}kg -> {ultimo_peso}kg) despite {meta} -- worth checking the diet is actually "
        "being followed, or reviewing the calorie target on the next revision."
    )
