---
name: actualizar-base-conocimiento
description: Investiga un tema de entrenamiento/nutrición/salud con fuentes verificables (metaanálisis, posicionamientos ISSN/ACSM/ACOG, guías oficiales) y lo integra en docs/base_conocimiento/ de TrainFitter siguiendo el formato y el rigor ya establecidos. Úsala cuando el entrenador pida "amplía la base de conocimiento", "busca evidencia sobre X" o "añade una nota nueva sobre Y".
---

# Actualizar la base de conocimiento de TrainFitter

Esta skill codifica el proceso ya usado para investigar y ampliar
`docs/base_conocimiento/` con evidencia real, para que sea repetible sin tener que
redescubrir las convenciones del proyecto cada vez.

## Cuándo usarla
- El entrenador pide investigar un tema nuevo (p. ej. "añade info sobre entrenamiento
  en ayunas", "qué dice la evidencia sobre el sueño y la hipertrofia").
- Aparece un PDF nuevo en `AA_files_Training/` que conviene destilar.
- Toca revisar si algo de la KB ha quedado desactualizado.

## Proceso

1. **Busca con fuentes primarias/verificables, no blogs genéricos.** Prioriza en este
   orden: posicionamientos de sociedades científicas (ISSN, ACSM, ACOG, OMS/WHO,
   USDA/dietary guidelines), meta-análisis y revisiones sistemáticas (PubMed/PMC),
   y solo después divulgación de referentes reconocidos (Renaissance Periodization,
   Stronger by Science, Jeff Nippard) — y siempre como *resumen de consenso*, nunca
   citando textualmente algo que no se ha verificado palabra por palabra.
2. **No inventes cifras ni cites algo que no hayas leído de verdad en el resultado de
   la búsqueda.** Si la evidencia es mixta o débil, dilo explícitamente en la nota en
   vez de presentar un número falso con seguridad.
3. **Decide si la nota es una ampliación de una existente o una nota nueva.** Las notas
   actuales son: `entrenamiento.md`, `nutricion.md`, `suplementacion.md`,
   `sinergias_nutrientes.md`, `estilo_vida_longevidad.md`,
   `seguridad_poblaciones_especiales.md`. Si el tema encaja en alguna, amplíala allí en
   vez de fragmentar el conocimiento en archivos pequeños.
4. **Formato de cada nota:**
   - Encabezados cortos, frases directas, cifras concretas con su rango (no solo "algo de proteína").
   - Al final de la nota, sección `## Fuentes consultadas (verificadas, <mes año>)` con
     enlaces reales en formato `[Título](URL)`.
   - Si la cifra sustituye a una anterior derivada del material del entrenador (Fase 0b),
     no la borres sin más: indica que se refina/contrasta con la nueva fuente.
5. **Actualiza `docs/base_conocimiento/00_indice_fuentes.md`** (tabla de notas) si es
   una nota nueva o si cambia significativamente la fuente de una existente.
6. **Si la cifra alimenta directamente el motor de reglas** (`agents/rutina_reglas.py`,
   `agents/dieta_reglas.py`, `agents/exercise_bank.py`, `agents/food_bank.py`), actualiza
   también la constante correspondiente en el código, con un comentario que referencie
   la nota de la KB — no dejes que el código y la documentación diverjan.
7. **Registra la investigación en `docs/decisiones.md`**: qué se buscó, qué cambió y
   por qué, siguiendo el estilo de entradas ya existente (rule/fact + Por qué + Cómo
   se aplica).
8. **Verifica que el pipeline sigue funcionando** tras el cambio:
   ```bash
   python -m py_compile agents/*.py
   python agents/run_pipeline_demo.py
   ```

## Recordatorio de límites del proyecto
Esta KB alimenta un sistema que genera **borradores**, no consejo clínico. Ninguna
cifra o guía que añadas aquí debe presentarse como sustituto del criterio de un
profesional titulado — si el tema toca patologías, embarazo o medicación, la nota
debe reforzar que eso siempre dispara `revisión_reforzada`, nunca dar una receta.
