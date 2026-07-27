"""
Agente de rutina: redacta un borrador de rutina de entrenamiento para un
cliente concreto, siguiendo el método del entrenador.

DISEÑO — dos motores intercambiables:
- "reglas" (por defecto, GRATIS): motor determinista en rutina_reglas.py que
  aplica los valores del método directamente en código. No necesita API key,
  no tiene coste, y es 100% reproducible — ideal para desarrollar y probar
  todo el pipeline sin depender de una cuenta de pago.
- "llm": llama al modelo de Anthropic con salida forzada por tool use. Se
  mantiene disponible para cuando haya presupuesto/API key configurada; en
  ese momento aporta redacción más rica y matices que las reglas no capturan.
Ambos motores devuelven el MISMO esquema (ver ENTREGAR_BORRADOR_RUTINA_TOOL),
así que el resto del pipeline (validador, orquestador) es agnóstico a cuál
se usó.

DISEÑO — por qué salida estructurada (JSON) y no Markdown libre:
Este borrador no es el destino final, es un paso intermedio del pipeline.
El agente validador (Fase 3) necesita poder recorrer los ejercicios en
código para cruzarlos contra las lesiones del cliente, y el orquestador
(Fase 4) necesita un estado programático, no un bloque de texto que haya
que volver a interpretar. Convertir JSON -> Markdown/HTML bonito para el
email (Fase 5/6) es un paso trivial; hacerlo al revés (parsear prosa) no lo es.

DISEÑO — qué parte de la base de conocimiento recibe el motor LLM:
Además del método (docs/metodo_entrenador.md), se le pasa la nota técnica
de entrenamiento y la de estilo de vida (recuperación/hábitos), que son las
relevantes para diseñar una rutina. Las notas de nutrición/suplementación
son objeto del agente de dieta (Fase 3), no de este.
"""

import json
import os
from dataclasses import dataclass

from knowledge import load_knowledge_files, load_metodo_entrenador
from rutina_reglas import generar_borrador_rutina_reglas

MODEL = "claude-sonnet-5"
# Sonnet 5 en vez de Opus: la tarea (redactar una rutina siguiendo un método ya
# documentado) no necesita el razonamiento más profundo/caro de Opus, y en vez
# de Haiku se prioriza calidad de personalización sobre coste mínimo, porque el
# resultado lo revisa un profesional pero debe llegarle ya bien pensado.

ENTREGAR_BORRADOR_RUTINA_TOOL = {
    "name": "entregar_borrador_rutina",
    "description": (
        "Entrega el borrador de rutina de entrenamiento estructurado para el cliente, "
        "siguiendo fielmente el método del entrenador."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "resumen_enfoque": {
                "type": "string",
                "description": "1-3 frases explicando el enfoque elegido para este cliente y por qué.",
            },
            "nivel_asumido": {
                "type": "string",
                "enum": ["principiante", "intermedio", "avanzado"],
            },
            "split": {
                "type": "string",
                "description": "Nombre del split elegido, p.ej. 'full_body', 'torso_pierna', 'push_pull_legs'.",
            },
            "dias_por_semana": {"type": "integer"},
            "duracion_sesion_min": {"type": "integer"},
            "advertencias_revision_humana": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Motivos por los que este borrador debería pasar por revisión "
                    "reforzada del entrenador antes de enviarse (lesiones, condiciones "
                    "de salud, dolor mencionado, etc). Lista vacía si no aplica ninguno."
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
                                    "series": {"type": "integer"},
                                    "repeticiones": {"type": "string"},
                                    "descanso_seg": {"type": "integer"},
                                    "notas": {"type": "string"},
                                },
                                "required": ["nombre", "series", "repeticiones"],
                            },
                        },
                        "cardio_opcional": {"type": "string"},
                    },
                    "required": ["dia", "ejercicios"],
                },
            },
            "progresion": {
                "type": "string",
                "description": "Cómo debe progresar el cliente semana a semana (sobrecarga progresiva).",
            },
            "mensaje_para_el_cliente": {
                "type": "string",
                "description": "Texto cercano, directo y pedagógico dirigido al cliente, en el tono real del entrenador.",
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
    """Error propio del agente de rutina (clave ausente, timeout, respuesta malformada...)."""


@dataclass
class RoutineDraft:
    """Borrador de rutina ya parseado, listo para el resto del pipeline."""

    cliente_id: str
    contenido: dict  # cumple ENTREGAR_BORRADOR_RUTINA_TOOL["input_schema"]

    def to_json(self, indent: int = 2) -> str:
        payload = {"cliente_id": self.cliente_id, **self.contenido}
        return json.dumps(payload, ensure_ascii=False, indent=indent)


def _build_system_prompt() -> str:
    metodo = load_metodo_entrenador()
    conocimiento_entrenamiento = load_knowledge_files(
        "entrenamiento", "estilo_vida_longevidad", "seguridad_poblaciones_especiales"
    )

    return f"""Eres el asistente que redacta BORRADORES de rutina de entrenamiento para
los clientes de un entrenador personal, replicando fielmente su método y su criterio.
Su motto es: "Enseña a tu cuerpo que quien manda es tu mente".

No eres el entrenador: eres quien le prepara un primer borrador para que él lo revise,
ajuste y apruebe antes de que llegue al cliente. Todo lo que generes es un PUNTO DE
PARTIDA, no una prescripción final.

# MÉTODO DEL ENTRENADOR (tu criterio de referencia)
{metodo}

# BASE DE CONOCIMIENTO TÉCNICA (entrenamiento y estilo de vida)
{conocimiento_entrenamiento}

# REGLAS AL DISEÑAR LA RUTINA
- Adapta días/semana, duración de sesión y material a la disponibilidad real del
  cliente. No propongas nada que no pueda hacer con lo que tiene.
- Si el perfil menciona una lesión, una condición de salud, embarazo/lactancia o
  cualquier dolor: adapta los ejercicios evitando lo contraindicado (p.ej. evita
  sentadilla libre profunda si hay lesión de rodilla) y añade el motivo exacto en
  `advertencias_revision_humana`. Nunca lo ignores ni lo minimices.
- Los valores del método (rangos de series/reps, volumen...) son puntos de partida
  razonables, no reglas rígidas: ajústalos al nivel, objetivo y contexto de esta
  persona concreta.
- El mensaje para el cliente debe sonar a él: cercano, directo, pedagógico, sin
  tecnicismos sin explicar.
- Debes responder ÚNICAMENTE llamando a la herramienta `entregar_borrador_rutina`."""


def generar_borrador_rutina(
    perfil_cliente: dict,
    motor: str = "reglas",
    api_key: str | None = None,
    model: str = MODEL,
    timeout: float = 60.0,
) -> RoutineDraft:
    """
    Genera un borrador de rutina para un cliente.

    Args:
        perfil_cliente: dict con el mismo esquema que examples/cliente_ejemplo_*.json.
        motor: "reglas" (por defecto, gratis, determinista) o "llm" (API de
            Anthropic, requiere ANTHROPIC_API_KEY).
        api_key: solo para motor="llm". Si no se pasa, se lee de ANTHROPIC_API_KEY.
        model: solo para motor="llm". String de modelo de Anthropic a usar.
        timeout: solo para motor="llm". Timeout en segundos para la llamada.

    Raises:
        RoutineAgentError: si el motor es "llm" y falta la API key, la llamada
            falla/expira, o la respuesta del modelo no trae el borrador esperado.
        ValueError: si `motor` no es "reglas" ni "llm".
    """
    if motor == "reglas":
        contenido = generar_borrador_rutina_reglas(perfil_cliente)
        return RoutineDraft(cliente_id=perfil_cliente.get("id_cliente", "desconocido"), contenido=contenido)
    if motor != "llm":
        raise ValueError(f"motor debe ser 'reglas' o 'llm', no {motor!r}")

    return _generar_borrador_rutina_llm(perfil_cliente, api_key=api_key, model=model, timeout=timeout)


def _generar_borrador_rutina_llm(
    perfil_cliente: dict,
    api_key: str | None = None,
    model: str = MODEL,
    timeout: float = 60.0,
) -> RoutineDraft:
    """Motor LLM (opcional): llama a la API de Anthropic con salida forzada por tool use."""
    import anthropic  # import perezoso: quien solo use el motor "reglas" no necesita este paquete

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RoutineAgentError(
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
                        "Genera su borrador de rutina:\n\n" + perfil_json
                    ),
                }
            ],
            tools=[ENTREGAR_BORRADOR_RUTINA_TOOL],
            tool_choice={"type": "tool", "name": "entregar_borrador_rutina"},
        )
    except anthropic.APITimeoutError as exc:
        raise RoutineAgentError(f"Timeout esperando respuesta del modelo ({timeout}s).") from exc
    except anthropic.APIConnectionError as exc:
        raise RoutineAgentError(f"No se pudo conectar con la API de Anthropic: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise RoutineAgentError(
            f"La API de Anthropic devolvió un error ({exc.status_code}): {exc.message}"
        ) from exc

    tool_uses = [block for block in response.content if block.type == "tool_use"]
    if not tool_uses:
        raise RoutineAgentError(
            "La respuesta del modelo no contiene el borrador estructurado esperado "
            f"(stop_reason={response.stop_reason!r})."
        )

    contenido = tool_uses[0].input
    return RoutineDraft(cliente_id=perfil_cliente.get("id_cliente", "desconocido"), contenido=contenido)
