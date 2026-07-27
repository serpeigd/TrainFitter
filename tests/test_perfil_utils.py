"""Tests for perfil_utils.tags_lesiones — safety-critical bilingual keyword
matching (a translation pass once silently broke this; see docs/decisiones.md)."""

from perfil_utils import tags_lesiones


def _con_lesion(perfil_base, zona: str, descripcion: str = "") -> dict:
    perfil_base["salud"]["lesiones"] = [
        {"zona": zona, "descripcion": descripcion, "estado": "antigua_controlada", "activa_actualmente": False}
    ]
    return perfil_base


def test_detects_knee_in_spanish(perfil_base):
    assert tags_lesiones(_con_lesion(perfil_base, "rodilla")) == {"rodilla"}


def test_detects_knee_in_english(perfil_base):
    assert tags_lesiones(_con_lesion(perfil_base, "left knee")) == {"rodilla"}


def test_detects_shoulder_in_spanish(perfil_base):
    assert tags_lesiones(_con_lesion(perfil_base, "hombro")) == {"hombro"}


def test_detects_shoulder_in_english(perfil_base):
    assert tags_lesiones(_con_lesion(perfil_base, "shoulder")) == {"hombro"}


def test_detects_lower_back_variants(perfil_base):
    for texto in ("lumbar", "espalda baja", "low back", "lower back"):
        perfil = _con_lesion(perfil_base, texto)
        assert tags_lesiones(perfil) == {"lumbar"}, f"failed for {texto!r}"


def test_detects_from_free_text_description_not_just_zone(perfil_base):
    perfil = _con_lesion(perfil_base, "unspecified area", "chronic knee pain when squatting")
    assert "rodilla" in tags_lesiones(perfil)


def test_no_false_positive_on_clean_profile(perfil_base):
    assert tags_lesiones(perfil_base) == set()


def test_multiple_injuries_combine_tags(perfil_base):
    perfil_base["salud"]["lesiones"] = [
        {"zona": "knee", "descripcion": "", "estado": "antigua_controlada", "activa_actualmente": False},
        {"zona": "shoulder", "descripcion": "", "estado": "activa", "activa_actualmente": True},
    ]
    assert tags_lesiones(perfil_base) == {"rodilla", "hombro"}
