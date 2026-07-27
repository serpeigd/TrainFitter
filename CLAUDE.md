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

Phases 0–4 + 5-lite (Streamlit panel) done, plus a 42-test pytest suite
(`tests/`, run with `pytest` from repo root — wired into CI). Pending:
bloodwork parser (`agents/analytics_parser.py`), Notion/Gmail connectors
(`mcp/`), automatic inbox trigger (`main.py`), Streamlit Cloud deploy.
CI (`.github/workflows/ci.yml`) runs the free rule-engine pipeline +
test suite end-to-end on every push — no secrets needed.

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
| Streamlit UI | `ui/app.py` |
| Tests | `tests/` (`conftest.py` fixture + `test_*.py` per module) |
| Example clients/outputs | `examples/` |
| Knowledge base (RAG-level) | `docs/base_conocimiento/*.md` |
| Trainer's method (judgment-level) | `docs/metodo_entrenador.md` |
