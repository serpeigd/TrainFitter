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

## Free-only guardrail

Reconfirmed while planning next steps: the **only** piece of this project that would
ever require a paid API key is the optional `motor="llm"` path (pay-per-token
Anthropic API calls). Every other planned addition — the test suite above, deploying
the Streamlit demo, a bloodwork PDF parser, Gmail/Notion connectors — uses either
local libraries or free-tier OAuth APIs. `motor="llm"` stays designed-but-untested
against the real API and is treated as strictly optional: the project's "fully free"
promise does not depend on it ever being exercised.

---

## Fitness content disclaimer

Client names, injuries, and other fitness/health details throughout this project
(the trainer's persona, `examples/cliente_ejemplo_*.json`, the knowledge base) are
entirely **fictional**, created for demo purposes. See `docs/metodo_entrenador.md`
for the fictional trainer profile this project was built around.
