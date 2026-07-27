"""Shared fixtures for the test suite.

`perfil_base` returns a minimal-but-complete client profile matching the
schema in examples/cliente_ejemplo_*.json, with no injuries/allergies/
conditions — a "clean" baseline. Individual tests deep-copy it and mutate
only the fields relevant to what they're checking.
"""

import copy

import pytest


def _perfil_base() -> dict:
    return {
        "id_cliente": "test_cliente",
        "fecha_admision": "2026-01-01",
        "datos_basicos": {"nombre": "Test Person", "edad": 30, "sexo": "hombre", "peso_kg": 80, "altura_cm": 180},
        "objetivo": {"principal": "hipertrofia", "en_sus_palabras": ""},
        "experiencia": {"nivel": "intermedio", "anios_entrenando": 2, "detalle": ""},
        "disponibilidad": {
            "dias_por_semana": 4,
            "minutos_por_sesion": 60,
            "lugar_entreno": "gimnasio_completo",
            "material_disponible": ["maquinas_guiadas", "poleas", "barras_y_discos", "mancuernas", "bancos"],
        },
        "salud": {
            "lesiones": [],
            "enfermedades_o_condiciones": [],
            "embarazo_o_lactancia": {"aplica": False, "detalle": ""},
            "medicacion_habitual": [],
            "alergias_alimentarias": [],
            "intolerancias_alimentarias": [],
            "analitica_adjunta": {"tiene": False, "archivo": None, "fecha": None, "notas": ""},
        },
        "nutricion": {
            "tipo_dieta": "omnivora",
            "restricciones": [],
            "alimentos_que_no_le_gustan": [],
            "comidas_al_dia_preferidas": 4,
            "contexto": "",
        },
        "estilo_de_vida": {
            "horas_sueno_promedio": 7,
            "nivel_estres_percibido": "medio",
            "tipo_trabajo": "sedentary office job",
            "pasos_diarios_aprox": 6000,
        },
        "notas_libres": "",
    }


@pytest.fixture
def perfil_base() -> dict:
    return copy.deepcopy(_perfil_base())
