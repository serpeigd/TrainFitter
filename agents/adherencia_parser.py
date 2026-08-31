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

from datetime import date, timedelta


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


def sugerencia_seguimiento(valoracion: str | None, idioma: str = "en") -> str:
    """A short, rule-based "what to consider next" line for the trainer --
    used by ui/app.py's portal check-in notification email
    (see mcp/gmail_client.py's enviar_notificacion_checkin()). Same
    heuristic spirit as valoracion_desde_ratios(): a quick, deterministic
    signal to prompt the trainer's own judgment, never a replacement for
    it -- see docs/base_conocimiento/adherencia_y_cambio_de_conducta.md,
    the same evidence already backing this whole check-in loop's design
    (Lally et al. 2010 on a missed day not being a failure state is why
    "Low" reads as "worth a conversation", not "the client failed").

    idioma: "en" (default) or "es" -- real, reported bug: this used to
    always return English regardless of the client's own plan language,
    so a Spanish client's portal check-in produced a trainer notification
    email mixing Spanish (the client's own free-text notes) with English
    (this line and resumir_adherencia()'s labels)."""
    if idioma == "es":
        if valoracion == "High":
            return "La adherencia se ve sólida -- buen momento para plantear una pequeña progresión en el próximo ciclo."
        if valoracion == "Medium":
            return (
                "Adherencia decente, pero vale la pena hacer un check-in rápido para ver qué está dificultando "
                "las cosas antes de subir la exigencia."
            )
        if valoracion == "Low":
            return (
                "La adherencia es baja -- tómalo como una señal para simplificar el plan o abordar una barrera "
                "real, no para forzar el progreso."
            )
        return "No hay suficientes datos en este check-in para valorar la adherencia -- considera hacer un seguimiento directo."
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


def resumir_adherencia(datos: dict, idioma: str = "en") -> str:
    """Turns leer_checklist_pdf()'s structured output into the short plain-
    text summary main.py saves as a Check-ins "Adherence notes" property
    (and ui/app.py's portal check-in form reuses for the same field).
    Pure formatting, no I/O.

    Args:
        datos: {"dias_rutina_completados", "dias_rutina_totales",
            "notas_rutina", "dias_dieta_seguidos", "dias_dieta_totales",
            "notas_dieta"} -- see pdf_generador.leer_checklist_pdf().
        idioma: "en" (default) or "es" -- real, reported bug: these labels
            used to always be English regardless of the client's own plan
            language, so a Spanish client's check-in mixed English labels
            with their own Spanish free-text notes in the same summary
            (both here and in the trainer notification email built from
            it -- see sugerencia_seguimiento()'s matching fix).
    """
    etiquetas = _ETIQUETAS_RESUMEN[idioma]
    partes = []
    # dias_rutina_totales == 0 means no routine checkboxes were found at
    # all (e.g. the checklist PDF's routine section was left completely
    # untouched in a way that couldn't be read) -- "0/0 sessions completed"
    # would misleadingly read as "did zero sessions" rather than "no
    # routine data in this reply", so the line is skipped entirely instead,
    # same as the diet line already does below.
    if datos["dias_rutina_totales"]:
        partes.append(
            etiquetas["rutina"].format(
                completados=datos["dias_rutina_completados"], totales=datos["dias_rutina_totales"],
            )
        )
    if datos["notas_rutina"]:
        partes.append(f"{etiquetas['notas_rutina']}: {datos['notas_rutina']}")

    if datos["dias_dieta_totales"]:
        seguidos = datos["dias_dieta_seguidos"] if datos["dias_dieta_seguidos"] is not None else "?"
        partes.append(etiquetas["dieta"].format(seguidos=seguidos, totales=datos["dias_dieta_totales"]))
    if datos["notas_dieta"]:
        partes.append(f"{etiquetas['notas_dieta']}: {datos['notas_dieta']}")

    return " ".join(partes)[:2000]  # Notion rich_text limit, same truncation as notion_connector.py


_ETIQUETAS_RESUMEN = {
    "en": {
        "rutina": "Routine: {completados}/{totales} sessions completed.",
        "notas_rutina": "Routine notes",
        "dieta": "Diet: {seguidos}/{totales} days followed.",
        "notas_dieta": "Diet notes",
    },
    "es": {
        "rutina": "Rutina: {completados}/{totales} sesiones completadas.",
        "notas_rutina": "Notas de rutina",
        "dieta": "Dieta: {seguidos}/{totales} días seguidos.",
        "notas_dieta": "Notas de dieta",
    },
}


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


_VENTANA_RESUMEN_MENSUAL_DIAS = 30
# Same numeric mapping ui/app.py's VALORACION_A_NUMERO already uses for its
# adherence trend chart -- duplicated rather than imported, since ui/app.py
# imports FROM this module, not the other way around.
_VALORACION_A_NUMERO_RESUMEN = {"Low": 1, "Medium": 2, "High": 3}
_NUMERO_A_ETIQUETA_TENDENCIA = {
    "en": {1: "low", 2: "moderate", 3: "strong"},
    "es": {1: "baja", 2: "media", 3: "alta"},
}


def resumen_mensual_tendencia(historial: list[dict], idioma: str = "en") -> str | None:
    """A short, free, rule-based monthly digest -- an adherence trend label
    plus a weight change -- built from the exact same Check-ins rows
    _render_historial_checkins() (ui/app.py) already fetches; no new
    Notion query needed.

    Directly grounded in competitor research: a paid coaching app's "AI
    Monthly Report" feature (see docs/decisiones.md), reproduced here as a
    deterministic aggregation instead of an LLM call -- this project's
    free-only guardrail (CLAUDE.md) applies to this too. Deliberately just
    a digest for the trainer/client to read: never touches the diet's own
    calorie math automatically, same "trainer always reviews" principle as
    tendencia_peso(), which this function complements rather than
    replaces -- that one flags a goal MISMATCH (needs an objetivo); this
    one just reports what happened over the last month, no goal needed.

    Returns None when the last _VENTANA_RESUMEN_MENSUAL_DIAS days don't
    have enough to summarize (no real adherence check-ins in that window,
    AND fewer than two weight points) -- same "don't fabricate a trend
    from one data point" discipline as tendencia_peso().

    Args:
        historial: notion_connector.historial_checkins()'s own return
            shape ({"fecha", "tipo", "valoracion", "notas", "peso_kg"}
            dicts, any order -- this function doesn't assume sorting).
        idioma: "en" (default) or "es".
    """
    limite = date.today() - timedelta(days=_VENTANA_RESUMEN_MENSUAL_DIAS)

    def _en_ventana(fecha_str: str | None) -> bool:
        if not fecha_str:
            return False
        try:
            return date.fromisoformat(fecha_str) >= limite
        except ValueError:
            return False

    # "Adherence check-in" only -- same filter historial_checkins() callers
    # already apply elsewhere (the check-in form's "Semana N:" counter,
    # _fecha_checkin_esta_semana()) -- a "Plan sent" row isn't adherence data.
    valoraciones = [
        _VALORACION_A_NUMERO_RESUMEN[fila["valoracion"]]
        for fila in historial
        if fila["tipo"] == "Adherence check-in"
        and fila["valoracion"] in _VALORACION_A_NUMERO_RESUMEN
        and _en_ventana(fila["fecha"])
    ]
    con_peso = sorted(
        (
            (fila["fecha"], fila["peso_kg"])
            for fila in historial
            if fila.get("peso_kg") is not None and _en_ventana(fila["fecha"])
        ),
        key=lambda par: par[0],
    )

    if not valoraciones and len(con_peso) < 2:
        return None

    n_checkins = len(valoraciones)
    palabra_checkin = "check-in" if n_checkins == 1 else "check-ins"  # kept as a loanword in both languages,
    # same convention as "Adherence check-in"'s own untranslated type name elsewhere in this project.
    if n_checkins:
        etiqueta = _NUMERO_A_ETIQUETA_TENDENCIA[idioma][round(sum(valoraciones) / n_checkins)]
        primera_parte = (
            f"Últimos {_VENTANA_RESUMEN_MENSUAL_DIAS} días: {n_checkins} {palabra_checkin}, "
            f"adherencia con tendencia {etiqueta}."
            if idioma == "es" else
            f"Last {_VENTANA_RESUMEN_MENSUAL_DIAS} days: {n_checkins} {palabra_checkin}, adherence trending {etiqueta}."
        )
    else:
        primera_parte = (
            f"Últimos {_VENTANA_RESUMEN_MENSUAL_DIAS} días:" if idioma == "es"
            else f"Last {_VENTANA_RESUMEN_MENSUAL_DIAS} days:"
        )
    partes = [primera_parte]

    if len(con_peso) >= 2:
        primer_peso, ultimo_peso = con_peso[0][1], con_peso[-1][1]
        etiqueta_peso = "Peso" if idioma == "es" else "Weight"
        partes.append(f"{etiqueta_peso}: {primer_peso}kg → {ultimo_peso}kg ({ultimo_peso - primer_peso:+.1f}kg).")

    return " ".join(partes)


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
