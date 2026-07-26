# Base de conocimiento — Índice y fuentes

Esta carpeta contiene la **ciencia destilada** que consultarán los agentes (rutina,
dieta, validador). Es la "memoria" del sistema: notas breves, estructuradas y
publicables, derivadas del material fuente del entrenador.

## Cómo se usa
- El **método** (`docs/metodo_entrenador.md`) define el *criterio* del entrenador
  (filosofía, reglas, tono). Es el nivel "system prompt".
- Esta **base de conocimiento** aporta el *detalle técnico* consultable (números,
  combinaciones, protocolos). Es el nivel "RAG / referencia".
- En la Fase 5 podrá migrarse a Notion sin cambiar esta estructura lógica.

## Notas de conocimiento
| Archivo | Tema | Fuente original |
|---|---|---|
| [entrenamiento.md](entrenamiento.md) | Hipertrofia, progresión, splits, cardio | `Hipertrofia.pdf`, rutina bulking/cutting |
| [nutricion.md](nutricion.md) | Calorías, macros, proteína, dieta flexible, longevidad | `CreatinayProte.pdf`, `Dieta_Bloques_Alimentos_Longevidad.pdf` |
| [suplementacion.md](suplementacion.md) | Creatina, tipos de proteína | `CreatinayProte.pdf` |
| [sinergias_nutrientes.md](sinergias_nutrientes.md) | Absorción, sinergias e interferencias | `Sinergias_Absorcion_Nutrientes.pdf` |
| [estilo_vida_longevidad.md](estilo_vida_longevidad.md) | Sueño, pasos, zona 2, hábitos | `Routine_Healthy.pdf`, `Routine_Anti_Aging.pdf` |

## Material fuente (local, NO versionado — `AA_files_Training/`)
Se mantiene fuera del control de versiones por contener material personal del
entrenador. Pendiente de destilar en fases posteriores si aportan al método:

- `AlimentosClave.pdf`, `Superalimentos.pdf`, `Microutrientes y Minerales.pdf`
- `HormonasFelicidad.pdf`, `AdenosinayGlutamato.pdf` (neuroquímica/bienestar)
- `Alcohol.pdf`, `Ozempic.pdf` (educación / mitos)
- `Routine_Anti_Aging.pdf`, `RutinaPrincipiante.pdf` / `Routine_Rookie.pdf`

> **Nota de rigor:** las cifras aquí recogidas provienen del material del entrenador.
> Antes de fijarlas como definitivas conviene contrastarlas con fuentes científicas
> actualizadas (metaanálisis, posicionamientos ISSN/ACSM). Ver `docs/decisiones.md`.
