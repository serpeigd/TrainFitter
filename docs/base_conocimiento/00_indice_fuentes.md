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
| Archivo | Tema | Fuente |
|---|---|---|
| [entrenamiento.md](entrenamiento.md) | Hipertrofia, progresión, splits, cardio, volumen (MEV/MAV/MRV) | `Hipertrofia.pdf` + RP Strength / ISSN (verificado jul. 2026) |
| [nutricion.md](nutricion.md) | Calorías, macros, proteína, fibra, ritmo de pérdida de grasa, longevidad | `CreatinayProte.pdf`, `Dieta_Bloques_Alimentos_Longevidad.pdf` + Morton 2018 / ISSN / USDA (verificado jul. 2026) |
| [suplementacion.md](suplementacion.md) | Creatina, proteína, cafeína, beta-alanina | `CreatinayProte.pdf` + ISSN / NIH ODS (verificado jul. 2026) |
| [sinergias_nutrientes.md](sinergias_nutrientes.md) | Absorción, sinergias e interferencias | `Sinergias_Absorcion_Nutrientes.pdf` |
| [estilo_vida_longevidad.md](estilo_vida_longevidad.md) | Sueño, pasos, zona 2, hábitos | `Routine_Healthy.pdf`, `Routine_Anti_Aging.pdf` + Sleep Foundation (verificado jul. 2026) |
| [seguridad_poblaciones_especiales.md](seguridad_poblaciones_especiales.md) | Embarazo (ACOG), señales de alarma (ACSM), rehab de rodilla/LCA | Investigación nueva (verificado jul. 2026) — respalda `validator_agent.py` |

## Material fuente (local, NO versionado — `AA_files_Training/`)
Se mantiene fuera del control de versiones por contener material personal del
entrenador. Pendiente de destilar en fases posteriores si aportan al método:

- `AlimentosClave.pdf`, `Superalimentos.pdf`, `Microutrientes y Minerales.pdf`
- `HormonasFelicidad.pdf`, `AdenosinayGlutamato.pdf` (neuroquímica/bienestar)
- `Alcohol.pdf`, `Ozempic.pdf` (educación / mitos)
- `Routine_Anti_Aging.pdf`, `RutinaPrincipiante.pdf` / `Routine_Rookie.pdf`

## Sobre el rigor de las fuentes

Cada nota que incorpora investigación externa termina con una sección **"Fuentes
consultadas"** con enlaces verificables (metaanálisis, posicionamientos ISSN/ACSM/
ACOG, guías oficiales USDA). Esto no contradice la decisión de la Fase 0c de no
"congelar" citas como ley eterna: esa decisión hablaba de no depender *solo* de notas
estáticas para siempre. Citar la fuente de una cifra concreta cuando se investiga es
buena práctica y no impide que, más adelante, el motor LLM siga contrastando con
evidencia más reciente en tiempo de generación — ver `docs/decisiones.md`.
