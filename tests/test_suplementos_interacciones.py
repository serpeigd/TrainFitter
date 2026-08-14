"""Tests for agents/suplementos_interacciones.py -- pure function, no I/O."""

from suplementos_interacciones import pares_interaccion_declarados


def _perfil(suplementos=None, medicacion=None):
    return {"salud": {"suplementos_actuales": suplementos or [], "medicacion_habitual": medicacion or []}}


def test_no_message_without_both_fields():
    assert pares_interaccion_declarados(_perfil(suplementos=["Iron"])) == []
    assert pares_interaccion_declarados(_perfil(medicacion=["Warfarin"])) == []
    assert pares_interaccion_declarados(_perfil()) == []


def test_no_message_for_an_unrecognized_pair():
    """Supplement + medication both declared, but neither matches a known
    category -- validator_agent.py's own generic check is the fallback
    here, this function has nothing more specific to add."""
    assert pares_interaccion_declarados(_perfil(["Creatine"], ["Ibuprofen"])) == []


def test_vitamin_k_anticoagulant_pair():
    mensajes = pares_interaccion_declarados(_perfil(["Vitamin K"], ["Warfarin"]))
    assert len(mensajes) == 1
    assert "vitamin K" in mensajes[0]
    assert "anticoagulant" in mensajes[0]


def test_iron_matches_multiple_medication_categories_in_one_message():
    mensajes = pares_interaccion_declarados(_perfil(["Iron"], ["Levothyroxine", "Doxycycline"]))
    assert len(mensajes) == 1
    assert "levothyroxine" in mensajes[0]
    assert "tetracyclines" in mensajes[0]


def test_magnesium_potassium_sparing_diuretic_pair():
    mensajes = pares_interaccion_declarados(_perfil(["Magnesium"], ["Spironolactone"]))
    assert len(mensajes) == 1
    assert "potassium-sparing diuretics" in mensajes[0]


def test_high_dose_omega3_anticoagulant_bleeding_risk():
    mensajes = pares_interaccion_declarados(_perfil(["Fish oil"], ["Aspirin"]))
    assert len(mensajes) == 1
    assert "bleeding" in mensajes[0].lower()


def test_vitamin_d_thiazide_and_digoxin():
    mensajes = pares_interaccion_declarados(_perfil(["Vitamin D"], ["Hydrochlorothiazide", "Digoxin"]))
    assert len(mensajes) == 1
    assert "thiazide" in mensajes[0]
    assert "digoxin" in mensajes[0]


def test_ashwagandha_matches_three_medication_categories():
    mensajes = pares_interaccion_declarados(
        _perfil(["Ashwagandha"], ["Lorazepam", "Levothyroxine", "Cyclosporine"]),
    )
    assert len(mensajes) == 1
    assert "sedatives/benzodiazepines" in mensajes[0]
    assert "levothyroxine" in mensajes[0]
    assert "immunosuppressants" in mensajes[0]


def test_st_johns_wort_ssri():
    mensajes = pares_interaccion_declarados(_perfil(["St. John's Wort"], ["Sertraline"]))
    assert len(mensajes) == 1
    assert "SSRI" in mensajes[0]
    assert "serotonin syndrome" in mensajes[0]


def test_multiple_supplements_produce_multiple_messages():
    """Both Vitamin K and fish oil have a documented interaction with
    anticoagulants -- unlike iron, which doesn't (see the "unrecognized
    pair" tests above for that distinction)."""
    mensajes = pares_interaccion_declarados(_perfil(["Vitamin K", "Fish oil"], ["Warfarin"]))
    assert len(mensajes) == 2


def test_a_supplement_match_with_no_overlapping_medication_category_is_silent():
    """Iron's keyword matches, and Warfarin's category (anticoagulantes)
    is a recognized medication -- but iron has no documented interaction
    with anticoagulants specifically (only with tetracyclines/quinolones/
    levothyroxine/bisphosphonates), so it must not produce a message just
    because *some* recognized medication category was declared."""
    mensajes = pares_interaccion_declarados(_perfil(["Iron"], ["Warfarin"]))
    assert mensajes == []


def test_creatine_and_protein_powder_have_no_specific_pair():
    """The two most common supplements this project actually recommends
    (see dieta_reglas._SUPLEMENTOS_TRYHARD_TEXTOS) have no known
    clinically relevant medication interaction at normal doses -- absent
    from the curated list on purpose, not an oversight."""
    assert pares_interaccion_declarados(_perfil(["Creatine"], ["Warfarin"])) == []
    assert pares_interaccion_declarados(_perfil(["Whey protein"], ["Warfarin"])) == []


def test_matching_is_accent_and_case_insensitive():
    mensajes_con_acento = pares_interaccion_declarados(_perfil(["cúrcuma"], ["ASPIRINA"]))
    mensajes_sin_acento = pares_interaccion_declarados(_perfil(["curcuma"], ["aspirina"]))
    assert len(mensajes_con_acento) == 1
    assert mensajes_con_acento == mensajes_sin_acento


def test_spanish_language_message():
    mensajes = pares_interaccion_declarados(_perfil(["Hierro"], ["Levotiroxina"]), idioma="es")
    assert len(mensajes) == 1
    assert "Interacción conocida" in mensajes[0]
    assert "hierro" in mensajes[0]
