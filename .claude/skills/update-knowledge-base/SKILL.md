---
name: update-knowledge-base
description: Research a training/nutrition/health topic with verifiable sources (meta-analyses, ISSN/ACSM/ACOG position stands, official guidelines) and integrate it into TrainFitter's docs/base_conocimiento/, following the format and rigor already established. Use it when the trainer asks to "expand the knowledge base," "look up evidence on X," or "add a new note about Y."
---

# Updating TrainFitter's knowledge base

This skill codifies the process already used to research and expand
`docs/base_conocimiento/` with real evidence, so it's repeatable without having to
rediscover the project's conventions every time.

## When to use it
- The trainer asks to research a new topic (e.g. "add info on fasted training,"
  "what does the evidence say about sleep and hypertrophy").
- A new PDF shows up in `AA_files_Training/` that's worth distilling.
- It's time to check whether something in the KB has gone stale.

## Process

1. **Search with primary, verifiable sources, not generic blogs.** Prioritize, in
   this order: position stands from scientific societies (ISSN, ACSM, ACOG, WHO,
   USDA dietary guidelines), meta-analyses and systematic reviews (PubMed/PMC), and
   only after that, communication from recognized figures (Renaissance Periodization,
   Stronger by Science, Jeff Nippard) — and always as a *consensus summary*, never
   quoting something word-for-word that hasn't actually been verified.
2. **Don't invent numbers or cite something you haven't actually read in the search
   results.** If the evidence is mixed or weak, say so explicitly in the note instead
   of presenting a made-up figure with false confidence.
3. **Decide whether it's an expansion of an existing note or a new one.** The current
   notes are: `entrenamiento.md`, `nutricion.md`, `suplementacion.md`,
   `sinergias_nutrientes.md`, `estilo_vida_longevidad.md`,
   `seguridad_poblaciones_especiales.md`. If the topic fits one of these, expand it
   there instead of fragmenting the knowledge across small files.
4. **Format for each note:**
   - Short headings, direct sentences, concrete figures with their range (not just
     "some protein").
   - At the end of the note, a `## Sources consulted (verified, <month year>)`
     section with real links formatted as `[Title](URL)`.
   - If a figure replaces an older one derived from the trainer's own material
     (Phase 0b), don't just delete it — note that it's being refined/cross-checked
     against the new source.
5. **Update `docs/base_conocimiento/00_indice_fuentes.md`** (the notes table) if it's
   a new note or if an existing note's source changes significantly.
6. **If the figure directly feeds the rule engine** (`agents/rutina_reglas.py`,
   `agents/dieta_reglas.py`, `agents/exercise_bank.py`, `agents/food_bank.py`), also
   update the corresponding constant in the code, with a comment referencing the KB
   note — don't let the code and the documentation drift apart.
7. **Log the research in `docs/decisiones.md`**: what was researched, what changed,
   and why, following the existing entry style (rule/fact + Why + How it's applied).
8. **Verify the pipeline still works** after the change:
   ```bash
   python -m py_compile agents/*.py
   python agents/run_pipeline_demo.py
   ```

## Reminder of the project's boundaries
This KB feeds a system that generates **drafts**, not clinical advice. No figure or
guideline you add here should be presented as a substitute for a licensed
professional's judgment — if the topic touches on conditions, pregnancy, or
medication, the note should reinforce that this always triggers
`revisión_reforzada`, never hand out a prescription.
