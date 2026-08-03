"""
Per-client seeded variety for the free rule engines (rutina_reglas.py,
dieta_reglas.py) — no LLM, no API call, no new dependency (random is
standard library), matching this project's free-only guardrail.

DESIGN — seeded, not truly random: the project owner's explicit call.
random.Random seeded from the client's own id_cliente means regenerating
the SAME client always reproduces the SAME plan — stable and testable,
and the trainer never sees an unexplained different plan just from
reloading the page — while two DIFFERENT clients with otherwise similar
profiles no longer get byte-identical output. See docs/decisiones.md for
the fuller rationale and what this replaced.

DESIGN — namespaced per purpose: rng_para_cliente() takes a `namespace`
string alongside id_cliente, so rutina_reglas.py's exercise-selection RNG
and its narrative-text RNG (and dieta_reglas.py's own) are independent
sequences — using one doesn't shift what the other would have picked,
even though they all derive from the same client.
"""

import random


def rng_para_cliente(perfil_cliente: dict, namespace: str) -> random.Random:
    """A random.Random instance seeded deterministically from this client's
    id_cliente and the given namespace. Falls back to the client's name if
    id_cliente is somehow missing, rather than raising — variety is a nice-
    to-have, and generation should never hard-fail over it."""
    identidad = perfil_cliente.get("id_cliente") or perfil_cliente.get("datos_basicos", {}).get("nombre", "")
    return random.Random(f"{identidad}:{namespace}")


def elegir_variante(rng: random.Random, variantes: list[str]) -> str:
    """Picks one of several equivalent phrasings using the given per-client
    RNG. Trivial, but named so call sites read as "pick a phrasing", not
    "call some RNG method"."""
    return rng.choice(variantes)
