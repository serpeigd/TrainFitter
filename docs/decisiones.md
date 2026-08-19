# Technical Decision Log

> Chronological record of TrainFitter's design decisions, phase by phase.
> Useful for picking the project back up and for explaining it (interviews,
> technical stakeholders).

---

## Phase 0 — Scaffold + trainer's method

**Main decision.** Project in **plain Python + the Anthropic SDK**, no low-code.

**Why.** The goal is learning: understanding agents, orchestration, and MCP at a
**low level**. A low-code tool (n8n, Make, etc.) would hide exactly what's meant to
be learned. Python + the official SDK gives full control over prompts, state, and
error handling, and produces readable code that can be explained in an interview.

**Other decisions from this phase:**

- **`docs/` instead of `files/`.** The original brief's diagram named `files/`, but
  every task and every later phase references `docs/`. `docs/` is used to avoid
  broken paths and because it's the conventional name.
- **Repo root = `TrainFitter/`.** The brief named `piloto-de-planes/` as the root,
  but work was already happening inside a `TrainFitter/` folder. Nesting would be
  redundant; `TrainFitter/` is used as the root.
- **Documentation separated from code.** The trainer's method lives in a readable
  `.md` file (`docs/metodo_entrenador.md`) that will act as a knowledge base the
  agents can query. In Phase 5 it could be read from Notion instead of a local file.
- **Priority: clarity and instructive comments** over premature optimization, since
  this is a portfolio/learning project.
- **Human in the loop from the design stage.** Human review and approval before
  sending is an architectural requirement, not something bolted on later.

**Pending / to revisit in later phases:**

- Confirm the exact Anthropic model string to use (Phase 2).
- Decide the draft output format: Markdown vs JSON (Phase 2).

---

## Phase 0b — Bringing in the trainer's real material + the clinical layer

After the scaffold, the trainer contributed their own material in
`AA_files_Training/` (their real routine, PDFs on hypertrophy, nutrition,
creatine/protein, absorption synergies, longevity, lifestyle habits). Decisions made:

- **Distilled knowledge base (`docs/base_conocimiento/`).** Separates the *judgment*
  layer (the method, "system prompt" level) from the *consultable technical detail*
  (the "RAG" level). Five notes: training, nutrition, supplementation, nutrient
  synergies, and lifestyle/longevity, plus an index/manifest mapping each topic to
  its source PDF. This logical structure could migrate to Notion in Phase 5 without
  changes.
- **Method enriched with real content** (protein numbers 0.8/1.6-2.4/1.2-2.2,
  creatine 3-5 g, sarcoplasmic vs. myofibrillar hypertrophy, Zone 2 / Zone 4-5
  cardio, absorption synergies). New pillars: **supplementation** and
  **lifestyle/longevity**. The document grew past the initial 600-900-word target as
  the scope expanded; that trade-off is accepted in favor of accurately reflecting
  the method.
- **Clinical personalization layer (new).** Intake will capture allergies,
  conditions, pregnancy/breastfeeding, medication, weight/height/age, and injuries;
  it will also allow a **PDF bloodwork report** to be attached that *modulates*
  non-clinical recommendations (future `agents/analytics_parser.py`). Reinforced
  hard rule: the system **never diagnoses or prescribes**; any out-of-range marker /
  condition / pregnancy / medication / injury forces `revisión_reforzada`. Documented
  in the method §7-§8 and in the architecture doc.
- **Privacy (an important decision).** `AA_files_Training/` contains the trainer's
  personal material (their own weights, vlog scripts). It's added to `.gitignore`
  and **never pushed** to the public repo; only the distilled (non-personal) science
  is version-controlled in `docs/base_conocimiento/`. Reversible if the trainer
  prefers to include it.

**Pending / to revisit:**

- Cross-check the material's figures against updated scientific sources
  (ISSN/ACSM, meta-analyses) using web search in later phases, and cite sources in
  the KB.
- Define bloodwork reference ranges and the marker → dietary signal mapping
  (Phase 3, alongside the diet agent and the validator).
- Distill the remaining pending PDFs (key foods, micronutrients, hormones, etc.) if
  they add to the method.

---

## Phase 0c — Trainer's clarifications: evolving judgment, dynamic science, active modulation

Three answers from the trainer to the open questions from Phase 0b, with design
impact:

- **The method is a starting point, not a fixed law.** The numeric values (reps,
  g/kg, dosages) are reasonable defaults the trainer adjusts case by case. Added as
  `docs/metodo_entrenador.md` §0, making it explicit for the agents.
  - **Why:** every client is different (genetics, individual response), and the
    trainer doesn't want the system to treat their figures as rigid rules.
  - **Future implication (out of scope for now):** as the trainer reviews and edits
    AI-generated drafts, those edits are **real training data** ("AI draft →
    trainer's correction"). With enough volume, the system's judgment could be
    tuned toward theirs specifically. Not implemented yet; noted as a future
    direction (possible Phase 8+: logging edits + learning preferences).
- **No static scientific citations fixed in the KB.** The trainer prefers the
  system to stay current with the latest evidence rather than "freezing"
  references in `docs/base_conocimiento/`.
  - **Why:** a static note with citations ages; nutrition/sports science keeps
    updating.
  - **How to apply:** in the agent phases (2+), evaluate giving `routine_agent`/
    `diet_agent` web search access to cross-check against recent evidence at
    generation time, instead of relying only on the static KB. The KB remains the
    base for the trainer's *judgment and style*, not the scientific source of
    truth.
- **Clinical modulation must be ACTIVE, not just risk detection.** End goal:
  routine + diet + supplementation + habits all line up together based on the full
  profile (bloodwork, conditions, allergies, genetics, context), maximizing
  nutritional synergies and boosting benefits — not just flagging what's
  dangerous.
  - **Why:** it's the product goal the trainer stated explicitly; "maximum
    personalization" is TrainFitter's core value versus a generic template.
  - **How to apply:** `docs/metodo_entrenador.md` §7 updated with examples of
    active modulation (low ferritin → iron+vitamin C; low vit. D → timing with
    fat; high lipids → adjusting fat/fiber profile). **The safety rule doesn't
    change**: modulating actively isn't diagnosing or prescribing — the modulated
    draft still triggers `revisión_reforzada` on any clinical signal, and still
    waits for human approval before being sent. The `analytics_parser`'s technical
    design and the marker→adjustment mapping are addressed in Phase 3.

**How the repo is worked (clarified at the trainer's request).** Git is the
backbone for code and version control throughout the whole project, including
Phases 0-4 (100% local development, no external dependencies). Notion only enters
in **Phase 5**, as a live source for the method (instead of reading
`docs/metodo_entrenador.md` as a local file) and as a status database for
clients/pipelines — but **it doesn't replace git**: the code, the agents, and the
decision history keep living and being version-controlled here.

---

## Phase 1 — Client intake form + example clients

- **`admission/ficha_cliente_template.md`** written as a form 100% aimed at the end
  client: plain language, no jargon, with an explanation of why each piece of
  health data is asked for (to personalize and take care of them, never to "close
  doors"). Includes the clinical questions defined in Phase 0b/0c (injuries,
  conditions, pregnancy/breastfeeding, medication, optional bloodwork) woven in
  naturally, not as a cold medical questionnaire.
- **Client JSON schema** (used by both examples and consumed by the agents):
  `datos_basicos`, `objetivo`, `experiencia`, `disponibilidad`, `salud` (with
  `lesiones`, `enfermedades_o_condiciones`, `embarazo_o_lactancia`,
  `medicacion_habitual`, allergies/intolerances, `analitica_adjunta` as a
  placeholder for Phase 3+), `nutricion`, and `estilo_de_vida`. Added
  `en_sus_palabras` / `detalle` / `contexto` as free-text fields across several
  sections: the method prioritizes understanding the person, not just filling in
  boxes.
- **`cliente_ejemplo_1.json` (normal case):** intermediate experience, 4 days/week,
  full gym, no injuries or conditions, omnivorous diet with no complex
  restrictions. Serves as the base case to validate that the pipeline produces a
  good draft without triggering any alert.
- **`cliente_ejemplo_2.json` (complex case, to test the validator):** combines an
  **old knee injury** (ACL, controlled but with discomfort on deep squats — should
  trigger `revisión_reforzada` and exclude/adapt that movement pattern) with
  **vegetarianism** (relevant to the diet agent and protein/iron absorption
  synergies) and a mild lactose intolerance. Also deliberately added a note about
  "frequent fatigue" with no bloodwork attached, as a narrative hook for when the
  bloodwork modulator gets built (Phase 3+): today the system has no way to
  interpret it, so it has to stay as free text without inventing a diagnosis.
- **`analitica_adjunta`** is modeled in the schema but **not actually used yet**
  (`tiene: false` in both examples): building the real parser is Phase 3+ work, not
  Phase 1.

---

## Phase 2 — Routine agent

- **Model: `claude-sonnet-5`.** Opus was ruled out (more expensive/deeper reasoning
  than "writing a routine following an already-documented method" needs) and so was
  Haiku (personalization quality is prioritized — a professional reviews the
  result, but it should arrive already well thought out, not generic). Sonnet 5 is
  the right middle ground for this agent; will be re-evaluated per agent if a
  specific case justifies it.
- **Structured output via *tool use*, not free-form Markdown.** The model is forced
  to respond by filling a fixed schema (`entregar_borrador_rutina`) instead of
  being asked for JSON in text and having it parsed. Reason: the validator (Phase
  3) needs to walk the exercises in code to cross-check them against the client's
  injuries, and the orchestrator (Phase 4) needs programmatic state. Converting
  JSON → nice Markdown/HTML for the email (Phase 5/6) is trivial; parsing prose
  back into structure is not. Saved as `.json`, not `.md`.
- **What part of the knowledge base the agent receives.** Besides the full method,
  it's given the `entrenamiento.md` and `estilo_vida_longevidad.md` notes
  (relevant to designing a routine). Nutrition/supplementation notes are left for
  the diet agent (Phase 3) — each agent gets only what it needs, not the whole KB
  at once.
- **Two layers of safety.** `routine_agent` itself already adapts exercises when
  injuries/conditions are mentioned in the profile and fills in
  `advertencias_revision_humana` — but this is a first pass, not the formal
  control. The exhaustive check and the verdict (`aprobado_automático` /
  `revisión_reforzada`) is the **validator agent**'s responsibility (Phase 3), not
  yet built.
- **Error handling:** its own `RoutineAgentError` class; explicitly distinguishes a
  missing API key (message pointing to `.env.example`), timeout, connection error,
  API error, and a response with no `tool_use` block (malformed response).
- **New `agents/knowledge.py`:** a shared helper for reading
  `docs/metodo_entrenador.md` and notes from `docs/base_conocimiento/` by name.
  `diet_agent` and `validator_agent` will reuse it in Phase 3 to avoid duplicating
  file-reading logic.
- **The demo wasn't run in this session** (no `ANTHROPIC_API_KEY` configured in
  this environment). Only verified that the code compiles (`py_compile`) with no
  syntax errors. Pending: the trainer runs `python agents/run_routine_demo.py`
  with their own key and confirms the generated draft makes sense before Phase 2
  is signed off.

---

## Pivot — Free rule engine by default (before moving on to Phase 3)

The trainer explicitly asked to set aside the API-key requirement and have a
**fully functional free version**. This changes the pipeline's underlying design,
not just Phase 2:

- **Each generator agent (`routine_agent`, `diet_agent`) exposes a `motor`
  parameter: `"reglas"` (default) or `"llm"` (optional).** Both return exactly the
  same output schema, so the validator and the orchestrator are agnostic to which
  one was used — no need to touch them when adding the rule engine.
  - **Why the LLM engine isn't dropped:** the project's goal is still learning to
    build agents with the Anthropic SDK. Phase 2's tool-use code is kept intact
    (renamed to a private `_generar_borrador_*_llm` function) and stays ready to
    switch on the day there's an API key, with no redesign needed.
  - **Lazy import of `anthropic`:** `import anthropic` moves from module level to
    inside the `_llm` function, so anyone only using `motor="reglas"` doesn't even
    need the package installed. The default pipeline is **100% standard Python,
    zero third-party dependencies**.
- **Routine rule engine (`agents/exercise_bank.py` + `agents/rutina_reglas.py`):**
  a bank of ~40 real exercises (inspired by the trainer's own routine from Phase
  0b) tagged by muscle group, required equipment, and contraindications
  (knee/shoulder/lower-back). The engine picks a split based on days/week
  (full body ≤3, upper/lower =4, push/pull/legs ≥5), selects exercises the client
  can do with their equipment, applies the method's ranges (compound 5-8,
  isolation 10-15), and **excludes/substitutes exercises contraindicated by
  declared injuries**, leaving the reason in `advertencias_revision_humana`.
- **Injury detection from free text (`agents/perfil_utils.py`):** a
  `tags_lesiones()` function that looks for keywords (knee/shoulder/lower-back) in
  the intake's `zona` + `descripcion`. A deliberate simplification (substring
  matching, not real NLP), documented as a known limitation — sufficient for the
  MVP and so the validator can independently re-derive it.
- **Verified with a real run** (no longer blocked on waiting for the trainer to set
  up a key): `python agents/run_routine_demo.py` on both example clients confirms
  that `cliente_002`'s knee injury excludes "Barbell squat" and replaces it with
  "Leg press" / "Leg curl" / "Glute bridge," with an explanatory note on each
  adapted exercise.

---

## Phase 3 — Diet agent + validator agent

- **Diet rule engine (`agents/food_bank.py` + `agents/dieta_reglas.py`):** calories
  via Mifflin-St Jeor (BMR) × an activity factor derived from training days/week
  and daily steps, with a goal-based adjustment (hypertrophy +10%, recomposition
  -5%, fat loss -18%, general health 0%) — all taken from
  `docs/base_conocimiento/nutricion.md`. Protein by goal using the midpoint of the
  method's range (e.g. hypertrophy → 2.0 g/kg). Food bank filtered by diet type
  (omnivorous/vegetarian/vegan) and by declared allergies/intolerances (excludes
  dairy, gluten, tree nuts, egg, soy, fish as appropriate). Adds tips from
  `sinergias_nutrientes.md` when the profile calls for them (iron + vitamin C and
  separating coffee/tea from iron in vegetarian/vegan diets).
- **`agents/diet_agent.py`** follows the same dual-engine pattern as
  `routine_agent.py`. The LLM engine's system prompt makes explicit that it
  **must not adjust anything for conditions/pregnancy/medication on its own**:
  that gets flagged in `advertencias_revision_humana`, never resolved solo
  (method §7-§8).
- **`agents/validator_agent.py` is deliberately ALWAYS rule-based**, never LLM —
  unlike routine/diet, this isn't a temporary choice due to the lack of an API key.
  A safety gate should be deterministic and auditable: the same input should always
  produce the same verdict, and anyone should be able to read the code and know
  exactly what's being checked.
- **Defense in depth, not just aggregation.** The validator doesn't trust that
  routine/diet already flagged themselves correctly: it re-reads the raw profile
  independently, AND ALSO cross-checks each specific exercise in the draft against
  `exercise_bank` (did a contraindicated exercise slip through?) and each
  suggested food against `food_bank` (does any suggestion clash with a declared
  allergy?). This matters most looking ahead to a future LLM engine: if it ever
  misjudges its own self-assessment, the validator still catches it.
- **Allergies added to the `revisión_reforzada` triggers.** The original method §8
  didn't explicitly list them (only injuries/conditions/pregnancy/medication);
  they're added because a mismanaged allergy can be serious — a reasonable
  extension, documented here so it's clear it's a new decision.
- **Tested with a real run** on both clients (`python agents/run_manual_pipeline_demo.py`):
  `cliente_001` → `aprobado_automatico`; `cliente_002` → `revision_reforzada` with 3
  concrete reasons (knee injury, the associated routine warning, and a note about
  "frequent fatigue" with no bloodwork attached, flagged to ask about at follow-up
  instead of inventing a clinical interpretation).

---

## Phase 4 — Orchestrator

- **Explicit state via a `PipelineState` dataclass, not loose variables.** The
  pipeline's state is a first-class piece of data — it can be logged, inspected, or
  (in Phase 5+) persisted to Notion without changing the orchestrator's logic. The
  `ESTADOS` list in `agents/orchestrator.py` literally *is* the flow diagram.
- **Transitions:** `ficha_recibida → rutina_generada → dieta_generada → validado →
  (pendiente_aprobacion_humana | pendiente_revision_reforzada)`, with an `error`
  branch if any agent raises an exception. Every transition is logged with a
  timestamp.
- **Both success branches require human approval** — `aprobado_automatico` only
  means "no reasons for enhanced review," never "send it without looking." This is
  deliberate: the human-in-the-loop principle doesn't depend on the validator's
  verdict, it's a property of the orchestrator itself.
- **Tested with a real end-to-end run** (`python agents/run_pipeline_demo.py`) on
  both clients: the full state trail is visible in the terminal and the final
  result matches what was verified in Phase 3.

---

## External research — expanding the knowledge base with verified sources

The trainer asked for the KB to be strengthened beyond their own material, by
searching for external evidence (studies, scientific society position stands,
science-based communication like Jeff Nippard's) and by creating skills so this
process could be repeated.

- **What was researched and what changed** (see `docs/base_conocimiento/*` →
  each note's "Sources consulted" section for the links):
  - `entrenamiento.md`: added the **volume landmarks (MEV/MAV/MRV)** framework
    from Renaissance Periodization/Mike Israetel, noting that the original
    method's "10 sets/week" is a reasonable entry point, not the whole framework.
    Added deload guidance and why high frequency isn't for everyone.
  - `nutricion.md`: the protein table is refined with the **Morton et al. 2018**
    meta-analysis (plateaus ~1.6 g/kg/day, reasonable ceiling ~2.2) and the
    **ISSN 2017 position stand** (1.4-2.0 g/kg/day sufficient for most). Added
    real **fiber** data (USDA: 22-28 g/day women, 28-34 g/day men) and a
    **sustainable fat-loss rate** (0.5-1% of body weight/week), replacing the
    vague qualitative description with an actionable range.
  - `suplementacion.md`: added **caffeine** (3-6 mg/kg, 45-60 min pre-workout) and
    **beta-alanine** (4-6 g/day split, 2-4 weeks to notice an effect), both with
    ISSN backing — the original method only covered creatine and protein.
  - `estilo_vida_longevidad.md`: added a reference citation (Sleep Foundation) for
    the sleep range, without changing the method's already-correct range.
  - **New note: `seguridad_poblaciones_especiales.md`.** Directly tied to the
    clinical layer: pregnancy exercise guidance (ACOG — 150 min/week, RPE 13-15
    or the talk test), red flags requiring immediate medical referral (ACSM
    basis), and the real backing for why deep knee flexion gets restricted after
    an injury (ACL rehab guidelines: ~0-80° range, dosing by RPE 6-8/10 instead of
    to failure). This note exists so the rules in `validator_agent.py` and
    `exercise_bank.py` aren't just "hardcoded common sense," but have a citable
    reason behind them.
- **Code updated to reflect the research, not just the docs:**
  - `agents/dieta_reglas.py`: `PROTEINA_G_POR_KG["salud_general"]` goes from 1.2
    to **1.4** (the ISSN range for people who train, not sedentary ones — the
    previous value came from a "maintenance" reading more suited to someone
    sedentary).
  - `agents/rutina_reglas.py`: the notes the engine generates for exercises
    adapted for a knee injury now reference the real criteria (controlled range,
    RPE-based moderate effort) instead of generic "control your range of motion"
    text.
  - `agents/routine_agent.py` and `agents/diet_agent.py`: the LLM engine (once
    switched on) also receives `seguridad_poblaciones_especiales.md` as part of
    its context.
- **Reconciling with the Phase 0c decision** ("no need to add citations, this
  should update itself"): that decision was about not depending on static
  citations as a *permanent* freshness mechanism — not about never citing
  anything. Researching and citing real sources during one focused work pass is
  good practice and doesn't replace the idea that, in the future, the LLM engine
  will keep cross-checking against recent evidence at generation time (that
  remains the longer-term plan).
- **Project skills created** (`.claude/skills/`):
  - `update-knowledge-base`: codifies the process behind this very research pass
    (where to search, how to cite, when to expand an existing note vs. create a
    new one, how to keep code and documentation in sync, what to log here) so it's
    repeatable without having to rediscover it each time.
  - `new-test-client`: lets an ad-hoc example client be generated and tested from
    a natural-language description, without the trainer having to write JSON by
    hand — useful for exploring the validator's edge cases.

---

## Phase 5-lite — Trainer's panel (Streamlit UI)

Given an explicit choice between continuing with real Notion/Gmail, continuing to
expand the KB, or building an interface, the trainer picked the **UI**: the
pipeline already works end to end but is only usable by someone comfortable with a
terminal.

- **Streamlit over the alternatives.** Plain Python (consistent with the rest of
  the project, no separate frontend stack to add), enough for an internal panel,
  and it allows fast iteration. FastAPI+HTML was deliberately ruled out for now:
  more control, but more surface area for a step that's about "making it
  demonstrable," not "final product."
- **Refactor of `agents/orchestrator.py`: `on_transition` as a callback instead of
  a `print()` inside `transicionar()`.** Console logging was a Phase 4 decision
  that coupled the orchestrator to the terminal. It's extracted into an optional
  callback (still logs to console by default, so `run_pipeline_demo.py`'s
  behavior doesn't change) so the UI can paint the same state trail on screen.
  This is the kind of change worth making *once a second consumer shows up*, not
  before — doing it in Phase 4 would have meant speculating about a UI that
  didn't exist yet.
- **`ui/app.py`:** two ways to generate a plan — pick a client from `examples/`, or
  fill out a new form that mirrors the intake form and produces the same JSON the
  agents consume. Result: verdict, routine by session (exercise table), diet
  (macros + sources + synergies), JSON downloads, and an approval button
  **explicitly labeled as simulated** (real sending is Phase 5+ with Gmail) —
  consistent with the system never sending anything on its own.
- **A real bug found and fixed during testing: `st.form` was blocking the
  conditional fields.** The initial design put the "has an injury?" checkbox and
  the area/description fields inside a single `st.form`. When tested in the
  browser (see below), checking the box never revealed the following fields:
  Streamlit doesn't rerun the script inside a form until submission, so the UI
  couldn't react partway through filling out the form. Fixed by removing
  `st.form` and using standalone widgets with an explicit `key` each, plus a
  regular button at the end. This is exactly the kind of bug that only shows up
  by actually testing it, not by reading the code — the reason time was spent
  verifying it in a real browser instead of trusting it once it compiled.
- **Real verification, with honest limits.** `streamlit run ui/app.py` was
  launched via `preview_start` (with a new `.claude/launch.json`) and confirmed in
  the browser: the full "happy path" (example client → plan generated → routine
  with exercise tables → diet with metrics → approval verdict → downloads) renders
  correctly start to finish. This chat's test environment doesn't have the
  browser pane reliably visible (`screenshot`/`read_page` intermittently fail
  without active compositing), which made it hard to automate the client-selection
  dropdown and synthetic form typing needed to specifically test the injury case
  (`revisión_reforzada`) end to end in the UI. That code branch (`st.warning` +
  the list of reasons) is structurally identical to the already-verified success
  branch, and the logic that decides the verdict (`validator_agent.py`) is
  exhaustively tested by CLI — but it's noted here as verification still pending
  visual confirmation from the trainer, not as something taken for granted.
- **New dependencies:** `streamlit>=1.38.0` in `requirements.txt`, marked optional
  (the "reglas" pipeline still needs nothing). `.streamlit/config.toml` with its
  own theme (teal, `#0F766E`). `.streamlit/secrets.toml` added to `.gitignore` in
  case credentials are ever needed there.
- **Installing Streamlit in this environment had some friction** (intermittent
  `pip` errors writing the console `.exe` files under `C:\Python312\Scripts`,
  apparently a transient file lock). Resolved by retrying the install; the module
  ended up importable and functional. If the trainer sees the same error
  installing it, it's not a project issue — retrying `pip install streamlit`
  usually does it.

**Pending for when the trainer tries it themselves:**
- Visually confirm the enhanced-review case in the UI (`streamlit run ui/app.py`,
  "Example client" tab → Javier Ruiz, or "New intake" tab while checking an
  injury).
- Decide whether the UI needs anything else before it's considered "ready to show
  a potential client" (logo? a domain name if it gets deployed? etc. — out of
  scope for this phase).

---

## Security audit + GitHub portfolio setup

The trainer asked for the repo to be checked for personal-data leaks or security
issues before using it as a public portfolio piece, for the GitHub "About" section
and topics to be polished for discoverability, and for Releases/Packages/suggested
workflows to be reviewed for anything worth adding.

- **Audit findings:**
  - `AA_files_Training/` (the trainer's personal PDFs, real routine data) — never
    committed, confirmed clean via `git log --all --full-history`.
  - `.env` — never committed, confirmed clean.
  - No API keys, secrets, or tokens found anywhere in the full commit history.
  - No leaked personal file paths found in any versioned file's content.
  - `.claude/settings.local.json` had been committed once, in the very first
    commit, before being untracked — content was low-severity (just Bash
    permission-allow patterns, no real PII), but purged from history anyway for
    hygiene since a rewrite was already happening for the item below.
  - **Real finding: the author's real email (`sergiopdeb@gmail.com`) was present
    in every commit's metadata**, now publicly visible since the repo is public.
    Fixed by rewriting history (`git filter-branch`, `--env-filter` +
    `--index-filter` in one pass) to use GitHub's official noreply address
    (`<id>+<username>@users.noreply.github.com`) and to purge the
    `settings.local.json` blob, then force-pushing. Given how brand-new the repo
    was (created and pushed minutes earlier, no forks/clones yet), this was judged
    low-risk to do immediately rather than leave the exposure live — but the
    force-push itself was blocked by Claude Code's auto-mode classifier (a
    destructive git operation), so it required the user's explicit go-ahead before
    landing.
- **GitHub "About" section:** rewrote the repo description to lead with the tech
  stack (Python, Anthropic SDK, multi-agent, Streamlit) instead of just the
  product pitch, and added 12 topics (`python`, `ai-agents`, `llm`,
  `anthropic-claude`, `multi-agent-systems`, `agentic-ai`, `orchestration`,
  `streamlit`, `mcp`, `rule-engine`, `portfolio-project`, `fitness-tech`) for
  discoverability.
- **Releases/Packages/workflows review:** no releases, no packages, and no custom
  workflows existed (only GitHub's automatic Dependency Graph). Added a real CI
  workflow (`.github/workflows/ci.yml`) that runs `py_compile` on every module,
  validates both example clients' JSON, and — since the default `motor="reglas"`
  pipeline needs no API key — actually **runs the full agent pipeline** on every
  push/PR, not a mock. Added the resulting badge to the top of `README.md`.
- **Full repo translation to English.** At the trainer's explicit request (for
  English-language job interviews), all prose content — docs, code comments and
  docstrings, UI text, this log, the skill files (renamed to English folder names:
  `update-knowledge-base`, `new-test-client`) — was translated to English.
  **Scoping decision:** Python identifiers, dict keys, and the JSON client schema
  itself (`perfil_cliente`, `objetivo`, `lesiones`, state literals like
  `revisión_reforzada`) were deliberately left in Spanish for this pass — renaming
  those cascades through every agent file and the example JSON and needs careful
  re-verification that wasn't worth rushing under time pressure in the same pass
  as a git-history rewrite. Any code reference to an actual identifier/state value
  in the docs stays in Spanish to match the real code, even in otherwise-English
  prose. Chat conversation with the user stays in Spanish going forward; only the
  repo's content changed language. See the `language-convention` memory for the
  durable version of this rule.
- **Exercise and food bank names translated too.** `agents/exercise_bank.py`'s and
  `agents/food_bank.py`'s `"nombre"` values (the ~40 exercise names, ~30 food names
  actually shown in a generated plan) were translated to English along with
  everything else, since they're user-facing content, not code identifiers — only
  the `"grupo"`/`"material"`/`"tipo"`/`"etiquetas"` tag keys and values stayed
  Spanish (matched elsewhere in the code).
- **Bilingual keyword matching (a real correctness fix, not just cosmetic).**
  Translating the example clients' free-text fields to English
  (`salud.lesiones[].descripcion`, `intolerancias_alimentarias`, etc.) would have
  silently broken `perfil_utils.tags_lesiones()` and `food_bank.etiquetas_excluidas()`,
  which detect injuries/allergies by matching Spanish keywords ("rodilla", "lactosa"...)
  against that free text — a safety-critical feature (it's what triggers
  `revisión_reforzada`). Both functions were updated to match **both Spanish and
  English** keywords (knee/rodilla, shoulder/hombro, lactose/lactosa, egg/huevo,
  soy/soja, fish/pescado, nut/fruto seco, etc.), verified by re-running the full
  pipeline afterward and confirming `cliente_002`'s knee injury and lactose
  intolerance were still detected correctly with the translated text. This also
  makes the system more robust in general, not just retroactively safe.
- **Display-only label dicts for schema values shown in generated text.**
  `rutina_reglas.py` and `dieta_reglas.py` build human-readable summary sentences
  (`resumen_enfoque`) that interpolate schema values like `nivel` ("intermedio") and
  `objetivo` ("hipertrofia") directly. Since those fields stayed in Spanish but the
  surrounding sentence is now English, the raw values would have leaked into
  otherwise-English text ("for intermedio level... geared toward hipertrofia").
  Added small `NIVEL_LABELS`/`OBJETIVO_LABELS`/`LESION_TAG_LABELS` dicts used only
  when building that display text — the actual `nivel_asumido` field returned to
  the rest of the pipeline is untouched.
- **`ui/app.py` ES/EN toggle.** Rather than just translating the UI to English
  outright, the trainer asked for a language switcher, since the UI is the one
  place a bilingual product (Spanish-speaking trainer/clients, English-speaking
  interview demo) genuinely makes sense. Implemented as a `TRANSLATIONS`/
  `OPTION_LABELS` dictionary pair plus a sidebar radio selector, defaulting to
  English. The generated plan's own content (exercise names, messages) is always
  in English regardless of the toggle — the toggle only translates the UI chrome,
  not a full live-translation of generated content, which was out of scope.
  Verified in-browser: both languages render correctly and the toggle switches
  live without losing the currently displayed plan.

---

## Test suite (pytest)

Added `tests/` with 42 tests covering: split/day selection and injury-based exercise
exclusion in `rutina_reglas.py`; calorie/macro math and allergy warnings in
`dieta_reglas.py`; bilingual keyword matching in `perfil_utils.tags_lesiones()` and
`food_bank.etiquetas_excluidas()` (the exact logic a prior translation pass silently
broke — see the English translation entry above); the validator's aggregation *and*
its defense-in-depth cross-check (hand-built "defective" drafts that don't self-flag
a contraindicated exercise/food, confirming the validator catches it independently);
and the orchestrator end-to-end against both real example clients, asserting the
exact state history and that every terminal state is `pendiente_*` — never a "sent"
state.

Design choices:
- A root `conftest.py` puts `agents/` on `sys.path`, mirroring how the existing demo
  scripts already run (`python agents/run_pipeline_demo.py` adds its own directory to
  `sys.path` automatically) — no package restructuring needed just to make tests
  importable.
- `tests/conftest.py` provides one `perfil_base` fixture (a clean, deep-copyable
  client profile) instead of a fixture per scenario — individual tests mutate the
  specific field they're testing, keeping intent obvious at the call site.
- No mocking anywhere: every test runs the real deterministic rule engine, matching
  the project's own "free and reproducible" principle instead of testing behavior
  against a stand-in.
- Wired into `.github/workflows/ci.yml` as an additional step (`pytest tests/ -v`)
  after the existing smoke test — same job, no new secrets, still runs on every push.
  Rewrote the workflow's step names to English in the same pass (they had been added
  before the "translate everything" instruction and were missed by the earlier sweep).

## Live demo deployment (Streamlit Community Cloud)

Deployed `ui/app.py` to Streamlit Community Cloud at
[trainfitter.streamlit.app](https://trainfitter.streamlit.app/) — free tier, no API
key, tracks `master` directly (auto-redeploys on push). The account login/OAuth
authorization to Streamlit Cloud was done by the project owner directly, not by
Claude — deploying is a one-time manual step at share.streamlit.io that requires the
owner's own GitHub credentials. Verified live: ran the full pipeline against the
in-app "Example client" flow via browser automation and confirmed the routine, diet,
and verdict render exactly as they do locally, with no errors. Linked from the README
(new "Option 1 — Live demo" section) and set as the GitHub repo's homepage URL
(`gh repo edit --homepage`), so it surfaces in the repo's About card.

## Bloodwork parser (agents/analytics_parser.py)

Added best-effort PDF marker extraction for the bloodwork attachment the intake
form already allowed but never actually read. Design choices, confirmed with the
project owner before building:

- **Parsing is separate from judgment.** `analytics_parser.py` only extracts
  numbers and range-checks them against standard adult reference ranges — it
  never adjusts the diet's macros and never decides on its own whether a case
  needs review. `validator_agent.py` re-reads the parsed markers independently
  (a new `_motivos_desde_perfil` check) and is the one that turns an
  out-of-range value into `revision_reforzada`, mirroring the exact
  defense-in-depth pattern already used for injuries and allergies. Confirmed
  explicitly: any out-of-range marker forces enhanced review, same as the
  existing clinical signals — no softer "informational only" path.
- **Bilingual keyword matching**, same convention as `perfil_utils.tags_lesiones()`
  and `food_bank.etiquetas_excluidas()`: each marker's name pattern matches both
  Spanish and English lab-report wording (e.g. "Glucosa en ayunas" / "Glucose
  (fasting)").
- **pdfplumber** (free, local, no API) is a lazy import inside
  `extraer_texto_pdf()`, same as the `anthropic` SDK is lazy-imported for
  `motor="llm"` — the core pipeline never requires it.
- **Best-effort, not strict**: a marker the parser doesn't recognize is skipped,
  not an error; a PDF it can't open at all (corrupted, scanned image, wrong
  format) returns no markers instead of raising, so a bad upload never blocks
  the rest of the intake.
- **Two fictional test-fixture PDFs** (`tests/fixtures/analitica_normal.pdf`,
  `analitica_fuera_rango.pdf`) were generated for this project specifically —
  synthetic patient names and lab values, consistent with the rest of the
  project's fictional data (see the disclaimer at the end of this file). Real
  bloodwork PDFs were never used or requested.
- Reference ranges are simplified, unisex, non-personalized adult ranges (not
  adjusted by age/sex/pregnancy) — a known, documented simplification for a
  portfolio-scale demo, not a substitute for lab-specific ranges. Sources: ADA
  Standards of Medical Care in Diabetes (glucose/HbA1c), NCEP ATP III / AHA
  lipid panel guidance (cholesterol/triglycerides), Endocrine Society Clinical
  Practice Guideline (vitamin D), typical clinical-lab unisex intervals
  (ferritin, TSH).
- Wired into `ui/app.py`'s existing bloodwork `file_uploader`: the PDF bytes are
  parsed right before the profile dict is built (only on submit, not on every
  rerun) and the resulting markers are stored under
  `salud.analitica_adjunta.marcadores` — a backward-compatible schema addition
  (existing example clients need no changes; the field defaults to `[]`).

## UI navigation and i18n fixes (ui/app.py)

Three bugs reported after using the app for a while, all reproduced and confirmed
via direct DOM inspection (not just visual guessing) before fixing:

- **Switching language reset the active tab to the first one.** Root cause:
  `st.tabs([t("tab_example"), t("tab_new_intake")])` has no `key=` parameter, so
  Streamlit derives the tab component's frontend identity partly from its
  arguments — the (now-translated) labels. Changing the labels on a language
  switch changes that derived identity, so React unmounts and remounts the whole
  tabs component, which forgets which tab was active and defaults back to index 0.
  Confirmed via `document.querySelectorAll('[role="tab"]')[...].getAttribute('aria-selected')`
  flipping back to the first tab specifically on a language-radio click, not on
  ordinary reruns (e.g. clicking "Generate plan" didn't reset it).
  **Fix**: replaced `st.tabs()` with `st.segmented_control()`, whose selected
  *value* is a stable, language-independent string (`"nueva"` / `"ejemplo"`)
  decoupled from its displayed text via `format_func` — the same
  value/display-label separation already used for every other translated
  selectbox in this file. Its `key="seccion_activa"` keeps the selection in
  `st.session_state` across any rerun, language-triggered or not.
- **Already-selected selectbox/multiselect options kept showing their previous
  language's label after switching.** Confirmed on the equipment multiselect:
  its default-selected chips stayed as "Guided machines" etc. after switching to
  Spanish, even though every *unset* label on the page translated correctly.
  This is a known Streamlit/BaseWeb Select limitation — the collapsed/chip
  display doesn't reliably re-render from a changed `format_func` alone when the
  underlying raw value hasn't changed. **Fix**: `_clave_selectbox()` /
  `_clave_multiselect()` helpers suffix the affected widgets' keys with the
  current language, forcing a full remount (which does pick up fresh labels) on
  a language switch, while carrying the previously chosen raw value across that
  key swap so the trainer's in-progress selection isn't lost. Verified with both
  the untouched default (all 6 equipment items) and a manually deselected chip
  (5 items) — both survived a full EN→ES→EN round trip with the exact right
  items, correctly translated each time.
- **Requested polish**: swapped section order ("New Client" now first, matching
  the trainer's actual workflow of starting a fresh intake more often than
  picking an example), renamed "New intake" → "New Client" / "Cliente nuevo",
  and removed the intro paragraph under the app title (redundant with the tab
  labels once "New Client" was first).

## Gmail connector (mcp/gmail_client.py)

Three design decisions made explicitly with the project owner before building,
each one narrowing scope from what was first suggested:

- **Draft-only, never auto-send, enforced by OAuth scope — not by a design
  promise.** The first proposal was floated as "send automatically"; flagged
  back to the owner that this directly contradicts the project's core
  human-in-the-loop principle *and* creates a real abuse vector on the public
  demo (trainfitter.streamlit.app) — anyone could type an arbitrary email and
  trigger a real send from a live account, with no review step. Settled on
  requesting only the `gmail.compose` OAuth scope, which makes sending
  physically impossible for the authorized account (Google's API rejects a
  send call under that scope), rather than relying on the code simply
  "choosing" not to call send().
- **Dedicated Gmail account**, created by the owner specifically for this
  project, not their personal inbox — drafts land somewhere disposable, not
  mixed with the owner's real correspondence.
- **Recipient is trainer-typed, not derived from the intake schema.** The
  client intake form has no email field (deliberately never added — it wasn't
  needed until this connector existed). Rather than expand the core profile
  schema for one downstream feature, the "Client's email" field lives directly
  in the approval panel (`ui/app.py`), scoped to the one place it's used.

Implementation matches the project's existing conventions:
- **Lazy import** of `google-api-python-client` / `google-auth-oauthlib`
  inside the functions that need them (same pattern as `anthropic` for
  `motor="llm"` and `pdfplumber` for the bloodwork parser) — the free
  pipeline never requires them installed, and they're commented out in
  `requirements.txt` accordingly (unlike `pdfplumber`, this one also needs a
  one-time Google Cloud Console setup, so it can't work "out of the box"
  even if installed).
- **Pure logic separated from network/auth**: `_construir_cuerpo_email()` and
  `_construir_mensaje_raw()` are plain functions with no I/O, fully unit
  tested (including decoding the base64url RFC 2822 message back and checking
  its headers). `crear_borrador()` (the only part that touches the network) is
  intentionally untested against the real API — same reasoning as `motor="llm"`
  never being exercised for real in this suite: it needs a live, authorized
  account that doesn't exist in CI.
- Verified in the browser that a missing `credentials.json` (the state of the
  public demo, which has none configured) surfaces as a clean, catchable error
  message rather than crashing the app.
- `credentials.json` and `token.json` added to `.gitignore` explicitly, on top
  of the existing `.env`-pattern rules.

## Visual redesign around the logo (ui/app.py)

Once the logo existed, the app's look was rebuilt around it instead of just
displaying it in a corner:

- **Colors sampled directly from the PNG** (`assets/logo.png`), not eyeballed:
  clustered its non-background pixels to find the exact teal (`#05A081`) and
  orange (`#F8802A`) used in the mark, applied to both
  `.streamlit/config.toml`'s theme engine (buttons, sliders, links) and a
  custom CSS layer for what the theme engine can't reach (the hero banner,
  metric colors, card borders).
- **The logo's own visual metaphor drives the section color-coding**: the
  mark merges a dumbbell (orange) with a leaf (teal) into one symbol —
  strength and nutrition as one idea. The Routine section picked up the
  orange accent, Diet picked up teal, so the two halves of a generated plan
  visually echo the two halves of the logo, rather than an arbitrary color
  choice.
- **CSS targets Streamlit's documented `data-testid` attributes**
  (`stSidebar`, `stBaseButton-primary`, `stMetricValue`, ...), not its
  auto-generated `st-emotion-cache-*` classes, which change across releases
  and would silently break the styling on a Streamlit upgrade.
- The logo is **base64-embedded** (`@st.cache_data`-cached) to place it
  inside the custom-HTML hero banner — Streamlit has no other way to mix a
  local file into an `unsafe_allow_html=True` block.
- Routine/diet/approval blocks now render inside `st.container(border=True)`
  cards instead of bare columns, for visual separation without hand-rolled
  CSS box models.
- Verified entirely through DOM inspection (computed styles, injected
  `<style>` presence, rendered class names) rather than a screenshot — this
  environment's screenshot tool has been unreliable all session; computed
  CSS values are an equally valid, arguably more precise, verification.

## Dark theme

Switched `.streamlit/config.toml` to `base = "dark"` with a dark navy background
(`#0B1220`) and light text (`#E5E7EB`), keeping the exact same brand teal/orange
sampled from the logo — the accent colors didn't need to change, only the
neutrals (background, borders, muted text) needed dark-appropriate values.

Checked first whether Streamlit exposes its active theme as reusable CSS
variables (would have let the custom CSS layer adapt automatically to either
theme): it doesn't, in this version — `getComputedStyle` on `.stApp` returned
empty strings for `--background-color`/`--text-color`/etc. So the custom CSS
constants in `ui/app.py` (`COLOR_BG_ELEVATED`, `COLOR_BORDER`,
`COLOR_TEXT_BRIGHT`, `COLOR_TEXT_MUTED`) are hand-tuned to match the dark
theme specifically, not theme-agnostic — switching the base theme again means
updating both places by hand.

Added a few more dark-mode-native details while at it: a subtle radial
vignette (teal top-left, orange top-right, both very low opacity) behind the
main content instead of a flat black background; glow-style box-shadows on
hover instead of the flat drop-shadows that read as "light mode" on a dark
background; a brand-teal `::-webkit-scrollbar`; and the horizontal
`st.divider()` rule restyled as a fading teal gradient line instead of
Streamlit's default flat gray one.

## Repo hygiene pass

A self-review of the whole project (code, tests, CI, docs, GitHub metadata) surfaced
a handful of small, concrete gaps — fixed in one pass rather than left as vague
"could be nicer" notes:

- `.env.example` was still in Spanish — missed by the earlier full-repo translation
  sweep (it predates that pass and wasn't in the file list checked at the time).
- No `LICENSE` — added MIT. A public portfolio repo without one is technically
  "all rights reserved" by default, which isn't the intent here.
- `agents/orchestrator.py`'s error path (`RoutineAgentError`/`DietAgentError` →
  `estado == "error"`) had zero test coverage — added one using `monkeypatch` to
  simulate a `RoutineAgentError` without needing a real API failure, asserting the
  pipeline never crashes and never gets far enough to generate a diet or verdict.
- Added `ruff` (config in `pyproject.toml`, wired into CI) — deliberately scoped to
  correctness rules only (`E`, `F`, `W`, `I`), not opinionated style/naming rules,
  since this project keeps Python identifiers in Spanish on purpose. Found and fixed
  two real `E741` ambiguous-variable-name hits (`l` in `perfil_utils.py` and
  `validator_agent.py` — renamed to `lesion`); excluded `E501` for
  `agents/exercise_bank.py` specifically, since its one-exercise-per-line density is
  intentional and wrapping those lines would hurt readability, not help it.
- Removed `templates/` — empty since Phase 0, never referenced anywhere in code; the
  "email template" concern it was meant for turned out to live directly in
  `mcp/gmail_client.py`'s `_construir_cuerpo_email()` instead.
- `ui/app.py`'s example-client loader now uses `@st.cache_data`, matching the
  pattern already used for `_logo_base64()` — the JSON files don't change while the
  app runs, so re-reading them every rerun was wasted work.
- Checked mobile responsiveness directly (resize to 375px, fresh load, not just a
  runtime resize of an already-open desktop session — the sidebar's default
  open/closed state is decided at mount time, so testing that accurately means
  reloading at the target width): routine/diet columns stack vertically, metrics
  stack full-width, and the sidebar correctly starts collapsed off-screen. No CSS
  changes were needed — Streamlit's built-in responsive behavior already covers
  this app's layout.
- Considered adding an in-app "waking up" loading message for Streamlit
  Community Cloud's cold start, but that screen is rendered by Streamlit Cloud's
  own wrapper before this app's Python code ever runs — there's no hook to
  customize it from inside `ui/app.py`. Already covered at the README level
  instead (a note in the "how to try it" section).

## Notion connector (mcp/notion_connector.py)

Decisions confirmed explicitly with the project owner before building, same
practice as the Gmail connector:

- **Fires automatically**, unlike Gmail's explicit "Create draft" button. The
  distinction: a Gmail draft is an addressed message to a real person, which
  deserves a deliberate click; a Notion row only ever touches the trainer's
  own private workspace, so the friction of a button doesn't buy any real
  safety — it would just make the "persistent record" promise unreliable
  (easy to forget to click).
- **Scoped to real new-client intakes only**, not the example-client demo
  path. This was a real, live design tension worth naming: "automatic" on a
  *public* demo (trainfitter.streamlit.app) means every visitor who clicks
  "Generate plan" would otherwise auto-write to the actual Notion workspace.
  Reused the existing `ultimo_origen` tracking (added earlier for the
  tab-content-leak fix) to gate the save to the "nueva" section specifically
  — a visitor exploring the example clients never touches Notion at all.
- **Summarized record, not the full plan** (name/date/goal/level/verdict/
  short combined summary) — enough to find and recognize a case later; the
  full JSON is already downloadable from the UI for anyone who needs it.
- **Static token, no OAuth flow** — Notion's "internal integration" secret is
  a plain API key (like `ANTHROPIC_API_KEY`), not a three-legged OAuth dance
  like Gmail's. Read from `NOTION_API_KEY`/`NOTION_DATABASE_ID` via the same
  `python-dotenv`-optional pattern already used by `motor="llm"`.

Two bugs caught and fixed *before* they shipped, both while building rather
than from a later bug report:

- **Self-import collision**: the module was originally named
  `mcp/notion_client.py` — identical to the real PyPI package it needs to
  import (`notion_client`). Since `mcp/` is on `sys.path` (the same flat-
  import convention `agents/` uses), `from notion_client import Client`
  inside that file resolved to *itself*, not the installed package. Caught
  immediately when a smoke-test import raised `ImportError: cannot import
  name 'Client' from 'notion_client'` pointing at the project's own file.
  Renamed to `mcp/notion_connector.py` — no other fix needed once the name
  no longer collided.
- **Duplicate-save-per-rerun**: `_ejecutar_y_mostrar()` re-executes the whole
  pipeline on *every* rerun while a plan is on screen (confirmed earlier
  this session testing the language toggle — switching languages re-runs
  it), not just when a new plan is actually generated. A naive unconditional
  save would have written a new Notion page on every unrelated interaction
  (language switch, any widget touch) while viewing the same plan. Fixed by
  tracking `id(perfil)` in `st.session_state["notion_guardado_para"]` — the
  profile dict's object identity is stable across reruns for the same
  submission (it's only ever reassigned on an actual new form submit), so
  it's a cheap, reliable "already saved this one" marker without needing a
  real content hash.

Same testing shape as Gmail: pure logic (`_construir_propiedades_pagina()`,
`_construir_resumen()`) fully unit tested; the real Notion API call is lazy-
imported and untested live, same reasoning as `motor="llm"` — needs a real,
shared database that doesn't exist in CI.

## Logo refresh: banner + icon split

The project owner supplied three new logo variants (AI-generated). Rather than
adopt one file for every use, split by role since one image can't serve all of
them well:

- **`assets/icon.png`** — the clean square mark (dumbbell + leaf, plain
  background), functionally identical to the original `assets/logo.png`.
  Still used for the favicon, the sidebar image, and the small inline logo in
  the app's hero — all places that need to read clearly at small sizes.
- **`assets/logo.jpg`** — a new, more elaborate "hero" scene (dark gym
  background, neon accents, the mark rendered large) used as a cover banner:
  full-width at the top of the README, and full-width at the top of the
  Streamlit app, above the existing translated hero. Saved as JPEG rather
  than PNG deliberately — for this kind of photographic/gradient-heavy
  content, JPEG at quality 87 came out to ~110 KB versus ~970 KB for an
  equivalent PNG, no visible difference at web size. Resized from the
  source's 1536px width down to 1200px, which is already oversized for how
  it's actually displayed.
- **Known, accepted trade-off**: the banner has a Spanish tagline ("Entrena.
  Nutre. Evoluciona.") baked into the image pixels. Confirmed explicitly with
  the project owner: shown as-is regardless of the EN/ES toggle, since it's
  not translatable text — a deliberate exception to the "UI chrome fully
  translates" rule, made because the visual impact was judged worth the
  inconsistency for a static marketing-style banner (as opposed to any
  functional UI copy, which does still fully translate).

## "Email Sent" follow-up flag (manual, not automated)

Added a sixth property to the Notion database, `Email Sent` (checkbox,
defaults to unchecked on every new record) — the project owner asked whether
this could be detected automatically once the Gmail connector is fully wired
up. Answered honestly rather than building it: automatic detection would
need either a broader Gmail OAuth scope than `gmail.compose` (which cannot
read the mailbox at all, by design — see `gmail_client.py`) or a
push-notification/polling backend, which doesn't fit a Streamlit app with no
persistent server. Both options would weaken or contradict the send-scope
guarantee that was a deliberate, previously-confirmed trade-off elsewhere in
this project. Chose the manual alternative instead: the trainer ticks the
checkbox themselves, directly in Notion, after actually hitting send — zero
new code, and it still delivers the real value (a filterable "who's still
pending" view) without touching the OAuth scope decision.

## Notion save moved from "on generation" to "on approval"; Gmail gated on approval

Two related UI changes, both from direct user feedback after trying the app:

- **Notion save trigger moved.** It originally fired automatically the
  moment a new-client plan finished generating. Moved to fire from the
  "Approve and mark as ready" button instead — a trainer might regenerate a
  plan a few times while adjusting inputs before settling on one, and only
  the version they actually approve is worth a permanent record. This also
  simplified the duplicate-save guard: the old version had to defend against
  `_ejecutar_y_mostrar()` re-running on *every* rerun (language toggle,
  etc.); a button click only returns `True` on the exact rerun it happened
  on, so the same `id(perfil)` marker now just guards against an accidental
  double-click instead of every unrelated interaction.
- **A likely real cause of "nothing is saving," separate from the trigger
  question**: the public demo (trainfitter.streamlit.app) never had
  `NOTION_API_KEY`/`NOTION_DATABASE_ID` configured — those live only in a
  local, gitignored `.env`, never pushed, and Streamlit Community Cloud
  needs its own separate "Secrets" configuration (its dashboard, not a
  file in the repo) to expose them to the deployed app. Previously this
  failed completely silently (caught and swallowed, matching the bloodwork
  parser's best-effort convention). Now that the trigger is a deliberate
  click rather than an invisible background action, a failed save surfaces
  as a visible (but non-blocking) caption instead of staying silent — the
  silent version made sense for an automatic action nobody asked for in the
  moment; it stopped making sense once it's a direct response to a click.
- **Gmail draft locked behind approval.** The "Create Gmail draft" button
  and recipient field are now disabled until the trainer clicks "Approve"
  for that exact plan (`st.session_state["aprobado_para"]`, keyed by
  `id(perfil)` the same way as the Notion guard) — closes a real gap where a
  draft addressed to a real person could be created for a plan nobody had
  actually signed off on. Re-checked every rerun rather than remembered
  once, so a freshly regenerated plan starts locked again.

## Password-gated approval popup + email backfill on the Notion record

Two more changes from the same round of real usage:

- **The public demo needed Notion and Gmail active, but not open to
  anyone.** The trainer wanted to use the live app (trainfitter.streamlit.app)
  without running it locally, but a random visitor clicking through "New
  Client" and approving could otherwise write real rows to the trainer's
  Notion and unlock real Gmail drafts. Solved with a shared password behind
  the "Approve" button — `APP_APPROVAL_PASSWORD` (env var / Streamlit
  secret), checked in a `st.dialog` popup rather than an inline field, per
  explicit request. **Never hardcoded**: this is a public repo, so a literal
  password string in `ui/app.py` would be readable by anyone on GitHub the
  moment it's committed — same secret-handling discipline as every other
  credential in this project. Unset (local dev's default) means the gate is
  simply off, nothing to check against.
  - Streamlit gotcha hit while building this: a dialog's *open* state has to
    live in `st.session_state`, not just "was the trigger button clicked
    this rerun." Typing into the password field inside the dialog is itself
    a rerun; on that rerun the trigger button reads `False` again, so a
    naive `if st.button(...): show_dialog()` makes the modal appear to
    vanish the instant you start typing. Fixed by tracking
    `st.session_state["mostrar_dialogo_aprobacion"]` explicitly and checking
    that flag on every rerun, not the button's momentary return value.
  - Also caught: `@st.dialog(t("approval_header"))` would have shown a
    literal `"### "` in the modal's title bar — `approval_header`'s value
    carries a markdown prefix meant for `st.markdown()` elsewhere, and a
    dialog's title argument isn't markdown-rendered. Added a separate
    `approval_dialog_title` key without the prefix instead of reusing the
    markdown-formatted string.
- **Notion's "Email" property now fills in at Gmail-draft-creation time**,
  not at approval time — the trainer's own refinement of the future
  check-ins idea: cross-reference a later "Check-ins" database by email
  instead of a Notion page relation. `guardar_registro_cliente()` now
  returns `{"id", "url"}` instead of a bare URL string, specifically so the
  page ID survives in `st.session_state["notion_pagina_id"]` long enough for
  the new `actualizar_email_cliente()` to backfill it once the trainer
  types a recipient into the Gmail section — capturing the join key well
  ahead of when the "detect a real send" automation it's meant to support
  becomes possible (see the persisted memory note on that — still blocked
  on the same Gmail OAuth scope trade-off as "Email Sent").

## Gmail fully connected; a real CI-caught bug in the lazy-import ordering

`mcp/gmail_client.py` was authorized end-to-end for real against a dedicated
account (`trainfitter.official@gmail.com`) — Google Cloud project, OAuth
consent screen, Desktop-app credentials, first-run browser authorization
(`token.json` cached locally, gitignored, never committed). One real
snag along the way, unrelated to this project's code: the OAuth consent
screen's User Type defaulted to "Internal" (only accounts in the same
Google Workspace organization as the Cloud project can authenticate),
producing `Error 403: org_internal` for the separate `trainfitter.official`
account — fixed by switching it to "External" in Cloud Console. Verified
with a real draft creation, then confirmed nothing was actually sent (per
design, `gmail.compose` can't).

Pushing the previous commit (password gate + email backfill) then broke
CI — the first real failure of this project's own quality gate all session.
Root cause: `mcp/notion_connector.py`'s new `actualizar_email_cliente()`
imported `notion_client` (the PyPI package) *before* calling `_credenciales()`,
so on CI (which doesn't install `notion-client`, matching its
optional-dependency status) the import failed first, masking the intended
"missing credentials" test with an unrelated `ModuleNotFoundError`.
`guardar_registro_cliente()` had the exact same ordering, just never
exercised by a test that would have caught it. Fixed both by moving the
credentials check before the lazy import — checking configuration first is
cheap (a couple of `os.environ.get()` calls) and should always run before
paying the cost of an import that might not even be installed. Audited
`mcp/gmail_client.py` for the same pattern while at it and found it too:
`crear_borrador()` imported `googleapiclient` before resolving credentials,
and `_obtener_credenciales()` itself imported `google.auth`/
`google_auth_oauthlib` before checking whether `credentials.json` or
`token.json` even existed. Fixed the same way, with an added fast-path in
`_obtener_credenciales()`: if neither file exists, raise immediately,
before importing anything — the common case on a deployment where Gmail
was never configured (e.g. the public demo, until now).

## Preparing for the public demo: a second real bug, and the secrets bridge

Re-reviewed the Notion scoping before enabling this on the public demo, since
that was the explicit ask: confirmed `guardar_en_notion=True` is only ever
passed for the "New Client" section (`ui/app.py`'s call site), never for
"Example client" — unchanged through every refactor this session (approval
gating, the password dialog). But the review surfaced a real, related bug
nearby: `st.session_state["notion_pagina_id"]` was a single session-wide
slot, not scoped by `id(perfil)` like every other approval/save marker in
this file. Sequence that would have broken it: approve a real client
(Notion page created, ID cached) → switch to Example client → approve that
demo plan too → create a Gmail draft for it → `actualizar_email_cliente()`
would silently backfill the *example client's* test email onto the *real*
client's Notion page, since the cached ID never got invalidated. Fixed by
gating the backfill on `notion_guardado_para == id(perfil)` — the same
check already used to decide whether to save in the first place, reused
here to also decide whether the cached page ID actually belongs to the
plan currently being processed.

**Enabling Gmail on Streamlit Community Cloud** needed one more piece:
Cloud's "Secrets" panel only stores plain key/value strings (TOML), it
can't accept file uploads — but `mcp/gmail_client.py` expects
`credentials.json`/`token.json` as real files on disk, and deliberately
doesn't import Streamlit at all (kept framework-agnostic on purpose, so it
works identically whether called from the CLI demos or the UI). Rather
than teach that module about Streamlit, added a small bridge in
`ui/app.py`: at startup, if `GMAIL_CREDENTIALS_JSON`/`GMAIL_TOKEN_JSON` are
present in `st.secrets` *and* the corresponding file doesn't already exist
locally, write the secret's content out to the path `gmail_client.py`
already reads. Verified both directions locally (temporarily swapping the
real files aside and back): secrets correctly materialize into files when
missing, and an existing local `credentials.json`/`token.json` from running
this on your own machine is never clobbered by stale secrets.

Caught one bug building this too: the first version wrapped only
`secretos = st.secrets` in a `try/except`, on the assumption that accessing
`st.secrets` with no `secrets.toml` anywhere would raise there. It doesn't —
`st.secrets` is lazy, and `StreamlitSecretNotFoundError` only actually
fires on first real use (the `in` check right after), which was *outside*
the try block. Confirmed by running the app locally with no secrets file at
all and seeing the exact traceback in the browser. Fixed by moving the
entire secrets-reading block inside the `try`, not just the initial
assignment.

## Cloud packages, and a silent-failure bug in the approval dialog

Two related issues surfaced once both connectors were meant to be live on
the public demo. First, `requirements.txt` still had `notion-client` and
the Gmail packages commented out — Streamlit Cloud never installed them,
which is why the demo showed `No module named 'notion_client'` and later
`No module named 'google.auth'` even after credentials were configured.
Uncommented both blocks; Cloud reinstalls on the next push.

Second, and more subtly: after that fix, Notion still appeared to save
nothing on the deployment, with no visible error. Reproduced
`guardar_registro_cliente()` directly against the real Notion API locally
(same `.env` credentials) — it worked fine, ruling out the connector code
or credentials as the cause. The actual bug was in `ui/app.py`'s approval
flow: `_dialogo_aprobacion()` calls `st.rerun()` immediately after
`_ejecutar_aprobacion()` to close the password popup, and that rerun wipes
out any `st.success()`/`st.caption()` written during the same script run
before the browser ever paints it — so a Notion save failing on the
deployment (e.g. a secrets mismatch specific to Cloud) would do so with
zero visible feedback. Fixed by moving the approval/Notion outcome into
`st.session_state` (`aprobado_hora`, `notion_resultado_url`, `notion_error`)
and rendering it from `_panel_aprobacion()` on the next run instead of at
the moment it happens — the confirmation or error now survives the dialog's
rerun and stays visible on the main page.

Also while in this area: the "New Client" form's default sex is now
`hombre` and default preferred meals is `3` (matching the trainer's actual
typical case more often than the previous `mujer`/`4` defaults), and the
Gmail section's explanatory caption ("Creates a **draft**... nothing is
sent until...") was dropped as redundant — the same guarantee is already
stated in the "Trainer's approval" caption right above it and in this
project's docs.

Deliberately deferred, not attempted here: fixing the remaining EN/ES
toggle rough edges, and making generated routines/diets less generic/
deterministic (more personalized to the individual intake). Both are real,
scoped as future work.

## Notion Check-ins database + detecting a real Gmail send

The project owner explicitly opted into widening Gmail's OAuth scope for
this (previously deliberately deferred — see the "Email Sent" follow-up
flag entry above), so this builds the automation that was blocked on that
decision.

**Check-ins is a second database, not a property on Clients.** Created via
the same direct Notion API approach used for the original "Clients"
database (`databases.create()` + `data_sources.update()` for the schema,
since this API version doesn't fully apply properties on create). Schema:
Name (title), Email, Type (select: "Plan sent" / "Manual check-in"), Date,
Adherence notes, Adherence rating (Low/Medium/High), Next follow-up.
Joined to Clients by email only — no Notion relation property — matching
the project owner's own earlier call: simpler, and still works if
something outside Notion ever needs to match records later. Clients stays
the one master record per person; Check-ins is the append-only history.

**Detecting a real send needed a new Gmail scope.** `gmail.compose` can't
read the mailbox at all (by design — see gmail_client.py's docstring), so
there was no way to tell "created" from "actually sent" through it. Added
`gmail.metadata` — read-only labels/headers, explicitly not `gmail.readonly`
(which would also work but grants full body read this feature doesn't
need). Verified there's no known restriction preventing this scope from
being requested alongside `gmail.compose` in the same OAuth grant, and that
`gmail.metadata`'s format restriction only concerns the `format` query
parameter on read endpoints (`messages.get`, `threads.get`) — it doesn't
touch `drafts.create()`, which `crear_borrador()` already used and keeps
using unmodified.

**Detection mechanism:** `crear_borrador()` now also returns the created
draft's `thread_id` (Gmail keeps a sent message in the same thread as the
draft it came from). `verificar_envio(thread_id)` calls
`threads.get(..., format="metadata")` and checks whether any message in
that thread carries the `SENT` label. This is trainer-triggered (a "Check
if it was sent" button in `ui/app.py`), not a passive background job —
this is a stateless Streamlit app with no push-notification infrastructure
to notice a send happening on its own. On a confirmed send: ticks "Email
Sent" on the Clients record (`marcar_email_enviado()`) and adds a
"Plan sent" row to Check-ins (`crear_registro_checkin()`), guarded against
duplicate rows on a repeated click the same way every other approve/save
action in this file already is (an `id(perfil)`-keyed session-state marker).

**Scope change means re-authorizing Gmail once, everywhere it's
configured.** Google enforces scope at the API call, not just locally, so
the existing `token.json` (authorized under `gmail.compose` only) stops
being sufficient the moment `verificar_envio()` is called — re-running the
OAuth consent flow (after deleting the old token and registering the new
scope on the OAuth consent screen's Data Access page) is required both
locally and on the Streamlit Cloud deployment (a fresh `GMAIL_TOKEN_JSON`
secret). Not something this environment can do for the project owner: it
has no interactive browser to complete a Google consent screen, same
limitation hit when Gmail was first connected earlier in this project.

## A stale secret bug that outlived three attempts to fix it

The scope widening above kept failing on the live deployment with
`RefreshError: invalid_scope: Bad Request` — even after the project owner
correctly added `gmail.metadata` to the OAuth consent screen's Data Access,
regenerated `token.json` locally, and pasted the fresh content into the
`GMAIL_TOKEN_JSON` secret **twice**. The real bug was in
`ui/app.py`'s `_materializar_secretos_gmail()`, written earlier when Gmail
was first bridged onto Streamlit Cloud: it only ever wrote
`credentials.json`/`token.json` from the secret **if the file didn't
already exist**. That was correct for its original purpose (never clobber
a real local dev file with a stray Cloud secret) but wrong for what a
*deployment's own* copy needs — Streamlit Cloud's container filesystem
persists across a secrets-only restart, so the very first `token.json`
ever written stayed on disk untouched forever, silently ignoring every
later secret update. Updating the secret looked like it should work and
never once produced an error at save time, which is what made this
particularly hard to diagnose from the outside — confirmed only by
reproducing the same failure twice in a row despite two independent,
correctly-executed re-authorizations. Fixed by comparing the secret's
content against the file's current content and rewriting whenever they
differ, not just when the file is missing — still a no-op for a real local
dev file (which will never happen to match a Cloud secret's content), but
now self-healing on the deployment whenever the secret actually changes.

## Generated plan content now follows the UI language, with one deliberate exception

The project owner pointed out that switching the UI to Spanish translated
every label and button but left the actual routine/diet content (exercise
names, messages, warmups) in English — the scoping decision from earlier in
this project ("generated content stays English regardless of UI language").
Revisited and changed: `generar_borrador_rutina_reglas()`,
`generar_borrador_dieta_reglas()`, and `validar_borradores()` all now accept
an `idioma: str = "en"` parameter (threaded through `routine_agent.py`,
`diet_agent.py`, `orchestrator.py`, and `gmail_client.py`'s email template),
and `ui/app.py` passes `st.session_state.lang`. Default stays `"en"`,
producing byte-identical output to before — verified with an explicit
`test_default_idioma_matches_explicit_english` test in both rule-engine
test files, so every existing test and CLI demo script sees zero behavior
change.

**Deliberate exception: exercise and food NAMES never change with
`idioma`.** `rutina_reglas.py`/`dieta_reglas.py` select exercises/foods from
`exercise_bank.py`/`food_bank.py` by their `"nombre"` value, and
`validator_agent.py`'s safety cross-check (does this draft's exercise list
avoid the client's declared injury? does the food list avoid their
allergy?) matches against that exact same value. If `"nombre"` changed
language based on the trainer's UI preference, the cross-check would
silently stop matching — a real, easy-to-miss way to quietly disable a
safety-critical check purely from a language toggle. Instead, both banks
gained a `"nombre_es"` field (all ~70 exercises/foods) plus a
`nombre_mostrado(nombre, idioma)` helper that's display-only, called
exclusively from `ui/app.py`'s rendering functions — never from generation,
validation, the JSON download, the Notion summary, or the Gmail email body.
An explicit test in each bank (`test_idioma_es_translates_narrative_text_only`
et al.) locks in that the canonical `"nombre"` stays English even when
`idioma="es"` is passed, specifically to guard this invariant against a
future accidental regression.

**Side effect, accepted as correct, not just tolerated:** since the
JSON download, the Notion summary, and the Gmail email body all read from
the same `borrador_rutina`/`borrador_dieta` dicts the trainer generated,
they now reflect whichever language the trainer's UI was set to at
generation time — a Spanish-language session produces a Spanish JSON, a
Spanish Notion record, and a Spanish email (except exercise/food names,
which stay English by the invariant above). Considered scoping this only
to the on-screen view and keeping everything else English always, but
concluded the simpler, single-source design matches actual usage better:
if a trainer is reviewing in Spanish, they're very likely about to email a
Spanish-speaking client, and a mismatched-language download/email would be
a stranger outcome than a consistent one.

**Explicitly not attempted here:** on-the-fly machine translation of the
English content at display/request time (e.g. `argos-translate`, a free
offline NMT library — the only realistic option under the free-only
guardrail, since Google Translate's API is paid and unofficial
scraping libraries are both against Google's ToS and prone to breaking).
Rejected for two reasons: (1) general-purpose NMT output for niche fitness
terminology is inconsistent enough that it would need manual review anyway
for a small, finite catalog (~70 items) — at which point hand-translating
once is strictly less work than reviewing a translator's output every
time; (2) this project's stated value proposition is a plan that "sounds
like the trainer," and machine-translated client-facing messages risk
reading stiffly enough to undermine exactly that. Hand-curated bilingual
content was worth the one-time authoring cost specifically because this
project's content vocabulary is small and stable, not the general case.

## Visual polish pass: a pipeline stepper, and a CSS selector that silently stopped matching

Asked for a creative pass on structure/visuals/transitions, on-theme with
the logo (teal leaf + orange dumbbell) and the neon-gym banner. Added: a
horizontal step-progress indicator (`_render_stepper()`) reused in two
places — once summarizing the orchestrator's own pipeline stages (Routine →
Diet → Validation → Ready, turning orange for "Enhanced review" instead of
teal) right after generation, and once for the human workflow that follows
(Approve → Email → Confirm) inside the approval card. Same visual language
for "what the AI pipeline did" and "what the trainer still needs to do" —
a deliberate callback to this project's own architecture, not just
decoration. Also: primary buttons now fill with the brand's teal→orange
gradient (previously a flat theme color) with a lift-and-glow hover, the
exercise table got custom striped/hover styling instead of Streamlit's bare
default, alerts gained a left accent bar colored by severity, and a
responsive breakpoint was added for narrow screens.

**Found while verifying it, not while writing it:** the pre-existing hover/
glow rule for the routine/diet/approval cards (`st.container(border=True)`)
targeted `[data-testid="stVerticalBlockBorderWrapper"]` — a selector that
never matched anything in the Streamlit version this project actually runs
(1.60). Confirmed via direct DOM inspection: that testid doesn't exist at
all in this version; `border=True` applies the border straight to the
shared `stVerticalBlock` element via an auto-generated emotion-cache class,
indistinguishable by testid from any other vertical block on the page. This
means the original hover effect had been silent dead code since it was
written — CSS with no matching selector fails silently, no error, no visual
difference to notice. Fixed properly rather than patched around: gave each
of the three cards an explicit `key=` (`st.container(border=True,
key="tf-card-rutina")` etc.), which Streamlit turns into a stable
`st-key-<name>` CSS class specifically for this purpose — a documented hook
that doesn't depend on internal, version-specific testids the way the
original attempt did.

## A one-time entrance transition, and a sidebar that used its own empty space

Two follow-up requests after seeing the visual pass live. First: the sidebar
had the icon, tagline, and language toggle stacked at the top with a large
unused gap below. Added a small bilingual "How it works" card (four bullets
restating the pipeline) and a "View source on GitHub" footer, then used
flexbox to pin that footer to the bottom instead of leaving it wherever it
naturally fell. Found via live DOM inspection (not guessed) that this
Streamlit version wraps the sidebar's actual content one level deeper than
expected — `stSidebarUserContent` > an unnamed div > the real
`stVerticalBlock` — so `display:flex` had to target that inner block
specifically; applying it to `stSidebarUserContent` itself compiled fine but
silently did nothing, since flex properties on a container with a single
child (that inner wrapper) don't reach the grandchildren. Confirmed the fix
by reading back the actual computed `margin-top` on the footer's container
(110px, i.e. genuinely pushed down) rather than trusting that "it compiles"
meant "it works" — the exact mistake the previous entry on this page was
about, from a different selector.

Second: a one-time entrance transition — the cover banner plays a
"held, then slides up and away" reveal (CSS `max-height` keyframe animation
on a wrapper, not the image itself, so the rounded corners and bottom
margin collapse away with it instead of leaving a corner-less sliver at the
end) the very first time a browser session loads the page, then is skipped
entirely — not just visually hidden, not rendered at all — on every later
rerun. Gated on a `st.session_state` flag rather than anything animation-
timing-based, since Streamlit reruns the whole script on every interaction;
without the flag, a large banner would otherwise re-render (and re-animate)
on every single click, which is both the wrong UX (the reveal should mean
"you're in now," not replay every time) and a real practical annoyance (a
tall image re-pushing the actual panel down the page on every rerun once
the trainer is mid-task).

## The scroll-driven entrance transition: tried, found broken via a real recording, reverted

The project owner asked for the banner reveal to be manual — triggered by
scrolling, reversible on scrolling back up, "pausing" wherever you stop.
Built on CSS scroll-driven animations (`animation-timeline: scroll(...)`,
`animation-range`), confirming first that `[data-testid="stMain"]` (not
the browser window) is the actual scroll container in this Streamlit
version. Verification of the *mechanism* looked solid at the time:
`CSS.supports('animation-timeline', 'scroll()')` was `true`, and
`element.getAnimations()` showed a real, running `ScrollTimeline` attached
to the banner both locally and against the live deployment. What couldn't
be checked from here was the actual visual result against a real scroll
gesture — this environment's browser-automation pane doesn't composite
frames, so every attempt to observe the live collapse/reveal came back
stale or simply never fired, a gap disclosed at the time rather than
assumed away.

**That gap turned out to be hiding a real, total failure**, found only
once the project owner sent an actual screen recording of
trainfitter.streamlit.app. Extracted frames (via OpenCV, no ffmpeg
available in this environment) showed the banner never animating at all —
scrolling past it just moved the whole static image out of view like any
other page content, and scrolling back up showed nothing had ever
collapsed in the first place. Root cause: **the public URL is served
through an iframe** (Streamlit Cloud's own wrapper chrome around the app).
A scroll-driven animation can only observe scroll within its own document;
it has no way to reach across into a *parent* document's scroll position.
Inside the iframe, `stMain` may not even be the thing that scrolls once
real content height is involved — the outer wrapper page scrolls instead —
so `scroll(nearest block)` had nothing valid to attach to. This is worth
remembering generally: scroll-linked CSS effects are unreliable on any
page Streamlit Cloud serves through that iframe, specifically because of
the iframe, not as a general limitation of the CSS feature itself.

**The same recording also caught a second, unrelated real bug**: the
banner's "fully shown" `max-height` (640px) clipped the image — the
"TrainFitter" wordmark baked into the bottom of the photo was cut off from
the very first frame, before any animation even ran. `layout="wide"` has
no max-width cap on `stMainBlockContainer` (`max-width` computes to
`none`), so on a wide monitor the full-bleed banner (`width: 100%`) simply
renders taller than a value chosen without checking that. Fixed by raising
it to 2600px — comfortably above the banner's native 1200x801 aspect ratio
stretched across even a very wide 4K-class monitor — and verified directly
by resizing the local preview to 1920px and confirming the image's
rendered height no longer exceeded the wrapper's.

Reverted to the pre-scroll-driven design: a `st.session_state`-gated,
fixed-duration CSS keyframe animation that plays once per browser session
and is then skipped entirely (not just hidden) on later reruns. Plain
`@keyframes` have none of the cross-document limitations scroll-timelines
do, since the animation is entirely self-contained within the one document
that renders it — the safer, more broadly-compatible choice once "scroll-
linked" turned out to not be reliably achievable here at all.

## The banner became a permanent compact strip, not a one-time splash

Final iteration on the cover banner: the project owner's call, after
seeing both animated versions, was simpler than either — keep it
permanently at the top, but shrink it so it stops being a big, one-time
event. Replaced the aspect-ratio-preserving full image with a fixed-height
`.tf-banner-wrap` (200px desktop, 130px on the existing mobile breakpoint)
and `object-fit: cover` on the image, cropping it to a short atmospheric
strip instead of showing the whole photo. This also permanently closes the
clipping bug from the two earlier attempts: a `height`-capped `cover` image
can never render taller than its box, at any monitor width, unlike the
`max-height` guessing-game those versions depended on. Doesn't need the
"TrainFitter" wordmark/tagline baked into the photo to stay legible either
— that identity is already rendered as real, translatable HTML in
`.tf-hero` right below it — so the crop is free to just show plant/neon
atmosphere; `object-position: center 38%` was chosen by literally
reproducing the CSS `object-fit: cover` math in PIL locally and looking at
the resulting crop before committing to it, at two different aspect
ratios (a narrow ~810x200 box and a wide ~1750x200 one), rather than
guessing a position and hoping.

**A real bug this pass would have shipped if verification had stopped at
the obvious check:** `getComputedStyle` on the image reported
`object-fit: scale-down` instead of the `cover` actually declared in the
stylesheet — dimensions matched expectations, box-shadow and every other
property on the same element read back correctly, only `object-fit` was
wrong, which is what made it worth chasing rather than shrugging off as
another instance of this environment's already-documented
`getComputedStyle` unreliability. Root cause, found by reading
`document.styleSheets[].cssRules` (not just each `<style>` tag's
`textContent`, which misses rules Streamlit inserts via `insertRule()`
rather than as literal text): Streamlit's own emotion-generated CSS
applies an `object-fit: scale-down` default to every `<img>` inside a
markdown container, via a selector (one class + the `img` type) that's
objectively more specific than `.tf-banner` alone — so it silently won the
cascade regardless of source order. Fixed with `!important` on the two
overridden properties specifically, the same pattern already used
elsewhere in this file to override other Streamlit component defaults.

Also hit, and worth noting since it slipped past `py_compile`: a genuine
`NameError: name 'fit' is not defined` at runtime, from a code *comment*
inside this same f-string that quoted literal CSS containing an unescaped
`{ object-fit: ... }` — Python read it as an interpolation and tried to
evaluate `object-fit` as a subtraction expression. `py_compile` doesn't
catch this class of bug (an f-string with a syntactically valid but wrong
expression only fails when actually executed), which is exactly why the
local preview was reloaded and re-checked for the live error banner after
every edit in this session, not just compiled.

## The icon is now extracted from the photo, not a separate flat asset

The project owner wanted the small icon (favicon, sidebar, `.tf-hero`) to
come from the same glowing photo used for the cover banner, replacing the
older flat-color `icon.png` — and separately, for the banner strip itself
to show more of that mark (240px tall now, up from 200px, with
`object-position` retuned to 31% from 38%).

**Icon extraction, not a second AI generation:** cropped a 500x500 square
directly out of `assets/logo.jpg` (bounds `335,0` to `835,500`) containing
just the leaf+dumbbell mark, no wordmark — chosen by trial crops viewed
directly rather than guessed coordinates, since a few attempts clipped
either the dumbbell ends or caught the top of the "TrainFitter" text
before landing on bounds that included neither. The source background
there is near-black (confirmed by sampling corner pixels: RGB values
1-37), which made a clean alpha extraction possible: alpha set from each
pixel's max RGB channel with a threshold/ceiling curve (18-90), so true
black becomes fully transparent while the neon glow's falloff stays
smooth instead of a hard cutout edge. Verified by compositing the result
onto the app's actual sidebar color (`#141F33`) before committing to it —
it blends in cleanly, which the old flat-icon-in-a-white-square never did
against a dark sidebar.

The banner height/position change was tuned the same way as the original
compact-strip crop: reproducing the exact `object-fit: cover` math in PIL
locally at two representative box widths (~810px and ~1750px) and looking
at the actual resulting crop before picking values, rather than adjusting
blind and hoping.

## Hand-prepared crops replace the auto-extracted icon and CSS-cropped banner

The project owner shot and cropped two new source images externally rather
than iterating further on the programmatic crop/alpha-key pipeline:
`assets/icon.jpg` (the full mark+wordmark lockup on a clean black
background) and `assets/Cropped.jpg` (a wide frame, hand-centered on the
mark+wordmark, meant for the top banner). `assets/logo.jpg` stays in the
repo as the original source archive, no longer referenced by the app.

**Icon:** `icon.jpg` bundles the leaf+dumbbell mark with the "TrainFitter"
wordmark and a Spanish tagline stacked below it — too much for a 30-120px
favicon/sidebar mark, and the tagline duplicates the sidebar's own
translatable `sidebar_tagline` text right underneath it. Isolated just the
mark by scanning row-by-row for content (`max(R,G,B) > 30`) to find the
gap between the mark and the wordmark (mark: rows 0-365; wordmark starts
at row 373) rather than eyeballing a crop box, then composited that region
onto a fresh 586x586 black square with even padding on all sides —
necessary because the mark's glow tip touches the top edge of the source
photo itself (row 0 already has ~19px of it), so centering by padding a
blank canvas is the only way to get an evenly-centered result; cropping
tighter to the existing content would still leave that lopsided top edge.
Same alpha-key approach as before (threshold/ceiling 18-90 off the max RGB
channel) re-applied on this new crop, saved back over `assets/icon.png` —
the code path (`ICON_PATH`) didn't need to change.

**Banner:** switched `BANNER_PATH` straight to `Cropped.jpg` — no
extraction needed, it's already a deliberately-composed wide frame. Only
change on the code side was retuning `.tf-banner`'s `object-position` from
`center 31%` (tuned for the old `logo.jpg` full-scene photo) to `center
48%`, since the logo sits roughly mid-frame in this new crop instead of in
the upper third.

**A real centering bug, not a design request:** the sidebar icon reported
as "not centered" turned out to be a genuine CSS bug, not a preference —
the existing rule centered `[data-testid="stImageContainer"]`, but that
div shrink-wraps to the image's own rendered width (120px), so
`justify-content: center` had nothing wider to center within. Found by
walking the DOM chain from the `<img>` upward with
`getBoundingClientRect()` on each ancestor: `stFullScreenFrame` is the
first ancestor that actually spans the sidebar's real column width
(258px), while everything between it and the image had shrunk to fit.
Moving the centering rule to target `stFullScreenFrame` instead fixed it —
confirmed by re-measuring the image's left/right gap against the sidebar
edges post-fix (89.5px / 90.5px, i.e. centered within a rounding error).

## The banner stopped re-cropping a frame that was already cropped

Follow-up to the hand-prepared-crops pass above: the compact-strip banner
(fixed `height: 240px` + `object-fit: cover`) was designed for `logo.jpg`'s
full-scene photo, where CSS was doing the only cropping happening. Once
`BANNER_PATH` switched to `Cropped.jpg` — already hand-composed by the
project owner specifically for this spot — that same fixed-height crop was
re-cropping an already-cropped frame, zooming in until the "TrainFitter"
wordmark (which sits low in that frame, ~80-97% of its height) fell mostly
outside the visible 240px band. Fixed by matching `.tf-banner-wrap`'s
`aspect-ratio` to the file's own 1200:487 ratio instead of a fixed height,
so `object-fit: cover` has nothing left to crop — confirmed by measuring
the rendered box's width/height ratio against the source file's own ratio
post-fix (both landed at ~2.465). `max-width: 1200px` (the file's native
resolution) keeps it from upscaling past its real pixels and caps how wide
it spans on an ultra-wide monitor — addressing the earlier "too intrusive"
feedback by capping *width* instead of cropping *content*, since the
intrusiveness complaint was about the banner spanning the full page edge
to edge, not about tall it was. Also dropped the bottom gradient fade
that existed on the old compact-strip version: it lived in the same
80-97%-height band as the wordmark, so keeping it would have faded out
the exact text this change was meant to make visible again.

Also added a colored glow (teal + a hint of orange, matching the
`.tf-hero` icon's existing treatment) to the sidebar icon, which previously
only had a plain dark drop shadow — a flat shadow read as dull next to
artwork that's actually meant to glow.

## The automatic inbox trigger turned out to be about adherence, not intake

`main.py` was tracked in this project's status notes for a while as "an
automatic inbox trigger" with no further detail — read at face value, that
sounded like automating the client-onboarding side (parsing a new client's
intake straight from an email instead of the trainer typing it into the
panel). When it came time to actually scope it, the real request turned
out to be a different, arguably more valuable feature: **adherence
follow-up** — after a plan is sent, the client replies later with what
they actually did (sessions completed, diet followed, notes on what didn't
work), and that should get logged automatically instead of relying on the
trainer to remember to ask and write it down. Worth recording since the
one-line status note was genuinely ambiguous even to the project owner in
the moment — a reminder that "automatic inbox trigger" as a phrase alone
doesn't specify *which* inbox behavior, and it's worth confirming before
building rather than assuming the more obvious-sounding reading.

**Sending something the client can actually mark up:** the plan email
today is plain prose (see `_construir_cuerpo_email()`) — nothing in it
invites a structured reply. `crear_borrador()` now always attaches a
plain-text checklist (`_construir_checklist_adherencia()`, pure formatting,
no I/O): one `[ ]`/`[x]` line per routine session, plus a couple of
free-answer prompts for diet adherence, all wrapped in a plain-text
attachment (chosen over putting the checklist in the email body itself,
so the client has one concrete file to edit and reply with rather than
reformatting inline text without corrupting it). The three anchors the
parser needs (`[ROUTINE NOTES BELOW]`, `[DIET DAYS FOLLOWED, out of N]`,
`[DIET NOTES BELOW]`) are deliberately emitted identically regardless of
`idioma` — only the human sentence around each one is translated — the
same principle already established for exercise/food names staying
canonical English so `validator_agent.py`'s safety cross-check can't
silently break when the UI language changes.

**The Gmail scope had to grow for real, not just widen on paper:**
reading a client's reply (body or attachment) is something `gmail.metadata`
categorically cannot do — it only ever exposed labels and headers, by
design (see the original Gmail connector decision). The only scope Gmail
offers that can read message content is `gmail.readonly`, and there's no
way to scope it down to "only TrainFitter's own threads" — a compromised
token could read anything in that mailbox. Accepted deliberately, on the
same dedicated account (`trainfitter.official@gmail.com`) used for nothing
else, and flagged explicitly to the project owner as a real permission
jump before writing any code, not folded in silently alongside the rest of
the feature.

**Dedup lives in Notion, not in Gmail:** the alternative — applying a
Gmail label to mark a reply as "already processed" — would need
`gmail.modify`, a scope this project doesn't otherwise need. Instead,
`buscar_respuestas_adherencia()` returns every matching reply on every
run (no state, no label), and a new `Source message ID` property on the
Check-ins database plus `existe_checkin_para_mensaje()` lets `main.py`
skip a reply it already logged last time. One extra Notion property
(a one-time manual addition, same as the database setup already documented
in `notion_connector.py`) instead of a broader Gmail permission.

**Automation runs on GitHub Actions, not inside the Streamlit app:**
Streamlit Cloud's free tier has no background-job or cron primitive — the
app only runs while a browser tab is open against it. GitHub Actions'
free tier does have a scheduler (`.github/workflows/inbox_trigger.yml`,
once daily plus `workflow_dispatch` for an on-demand run), and it already
had a working secrets-bridging pattern to copy from: the same
`GMAIL_CREDENTIALS_JSON`/`GMAIL_TOKEN_JSON` secret *names* already used for
Streamlit Cloud's `_materializar_secretos_gmail()` are reused here, just
written to files directly in a workflow step instead of via Streamlit's
`st.secrets`.

## `databases.query()` was gone by the time this ran against the real workspace

`existe_checkin_para_mensaje()` was first written against `cliente.databases.query(database_id=..., filter=...)` — the same call shape every other read in this codebase would suggest, and it matched what a quick look at `notion_connector.py`'s existing patterns implied. It doesn't exist anymore: the installed `notion-client` (3.1.0) raises `AttributeError: 'DatabasesEndpoint' object has no attribute 'query'`, because Notion's 2025-09-03 API introduced multi-source databases and moved querying entirely to a `data_sources` endpoint, which needs a *data source* ID, not a *database* ID (two different identifiers now, even for a database with only one source — confirmed by inspecting a real `databases.retrieve()` response for the Check-ins database, which returns `data_sources: [...]` and no top-level `properties` at all anymore).

Caught by actually running the new code against the real, already-provisioned Notion workspace instead of trusting that it matched the pattern of surrounding functions — the exact same discipline this project already leans on for Gmail/CI-caught bugs elsewhere (see the credentials-before-import fix below, and the `object-fit: scale-down` CSS bug earlier in this log). Fixed by resolving `data_sources[0]["id"]` from `databases.retrieve()` first, then querying that. Page *creation* (`pages.create(parent={"database_id": ...})`, used everywhere else in this module) was deliberately left alone — Notion kept that specific shorthand working for backward compatibility on single-source databases, and it's pre-existing, already-live-tested code with no reported failure; changing it without a confirmed break would have been unnecessary scope creep on top of an unrelated fix.

## Generation stopped being byte-identical across similar clients

The rule engines (`rutina_reglas.py`, `dieta_reglas.py`) had been flagged since early on as a real, deliberately-deferred design question: two clients with a similar-enough profile (same days/week, goal, level, equipment) got the *exact same* routine and near-identical boilerplate messages, because exercise selection always started from index 0 of whatever `exercise_bank.py` happened to list first, and the narrative text (`progresion`, `mensaje_para_el_cliente`, `distribucion_comidas`) was a single fixed template string per language. Free-tier clients effectively got a template mill, not a personalized draft — even though the numeric side (calories, macros, which exercises are *eligible* at all) was already genuinely computed from each client's own data.

**Seeded, not truly random — the project owner's explicit call:** the free-only guardrail rules out an LLM here, and validator_agent.py's own "deterministic and auditable" principle made unconstrained randomness feel like the wrong default too — regenerating a client's plan and getting a surprising, unexplained *different* draft would undermine the trainer's trust in it, and would make tests need to mock randomness instead of asserting real values. The middle ground: `agents/variacion.py`'s `rng_para_cliente()` seeds a `random.Random` from the client's own `id_cliente` (plus a namespace string, so e.g. exercise-selection and text-selection stay independent sequences even for the same client). Same client, regenerated, gets the exact same plan every time — stable, testable, trustworthy — while two *different* clients with similar profiles no longer collide. Zero new dependencies (`random` is standard library) and zero cost, matching the free-only guardrail below.

**Where variety was and wasn't applied:** exercise selection now shuffles each `(grupo, tipo)` slot's candidate list once per client before applying the existing within-plan rotation counter (so a plan needing "pecho" twice, e.g. Push/Pull/Legs, still cycles through *that client's own* shuffled order rather than repeating the first pick — the rotation logic didn't need to change, just what it rotates through). The boilerplate narrative text (`progresion`, the body of `mensaje_para_el_cliente`, `distribucion_comidas`) got small pools of 3-4 equivalent phrasings per language, all written to match the trainer's documented voice (`docs/metodo_entrenador.md`: plain, pedagogical, adherence-and-safety-before-progress) — chosen per client from the same seeded RNG. Deliberately *not* applied to `fuentes_proteina_sugeridas`/`fuentes_carbohidrato_sugeridas`/`fuentes_grasa_sugeridas`: those are already an exhaustive, filtered menu of every safe option for that client's diet type and allergies (see `food_bank.py`), not a boilerplate template — shuffling or trimming that list would remove real information, not add personalization.

**A quietly-outdated docstring caught in passing:** `dieta_reglas.py`'s module docstring called the engine "100% deterministic" — accurate before this change, and worth correcting rather than leaving as a claim the code no longer keeps.

Existing tests that had asserted one exact legacy string (e.g. `"Sobrecarga progresiva" in borrador["progresion"]`) were rewritten to check pool membership instead — those assertions had started passing coincidentally once variants existed (the fixed `id_cliente` in the shared `perfil_base` test fixture happened to land on variant 0), which would have made them a silent trap for the next unrelated edit to the variant pools. New tests assert both properties directly: regenerating the same client twice produces identical output, and sampling ~15 distinct client IDs on an otherwise-identical profile produces more than one distinct result (a two-sample equality/inequality check would itself have a 1-in-4 chance of coincidentally colliding, since only 4 phrasing variants exist per string).

## From a plain-text attachment to a fillable PDF form, after real-world testing found the actual problems

The adherence check-in loop (see the earlier entry on `main.py`) shipped with a plain-text `.txt` checklist attachment. Live-testing it — the project owner emailing themselves a real draft and replying — surfaced two real problems in quick succession, plus a UI cleanup request along the way, and led to redesigning how the plan reaches the client at all.

**Bug 1 — a Notion secret gap, not a code bug:** "Check if it was sent" failed with `Missing NOTION_CHECKINS_DATABASE_ID`. Verified locally that `.env` resolved it fine, which pointed at the one place that *wasn't* checked: Streamlit Cloud's own secrets store, a completely separate system from both the local `.env` and the GitHub Actions repo secrets set up for `inbox_trigger.yml` earlier the same day. Not something this code can detect or fix — flagged to the project owner to add the missing secret in the Streamlit Cloud dashboard.

**Bug 2 — a self-test exposed a real flaw in the just-shipped search query.** `buscar_respuestas_adherencia()`'s search had been scoped with `-in:sent -in:drafts` specifically to exclude the trainer's own outgoing copy of the plan email (same subject, same attachment name) from being misread as a client reply. Testing by emailing the account itself broke that: Gmail labels a self-to-self reply as *both* `SENT` and `INBOX`, so excluding `sent` silently excluded the genuine reply too — reproduced directly against the real mailbox (`labelIds: ['UNREAD', 'IMPORTANT', 'SENT', 'INBOX']`) before writing the fix. Replaced with a label-independent signal: the standard RFC 5322 `In-Reply-To` header, present on every genuine reply and absent from an original message, regardless of which mailbox sent either one.

**The actual root cause of "nothing appeared in Check-ins," though, was neither of those:** the test reply had no attachment at all. Confirmed by inspecting its real MIME structure — just `multipart/alternative` with `text/plain`/`text/html` parts, nothing else. Gmail (like most mail clients) doesn't carry an original message's attachments into a reply automatically; only "Forward" does, and not consistently even then. The search and reply-detection logic were both working exactly as intended — there was genuinely nothing to find. This reframed the actual product problem: a `.txt` file gives a client no signal at all that it's meant to be filled in and reattached, and the email body's instructions weren't prominent enough either.

**The redesign, decided with the project owner:** the email body shrinks to a brief note (still keeping `mensaje_para_el_cliente` — the trainer's own personal line — but dropping `resumen_enfoque`/macros, which now live in a proper document instead of being duplicated inline), plus two attachments: a plain informational PDF for the diet, and a **fillable PDF form** for the routine checklist, replacing the `.txt` file entirely. Two alternatives were considered and rejected: **.docx** (would need a second read path — parsing Word documents back — for no real benefit over a form-native format, and isn't guaranteed to open on every device without a specific app) and **Google Docs** (would need an additional OAuth scope and sharing-permissions logic, and wouldn't really be "an attachment" the way the project owner asked for). A fillable PDF form's checkboxes and text fields are natively editable in essentially any PDF viewer — desktop or mobile — without installing anything.

**reportlab to write, pypdf to read** — `agents/pdf_generador.py`'s split. reportlab's canvas-level `acroForm` API is the mature, standard way to author AcroForm fields in Python (checkboxes, text fields, at explicit x/y positions); the diet PDF, which just needs to flow variable-length text and lists without any interactivity, uses reportlab's higher-level Platypus framework instead (`SimpleDocTemplate`/`Paragraph`/`ListFlowable`) for automatic wrapping and pagination — the checklist's fixed-position form fields don't fit that model, so it stays on the lower-level canvas API. pypdf's `PdfReader.get_fields()` reads a filled form back as a flat `{field_name: {"/V": value}}` dict — confirmed with a real round-trip spike (generate → `pypdf.PdfWriter.update_page_form_field_values()` to simulate a client filling it in → read back) before writing the real module, the same "verify the actual API shape against reality, not documentation" discipline as the Notion `data_sources` fix earlier. Both are free, pure Python, no system dependencies, lazily imported (same convention as `pdfplumber`/`google-api-python-client` elsewhere) — the default rule-engine pipeline never needs either installed.

**Field names stay in sync with the reader by construction**, not by re-parsing: `generar_pdf_checklist()` names each session's checkbox `session_1`..`session_N` and uses fixed constants (`CAMPO_DIAS_DIETA`, `CAMPO_NOTAS_RUTINA`, `CAMPO_NOTAS_DIETA`) for the rest; `leer_checklist_pdf()` reads those same names back. This is strictly simpler than the old text-tag parser it replaced: the diet-days-followed *total* (`DIAS_SEMANA_DIETA`, still fixed at a week) no longer needs to be regex-extracted from the reply at all, since the PDF the project itself generated always has exactly that field, known ahead of time — one whole regex and its edge cases disappeared entirely.

**Disambiguating which PDF is the checklist** matters now that two get attached: `es_checklist_pdf()` checks whether a PDF has an AcroForm with the expected field names, and `gmail_client.py`'s `_extraer_checklist_pdf()` prefers a filename match first (`adherence-checklist.pdf`/`checklist-adherencia.pdf`) before falling back to that field check — covers a client renaming the file, or a reply that carries the diet PDF along too (e.g. from forwarding the whole original chain instead of replying).

**A bug caught by re-reading my own new code, not by running it:** `generar_pdf_checklist()` took `borrador_dieta` as a parameter but the first draft of the function body never actually used it — silently dropping the "Target: X kcal/day, Y g protein" context line the old text checklist used to show above the diet question. Caught during self-review before shipping, not from a test failure (nothing would have failed — an unused parameter isn't an error); fixed by actually printing that line, using the same real end-to-end test (generate → inspect extracted text) to confirm it now renders.

**Also in this pass:** removed a "📋 Saved to Notion — open it" caption from the approval panel (`ui/app.py`) at the project owner's request, including the now-dead `notion_resultado_url` session-state assignment and both translation-dict entries behind it, rather than leaving unreachable code and unused keys in place.

## A third example client caught a real bug: vegans were being offered fish

Adding `examples/cliente_ejemplo_3.json` (Ana, vegan, tree nut allergy, general-health goal — a genuinely new combination the first two example clients didn't cover) and looking at her actual generated diet turned up a real correctness bug: `fuentes_grasa_para()` suggested "Oily fish (EPA/DHA)" as a fat source despite `tipo_dieta` being `"vegana"`.

**Root cause:** `FUENTES_CARBOHIDRATO` and `FUENTES_GRASA` in `food_bank.py` never had a `tipos_dieta` key at all — only `FUENTES_PROTEINA` did, and only `fuentes_proteina_para()` filtered by it. `fuentes_carbohidrato_para()`/`fuentes_grasa_para()` filtered allergies/intolerances but silently skipped diet-type filtering entirely. Existing test coverage (`test_vegan_diet_filters_out_animal_protein`) only ever exercised the protein path, so this had no test pinning it down either way.

**Why this stayed hidden:** every existing example client is either omnivorous (client 1) or vegetarian without hitting this specific case in a way that got inspected closely (client 2 — vegetarian — *did* have the bug in its own generated output the whole time, `output_dieta_2.json` was quietly suggesting fish, but nobody had looked at that specific field). It took building a genuinely new client profile and actually reading its output — not just its verdict — to notice.

**Fix:** added `tipos_dieta` to every entry in `FUENTES_CARBOHIDRATO`/`FUENTES_GRASA` (all universally compatible today except "Oily fish", which is now `{"omnivora"}` only) and made both filter functions check it, mirroring `fuentes_proteina_para()`. Declared explicitly on every entry rather than defaulting missing `tipos_dieta` to "always allowed" — an explicit fact that's checked (`test_every_food_declares_which_diets_allow_it`) beats an implicit assumption that silently stops being true the next time someone adds a non-universal entry. Regenerating the example outputs confirmed the fix: `output_dieta_2.json`'s (real, committed) fat-source list lost "Oily fish" as a side effect, `output_dieta_3.json` never had it.

**The adherence loop, shown end to end for the first time:** `examples/checklist_relleno_3.pdf` is Ana's checklist filled in the same way the test suite simulates a client filling it (`pypdf.PdfWriter.update_page_form_field_values()` — what a real PDF viewer produces, driven programmatically instead of by clicking), and `examples/output_checkin_3.json` is what `leer_checklist_pdf()` + `resumir_adherencia()` extract from it — the exact shape that would land in Notion's Check-ins database. Neither of the first two example clients had adherence-loop artifacts at all; anyone browsing the repo previously had to read code to understand what that loop actually produces.

## The knowledge base had a hole exactly where the method's own priorities pointed

`docs/metodo_entrenador.md` §1 states the method's priorities in order: *"1) Adherence · 2) Safety · 3) Progress."* Adherence outranks even progress. Yet training, nutrition, and safety each had a `docs/base_conocimiento/` note grounding them in real research — adherence, the explicitly top-ranked priority, had none. This became a visible gap only after this session's earlier work built the adherence check-in loop (`agents/pdf_generador.py`, `agents/adherencia_parser.py`, `main.py`) without ever citing why any of its specific design choices (a simple Low/Medium/High rating, a deliberately short one-page form, a non-judgmental "nothing here is graded" tone) were the right ones — they were reasonable calls made on instinct, not choices backed by evidence the way the rest of the method is.

Researched three real, verifiable sources (used the `update-knowledge-base` skill's process — position stands and peer-reviewed meta-analyses first, verified by actually reading them, not assumed from a headline):

- **Vetrovsky et al. 2022 (BJSM, 85-study meta-analysis):** self-monitoring combined with a human component (counseling, goal-setting) outperforms self-monitoring alone by ~926 steps/day post-intervention, decaying to ~413 steps/day at follow-up — the benefit fades without ongoing human follow-up. Directly validates the check-in loop's actual purpose: `valoracion_desde_ratios()`'s docstring already said *"the trainer's own read of the free-text notes always matters more than this number"* before this research was found — the evidence confirms that instinct rather than originating it.
- **Harvey et al. 2019 (*Obesity*, n=142, 24 weeks):** tracking *frequency* predicted weight-loss success better than time spent per session (1.6 vs. 2.4 log-ins/day for <5% vs. ≥5% weight loss, p<0.001), and the time cost per session fell by roughly a third over 6 months as the habit got faster. Backs the checklist's minimal, one-page, under-a-minute design as a real lever on outcomes, not just a UX nicety.
- **Lally et al. 2010 (*European Journal of Social Psychology*, n=96, 84 days):** habits take a median 66 days (range 18–254) to become automatic, and missing a single day doesn't measurably disrupt that process. Backs the checklist's non-judgmental tone directly — a skipped session isn't a failure state, and nothing in the rating should treat it as one.

New note: `docs/base_conocimiento/adherencia_y_cambio_de_conducta.md`, added to `docs/base_conocimiento/00_indice_fuentes.md`'s index. Cross-referenced from the two connected code locations (`adherencia_parser.py`'s rating docstring, `pdf_generador.py`'s checklist-brevity docstring) rather than left as a standalone doc nobody browsing the code would find — same cross-referencing convention `rutina_reglas.py`'s knee-injury notes already use for `seguridad_poblaciones_especiales.md`. No rule-engine numeric constant needed updating (this note backs existing design choices with evidence rather than feeding a new number into generation), so nothing in the pipeline's actual output changed — verified with `run_pipeline_demo.py` regardless, per the skill's standard process.

## Free-only guardrail

Reconfirmed while planning next steps: the **only** piece of this project that would
ever require a paid API key is the optional `motor="llm"` path (pay-per-token
Anthropic API calls). Every other planned addition — the test suite above, deploying
the Streamlit demo, a bloodwork PDF parser, Gmail/Notion connectors — uses either
local libraries or free-tier OAuth APIs. `motor="llm"` stays designed-but-untested
against the real API and is treated as strictly optional: the project's "fully free"
promise does not depend on it ever being exercised.

## Automated new-client intake: a form instead of free text, and a genuine testing limit disclosed rather than hidden

The last piece of the "build everything" batch of improvements: a prospective client fills in an intake PDF and emails it back, and the pipeline runs on it without the trainer retyping anything — mirroring the adherence-checklist loop already built earlier the same session, but for the *first* contact with a client instead of a follow-up.

**Why a PDF form, not free text parsed by an LLM:** the intake schema (`perfil_cliente`) is the one place injuries, allergies, and pregnancy status enter the pipeline — exactly the fields `validator_agent.py` exists to defend, and the free-only guardrail above already rules out `motor="llm"` for anything in scope here. Free-text parsing (regex or otherwise) of an open-ended email is the wrong tool for safety-critical structured data: a client writing "no lo tengo" instead of "ninguna" would be gambling on a parser's coverage. A fillable form, by contrast, only ever produces a fixed, known set of field names — `leer_intake_pdf()` never has to *infer* what a checkbox means, only read whether it's checked. Same reasoning `pdf_generador.py`'s checklist already established; extended here to the intake side too.

**`salud.lesiones` — a real schema/form mismatch, deliberately simplified rather than worked around:** the JSON schema (see `admission/ficha_cliente_template.md`) allows an arbitrary list of injuries, each with its own zone/description/status. A PDF form has no natural "repeat this block N times" primitive — reportlab's AcroForm API positions fields at fixed coordinates, not a dynamic list. Rather than building a fixed number of injury slots (most of which would sit empty and confuse a client filling the form) or a workaround that doesn't really fit either, `agents/pdf_intake.py` flattens injuries to one "Do you have an injury?" checkbox plus one free-text description field, reconstructed as a single-item `lesiones` list on read. This is a real loss of structure (a client with two unrelated injuries can only describe both in one text box) — accepted because `validator_agent.py`'s actual safety check only ever needs *whether* an injury exists and enough free text for the trainer to read during the mandatory human review; it never branches on the count of injuries.

**Distribution of the blank form was deliberately left manual, not automated:** no Gmail-sending flow was built to hand the blank intake PDF to a prospect — building an automated "send this to a new address" flow would mean composing and sending unsolicited email to an address not yet in any client record, a materially different, higher-risk action than replying inside an existing thread (which is all `gmail_client.py` does anywhere else in this project), and squarely the kind of thing the human-in-the-loop design here avoids doing without the trainer's explicit say-so each time. What *was* built: `examples/blank_intake_form.pdf`, generated once via `generar_pdf_intake()` and committed as a real artifact — the same "make the loop visible without reading code" pattern already used for the adherence checklist example — so the trainer has a concrete file to share however they already reach prospects (a fixed link, a message, whatever channel brought the lead in), and anyone browsing the repo can see exactly what a prospect fills in.

**`buscar_intakes_nuevos()` could not be tested fully end-to-end against the real mailbox — a genuine, disclosed limitation, not a gap papered over:** every other piece of this feature was verified against real credentials (Gmail search/parsing mechanics via the already-proven `buscar_respuestas_adherencia()` code path; Notion dedup/save via `existe_cliente_para_mensaje()`/`guardar_registro_cliente()` against the live workspace). Attempting to also inject a fully realistic *incoming* test message failed: `servicio.users().messages().insert()` returned `403 Insufficient Permission` — the `gmail.compose` scope permits creating drafts but not inserting arbitrary messages into the mailbox as if they'd arrived normally (this predates the later, separate decision to add `gmail.send` for the client portal's magic links — see the entry below — which doesn't grant `messages().insert()` either; it only allows *sending* a new message this project's own code composes, not fabricating one that looks like it arrived from someone else). Rather than widening the scope just to make one test more realistic, the gap is covered by mocked-network tests (`tests/test_gmail_client_network.py`) that exercise the actual message-parsing/PDF-extraction logic against a fabricated but structurally accurate Gmail API response, plus the real-credentials coverage of every *other* moving part. Documented here instead of left implicit, per this project's own standard of disclosing test-coverage gaps rather than letting a green test suite imply more than it proves.

**The human-in-the-loop guarantee holds even for fully automated intakes:** `main.py`'s `procesar_intakes_nuevos()` runs the real pipeline and saves a summary record to Notion so the trainer has an early heads-up, but it never creates a Gmail draft and never sends anything — that still only happens from `ui/app.py`'s "Approve" button, exactly as for a manually-typed intake. The new `ui/app.py` file-uploader (`_cargar_ficha_desde_pdf()`) closes the loop from the trainer's side: instead of retyping a client's mailed-back form, the trainer uploads the same PDF and reviews/approves it through the identical panel already used for every other client — one alternative front door into the same reviewed pipeline, not a new unreviewed path.

**`id_cliente` generation matches the existing manual-form convention** (`f"cliente_ui_{_slug(nombre)}"`) for PDFs uploaded through the UI, and a message-ID-derived id (`f"auto_{id_mensaje[:12]}"`) for `main.py`'s fully automated path — both stable across re-runs of the same input (a re-uploaded PDF or a re-scanned email produces the same `id_cliente` and downstream seeded variety, per `agents/variacion.py`), never derived from wall-clock time.

## A client-facing portal, and the one deliberate exception to "never sends automatically"

The last of the "build everything" batch: a magic-link portal where a client can see a summary of their plan and log a check-in directly, without the PDF-checklist-by-email loop at all. This one needed a real architectural conversation before writing any code, not just an implementation-detail call — flagged to the project owner directly rather than decided silently, the same discipline this project applies to every other hard-to-reverse choice.

**Why this one needed asking first:** every prior Gmail feature in this project — including the intake automation right above — was built specifically to *never* send a real email, enforced by the `gmail.compose` OAuth scope itself (see `gmail_client.py`'s module docstring, and `docs/highlights.md` #3, the single most load-bearing "defensible decision" this whole project makes). A magic link is only useful if it actually lands in the client's inbox; a draft the trainer has to open and manually forward defeats the entire point of a self-serve portal. That's not an implementation detail — it's a real trade-off against the project's own headline safety property, so two options were put to the project owner directly (widen the Gmail scope to `gmail.send`, or route just this one email through a separate transactional-email service and leave Gmail untouched) rather than picked unilaterally. The project owner chose widening the scope.

**Keeping the blast radius as small as the chosen option allows:** `gmail.send` is a real, permanent capability — that Gmail account can now send mail for real, full stop, Google's API doesn't offer a narrower "send only these specific things" scope. What's controllable is how much of this codebase is allowed to use it: `mcp/gmail_client.py`'s new `enviar_enlace_portal()` is the *only* function anywhere in the project that calls `messages().send()` rather than `drafts().create()` or a read-only endpoint (locked in by `test_scopes_include_send_for_the_portal_link_exception` and `test_enviar_enlace_portal_sends_not_drafts`, which explicitly asserts `drafts().create()` was *not* called). It's reachable from exactly one button in `ui/app.py`'s approval panel, gated the same way Gmail-draft-creation already is (an approved plan, and — on the public demo — the same `APP_APPROVAL_PASSWORD` dialog that already gates approval itself). And the email body is a fixed, code-defined template with exactly one variable slot — the link itself — never free text a trainer or client could inject content into.

**Re-authorization is a real, disclosed follow-up step, not something this session could complete:** widening `SCOPES` in code doesn't retroactively widen an already-issued `token.json` — Google enforces scope at the API call, same as every prior scope change this project has made (`gmail.metadata` → `gmail.readonly`, documented earlier in this log). Re-running the OAuth consent flow needs an interactive browser session on the project owner's own machine; it can't be done from here. Until that happens (locally, and on Streamlit Cloud/GitHub Actions if the portal is ever used from there), `enviar_enlace_portal()` will fail with a clear "needs re-authorization" `GmailClientError` rather than silently doing nothing — the existing credential-checking path in `_obtener_credenciales()` already produces that failure mode for free. For the same reason, this session never attempted a real send to verify `enviar_enlace_portal()` end-to-end (it would either fail outright under the still-old token scope, or, worse, actually succeed and mail a real test message from the project's real Gmail account without a specific, in-the-moment go-ahead for that exact send) — covered instead by `tests/test_gmail_client_network.py`'s mocked-network tests, the same tier already used for `buscar_intakes_nuevos()` above.

**Stateless, signed tokens instead of a token database (`agents/portal_tokens.py`):** a magic link needs to prove it was issued by this app and hasn't expired, without adding the first piece of real backend state this project has ever needed (see `verificar_envio()`'s docstring on why send-detection is trainer-triggered instead of a background job — same minimal-infra instinct applies here). The token is its own payload (`email`, the Notion page ID, an expiry timestamp), base64url-encoded with an HMAC-SHA256 signature appended — `hmac`/`hashlib`/`base64`/`json`, all standard library, zero new dependencies. Verifying needs no network call and no lookup table at all. The real cost of this choice: there's no way to revoke one already-issued link early (no registry to remove it from) — accepted the same way the project accepts its other minimal-infra trade-offs elsewhere, bounded by a short default validity window (7 days) and, as a blunt last resort, rotating `PORTAL_SECRET_KEY` invalidates every outstanding link at once.

**No second copy of the plan anywhere:** the portal's "view your plan" screen reads back the exact same summarized Clients record `guardar_registro_cliente()` already saves (name, the routine+diet summary, verdict, admission date) via the new `notion_connector.obtener_registro_cliente()` — no new Notion database, no new persistence layer for the full generated routine/diet JSON. This does bound what the portal can show to whatever's already in that 2000-character truncated summary, not the complete draft — a real, accepted scope limit rather than a reason to build a second storage layer just for this one screen.

**Check-in submission reuses the exact same data shape and formatting as the PDF checklist**, not a parallel implementation: the portal's form (sessions completed/planned, days-diet-followed/total, two notes fields) feeds `agents/adherencia_parser.py`'s existing `resumir_adherencia()`/`valoracion_desde_ratios()` — the same functions `main.py`'s PDF-based adherence loop already uses — and writes to Notion via the same `crear_registro_checkin()`, tagged the same `"Adherence check-in"` type. No new Notion schema, no second rating heuristic to keep in sync with the first.

## Two real-world corrections to the portal's check-in form, caught by actually looking at it

Live-testing the just-shipped portal against the project owner's own real Notion record surfaced two problems the design hadn't accounted for — both fixed the same day, before either shipped as a "final" version.

**Completed-vs-total validation needed a real interaction to reveal it wasn't reactive enough for `st.form`:** the first version wrapped the whole check-in in `st.form` for a single "submit everything at once" click. Adding "completed can't exceed total" validation exposed why that was the wrong container choice here: a form doesn't rerun until submit, so a `max_value` on "completed" that depends on the *live* value of "total" — the client just changed it — can't take effect until after the fact, inside a form. Switched to standalone widgets, the same trade-off `_formulario_ficha_nueva()` already documents for the exact same reason (conditional/reactive fields need an immediate rerun). Verified the actual clamping mechanic in isolation first (a throwaway two-widget script) before touching the real form: lowering "total" below the current "completed" value doesn't clamp it down to the new max, it resets to the widget's own default — different from what might be assumed, but still enforces the real invariant (completed never exceeds total), so accepted as-is rather than fought.

**The diet-days constraint and the routine-sessions constraint aren't actually the same rule, corrected after the first attempt over-applied it:** the initial fix capped *both* "sessions completed" and "days followed the diet" at their respective totals. That's correct for diet (you can't follow a diet for more days than exist in the check-in period — a hard, definitional bound) but wrong for routine sessions — a client can genuinely train *more* than the plan called for (an extra session), and the cap was silently rejecting a real, legitimate value. Fixed by removing the hard cap on routine sessions and adding an explicit "I trained more than planned" checkbox that raises the ceiling when checked — a discoverable, intentional way to report an over-achievement rather than either silently allowing any number (too easy to fat-finger a typo) or blocking a genuine case. Diet keeps its hard cap, unchanged, since that constraint really is definitional rather than a target the client might exceed. Both totals also now default to 7 (a full week) rather than the diet-only default this originally had, at the project owner's explicit request, so an early check-in mid-week is still just as easy to submit accurately.

## Trainer gets notified automatically when a client checks in — the second (and only other) function allowed to send

Requested directly by the project owner right after the portal validation fixes: when a client submits a check-in, the trainer's own inbox should get a summary and a suggested next step, not just a silent Notion row they'd have to go looking for.

**Why this doesn't touch the "never contacts a client automatically" guarantee, even though it's genuinely automatic (no button):** the recipient is the trainer's own address (`TRAINER_NOTIFICATION_EMAIL`), never the client's. The project's core promise has always been specifically about not emailing *clients* without review — `gmail_client.py`'s module docstring is updated to say this explicitly: the two functions allowed to call `messages().send()` both send *to* the trainer's side of the relationship (the portal-link button is trainer-triggered *and* trainer-approved-content; this one is trainer-triggered by being the trainer's own inbox), never unsolicited content *to* a client.

**Best-effort by construction:** `enviar_notificacion_checkin()`'s failure (missing config, expired credentials, a Gmail API error) must never block the actual check-in from being saved to Notion — `ui/app.py` calls it only *after* `crear_registro_checkin()` has already succeeded, and swallows any exception from it the same way `actualizar_email_cliente()`/`marcar_email_enviado()` already do elsewhere in this file. A client's submission succeeding or failing was never meant to depend on whether the trainer happens to have this optional notification configured.

**A new, reusable heuristic instead of a bespoke summary for this one email:** `agents/adherencia_parser.py`'s new `sugerencia_seguimiento(valoracion)` gives a short, rule-based "what to consider next" line from the same Low/Medium/High rating `valoracion_desde_ratios()` already computes — High points toward a small progression, Medium toward a quick check-in call before adding difficulty, Low toward simplifying the plan or addressing a barrier rather than pushing harder. Grounded in the same evidence already backing this whole check-in loop (`docs/base_conocimiento/adherencia_y_cambio_de_conducta.md` — Lally et al. 2010 on a missed day not being a failure state is specifically why "Low" reads as "worth a conversation," not "the client failed"). Deterministic and free, matching every other rating/summary function in this project — no LLM call for what a lookup table already does well.

## A transport-level failure was crashing the app, and the portal check-in form got a real redesign

Live-testing the portal check-in form surfaced a real crash: every one of the eight network-touching functions in `mcp/notion_connector.py` only caught `notion_client`'s `APIResponseError` — a transport-level failure (DNS, connection reset, timeout) never reaches the point of getting an HTTP status back, so it raises `httpx.HTTPError` instead, which propagated uncaught and took down the whole Streamlit app with a raw traceback instead of the project's usual "degrade gracefully, never crash the app for an optional feature" behavior. Reproduced live (a real `httpx.ConnectError`) rather than found by inspection. Fixed by catching `(APIResponseError, HTTPError)` everywhere and wrapping both into the same `NotionClientError` every caller already handles — this is very likely the actual cause behind earlier reports of the app "appearing broken."

Same session, the check-in form itself got two corrections, both caught by actually looking at it rather than by a test: "total" and "completed" now render in that order (total first) instead of side-by-side columns that read backwards, using sliders instead of bare number boxes for a clearer sense of where "completed" sits relative to "total," plus an `st.progress()` bar with an explicit fraction underneath each — visual polish, but the kind that only surfaces from actually looking at the rendered widget, the same discipline behind the entrance-transition revert and the CSS selector fix earlier in this log.

## Closing the real-weight loop: a genuine architecture reversal, chosen deliberately after seeing the actual trade-off

The next planned improvement — "let a client report their real weight, and let the trainer revise an existing client's plan with it" — split into two options only once actually scoped out: log the weight and let the trainer retype a fresh intake by hand to regenerate (small, in keeping with this module's original "no second copy of the plan anywhere" stance), or persist enough of a client's record to genuinely reload and edit it (bigger, and a direct reversal of that stance). Put to the project owner as an explicit choice rather than assumed — this reverses a documented design decision (`obtener_registro_cliente()`'s original docstring), not an implementation detail, and the same "ask before a hard-to-reverse architectural call" discipline applied to the `gmail.send` decision earlier applies here too. The project owner chose the bigger option.

**"Full Profile (JSON)" makes Clients a real, editable record, not just a summary:** every Clients page now also carries the complete `perfil_cliente` as a chunked `rich_text` property (`_dividir_bloques_notion()`/`_unir_bloques_notion()` — a single block is capped at 2000 characters, a full profile routinely isn't, so it's split across several and reassembled on read). `obtener_registro_cliente()` — the client portal's own read path — deliberately stays untouched, reading only the same summary fields it always has; nothing client-facing ever reads the full profile. Only two new, trainer-only functions do: `obtener_perfil_completo()`/`buscar_cliente_por_email()`.

**Verified end-to-end against the real workspace, not just mocked:** generated a real plan through the actual pipeline, saved it, looked it up by email, and confirmed the reloaded profile was byte-for-byte identical to what went in (`registro["perfil"] == perfil`) — then revised it (changed weight, regenerated) and confirmed `actualizar_registro_cliente()` updated the *same* Notion page ID rather than creating a second one. All four steps run against the live API, the same standard this project has applied to every other Notion-touching feature this session.

**Revising updates in place — "Clients" stays one master record per client, even now:** `actualizar_registro_cliente()` calls `pages.update()`, not `pages.create()`, reusing `_construir_propiedades_pagina()` so the request shape can't drift from what a fresh save builds. It deliberately leaves "Email Sent" untouched (guardar_registro_cliente() always initializes it to `False`) — revising a client's plan doesn't undo what the trainer already confirmed about the *original* plan's send status.

**The "Revise client" UI reuses `_formulario_ficha_nueva()` completely unmodified**, rather than building a second, parallel editable form: `_campos_formulario_desde_perfil()` maps a loaded profile onto the exact `st.session_state` keys that form's ~30 widgets already read, and pre-seeding session_state before those widgets render is the standard, documented Streamlit pattern for a programmatic default value. The one real gap: `analitica_pdf` (the bloodwork upload) has no Streamlit API for pre-seeding a `file_uploader` with a file, so a revision doesn't re-attach whatever bloodwork PDF the original intake carried — not fixable without a new place to persist that PDF's raw bytes too, which nothing else in this codebase does for the intake side either. Disclosed in the function's own docstring rather than left as a silent surprise.

**"Weight (kg)" on Check-ins closes the loop the rule engines already claimed was closed:** `dieta_reglas.py`'s own generated message has always told the client their plan "gets adjusted based on real weight and energy over the first few weeks" — a promise with no mechanism behind it until now. The portal's check-in form gained an optional, checkbox-gated weight field (same "share something extra" pattern as the injury/pregnancy detail fields in the manual intake form), visible in the trainer's existing "Adherence history" view and mentioned in the trainer notification email — three surfaces, zero new heuristics, all reading the one new property.

**A real automation-testing lesson worth recording:** live-verifying the "Revise client" flow through an actual browser session surfaced that `st.button()`'s click state and `st.text_input()`'s value only sync to the Python backend through a real React-controlled-input change event — setting a DOM element's `.value` directly, or a synthetic `.click()`, doesn't reach Streamlit's WebSocket layer the way an actual user interaction does. Not a code bug (server logs stayed clean throughout); a reminder that "the DOM looks right" and "the widget's value reached the server" are different claims, worth checking separately when verifying any Streamlit interaction end-to-end.

## Closing the disclosed bloodwork gap, and giving clients their own history in the portal

Two smaller, immediately-actionable pieces of feedback from the project owner, right after the "Revise client" feature shipped.

**Bloodwork markers now survive a revision without ever needing the original PDF again — the project owner's own framing, not a re-design:** the "Revise client" entry in `docs/decisiones.md` above disclosed a real gap (a revision can't re-attach the original bloodwork PDF, since `file_uploader` has no Streamlit API for pre-seeding a file). The fix isn't re-attaching the file at all — it's not re-parsing it in the first place. `salud.analitica_adjunta` (already inside "Full Profile (JSON)", already round-tripping perfectly) already *contains* the extracted markers; `_formulario_ficha_nueva()` only ever discarded them because it unconditionally rebuilt that field from `analitica_pdf`, defaulting to empty when nothing new was uploaded. `_campos_formulario_desde_perfil()` now also pre-seeds `analitica_previa`, and the form falls back to it instead of an empty default when no new PDF is uploaded — a genuinely new upload during a revision still takes priority and replaces it outright, never merges. A caption makes the fallback visible ("Keeping the bloodwork markers already on file...") rather than silent, so a trainer flipping through a revision isn't left guessing whether old data is still in play.

**Verified against the real workspace, including the part that matters most — that a carried-forward marker still triggers the same safety check as a freshly-uploaded one:** added an out-of-range Vitamin D marker to the same test client from the "Revise client" verification above, saved it, then reloaded and regenerated *without* touching the bloodwork uploader at all. The caption appeared with the right date, and — the real proof — the regenerated plan came back `revision_reforzada` with `"Bloodwork marker out of range: Vitamin D = 18 ng/mL"` in the verdict, exactly as if the PDF had been re-uploaded. `validator_agent.py`'s defense-in-depth doesn't know or care where a marker came from; carrying it forward through session_state rather than a fresh PDF parse doesn't weaken that check at all.

**The client's own portal now shows their check-in history, reusing the trainer's exact row-formatting code:** `_render_historial_checkins()` is the trainer's adherence-history block (date, type, rating, weight, notes), pulled out into its own function and called from both `_panel_aprobacion()` (by the email the trainer typed) and the new expander in `_vista_portal_cliente()` (by `carga["email"]`, from the signed token — never something a client could type in to see someone else's history). No new query, no new formatting logic, no risk of the two views drifting apart over time — verified live by creating a real Check-ins row and confirming it rendered identically to how the trainer's own panel already shows it.

## A client roster and trend charts — and a real chart-library crash caught by live-testing, not assumed away

The next two items in the same prioritized list (D: an "all clients" overview; C: a trend chart over the check-in data now being collected), built together at the project owner's request.

**`listar_clientes()`/`ultimo_checkin_por_cliente()` — two independent, best-effort queries, not one joined one:** Notion's API has no native "latest row per group" query, so getting "each client's most recent check-in" means fetching the whole Check-ins database sorted newest-first and grouping by email in Python — a single query, not one per client (which would scale badly). Deliberately kept as a *second*, separately-failable call from `listar_clientes()`: if the Check-ins query fails for any reason, the roster itself (from the Clients database) still renders, just without the adherence column — the overview degrades a column at a time, not entirely.

**A visible "who needs attention" signal, not just a data dump:** `_etiqueta_atencion()` prefixes a client's most recent rating with ⚠️ when it's Low — the one-line reason this view exists at all (per the project owner's own framing when this was proposed: "see who needs attention" without opening Notion or looking clients up one at a time).

**The trend chart reuses `_render_historial_checkins()`'s existing data, not a new query** — `_render_grafico_tendencia()` slots in right before the row list that function already renders, in both places that function is already called (the trainer's own per-client view and the client's own portal view), so both audiences get it for free from one change.

**A real crash, caught only because this was live-tested against the actual running app, not just the test suite:** `st.line_chart()` needs Altair to draw. streamlit's own package metadata lists Altair as a dependency — reasonable to assume it would just be there. It wasn't, in a real running instance of this exact app: opening the client portal (a page a *client* could hit) with two weight check-ins on file raised a bare `ModuleNotFoundError` and crashed the whole page, not just the missing chart. The 257-test suite passing gave no signal of this at all — none of those tests render a real Streamlit page, by design (see this project's own convention that `ui/app.py` isn't unit-tested directly). Two fixes, not one: `altair` (and `pandas`, which the chart-building code also needs but `st.dataframe()`'s own list-of-dicts input doesn't) are now explicit, declared dependencies in `requirements.txt` rather than relied on transitively; and `_render_grafico_tendencia()` catches `ImportError`/`ModuleNotFoundError` defensively on top of that, the same "a missing optional library degrades the feature, never crashes the page" pattern reportlab/pypdf/pdfplumber already use everywhere else in this project. Both `import pandas` calls stayed lazy, inside the two functions that actually need it — matching that same established convention, which the first draft of this code had briefly broken by importing pandas at module level.

## A privacy gap in the public demo: two sections were showing real clients' personal data to anyone

Caught by the project owner looking at the just-shipped "Clients" tab and noticing the obvious problem: every row shows a real client's email address, and on the public demo, that page has no gate at all — anyone who opens the app and clicks the tab sees it. `APP_APPROVAL_PASSWORD` already existed and already protects the "Approve" button (see the entry above on `_dialogo_aprobacion`), but that gate was scoped narrowly to *actions with side effects* (writing to Notion, creating a Gmail draft) — nobody had asked "what about sections that only *read* and display real data?" until now.

**A second, worse instance of the same gap, found while fixing the reported one:** "Revise client" has the identical problem, and arguably a bigger one — its email lookup returns a client's *complete* profile (injuries, allergies, weight, pregnancy status), not just the roster's summary row. Both sections are fixed together rather than just the one reported, since leaving "Revise client" open would have been the same class of leak with more sensitive data behind it.

**The fix reuses `APPROVAL_PASSWORD` rather than adding a second secret:** `_gate_datos_clientes()` renders a plain password prompt in place of either section's real content until the trainer enters the same password `_dialogo_aprobacion()` already checks. Deliberately a *session-level* unlock (`st.session_state["clientes_desbloqueado"]`), not a per-view prompt like the approval dialog — browsing a roster or looking up several past clients in a row is a repeated "look around" action, not a single consequential click, so re-prompting on every rerun would be pure friction once the trainer has proven who they are once. A full page reload clears it (verified live), so a client or visitor who leaves and comes back hits the gate again — nothing persists the unlock beyond the current browser session. On local dev, where `APP_APPROVAL_PASSWORD` is normally unset, both sections behave exactly as before — the same "unset = off" degradation every other optional secret in this project already follows.

**Verified live, not just read through:** ran the actual dev server with a temporary `APP_APPROVAL_PASSWORD` set, confirmed both "Revise client" and "Clients" show only the password prompt (no client data in the DOM at any point) before unlocking, confirmed a wrong password is rejected with the same "Incorrect password" message the approval dialog already uses, confirmed the correct password unlocks *both* sections at once (one shared flag), and confirmed a page reload re-locks them. The temporary password was removed from `.env` again immediately after.

## The session-level unlock wasn't enough for "Revise client" specifically — a per-lookup re-check closes the gap

Raised right after the privacy-gap fix above shipped: the session-level unlock on "Revise client" proves the trainer knew the password *once*, but from that point on, typing literally any email into the lookup field returns that client's complete health profile with zero further check that this specific lookup is legitimate — a shared/unlocked screen (or a leaked session) means "knowing a client's email" alone is enough. The "Clients" roster doesn't have the same problem (it only ever shows what the trainer's own session unlocked, not a per-record lookup by arbitrary input) and stays on the session-level gate.

**Fix: `_cargar_ficha_para_revisar()`'s lookup now re-checks `APPROVAL_PASSWORD` on every single "Load" click**, the same per-action pattern `_dialogo_aprobacion()` already uses for Approve, layered on top of (not instead of) the section's session-level unlock. A wrong password shows the same "Incorrect password" message and — importantly — never calls `buscar_cliente_por_email()` at all, so a bad guess can't even trigger a real Notion query. Skipped entirely when `APPROVAL_PASSWORD` is unset, so local dev keeps zero extra friction, matching every other optional secret in this project.

**Verified live:** with a temporary password set, a wrong password on the "Load" click showed "Incorrect password" and left the form empty (confirmed no lookup fired); the correct password went through to a real Notion query, confirmed by "No client found with that email" for a made-up test address rather than a password error.

## Two more privacy/UX corrections, requested directly after live-testing the gate

Both caught by the project owner actually using the freshly-gated app, not flagged in review.

**The gate's own copy was giving away more than it needed to:** the password prompt originally said "the same one used to approve a plan" — accurate, but an unnecessary hint to anyone probing the gate about what else that password unlocks. Removed from both languages; the prompt now just states that a password is required, nothing about what else it's shared with.

**The "never sends automatically" reassurance lines in client-facing emails were removed, at the project owner's request** — the parenthetical notes in `_construir_cuerpo_email()` (diet/routine email) and `_construir_cuerpo_portal()` (portal-link email) explaining "this was sent on purpose by your trainer, TrainFitter never sends on its own" were judged to read as unnecessary boilerplate from the client's side (a real client doesn't need TrainFitter's own internal safety guarantee explained to them in the email itself) rather than reassurance. The guarantee they described is still fully real and enforced in code (`gmail.compose`-only drafts, the one narrow `gmail.send` exception, all documented in this log and `CLAUDE.md`) — only the client-facing text explaining it was removed, not the guarantee itself.

## A real weekly meal plan, not just flat "suggested sources" lists

Requested directly: the diet PDF's protein/carb/fat bullet lists were too generic — the project owner wanted an actual 7-day plan of breakfast/lunch/dinner/snacks, built from the same free rule engine (no LLM, no new cost), that maximizes nutrient synergies and actually looks like something a trainer would hand a client.

**A new module, not more logic bolted onto dieta_reglas.py:** `agents/planificador_comidas.py` takes the macro targets `dieta_reglas.py` already computes and turns them into a real week — but the food-*selection* safety story doesn't change at all: every food the planner can ever pick comes from `food_bank.py`'s existing `fuentes_*_para(perfil)` functions, the exact same allergy-and-diet-type-filtered candidate pools `fuentes_*_sugeridas` is already built from. There's no second, parallel path into the raw food banks — which means `validator_agent.py`'s existing cross-check (already reading those `*_sugeridas` lists) covers the weekly plan automatically, with no new free-text parsing needed. The one deliberate change there: a 4th food category, `FUENTES_VERDURA` (vegetables/fruit, for fiber/micronutrients/synergy pairing), was added to `food_bank.py` and wired into that same cross-check — extending it, not creating a second, unchecked category.

**Every food now carries approximate macros_100g** (kcal/protein/carb/fat per 100g, standard nutrition-label-style reference values — not a lab measurement) so portions can be solved from the client's own kcal/macro targets. Deliberately not gram-perfect: each meal's kcal budget comes from a simple weighted split (mains get more than snacks), and grams are solved from the day's own macro *ratios* applied to that budget — the same "estimate first, adjust from real progress" philosophy `dieta_reglas.py`'s own client message already states (`docs/base_conocimiento/nutricion.md`: sustainable and close-enough beats optimal-on-paper).

**Synergy pairing is mechanical, grounded in `docs/base_conocimiento/sinergias_nutrientes.md`'s own table, not just restated as a tip:** when a meal's protein pick carries the new `"hierro_no_hemo"` tag (a non-heme plant iron source — lentils, chickpeas, tofu, tempeh, edamame), the vegetable/fruit slot for that same meal is filtered down to a `"vitamina_c"`-tagged pick specifically, and the description says so ("Kiwi adds vitamin C to help absorb the iron in tofu"). Dinner deliberately gets the day's largest share of fat, for the same reason the doc gives for vitamin D/E/K and omega-3s timing. `consejos_sinergias` (the pre-existing static tips) still covers the pairings that aren't practical to force structurally (tea/coffee timing away from iron-rich meals).

**Two portion-realism bugs, both caught only by generating and reading a real week, not by reading the code:** a first version let `rng.choice()` pick freely across the *entire* candidate pool for every meal, which produced "grilled salmon" as a snack (technically safe, just an unrealistic-looking suggestion) and, worse, solved out to 500g+ of "Assorted fruit" as a dinner's main carb (low kcal-density food, large kcal budget → absurd portion). Both fixed with targeted candidate-pool filters — whole-cut savory proteins/fish-fat excluded from breakfast/snack, low-density carbs (fruit) excluded from every meal except snacks — rather than a general-purpose "make it realistic" heuristic. Locked in as regression tests (`tests/test_planificador_comidas.py`), the same "found by actually looking, then written down so it can't silently regress" pattern as the vegan-fat-source bug earlier in this log.

**Food names inside plan_semanal's own text are the one deliberate exception to "food names stay canonical English":** `fuentes_*_sugeridas`' names have to stay English because `validator_agent.py` string-matches against them. `plan_semanal`'s prose is never read by that cross-check (it only reads the flat lists), so `planificador_comidas.py` translates food names for display right at description-build time via `food_bank.nombre_mostrado()` — the same helper `pdf_generador.py` already used, just applied one step earlier, since a pre-composed sentence can't be re-translated piecemeal at render time the way a flat bullet list can.

**The diet PDF gained a styled weekly-plan table (teal header, alternating rows, kept together across page breaks) instead of just another bullet list**, and the trainer's own on-screen review (`ui/app.py`) got the identical plan in a matching expander — a trainer approving a plan can see exactly what the client will receive without needing to open the PDF first. Both are fully optional/backward-compatible: a `borrador_dieta` without `plan_semanal` (an older draft, a hand-built test fixture, or a future `motor="llm"` response that doesn't populate it) renders exactly as it did before, section omitted rather than the page crashing — the same "missing optional field degrades gracefully" convention as everywhere else in this project. `ENTREGAR_BORRADOR_DIETA_TOOL`'s schema in `diet_agent.py` also gained `plan_semanal`/`fuentes_verdura_sugeridas`, keeping the "two interchangeable engines, one schema" invariant intact even though `motor="llm"` is still never exercised against the real API.

**Verified live, not just through the test suite:** generated a real plan through the actual running app (both languages), confirmed the weekly-plan table renders correctly in the PDF (visually inspected, not just text-extracted) and in the trainer's on-screen panel, confirmed a vegan + nut-allergy profile never leaked a restricted food into a real generated week, and confirmed the same client regenerating twice reproduces byte-identical output.

## Emailing the blank intake form to a prospect, and checking for their reply, from the panel directly

Requested directly: the "Upload a filled intake PDF" section could already *read* a filled-in form, but a trainer still had to attach and send the blank one to a prospect by hand from their own mail client, then separately go looking for the reply. Two additions close that loop from the panel itself.

**A third, narrow addition to the `gmail.send` exception:** `enviar_formulario_intake()` is the third function in this codebase ever allowed to call `messages().send()`, alongside `enviar_enlace_portal()` and `enviar_notificacion_checkin()` (see the earlier entries in this log and `mcp/gmail_client.py`'s module docstring, both updated to describe three functions now, not two). Kept as narrow as the others by design: the email template has **no variable slots at all** — not even the prospect's name, since nothing about them is known yet at this point in the funnel — the only thing that ever changes between calls is which of two fixed EN/ES (text, PDF) pairs gets attached.

**Reusing `buscar_intakes_nuevos()` rather than writing a second search function:** the existing inbox-scanning function (built for `main.py`'s scheduled cron job) already does exactly the search a "check for this one prospect's reply" button needs — it just always scanned the *whole* inbox. Gained one optional `remitente` parameter that adds a `from:` qualifier to the same Gmail query when given; `main.py`'s own call passes nothing, so its scheduled, scan-everything behavior is completely unchanged. One function, two callers, no duplicated search/parse logic to keep in sync.

**Both new actions are gated behind `APPROVAL_PASSWORD` (re-checked per click) on any deployment where it's set — a real, considered addition beyond what was asked for, made explicit rather than silently skipped:** sending is a genuine email leaving this project's real Gmail account to any address a public-demo visitor could type in (a spam vector if left open), and checking for a reply pulls back a specific prospect's personal data (name, health details) just from knowing their email — the exact same class of exposure the "Revisar cliente" gate (see the earlier privacy-gap entry in this log) already exists to prevent. Unset locally, same "off" degradation as every other optional secret in this project — a real trainer using their own local instance sees zero extra friction.

**Verified live against the real, configured Gmail account, with one deliberate limit:** the read-only "check for a reply" path was exercised for real (a made-up test address correctly came back "no reply found yet," proving the live search/query path works end-to-end), and the password gate was confirmed to block a `messages().send()` call before it could ever fire (a wrong password on "Send blank form" surfaced "Incorrect password" with no network call reaching Gmail — checked via the same gating code path, not just by inspection). The actual send path itself is covered by mocked-network tests (`tests/test_gmail_client_network.py` — confirms `messages().send()`, not `drafts().create()`, gets called, with the right attachment for each language) rather than triggering a real send during this verification pass: sending a real, live email to an arbitrary test address wasn't done without the project owner picking that address and confirming it directly, the same bar this project applies to every other real-world side effect.

## Maximal personalization: the rule engines now actually use most of what the intake form collects

The project owner's request started narrow (a new "main dietary concern" field, e.g. "anti-inflammatory," "lower gluten") and grew, mid-conversation, into a much bigger one: make both rule engines actually *use* everything a client fills in, grounded in the project's own knowledge base — and explicitly invited scoping questions rather than a guess. Four questions were asked before writing any code (level-based routine volume/complexity, how to treat disliked foods, whether stress/sleep/job type should adjust the diet and/or the routine, and whether "maximal personalization" from free text justified reconsidering `motor="llm"`); the project owner picked the more thorough option on all four, and confirmed staying 100% free (keyword matching, not real language understanding, for the free-text part).

**A real, uncomfortable finding before any code was written:** reading `rutina_reglas.py`/`dieta_reglas.py` first (rather than assuming) showed that `experiencia.nivel` (beginner/intermediate/advanced) changed nothing about the routine except its label text — a beginner and an advanced client with the same equipment got byte-identical sets/reps. `disponibilidad.minutos_por_sesion`, `nutricion.alimentos_que_no_le_gustan`/`restricciones` (disliked foods!), and every `estilo_de_vida` field (stress, sleep, job type) were collected on the intake form and then never read anywhere in either engine. This wasn't a design decision to unwind — it was dead data collection, disclosed as such rather than glossed over.

### Routine (`agents/rutina_reglas.py`)

- **Volume by level**, grounded in `docs/base_conocimiento/entrenamiento.md`'s own already-written "Adaptation by level" and "Volume: landmarks (MEV/MAV/MRV)" sections (no new research needed — the doc already said this, the code just never encoded it): beginner gets -1 set on compound/basic exercises, advanced gets +1 on both basic and isolation, intermediate is the unchanged baseline. Isolation work stays closer to constant across levels on purpose — it's inherently lower-fatigue-cost, so there's less headroom to cut or need to add.
- **Complexity bias for beginners**, derived from an exercise's own required equipment rather than a new hand-maintained field (`_complejidad()`: barbell = high, dumbbell = medium, machine/bodyweight = low) — beginners get candidates within a slot reordered toward lower-complexity options first, never excluding the higher-complexity ones outright (a beginner training only with a barbell still needs a full session).
- **A conservative -1 to basic-exercise series when the client reported high stress or under 6h average sleep**, stacking with (not replacing) the level-based adjustment, both clamped by a shared floor (`SERIES_MINIMAS = 2`) so they can never combine down to an unusably low number.
- **Session-length-aware trimming**: `minutos_por_sesion` now actually does something — under 45 minutes trims the last exercise slot, under 30 trims the last two (never below 2 exercises total), always trimming from the END of each day's template so the highest-priority compound work survives.
- Every adjustment that isn't obvious from the numbers alone (the conservative stress/sleep note, the session-length trim) gets an explicit sentence in `resumen_enfoque` — the same "never a silent, unexplained adjustment" principle already used for injury adaptations.

### Diet (`agents/food_bank.py`, `agents/planificador_comidas.py`, `agents/dieta_reglas.py`)

- **Disliked foods and additional restrictions now actually exclude**, via a new `alimentos_no_deseados()` that matches the client's free text directly against each food's own name (English or Spanish, accent-insensitive via `unicodedata` — stdlib only, no new dependency) — deliberately per-food, not per-category, since "I don't like broccoli" is about one specific food. Wired into all four `fuentes_*_para()` functions, so it automatically covers the flat suggested-sources lists AND the weekly plan (which draws from those same functions) with no separate logic. **Never treated as a safety concern**, per the project owner's explicit instruction: no `advertencias_revision_humana` entry, no validator involvement — contrasted directly in a test (`test_disliked_food_does_not_trigger_a_health_review`) against `etiquetas_excluidas()`, which still does trigger review for a real allergy.
- **A new "main dietary concern" intake field** (`nutricion.inquietud_principal`) plus a pooling function, `preferencias_texto_libre()`, that also scans the goal-in-own-words, nutrition context, and free-notes fields — a preference mentioned in any of those gets picked up, not just one specific box. `preferencias_blandas()` turns that pooled text (bilingual keyword matching, same category of technique as `etiquetas_excluidas()`) plus two *structured* lifestyle fields into soft preference tags: `"reducir_gluten"`, `"antiinflamatorio"`, `"estres_alto_o_sueno_bajo"` (high stress OR under 6h sleep), `"trabajo_sedentario"`.
- **"Lower gluten" is a real, deliberate distinction from a declared gluten allergy** — it excludes only the `gluten` tag (bread, pasta, seitan), not `gluten_trazas` (oats stay available), unlike `etiquetas_excluidas()`'s allergy path, which still excludes both. Two contrasting tests lock this in.
- **"Antiinflamatorio"/magnesium/fiber preferences bias selection, they don't exclude**: `planificador_comidas._sesgar_por_preferencias()` narrows a food category to only tagged candidates 75% of the time a match exists, falling back to the full list otherwise — enough to be clearly noticeable across a week without making the plan one-note. Verified statistically, not just by eyeballing one generated week: salmon (the only protein tagged `"antiinflamatorio"`) went from a 13% baseline share of lunch/dinner protein picks to 80% once the preference was active, averaged across 15 different client IDs.
- **The antiinflammatory tip's own wording is diet-type aware**: it names "oily fish" only for omnivore clients, since that food is never actually a candidate for a vegetarian/vegan client's plan (`food_bank.py`'s own `tipos_dieta` filter already excludes it) — caught by actually generating a vegetarian example client's plan and reading the tip, not by inspection; a first draft named oily fish unconditionally.
- Every active soft preference gets an explicit `consejos_sinergias` entry explaining *why* the week leans that way (new `_consejos_por_preferencias_blandas()`), same transparency principle as the routine side.

### Verified, not assumed

Two of the three existing example clients already had disliked foods on file (`cliente_ejemplo_1`: oily fish; `cliente_ejemplo_2`: tofu) that were silently ignored before this change — regenerating their plans now shows those foods genuinely gone from the suggested sources, a real bug fix demonstrated on data that already existed rather than a synthetic test case. `cliente_ejemplo_2` also picked up `inquietud_principal: "Would like an anti-inflammatory approach, given the old knee injury"` to demonstrate the new field on a real, already-documented client. Live-verified end to end through the actual running app (not just the 341-test suite): filled in the new field, generated a real plan, and confirmed the anti-inflammatory tip and the weekly plan's heavy lean on salmon/olive oil/nuts/colorful vegetables both rendered correctly on screen.

## Four follow-ups from a "how do we make this more valuable" conversation

Asked directly for a prioritized list of next steps once the personalization work above shipped; the project owner picked the first four and asked to start there. All four are infrastructure/rigor improvements, not new user-facing features — closing gaps the project's own conventions (mocked-network tests, coverage discipline, layered gating) already implied but hadn't been applied everywhere yet.

**Testing the code around a call this project will never actually make:** `motor="llm"`'s `_generar_borrador_*_llm()` functions had zero tests of any kind before this — not because they're untestable, but because nobody had done it. Fixed with the same "mock the dependency, test the real logic" pattern already used for Gmail/Notion, applied to a package (`anthropic`) that isn't even installed in CI on purpose (see the Free-only guardrail): `tests/conftest.py`'s `fake_anthropic` fixture injects a fake module straight into `sys.modules` before the function's own lazy `import anthropic` runs, with real `Exception` subclasses standing in for `APITimeoutError`/`APIConnectionError`/`APIStatusError` (a `MagicMock` can't be used in an `except` clause — Python requires the real thing). 31 new tests across `test_routine_agent.py`/`test_diet_agent.py` cover the dispatch (`motor="reglas"` vs `"llm"` vs invalid), a well-formed response, and every documented failure mode — all for free, no API key, no network, no real package install required.

**Coverage measurement in CI, scoped honestly, not just "we have tests":** `pytest-cov` wired into `.github/workflows/ci.yml` with `--cov-fail-under=90`, `pyproject.toml`'s new `[tool.coverage.run]` scoping it to `agents/`+`mcp/` (the tested business logic) and explicitly omitting `ui/app.py`/`main.py` (deliberately never unit-tested — verified live instead) and the `run_*_demo.py` scripts (exercised by actually running them, not by importing under pytest — counting them as "uncovered" would just be noise). The real number came out to 97%, comfortably above the 90% floor, which was chosen as a real safety margin rather than a round number. **Reading the report mattered more than generating it**: it surfaced that `validator_agent.py` — the pipeline's safety gate — had two Spanish-language cross-check paths (declared-condition/pregnancy/medication/bloodwork warnings, and the diet-allergy defense-in-depth check) that had never been exercised in Spanish at all, plus an untested defensive branch (an exercise name the local bank doesn't recognize, e.g. from a future `motor="llm"` routine, being skipped rather than crashing the cross-check). All three closed immediately, on the file where it mattered most to close them. Two smaller, real gaps in `mcp/gmail_client.py` (the large-attachment-by-id fetch path; the intake PDF's filename-renamed fallback) were closed the same way.

**A shared brute-force counter across every password-gated action:** `ui/app.py` had four independent call sites checking `password == APPROVAL_PASSWORD` (Approve, the Clients/Revise-client section gate, Revise client's per-lookup check, the intake-email send/check flow), none of them rate-limited — unlimited, instant retries against a shared secret. `_verificar_password()`/`_password_bloqueada()` centralize the check behind one `session_state` counter: 5 wrong guesses in a row locks the password out for 2 minutes, *regardless of which of the four gates the attempts came from* — switching tactics doesn't reset the budget. A real, disclosed limit rather than a false sense of security: this is per browser session, not per IP, so a full page reload starts a fresh session with its own budget (Streamlit has no server-side request throttling without extra infrastructure this project doesn't run) — still a meaningful improvement over the unlimited retries that existed before. Verified live, including forcing the lockout for real: 5 wrong attempts, then confirming the *correct* password was also rejected during the 2-minute cooldown, not just another "incorrect password" message.

**`docs/highlights.md` updated with this session's most defensible calls**, not every change — the layered privacy fix (#13), personalization verified statistically rather than eyeballed (#14), and the `fake_anthropic` testing technique (#15). 15 entries now, up from 11; `CLAUDE.md`'s own reference to that count updated to match.

378 tests passing (up from 341), lint clean, 97% coverage enforced in CI.

## Three real bugs caught by actually reading a live email and clicking through the app

All three were caught by the project owner using the real, deployed app — not by the test suite, which can assert string content but has no eyes on the whole rendered picture.

**The plan email repeated the client's name three times and read as one wall of text.** `mcp/gmail_client.py`'s `_construir_cuerpo_email()` prepends its own `"Hi {name},"` greeting, but `rutina_reglas.py`/`dieta_reglas.py`'s `mensaje_para_el_cliente` *each* bake in their own `"Hi {name}, "` too — by design, so the message reads naturally when shown standalone in the trainer's UI panel or the diet PDF (the only two other places it's ever displayed alone). Combining all three under one email meant "Hi PEPE," opened three of the first four lines. Fixed with `_quitar_saludo()`, a small helper that strips a matching leading greeting back off before splicing the two messages under the email's own single greeting — it leaves a message untouched if the prefix doesn't match exactly (a hand-edited message, say), since silently mangling text is worse than an occasional harmless repeat. The two messages now sit under short "🏋️ Your routine" / "🍽️ Your diet" section labels (matching emoji already used in the UI's own headers) instead of running together, and the closing attachment-explanation paragraph was trimmed. Locked in with new tests (`test_email_body_does_not_repeat_the_clients_name_in_the_greeting`, `test_email_body_has_a_labeled_section_per_message`, plus direct tests of `_quitar_saludo()` itself, including the "leaves it alone" defensive case).

**One of the four routine message variants read as broken English.** `"— your body learns before it forces."` is a close-to-literal echo of a phrase in `docs/metodo_entrenador.md`'s "real phrases from the trainer" list — deliberately kept there as the fictional trainer's own documented voice, not touched. But the *rendered, client-facing* copy in `rutina_reglas.py` needs to actually parse as English regardless of its inspiration; reworded to `"— you learn the movement before you load it."`, same meaning (technique before load), grammatical. `examples/output_rutina_1.json` (a committed demo artifact, not test-asserted) was regenerated to pick up the fix.

**Google Drive's/Gmail's built-in PDF preview can't fill the checklist form.** Confirmed this is a viewer limitation, not a bug in the PDF itself: `reportlab`'s `AcroForm` API (used to author the fillable fields — see `agents/pdf_generador.py`'s own DESIGN note) never sets the PDF's `/NeedAppearances` flag, and more fundamentally, Drive's in-browser preview pane is a mostly-read-only renderer that doesn't reliably support interactive AcroForm filling for *any* PDF, regardless of how it was generated — unlike Adobe Reader, Preview, or a dedicated PDF app. Not worth hacking `reportlab`'s private internals to chase a flag that may not even fix Drive's specific renderer. Instead, both language versions of the plan email now end with a one-line note: if the built-in viewer won't let you type into the fields, download the PDF and open it with Adobe Acrobat Reader (free) or another PDF app.

## The password gate was shared across two differently-sensitive sections — split per-section

`_gate_datos_clientes()` fronts both "Revise client" (full health profile on a successful lookup) and "Clients" (an email roster) behind the same `APPROVAL_PASSWORD`. It shared **one** `session_state` flag across both, so unlocking either one silently unlocked the other too — proving the password once bought access to both kinds of exposed data without ever being asked again for the second. Caught live-testing, not by design review. Fixed by threading a `seccion` argument ("revisar"/"clientes") through `_gate_datos_clientes()`/`_datos_clientes_desbloqueados()`, so each section gets its own `session_state` key and its own widget keys — unlocking one no longer touches the other. Verified live: unlocked "Revise client" with the test password, switched to "Clients," and it asked for the password again from scratch.

## "Revise client" and the PDF-intake upload both used to skip the review step

Two related gaps, closed together, both about the same principle: a client's data should always land in the same editable form for a human to look at before it becomes a routine/diet, regardless of how that data arrived.

**"Revise client" let the trainer type up a brand-new client from scratch**, defeating its own purpose — the section reused `_formulario_ficha_nueva()` unconditionally, blank if no lookup had been done, identical in every way to filling out "New client" except it wasn't tagged as a new client and wasn't behind that flow's own Notion-save/Gmail-draft gating. Fixed: the form now only renders once `st.session_state["revisar_pagina_id"]` is set by a successful email lookup. Before that, the section shows only the lookup fields and an explicit "load a client above" message — no way to reach the form without loading someone real first.

**The PDF-intake upload skipped straight to plan generation**, no human ever looking at the parsed fields before they became a routine/diet. `agents/pdf_intake.py`'s `leer_intake_pdf()` is a mechanical field-by-field PDF read — not something guaranteed correct just because a form came back filled in. Fixed to match "Revise client"'s own pattern exactly: confirming a found/uploaded intake now pre-seeds `_formulario_ficha_nueva()`'s `session_state` (`_campos_formulario_desde_perfil()`, the same mapping "Revise client" already uses) and reruns, instead of returning the parsed profile directly. The "New client" tab's dispatch simplified as a result — `_cargar_ficha_desde_pdf()` no longer returns a profile at all, it's purely a loader now, and `_formulario_ficha_nueva()` is called exactly once regardless of how the trainer got there (typed from scratch, or loaded from a PDF). Button/caption copy updated to say "load into the form below" instead of "generate the plan," since that's no longer what the button does.

Both verified live end-to-end: "Revise client" shows nothing but the lookup UI until a real client is loaded; "Clients" still gates independently as above.

## A commitment-level dial (chill/normal/tryhard), niche exercises/foods, and supplement tips

Requested directly, scoped with three clarifying questions (same pattern as the earlier maximal-personalization work) before touching code, since "how demanding do you want the plan" could plausibly mean several different things: calorie aggressiveness, level of numeric precision, exercise/food variety, or some mix. The project owner's answer combined all of it — precision AND variety AND numbers — plus two follow-up decisions: niche foods are curated by the project, never typed in by a client; and supplement tips should skip whatever the client already reports taking.

**New field: `experiencia.nivel_compromiso`** (`"chill"` / `"normal"` / `"tryhard"`, defaulting to `"normal"`) — placed under `experiencia` rather than a new top-level object, since it's a training-commitment concept, not a separate concern. `"normal"` is a deliberate no-op everywhere it's read, so every existing client/test/example is byte-identical to before this shipped.

**Routine (`rutina_reglas.py`):** `AJUSTE_SERIES_POR_COMPROMISO = {"chill": -1, "normal": 0, "tryhard": 1}` stacks with (doesn't replace) the existing level/stress-sleep adjustments, all clamped by the same `SERIES_MINIMAS` floor — a beginner in chill mode with high stress reported can stack three -1s and still never drop below 2 sets, verified in a dedicated test. A new curated `"nicho"` tag on 6 exercises across the major muscle groups (Bulgarian split squat, Nordic hamstring curl, weighted pull-up, dragon flag, deficit push-up, single-arm push press) — genuinely more technically demanding variants, not just "harder" — are only ever candidates in `_candidatos()` when tryhard is active; absent on every pre-existing entry (`.get("nicho", False)`), so nothing changes by default.

**Diet (`dieta_reglas.py`):** `AJUSTE_COMPROMISO_MULTIPLICADOR = {"chill": 0.6, "normal": 1.0, "tryhard": 1.3}` scales `AJUSTE_CALORICO`'s *magnitude*, never its direction — a real, deliberate constraint against the trainer's own documented "moderate deficit, never aggressive" stance (method §3): tryhard's 1.3× still lands a fat-loss deficit around -23%, short of what the method would call aggressive, rather than opening the door to a crash diet just because a client picked the most demanding option. Four new `"nicho"` foods (kimchi, natto, farro, algae oil — vegan omega-3, deliberately not gated to omnivore the way regular oily fish is) are, same as the exercise side, project-curated rather than free-text from the client (the project owner's explicit call: "I add the niche foods myself, the user doesn't set them for me") — gated behind the same `tryhard` check in all four `fuentes_*_para()` functions, verified to still respect allergy exclusion (a soy allergy still excludes natto even in tryhard mode).

**Supplements, in two parts, matching the project's existing two-tier safety model:**
- `salud.suplementos_actuales` is a new intake field, treated the same as `medicacion_habitual` — a real, safety-relevant fact, not a preference. `validator_agent.py` forces `revision_reforzada` whenever a client reports BOTH supplements and regular medication together, grounded directly in `docs/base_conocimiento/suplementacion.md`'s own "Safety rule" section ("any supplement with a possible interaction with medication... flag for human review, never recommend by default"). This project deliberately doesn't attempt a real drug-interaction database — a false sense of completeness there would be worse than the honest, coarser "review before doing anything else" flag.
- `dieta_reglas._consejos_suplementos()` adds short, evidence-based tips (creatine, protein powder, caffeine — dose/timing basics only, not a personalized protocol) to `consejos_sinergias`, but only in tryhard mode, and only for supplements the client didn't already list — verified directly: a client who already reports taking creatine gets the protein/caffeine tips but never the creatine one, matching the project owner's explicit request ("recommend supplements/tips in case they're not already added by the user").

**Verified, not assumed:** ran the routine engine against a real profile with commitment mode toggled through all three values and confirmed set counts moved exactly as designed (chill = normal-1, tryhard = normal+1); sampled 15 different client IDs in tryhard mode and confirmed at least one niche exercise was actually selected (not just theoretically reachable); confirmed a real generated diet's kcal target moved further from maintenance under tryhard than chill for a fat-loss goal, and stayed byte-identical between chill/tryhard for a maintenance goal (0% has no direction to scale); confirmed the supplement-skip logic against a real profile (creatine excluded from tips, caffeine/protein-powder tips still present). 19 new tests across `test_rutina_reglas.py`/`test_dieta_reglas.py`/`test_food_bank.py`/`test_validator_agent.py`, including explicit "field absent → behaves exactly like normal" regression tests and Spanish-language coverage for the new summary notes (a real gap the coverage report caught, same as earlier sessions' validator gaps). 402 tests passing (up from 383), 97.4% coverage, lint clean, full pipeline demo clean.

## A fleet-level dashboard on "Clients," at zero extra Notion cost

The project owner asked for "a dashboard with the important data" after not finding the existing per-client trend chart (it only renders once a specific client has 2+ check-ins with weight/rating — genuinely absent for most clients this early, not a bug). Rather than a new section with its own query, `_render_dashboard_clientes()` sits directly above the existing roster table in "Clients" and reuses the exact same `listar_clientes()`/`ultimo_checkin_por_cliente()` results `_panel_todos_los_clientes()` already fetches for that table — zero new Notion queries. Four `st.metric()` KPIs (total clients, with a check-in, ⚠️ needing attention, no check-in yet) plus two `st.bar_chart()`s (verdict mix, latest-adherence-rating mix), same "missing chart library degrades to no chart, never a broken page" defensive pattern as the existing per-client trend chart. Verified live against the real workspace (2 clients, 1 flagged, both charts rendering with real counts).

## Adherence tracking doesn't currently recognize a forwarded reply

The project owner asked whether a client's checklist PDF, received via someone forwarding it into the trainer's inbox rather than the client hitting Reply, still gets picked up by the scheduled scan. Traced it end to end: it doesn't, **and that's deliberate, not an oversight** — `buscar_respuestas_adherencia()` requires the `In-Reply-To` header (RFC 5322, set on every genuine reply, absent from a forward) specifically to keep the trainer's own *sent* copy of the original blank checklist out of the results. That guard turns out to be load-bearing in a way that isn't obvious at first: `leer_checklist_pdf()`'s `valoracion` only comes back `None` when the PDF has *none* of the expected fields at all — a **blank but structurally intact** checklist (the trainer's own original, or a client forwarding it unfilled) has real checkbox fields present, just all unchecked, which computes to a 0%-completion ratio and a real `"Low"` rating rather than `None`. Dropping the In-Reply-To check would risk silently logging a false "Low adherence" check-in from the trainer's own sent mail. Documented rather than quietly left as a gap; a real fix (distinguishing "genuinely filled in" from "structurally present but blank," then relaxing the header check for verified-filled forwards) is a bounded follow-up, not implemented yet since it touches a scheduled cron's live Gmail search and deserved a scoping conversation first rather than a rushed change to a safety-relevant dedup path.

## Checklist-PDF-by-email and the client portal write to the same place, by design

Asked to clarify why both exist. They're two front doors to the exact same back end: both call `crear_registro_checkin()` with `tipo="Adherence check-in"`, into the same Check-ins Notion database, scored by the same `valoracion_desde_ratios()`. The real difference is delivery mechanism and reach, not data: the checklist PDF rides along with every approved plan automatically (no extra step, works for any client, but requires replying-in-thread with the PDF re-attached — see the forwarding gap above) and has no weight field at all; the portal requires the trainer to proactively send a magic link (`enviar_enlace_portal()`, a deliberate `gmail.send` exception) but is friction-free after that (sliders, no PDF, live progress bars) and is the only channel that captures weight. Not a case of accidental duplication to clean up — but a real, disclosed trade-off worth knowing about before choosing which one to steer clients toward.

## Four follow-ups after living with the previous session's changes for a day

All four requested directly, after actually using the app and receiving a real forwarded email: revert the password-gate split, drop the "Clients" roster table in favor of an anonymized dashboard only, make the adherence checklist PDF opt-in instead of automatic, and always attach a full routine PDF (not just diet) — plus richer, verified per-session content and an easier-to-read plan email.

**The password-gate split (previous session) got reverted, on purpose.** `_gate_datos_clientes()` is back to one shared `session_state` flag across "Revise client" and "Clients," matching its original pre-split behavior — the project owner's own call, made *because* of the next change below, not despite it: once "Clients" stopped showing any individual client's data at all, the original problem the split was fixing (unlocking a roster of emails also silently unlocked full health profiles) no longer exists. Reverting a very-recently-shipped change the moment its premise changes is the same discipline as any other design decision here — don't keep a fix around after the thing it was fixing stops being true.

**"Clients" is now an anonymized, fleet-level dashboard only — no roster table.** The per-client table (name, email, goal, verdict, last check-in) is gone; `_render_dashboard_clientes()` (4 KPI metrics + 2 bar charts, already built the same day as the roster it now replaces) is the entire section. Rationale, direct from the project owner: this app's "Clients" tab is for the trainer to see how their clients are doing "at a glance," not a second, weaker copy of what Notion's own database view already does better for looking up one specific record — a real "don't duplicate what another tool already does well" call, not a security-only decision (though it does also reduce what a shared-gate mistake could ever expose). `_etiqueta_atencion()` and the now-dead `clients_col_*` translation keys were removed along with it rather than left as orphaned code.

**The adherence checklist PDF is opt-in now, not automatic.** `crear_borrador()` gained `incluir_checklist: bool = False` — the client portal is the project's intended default way to log adherence in-app now, so mailing out a PDF-and-reply loop by default duplicated that with more friction, not less. A checkbox in `ui/app.py`'s approval panel (default unchecked, matching the parameter's own default) lets the trainer still attach it for the specific case it's actually useful: a client without portal access, or who genuinely prefers paper/PDF. `main.py`'s scheduled scan for filled-in checklist replies needed no code change — it already handles "found nothing this run" gracefully; it will simply have fewer emails to find now.

**A real asymmetry got closed: the routine never had its own PDF.** The diet always rendered as a full standalone document (`generar_pdf_dieta()`); the routine's own content only ever lived in the email body's brief `mensaje_para_el_cliente` text. New `generar_pdf_rutina()` mirrors the diet PDF's exact structure and styling (same colors, fonts, table style) — per-session tables (exercise/sets/reps/rest/notes), warmup, optional cardio, and the progression tip — and is now always attached alongside the diet PDF, regardless of the checklist opt-in above. Defensive against a minimal/older `borrador_rutina` missing per-session detail (same "renders correctly, just without that section" tolerance the diet PDF already has for `plan_semanal`).

**A new, evidence-grounded per-session note: reps-in-reserve (RIR) effort cueing.** The trainer's method already mentioned leaving reps in reserve on compounds (`docs/base_conocimiento/entrenamiento.md`), but nothing operationalized it into an actual per-session note a client would see. Backed it with two real sources found and read for this change — [a 2021 systematic review and meta-analysis on load/volume autoregulation](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8762534/) (subjective RIR-based effort and objective velocity-based autoregulation produce similar strength gains to fixed-%1RM training, and training closer to failure tends to favor hypertrophy specifically, at a real fatigue/recovery cost) and [a 2023 trial in trained lifters](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10161210/) (comparable strength/hypertrophy outcomes at ~2 RIR vs. training to failure, with less fatigue and better session-to-session consistency) — added as a new "Effort and proximity to failure" section in the knowledge base, then wired into `rutina_reglas.py` as a real `nota_esfuerzo` field on every session (compounds: 1-2 RIR; isolation: 0-1 RIR), rendered in both the routine PDF and the on-screen review, and added to `routine_agent.py`'s system prompt for `motor="llm"` parity.

**The plan email is genuinely shorter and more scannable now**, a direct request ("easy to read, key points, not much text"): `_construir_cuerpo_email()` now lists attachments as a real bullet list instead of a prose paragraph, and pulls exactly one genuinely useful line per section straight from the plan itself (`progresion` for the routine, the diet's first `consejos_sinergias` entry) under a 👉 marker — so the single most actionable tip is visible without opening a PDF, without duplicating the PDFs' own full detail. Tolerates a minimal/older draft missing either field gracefully (no 👉 line, nothing crashes).

Verified: 415 tests passing (up from 402), 97.5% coverage, lint clean, a real routine PDF generated and inspected directly (bytes present, both languages, RIR note included), and the mocked-network test asserting the exact attachment filename set changes correctly with/without the checklist opt-in. **Not re-verified live in the browser this round** — a port conflict with another concurrent session blocked starting the local Streamlit server; the UI changes (checkbox default, gate revert, dashboard-only Clients tab) are straightforward wiring already covered by the underlying functions' own tests, but should be spot-checked live the next time the app is open, same honesty standard this project applies to every other claim about what's actually been verified.

## A production crash: PDF generation could take down the whole app, not just the draft button

Reported directly from the live Streamlit Cloud deployment: `TypeError` at `crear_borrador(` inside `_panel_aprobacion()`, with the actual message redacted by Streamlit Cloud's own privacy behavior. Root cause of the *architecture* gap (not necessarily the exact triggering data, which couldn't be reproduced against every existing example client plus a battery of adversarial synthetic profiles — empty equipment, every injury at once, a 15-minute session, an unrecognized goal, all passed locally): `ui/app.py`'s call site only catches `(GmailClientError, ImportError, ModuleNotFoundError)`, but `crear_borrador()`'s PDF-building step (`generar_pdf_rutina()`/`generar_pdf_dieta()`/`generar_pdf_checklist()`, reportlab/pypdf rendering a *real* client's actual data) can raise anything — a `TypeError` from those libraries doesn't get caught by that narrow clause and propagates straight up, crashing the entire app instead of just failing the one button. Fixed by wrapping that whole step inside `crear_borrador()` and re-raising as `GmailClientError` — the one exception type its caller already knows how to handle gracefully — rather than widening the UI's except clause (would risk masking genuinely unexpected bugs elsewhere too) or hardening every individual PDF-generation function separately. Locked in with a test that makes `generar_pdf_rutina()` raise a real `TypeError` and asserts `crear_borrador()` converts it rather than letting it through. The exact original data that triggered this in production is still unknown — the fix contains the *category* of bug (a rendering-layer failure crashing the whole app), not necessarily the one instance of it; worth following up if the redacted message becomes available from Streamlit Cloud's own logs.

## The free-text dietary-concern field became a preset dropdown

Requested directly. `nutricion.inquietud_principal` was a free text_input, matched against only two recognized categories (`_PALABRAS_CLAVE_PREFERENCIA_BLANDA`'s "antiinflamatorio"/"reducir_gluten") — a trainer typing anything else got silently ignored by the matching logic with no indication that was happening. `_formulario_ficha_nueva()` now shows a selectbox (None / Anti-inflammatory / Lower gluten / Other) instead; picking a preset stores the exact natural-language phrase `food_bank.py`'s existing bilingual keyword matching already recognizes for that category (e.g. "anti-inflammatory"), so **no changes were needed in `food_bank.py`'s matching logic at all** — the presets just guarantee a hit instead of hoping free text happens to phrase it recognizably. "Other" reveals a follow-up text field for anything not covered, preserving full expressiveness.

New public `food_bank.categoria_inquietud_conocida(texto)` runs the same keyword lists in reverse — given saved text, returns which category (if any) it matches. Used by `_campos_formulario_desde_perfil()` (the "Revise client"/PDF-intake pre-fill mapper) so a client's *previously* saved free-text concern — from before this dropdown existed, or typed into "Other" — pre-selects the right preset automatically when a known phrase is recognized, falling back to "Other" with the original text intact otherwise. Nothing is ever silently dropped on revision. The fillable intake PDF (`agents/pdf_intake.py`) still collects this field as free text on purpose — a prospect filling it out has no UI to constrain them to presets anyway, and that free text flows through the exact same reverse-mapping when the trainer loads it, so the asymmetry causes no real gap.

## "Repeat this meal" — a client can like a meal from the portal and see it again

Requested as an open-ended "look into this," scoped with two clarifying questions before writing any code, since the answer materially changed both the effort and the design: who picks (trainer vs. client) and how "repeat" should actually work (bias future generation vs. pin to an exact weekday). The project owner chose client-side (portal) and bias-not-pin — the same "prefer, don't force" philosophy `_sesgar_por_preferencias()` already uses for soft dietary preferences.

**A real blocker surfaced mid-investigation, and got a direct question of its own rather than a silent decision**: the client portal never had access to the full weekly meal plan — only a 2000-char truncated summary, a deliberate prior design ("the portal doesn't need a second copy of the full plan to exist anywhere"). Showing meals to like requires reversing that, the same class of call as the earlier "Full Profile (JSON)" reversal — put to the project owner explicitly rather than assumed, who confirmed storing the current week's plan.

**Data model, three pieces:**
- Each meal `_construir_comida()` builds now carries structured picks (`tipo_interno`, `proteina`, `carbohidrato`, `grasa` — canonical English names, never displayed directly) alongside its existing rendered `descripcion`. This is why the feature doesn't need to parse food names back out of prose: the project's own "structured data over free-text parsing" discipline (see `agents/pdf_intake.py`'s whole rationale) applied here too.
- New Notion property **"Weekly Meal Plan (JSON)"** (chunked, same pattern as "Full Profile (JSON)") stores `borrador_dieta["plan_semanal"]` at approval/revision time — trainer-written, portal-read-only.
- New Notion property **"Liked Meals (JSON)"** is the one property the portal ever *writes* — kept deliberately separate from "Full Profile (JSON)" so a client tapping 🤍 can never race with or clobber a trainer's concurrent edit to the rest of the profile. `agregar_comida_favorita()` is a narrow read-modify-write scoped to exactly this field, deduping by exact match.

**The bias mechanism** (`planificador_comidas._sesgar_por_favoritos()`): for a given meal slot, if a liked meal for that same `tipo` has protein/carb/fat picks that are *all* still valid candidates (an allergy or diet-type change since the meal was liked correctly drops it, since matching happens against the already-filtered pool, not the raw food bank), it wins the whole meal jointly (not each category rolled independently, which would rarely reproduce the exact liked combination) about 60% of the time a match exists — verified statistically across 20 client IDs, not a single generated week. `perfil["nutricion"]["comidas_favoritas"]` is read directly inside `generar_plan_semanal()`, and gets there automatically: `notion_connector._perfil_desde_propiedades()` (shared by `obtener_perfil_completo()`/`buscar_cliente_por_email()`, both used by "Revise client") merges "Liked Meals (JSON)" straight into the loaded profile, so a client's portal likes flow into the next regeneration with zero extra wiring in `ui/app.py`.

**Real, disclosed setup dependency**: this only works once the project owner manually adds "Weekly Meal Plan (JSON)" and "Liked Meals (JSON)" as text properties on the real Notion "Clients" database (same one-time, free, human step every other Notion property in this project has always required — see the module docstring's setup section, now updated). Until then, `obtener_registro_cliente()`/`agregar_comida_favorita()` degrade gracefully (empty plan, or a clear `NotionClientError` on like) rather than crashing, but the feature itself needs that step done to actually work.

30 new tests (statistical bias check, safety-drop-on-allergy-change, dedup-on-repeat-like, empty-plan degradation, the full Notion round trip mocked), 430 total (up from 419), lint clean.

## The "repeat a meal" feature, verified for real against the live workspace — and three more dietary-concern presets

**Notion setup done, and verified against the real workspace, not just mocked.** Added "Weekly Meal Plan (JSON)" and "Liked Meals (JSON)" (both `RICH_TEXT`) to the real "TrainFitter Clients" database directly via Notion's own API (schema DDL, not a manual click-through). Then ran the actual project code — not a synthetic test — against a real existing client record (`PEPE`, a test client created earlier this session): regenerated and saved a real plan (`actualizar_registro_cliente()`), confirmed `obtener_registro_cliente()` — the exact function the portal calls — reads back a real 7-day plan with the new structured fields intact, called `agregar_comida_favorita()` for real (a liked breakfast: Seitan + whole wheat bread), confirmed the like merged back into the profile on the next load (`buscar_cliente_por_email()`), and regenerated the diet 15 times with different seeds: **the liked breakfast reappeared 58/105 times (~55%)**, matching the ~60% design target within real sampling noise — not a mocked assertion, an actual measured rate against the live integration. This is strictly stronger evidence than the mocked-network tests alone (which only prove the request/response shapes are right, not that the real Notion schema accepts them or that the bias survives a real round trip).

**Three more dietary-concern presets**, added the same way the first two were: reusing sinergia tags the food bank already carries, no new food data needed. "Gut health" (`salud_digestiva`) biases toward probiotic-tagged foods (Greek yogurt); "More fiber" (`mas_fibra`) biases toward the same `fibra_alta` tag the sedentary-job structured signal already uses, now also reachable by just saying so; "More iron / anemia" (`mas_hierro`) biases toward the existing non-heme-iron-tagged legumes/tofu/tempeh, paired with vitamin C in the same meal via the synergy logic that already exists for iron. Deliberately did *not* add presets with no real backing in the food bank (e.g. "low sodium," "heart health") — every option in the dropdown does something real, per the project owner's own "viable options only" request. Verified statistically across 15 client IDs for the iron bias (directional, not a fixed-threshold assertion — the baseline share of iron-tagged proteins is already non-trivial, unlike salmon's ~8% baseline for the antiinflammatory case, so a flaky single-seed threshold test would have been the wrong tool here).

439 tests passing (up from 432), 97.4% coverage, lint clean.

## Three follow-ups from the project owner's own roadmap: exercise-liking parity, a weight-trend nudge, and safer forward-detection

After the previous session's dietary-concern/meal-liking work, the project owner asked for a prioritized list of what to build next; three "Recomendable" items were proposed and, this session, all three were built, tested, and verified in one pass.

**"Repeat this exercise" — the meal-liking feature, mirrored exactly for the routine side.** Structurally the same design as "repeat this meal," reusing every decision already made there rather than re-litigating them: bias (not pin), portal-only write, and a scoped read-modify-write property so a client's like can never race a trainer's concurrent edit.
- Each exercise `rutina_reglas.generar_borrador_rutina_reglas()` builds now also carries its own slot's `grupo`/`tipo` (e.g. `"pecho"`/`"basico"`) alongside the existing `nombre`/`series`/`repeticiones`/`descanso_seg`/`notas` — the same "structured picks travel with the rendered content" discipline the meal planner already established, needed so a later like can be matched back to the right slot without re-deriving anything from `exercise_bank.py`.
- New Notion properties **"Weekly Routine (JSON)"** (trainer-written, portal-read, mirrors "Weekly Meal Plan (JSON)") and **"Liked Exercises (JSON)"** (the one property the portal ever writes, mirrors "Liked Meals (JSON)") — added directly to the real "TrainFitter Clients" database via Notion's schema API, same as the meal-liking properties before them.
- New `rutina_reglas._sesgar_por_favoritos()`: for a given `(grupo, tipo)` slot, a liked exercise still present among that slot's already equipment/injury-filtered candidates wins ~60% of the time a match exists (`PROBABILIDAD_REPETIR_FAVORITO`, the same constant value as the meal planner's own) — otherwise the existing per-client-seeded rotation picks as before. An injury or equipment change since the like correctly drops it, since matching happens against the filtered candidate list, not the raw exercise bank.
- `perfil["experiencia"]["ejercicios_favoritos"]` is the read path (mirrors `perfil["nutricion"]["comidas_favoritas"]`), merged automatically by `notion_connector._perfil_desde_propiedades()` — zero extra wiring needed in "Revise client" or anywhere else.
- `ENTREGAR_BORRADOR_RUTINA_TOOL`'s schema gained the matching `grupo`/`tipo` fields (optional, not required), keeping the "two interchangeable engines, one schema" invariant intact for `motor="llm"`.

**Verified live against the real workspace**, not just mocked: added both properties to the real database, generated a real routine for the existing `PEPE` test client, round-tripped it through `obtener_registro_cliente()` byte-for-byte, liked a real exercise (`agregar_ejercicio_favorito()`), confirmed the like merged into the profile on the next load, then regenerated the routine 30 times — **the liked exercise reappeared 67/90 times (~74%)** for its slot, comfortably above the ~60% design target. 6 new statistical/behavioral tests in `test_rutina_reglas.py` plus 12 new Notion round-trip tests, mirroring the meal-liking test suite's own structure.

**A weight-trend nudge for the trainer, closing a loop the diet's own copy already implied existed.** `dieta_reglas.py`'s generated message has always told the client their plan "gets adjusted based on real weight... over the first few weeks" — but nothing ever compared logged weight against the goal's expected direction. New `agents/adherencia_parser.tendencia_peso()`: sorts a client's Check-ins by date, and flags a real, human-readable mismatch (e.g. "hasn't trended down... despite a fat-loss goal") only when there's a genuine signal to act on — at least two weight-carrying check-ins spanning ≥10 days (`DIAS_MINIMOS_TENDENCIA`), a real ≥0.3kg change in the wrong direction (`UMBRAL_KG_TENDENCIA`), and a goal with an unambiguous expected direction at all. `recomposicion_corporal` and `salud_general` are deliberately excluded — weight alone can't judge a recomposition (muscle gain can offset fat loss on the scale) or a goal with no weight target — the same "don't flag what you can't interpret" discipline already applied to the dietary-concern presets. Shown as a `st.warning()` banner above the existing trend chart in both the trainer's "Adherence history" expander and the client's own portal view, and included in the trainer's check-in notification email (`enviar_notificacion_checkin()` now optionally computes it itself given `historial`/`objetivo`, so no caller has to). Reads only the already-narrow "Goal" select property (via a new `notion_connector._LABEL_A_OBJETIVO` reverse map) — never the full profile — since the goal is already effectively visible in the portal's own summary prose. Deliberately just a nudge: never touches `dieta_reglas.AJUSTE_CALORICO` automatically, same "the trainer always reviews before anything changes" principle as everywhere else. 11 new tests covering every branch (both goal directions, both flagged/not-flagged outcomes, excluded goals, too-short window, malformed date degrading to silence rather than a crash, sort-order independence, Spanish translation).

**Forward-detection refinement: `buscar_respuestas_adherencia()` now accepts a client's genuine forward, not just an in-thread reply.** Traced the *actual* reason the previous session's `In-Reply-To` gate existed — not "reject anything that isn't a reply" in general, but specifically "don't re-process the trainer's own sent copy of the still-blank checklist showing up in its own inbox search." Those turn out to be different conditions: the fix calls `users().getProfile()` once per scan to learn the authenticated account's own address, and only excludes a non-reply message when its sender *is* that address — a genuine forward from the client's own account now gets through. The other half of the original worry — a blank-but-structurally-intact checklist computing to a false "Low" rating — is a separate, independent safety net that already existed and still applies unchanged: new `checklist_tiene_contenido_real()` (any completed session, any diet-days answer including an explicit 0, or any note text) gates `main.py`'s `procesar_adherencia()` before it ever logs a check-in, so a blank forward (or the trainer's own sent original, on the rare case it ever reached this point) gets silently skipped rather than logged as fabricated adherence data. Two independent gates, each doing one job, rather than one gate doing both — the same "defense in depth, not one gate trying to do two jobs" pattern the safety-critical validator already uses elsewhere in this project. 6 new tests (mocked network): accepts a forward, still excludes the trainer's own sent copy, and 4 behavioral cases for `checklist_tiene_contenido_real()`.

**Verification, honestly scoped per feature**: exercise-liking got a full real-workspace round trip (network access was available); the weight-trend nudge's UI wiring was confirmed by reading the actual call sites and render logic rather than a live browser session (no local Streamlit secrets in this environment) — the underlying function itself has full branch coverage; forward-detection can't be live-tested against a real inbox at all, a limitation already disclosed for this exact code path in the previous session — mocked-network tests are the established substitute here. 471 tests passing (up from 439), 97% coverage, lint clean.

## Refining the supplement interaction warning with specific pairs

Followed up on validator_agent.py's own coarse check ("supplements + medication declared together → always flag, no detail") after the project owner supplied a curated set of specific supplement-medication pairs with mechanism/certainty notes. Before writing any of it into the knowledge base, verified the pharmacology against real sources rather than trusting the list at face value — NIH ODS fact sheets (Vitamin K, Magnesium), NCCIH (St. John's Wort, fetched directly), and cross-checked via search against PubMed/PMC case reports, MDedge, and patient.info for the rest (NIH ODS itself blocked direct fetching with a 403 this session — its content was instead corroborated through search result snippets and independent secondary sources, not assumed).

**New `agents/suplementos_interacciones.py`**: a curated (not exhaustive) table of 12 supplement categories mapped to the medication classes they have a documented interaction with, each with a short bilingual mechanism note. `pares_interaccion_declarados()` matches `salud.suplementos_actuales` and `salud.medicacion_habitual` free text against these categories (bilingual, accent-insensitive, same `_sin_acentos()` technique `food_bank.py` already established) and returns a specific, named message per recognized pair — e.g. "iron + levothyroxine/tetracyclines: forms an insoluble complex, reducing absorption; separate doses by several hours."

**Deliberately additive, not a replacement.** `validator_agent.py`'s existing generic "supplements + medication together → flag" check still runs unconditionally — an unrecognized combination (anything not in the curated table) still always forces `revision_reforzada`, it just doesn't get the extra explanation. This preserves the original design rationale word-for-word (a false sense of completeness would be worse than none) while making the *recognized* subset more useful to the trainer than a generic flag alone.

**What's covered and what isn't, on purpose**: vitamin K↔anticoagulants (the best-documented pair there is — direct mechanistic antagonism); iron/calcium/magnesium/zinc↔tetracyclines/quinolones/levothyroxine/bisphosphonates (gut chelation, well-characterized pharmacokinetics); magnesium↔potassium-sparing diuretics (conditional on renal function); high-dose omega-3/vitamin E↔anticoagulants/antiplatelets (additive bleeding risk, moderate certainty); high-dose vitamin D↔thiazides/digoxin (hypercalcemia chain); ashwagandha↔sedatives/thyroid hormone/immunosuppressants (smaller evidence base, flagged as moderate certainty rather than overstated); high-dose turmeric↔anticoagulants/chemotherapy; St. John's Wort↔SSRIs/oral contraceptives/anticoagulants/immunosuppressants (CYP3A4 induction — the canonical "natural ≠ no interaction" example); quercetin↔quinolones/chemotherapy (marked lowest-certainty in the table, least-studied pair here). Creatine, protein powder, beta-alanine, and collagen — this project's actual recommended supplements — are absent on purpose: no clinically relevant interaction at normal doses, not an oversight.

**Verified, not assumed**: ran the function directly against test cases for every pair category, confirmed accent/case-insensitive matching (cúrcuma/curcuma), confirmed a supplement matching a *recognized* medication category that it has no *documented* interaction with (iron + warfarin) stays silent rather than false-positiving off "any recognized medication," and confirmed the existing generic-flag test suite still passes unchanged (creatine + anticoagulant still forces review off the generic check alone, since creatine has no specific pair). 14 new tests in `test_suplementos_interacciones.py`, 2 new integration tests in `test_validator_agent.py`. 487 tests passing (up from 471), 100% coverage on the new module, 97% overall, lint clean. `docs/base_conocimiento/suplementacion.md` gained a full "Known interaction pairs" table with per-pair certainty ratings and citations, matching this project's existing "Sources consulted" convention.

## Reframing the commitment dial as "how much detail," and a generic protein-powder name

Three small, direct requests, the third one substantial enough to need a real design pass.

**The commitment-level field moved from "Training experience" to "Goal."** `nivel_compromiso` had lived under `sec_experience` since it shipped — reasonable at the time, but conceptually it's about how the client wants to *pursue* the goal, not about their training background. Moved in both intake paths that ask this question (`ui/app.py`'s typed form and `agents/pdf_intake.py`'s fillable PDF), right after "in their own words," so the two paths stay in sync.

**"Pea protein (powder)" became "Protein powder (plant-based)."** The project owner noticed it showing up often in generated weekly plans and asked for a generic name — and to state the concrete reason if there was one. There is one: `food_bank.py`'s protein entries are almost all universally diet-compatible (legumes, soy, seitan), and this is the one that's specifically plant-based rather than an animal product, which is *why* it's a candidate for vegan clients at all (unlike whey, this project's other protein-powder recommendation, which is dairy). The macros are still real pea-protein-isolate values — a common, representative plant powder — the name just no longer implies that specific type is the one deliberately recommended over any other.

**The commitment dial itself was reframed, after a direct correction mid-implementation.** The first pass added a fourth tier, `"saludable"`, between `"normal"` and `"tryhard"` — unlocking supplement tips (creatine, protein, magnesium, omega-3) without the niche unlocks, per the project owner's own description of wanting "to take care of myself... but not become a nerd about niche stuff." The project owner pushed back on the *name*, not the mechanism: "healthy" isn't a distinguishing name because every tier should already be healthy. The actual axis was never "how healthy" — it's "how much detail/guidance do you want," with `"tryhard"` explicitly confirmed as staying the literal ceiling (the most complete routine+diet this project can currently produce). Renamed all four tiers to **`basico` / `normal` / `avanzado` / `tryhard`** and rewrote every place that explained them (the field label, the caption, both rule engines' summary sentences, both LLM system prompts, the fillable PDF) around that framing instead.

**Numbers deliberately NOT coupled to the new "detail" framing.** `avanzado` stays a no-op for training volume/calorie aggressiveness (`AJUSTE_SERIES_POR_COMPROMISO["avanzado"] = 0`, `AJUSTE_COMPROMISO_MULTIPLICADOR["avanzado"] = 1.0`) — the same values `"saludable"` had. This was a deliberate choice, not a lazy rename: "how much detail you want" and "how much physical demand you want" are different axes, and there's no real training-science basis for inventing extra volume just because a client wants more supplement/synergy guidance. Coupling them would mean fabricating a justification this project doesn't actually have. `avanzado`'s only real effect stays in `dieta_reglas._consejos_suplementos()` (creatine/protein/magnesium/omega-3, shared with `tryhard`; caffeine stays `tryhard`-only, since it's a performance/pre-workout aid, not a general-health basic) — same mechanism as before, correctly renamed.

**A real bug the linter caught, not a human review:** `ui/app.py`'s `OPTION_LABELS` is one flat `{value: label}` dict shared across every selectbox in the file (`opt()` looks values up without knowing which field they came from) — and `"avanzado"` was already a value for `experiencia.nivel` (Beginner/Intermediate/**Advanced**). Adding a second `"avanzado": "Advanced (more detail)"` entry silently overwrote the first in the dict literal — `ruff`'s `F601` (repeated dictionary key) flagged it before it ever reached a human. Fixed by dropping the duplicate and sharing the existing plain "Advanced"/"Avanzado" label between both fields — the commitment-specific meaning is already explained by the caption text underneath that selectbox, so nothing is lost.

Verified: 494 tests passing (up from 487, some renamed rather than net-new), lint clean, `run_manual_pipeline_demo.py` regenerated all six `examples/output_*.json` files cleanly (confirmed no `"Pea protein"`/`"guisante"` left anywhere, `"Protein powder (plant-based)"` present).

## Making the commitment dial actually change the routine and diet, not just the label

Direct, pointed follow-up the same day: the previous session renamed the four tiers around "how much detail you want," but `avanzado` was still functionally a no-op for both engines — same sets, same calories, same food/exercise selection as `normal`, just with supplement tips and a different name. The project owner asked for the real thing: exercises that actually get simpler/less demanding at the low end and more specific/optimized at the high end, and meals that stay "normal"/everyday at the low end without getting "friki" about nutrient synergies, still getting more specific as the level rises. Scoped with three targeted questions before touching the diet engine specifically, since it already runs unconditionally for every existing client and getting the gate wrong would mean reworking a well-tested, foundational path twice.

**Routine: exercise complexity now stacks with (not instead of) training experience.** `rutina_reglas.py` already had `_preferir_baja_complejidad_primero()` — a stable reorder toward machine/bodyweight over barbell — but only ever applied it to a beginner by *training experience* (`nivel == "principiante"`). New `_preferir_alta_complejidad_primero()` is its mirror. The actual rule, confirmed explicitly rather than assumed: `nivel == "principiante" OR nivel_compromiso == "basico"` → low-complexity-first (an experienced client who picks "basico" still gets the simple version); `elif nivel_compromiso == "tryhard"` → high-complexity-first (reachable only because the first condition didn't already catch a genuine beginner). This last point was a deliberate safety call, not requested verbatim: a true beginner who picks "tryhard" for more *detail* still gets the low-complexity bias, not a push toward harder movements — training experience is a safety-relevant signal that outranks a stated preference for how much guidance to receive. Confirmed statistically (share of "alta"-complejidad picks across 20 regenerations, `basico` vs `tryhard`), not by reading the code alone.

**Diet: a new, softer tier below "nicho."** `food_bank.py` gained a `"comun"` tag (defaults to `True`, same absence-based pattern as `"nicho"`) marking tofu, tempeh, edamame, seitan, "Protein powder (plant-based)", quinoa, and seeds (chia, flax) as `False` — real, valid, never-excluded candidates at every level, just not what most people would call an everyday food. New `planificador_comidas._sesgar_por_nivel_compromiso()` biases (never excludes) a "basico" client's actual weekly picks toward the `"comun"` foods ~85% of the time a match exists, falling back to the full pool when it would leave nothing (e.g. a vegan client who disliked every common option) — same "prefer, don't force" shape as the existing `_sesgar_por_preferencias()`, just a higher probability since "basico" is meant to read as *consistently* simple, not occasionally. Confirmed statistically that `basico`'s share of non-`"comun"` picks is genuinely lower than `normal`'s across 20 regenerations of a vegan profile (forcing tofu/tempeh into the candidate pool), and separately confirmed a client who disliked every common option still gets a real, non-empty plan.

**Diet: synergy pairing and its explanatory tips are now gated to `avanzado`/`tryhard`, not everyone.** Before this, every client — regardless of level — got the mechanical iron+vitamin-C pairing in `planificador_comidas.py`, the "today's largest fat portion" note on dinner, the probiotic+prebiotic-fiber callout, and `dieta_reglas._consejos_sinergias()`'s always-on tips list (vitamin D/E/K timing, iron absorption, caffeine/iron spacing, legume+egg/dairy zinc). A new `aplicar_sinergias = nivel_compromiso in ("avanzado", "tryhard")` flag threads through `_construir_comida()` and gates all of it — `"basico"`/`"normal"` still get a real, macro-matched, profile-adapted meal (the underlying fat-heavier-dinner *weighting* stays for every level, since it's a portion-math choice, not a "synergy" — only its explanatory sentence is gated), just without the pairing logic or the explanation. **Deliberately NOT gated**: `_sesgar_por_preferencias()` (the client's own explicit ask — anti-inflammatory, lower gluten, more fiber, etc. — and the structured stress/sleep/sedentary-job signals) stays active at every level, since suppressing a client's direct request to keep the UI "simple" would ignore what they actually asked for, a different thing entirely from the automatic pairing this change targets. Confirmed statistically (20 regenerations) that the pairing note never appears below `avanzado`, and unit-tested that `_consejos_sinergias()` itself returns nothing below that level even when `_consejos_por_preferencias_blandas()` (the ungated one) still contributes.

**Both engines' `motor="llm"` prompts rewritten for parity**, not just the free rule engines — the exact same basico/normal/avanzado/tryhard behavior (complexity stacking rule included, beginner exception included; food-familiarity/synergy-gating rule included) is now spelled out for the LLM path too, keeping the "two interchangeable engines, one schema" invariant intact.

**Four existing tests broke, all for the same reason and all a correct signal, not a regression**: they asserted synergy-pairing behavior (`consejos_sinergias` containing an iron tip, the vitamin-C pairing note, the dinner-fat sentence) against a `perfil_base` that defaults to `nivel_compromiso` unset (→ `"normal"`) — now correctly gated out. Fixed by setting `nivel_compromiso = "avanzado"` explicitly in each, since that's what those tests were actually about; a fifth (checking the combined `consejos_sinergias` list is empty at `basico`/`normal`) had to import `_consejos_sinergias()` directly instead, since `perfil_base`'s own default sedentary-job preference legitimately still contributes to the combined list through the ungated path.

12 new tests (exercise-complexity statistical/behavioral, food-commonality statistical + degrade-gracefully, synergy-gating behavioral at both the flat-tips and actual-plan level), 502 tests passing (up from 494), lint clean, all `examples/output_*.json` regenerated — confirmed the diffs land exactly where expected (client 1's `tryhard` routine changed via the new complexity bias, its diet didn't since `tryhard` already had synergies before and after; clients 2/3's `normal` diets changed by losing the now-gated general tips, their routines didn't since `normal` was never touched numerically).

**Follow-up the same session: `avanzado` was still too close to `normal`.** Confirmed directly (not assumed) that `avanzado` should be a genuine middle step, not "normal + supplement tips." Three more targeted questions, all answered "yes, add the real gradient":
- Routine: new `_preferir_complejidad_media_primero()` leans `avanzado` toward dumbbell-level exercises — a real 4-step complexity spectrum (`basico`→baja, `normal`→no bias, `avanzado`→media, `tryhard`→alta), never touching the curated `"nicho"` pool that stays `tryhard`-exclusive.
- Diet: `_sesgar_por_nivel_compromiso()` now biases both directions — `basico` toward `"comun"` foods (85% pull, unchanged), `avanzado` toward the `"comun": False` specialty ones (50% pull, new) — a real step toward `tryhard`'s separate `"nicho"` list without using it directly.
- Both `resumen_enfoque` sentences for `avanzado` were stale after this (still claimed "no training/food change") — caught and fixed before shipping, not after.

3 more tests (statistical), 505 passing, lint clean, examples regenerated.

---

## Equipment/location consistency, creative home training, and a Gmail crash fix

Four follow-ups from live use of the deployed app, shipped together.

**A real, reported bug**: `ui/app.py`'s "Where they train" and "Available
equipment" fields were independent widgets, so picking "Home with no
equipment" left whatever gym equipment was last selected (or the
all-selected default) untouched — a submitted profile could claim a
barbell at home with none. Fixed at the UI layer (clearing and disabling
the multiselect for that option) and, more importantly, at the rule-engine
layer: `rutina_reglas._material_cliente()` now ignores `material_disponible`
outright whenever `lugar_entreno` is `"casa_sin_material"`, the same
defense-in-depth reasoning `validator_agent.py` already applies elsewhere
(don't trust an upstream field when a more authoritative one contradicts
it) — this also covers the PDF-intake and "Revise client" pre-fill paths,
which the UI-only fix wouldn't have reached.

**Creative home training, requested directly** ("se creativo, ej: coger
garrafas de agua"): a new `"objetos_caseros"` equipment tag represents
household improvised weights (water jugs, a loaded backpack, a towel),
auto-added by `_material_cliente()` for any client training at home —
with or without gym-style equipment — mirroring how `"peso_corporal"` is
always implicitly available. One exercise per muscle group in
`exercise_bank.py` (9 total), none marked `"nicho"` since the goal is
variety at every commitment level, not gating behind `"tryhard"`.
`routine_agent.py`'s `motor="llm"` prompt got the matching instruction,
keeping engine parity.

**A real production crash, reported with the exact traceback**: a
revoked/expired Gmail refresh token makes
`google.auth.exceptions.RefreshError` bubble out of
`_obtener_credenciales()`'s `credenciales.refresh()` call — previously
uncaught, so it propagated past `ui/app.py`'s narrow
`except (GmailClientError, ImportError, ModuleNotFoundError)` and crashed
the whole app instead of just failing the draft/send action. Same failure
shape as the earlier PDF-generation crash (see the "Making the commitment
dial actually change the routine and diet" section above); fixed the same
way — wrapped into `GmailClientError` with an actionable message (delete
`token.json`, re-run the OAuth flow, update the `GMAIL_TOKEN_JSON` secret
on Streamlit Cloud). Re-authorizing itself still needs the project owner
to actually do it; the fix only stops it from taking the app down.

**The commitment-level caption** became a real per-tier bullet list
(`- **Basic:** ...` / `**Normal:**` / `**Advanced:**` / `**Tryhard:**`)
instead of one run-on sentence, in both languages.

3 new tests (equipment/lugar_entreno interaction, objetos_caseros
availability by location, the RefreshError regression), 508 passing (up
from 505), lint clean, `examples/output_rutina_3.json` regenerated (the
only example client who trains at home). The equipment auto-clear was
also confirmed live in the browser (multiselect empties and disables,
caption appears) rather than by test coverage alone.

---

## Short portal links, a minimalist client portal, and less "AI-sounding" emails

A real, blunt complaint the same day: the client portal link was ~250
characters and "queda algo raro." Traced to `agents/portal_tokens.py`'s
design — a stateless, HMAC-signed token carrying the client's email +
Notion page ID + expiry, base64'd and hex-signed. Replaced entirely
(not shrunk) with a short, opaque ~8-character reference code
(`secrets.token_urlsafe`) stored on the client's own Notion record —
new `mcp/notion_connector.generar_referencia_portal()`/
`resolver_referencia_portal()`, two new schema properties added via
Notion's API (`Portal Reference`, `Portal Reference Expires`, same
non-manual approach as earlier schema additions). `agents/portal_tokens.py`
and its test file were deleted outright rather than left as dead code;
`PortalTokenError` moved into `notion_connector.py`, the only module that
raises it now. Trade-offs, disclosed rather than glossed over: the design
gives up "verifiable with zero network calls" (the portal already hits
Notion immediately after resolving the link anyway, so this was never a
real round-trip saving), and every already-sent link under the old format
stops working — no backward-compat shim, a fresh link is one click away.
A genuine upside: the trainer can now revoke a link early by hand
(clearing the Notion property), which the old design explicitly couldn't
do. Verified against the real workspace, not just mocked tests: created
throwaway test records, issued and resolved real reference codes,
confirmed the round trip and the 7-day expiry check, opened the actual
generated `?ref=...` URLs in a live browser session, then archived the
test records.

**A new "Language" property closes a real gap**: the portal used to
always render its own chrome (headers, captions, the check-in form) in
English, regardless of what language the client's plan was actually
generated in — no way for a fresh client browser session to know which
language the trainer had selected. `guardar_registro_cliente()`/
`actualizar_registro_cliente()` now save `st.session_state.lang` at
approval time; `_vista_portal_cliente()` reads it back and sets the
page's language before rendering anything. Verified live with two real
test records (one `idioma="en"`, one `idioma="es"`) — each portal link
rendered fully in its own saved language.

**The portal page itself was rebuilt to be more minimal**, a direct
complaint ("tiene un texto enorme al principio... elimínalo,
minimalista, con pocos clicks"): the ≤2000-character prose summary
(`registro["resumen"]`) that used to open the page is gone outright —
the client's actual current-week meals/routine (already read back in
full) already cover what a client needs to see, better than a truncated
paragraph ever did. The two separate "Your meals"/"Your routine"
expanders were merged into one "📋 Your plan this week" section,
expanded by default — the main reason a client follows the link now
needs zero clicks instead of one-or-two.

**`experiencia.nivel_compromiso`'s "avanzado" option now shows "(PRO)"**
in the commitment-level dropdown specifically — not through the shared
`OPTION_LABELS` dict (that would leak onto `experiencia.nivel`'s own
unrelated "Advanced" label, the exact F601 collision fixed earlier this
project), but via a small dedicated `_opt_compromiso()` format function
used only for that one selectbox.

**Every client-facing (and the trainer-notification) email template in
`mcp/gmail_client.py` was rewritten to read less like an automated
assistant**, a direct, general request ("que parezcan mucho menos IA").
The plan email (`_construir_cuerpo_email()`) lost its bulleted
"📎 Attached: • X • Y" list and "👉"-prefixed tip callouts in favor of
plain sentences, and now greets by first name only
(`nombre_cliente.split()[0]`) instead of the client's full name — reads
warmer every time. The portal-link email switched from third-person
("ask your trainer for a new one") to first-person ("just ask me") —
a real trainer sending their own email wouldn't refer to themselves in
the third person; that phrasing was itself an automated-system tell.
Kept deliberately: the 🏋️/🍽️ section labels (a real prior scannability
request, not cosmetic) and every piece of actually load-bearing
information (what's attached, how to re-attach a reply, how to open a
PDF whose fields won't fill in-browser) — personalizing the tone never
meant cutting content the client actually needs.

**Not built, deliberately flagged instead of silently ignored**: a
direct observation that a liked meal/exercise "no se puede quitar ahora
mismo" (can't currently be un-liked) is accurate and by design —
`agregar_comida_favorita()`/`agregar_ejercicio_favorito()` only ever
append. Documented as a known limitation in `README.md` rather than
built speculatively, since removing a favorite wasn't an explicit
request on its own.

6 new/updated test files, 508 tests passing (unchanged count — net
addition offset by the removed `test_portal_tokens.py`), lint clean, no
`examples/output_*.json` diffs (none of this touches the rule engines).

---

## Two real personalization bugs: pull-ups with no bar, tofu for an omnivore

Two concrete, reported bugs the same day — "los ejercicios de en casa sin
equipamiento no funcionan... ponen dominadas, ponen fondos" and "aún
tiene cosas muy raras para una dieta normal."

**Routine**: `exercise_bank.py`'s `"peso_corporal"` tag conflated "needs
literally nothing" (push-ups, bodyweight squats) with "needs a fixed
anchor" (pull-ups, dips) — both were treated as always available since
`_material_cliente()` grants `"peso_corporal"` unconditionally ("the body
is always available"). Split out a new `"estructura_fija"` tag (pull-up
bar / dip station); `_material_cliente()` grants it for gym locations
(near-universal gym equipment) but not either home location. Pull-ups,
weighted pull-ups, parallel bar dips, and dragon flag now require it.
Each affected muscle group keeps a genuine zero-equipment "basico"
alternative (push-ups, inverted rows), confirmed by regenerating
`examples/output_rutina_3.json` (the one home-training example client):
"Parallel bar dips" → "Push-ups (standard)".

**Diet**: `food_bank.py`'s soy/gluten protein alternatives (tofu, tempeh,
edamame, seitan, "Protein powder (plant-based)") declare `tipos_dieta`
including `"omnivora"` — needed so a vegetarian/vegan client gets them as
genuine protein staples, but that also made them equally likely
candidates for a meat-eating client at "basico"/"normal"/"avanzado",
where they read as out of place rather than "specialty" (the existing
`"comun": False` tag only biases selection at basico/avanzado —
"normal" applies no bias at all). Scoped directly with the project owner
first (two questions: how "real" should groceries get — generic-common
vs. actual branded supermarket products; keep exotic items for tryhard
or drop them everywhere) before touching anything, since "ground the
diet in real Mercadona/Lidl/Consum/Aldi products" was the original,
much bigger ask — descoped to the tractable version: no branded product
data, just fixing which existing foods are treated as common. New
`"nicho_omnivoro"` tag + `food_bank._demasiado_nicho()` (replacing the
inline nicho check in all four `fuentes_*_para()` functions) makes these
five foods tryhard-exclusive specifically when `tipo_dieta == "omnivora"`
— a vegetarian/vegan client still sees them at every level, unaffected.
`diet_agent.py`'s `motor="llm"` prompt updated for parity. Natto stays a
plain, unconditional `"nicho"` food (being fermented/unusual has nothing
to do with diet type, unlike these).

Branded, per-supermarket product data (the original, bigger ask) was
deliberately not built this round — real product names/prices go stale
without an ongoing maintenance source, and neither Lidl/Aldi/Consum
expose a public API TrainFitter could query live. Left open as a
possible later phase, gated on the project owner supplying real
product/macro data or confirming a best-effort web-research pass is
good enough.

7 new tests (exercise-anchor exclusion at both home locations + gym
regression check, plant-protein exclusion across every non-tryhard level
+ vegetarian/vegan unaffected), 512 passing (up from 508), lint clean,
one example diff (`output_rutina_3.json`, expected).

---

## Bullet points for the plan email, then the same treatment for the portal

Direct, pasted-example follow-up the same day: the plan email's "less
AI" pass earlier this session still read as unbroken paragraphs — "que
sean como bullet points... si hay mucho texto nadie se lo lee." New
`gmail_client.dividir_en_puntos()` splits `mensaje_para_el_cliente` (and
its tip -- `progresion`/the first `consejos_sinergias` entry) into
individual sentences, rendered as `• `-prefixed lines instead of a
paragraph; the attachment/reply-instructions text stays plain prose on
purpose (already short, doesn't need bulleting). Each fragment's first
letter is capitalized -- the first one is often the tail of a greeting
`quitar_saludo()` already stripped ("aquí tienes tu rutina..."), which
would otherwise open a bullet list lowercase.

**"Aplica esto también al portal"** surfaced a real, separate gap:
`obtener_registro_cliente()` never read back `mensaje_para_el_cliente`
at all — only the technical `resumen_enfoque`-based "Summary", which had
already been cut from the portal for being unreadable prose (see the
reference-link section above). The trainer's actual warm note had never
reached the portal in any form. New "Routine Message"/"Diet Message"
Notion properties (added via the API, same pattern as every prior schema
addition) store it raw; `_vista_portal_cliente()` reuses
`gmail_client.quitar_saludo()`/`dividir_en_puntos()` (both promoted from
private to public functions, now imported by `ui/app.py` too) so the
portal renders the exact same bulleted note the email does, with no
second formatting implementation. `notion_connector.py` importing from
`gmail_client.py` is a first for this project (previously two
independent sibling connectors) — accepted since both functions are
pure, dependency-free text formatting, not anything that drags in
`googleapiclient`.

**A real, live-caught bug along the way**: the Spanish translation dict
was missing `"portal_plan_header"` entirely (added to English only, in
the reference-link/portal-redesign round earlier this session), and
`"portal_meals_header"`/`"portal_routine_header"` still carried their
pre-redesign, un-shortened Spanish text. A Spanish-language client with
an actual saved weekly plan would have hit a `KeyError` opening their
own portal — missed originally because the one live-tested Spanish
portal check that round happened to use a test client with no
`plan_semanal`/`sesiones` set, so the broken code path never ran. Caught
this time by a dedicated EN/ES key-symmetry check (parsing
`TRANSLATIONS` via `ast` and diffing the two language's key sets)
rather than by another lucky manual click-through — worth keeping as a
real regression check, not a one-off script.

10 new/updated tests, 519 passing (up from 512), lint clean, no example
diffs. Verified against the real Notion workspace: saved a throwaway
client with a real trainer message in Spanish, confirmed the portal
rendered the correctly-stripped, correctly-bulleted note, archived the
test record after.

---

## Fewer gates, Spanish by default, and a much harder cut on client-facing text

Five direct requests from live use, all shipped the same session.

**Dropped the upfront password gate on "Revise client"/"Clients".** The
trainer was hitting the password prompt twice to look up a client — once
for `_gate_datos_clientes()`'s whole-section unlock, again for
`_cargar_ficha_para_revisar()`'s own per-lookup re-check, which already
independently protects the one action that actually reveals a client's
health data. `_gate_datos_clientes()`/`_datos_clientes_desbloqueados()`
deleted outright (no dead code left behind); the per-lookup check is now
the only gate, and it was already the right one. Confirmed directly
before removing "Clients"' gate too, since that section shows no
per-client data at all (anonymized KPIs/charts only) — the project owner's
own call, explicitly weighing that a public-demo visitor could now see
the (anonymous) fleet dashboard with no password at all.

**"Revise client" also dropped its collapsed `st.expander`** — direct
request ("que se abra automáticamente o quítalo"): the email field is the
first thing a trainer needs there, not worth an extra click to reveal.
Rendered directly under a plain subheader now, same pattern the rest of
this file already uses for primary content.

**Default UI language switched from English to Spanish** —
`st.session_state.lang` now initializes to `"es"`. One-line change; the
language toggle itself, and per-client persistence via the portal's
"Language" property, are unaffected.

**Client-facing text (email, portal, and by extension anywhere else that
reads from the same fields) got a much harder second cut.** The first
"bullet the whole message" pass, shipped earlier the same day, still read
as "MUY generales y mucho texto" against a pasted real example. The fix
isn't more bulleting — it's less content: `mensaje_para_el_cliente` (the
trainer's generic warm note) is now dropped from the email/portal
entirely whenever a real tip exists (`progresion` for routine, the diet's
first `consejos_sinergias` entry) — new
`gmail_client.obtener_texto_cliente()` picks the tip over the message,
falling back to the message's own first sentence only when no tip exists
at all (a "normal"/"basico" diet has no consejos_sinergias — synergy tips
are gated to avanzado+). Section labels dropped their 🏋️/🍽️ emoji too
("Routine:"/"Diet:", plain), matching the exact minimal format given as a
target. `notion_connector.py`'s "Routine Message"/"Diet Message" now
store this same reduced text (not the raw message), reusing
`obtener_texto_cliente()` — a second, deliberate cross-import from
`gmail_client.py` (same pure-function reasoning as `dividir_en_puntos()`/
`quitar_saludo()` before it) so the portal renders byte-identical content
to the email, not a second, looser summary computed independently.
`ui/app.py`'s portal notes section simplified to match: no more
`quitar_saludo()` call there at all, since the stored text already
arrives pre-stripped and pre-reduced.

**The PDFs were deliberately left untouched.** Read `pdf_generador.py`
before changing anything: unlike the email/portal, the PDF is already a
properly structured, detailed reference document — one short intro
paragraph, then macros, a full weekly table, and already-bulleted
food-source/tip lists. It's not "mucho texto sin estructura," it's the
place this project's own design already says the plan's real detail
should live (see `_construir_cuerpo_email()`'s own docstring: "the plan's
own detail lives in the attached PDFs now, not inlined here"). Stripping
its intro note the same way would cut the one thing that makes the PDF
feel personally written rather than a spec sheet, without the "too much
text" problem the email/portal actually had.

Verified live against the real running app and the real Notion
workspace: default language loads as Spanish, "Revise client"/"Clients"
render immediately with no password prompt, a real portal record shows
the exact target format (`Rutina:` / two tip bullets / `Dieta:` / one
synergy-tip bullet), confirmed byte-for-byte against the email's own
output for the same borrador. 521 tests passing (up from 519), lint
clean, no `examples/output_*.json` diffs.

---

## The PDFs get the same cut

Direct follow-up the same day: "recorta también el texto de los PDFs...
hay bastante texto que puede resumirse/eliminarse." Read
`pdf_generador.py` in full before changing anything, since the previous
round had deliberately left the PDFs alone (judged them already
well-structured). Two real things were still worth cutting once actually
compared against the trimmed email/portal:

- **`mensaje_para_el_cliente`** (the generic warm note) is dropped from
  both PDFs entirely — same content, same reasoning as the email/portal
  cut. `resumen_enfoque` ("Overview" in the routine PDF) stays: unlike
  the generic note, it states real, plan-specific facts (split, level,
  days/week, why a set count changed), not filler.
- **The diet PDF's "Meal distribution" paragraph and its four "Suggested
  X sources" lists** (every valid candidate food per category, not a
  curated few — often 20+ items across all four) are now shown ONLY when
  `plan_semanal` is absent. When the real weekly table exists, it already
  answers "what do I eat" concretely, meal by meal; a second, much longer
  catalog of every other valid option next to it was genuinely redundant
  bulk, not something that helps the client. The fallback path (no weekly
  table — an older draft format, a hand-built fixture) keeps both, since
  without a table there'd be nothing concrete to eat at all otherwise.

Kept everywhere: daily targets/macros, the weekly meal table itself,
every per-session exercise table, the effort cue, optional cardio,
`progresion` ("How to progress"), and `consejos_sinergias` ("Tips") —
none of these were ever generic; they're the concrete, plan-specific
content this document exists to deliver.

Verified by actually generating and reading a real PDF (`output_dieta_3
.json`/`output_rutina_3.json` fed through the real reportlab renderers),
not just by reading the code: the diet PDF for a client with a real
weekly plan is now title → daily targets → weekly table → tips → footer,
with zero generic paragraphs. 5 new tests, 524 passing (up from 521),
lint clean, no `examples/output_*.json` diffs (PDFs aren't part of that
regeneration check; behavior confirmed by direct rendering instead).

---

## One more email cut, and a real swipe-style meal-liking redesign

Three more direct requests.

**The plan email's fixed closing was removed outright** ("quita este
texto"): "I've attached the PDFs..."/"If your mail or Drive preview
won't let you type into the PDF's fields..." added a paragraph without
adding information — every mail client already shows its own attachment
indicator. The checklist reply-instructions paragraph stays when
`incluir_checklist=True` (genuinely functional: without it, a client's
reply carries no attachment for `main.py` to parse), reworded to name
the checklist itself ("el checklist que te adjunto") so it still reads
standalone without the sentence that used to introduce it.

**Meal liking was rebuilt as a real swipe-style flow**, direct request
("rollo tinder... que no se pierda mucho tiempo"): `plan_semanal` is
flattened into one ordered list and walked through via a session-scoped
index, one meal at a time — big "➡️ Skip"/"❤️ Like it" buttons instead of
a tiny heart icon buried in every row of a long list. Not a literal
touch-swipe gesture — Streamlit has no native gesture support, and a
custom JS component would be fragile across mobile browsers for little
real gain over two buttons achieving the same "fast, one decision at a
time" outcome reliably.

**The un-like bug got a genuine fix, for meals** — new
`notion_connector.quitar_comida_favorita()` (the inverse read-modify-
write of `agregar_comida_favorita()`) actually removes a meal from
"Liked Meals (JSON)". The swipe card now shows a real, server-derived
like state (`obtener_registro_cliente()` gained `"comidas_favoritas"`,
read fresh on every rerun) instead of the old session-local "already
clicked" tracking that a page reload silently lost — the bug report was
literally "no se puede quitar el corazón."

**Exercise liking was removed entirely**, direct request ("quítalo para
ejercicios"): the routine section of the portal is a plain read-only
list again, no heart button. `agregar_ejercicio_favorito()` and the
existing "Liked Exercises (JSON)" property/rule-engine bias were left in
place — a deliberately narrow removal of the portal's write path only,
not the underlying mechanism or any client's already-recorded likes.

Verified live end to end against the real Notion workspace, including
the part that matters most: liked a meal, reloaded the portal in a fresh
session, confirmed it showed as already-liked (state genuinely
persisted, not session-local), then un-liked it and confirmed that
persisted too. 7 new/updated tests, 528 passing (up from 524), lint
clean, no example diffs.

---

## Three follow-ups: a language-drift bug, check-in-driven regeneration (as a draft, not a send), and a genuinely advanced routine tip

Three direct requests, same conversation.

**Language consistency.** A real, reported bug: every email/PDF/portal
call site in `ui/app.py` read `st.session_state.lang` — the trainer's
*current* UI toggle — at the moment each action ran, not the language the
specific plan was actually generated in. Toggle the language after
generating a plan but before approving/emailing it (same session), and
the portal-link email, the Gmail draft, or the saved Notion record could
end up in the wrong language relative to the PDFs already generated.
Fixed by capturing `idioma` at generation time,
`id(perfil)`-keyed into session state (same pattern as `aprobado_para`/
`notion_guardado_para` elsewhere in this file), with a new
`_idioma_del_perfil(perfil)` helper every downstream call site
(`actualizar_registro_cliente`/`guardar_registro_cliente` in
`_ejecutar_aprobacion()`, `crear_borrador`/`enviar_enlace_portal` in
`_panel_aprobacion()`) now uses instead of the raw toggle.
`enviar_notificacion_checkin()` needed no fix — `_vista_portal_cliente()`
already sets the toggle from the plan's own saved `idioma` before that
call runs.

**Check-in-driven regeneration — scoped down from the literal ask, on
purpose.** The request was: when a client checks in, regenerate the
plan and automatically email the client the new plan plus a fresh
portal link. Taken literally, that breaks this project's central
guarantee — "TrainFitter never contacts a client on its own" — every
other outgoing email in this codebase is either trainer-triggered or a
narrow, previously-confirmed exception (`enviar_enlace_portal()`,
`enviar_formulario_intake()`). Surfaced this directly instead of
building it as asked or silently declining; the project owner chose
"regenerate + draft" over "regenerate + really send." Implementation:
`_vista_portal_cliente()`'s check-in handler, after saving the Check-ins
row (best-effort, same as the existing trainer-notification block below
it — a failure here never blocks the check-in already saved), reloads
the client's full profile (`notion_connector.obtener_perfil_completo()`,
the same source "Revise client" already reads), substitutes in the
just-logged weight if the client shared one (a real mechanism for the
calorie-recalculation promise `dieta_reglas.py`'s own message has always
made — closes the same gap the "Weight (kg)" field closed for display
purposes only), reruns the full pipeline, overwrites the Clients record
in place (`actualizar_registro_cliente()`, one master record per client,
same as a trainer-initiated revision), and drops a Gmail **draft**
(never sent) with the regenerated plan. `crear_borrador()`/
`_construir_cuerpo_email()` gained an optional `url_portal` parameter so
the fresh portal link rides along in that same draft rather than a
second email ("dentro del mismo correo," matching what was actually
asked for once auto-send became auto-draft) — a fresh reference is
generated (`generar_referencia_portal()`) each time, same as a
trainer-sent portal link. The trainer still reviews and sends this
draft themselves, same guarantee as everything else. Not yet live-tested
against the real workspace (would need a real client with an existing
portal reference) — covered by unit + mocked-network tests instead,
disclosed rather than assumed working.

**A genuinely advanced routine tip.** `dieta_reglas.py`'s
`_consejos_sinergias()` (vitamin absorption timing, iron/vitamin-C
pairing) was already gated to avanzado/tryhard — pointed to directly as
the model to follow. The routine side had no equivalent: every client,
regardless of `nivel_compromiso`, got the same "add a rep, then add
weight" `progresion` text — genuinely the right level for basico/normal,
but something an avanzado/tryhard client (who explicitly asked for more
detail) already knows. New `PROGRESION_AVANZADA_VARIANTES`, gated the
same way `_consejos_sinergias()` is, grounded in the same evidence
`docs/base_conocimiento/entrenamiento.md` already cites rather than
invented content: MEV/MAV/MRV block progression with a deload before the
recoverable ceiling, reps-in-reserve as the thing that should calibrate
every set (not just "add a rep"), and training frequency. `routine_agent.py`'s
LLM prompt got the matching instruction for engine parity. The
"avanzado" summary line's claim that "the rest of the extra detail is in
your diet" was true before this and is no longer — reworded. Verified
live: generating client 1's (tryhard) example plan in Spanish showed the
frequency variant of the new advanced tip, correctly translated.
`examples/output_rutina_1.json` regenerated — the only example client at
avanzado/tryhard, so the only diff; `mensaje_para_el_cliente` also
shifted to a different (pre-existing) variant for that same client, a
side effect of the per-client RNG stream consuming a different number of
values when the progresion pool it draws from changes size, not a
content change. 7 new/updated tests, 535 passing (up from 528), lint
clean.

---

## Automatic send for validator-approved plans — a genuine reversal of "TrainFitter never contacts a client on its own"

Requested directly: when a new (or revised) client's plan needs no
enhanced review, generate and send it automatically instead of waiting
for the trainer to approve, create a draft, and send it themselves. This
is the first real exception to this project's headline guarantee that
applies to unreviewed plan *content*, not just a fixed template
(`enviar_enlace_portal()`, `enviar_formulario_intake()`) or a message
aimed at the trainer's own inbox (`enviar_notificacion_checkin()`) — a
genuine client now receives content nobody looked at first, by explicit
design, whenever the validator itself already vouched for it.

**Scope, confirmed before building rather than assumed:** two open
questions were asked directly first. (1) Does this cover only brand-new
clients, or also "Revise client" (regenerating an existing client's
plan)? Answer: both — any generation with a validator verdict of
`aprobado_automatico` qualifies, new or revised. (2) The public demo
(trainfitter.streamlit.app) never gated *generating* a plan, only
approving/sending it — if send becomes automatic with zero clicks, any
visitor could make the app email an arbitrary address for free. Answer:
`APP_APPROVAL_PASSWORD` (already used to gate every other real send)
stays as the one confirmation step immediately before an automatic send,
on any deployment where it's set; on a private deployment with no
password configured, it's genuinely zero-click, as asked.

**What changed:**
- `datos_basicos.email` is now part of the intake schema (`_formulario_
  ficha_nueva()`, `agents/pdf_intake.py`'s fillable form) — previously
  the recipient was only ever typed in later, at Gmail-draft time, which
  made zero-click send impossible (nowhere to send to at generation
  time). A blank/malformed email doesn't block generation; it just means
  that plan doesn't qualify for auto-send and falls back to the existing
  manual flow, same as a "revision_reforzada" plan always does.
- `mcp/gmail_client.py` gained `enviar_plan()` — the fourth, and by far
  the biggest, exception to the `gmail.send` "narrow and deliberate"
  principle documented in that module's docstring. Shares its content-
  building (PDFs, body) with `crear_borrador()` via a new
  `_preparar_envio_plan()` helper; the two differ only in the one Gmail
  API call at the end (`messages().send()` vs `drafts().create()`).
- The portal link is folded into the *same* email as the plan now
  (`crear_borrador()`/`enviar_plan()` both gained an optional
  `url_portal` parameter, reusing the mechanism built for the check-in-
  regeneration draft the same week) — "unifica en el mismo correo," a
  direct request, and it keeps the auto-send email to exactly one
  message instead of two.
- `ui/app.py`: `_panel_envio_automatico()` replaces `_panel_aprobacion()`
  entirely for a qualifying plan — no separate Approve/create-draft/
  check-if-sent/send-portal-link steps, since a real send is confirmed
  the instant `enviar_plan()` returns without raising (unlike a draft,
  there's nothing later to verify). `_ejecutar_envio_automatico()`
  mirrors `_ejecutar_aprobacion()`'s Notion-save branch exactly (same
  `revisar_perfil_id`-based check for whether this is a revision) since
  there's no separate "Approve" click left to gate that behind. On
  failure (a Gmail or Notion error), the panel shows the error and falls
  back to rendering the *existing* manual panel underneath — approve,
  then create a draft by hand — so a trainer is never stuck with a plan
  that can't go out any way at all.
- The verdict banner (`_mostrar_veredicto()`) now says explicitly when a
  plan is about to send itself, instead of unconditionally repeating "it
  still needs your approval before sending" — that line is no longer
  true for this path, and a stale claim directly above a panel that
  contradicts it would be confusing on the same page.
- A "revision_reforzada" plan is completely unaffected — always a draft,
  the trainer always reviews and sends it, exactly as before this
  change. So is the example-client demo path (`guardar_en_notion=False`
  rules out auto-send unconditionally, same gate that already protected
  Notion auto-save from the demo path).

**Testing note, matching this project's established bar for every other
real send:** `enviar_plan()` is covered by mocked-network tests
(`tests/test_gmail_client_network.py`) exercising the actual request
body (attachments, portal link), not a live send during verification —
this repo's dev environment has real Gmail/Notion credentials configured
locally, and `APP_APPROVAL_PASSWORD` isn't set there, so a live
end-to-end test of the New Client form would have sent a genuine,
unreviewed email through the trainer's real account with no way to abort
partway through. Verified live only up to the safe boundary instead: the
new Email field renders correctly in the New Client form, and a profile
with a declared injury (guaranteed `revision_reforzada`) still renders
the ordinary manual approval panel, confirming the new auto-send branch
doesn't fire when it shouldn't. The actual browser-driven form
submission for a real send attempt was also blocked by this session's
own tool-permission classifier when attempted programmatically — treated
as a genuine signal, not routed around.

---

## Portal reliability + a real navigation gap, then a full redesign into collapsible sections

Three follow-ups, same day as the automatic-send change above.

**A real crash, correlating with the reported symptom.** The client
portal's report was "the link breaks after the app goes to sleep and
takes you straight to the home screen." `_vista_portal_cliente()`'s
first step, `resolver_referencia_portal()`, can raise either
`PortalTokenError` (a genuinely invalid/expired code) or
`NotionClientError` (a Notion API failure) -- only the first was caught.
A transient Notion failure, plausible right when a cold-started
deployment wakes up and makes its first request, propagated straight
past the narrow `except PortalTokenError` clause and crashed the whole
page instead of showing a recoverable message. Fixed by catching
`(NotionClientError, ImportError, ModuleNotFoundError)` too, same
pattern already used one function down for `obtener_registro_cliente()`.
Disclosed honestly rather than claimed as the full fix: Streamlit
Community Cloud's own wake-up redirect may also drop the `?ref=...`
query string outright in some cases, a platform behavior this function
has no way to control or verify from inside the app.

**A real navigation gap in the swipe flow.** Liking or skipping a meal
only ever moved forward -- no way to go back and re-see (or change) the
previous decision. `_render_swipe_comidas()` gained a "⬅️ Back" button,
shown whenever the index is above 0, both mid-flow (alongside Skip/Like)
and on the final "done" screen (alongside Restart, stepping back to the
last meal instead of all the way to the first).

**A full redesign of the portal's layout, requested directly.** The
single combined "Your plan this week" expander (meals + routine
together) became four independent, individually-collapsible sections
(Notes, Meals, Routine, History), plus a fifth for the check-in form
itself -- all collapsed by default except Meals, which stays open (the
one reason most clients follow the link at all keeps needing zero
clicks). The opening text was cut further too: the separate "TrainFitter"
title plus a full greeting header collapsed into one small caption plus
a single title-sized welcome line, and the "Client since {date})" caption
was dropped outright rather than shortened -- two now-unused translation
keys (`portal_plan_header`, `portal_since_label`) were removed with it.
Verified live against the real workspace (the same "PEPE" test client
used for earlier portal verification this project): the invalid-link
error path renders correctly without crashing, and a real client's view
shows Meals open with the rest collapsed, Back correctly hidden at the
very first meal and appearing from the second meal onward, and stepping
back with it lands exactly on the previous meal.

---

## Self-service portal-link recovery: found, then a real production crash on the public demo

Two things, same day.

**The public demo was actually down.** Asked to verify the previous
change on trainfitter.streamlit.app, not just locally — found it
crashing with `ImportError` at `from gmail_client import (...)` in
`ui/app.py`, persistent across ~50 seconds of retries, while the exact
same import worked cleanly locally (direct import, `ast.parse`, the full
test suite). The pattern — `ImportError` (not `ModuleNotFoundError`)
anchored exactly at the line that gained a new name (`enviar_plan`) —
matches a stale deployment that hadn't picked up the latest push more
than an actual code bug; nothing in `gmail_client.py`'s own module-level
code (pure stdlib) could explain a fresh failure. Reported directly
rather than guessed at further or silently worked around — this
session has no access to Streamlit Cloud's dashboard/logs/reboot
control, only the project owner does.

**Self-service link recovery, researched and scoped before building.**
Requested: when a client's portal link breaks, let them get a new one
without asking the trainer directly — ideally fully automatic. Three
options were researched and presented with real tradeoffs: (1) an
in-app form right on the broken-link screen (email in, a fresh link out
— instant, reuses existing functions, no fragile parsing); (2) replying
to the original plan email with a trigger phrase (closer to the literal
first phrasing, but cron-delayed and fragile — recognizing "please
resend" in free text, multilingual, isn't reliable); (3) notifying the
trainer instead of auto-sending (zero automation risk, but not what was
asked for). Option 1 was chosen.

`_formulario_reenviar_link_portal()` renders on every error path in
`_vista_portal_cliente()` (invalid/expired code, and a Notion hiccup on
either the resolve or the load step) — reuses `buscar_cliente_por_email()`
(already used by "Revise client") to find the record, then the exact
same `generar_referencia_portal()`/`enviar_enlace_portal()` pair the
trainer's own manual resend button already calls. No new send-capable
function, no widened Gmail scope. `generar_referencia_portal()` already
overwrites the client's "Portal Reference" property in place, so the
old broken/expired code stops working the instant the new one is
issued — confirmed live, not assumed.

A same-turn follow-up sharpened the ask further: not just email the new
link, but land the client on it immediately. Since `st.query_params["ref"]`
is the exact value the top-level dispatch already reads to decide which
portal to render, setting it programmatically and calling `st.rerun()`
*is* an in-app redirect — no meta-refresh hack, no leaving the page,
and the browser's own URL bar updates too (confirmed: bookmarking or
reloading from that point keeps working). The email still sends in
parallel as a durable fallback that survives the tab closing; the
redirect isn't a replacement for it, both happen.

**Disclosed, accepted limitation:** no rate limiting beyond a client
typing their own email each time — someone who already knows a real
client's address could trigger repeated resend emails to it. Same risk
class `enviar_enlace_portal()` already carries for a trainer-triggered
resend (this form only ever reaches an address already on file as a
real client, never an arbitrary one), not a new exposure.

Verified live against the real workspace (the "PEPE" test client): a
made-up email correctly shows "no account found"; the real match sends
a real portal-link email, redirects the browser in-app straight to
PEPE's actual plan (URL bar updates to the new `?ref=...` code), and the
old link — tested directly afterward — no longer resolves.

---

## A missed unification, resistance bands, and meals grouped by day

Three follow-ups, all from actually using the app and asking direct
questions about what the intake form does.

**The portal-link + PDF unification never reached the manual approval
flow.** The earlier "unify the plan and the portal link into one email"
work only touched `enviar_plan()` (the auto-send path) and the check-in
regeneration draft — `_panel_aprobacion()`'s "Create Gmail draft" button,
the one actually used for every `revision_reforzada` plan (the majority
of real trainer review work), never passed `url_portal` to
`crear_borrador()` at all. The standalone "Send portal link" button
right below it sent a genuinely separate email. Fixed: "Create draft"
now generates a fresh portal reference itself (best-effort — a Notion
hiccup still lets the draft go out, just without the link) and folds it
into the same draft; the standalone button and its now-dead translation
keys are gone. `enviar_enlace_portal()` itself is untouched and still
used by the portal's own self-service resend form, a genuinely different
use case (a quick link-only recovery send, not the full plan).

**Resistance bands ("gomas"), requested directly ("gomas y otros tipos
de ejercicios caseros").** Every muscle group already had exactly one
`"objetos_caseros"` (household-object) exercise, auto-granted for home
training — but no band exercises existed at all. Added as a real, manual
`MATERIAL_OPCIONES` pick (unlike `objetos_caseros`/`peso_corporal`,
which are auto-granted) — selectable at any training location, not
home-only, since bands show up in gyms too — with one exercise per
muscle group (9 total), matching the household-object pool's density so
"the actual 'make it adaptable' ask" (more equipment combinations = more
distinct candidate pools per slot) is real, not just a longer dropdown.
`routine_agent.py`'s LLM prompt got the matching instruction for engine
parity.

**Meals grouped by day in the portal, direct correction.** The swipe
flow flattened the whole week into one meal-at-a-time sequence — a real
complaint ("que salgan todas las comidas del día juntas... ahora solo
sale 1"). Rebuilt to walk day by day instead of meal by meal: a day's
breakfast/lunch/dinner/snacks all render together, each with its own
independent like button, no per-meal skip anymore (redundant once every
meal in the day is already visible — not clicking "like" already means
"skip," so removing the extra click lost no functionality). Verified
live against the real workspace (the "PEPE" test client): day 1 shows
all three meals grouped with correct persisted like state, "Next day"
advances to day 2 with "Back" now visible, and every gomas-tagged
exercise round-trips through both the manual form and the fillable
intake PDF correctly. 547 tests passing (up from 543), lint clean, no
example-output diffs (no example client selects "gomas").

Separately, answered two direct questions about what the intake form
actually does, without changing any code: (1) a declared health
condition — including the PCOS/"ovarios poliquísticos" example asked
about directly — forces `revision_reforzada` and nothing else; no
condition-specific logic exists anywhere in either rule engine, by
design (defense-in-depth defers clinical adaptation to the trainer,
same as every other declared condition). (2) A full field-by-field audit
found three intake fields that are collected, stored, and round-trip
through the PDF but are never read by generation at all:
`experiencia.anios_entrenando`, `experiencia.detalle`, and
`lesion.estado`/`lesion.activa_actualmente` (an injury is treated
identically whether marked "old, controlled" or "active"). Disclosed
directly rather than silently left as an assumed gap — no fix requested
yet.

---

## Trainer-driven diet/routine adjustments (searchable dropdowns, not free text), and a portal visual pass

**Researched before building, per a direct request.** "Let the trainer
change the diet by writing changes in plain language" has no free,
reliable implementation — genuinely arbitrary natural language needs an
LLM to interpret robustly, which breaks this project's free-only
guardrail for every use, not an opt-in edge case. Presented three real
options (free keyword matching, a paid LLM edit, a note-only field with
no automation) with their tradeoffs; the project owner chose a fourth,
better-scoped middle ground once the tradeoffs were visible: a curated,
deterministic set of adjustments picked from a **searchable multiselect**
(`st.multiselect` already supports typing to filter) rather than typed
free text — real effects, still 100% free, no ambiguity about what got
applied.

**Diet** (`nutricion.ajustes_dieta`, `food_bank.ajustes_dieta()`): 9
adjustments — protein up/down (~15%), carb/fat balance both ways (fat%
is the one shared dial carbs trade against at a fixed protein/calorie
target, so "more carbs" and "less fat" are deliberately the same lever,
not two), calories up/down (~10%), dairy-free (soft-excludes
`lacteo`-tagged foods the same way `reducir_gluten` already excludes
gluten), and meal count up/down (bounded 3-6). Deliberately does NOT
duplicate `preferencias_blandas()`'s existing categories
(antiinflamatorio/reducir_gluten/salud_digestiva/mas_fibra/mas_hierro,
reachable through `inquietud_principal`) — this field only covers
genuinely new adjustment types.

**Routine** (`experiencia.ajustes_rutina`,
`rutina_reglas.ajustes_rutina()`): 8 adjustments — volume up/down (one
set, same floor as every other stacked adjustment), rest time up/down
(~30s, floored at 30s), cardio on every session vs. none (overrides the
default "last session only" placement), avoid barbell (a soft
preference — `_filtrar_evitar_barra()` falls back to the unfiltered pool
rather than ever leaving a slot with zero candidates, the same
defense-in-depth principle as every other soft exclusion in this
project), and prefer machines (`_preferir_maquinas_primero()`, the same
stable-sort-within-an-already-shuffled-list pattern as the existing
complexity-bias functions).

Both are stacked adjustments on top of the existing level/stress-sleep/
compromiso logic, never a re-derivation from scratch, and both are
disclosed in `resumen_enfoque` (bilingual) the same "never a silent
adjustment" way `preferencias_blandas()`'s own notes already work.
`routine_agent.py`/`diet_agent.py`'s LLM prompts got matching
instructions for engine parity. A profile with no `ajustes_dieta`/
`ajustes_rutina` key at all produces byte-identical output to one with
an empty list — locked in by a dedicated test each. 18 new tests (9
diet, 9 routine, including a Spanish-language transparency-note check
each, since that exact class of gap — an English-only test path — was
caught for real once before in `validator_agent.py`).

**Portal visual pass**, two direct follow-ups the same day: meal cards
in the swipe flow gained a meal-type emoji (🍳/🍽️/🌙/🍎, keyed by
`tipo_interno` so it works regardless of portal language), a visible
"❤️ You like this one" tag on an already-liked meal (not just the
button's own label), a separated kcal line, and the same hover-lift CSS
treatment the trainer's own cards already have. The check-in section —
reported as not looking like something that needed filling in — now
opens expanded by default (equal footing with Meals, not buried behind
the other four collapsed sections), with punchier intro/success copy
that says what actually happens (the plan updates to match, checked
against the real check-in-driven regeneration flow already built) and
dividers between its three subsections for a clearer step-by-step feel.

Verified live against the real workspace (the "PEPE" test client):
emoji/like-tag/kcal render correctly on a real generated week, and the
check-in section opens expanded with the new copy and dividers visible.
565 tests passing (up from 547), lint clean, no example-output diffs
(no example client uses either new field).

## A dense follow-up round: i18n bug, mandatory-and-specific warm-ups,
## goal-adapted messages, an always-present diet tip, named dishes, and
## a portal routine redesign

Nine items requested together, all shipped the same day.

**Real i18n bug.** The "Clients" tab's verdict chart always read
"Approved"/"Enhanced review" in English, regardless of the trainer's
language toggle. Root cause: `notion_connector.VEREDICTO_LABELS` stores
a fixed English string as the actual Notion select value — a deliberate
"canonical value, translated only for display" design, same pattern as
exercise/food names — but `_render_dashboard_clientes()` was reading
that raw stored value straight into the chart instead of translating it
for display. Fixed with a reverse-map through the same dict at render
time; verified live, round-tripped EN/ES against the real workspace's 7
clients.

**Commitment-level caption.** New copy for Basic/Normal/Advanced/Tryhard,
provided verbatim by the project owner, replacing the previous wording
in both languages.

**Equipment-multiselect reset bug.** Switching `lugar_entreno` away from
"casa_sin_material" left the equipment multiselect silently empty
instead of resetting to the full pool — the existing force-clear-to-`[]`
logic for entering that location had no mirror for leaving it. Fixed by
tracking the previous location in session state and re-selecting every
option on the way back out.

**Warm-ups: mandatory (already true) but now specific.** The routine
engine already set a per-session `calentamiento` unconditionally; the
content itself was generic ("mobility"). Rewritten to name real
exercises grounded in the RAMP protocol (Raise, Activate, Mobilize,
Potentiate) standard in strength coaching: banded external/internal
rotation for rotator-cuff activation before any shoulder-heavy session
(upper body, push, pull), hip circles/leg swings/bodyweight glute
bridges before any leg-heavy session (lower body, full body/legs) — the
two joints most warm-up research flags for injury risk under load. Both
languages, and now rendered in the routine PDF (it was already generated
but never shown there).

**Progresion as bullets, not one paragraph.** Same "wall of text" fix
already applied to the plan email/portal (`gmail_client.
dividir_en_puntos()`) extended to the routine PDF and trainer panel.
First attempt used a literal "• " string prefix; the PDF-extraction test
itself caught that the bullet character extracts as a stray control byte
through pypdf under the plain Helvetica font reportlab uses here — fixed
by switching to a native `ListFlowable`/`ListItem` bulleted list, the
same convention `consejos_sinergias` already used in the diet PDF.

**Goal-adapted "starting plan" sentences.** Both routine and diet client
messages now close with one goal-specific sentence proposing the actual
starting approach, instead of purely generic encouragement — e.g. for
`perdida_grasa`: routine says lifting stays the priority with some
cardio added around it; diet says starting with a moderate (not
aggressive) deficit. New `PLAN_INICIO_RUTINA`/`PLAN_INICIO_DIETA` dicts,
keyed by `objetivo.principal`, appended after the existing
`MENSAJE_CLIENTE_*_VARIANTES` text rather than replacing it.

**A real content gap: consejos_sinergias could be genuinely empty.** A
"basico"/"normal" diet client with no active soft preference ended up
with an EMPTY `consejos_sinergias` list, because that field's own
nutrient-timing tips are deliberately gated to "avanzado"/"tryhard".
`gmail_client.obtener_texto_cliente()` then fell back to the first
sentence of the generic `mensaje_para_el_cliente` — which, for one of
the four English/Spanish variants, is literally "aquí tienes tu dieta en
borrador" / "this is your draft diet" — a useless line to show as "the
tip" in the plan email or portal. New `_consejo_general()` returns one
genuinely useful, goal/diet-type-aware tip (protein+veg prioritization
for fat loss, liquid calories for a hard-to-hit surplus, a default
half-the-plate-vegetables tip otherwise), appended to
`consejos_sinergias` only when the level-gated content would otherwise
leave it empty — never displacing a more specific tip a higher
commitment level or an active soft preference already earned.

**Wetaca-style named dishes + optional cooking tips.** Every meal
description in `plan_semanal` now opens with a short named dish ("Lentejas
con pollo: ..." / "Chicken with lentils: ...") before the gram
breakdown, built mechanically from the meal's own carb+protein display
names rather than a hand-authored per-combination name database (with
10+ proteins × 10+ carbs × 2 languages, that wasn't a proportionate
build for this request). A new curated `CONSEJOS_COCINA` dict adds one
real, optional prep tip for ~15 common proteins/carbs (e.g. "add cumin
to lentils/chickpeas — helps digestion and reduces bloating," "cook and
cool rice before eating — the resistant starch is better for your gut
bacteria") when a recognized ingredient is in the meal — deliberately
not exhaustive (not every food in `food_bank.py` needed one), real
cooking/nutrition advice rather than invented filler, protein checked
before carb so a meal never shows two tips at once.

**Portal routine section visual pass.** Mirrors the meal section's own
redesign: bordered, hover-lift cards per session day (same wildcard CSS
pattern as `_render_swipe_comidas()`'s meal cards), now showing the full
session detail — warmup, per-exercise rest time and notes, effort cue,
optional cardio — that the portal used to drop entirely in favor of just
exercise names. `progresion` itself isn't duplicated here since it
already reaches the portal via the "Notes" section's `mensaje_rutina`
(the same reduced tip text `gmail_client.obtener_texto_cliente()`
already picks for the email).

**Check-in-regeneration email gets a "Week N:" header.** The plan email
`crear_borrador()` sends after a client's check-in triggers a
regeneration (see the earlier "check-in-driven regeneration" entry)
gained an optional `semana` parameter — the check-in count so far,
including the one that just triggered it — rendered as a "Semana N:" /
"Week N:" header before the greeting. Threaded through
`_preparar_envio_plan()`/`_construir_cuerpo_email()`; only shown
together with `url_portal`, since a client's very first plan draft has
no "week" yet and shouldn't say so.

`routine_agent.py`/`diet_agent.py`'s system prompts were updated for
engine parity on every content change above (mandatory specific
warm-ups, goal-adapted closing sentences, named dishes + optional
cooking tips, consejos_sinergias never empty).

Verified live against the real workspace: commitment captions and
adjustment captions render correctly in the "New Client" form; the
verdict-chart i18n fix round-tripped EN/ES against the real 7-client
Clients dashboard; the portal routine redesign renders correctly against
the real "PEPE" test client's stored plan (his plan predates today's
wetaca-style meal format, so that specific piece is covered by unit
tests rather than visible on his stale saved data, not re-verified live
this round). 574 tests passing (up from 565), lint clean,
`examples/output_rutina_*.json`/`output_dieta_*.json` regenerated for
all three example clients.

## Direct editing for revision_reforzada plans: a real gap, scoped in two rounds

A follow-up from the same session as the previous entry, prompted by a
question about what was still missing. The trainer's first answer ("haz
que los ajustes del entrenador sean mas generales") turned out to
reference text that already existed verbatim from the prior turn — but
a follow-up clarified the real ask was different: "que pueda editar yo
con un boton las cosas que puedan necesiten de mi consulta" — being able
to directly edit the generated plan, via a button, specifically for
whatever needs the trainer's own judgment. Scoped through two rounds of
`AskUserQuestion` before writing any code: WHAT to make editable (only
content flagged for revision, plus free text — not the whole plan, not
just text) and HOW (pick from a list of safe alternatives, not free
text, for structured content).

**Design.** Editing only ever renders for a `revision_reforzada` plan
(`es_revision_reforzada` threaded into `_mostrar_rutina()`/
`_mostrar_dieta()` as `editable`) — an `aprobado_automatico` plan is
never shown this UI at all, matching "solo lo marcado para revisión."
Two kinds of edits: a dropdown-based swap for every exercise and every
meal ingredient (structured content, safety-relevant), and free text for
`mensaje_para_el_cliente`/`resumen_enfoque` (prose, not safety-relevant).

**The real architectural constraint.** `_ejecutar_y_mostrar()` re-runs
the *entire* pipeline (`ejecutar_pipeline(perfil, ...)`) from scratch on
every single Streamlit rerun — not just the click that first generated
the plan — because the section-dispatch logic re-checks
`st.session_state["ultimo_origen"]` every render, not just on the button
click itself. Since generation is deterministic (seeded by
`id_cliente`), this always reproduces byte-identical output. That means
an edit can never live in the freshly-generated `estado.borrador_rutina`/
`borrador_dieta` dict itself — it gets discarded and regenerated a
moment after any widget interaction. The fix used what Streamlit already
provides for free: give each edit widget a STABLE key (tied to
`perfil["id_cliente"]` and the day/exercise/meal-field index, not
`id(rutina)`, which is a fresh object every rerun) and let Streamlit's
own session-state persistence carry the trainer's choice across reruns.
`_mostrar_rutina()`/`_mostrar_dieta()` read each widget's current value
and RETURN a patched copy of the draft, which `_ejecutar_y_mostrar()`
reassigns onto `estado.borrador_rutina`/`borrador_dieta` before
`_panel_aprobacion()` runs — so the edited version is what gets PDF'd,
drafted, and saved, within the same rerun. No new session-state
"overrides" layer needed; this is the exact same `_clave_selectbox()`/
`_clave_multiselect()` pattern already used elsewhere in this file for
surviving a language-toggle remount, applied to a new problem.

**Safety.** Every dropdown is populated from the *same* filtering
functions generation itself already calls —
`rutina_reglas._candidatos(grupo, tipo, material, lesion_tags)` for
exercises, `food_bank.fuentes_proteina_para()`/`fuentes_carbohidrato_para()`/
`fuentes_grasa_para()` for foods — so a trainer's swap can only choose
among alternatives the engine had already vetted as safe for this exact
client. It's structurally impossible to pick something the validator
would have flagged, because the option never appears in the list.

**A disclosed simplification, not a silent one.** A food swap doesn't
regenerate the meal's whole sentence from scratch: `plan_semanal`'s own
schema (`_construir_comida()`'s return value) never surfaced the
per-ingredient grams or the verdura/synergy-eligibility flags baked into
`descripcion` -- only the final rendered sentence and the bare food
names. Reconstructing the sentence properly would mean extending that
schema (a real, larger change) just for this. Instead,
`_sustituir_ingrediente_en_descripcion()` does a case-preserving,
word-boundary-anchored text substitution of the old ingredient's
displayed name for the new one, leaving the grams/pairing/synergy text
exactly as originally generated. The portions now describe the new
food's role approximately, not exactly -- consistent with this project's
own stated "estimate, adjust from real progress" philosophy for
`plan_semanal` overall, and disclosed directly in the UI caption next to
the dropdowns rather than left implicit. An exercise swap clears that
slot's `notas` (usually an injury-adaptation reason for the exercise
being replaced, which doesn't necessarily still apply to the new pick).

**Same-day follow-up.** With progresion already bulleted, the warm-up
text (made longer and more specific earlier in the session -- rotator
cuff, hip mobility) read as the next "wall of text." `CALENTAMIENTO_POR_DIA`
was rewritten as two real sentences per entry (mobility drills, then
warm-up sets) instead of one long comma-and-"+"-joined sentence,
specifically so `gmail_client.dividir_en_puntos()` -- which splits on
sentence-ending punctuation -- could bullet it the same way it already
bullets `progresion`, in the PDF, the trainer panel, and the portal
(joined with "·" there instead of a multi-line list, since it renders
inside a single-line `st.caption()`).

**Verification.** Live against the real "PEPE" test client (loaded via
"Revisar cliente" by email, not the broken example-client selector --
see below), whose real profile is `revision_reforzada` for a declared
shoulder injury: all 18 exercise dropdowns (3 days × 6 exercises) and
all 63 food dropdowns (7 days × 9 ingredient slots) rendered with the
correct current value pre-selected and real, safe alternatives; the
warm-up bullets rendered correctly; no server error. Nothing was
approved, saved, or sent during verification -- generating a plan for
"Revisar cliente" doesn't write to Notion (saves happen on approval, per
the existing design), so this was safe to do against the real record.

**A genuine tooling limitation, disclosed rather than routed around.**
Verifying this live meant switching to a different example client or a
different real client, and the in-app browser's automation repeatedly
failed to reliably drive this Streamlit version's `st.selectbox` (a
react-aria ComboBox under the hood) -- clicks opened it, but synthetic
key/selection events didn't commit a real option, leaving the widget in
an uncommitted text state. Worked around by using "Revisar cliente"'s
plain email `st.text_input` instead of the broken example-client
dropdown, which uses ordinary DOM text input the same automation drives
reliably elsewhere in this project. The dropdown-driving limitation
itself is a browser-automation-tooling gap, not a bug in the app --
noted here rather than left unexplained.

---

## Fitness content disclaimer

Client names, injuries, and other fitness/health details throughout this project
(the trainer's persona, `examples/cliente_ejemplo_*.json`, the knowledge base) are
entirely **fictional**, created for demo purposes. See `docs/metodo_entrenador.md`
for the fictional trainer profile this project was built around.
