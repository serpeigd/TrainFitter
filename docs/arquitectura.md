# Arquitectura de TrainFitter

> **Estado: esqueleto (Fase 0).** Este documento se irá rellenando fase a fase.
> El diagrama de estados "real" se añadirá en la Fase 4 (orquestador) y la versión
> final orientada a lector técnico en la Fase 7.

---

## Visión general

TrainFitter es un pipeline de **agentes de IA** que transforma la ficha de un cliente
en borradores de rutina y dieta, con una **revisión humana obligatoria** antes de
cualquier envío. Cada agente tiene una responsabilidad única y acotada.

## Flujo previsto

```
   ┌──────────────────┐        ┌───────────────────────────┐
   │  Ficha cliente   │        │  Analítica (PDF) opcional │
   │  (admission/)    │        │  → extracción de marcadores│
   └────────┬─────────┘        └────────────┬──────────────┘
            │                               │
            └──────────────┬────────────────┘
                           ▼
              ┌────────────────────────┐
              │  Perfil clínico unificado│  (objetivo + salud + marcadores)
              └────────────┬───────────┘
                           │   ┌───────────────────────────────┐
                           │   │  Base de conocimiento          │
                           │◄──┤  docs/base_conocimiento/*      │
                           │   │  (entrenamiento, nutrición,    │
                           │   │   suplementación, sinergias…)  │
                           ▼   └───────────────────────────────┘
   ┌──────────────────┐
   │  Agente Rutina   │   Redacta borrador de rutina según el método (docs/metodo_*)
   │ routine_agent.py │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │  Agente Dieta    │   Redacta borrador de dieta flexible según el método
   │  diet_agent.py   │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ Agente Validador │   Comprueba coherencia con el método + señales de riesgo
   │ validator_agent  │   (lesiones, restricciones). Emite veredicto.
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │   Orquestador    │   Coordina el pipeline con estado explícito y logging
   │  orchestrator.py │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────────────────┐
   │      Revisión humana         │   El entrenador revisa y APRUEBA el borrador
   │  (siempre, sin excepción)    │
   └────────┬─────────────────────┘
            │
            ▼
   ┌──────────────────┐
   │  Envío al cliente│   Solo tras aprobación (borrador en Gmail — Fase 5)
   └──────────────────┘
```

## Componentes (se detallan en fases posteriores)

| Componente          | Archivo                     | Fase | Estado   |
|---------------------|-----------------------------|------|----------|
| Ficha de admisión   | `admission/`                | 1    | Pendiente |
| Base de conocimiento| `docs/base_conocimiento/`   | 0    | **Hecho** |
| Parser de analítica | `agents/analytics_parser.py`| 3+   | Pendiente |
| Agente de rutina    | `agents/routine_agent.py`   | 2    | **Hecho** |
| Agente de dieta     | `agents/diet_agent.py`      | 3    | Pendiente |
| Agente validador    | `agents/validator_agent.py` | 3    | Pendiente |
| Orquestador         | `agents/orchestrator.py`    | 4    | Pendiente |
| Conector Notion     | `mcp/notion_client.py`      | 5    | Pendiente |
| Conector Gmail      | `mcp/gmail_client.py`       | 5    | Pendiente |
| Disparo automático  | `main.py` + `inbox/`        | 6    | Pendiente |

## Capa de personalización clínica (modulación activa)

La admisión captura datos de salud (alergias, enfermedades, embarazo/lactancia,
medicación, peso) y admite una **analítica en PDF**. Un futuro `analytics_parser`
extraerá marcadores (glucosa/HbA1c, lípidos, ferritina, vitamina D, TSH, función
hepática/renal) que **modulan activamente** rutina, dieta y suplementación — el
objetivo es que todo el plan salga cuadrado con el perfil completo de la persona,
maximizando sinergias y potenciando beneficios, no solo evitando riesgos.

Modular activamente no relaja la regla dura: el sistema **no diagnostica ni
prescribe**; cualquier marcador fuera de rango, patología, embarazo, medicación o
lesión **fuerza `revisión_reforzada`** — el borrador ya modulado espera aprobación del
entrenador (y derivación médica cuando proceda) antes de cualquier envío.
Ver `docs/metodo_entrenador.md` §7.

## Agente de rutina (Fase 2)

`agents/routine_agent.py` recibe el perfil del cliente y llama al modelo con **salida
forzada por tool use** (no texto libre parseado): el modelo debe rellenar el esquema
`entregar_borrador_rutina`, lo que da un JSON estructurado fiable en vez de tener que
parsear Markdown. El system prompt inyecta el método completo
(`docs/metodo_entrenador.md`) más las notas técnicas de `entrenamiento.md` y
`estilo_vida_longevidad.md`. Si el perfil trae lesiones u otras señales de salud, el
propio agente ya adapta ejercicios y rellena `advertencias_revision_humana` — esta es
una primera capa de seguridad; la comprobación exhaustiva y el veredicto formal llegan
con el **agente validador** (Fase 3). Modelo usado: `claude-sonnet-5` (ver
`docs/decisiones.md`, Fase 2, para la justificación).

## Principio transversal: humano en el bucle

Ningún plan llega al cliente sin aprobación humana. El sistema está diseñado para
**asistir** al entrenador, no para reemplazarlo. La generación por IA siempre produce
un **borrador**, y cualquier señal de riesgo (lesión, patología, marcador clínico)
fuerza una **revisión reforzada**.
