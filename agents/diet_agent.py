"""
Diet agent: writes a draft diet for a specific client, following the
trainer's method. Same design pattern as routine_agent.py (see that file
for the full "reglas" vs. "llm" and structured-output reasoning); only
diet-specific details are documented here.

IMPORTANT (method §7-§8): this is a nutrition DRAFT, not a clinical
prescription. The agent never adjusts anything for conditions,
pregnancy/breastfeeding, or medication on its own — those signals are
collected in `advertencias_revision_humana` and trigger the trainer's
enhanced review (and referral to a licensed professional where appropriate)
before sending.
"""

import json
import os
from dataclasses import dataclass

from dieta_reglas import generar_borrador_dieta_reglas
from knowledge import load_knowledge_files, load_metodo_entrenador

MODEL = "claude-sonnet-5"

ENTREGAR_BORRADOR_DIETA_TOOL = {
    "name": "entregar_borrador_dieta",
    "description": (
        "Delivers the structured diet draft for the client, faithfully "
        "following the trainer's method."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "resumen_enfoque": {"type": "string"},
            "calorias_objetivo_kcal": {"type": "integer"},
            "macros": {
                "type": "object",
                "properties": {
                    "proteina_g": {"type": "integer"},
                    "grasa_g": {"type": "integer"},
                    "carbohidratos_g": {"type": "integer"},
                },
                "required": ["proteina_g", "grasa_g", "carbohidratos_g"],
            },
            "comidas_al_dia": {"type": "integer"},
            "distribucion_comidas": {"type": "string"},
            "fuentes_proteina_sugeridas": {"type": "array", "items": {"type": "string"}},
            "fuentes_carbohidrato_sugeridas": {"type": "array", "items": {"type": "string"}},
            "fuentes_grasa_sugeridas": {"type": "array", "items": {"type": "string"}},
            "fuentes_verdura_sugeridas": {"type": "array", "items": {"type": "string"}},
            "plan_semanal": {
                "type": "array",
                "description": (
                    "A 7-day meal plan, Monday first. Each day breaks down into "
                    "breakfast/lunch/dinner (+ snacks matching comidas_al_dia), each "
                    "with a short description of what to eat and its approximate kcal."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "dia": {"type": "string"},
                        "comidas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "tipo": {"type": "string"},
                                    "descripcion": {"type": "string"},
                                    "aprox_kcal": {"type": "integer"},
                                },
                                "required": ["tipo", "descripcion", "aprox_kcal"],
                            },
                        },
                    },
                    "required": ["dia", "comidas"],
                },
            },
            "consejos_sinergias": {"type": "array", "items": {"type": "string"}},
            "advertencias_revision_humana": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Reasons this draft should go through enhanced review before "
                    "being sent (allergies, health conditions, pregnancy, "
                    "medication...). Empty if none apply. NEVER adjust the diet "
                    "yourself for a condition: flag it here and leave the clinical "
                    "adjustment to the professional."
                ),
            },
            "mensaje_para_el_cliente": {"type": "string"},
        },
        "required": [
            "resumen_enfoque",
            "calorias_objetivo_kcal",
            "macros",
            "comidas_al_dia",
            "fuentes_proteina_sugeridas",
            "advertencias_revision_humana",
            "mensaje_para_el_cliente",
        ],
    },
}


class DietAgentError(Exception):
    """The diet agent's own error (missing key, timeout, malformed response...)."""


@dataclass
class DietDraft:
    cliente_id: str
    contenido: dict

    def to_json(self, indent: int = 2) -> str:
        payload = {"cliente_id": self.cliente_id, **self.contenido}
        return json.dumps(payload, ensure_ascii=False, indent=indent)


def _build_system_prompt() -> str:
    metodo = load_metodo_entrenador()
    conocimiento_nutricion = load_knowledge_files(
        "nutricion", "suplementacion", "sinergias_nutrientes", "seguridad_poblaciones_especiales"
    )

    return f"""You are the assistant that writes diet DRAFTS for a personal trainer's
clients, faithfully replicating their method and judgment. Their motto is:
"Teach your body that your mind is in charge."

You are not a licensed professional: you're the one preparing a first draft for the
trainer (and, when appropriate, a nutrition professional) to review and approve
before it reaches the client. Everything you generate is a STARTING POINT.

# TRAINER'S METHOD (your reference judgment)
{metodo}

# TECHNICAL KNOWLEDGE BASE (nutrition, supplementation, absorption synergies)
{conocimiento_nutricion}

# RULES WHEN DESIGNING THE DIET
- No forbidden foods: amounts and context, not restriction for restriction's sake.
- Always respect allergies, intolerances, and diet type (vegetarian/vegan/etc.).
- If the profile mentions an allergy, a disease/condition, pregnancy/breastfeeding, or
  regular medication: DO NOT design a clinical adjustment yourself. Capture the exact
  reason in `advertencias_revision_humana` and stick to a general, cautious diet.
- Apply absorption synergies when they fit the profile (e.g. plant iron + vitamin C
  in vegetarian/vegan diets).
- Never suggest a food the client listed under disliked foods or additional
  restrictions, even though those aren't allergies. If they mentioned a dietary
  approach or main concern (e.g. anti-inflammatory, lowering gluten, gut health,
  more fiber, more iron/anemia), lean the suggestions that way and say so in
  `consejos_sinergias` -- but a "lower gluten" preference is not the same as a
  declared gluten allergy/intolerance: don't treat it as one, and don't add an
  `advertencias_revision_humana` entry for it.
- If the profile reports high stress, low average sleep, or a sedentary job, you may
  lean the suggestions toward magnesium-rich or higher-fiber foods respectively and
  mention why -- this is a preference, not a clinical adjustment.
- If `experiencia.nivel_compromiso` is "chill", keep the calorie target gentler than
  usual; if "tryhard", it can be a bit more assertive (never crossing into an
  aggressive deficit/surplus), and you may suggest niche/specialty foods and general
  evidence-based supplement tips (creatine, protein powder, caffeine) -- skip any
  supplement the client already listed under `salud.suplementos_actuales`. If the
  profile lists BOTH current supplements and regular medication, treat that as a
  possible interaction: note it in `advertencias_revision_humana`, don't try to
  resolve it yourself.
- Build `plan_semanal` as a real, varied 7-day plan (Monday first) -- not the same
  meals repeated every day. Every food you mention in it must also appear in the
  matching fuentes_*_sugeridas list (protein/carbohydrate/fat/vegetable), so it never
  suggests something outside what's already been filtered for this client's diet
  type and allergies.
- The message to the client should sound like the trainer: warm, direct, pedagogical.
- You must respond ONLY by calling the `entregar_borrador_dieta` tool."""


def generar_borrador_dieta(
    perfil_cliente: dict,
    motor: str = "reglas",
    idioma: str = "en",
    api_key: str | None = None,
    model: str = MODEL,
    timeout: float = 60.0,
) -> DietDraft:
    """
    Generates a draft diet for a client.

    Args:
        perfil_cliente: dict with the same schema as examples/cliente_ejemplo_*.json.
        motor: "reglas" (default, free, deterministic) or "llm".
        idioma: "en" (default) or "es" — language of the narrative text; see
            dieta_reglas.generar_borrador_dieta_reglas()'s docstring for
            what this does and doesn't affect.
        api_key, model, timeout: only for motor="llm".

    Raises:
        DietAgentError: if motor is "llm" and the API key is missing, the
            call fails/times out, or the model's response doesn't include
            the expected draft.
        ValueError: if `motor` is neither "reglas" nor "llm".
    """
    if motor == "reglas":
        contenido = generar_borrador_dieta_reglas(perfil_cliente, idioma=idioma)
        return DietDraft(cliente_id=perfil_cliente.get("id_cliente", "desconocido"), contenido=contenido)
    if motor != "llm":
        raise ValueError(f"motor must be 'reglas' or 'llm', not {motor!r}")

    return _generar_borrador_dieta_llm(perfil_cliente, idioma=idioma, api_key=api_key, model=model, timeout=timeout)


def _generar_borrador_dieta_llm(
    perfil_cliente: dict,
    idioma: str = "en",
    api_key: str | None = None,
    model: str = MODEL,
    timeout: float = 60.0,
) -> DietDraft:
    import anthropic

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise DietAgentError(
            "ANTHROPIC_API_KEY not found. Set it in your .env file "
            "(copy .env.example to .env and fill in your key) before using motor='llm'."
        )

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    system_prompt = _build_system_prompt()
    if idioma == "es":
        system_prompt += "\n\nWrite all user-facing text (resumen_enfoque, distribucion_comidas, mensaje_para_el_cliente, consejos_sinergias) in Spanish."
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
                        "Generate their draft diet:\n\n" + perfil_json
                    ),
                }
            ],
            tools=[ENTREGAR_BORRADOR_DIETA_TOOL],
            tool_choice={"type": "tool", "name": "entregar_borrador_dieta"},
        )
    except anthropic.APITimeoutError as exc:
        raise DietAgentError(f"Timeout waiting for the model's response ({timeout}s).") from exc
    except anthropic.APIConnectionError as exc:
        raise DietAgentError(f"Could not connect to the Anthropic API: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise DietAgentError(
            f"The Anthropic API returned an error ({exc.status_code}): {exc.message}"
        ) from exc

    tool_uses = [block for block in response.content if block.type == "tool_use"]
    if not tool_uses:
        raise DietAgentError(
            "The model's response doesn't contain the expected structured draft "
            f"(stop_reason={response.stop_reason!r})."
        )

    contenido = tool_uses[0].input
    return DietDraft(cliente_id=perfil_cliente.get("id_cliente", "desconocido"), contenido=contenido)
