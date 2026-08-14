"""
Known supplement-medication interaction pairs -- refines
validator_agent.py's coarse "supplements + medication together -> flag"
check into a specific, named pair (mechanism + what to do) when one is
recognized. See docs/base_conocimiento/suplementacion.md's "Known
interaction pairs" table for the same data with citations.

DESIGN -- a curated list, not a drug-interaction database: this covers
the handful of well-documented, high-certainty pairs a trainer is
actually likely to run into with this project's own supported
supplements (docs/base_conocimiento/suplementacion.md), not an attempt
at exhaustive pharmacological coverage (see validator_agent.py's own
docstring for why this project deliberately doesn't try to be
complete there). Creatine, protein powder, beta-alanine, and collagen
are absent on purpose -- no clinically relevant medication interaction
at normal doses. This is purely ADDITIVE: validar_borradores() still
runs its own generic "supplements + medication together" check
regardless of whether a specific pair here matches, so an
unrecognized combination is never silently let through -- it just
doesn't get the more specific explanation this module adds.
"""

import unicodedata


def _sin_acentos(texto: str) -> str:
    """Strips diacritics so "curcuma"/"hiperico" still match "cúrcuma"/
    "hipérico" -- same technique as food_bank.py's own helper of the
    same name, duplicated here rather than imported to keep this module
    free of a cross-import into food_bank.py for one small function."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


# Medication/condition categories, matched against salud.medicacion_habitual
# free text (bilingual, accent-insensitive, same style as
# perfil_utils.tags_lesiones()).
_PALABRAS_CLAVE_MEDICACION = {
    "anticoagulantes": (
        "anticoagulante", "warfarina", "acenocumarol", "sintrom",
        "anticoagulant", "warfarin", "blood thinner",
    ),
    "antiagregantes": (
        "antiagregante", "aspirina", "clopidogrel",
        "antiplatelet", "aspirin", "clopidogrel",
    ),
    "tetraciclinas": ("tetraciclina", "doxiciclina", "tetracycline", "doxycycline"),
    "quinolonas": (
        "quinolona", "ciprofloxacino", "levofloxacino",
        "quinolone", "ciprofloxacin", "levofloxacin",
    ),
    "levotiroxina": (
        "levotiroxina", "eutirox", "hormona tiroidea",
        "levothyroxine", "synthroid", "thyroid hormone",
    ),
    "bifosfonatos": ("bifosfonato", "alendronato", "fosamax", "bisphosphonate", "alendronate"),
    "diureticos_ahorradores_potasio": (
        "espironolactona", "amilorida", "diuretico ahorrador de potasio",
        "spironolactone", "amiloride", "potassium-sparing diuretic",
    ),
    "tiazidas": ("tiazida", "hidroclorotiazida", "thiazide", "hydrochlorothiazide"),
    "digoxina": ("digoxina", "digoxin"),
    "sedantes_benzodiacepinas": (
        "benzodiacepina", "diazepam", "lorazepam", "alprazolam", "ansiolitico",
        "benzodiazepine", "sedative",
    ),
    "inmunosupresores": (
        "inmunosupresor", "ciclosporina", "tacrolimus",
        "immunosuppressant", "cyclosporine", "tacrolimus",
    ),
    "anticonceptivos_orales": (
        "anticonceptivo", "pastilla anticonceptiva",
        "oral contraceptive", "birth control",
    ),
    "isrs": (
        "isrs", "antidepresivo", "sertralina", "fluoxetina", "escitalopram",
        "ssri", "antidepressant", "sertraline", "fluoxetine", "escitalopram",
    ),
    "quimioterapia": ("quimioterapia", "quimio", "chemotherapy"),
}

_MEDICACION_DISPLAY = {
    "anticoagulantes": {"es": "anticoagulantes", "en": "anticoagulants"},
    "antiagregantes": {"es": "antiagregantes", "en": "antiplatelets"},
    "tetraciclinas": {"es": "tetraciclinas", "en": "tetracyclines"},
    "quinolonas": {"es": "quinolonas", "en": "quinolones"},
    "levotiroxina": {"es": "levotiroxina", "en": "levothyroxine"},
    "bifosfonatos": {"es": "bifosfonatos", "en": "bisphosphonates"},
    "diureticos_ahorradores_potasio": {
        "es": "diuréticos ahorradores de potasio", "en": "potassium-sparing diuretics",
    },
    "tiazidas": {"es": "diuréticos tiazídicos", "en": "thiazide diuretics"},
    "digoxina": {"es": "digoxina", "en": "digoxin"},
    "sedantes_benzodiacepinas": {"es": "sedantes/benzodiacepinas", "en": "sedatives/benzodiazepines"},
    "inmunosupresores": {"es": "inmunosupresores", "en": "immunosuppressants"},
    "anticonceptivos_orales": {"es": "anticonceptivos orales", "en": "oral contraceptives"},
    "isrs": {"es": "antidepresivos ISRS", "en": "SSRIs"},
    "quimioterapia": {"es": "quimioterapia", "en": "chemotherapy"},
}

# Supplement categories, matched against salud.suplementos_actuales free
# text. Each maps to which _PALABRAS_CLAVE_MEDICACION categories it has a
# documented interaction with, plus a short bilingual mechanism note (see
# docs/base_conocimiento/suplementacion.md for the citation behind each).
_INTERACCIONES = {
    "vitamina_k": {
        "palabras": ("vitamina k", "vitamin k"),
        "display": {"es": "vitamina K", "en": "vitamin K"},
        "medicaciones": ("anticoagulantes",),
        "es": (
            "es cofactor de los mismos factores de coagulación que este tipo de medicación "
            "bloquea -- un cambio brusco en la ingesta puede alterar su efecto de forma impredecible."
        ),
        "en": (
            "is a cofactor for the same clotting factors this medication blocks -- a sudden "
            "change in intake can swing its effect unpredictably."
        ),
    },
    "hierro": {
        "palabras": ("hierro", "iron"),
        "display": {"es": "hierro", "en": "iron"},
        "medicaciones": ("tetraciclinas", "quinolonas", "levotiroxina", "bifosfonatos"),
        "es": (
            "puede formar un complejo insoluble con este tipo de medicación en el tubo digestivo, "
            "reduciendo su absorción -- suele recomendarse separar las tomas varias horas."
        ),
        "en": (
            "can form an insoluble complex with this medication in the gut, reducing its "
            "absorption -- doses are usually recommended to be separated by several hours."
        ),
    },
    "calcio": {
        "palabras": ("calcio", "calcium"),
        "display": {"es": "calcio", "en": "calcium"},
        "medicaciones": ("tetraciclinas", "quinolonas", "levotiroxina", "bifosfonatos"),
        "es": (
            "puede formar un complejo insoluble con este tipo de medicación en el tubo digestivo, "
            "reduciendo su absorción -- suele recomendarse separar las tomas varias horas."
        ),
        "en": (
            "can form an insoluble complex with this medication in the gut, reducing its "
            "absorption -- doses are usually recommended to be separated by several hours."
        ),
    },
    "magnesio": {
        "palabras": ("magnesio", "magnesium"),
        "display": {"es": "magnesio", "en": "magnesium"},
        "medicaciones": ("tetraciclinas", "quinolonas", "levotiroxina", "bifosfonatos", "diureticos_ahorradores_potasio"),
        "es": (
            "puede formar un complejo insoluble con antibióticos/bifosfonatos/levotiroxina "
            "reduciendo su absorción, y puede acumularse en exceso junto con un diurético "
            "ahorrador de potasio si la función renal está comprometida."
        ),
        "en": (
            "can form an insoluble complex with antibiotics/bisphosphonates/levothyroxine "
            "reducing their absorption, and can build up to unsafe levels alongside a "
            "potassium-sparing diuretic if kidney function is impaired."
        ),
    },
    "omega3": {
        "palabras": ("omega 3", "omega-3", "omega3", "aceite de pescado", "fish oil"),
        "display": {"es": "omega-3 (dosis alta)", "en": "high-dose omega-3"},
        "medicaciones": ("anticoagulantes", "antiagregantes"),
        "es": (
            "en dosis altas tiene un leve efecto sobre la coagulación que puede sumarse al de "
            "este tipo de medicación, aumentando el riesgo de sangrado."
        ),
        "en": (
            "at high doses has a mild anti-clotting effect that can add to this medication's "
            "own, increasing bleeding risk."
        ),
    },
    "vitamina_e": {
        "palabras": ("vitamina e", "vitamin e"),
        "display": {"es": "vitamina E (dosis alta)", "en": "high-dose vitamin E"},
        "medicaciones": ("anticoagulantes", "antiagregantes"),
        "es": (
            "en dosis altas inhibe la agregación plaquetaria y puede sumarse al efecto de este "
            "tipo de medicación, aumentando el riesgo de sangrado."
        ),
        "en": (
            "at high doses inhibits platelet aggregation and can add to this medication's own "
            "effect, increasing bleeding risk."
        ),
    },
    "ashwagandha": {
        "palabras": ("ashwagandha",),
        "display": {"es": "ashwagandha", "en": "ashwagandha"},
        "medicaciones": ("sedantes_benzodiacepinas", "levotiroxina", "inmunosupresores"),
        "es": (
            "puede potenciar el efecto sedante de este tipo de medicación, elevar los niveles de "
            "hormona tiroidea, o contrarrestar un inmunosupresor por su efecto inmunoestimulante, "
            "según el caso."
        ),
        "en": (
            "can potentiate this medication's sedative effect, raise thyroid hormone levels, or "
            "work against an immunosuppressant's purpose (it has an immune-stimulating effect), "
            "depending on the case."
        ),
    },
    "curcuma": {
        "palabras": ("curcuma", "cúrcuma", "curcumina", "turmeric", "curcumin"),
        "display": {"es": "cúrcuma (dosis alta)", "en": "high-dose turmeric/curcumin"},
        "medicaciones": ("anticoagulantes", "antiagregantes", "quimioterapia"),
        "es": (
            "en dosis altas puede sumar un leve efecto anticoagulante, o interferir con algunos "
            "protocolos de quimioterapia."
        ),
        "en": (
            "at high doses can add a mild anticoagulant effect, or interfere with some "
            "chemotherapy protocols."
        ),
    },
    "vitamina_d": {
        "palabras": ("vitamina d", "vitamin d"),
        "display": {"es": "vitamina D (dosis alta)", "en": "high-dose vitamin D"},
        "medicaciones": ("tiazidas", "digoxina"),
        "es": (
            "en dosis altas puede elevar el calcio en sangre; combinada con un diurético "
            "tiazídico el riesgo de hipercalcemia sube, y la hipercalcemia a su vez aumenta el "
            "riesgo de arritmia en quien toma digoxina."
        ),
        "en": (
            "at high doses can raise blood calcium; combined with a thiazide diuretic the risk "
            "of hypercalcemia rises, and hypercalcemia in turn raises arrhythmia risk for "
            "someone on digoxin."
        ),
    },
    "zinc": {
        "palabras": ("zinc",),
        "display": {"es": "zinc (dosis alta)", "en": "high-dose zinc"},
        "medicaciones": ("quinolonas", "tetraciclinas"),
        "es": (
            "puede formar un complejo insoluble con este tipo de antibiótico en el tubo "
            "digestivo, reduciendo su absorción -- suele recomendarse separar las tomas varias horas."
        ),
        "en": (
            "can form an insoluble complex with this antibiotic in the gut, reducing its "
            "absorption -- doses are usually recommended to be separated by several hours."
        ),
    },
    "hierba_de_san_juan": {
        "palabras": ("hierba de san juan", "hiperico", "st john's wort", "st. john's wort", "st johns wort"),
        "display": {"es": "hierba de San Juan", "en": "St. John's Wort"},
        "medicaciones": ("isrs", "anticonceptivos_orales", "anticoagulantes", "inmunosupresores"),
        "es": (
            "induce una enzima hepática (CYP3A4) que acelera la eliminación de muchos fármacos, "
            "reduciendo su eficacia -- o, combinada con antidepresivos ISRS, puede producir un "
            "síndrome serotoninérgico."
        ),
        "en": (
            "induces a liver enzyme (CYP3A4) that speeds up how quickly many drugs are cleared, "
            "reducing their effectiveness -- or, combined with SSRIs, can trigger serotonin syndrome."
        ),
    },
    "quercetina": {
        "palabras": ("quercetina", "quercetin"),
        "display": {"es": "quercetina", "en": "quercetin"},
        "medicaciones": ("quinolonas", "quimioterapia"),
        "es": (
            "puede interferir con la absorción de este tipo de antibiótico, o con el metabolismo "
            "de algunos fármacos de quimioterapia."
        ),
        "en": (
            "can interfere with this antibiotic's absorption, or with how some chemotherapy "
            "drugs are metabolized."
        ),
    },
}


def _coincide(texto_normalizado: str, palabras: tuple) -> bool:
    return any(_sin_acentos(palabra) in texto_normalizado for palabra in palabras)


def pares_interaccion_declarados(perfil: dict, idioma: str = "en") -> list[str]:
    """Cross-checks salud.suplementos_actuales against salud.medicacion_habitual
    for a recognized, specific interaction pair. Returns one message per
    matched supplement (naming every matched medication category together),
    possibly none even when both fields are non-empty -- validator_agent.py's
    own coarser "supplements + medication together" check still runs
    regardless and is the fallback for an unrecognized combination, not
    replaced by this."""
    salud = perfil.get("salud", {})
    suplementos = " ".join(salud.get("suplementos_actuales", [])).lower()
    medicacion = " ".join(salud.get("medicacion_habitual", [])).lower()
    if not suplementos or not medicacion:
        return []

    suplementos_norm = _sin_acentos(suplementos)
    medicacion_norm = _sin_acentos(medicacion)

    medicaciones_declaradas = {
        clave for clave, palabras in _PALABRAS_CLAVE_MEDICACION.items() if _coincide(medicacion_norm, palabras)
    }
    if not medicaciones_declaradas:
        return []

    mensajes = []
    for datos in _INTERACCIONES.values():
        if not _coincide(suplementos_norm, datos["palabras"]):
            continue
        coincidencias = medicaciones_declaradas & set(datos["medicaciones"])
        if not coincidencias:
            continue
        nombre_medicaciones = ", ".join(
            _MEDICACION_DISPLAY[clave][idioma] for clave in sorted(coincidencias)
        )
        if idioma == "es":
            mensajes.append(
                f"Interacción conocida: {datos['display']['es']} + {nombre_medicaciones} -- "
                f"{datos['es']} Revisar antes de recomendar nada más."
            )
        else:
            mensajes.append(
                f"Known interaction: {datos['display']['en']} + {nombre_medicaciones} -- "
                f"{datos['en']} Review before recommending anything further."
            )
    return mensajes
