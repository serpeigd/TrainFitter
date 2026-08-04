# Knowledge Base — Index and Sources

This folder holds the **distilled science** that the agents (routine, diet,
validator) consult. It's the system's "memory": short, structured, publishable
notes derived from the trainer's source material.

## How it's used
- The **method** (`docs/metodo_entrenador.md`) defines the trainer's *judgment*
  (philosophy, rules, tone). This is the "system prompt" level.
- This **knowledge base** provides the consultable *technical detail* (numbers,
  combinations, protocols). This is the "RAG / reference" level.
- In Phase 5 it could migrate to Notion without changing this logical structure.

## Knowledge notes
| File | Topic | Source |
|---|---|---|
| [entrenamiento.md](entrenamiento.md) | Hypertrophy, progression, splits, cardio, volume (MEV/MAV/MRV) | `Hipertrofia.pdf` + RP Strength / ISSN (verified Jul 2026) |
| [nutricion.md](nutricion.md) | Calories, macros, protein, fiber, fat-loss rate, longevity | `CreatinayProte.pdf`, `Dieta_Bloques_Alimentos_Longevidad.pdf` + Morton 2018 / ISSN / USDA (verified Jul 2026) |
| [suplementacion.md](suplementacion.md) | Creatine, protein, caffeine, beta-alanine | `CreatinayProte.pdf` + ISSN / NIH ODS (verified Jul 2026) |
| [sinergias_nutrientes.md](sinergias_nutrientes.md) | Absorption, synergies, and interference | `Sinergias_Absorcion_Nutrientes.pdf` |
| [estilo_vida_longevidad.md](estilo_vida_longevidad.md) | Sleep, steps, Zone 2, habits | `Routine_Healthy.pdf`, `Routine_Anti_Aging.pdf` + Sleep Foundation (verified Jul 2026) |
| [seguridad_poblaciones_especiales.md](seguridad_poblaciones_especiales.md) | Pregnancy (ACOG), red flags (ACSM), knee/ACL rehab | New research (verified Jul 2026) — backs `validator_agent.py` |
| [adherencia_y_cambio_de_conducta.md](adherencia_y_cambio_de_conducta.md) | Self-monitoring + human follow-up, tracking frequency, habit formation | New research (verified Aug 2026) — backs the method's #1 priority and `agents/adherencia_parser.py`/`agents/pdf_generador.py` |

## Source material (local, NOT version-controlled — `AA_files_Training/`)
Kept out of version control because it contains the trainer's personal material.
Still pending distillation in later phases if useful to the method:

- `AlimentosClave.pdf`, `Superalimentos.pdf`, `Microutrientes y Minerales.pdf`
- `HormonasFelicidad.pdf`, `AdenosinayGlutamato.pdf` (neurochemistry/wellbeing)
- `Alcohol.pdf`, `Ozempic.pdf` (education / myth-busting)
- `Routine_Anti_Aging.pdf`, `RutinaPrincipiante.pdf` / `Routine_Rookie.pdf`

## On the rigor of the sources

Every note that incorporates outside research ends with a **"Sources consulted"**
section with verifiable links (meta-analyses, ISSN/ACSM/ACOG position stands,
official USDA guidelines). This doesn't contradict the Phase 0c decision against
"freezing" citations as eternal law: that decision was about not depending *solely*
on static notes forever. Citing the source of a specific figure while actually doing
the research is good practice, and it doesn't stop the LLM engine from later
cross-checking against more recent evidence at generation time — see
`docs/decisiones.md`.
