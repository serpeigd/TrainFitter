"""
Agente de dieta: redacta un borrador de dieta para un cliente concreto,
siguiendo el método del entrenador. Mismo patrón de diseño que routine_agent.py
(ver ese archivo para el razonamiento completo de "reglas" vs "llm" y de
salida estructurada); aquí solo se documentan las particularidades de dieta.

IMPORTANTE (método §7-§8): esto es un BORRADOR de nutrición, no una pauta
clínica. El agente no ajusta nada por patologías, embarazo/lactancia o
medicación por su cuenta — esas señales se recogen en
`advertencias_revision_humana` y disparan revisión reforzada del entrenador
(y derivación a un profesional titulado cuando corresponda) antes de enviar.
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
        "Entrega el borrador de dieta estructurado para el cliente, siguiendo "
        "fielmente el método del entrenador."
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
            "consejos_sinergias": {"type": "array", "items": {"type": "string"}},
            "advertencias_revision_humana": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Motivos por los que este borrador debería pasar por revisión reforzada "
                    "antes de enviarse (alergias, condiciones de salud, embarazo, medicación...). "
                    "Vacío si no aplica ninguno. NUNCA ajustes tú la dieta para una patología: "
                    "márcala aquí y deja el ajuste clínico al profesional."
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
    """Error propio del agente de dieta (clave ausente, timeout, respuesta malformada...)."""


@dataclass
class DietDraft:
    cliente_id: str
    contenido: dict

    def to_json(self, indent: int = 2) -> str:
        payload = {"cliente_id": self.cliente_id, **self.contenido}
        return json.dumps(payload, ensure_ascii=False, indent=indent)


def _build_system_prompt() -> str:
    metodo = load_metodo_entrenador()
    conocimiento_nutricion = load_knowledge_files("nutricion", "suplementacion", "sinergias_nutrientes")

    return f"""Eres el asistente que redacta BORRADORES de dieta para los clientes de un
entrenador personal, replicando fielmente su método y su criterio. Su motto es:
"Enseña a tu cuerpo que quien manda es tu mente".

No eres un profesional titulado: eres quien prepara un primer borrador para que el
entrenador (y, cuando corresponda, un profesional de la nutrición) lo revise y apruebe
antes de que llegue al cliente. Todo lo que generes es un PUNTO DE PARTIDA.

# MÉTODO DEL ENTRENADOR (tu criterio de referencia)
{metodo}

# BASE DE CONOCIMIENTO TÉCNICA (nutrición, suplementación, sinergias de absorción)
{conocimiento_nutricion}

# REGLAS AL DISEÑAR LA DIETA
- Sin alimentos prohibidos: cantidades y contexto, no restricción por restricción.
- Respeta siempre alergias, intolerancias y tipo de dieta (vegetariana/vegana/etc.).
- Si el perfil menciona una alergia, una enfermedad/condición, embarazo/lactancia o
  medicación habitual: NO diseñes un ajuste clínico por tu cuenta. Recoge el motivo
  exacto en `advertencias_revision_humana` y sigue con una dieta general prudente.
- Aplica sinergias de absorción cuando encajen con el perfil (p.ej. hierro vegetal +
  vitamina C en dietas vegetarianas/veganas).
- El mensaje para el cliente debe sonar a él: cercano, directo, pedagógico.
- Debes responder ÚNICAMENTE llamando a la herramienta `entregar_borrador_dieta`."""


def generar_borrador_dieta(
    perfil_cliente: dict,
    motor: str = "reglas",
    api_key: str | None = None,
    model: str = MODEL,
    timeout: float = 60.0,
) -> DietDraft:
    """
    Genera un borrador de dieta para un cliente.

    Args:
        perfil_cliente: dict con el mismo esquema que examples/cliente_ejemplo_*.json.
        motor: "reglas" (por defecto, gratis, determinista) o "llm".
        api_key, model, timeout: solo para motor="llm".

    Raises:
        DietAgentError: si el motor es "llm" y falta la API key, la llamada
            falla/expira, o la respuesta del modelo no trae el borrador esperado.
        ValueError: si `motor` no es "reglas" ni "llm".
    """
    if motor == "reglas":
        contenido = generar_borrador_dieta_reglas(perfil_cliente)
        return DietDraft(cliente_id=perfil_cliente.get("id_cliente", "desconocido"), contenido=contenido)
    if motor != "llm":
        raise ValueError(f"motor debe ser 'reglas' o 'llm', no {motor!r}")

    return _generar_borrador_dieta_llm(perfil_cliente, api_key=api_key, model=model, timeout=timeout)


def _generar_borrador_dieta_llm(
    perfil_cliente: dict,
    api_key: str | None = None,
    model: str = MODEL,
    timeout: float = 60.0,
) -> DietDraft:
    import anthropic

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise DietAgentError(
            "No se ha encontrado ANTHROPIC_API_KEY. Configúrala en tu archivo .env "
            "(copia .env.example a .env y rellena tu clave) antes de usar motor='llm'."
        )

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    system_prompt = _build_system_prompt()
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
                        "Este es el perfil del cliente (ficha de admisión ya rellenada). "
                        "Genera su borrador de dieta:\n\n" + perfil_json
                    ),
                }
            ],
            tools=[ENTREGAR_BORRADOR_DIETA_TOOL],
            tool_choice={"type": "tool", "name": "entregar_borrador_dieta"},
        )
    except anthropic.APITimeoutError as exc:
        raise DietAgentError(f"Timeout esperando respuesta del modelo ({timeout}s).") from exc
    except anthropic.APIConnectionError as exc:
        raise DietAgentError(f"No se pudo conectar con la API de Anthropic: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise DietAgentError(
            f"La API de Anthropic devolvió un error ({exc.status_code}): {exc.message}"
        ) from exc

    tool_uses = [block for block in response.content if block.type == "tool_use"]
    if not tool_uses:
        raise DietAgentError(
            "La respuesta del modelo no contiene el borrador estructurado esperado "
            f"(stop_reason={response.stop_reason!r})."
        )

    contenido = tool_uses[0].input
    return DietDraft(cliente_id=perfil_cliente.get("id_cliente", "desconocido"), contenido=contenido)
