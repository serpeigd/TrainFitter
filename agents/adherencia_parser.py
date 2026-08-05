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
