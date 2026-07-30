# TrainFitter — Working Notes for Claude

Portfolio project: a multi-agent pipeline (personal-trainer domain) demonstrating
agent orchestration, dual free/LLM engines, and a safety-gated human-in-the-loop
design. Public repo: **github.com/serpeigd/TrainFitter**.

## Standing conventions (do not re-ask)

- **Language split**: all repo content (code, comments, docs, commit messages,
  UI copy) is written in **English**. Chat with the user stays in **Spanish**.
- **Scoping exception**: Python identifiers, dict/JSON keys, and schema/state
  literal values (e.g. `perfil_cliente`, `revision_reforzada`,
  `generar_borrador_rutina`) stay in **Spanish** — only prose/comments/docs were
  translated. Don't "fix" these; it's a deliberate, documented decision.
- **Git identity**: repo-local `user.email` is set to the GitHub noreply address
  (`125498425+serpeigd@users.noreply.github.com`). Already configured — new
  commits use it automatically.
- Push future work to the `serpeigd/TrainFitter` GitHub repo (public, portfolio).
- Full chronological decision log with rationale lives in
  [`docs/decisiones.md`](docs/decisiones.md) — read it only if you need the
  *why* behind a past call; don't load it by default (it's long).
- [`docs/highlights.md`](docs/highlights.md) is the condensed, interview-ready
  version of the same log (7 decisions, 1 page) — update it when a change adds
  a genuinely new "defensible decision," not for routine work.

## Architecture (see [`docs/arquitectura.md`](docs/arquitectura.md) for full detail)

```
Client intake JSON → routine_agent + diet_agent (motor="reglas"|"llm", same output schema)
                   → validator_agent (ALWAYS rule-based, re-derives risk from raw profile)
                   → verdict: aprobado_automatico | revision_reforzada
                   → human review (ALWAYS, no auto-send)
```

- **Two interchangeable engines** per generation agent: `"reglas"` (default,
  free, deterministic, no API key) vs `"llm"` (optional, `ANTHROPIC_API_KEY`,
  Claude tool-use forced output). Same output schema either way.
- **Validator is deliberately never LLM** — deterministic safety gate,
  defense-in-depth (cross-checks against `exercise_bank.py`/`food_bank.py`,
  doesn't trust upstream agents' self-reported flags).
- **Orchestrator** (`agents/orchestrator.py`) is an explicit state machine:
  `ficha_recibida → rutina_generada → dieta_generada → validado →
  (pendiente_aprobacion_humana | pendiente_revision_reforzada)`, plus `error`.
  Takes an `on_transition` callback (default: console log) — this is what lets
  `ui/app.py` render live progress without the orchestrator knowing Streamlit
  exists.
- **`ui/app.py`** (Streamlit): trainer-facing panel, ES/EN toggle via
  `TRANSLATIONS`/`OPTION_LABELS` dicts + `t()`/`opt()` helpers. Widgets are
  standalone (not `st.form`) so conditional fields (e.g. injury detail) render
  immediately — `st.form` doesn't rerun until submit.
- Bilingual keyword matching in `perfil_utils.tags_lesiones()` and
  `food_bank.etiquetas_excluidas()` — safety-critical (injury/allergy
  detection), must match both Spanish and English free text.

## Status

Phases 0–4 + 5-lite (Streamlit panel) done, plus a pytest suite (`tests/`, run
with `pytest` from repo root — wired into CI) and a live demo at
[trainfitter.streamlit.app](https://trainfitter.streamlit.app/) (auto-redeploys
on push to master). `agents/analytics_parser.py` extracts bloodwork markers
from the intake's PDF attachment (best-effort, bilingual, forces
`revision_reforzada` on out-of-range values via `validator_agent.py` — same
defense-in-depth pattern as injuries/allergies). `mcp/gmail_client.py` creates a real Gmail **draft** (never sends —
enforced by the `gmail.compose` OAuth scope, not just by convention),
**live-tested end-to-end** with a real OAuth-authorized account
(`trainfitter.official@gmail.com`); recipient is typed in the approval
panel, not part of the intake schema. Also exposes `verificar_envio()`
(needs the added `gmail.metadata` scope — labels/headers only, never the
message body) to check on demand whether a draft's thread now contains a
sent message. `mcp/notion_connector.py` saves a summarized record
(name/date/goal/level/verdict/summary) to a "Clients" Notion database, and
backfills the client's email onto that record once a Gmail draft is
created for them (`actualizar_email_cliente()`). A second "Check-ins"
Notion database (joined to Clients by email, not a relation property)
logs one row per interaction: `ui/app.py`'s "Check if it was sent" button
calls `verificar_envio()`, and on a confirmed real send, ticks "Email
Sent" on the Clients record (`marcar_email_enviado()`) and adds a
"Plan sent" row to Check-ins (`crear_registro_checkin()`) — trainer-
triggered, not a background job (stateless Streamlit app, no push
infra). Notion-save and Gmail-draft-creation are gated behind the
"Approve" button (Gmail stays disabled until that exact plan is approved;
Notion saves on approval, not generation) — fires only for genuine
new-client intakes, never the example-client demo path. On any deployment
with `APP_APPROVAL_PASSWORD` set (env var / Streamlit secret, never
hardcoded), approving requires that password via a popup (`st.dialog`), so
the public demo can have both connectors active without a random visitor
writing to the trainer's real accounts. Generated routine/diet content
(exercise/food names excepted — see below) now follows the UI's EN/ES
toggle: `rutina_reglas.py`/`dieta_reglas.py`/`validator_agent.py` all take
an `idioma` parameter, threaded through `routine_agent.py`/`diet_agent.py`/
`orchestrator.py`/`gmail_client.py`, defaulting to `"en"` (byte-identical
to pre-existing behavior). Exercise/food **names** are a deliberate
exception — they stay canonical English in `exercise_bank.py`/
`food_bank.py`'s `"nombre"` field regardless of `idioma`, since
`validator_agent.py`'s safety cross-check (injuries vs. exercises,
allergies vs. foods) matches against that exact value; a `nombre_es` field
plus a display-only `nombre_mostrado()` helper (used only by `ui/app.py`,
never by generation/validation) covers on-screen translation instead.
Pending: automatic inbox trigger (`main.py`), and making the free rule
engine's generation itself less deterministic/personalized (a bigger,
not-yet-scoped design question — see `docs/decisiones.md`). CI
(`.github/workflows/ci.yml`) runs the free rule-engine pipeline + test
suite + lint end-to-end on every push — no secrets needed.

## Free-only guardrail

The project's core promise is **fully free, no paid API key required**.
The *only* piece that would ever need one is the optional `motor="llm"`
path (pay-per-token Anthropic API) — it's designed but deliberately never
exercised against the real API. Every other planned addition (tests, deploy,
bloodwork parser, Gmail/Notion) uses local libraries or free-tier OAuth.
When proposing next steps, keep this the default; only touch `motor="llm"`
if the user explicitly opts in to spending money.

## Key files

| Area | File |
|---|---|
| Routine rule engine | `agents/rutina_reglas.py` |
| Diet rule engine | `agents/dieta_reglas.py` |
| Validator | `agents/validator_agent.py` |
| Orchestrator | `agents/orchestrator.py` |
| Exercise/food banks | `agents/exercise_bank.py`, `agents/food_bank.py` |
| Bloodwork parser | `agents/analytics_parser.py` |
| Gmail connector (draft-only) | `mcp/gmail_client.py` |
| Notion connector (auto-save) | `mcp/notion_connector.py` |
| Streamlit UI | `ui/app.py` |
| Tests | `tests/` (`conftest.py` fixture + `test_*.py` per module) |
| Example clients/outputs | `examples/` |
| Knowledge base (RAG-level) | `docs/base_conocimiento/*.md` |
| Trainer's method (judgment-level) | `docs/metodo_entrenador.md` |
