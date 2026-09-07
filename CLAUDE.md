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
- **Commit + push is automatic (2026-08-19, explicit standing authorization in
  chat) — no confirmation step before it, for any change in this repo.**
  Previously every commit was confirmed via a question first; that step is
  gone now. The bar for what gets committed is unchanged: tests pass, lint is
  clean, docs (`CLAUDE.md`/`docs/decisiones.md`) are updated in the same
  change, `git fetch` + rebase against `origin/master` first if it's moved.
  Still surface what changed and why after pushing, same as always — only the
  "should I commit this?" question is gone, not the summary.
- **Keep it short (2026-08-13, explicit request in chat).** Too much text, too much
  explaining. Lead with the answer or the change; give reasoning only where it would
  change a decision. Don't recap work already visible in the diff, don't restate the
  question before answering it, and don't close with a summing-up line. Applies to
  chat, commit messages and PR bodies. Reference docs (README, this file) can be
  longer, but only where the length earns it.
- Full chronological decision log with rationale lives in
  [`docs/decisiones.md`](docs/decisiones.md) — read it only if you need the
  *why* behind a past call; don't load it by default (it's long).
- [`docs/highlights.md`](docs/highlights.md) is the condensed, interview-ready
  version of the same log (22 decisions, ~2 pages) — update it when a change adds
  a genuinely new "defensible decision," not for routine work.
- **Scheduled documentation-sync runs (added 2026-08-07, explicit decision in
  chat): standing authorization to merge doc-only PRs from that recurring task
  yourself, without waiting for approval, once CI (`ci.yml`) is green — same
  bar as any other merge, just no confirmation step for this specific,
  narrow case (README/`docs/` changes only, never product code).** That
  scheduled run lands on a fresh randomly-named branch every time, so an
  unmerged PR from a previous run is never reused automatically. Before
  opening a new one, check for another open PR titled starting "docs: sync" —
  if found, fold any still-valid unique content from it into the new one,
  merge the more complete/accurate PR once CI is green, and close the other
  with a comment linking to the merged one. Don't leave two open at once.

## Architecture (see [`docs/arquitectura.md`](docs/arquitectura.md) for full detail)

```
Client intake JSON → routine_agent + diet_agent (motor="reglas"|"llm", same output schema)
                   → validator_agent (ALWAYS rule-based, re-derives risk from raw profile)
                   → verdict: aprobado_automatico | revision_reforzada
                   → aprobado_automatico: sent automatically, zero clicks (mcp/gmail_client.py's
                     enviar_plan(), as of 2026-08-19 — see below)
                   → revision_reforzada: human review, ALWAYS, before anything sends — but once
                     approved, "send" now means enviar_plan() directly too (a real send, no draft
                     in between); a Gmail draft is a secondary, explicit fallback button, not the
                     default path (see below)
```

- **Two interchangeable engines** per generation agent: `"reglas"` (default,
  free, no API key, deterministic *per client* — see `agents/variacion.py`)
  vs `"llm"` (optional, `ANTHROPIC_API_KEY`, Claude tool-use forced output).
  Same output schema either way.
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

Phases 0–4 + 5-lite (Streamlit panel) done. Live demo at
[trainfitter.streamlit.app](https://trainfitter.streamlit.app/) (auto-redeploys
on push to master). 632 tests passing (`pytest` from repo root, wired into
CI), ~97% coverage on `agents/`+`mcp/` (`ui/app.py`/`main.py` deliberately
excluded from coverage — verified live instead, same convention throughout).

**What's built:**
- Free rule engines (routine + diet, `agents/rutina_reglas.py`/`dieta_reglas.py`)
  with an optional `motor="llm"` alternative, same output schema either way;
  `agents/validator_agent.py` is a deliberately-never-LLM safety gate.
- `agents/food_bank.py` (61 curated foods) + `agents/planificador_comidas.py`
  build a real 7-day meal plan (not just suggested-source lists) — synergy
  pairing, a shopping list, no-cook/quick-cook badges, and a client-set
  cuisine preference scoped to 1-2 days/week.
- `ui/app.py` (Streamlit): trainer panel (New Client / Revise Client /
  Clients dashboard, EN/ES toggle) plus a client-facing **portal** (magic
  link via a short Notion-stored reference code) — tab-based
  (Home/Meals/Routine/Check-in/Progress), with meal/exercise liking,
  adherence check-ins, a free monthly digest, and self-service link
  recovery.
- `mcp/gmail_client.py`: drafts (`gmail.compose`) plus real, deliberate,
  narrow sends (`gmail.send`) for the portal link, `aprobado_automatico`
  auto-send, and the `revision_reforzada` "send directly" button —
  `revision_reforzada` is otherwise still always human-reviewed first,
  no exceptions.
- `mcp/notion_connector.py`: "Clients" + "Check-ins" databases, full-profile
  storage enabling "Revise client", per-client liked/disliked meals &
  exercises, cuisine preference.
- `main.py` (GitHub Actions cron, `.github/workflows/inbox_trigger.yml`):
  scans the inbox for adherence-checklist replies and new-client intake
  PDFs, fully automated, never sends or drafts anything itself.
- `agents/pdf_generador.py`/`pdf_intake.py`: fillable intake + checklist
  PDFs, styled diet/routine PDFs with the weekly meal table and shopping
  list.
- `agents/analytics_parser.py`: best-effort bloodwork-marker extraction,
  forces `revision_reforzada` on out-of-range values.
- `agents/suplementos_interacciones.py`: curated supplement–medication
  interaction table backing the validator's generic check.

**In progress**: publishing the Gmail OAuth consent screen to Google's
Production status to fix the recurring 7-day token-expiry (Testing-mode
apps auto-expire every refresh token) — needed a real, owned, verifiable
domain, so a `gh-pages` branch now hosts a privacy-policy page at
[serpeigd.github.io/TrainFitter](https://serpeigd.github.io/TrainFitter/)
(separate from `master`, doesn't touch the existing `docs/` folder).
Submitted for Google's verification review as of 2026-09-07 — outcome not
yet known.

Full chronological development log — every session's changes, the direct
requests behind them, bugs found and fixed, and how each was verified —
lives in [`docs/status_history.md`](docs/status_history.md). Read it only
if you need the *history* behind a specific past decision, bug, or number
(when a feature shipped, why an earlier approach was abandoned, test
counts over time); don't load it by default, it's very long.

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
| Weekly meal planner (breakfast/lunch/dinner/snacks, synergy pairing) | `agents/planificador_comidas.py` |
| Per-client seeded variety (exercise picks, phrasing) | `agents/variacion.py` |
| Validator | `agents/validator_agent.py` |
| Orchestrator | `agents/orchestrator.py` |
| Exercise/food banks | `agents/exercise_bank.py`, `agents/food_bank.py` |
| Supplement-medication interaction pairs | `agents/suplementos_interacciones.py` |
| Bloodwork parser | `agents/analytics_parser.py` |
| Diet/checklist PDF generation + reading | `agents/pdf_generador.py` |
| Intake PDF generation + reading | `agents/pdf_intake.py` |
| Adherence summary formatting (rating, Notion text, suggested next step) | `agents/adherencia_parser.py` |
| Gmail connector (draft + portal-link send + adherence-reply/new-intake search) | `mcp/gmail_client.py` |
| Notion connector (auto-save + check-ins + portal reference codes) | `mcp/notion_connector.py` |
| Automatic inbox trigger (cron; adherence + new intakes) | `main.py`, `.github/workflows/inbox_trigger.yml` |
| Streamlit UI | `ui/app.py` |
| Tests | `tests/` (`conftest.py` fixture + `test_*.py` per module) |
| Example clients/outputs | `examples/` |
| Knowledge base (RAG-level) | `docs/base_conocimiento/*.md` |
| Trainer's method (judgment-level) | `docs/metodo_entrenador.md` |
