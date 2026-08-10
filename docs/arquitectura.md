# TrainFitter Architecture

> **Status: full pipeline (Phases 0-4) + trainer's panel (Phase 5-lite) + automatic
> inbox trigger (Phase 6), all done.** Gmail and Notion are both connected,
> including a second Notion "Check-ins" database that logs a client's interaction
> history once a real Gmail send is confirmed. `main.py`, scheduled via
> `.github/workflows/inbox_trigger.yml`, scans the inbox for adherence check-in
> replies and new-client intake PDFs — see the "Automatic inbox trigger" section
> below. Beyond the original phase plan, the project has since added a
> client-facing magic-link portal, a "Revise client" flow that stores and reloads
> a client's full profile from Notion, real-weight tracking through the
> check-in loop, and a "Clients" roster tab with per-client trend charts (weight,
> adherence rating) — see [`README.md`](../README.md) and
> [`docs/decisiones.md`](decisiones.md) for the full, current feature list; this
> document focuses on the core pipeline's design, not a changelog of every
> feature added on top of it.
>
> Note on naming: internal Python identifiers, dict/JSON keys, and literal state
> values (e.g. `perfil_cliente`, `revision_reforzada`, `generar_borrador_rutina()`)
> are still in Spanish — only prose, comments, and docs were translated to English
> in this pass. See `docs/decisiones.md` for that scoping decision.

---

## Overview

TrainFitter is an agent pipeline that turns a client's intake form into draft
routines and diets, with **mandatory human review** before anything is sent. Each
agent has a single, well-scoped responsibility.

## Key decision: two interchangeable engines per agent

`routine_agent` and `diet_agent` don't call a single fixed backend: they expose a
`motor` parameter with two implementations that return **the same output schema**,
so the rest of the pipeline is agnostic to which one ran.

| Engine | Cost | How it works | When it's used |
|---|---|---|---|
| `"reglas"` (default) | **Free**, no API key, no network | Deterministic Python code that applies the method's values directly (splits, rep ranges, calorie/macro math, exercise/food banks filtered by equipment/allergies/injuries) | Development, demos, the whole pipeline today |
| `"llm"` (optional) | Requires `ANTHROPIC_API_KEY` | Calls the Anthropic model with output forced via *tool use* (`entregar_borrador_rutina` / `entregar_borrador_dieta`) | When richer, more nuanced writing is wanted; already designed to switch on without touching the rest of the system |

The **validator agent**, by contrast, is **always rule-based** by design: a safety
gate should be deterministic and auditable, not a model's "opinion" — see
`agents/validator_agent.py` for the full reasoning.

## Data flow

```
   Client intake (admission/) ──► Client profile JSON (schema in examples/cliente_ejemplo_*.json)
                                          │
                     ┌────────────────────┼────────────────────┐
                     ▼                    ▼                    ▼
              routine_agent          diet_agent          (both read)
              (motor rules/llm)      (motor rules/llm)   docs/metodo_entrenador.md
                     │                    │              docs/base_conocimiento/*
                     ▼                    ▼
              routine draft           diet draft
                     │                    │
                     └─────────┬──────────┘
                                ▼
                     validator_agent (always rule-based)
                     - re-reads the raw client profile (doesn't
                       blindly trust routine/diet's own warnings)
                     - cross-checks exercises vs. injuries (exercise_bank)
                     - cross-checks food vs. allergies (food_bank)
                                ▼
              verdict: aprobado_automatico | revision_reforzada
                                ▼
                     Human review (ALWAYS, no exceptions)
                                ▼
              Notion "Clients" record saved (mcp/notion_connector.py)
                     - stores the summary AND the full perfil_cliente
                       (chunked rich_text), so a client can later be
                       looked up and revised, not just displayed
                                ▼
              Gmail draft created (mcp/gmail_client.py) — trainer reviews and sends it themselves
                                ▼
              Trainer confirms the send in the UI ("Check if it was sent")
                                ▼
              Notion "Email Sent" ticked + a row added to "Check-ins"
```

Two paths run alongside the core flow above, both reusing the same underlying
pieces rather than duplicating them:

- **Client portal (magic link):** instead of the trainer confirming a send, the
  trainer can send the client a signed, self-expiring link
  (`agents/portal_tokens.py`) via `gmail_client.enviar_enlace_portal()` — the one
  function in the codebase allowed to call `messages().send()` for a client-facing
  message. The client opens `ui/app.py` with a `?portal_token=...` query param,
  sees a summary read back from the same Notion "Clients" record, and can log a
  check-in themselves (feeding the same `crear_registro_checkin()` the PDF-based
  loop uses) — including their own check-in history and, optionally, their
  current weight.
- **Revise client:** the trainer looks up a past client by email
  (`notion_connector.buscar_cliente_por_email()`), and the same intake form used
  for a brand-new client reopens pre-filled with their stored `perfil_cliente`.
  Re-approving calls `actualizar_registro_cliente()` (`pages.update()`, not
  `pages.create()`) so the same Notion page is corrected in place. Bloodwork
  markers already extracted from a prior upload carry forward automatically
  (no need to re-attach the original PDF); an actually new PDF still overrides
  them.

## Orchestrator state diagram (real, `agents/orchestrator.py`)

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
       ├── verdict == "revision_reforzada" ──► pendiente_revision_reforzada
       │
       └── verdict == "aprobado_automatico" ──► pendiente_aprobacion_humana

 (at any point, if an agent raises RoutineAgentError/DietAgentError) ──► error
```

Both success branches end in a "pendiente_*" (pending) state: **even
`aprobado_automatico` only means "no reasons for enhanced review," never "send it
without anyone looking."** The trainer always approves before anything reaches the
client — see `PipelineState` in `agents/orchestrator.py`.

`ejecutar_pipeline()` accepts an optional `on_transition` callback (by default, it
logs to the console). That's what lets the UI (see below) paint the same state trail
on screen instead of in a terminal the user never sees, without the orchestrator
knowing anything about Streamlit.

## Trainer's panel (`ui/app.py`) — Streamlit interface

The CLI pipeline is the development layer; `ui/app.py` is the layer a
non-technical trainer could actually use. It turns `ejecutar_pipeline()` into a
click-through experience, organized into four sections navigated via
`st.segmented_control()` (`New Client` first, per the trainer's own workflow) —
deliberately **not** `st.tabs()`, whose labels double as their React identity, so
translating them on a language switch remounted the whole component and reset
the view back to the first tab (reproduced and confirmed while building this;
`st.segmented_control`'s selected value is decoupled from its displayed text via
`format_func`, so it survives a language switch untouched):

- **"New Client" section:** either upload a filled-in intake PDF
  (`_cargar_ficha_desde_pdf()`) or fill out a form that mirrors
  `admission/ficha_cliente_template.md` (basic info, goal, experience,
  availability, health, nutrition, lifestyle) and builds the same JSON the
  agents consume — a trainer could onboard a real client without touching code
  or JSON by hand.
- **"Revise client" section:** look up a past client by email
  (`notion_connector.buscar_cliente_por_email()`) and reopen the same intake
  form pre-filled with their stored `perfil_cliente`, to edit and regenerate;
  re-approving updates the existing Notion record in place instead of
  duplicating it (see "Revise client" below).
- **"Clients" section (`_panel_todos_los_clientes()`):** a roster of every real
  client (`notion_connector.listar_clientes()`), joined in Python with each
  client's most recent Check-ins row (`ultimo_checkin_por_cliente()` — Notion
  has no native "latest row per group" query) and flagged with ⚠️
  (`_etiqueta_atencion()`) when that latest adherence rating is Low. The two
  Notion queries are independently best-effort: if the Check-ins lookup fails,
  the roster itself still renders, just without the adherence column.
- **"Example client" section:** pick one of the JSON files in `examples/`, preview
  the full intake, generate the plan.
- **Live execution:** `st.status(...)` plus the `on_transition` callback show each
  orchestrator transition as it happens.
- **Result:** verdict (with reasons if enhanced review applies), routine broken down
  by session with an exercise table, diet with macros and suggested sources, and JSON
  download buttons.
- **Approval + Gmail draft:** an "Approve and mark as ready to send" checklist
  button, plus a real "Create Gmail draft" action (`mcp/gmail_client.py`) that
  takes the client's email (typed by the trainer — the intake form doesn't
  collect it) and creates an actual draft in a dedicated Gmail account. The
  OAuth scope requested (`gmail.compose`) can only create drafts — it's
  physically incapable of sending or reading mail, so the UI never sends
  anything on its own even in principle, not just by convention. On real
  new-client plans, approving also saves a record to a Notion "Clients"
  database (`mcp/notion_connector.py`).
- **Send confirmation + Check-ins:** a "Check if it was sent" button calls
  `gmail_client.verificar_envio()` (needs the added `gmail.metadata` scope —
  labels/headers only) to check whether the trainer actually sent the draft,
  not just created it. On a confirmed send, it ticks "Email Sent" on the
  Clients record and logs a row in a second Notion "Check-ins" database
  (joined by email, not a relation property) — the interaction history for
  that client. This is trainer-triggered, not a background job: a stateless
  Streamlit app has no push infrastructure to notice a send passively.
  `_render_historial_checkins()` (shared with the client portal, see below)
  also renders a trend chart (`_render_grafico_tendencia()`, weight and
  adherence rating over time via `st.line_chart()`/Altair) from the same
  check-in data, with no extra query.
- **Password-gated approval:** on any deployment with `APP_APPROVAL_PASSWORD`
  set, approving a plan requires that password via a popup — so the public
  demo can have Notion and Gmail both active without a random visitor
  writing to the trainer's real accounts just by clicking through.

**Design note found during testing:** the new-intake widgets are deliberately NOT
inside an `st.form`. That was tried first, but Streamlit doesn't rerun the script
inside a form until "submit" is pressed — so a checkbox like "has an injury?" never
got the chance to reveal the "injury area" field in time. With standalone widgets
(each with its own `key`), every interaction reruns the script and the UI can react
immediately. The cost is somewhat more frequent re-rendering, which is irrelevant for
a pipeline as fast as the rule engine.

## Components

| Component | File | Phase | Status |
|---|---|---|---|
| Client intake form | `admission/ficha_cliente_template.md` | 1 | **Done** |
| Knowledge base | `docs/base_conocimiento/` | 0 | **Done** |
| Knowledge-loading helper | `agents/knowledge.py` | 2 | **Done** |
| Exercise bank | `agents/exercise_bank.py` | 2 | **Done** |
| Rule engine — routine | `agents/rutina_reglas.py` | 2 | **Done** |
| Routine agent (dual engine) | `agents/routine_agent.py` | 2 | **Done** |
| Food bank | `agents/food_bank.py` | 3 | **Done** |
| Rule engine — diet | `agents/dieta_reglas.py` | 3 | **Done** |
| Diet agent (dual engine) | `agents/diet_agent.py` | 3 | **Done** |
| Validator agent | `agents/validator_agent.py` | 3 | **Done** |
| Orchestrator (explicit state) | `agents/orchestrator.py` | 4 | **Done** |
| Trainer's panel (UI) | `ui/app.py` | 5-lite | **Done** |
| Bloodwork parser | `agents/analytics_parser.py` | 5+ | **Done** |
| Notion connector (Clients + Check-ins) | `mcp/notion_connector.py` | 5 | **Done** |
| Gmail connector (draft + send-detection) | `mcp/gmail_client.py` | 5 | **Done** |
| Automatic trigger (adherence + new intakes) | `main.py` + `.github/workflows/inbox_trigger.yml` | 6 | **Done** |
| Intake PDF (generate + read) | `agents/pdf_intake.py` | 6 | **Done** |
| Client portal (magic link) | `agents/portal_tokens.py`, `ui/app.py`'s `_vista_portal_cliente()` | 6+ | **Done** |
| Revise client (Notion-backed full profile) | `notion_connector.py`'s `buscar_cliente_por_email()`/`actualizar_registro_cliente()`, `ui/app.py`'s `_cargar_ficha_para_revisar()` | 6+ | **Done** |
| Client roster + trend charts | `notion_connector.py`'s `listar_clientes()`/`ultimo_checkin_por_cliente()`, `ui/app.py`'s `_panel_todos_los_clientes()`/`_render_grafico_tendencia()` | 6+ | **Done** |

## Clinical personalization layer (active modulation)

Intake captures health data (allergies, conditions, pregnancy/breastfeeding,
medication, weight) and allows a **PDF bloodwork report** to be attached. The
rule engine actively modulates the diet based on what it knows about the profile
(diet type, allergies/intolerances, goal → calories/macros) and applies absorption
synergies when the diet type calls for it (e.g. iron + vitamin C in
vegetarian/vegan diets). `agents/analytics_parser.py` extracts common markers
from the attached bloodwork PDF (glucose/HbA1c, total/LDL/HDL cholesterol,
triglycerides, ferritin, vitamin D, TSH) using standard adult reference ranges —
best-effort, bilingual (ES/EN) keyword matching, same pattern already used for
injury/allergy detection. It never adjusts the diet's macros directly; it only
surfaces what it found so the validator can decide.

Modulating actively doesn't loosen the hard rule: the system **never diagnoses or
prescribes**; any out-of-range marker, condition, pregnancy, medication, injury, or
allergy **forces `revisión_reforzada`** — see `docs/metodo_entrenador.md` §7 and
`agents/validator_agent.py`.

## Cross-cutting principle: human in the loop

No plan reaches the client without human approval. The system is designed to
**assist** the trainer, not replace them. Generation always produces a **draft**, and
any risk signal (injury, condition, allergy, clinical marker) forces an **enhanced
review**.
