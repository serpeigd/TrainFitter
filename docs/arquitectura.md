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
   ┌──────────────────┐
   │  Ficha cliente   │   (JSON estructurado desde el formulario de admisión)
   │  (admission/)    │
   └────────┬─────────┘
            │
            ▼
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
| Agente de rutina    | `agents/routine_agent.py`   | 2    | Pendiente |
| Agente de dieta     | `agents/diet_agent.py`      | 3    | Pendiente |
| Agente validador    | `agents/validator_agent.py` | 3    | Pendiente |
| Orquestador         | `agents/orchestrator.py`    | 4    | Pendiente |
| Conector Notion     | `mcp/notion_client.py`      | 5    | Pendiente |
| Conector Gmail      | `mcp/gmail_client.py`       | 5    | Pendiente |
| Disparo automático  | `main.py` + `inbox/`        | 6    | Pendiente |

## Principio transversal: humano en el bucle

Ningún plan llega al cliente sin aprobación humana. El sistema está diseñado para
**asistir** al entrenador, no para reemplazarlo. La generación por IA siempre produce
un **borrador**, y cualquier señal de riesgo (lesión, patología) fuerza una **revisión
reforzada**.
