"""Tests for agents/variacion.py -- the seeded-RNG helper shared by
rutina_reglas.py and dieta_reglas.py."""

from variacion import elegir_variante, rng_para_cliente


def test_same_client_and_namespace_produce_the_same_rng_sequence():
    perfil = {"id_cliente": "cliente_001"}
    rng_1 = rng_para_cliente(perfil, "rutina:texto")
    rng_2 = rng_para_cliente(perfil, "rutina:texto")
    assert [rng_1.random() for _ in range(5)] == [rng_2.random() for _ in range(5)]


def test_different_clients_produce_different_rng_sequences():
    rng_a = rng_para_cliente({"id_cliente": "cliente_001"}, "rutina:texto")
    rng_b = rng_para_cliente({"id_cliente": "cliente_002"}, "rutina:texto")
    assert [rng_a.random() for _ in range(5)] != [rng_b.random() for _ in range(5)]


def test_different_namespaces_produce_different_rng_sequences_for_the_same_client():
    """rutina_reglas.py's exercise-selection RNG and its text RNG (and
    dieta_reglas.py's own) must not correlate just because they share a
    client -- otherwise picking one thing would silently bias the other."""
    perfil = {"id_cliente": "cliente_001"}
    rng_ejercicios = rng_para_cliente(perfil, "rutina:ejercicios")
    rng_texto = rng_para_cliente(perfil, "rutina:texto")
    assert [rng_ejercicios.random() for _ in range(5)] != [rng_texto.random() for _ in range(5)]


def test_falls_back_to_name_when_id_cliente_missing():
    """Variety is a nice-to-have -- a profile missing id_cliente (shouldn't
    happen per the schema, but generation must never hard-fail over it)
    still gets a usable, stable seed."""
    perfil = {"datos_basicos": {"nombre": "Ana Test"}}
    rng_1 = rng_para_cliente(perfil, "rutina:texto")
    rng_2 = rng_para_cliente(perfil, "rutina:texto")
    assert rng_1.random() == rng_2.random()


def test_elegir_variante_picks_from_the_given_list():
    rng = rng_para_cliente({"id_cliente": "cliente_001"}, "rutina:texto")
    variantes = ["a", "b", "c"]
    assert elegir_variante(rng, variantes) in variantes


def test_elegir_variante_single_item_list_is_safe():
    rng = rng_para_cliente({"id_cliente": "cliente_001"}, "rutina:texto")
    assert elegir_variante(rng, ["only option"]) == "only option"
