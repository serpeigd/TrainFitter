"""
Routine agent: writes a draft training routine for a specific client,
following the trainer's method.

DESIGN — two interchangeable engines:
- "reglas" (default, FREE): a deterministic engine in rutina_reglas.py that
  applies the method's values directly in code. No API key needed, no cost,
  and 100% reproducible — ideal for developing and testing the whole
  pipeline without depending on a paid account.
- "llm": calls the Anthropic model with output forced via tool use. Kept
  available for when there's budget/an API key configured; at that point it
  adds richer writing and nuance the rules can't capture.
Both engines return the SAME schema (see ENTREGAR_BORRADOR_RUTINA_TOOL), so
the rest of the pipeline (validator, orchestrator) is agnostic to which one
was used.

DESIGN — why structured output (JSON) and not free-form Markdown:
This draft isn't the final destination, it's an intermediate step in the
pipeline. The validator agent (Phase 3) needs to be able to walk the
exercises in code to cross-check them against the client's injuries, and
the orchestrator (Phase 4) needs programmatic state, not a block of text
that has to be re-interpreted. Converting JSON -> nice Markdown/HTML for the
email (Phase 5/6) is a trivial step; doing it the other way around (parsing
prose) is not.

DESIGN — what part of the knowledge base the LLM engine receives:
Besides the method (docs/metodo_entrenador.md), it's given the training note
and the lifestyle note (recovery/habits), which are the relevant ones for
designing a routine. The nutrition/supplementation notes are the diet
agent's concern (Phase 3), not this one's.
"""

import json
import os
from dataclasses import dataclass

from knowledge import load_knowledge_files, load_metodo_entrenador
from rutina_reglas import generar_borrador_rutina_reglas

MODEL = "claude-sonnet-5"
# Sonnet 5 instead of Opus: the task (writing a routine following an
# already-documented method) doesn't need Opus's deeper/more expensive
# reasoning, and instead of Haiku, personalization quality is prioritized
# over minimal cost, because a professional reviews the result but it
# should arrive already well thought out.

ENTREGAR_BORRADOR_RUTINA_TOOL = {
    "name": "entregar_borrador_rutina",
    "description": (
        "Delivers the structured training routine draft for the client, "
        "faithfully following the trainer's method."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "resumen_enfoque": {
                "type": "string",
                "description": "1-3 sentences explaining the approach chosen for this client and why.",
            },
            "nivel_asumido": {
                "type": "string",
                "enum": ["principiante", "intermedio", "avanzado"],
            },
            "split": {
                "type": "string",
                "description": "Name of the chosen split, e.g. 'full_body', 'upper_lower', 'push_pull_legs'.",
            },
            "dias_por_semana": {"type": "integer"},
            "duracion_sesion_min": {"type": "integer"},
            "advertencias_revision_humana": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Reasons this draft should go through the trainer's enhanced "
                    "review before being sent (injuries, health conditions, pain "
                    "mentioned, etc). Empty list if none apply."
                ),
            },
            "sesiones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "dia": {"type": "string"},
                        "grupos_musculares": {"type": "array", "items": {"type": "string"}},
                        "calentamiento": {"type": "string"},
                        "ejercicios": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "nombre": {"type": "string"},
                                    "grupo": {
                                        "type": "string",
                                        "description": (
                                            "Internal muscle-group key for this exercise, e.g. 'pecho', "
                                            "'espalda' -- lets a client's future 'like this exercise' "
                                            "carry over correctly. Not shown to the client."
                                        ),
                                    },
                                    "tipo": {
                                        "type": "string",
                                        "enum": ["basico", "aislamiento"],
                                    },
                                    "series": {"type": "integer"},
                                    "repeticiones": {"type": "string"},
                                    "descanso_seg": {"type": "integer"},
                                    "notas": {"type": "string"},
                                },
                                "required": ["nombre", "series", "repeticiones"],
                            },
                        },
                        "cardio_opcional": {"type": "string"},
                        "nota_esfuerzo": {
                            "type": "string",
                            "description": (
                                "One sentence on how close to failure to train this session -- e.g. "
                                "reps-in-reserve (RIR) guidance for the compound work vs. the isolation work."
                            ),
                        },
                    },
                    "required": ["dia", "ejercicios"],
                },
            },
            "progresion": {
                "type": "string",
                "description": "How the client should progress week to week (progressive overload).",
            },
            "mensaje_para_el_cliente": {
                "type": "string",
                "description": "Warm, direct, pedagogical text addressed to the client, in the trainer's real tone.",
            },
        },
        "required": [
            "resumen_enfoque",
            "nivel_asumido",
            "dias_por_semana",
            "advertencias_revision_humana",
            "sesiones",
            "progresion",
            "mensaje_para_el_cliente",
        ],
    },
}


class RoutineAgentError(Exception):
    """The routine agent's own error (missing key, timeout, malformed response...)."""


@dataclass
class RoutineDraft:
    """An already-parsed routine draft, ready for the rest of the pipeline."""

    cliente_id: str
    contenido: dict  # matches ENTREGAR_BORRADOR_RUTINA_TOOL["input_schema"]

    def to_json(self, indent: int = 2) -> str:
        payload = {"cliente_id": self.cliente_id, **self.contenido}
        return json.dumps(payload, ensure_ascii=False, indent=indent)


def _build_system_prompt() -> str:
    metodo = load_metodo_entrenador()
    conocimiento_entrenamiento = load_knowledge_files(
        "entrenamiento", "estilo_vida_longevidad", "seguridad_poblaciones_especiales"
    )

    return f"""You are the assistant that writes training routine DRAFTS for a personal
trainer's clients, faithfully replicating their method and judgment.
Their motto is: "Teach your body that your mind is in charge."

You are not the trainer: you're the one preparing a first draft for them to review,
adjust, and approve before it reaches the client. Everything you generate is a
STARTING POINT, not a final prescription.

# TRAINER'S METHOD (your reference judgment)
{metodo}

# TECHNICAL KNOWLEDGE BASE (training and lifestyle)
{conocimiento_entrenamiento}

# RULES WHEN DESIGNING THE ROUTINE
- Adapt days/week, session length, and equipment to the client's real availability.
  Don't propose anything they can't do with what they have.
- If the client trains at home with little or no gym equipment (`lugar_entreno`
  "casa_con_material"/"casa_sin_material"), don't default to bodyweight-only:
  mix in creative household substitutes (water jugs/bottles as dumbbells, a
  loaded backpack for rows/squats/lunges, a towel on a smooth floor as a
  sliding surface) alongside genuine bodyweight work. If `material_disponible`
  includes `"gomas"` (resistance bands), use them too -- a real, distinct
  equipment type from the household substitutes above, not interchangeable
  with them: band presses/rows/squats/curls/pushdowns/Pallof presses add
  resistance a bodyweight-only or water-jug exercise can't. Don't prescribe pull-ups,
  dips, or anything else that needs a real bar/anchor to hang or push off of
  unless the client explicitly reported having one -- most homes don't, even
  when the client otherwise has some equipment. Use an inverted row against a
  sturdy table or push-ups instead of a pull-up/dip, the same substitution the
  rule engine makes.
- If the profile mentions an injury, a health condition, pregnancy/breastfeeding, or
  any pain: adapt the exercises to avoid what's contraindicated (e.g. avoid deep free
  squats if there's a knee injury) and add the exact reason to
  `advertencias_revision_humana`. Never ignore or downplay it.
- The method's values (set/rep ranges, volume...) are reasonable starting points,
  not rigid rules: adjust them to this specific person's level, goal, and context.
  A beginner should get less volume and simpler, more guided exercises than an
  advanced trainee with the exact same available equipment; trim the number of
  exercises per session for someone with limited time (e.g. under 45 minutes)
  rather than prescribing a session they can't actually finish; and if they
  reported high stress or short sleep, keep volume a bit more conservative for
  this first block and say so in the summary.
- `experiencia.nivel_compromiso` (basico/normal/avanzado/tryhard) controls both
  volume AND exercise complexity, going from simplest/least demanding at
  "basico" to most specific/optimized at "tryhard" -- say so briefly in the
  summary at every level so the client knows their choice was received.
  - "basico": trim volume slightly (one fewer set) AND prefer the simplest,
    least technically demanding exercise variants (machine-guided/bodyweight
    over free-weight/barbell) for every slot, regardless of the client's own
    training experience -- "essentials only" applies even to an experienced
    lifter who picked this level.
  - "normal": the default, no adjustment.
  - "avanzado": same volume as "normal" (its set count never moves), but a
    real middle step for exercise selection -- lean toward dumbbell-level
    variants over both pure bodyweight/machine AND barbell compounds where the
    slot allows. Still never touch the small curated "niche" pool that's
    "tryhard"-only (see below).
  - "tryhard" (the most complete level this project currently offers): volume
    can be a bit higher (one extra set) AND you may lean toward more
    technically demanding exercise variants (e.g. Bulgarian split squats,
    weighted pull-ups) where the client's equipment allows -- UNLESS the
    client is a genuine beginner (`experiencia.nivel == "principiante"`), in
    which case keep the simpler variants regardless of "tryhard" -- training
    experience is a safety signal that outranks a detail-level preference.
- `progresion` should match the client's `nivel_compromiso`, same as the volume/exercise
  adjustments above: for "basico"/"normal", the simple rule ("chase one more rep before you
  chase more weight, add load once every set tops out its range") is genuinely the right
  level. For "avanzado"/"tryhard", that rule is beginner-level guidance they already know --
  give them something they don't: MEV/MAV/MRV block progression (start near minimum effective
  volume, add a set every week or two toward the maximum adaptive range, deload before hitting
  the recoverable ceiling), how reps-in-reserve should calibrate every set rather than just
  "add a rep," or training frequency (twice a week per muscle group at moderate volume usually
  beats once a week at the same total volume).
- `experiencia.ajustes_rutina` is a list of trainer-picked adjustment keys (from a
  searchable dropdown, not free text) -- apply each one that's present, and say so in
  `resumen_enfoque` the same way the rule engine's own transparency note does:
  `"mas_volumen"`/`"menos_volumen"` (one set up/down, same floor as everything else),
  `"mas_descanso"`/`"menos_descanso"` (~30s more/less rest between sets, never under
  30s), `"mas_cardio"` (every session gets the cardio block, not just the last one)/
  `"menos_cardio"` (drop it from every session), `"evitar_barra"` (prefer non-barbell
  variants for this client specifically -- a preference, not a safety exclusion, so
  only apply it where an equally valid alternative exists), `"preferir_maquinas"`
  (lean toward machine-based exercises where the client's equipment allows).
- Give every session a one-sentence `nota_esfuerzo`: reps-in-reserve (RIR) guidance,
  not just a rep-count range. Compound/basic lifts should stay 1-2 reps short of
  failure; isolation work at the end of the session can go closer to failure
  (0-1 reps left) -- proximity to failure is its own training variable, separate
  from load and volume.
- Every session's `calentamiento` is mandatory (never empty) and must name real
  exercises, not just "mobility": banded external/internal rotations for rotator-cuff
  activation before any shoulder-heavy session (upper body, push, pull), and hip
  circles/leg swings/bodyweight glute bridges before any leg-heavy session (lower
  body, full body) -- these are the two joints warm-up research flags for injury
  risk under load, so name them specifically.
- `mensaje_para_el_cliente` should end with one goal-specific sentence proposing the
  actual starting approach (not just generic encouragement) -- e.g. for `perdida_grasa`,
  something like "lifting stays the priority, with some cardio added around it to
  speed things up"; for `hipertrofia`, "the focus is raising volume while eating
  enough to support it"; for `recomposicion_corporal`, "strength and technique on
  the basics drives this more than volume or cardio"; for `salud_general`,
  "consistency, not maximum performance, is the actual goal."
- The message to the client should sound like the trainer: warm, direct,
  pedagogical, no unexplained jargon.
- You must respond ONLY by calling the `entregar_borrador_rutina` tool."""


def generar_borrador_rutina(
    perfil_cliente: dict,
    motor: str = "reglas",
    idioma: str = "en",
    api_key: str | None = None,
    model: str = MODEL,
    timeout: float = 60.0,
) -> RoutineDraft:
    """
    Generates a draft routine for a client.

    Args:
        perfil_cliente: dict with the same schema as examples/cliente_ejemplo_*.json.
        motor: "reglas" (default, free, deterministic) or "llm" (Anthropic
            API, requires ANTHROPIC_API_KEY).
        idioma: "en" (default) or "es" — language of the narrative text
            (resumen_enfoque, progresion, mensaje_para_el_cliente, etc; see
            rutina_reglas.generar_borrador_rutina_reglas()'s docstring for
            what this does and doesn't affect).
        api_key: only for motor="llm". If not passed, read from ANTHROPIC_API_KEY.
        model: only for motor="llm". Anthropic model string to use.
        timeout: only for motor="llm". Timeout in seconds for the call.

    Raises:
        RoutineAgentError: if motor is "llm" and the API key is missing, the
            call fails/times out, or the model's response doesn't include
            the expected draft.
        ValueError: if `motor` is neither "reglas" nor "llm".
    """
    if motor == "reglas":
        contenido = generar_borrador_rutina_reglas(perfil_cliente, idioma=idioma)
        return RoutineDraft(cliente_id=perfil_cliente.get("id_cliente", "desconocido"), contenido=contenido)
    if motor != "llm":
        raise ValueError(f"motor must be 'reglas' or 'llm', not {motor!r}")

    return _generar_borrador_rutina_llm(perfil_cliente, idioma=idioma, api_key=api_key, model=model, timeout=timeout)


def _generar_borrador_rutina_llm(
    perfil_cliente: dict,
    idioma: str = "en",
    api_key: str | None = None,
    model: str = MODEL,
    timeout: float = 60.0,
) -> RoutineDraft:
    """LLM engine (optional): calls the Anthropic API with output forced via tool use."""
    import anthropic  # lazy import: anyone only using motor="reglas" doesn't need this package

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RoutineAgentError(
            "ANTHROPIC_API_KEY not found. Set it in your .env file "
            "(copy .env.example to .env and fill in your key) before using motor='llm'."
        )

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    system_prompt = _build_system_prompt()
    if idioma == "es":
        system_prompt += "\n\nWrite all user-facing text (resumen_enfoque, progresion, mensaje_para_el_cliente) in Spanish."
    perfil_json = json.dumps(perfil_cliente, ensure_ascii=False, indent=2)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Here is the client's profile (intake form already filled out). "
                        "Generate their draft routine:\n\n" + perfil_json
                    ),
                }
            ],
            tools=[ENTREGAR_BORRADOR_RUTINA_TOOL],
            tool_choice={"type": "tool", "name": "entregar_borrador_rutina"},
        )
    except anthropic.APITimeoutError as exc:
        raise RoutineAgentError(f"Timeout waiting for the model's response ({timeout}s).") from exc
    except anthropic.APIConnectionError as exc:
        raise RoutineAgentError(f"Could not connect to the Anthropic API: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise RoutineAgentError(
            f"The Anthropic API returned an error ({exc.status_code}): {exc.message}"
        ) from exc

    tool_uses = [block for block in response.content if block.type == "tool_use"]
    if not tool_uses:
        raise RoutineAgentError(
            "The model's response doesn't contain the expected structured draft "
            f"(stop_reason={response.stop_reason!r})."
        )

    contenido = tool_uses[0].input
    return RoutineDraft(cliente_id=perfil_cliente.get("id_cliente", "desconocido"), contenido=contenido)
