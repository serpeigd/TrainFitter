# Arquitectura de TrainFitter

> **Estado: pipeline completo (Fases 0-4) + panel del entrenador (Fase 5-lite).**
> Falta la integración con Notion/Gmail reales y el disparador automático desde
> `inbox/`. La versión final orientada a lector técnico llega en la Fase 7.

---

## Visión general

TrainFitter es un pipeline de agentes que transforma la ficha de un cliente en
borradores de rutina y dieta, con una **revisión humana obligatoria** antes de
cualquier envío. Cada agente tiene una responsabilidad única y acotada.

## Decisión clave: dos motores intercambiables por agente

`routine_agent` y `diet_agent` no llaman a un único backend fijo: exponen un parámetro
`motor` con dos implementaciones que devuelven **el mismo esquema de salida**, así que
el resto del pipeline es agnóstico a cuál se usó.

| Motor | Coste | Cómo funciona | Cuándo se usa |
|---|---|---|---|
| `"reglas"` (por defecto) | **Gratis**, sin API key, sin red | Código Python determinista que aplica los valores del método directamente (splits, rangos de reps, cálculo de calorías/macros, banco de ejercicios/alimentos filtrado por material/alergias/lesiones) | Desarrollo, demos, todo el pipeline hoy |
| `"llm"` (opcional) | Requiere `ANTHROPIC_API_KEY` | Llama al modelo de Anthropic con salida forzada por *tool use* (`entregar_borrador_rutina` / `entregar_borrador_dieta`) | Cuando se quiera redacción más rica/matizada; queda ya diseñado para activarse sin tocar el resto del sistema |

El **agente validador**, en cambio, es **siempre reglas** por diseño: un gate de
seguridad debe ser determinista y auditable, no una "opinión" de un modelo — ver
`agents/validator_agent.py` para el razonamiento completo.

## Flujo de datos

```
   Ficha cliente (admission/) ──► Perfil JSON (esquema en examples/cliente_ejemplo_*.json)
                                          │
                     ┌────────────────────┼────────────────────┐
                     ▼                    ▼                    ▼
              routine_agent          diet_agent          (ambos leen)
              (motor reglas/llm)     (motor reglas/llm)  docs/metodo_entrenador.md
                     │                    │              docs/base_conocimiento/*
                     ▼                    ▼
              borrador_rutina        borrador_dieta
                     │                    │
                     └─────────┬──────────┘
                                ▼
                       validator_agent (siempre reglas)
                     - relee el perfil crudo (no confía ciegamente
                       en las advertencias de rutina/dieta)
                     - cruza ejercicios vs. lesiones (exercise_bank)
                     - cruza alimentos vs. alergias (food_bank)
                                ▼
                    veredicto: aprobado_automatico | revision_reforzada
                                ▼
                        Revisión humana (SIEMPRE, sin excepción)
                                ▼
                  Envío al cliente (borrador en Gmail — Fase 5+)
```

## Diagrama de estados del orquestador (real, `agents/orchestrator.py`)

```
 ficha_recibida
       │  routine_agent.generar_borrador_rutina()
       ▼
 rutina_generada
       │  diet_agent.generar_borrador_dieta()
       ▼
 dieta_generada
       │  validator_agent.validar_borradores()
       ▼
 validado
       │
       ├── veredicto == "revision_reforzada" ──► pendiente_revision_reforzada
       │
       └── veredicto == "aprobado_automatico" ──► pendiente_aprobacion_humana

 (en cualquier punto, si un agente lanza RoutineAgentError/DietAgentError) ──► error
```

Ambas ramas de éxito terminan en un estado "pendiente_*": **incluso
`aprobado_automatico` significa "sin motivos de revisión reforzada", nunca "enviar
sin que nadie lo mire"**. El entrenador siempre aprueba antes de que algo llegue al
cliente — ver `PipelineState` en `agents/orchestrator.py`.

`ejecutar_pipeline()` acepta un callback `on_transition` opcional (por defecto,
loguea a consola). Esto es lo que permite que la UI (ver más abajo) pinte el mismo
recorrido de estados en pantalla en vez de en una terminal que el usuario nunca ve,
sin que el orquestador sepa nada de Streamlit.

## Panel del entrenador (`ui/app.py`) — interfaz Streamlit

El pipeline por CLI es la capa de desarrollo; `ui/app.py` es la capa que un
entrenador sin conocimientos técnicos podría usar de verdad. Convierte
`ejecutar_pipeline()` en una experiencia de clic:

- **Pestaña "Cliente de ejemplo":** elige uno de los JSON en `examples/`, previsualiza
  la ficha completa, genera el plan.
- **Pestaña "Nueva ficha":** formulario completo que espeja
  `admission/ficha_cliente_template.md` (datos básicos, objetivo, experiencia,
  disponibilidad, salud, nutrición, estilo de vida) y construye el mismo JSON que
  consumen los agentes — un entrenador podría dar de alta un cliente real sin tocar
  código ni JSON a mano.
- **Ejecución en vivo:** `st.status(...)` + el callback `on_transition` muestran cada
  transición del orquestador según ocurre.
- **Resultado:** veredicto (con motivos si aplica revisión reforzada), rutina por
  sesión con tabla de ejercicios, dieta con macros y fuentes sugeridas, y botones de
  descarga en JSON.
- **Aprobación simulada:** un botón "Aprobar y marcar como listo para enviar" dentro
  de la UI dice explícitamente que es una simulación — el envío real llega con Gmail
  (Fase 5+). La UI nunca envía nada por su cuenta, coherente con el resto del sistema.

**Nota de diseño encontrada durante las pruebas:** los widgets de la ficha nueva NO
están dentro de un `st.form`. Se probó así primero, pero Streamlit no vuelve a
ejecutar el script dentro de un formulario hasta que se pulsa "enviar" — así que un
checkbox como "¿tiene lesión?" nunca llegaba a revelar el campo de "zona de la
lesión" a tiempo. Con widgets sueltos (cada uno con `key` propia), cada interacción
reejecuta el script y la UI puede reaccionar de inmediato. El coste es una rerenderización
algo más frecuente, irrelevante para un pipeline tan rápido como el de reglas.

## Componentes

| Componente | Archivo | Fase | Estado |
|---|---|---|---|
| Ficha de admisión | `admission/ficha_cliente_template.md` | 1 | **Hecho** |
| Base de conocimiento | `docs/base_conocimiento/` | 0 | **Hecho** |
| Helper de lectura de conocimiento | `agents/knowledge.py` | 2 | **Hecho** |
| Banco de ejercicios | `agents/exercise_bank.py` | 2 | **Hecho** |
| Motor de reglas — rutina | `agents/rutina_reglas.py` | 2 | **Hecho** |
| Agente de rutina (dual motor) | `agents/routine_agent.py` | 2 | **Hecho** |
| Banco de alimentos | `agents/food_bank.py` | 3 | **Hecho** |
| Motor de reglas — dieta | `agents/dieta_reglas.py` | 3 | **Hecho** |
| Agente de dieta (dual motor) | `agents/diet_agent.py` | 3 | **Hecho** |
| Agente validador | `agents/validator_agent.py` | 3 | **Hecho** |
| Orquestador (estado explícito) | `agents/orchestrator.py` | 4 | **Hecho** |
| Panel del entrenador (UI) | `ui/app.py` | 5-lite | **Hecho** |
| Parser de analítica | `agents/analytics_parser.py` | 5+ | Pendiente |
| Conector Notion | `mcp/notion_client.py` | 5 | Pendiente |
| Conector Gmail | `mcp/gmail_client.py` | 5 | Pendiente |
| Disparo automático | `main.py` + `inbox/` | 6 | Pendiente |

## Capa de personalización clínica (modulación activa)

La admisión captura datos de salud (alergias, enfermedades, embarazo/lactancia,
medicación, peso) y admite una **analítica en PDF**. Hoy el motor de reglas ya
modula activamente la dieta a partir de lo que sabe del perfil (tipo de dieta,
alergias/intolerancias, objetivo → calorías/macros) y aplica sinergias de absorción
cuando el tipo de dieta lo justifica (p.ej. hierro + vitamina C en dietas
vegetarianas/veganas). Un futuro `analytics_parser` extraerá marcadores de la
analítica (glucosa/HbA1c, lípidos, ferritina, vitamina D, TSH...) para modular
también sobre esos datos.

Modular activamente no relaja la regla dura: el sistema **no diagnostica ni
prescribe**; cualquier marcador fuera de rango, patología, embarazo, medicación,
lesión o alergia **fuerza `revisión_reforzada`** — ver `docs/metodo_entrenador.md` §7
y `agents/validator_agent.py`.

## Principio transversal: humano en el bucle

Ningún plan llega al cliente sin aprobación humana. El sistema está diseñado para
**asistir** al entrenador, no para reemplazarlo. La generación siempre produce un
**borrador**, y cualquier señal de riesgo (lesión, patología, alergia, marcador
clínico) fuerza una **revisión reforzada**.
