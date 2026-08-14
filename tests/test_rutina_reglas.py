"""Tests for the routine rule engine (agents/rutina_reglas.py)."""

from exercise_bank import EXERCISE_BANK
from rutina_reglas import MENSAJE_CLIENTE_RUTINA_VARIANTES, PROGRESION_VARIANTES, generar_borrador_rutina_reglas

INDICE_EJERCICIOS = {e["nombre"]: e for e in EXERCISE_BANK}


def test_split_selection_by_days_per_week(perfil_base):
    casos = {
        2: "full_body",
        3: "full_body",
        4: "upper_lower",
        5: "push_pull_legs",
        6: "push_pull_legs",
    }
    for dias, split_esperado in casos.items():
        perfil_base["disponibilidad"]["dias_por_semana"] = dias
        borrador = generar_borrador_rutina_reglas(perfil_base)
        assert borrador["split"] == split_esperado
        assert len(borrador["sesiones"]) == dias


def test_four_days_alternates_upper_lower(perfil_base):
    perfil_base["disponibilidad"]["dias_por_semana"] = 4
    borrador = generar_borrador_rutina_reglas(perfil_base)
    dias = [sesion["dia"] for sesion in borrador["sesiones"]]
    assert "Upper A" in dias[0]
    assert "Lower A" in dias[1]
    assert "Upper B" in dias[2]
    assert "Lower B" in dias[3]


def test_bodyweight_only_when_no_equipment(perfil_base):
    perfil_base["disponibilidad"]["material_disponible"] = []
    borrador = generar_borrador_rutina_reglas(perfil_base)
    for sesion in borrador["sesiones"]:
        for ejercicio in sesion["ejercicios"]:
            info = INDICE_EJERCICIOS[ejercicio["nombre"]]
            assert info["material"] <= {"peso_corporal"}


def test_knee_injury_excludes_contraindicated_exercises(perfil_base):
    perfil_base["salud"]["lesiones"] = [
        {"zona": "left knee", "descripcion": "old ACL injury", "estado": "antigua_controlada", "activa_actualmente": False}
    ]
    borrador = generar_borrador_rutina_reglas(perfil_base)
    for sesion in borrador["sesiones"]:
        for ejercicio in sesion["ejercicios"]:
            info = INDICE_EJERCICIOS[ejercicio["nombre"]]
            assert "rodilla" not in info["contraindicaciones"]


def test_knee_injury_adds_cautionary_note_on_leg_exercises(perfil_base):
    perfil_base["salud"]["lesiones"] = [
        {"zona": "knee", "descripcion": "sensitive knee", "estado": "antigua_controlada", "activa_actualmente": False}
    ]
    borrador = generar_borrador_rutina_reglas(perfil_base)
    notas = [
        ejercicio["notas"]
        for sesion in borrador["sesiones"]
        for ejercicio in sesion["ejercicios"]
        if INDICE_EJERCICIOS[ejercicio["nombre"]]["grupo"] in {"pierna_cuadriceps", "pierna_isquios_gluteo", "gemelos"}
    ]
    assert any("knee" in nota for nota in notas)


def test_injury_generates_human_review_warning(perfil_base):
    perfil_base["salud"]["lesiones"] = [
        {"zona": "shoulder", "descripcion": "rotator cuff strain", "estado": "activa", "activa_actualmente": True}
    ]
    borrador = generar_borrador_rutina_reglas(perfil_base)
    assert len(borrador["advertencias_revision_humana"]) == 1
    assert "shoulder" in borrador["advertencias_revision_humana"][0].lower()


def test_clean_profile_has_no_warnings(perfil_base):
    borrador = generar_borrador_rutina_reglas(perfil_base)
    assert borrador["advertencias_revision_humana"] == []


def test_summary_uses_english_display_labels(perfil_base):
    perfil_base["experiencia"]["nivel"] = "principiante"
    perfil_base["objetivo"]["principal"] = "perdida_grasa"
    borrador = generar_borrador_rutina_reglas(perfil_base)
    assert "beginner" in borrador["resumen_enfoque"]
    assert "fat loss" in borrador["resumen_enfoque"]
    assert "principiante" not in borrador["resumen_enfoque"]


def test_idioma_es_translates_narrative_text_only(perfil_base):
    """idioma="es" must translate the narrative text (resumen, day label,
    warmup, progression, client message) but NEVER the exercise "nombre"
    field -- the validator's safety cross-check (test_validator_agent.py)
    depends on that field staying the canonical English value regardless of
    UI language (see exercise_bank.py's module docstring)."""
    perfil_base["experiencia"]["nivel"] = "principiante"
    perfil_base["objetivo"]["principal"] = "perdida_grasa"
    borrador = generar_borrador_rutina_reglas(perfil_base, idioma="es")

    assert "pérdida de grasa" in borrador["resumen_enfoque"]
    assert "principiante" in borrador["resumen_enfoque"]
    assert "beginner" not in borrador["resumen_enfoque"]
    assert borrador["sesiones"][0]["dia"].startswith("Día ")
    assert borrador["mensaje_para_el_cliente"].startswith("Hola ")
    # progresion is picked from a pool of equivalent Spanish phrasings (see
    # variacion.py) -- check membership in that pool, not one exact legacy
    # string, so this test doesn't depend on which variant got picked.
    assert borrador["progresion"] in PROGRESION_VARIANTES["es"]

    for sesion in borrador["sesiones"]:
        for ejercicio in sesion["ejercicios"]:
            assert ejercicio["nombre"] in INDICE_EJERCICIOS  # still the canonical English key


def test_default_idioma_matches_explicit_english(perfil_base):
    """The default (no idioma passed) must produce byte-identical output to
    idioma="en" explicitly -- existing callers (CLI demos, motor="llm"
    comparisons) must see no behavior change from adding this parameter."""
    borrador_default = generar_borrador_rutina_reglas(perfil_base)
    borrador_en = generar_borrador_rutina_reglas(perfil_base, idioma="en")
    assert borrador_default == borrador_en


def test_regenerating_the_same_client_is_stable(perfil_base):
    """Same id_cliente -> same exercise picks and same narrative phrasing
    every time (seeded by id_cliente, see variacion.py) -- regenerating a
    client's plan should never surprise the trainer with a different draft."""
    borrador_1 = generar_borrador_rutina_reglas(perfil_base)
    borrador_2 = generar_borrador_rutina_reglas(perfil_base)
    assert borrador_1 == borrador_2


def test_different_clients_get_varied_narrative_text(perfil_base):
    """Clients with an otherwise-identical profile shouldn't all read
    byte-identical boilerplate -- the whole point of seeding by id_cliente
    (see docs/decisiones.md). Only 4 variants exist, so two individual IDs
    can coincidentally land on the same one (1-in-4 chance) -- sample
    enough distinct IDs that the pool's actual size shows up, instead of
    asserting inequality between two arbitrary picks."""
    progresiones = set()
    for i in range(15):
        perfil_base["id_cliente"] = f"cliente_variedad_{i}"
        borrador = generar_borrador_rutina_reglas(perfil_base)
        assert borrador["progresion"] in PROGRESION_VARIANTES["en"]
        progresiones.add(borrador["progresion"])
    assert len(progresiones) > 1


def test_client_message_greeting_stays_fixed_around_the_varied_body(perfil_base):
    """The "Hi {name}, " greeting is prepended outside the variant pool
    (see rutina_reglas.py) -- every variant must still produce a message
    starting with it, regardless of which body text got picked."""
    for id_cliente in ("cliente_a", "cliente_b", "cliente_c", "cliente_d", "cliente_e"):
        perfil_base["id_cliente"] = id_cliente
        borrador = generar_borrador_rutina_reglas(perfil_base)
        assert borrador["mensaje_para_el_cliente"].startswith("Hi Test, ")
        cuerpo = borrador["mensaje_para_el_cliente"].removeprefix("Hi Test, ")
        assert cuerpo in MENSAJE_CLIENTE_RUTINA_VARIANTES["en"]


def test_different_clients_can_get_different_exercises(perfil_base):
    """Exercise selection is shuffled per client too (see
    rng_para_cliente() usage in rutina_reglas.py) -- sample enough distinct
    client IDs that at least one pair disagrees on the first day's first
    exercise, ruling out a shuffle that's accidentally a no-op."""
    primeros_ejercicios = set()
    for i in range(15):
        perfil_base["id_cliente"] = f"cliente_variedad_{i}"
        borrador = generar_borrador_rutina_reglas(perfil_base)
        primeros_ejercicios.add(borrador["sesiones"][0]["ejercicios"][0]["nombre"])
    assert len(primeros_ejercicios) > 1


# --- Level-based volume/complexity (maximal personalization) --------------


def test_beginner_gets_fewer_sets_on_basic_exercises_than_intermediate(perfil_base):
    perfil_base["experiencia"]["nivel"] = "principiante"
    principiante = generar_borrador_rutina_reglas(perfil_base)

    perfil_base["experiencia"]["nivel"] = "intermedio"
    intermedio = generar_borrador_rutina_reglas(perfil_base)

    series_principiante = [e["series"] for s in principiante["sesiones"] for e in s["ejercicios"]]
    series_intermedio = [e["series"] for s in intermedio["sesiones"] for e in s["ejercicios"]]
    assert sum(series_principiante) < sum(series_intermedio)


def test_advanced_gets_more_sets_than_intermediate(perfil_base):
    perfil_base["experiencia"]["nivel"] = "avanzado"
    avanzado = generar_borrador_rutina_reglas(perfil_base)

    perfil_base["experiencia"]["nivel"] = "intermedio"
    intermedio = generar_borrador_rutina_reglas(perfil_base)

    series_avanzado = [e["series"] for s in avanzado["sesiones"] for e in s["ejercicios"]]
    series_intermedio = [e["series"] for s in intermedio["sesiones"] for e in s["ejercicios"]]
    assert sum(series_avanzado) > sum(series_intermedio)


def test_series_never_drop_below_the_floor(perfil_base):
    """A beginner (-1 basic) with high stress/low sleep (-1 more) stacks to
    -2 on basic exercises -- must still clamp at SERIES_MINIMAS, never go
    to 1 or 0 sets."""
    perfil_base["experiencia"]["nivel"] = "principiante"
    perfil_base["estilo_de_vida"]["nivel_estres_percibido"] = "alto"
    borrador = generar_borrador_rutina_reglas(perfil_base)
    for sesion in borrador["sesiones"]:
        for ejercicio in sesion["ejercicios"]:
            assert ejercicio["series"] >= 2


def test_beginner_is_biased_toward_lower_complexity_exercises(perfil_base):
    """Machine/bodyweight/dumbbell exercises should show up more often than
    barbell compound lifts for a beginner when both are valid candidates
    for the same slot -- sampled across many client IDs since it's a bias,
    not an absolute exclusion (see rutina_reglas.py's
    _preferir_baja_complejidad_primero())."""
    barbell_exercises = {e["nombre"] for e in EXERCISE_BANK if "barras_y_discos" in e["material"]}

    conteo_principiante = 0
    conteo_avanzado = 0
    total = 0
    for i in range(20):
        perfil_base["id_cliente"] = f"complejidad_test_{i}"
        perfil_base["experiencia"]["nivel"] = "principiante"
        principiante = generar_borrador_rutina_reglas(perfil_base)
        perfil_base["experiencia"]["nivel"] = "avanzado"
        avanzado = generar_borrador_rutina_reglas(perfil_base)

        for sesion in principiante["sesiones"]:
            for ejercicio in sesion["ejercicios"]:
                total += 1
                if ejercicio["nombre"] in barbell_exercises:
                    conteo_principiante += 1
        for sesion in avanzado["sesiones"]:
            for ejercicio in sesion["ejercicios"]:
                if ejercicio["nombre"] in barbell_exercises:
                    conteo_avanzado += 1

    assert conteo_principiante < conteo_avanzado


def test_short_session_trims_the_last_exercises(perfil_base):
    perfil_base["disponibilidad"]["minutos_por_sesion"] = 25
    corto = generar_borrador_rutina_reglas(perfil_base)

    perfil_base["disponibilidad"]["minutos_por_sesion"] = 60
    normal = generar_borrador_rutina_reglas(perfil_base)

    for s_corto, s_normal in zip(corto["sesiones"], normal["sesiones"]):
        assert len(s_corto["ejercicios"]) < len(s_normal["ejercicios"])
        assert len(s_corto["ejercicios"]) >= 2


def test_short_session_note_appears_in_summary(perfil_base):
    perfil_base["disponibilidad"]["minutos_por_sesion"] = 20
    borrador = generar_borrador_rutina_reglas(perfil_base)
    assert "25-minute" not in borrador["resumen_enfoque"]  # sanity: not hardcoded
    assert "20-minute" in borrador["resumen_enfoque"]


def test_high_stress_or_low_sleep_note_appears_in_summary(perfil_base):
    perfil_base["estilo_de_vida"]["horas_sueno_promedio"] = 5
    borrador = generar_borrador_rutina_reglas(perfil_base)
    assert "conservative" in borrador["resumen_enfoque"].lower()


def test_normal_stress_and_sleep_has_no_conservative_note(perfil_base):
    borrador = generar_borrador_rutina_reglas(perfil_base)
    assert "conservative" not in borrador["resumen_enfoque"].lower()


def test_tryhard_adds_a_set_and_basico_removes_one(perfil_base):
    perfil_base["experiencia"]["nivel_compromiso"] = "basico"
    basico = generar_borrador_rutina_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    normal = generar_borrador_rutina_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_rutina_reglas(perfil_base)

    series_basico = basico["sesiones"][0]["ejercicios"][0]["series"]
    series_normal = normal["sesiones"][0]["ejercicios"][0]["series"]
    series_tryhard = tryhard["sesiones"][0]["ejercicios"][0]["series"]
    assert series_basico == series_normal - 1
    assert series_tryhard == series_normal + 1


def test_series_never_drop_below_the_floor_even_stacked_with_basico(perfil_base):
    """basico (-1) stacked with a beginner's own -1 and the stress/sleep -1
    could reach zero or negative without the shared floor."""
    perfil_base["experiencia"]["nivel"] = "principiante"
    perfil_base["experiencia"]["nivel_compromiso"] = "basico"
    perfil_base["estilo_de_vida"]["horas_sueno_promedio"] = 5
    borrador = generar_borrador_rutina_reglas(perfil_base)
    for sesion in borrador["sesiones"]:
        for ejercicio in sesion["ejercicios"]:
            assert ejercicio["series"] >= 2


def test_niche_exercises_only_appear_in_tryhard_mode(perfil_base):
    nicho = {e["nombre"] for e in EXERCISE_BANK if e.get("nicho")}
    perfil_base["disponibilidad"]["material_disponible"] = [
        "maquinas_guiadas", "poleas", "barras_y_discos", "mancuernas", "bancos", "bicicleta_estatica",
    ]

    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    normal = generar_borrador_rutina_reglas(perfil_base)
    usados_normal = {e["nombre"] for s in normal["sesiones"] for e in s["ejercicios"]}
    assert not (usados_normal & nicho)

    encontrado = False
    for i in range(15):
        perfil_base["id_cliente"] = f"nicho_test_{i}"
        perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
        tryhard = generar_borrador_rutina_reglas(perfil_base)
        usados_tryhard = {e["nombre"] for s in tryhard["sesiones"] for e in s["ejercicios"]}
        if usados_tryhard & nicho:
            encontrado = True
            break
    assert encontrado


def test_niche_exercises_do_not_appear_in_avanzado_mode(perfil_base):
    """"avanzado" is deliberately NOT "tryhard" -- niche exercises stay
    exclusive to tryhard, the literal ceiling of detail this project
    offers (see docs/decisiones.md)."""
    nicho = {e["nombre"] for e in EXERCISE_BANK if e.get("nicho")}
    perfil_base["disponibilidad"]["material_disponible"] = [
        "maquinas_guiadas", "poleas", "barras_y_discos", "mancuernas", "bancos", "bicicleta_estatica",
    ]
    for i in range(15):
        perfil_base["id_cliente"] = f"nicho_avanzado_test_{i}"
        perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
        avanzado = generar_borrador_rutina_reglas(perfil_base)
        usados = {e["nombre"] for s in avanzado["sesiones"] for e in s["ejercicios"]}
        assert not (usados & nicho)


def test_avanzado_series_match_normal(perfil_base):
    """"avanzado"'s extra detail is dietary (supplement guidance), not
    training volume -- detail and physical intensity are different axes
    (see docs/decisiones.md)."""
    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    normal = generar_borrador_rutina_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    avanzado = generar_borrador_rutina_reglas(perfil_base)
    assert avanzado["sesiones"][0]["ejercicios"][0]["series"] == normal["sesiones"][0]["ejercicios"][0]["series"]


def test_commitment_mode_note_appears_in_summary(perfil_base):
    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_rutina_reglas(perfil_base)
    assert "tryhard" in tryhard["resumen_enfoque"].lower()

    perfil_base["experiencia"]["nivel_compromiso"] = "basico"
    basico = generar_borrador_rutina_reglas(perfil_base)
    assert "basic" in basico["resumen_enfoque"].lower()

    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    avanzado = generar_borrador_rutina_reglas(perfil_base)
    assert "advanced" in avanzado["resumen_enfoque"].lower()

    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    normal = generar_borrador_rutina_reglas(perfil_base)
    assert "tryhard" not in normal["resumen_enfoque"].lower()
    assert "basic" not in normal["resumen_enfoque"].lower()


def test_missing_nivel_compromiso_defaults_to_normal_behavior(perfil_base):
    """A profile without the field at all (e.g. an older saved client) must
    behave exactly like nivel_compromiso="normal", not crash or change
    numbers."""
    assert "nivel_compromiso" not in perfil_base["experiencia"]
    sin_campo = generar_borrador_rutina_reglas(perfil_base)
    perfil_base["experiencia"]["nivel_compromiso"] = "normal"
    con_normal = generar_borrador_rutina_reglas(perfil_base)
    assert sin_campo["sesiones"][0]["ejercicios"][0]["series"] == con_normal["sesiones"][0]["ejercicios"][0]["series"]


def test_commitment_mode_note_appears_in_summary_es(perfil_base):
    perfil_base["experiencia"]["nivel_compromiso"] = "tryhard"
    tryhard = generar_borrador_rutina_reglas(perfil_base, idioma="es")
    assert "tryhard" in tryhard["resumen_enfoque"].lower()

    perfil_base["experiencia"]["nivel_compromiso"] = "basico"
    basico = generar_borrador_rutina_reglas(perfil_base, idioma="es")
    assert "básico" in basico["resumen_enfoque"].lower()

    perfil_base["experiencia"]["nivel_compromiso"] = "avanzado"
    avanzado = generar_borrador_rutina_reglas(perfil_base, idioma="es")
    assert "avanzado" in avanzado["resumen_enfoque"].lower()


def test_every_session_gets_an_effort_note(perfil_base):
    borrador = generar_borrador_rutina_reglas(perfil_base)
    for sesion in borrador["sesiones"]:
        assert sesion["nota_esfuerzo"]
        assert "RIR" in sesion["nota_esfuerzo"] or "reps in reserve" in sesion["nota_esfuerzo"].lower()


def test_effort_note_is_translated_for_spanish(perfil_base):
    borrador = generar_borrador_rutina_reglas(perfil_base, idioma="es")
    for sesion in borrador["sesiones"]:
        assert "margen" in sesion["nota_esfuerzo"].lower()


# --- Liked exercises (ejercicios_favoritos) -- portal "repeat this exercise" ---


def test_exercise_dict_includes_group_and_type_fields(perfil_base):
    """Alongside "nombre", each exercise now also carries its own slot's
    "grupo"/"tipo" -- what lets a client "like" a specific exercise from
    the portal and have it match back to the right slot later, without
    this project re-deriving it from exercise_bank.py at like-time (see
    docs/decisiones.md)."""
    borrador = generar_borrador_rutina_reglas(perfil_base)
    ejercicio = borrador["sesiones"][0]["ejercicios"][0]
    info = INDICE_EJERCICIOS[ejercicio["nombre"]]
    assert ejercicio["grupo"] == info["grupo"]
    assert ejercicio["tipo"] == info["tipo"]


def test_liked_exercise_reappears_more_often_than_baseline(perfil_base):
    """Statistical check, not a single-example read (same discipline as
    planificador_comidas.py's own liked-meal test): a liked exercise
    should show up in its slot noticeably more than the baseline rotation
    chance among that slot's candidates."""
    baseline = generar_borrador_rutina_reglas(perfil_base)
    primer_ejercicio = baseline["sesiones"][0]["ejercicios"][0]
    grupo_objetivo = primer_ejercicio["grupo"]
    tipo_objetivo = primer_ejercicio["tipo"]
    nombre_objetivo = primer_ejercicio["nombre"]

    perfil_base["experiencia"]["ejercicios_favoritos"] = [
        {"grupo": grupo_objetivo, "tipo": tipo_objetivo, "nombre": nombre_objetivo},
    ]
    apariciones = 0
    total = 0
    for i in range(20):
        perfil_base["id_cliente"] = f"favoritos_ejercicio_test_{i}"
        borrador = generar_borrador_rutina_reglas(perfil_base)
        for sesion in borrador["sesiones"]:
            for ejercicio in sesion["ejercicios"]:
                if ejercicio["grupo"] == grupo_objetivo and ejercicio["tipo"] == tipo_objetivo:
                    total += 1
                    if ejercicio["nombre"] == nombre_objetivo:
                        apariciones += 1
    assert apariciones / total > 0.35  # well above what an unbiased rotation across many candidates would give


def test_no_favorite_exercises_behaves_exactly_like_before(perfil_base):
    """A profile without ejercicios_favoritos at all (every existing
    client) must produce byte-identical routines to before this feature
    existed."""
    assert "ejercicios_favoritos" not in perfil_base["experiencia"]
    sin_favoritos = generar_borrador_rutina_reglas(perfil_base)
    perfil_base["experiencia"]["ejercicios_favoritos"] = []
    con_lista_vacia = generar_borrador_rutina_reglas(perfil_base)
    assert sin_favoritos == con_lista_vacia


def test_liked_exercise_dropped_if_no_longer_a_valid_candidate(perfil_base):
    """A safety-adjacent guarantee: if the liked exercise's equipment is no
    longer available (or a new injury contraindicates it), it must never
    be resurrected just because it's on the favorites list --
    ejercicios_favoritos is matched against the already-filtered candidate
    pool, not the raw exercise bank."""
    perfil_base["experiencia"]["ejercicios_favoritos"] = [
        {"grupo": "pecho", "tipo": "basico", "nombre": "Barbell Bench Press"},
    ]
    perfil_base["disponibilidad"]["material_disponible"] = []  # bodyweight-only: no barbell lift is a candidate
    borrador = generar_borrador_rutina_reglas(perfil_base)
    nombres = {ej["nombre"] for sesion in borrador["sesiones"] for ej in sesion["ejercicios"]}
    assert "Barbell Bench Press" not in nombres
