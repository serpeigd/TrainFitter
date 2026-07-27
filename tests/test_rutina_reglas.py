"""Tests for the routine rule engine (agents/rutina_reglas.py)."""

from exercise_bank import EXERCISE_BANK
from rutina_reglas import generar_borrador_rutina_reglas

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
