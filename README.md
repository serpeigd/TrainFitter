<p align="center">
  <img src="assets/Cropped.jpg" alt="TrainFitter" width="100%">
</p>

# TrainFitter

[![CI](https://github.com/serpeigd/TrainFitter/actions/workflows/ci.yml/badge.svg)](https://github.com/serpeigd/TrainFitter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-informational.svg)](LICENSE)

**🔗 [Live demo](https://trainfitter.streamlit.app/) — no install, no login, no API key.**
**📋 [Engineering highlights](docs/highlights.md)** — the 1-page version of what's interesting here.

**An assistant that helps you prepare draft workout and nutrition plans for your
clients, following your own method and judgment — faster, without losing your voice.**

> *"Teach your body that your mind is in charge."*

---

## What problem does it solve?

When you coach online, the bottleneck isn't coaching itself: it's the **time** spent
writing a routine and a diet from scratch for every new client. Hours of repetitive
work that take away from what actually matters — follow-up and the relationship with
the person.

TrainFitter takes a client's **intake form** and generates a **first draft** of their
routine and diet following *your* documented methodology: how you progress load, how
you approach flexible nutrition, your warm and pedagogical tone, and the myths you
reject. You just **review, adjust, and approve**.

## What do you get?

- A **draft routine** adapted to the client's level, equipment, and availability.
- A **draft diet** that's flexible and adjusted to their preferences and restrictions.
- An **automatic flag** whenever a case needs your enhanced review (an injury or a
  clinical condition, for example), so nothing sensitive slips through.

Personalization goes beyond the goal: the intake form collects **health data**
(allergies, conditions, pregnancy, medication, weight) and even lets a **bloodwork
report** be attached to fine-tune the diet. Anything clinical is flagged for **you**
to review — the system never diagnoses or prescribes.

## How it works (in one sentence)

Client intake → draft routine → draft diet → automatic safety review →
**you approve before anything is sent**.

## The most important part: you have the final say

TrainFitter **never sends anything to the client on its own**, with one narrow,
disclosed exception (the client portal's magic-link email — see below). Everything
it produces is a **draft for your review**. It doesn't replace your professional
judgment or medical advice: any injury, condition, or clinical adjustment is always
flagged for you to review personally.

---

## Features

This repository is built phase by phase, as a learning project. Right now:

- The **full pipeline actually works**: client intake → routine → diet → safety
  validation → ready-for-your-approval state. **Free, no API key or account required**
  — the default engine is deterministic and doesn't depend on any external service.
- A **visual panel** (not just a terminal): upload or create a client intake, watch
  the plan get generated, review the routine and diet with tables and metrics, and
  approve — all from the browser. Dark theme by default, and a full **English/Spanish
  toggle** — the generated plan's narrative text (messages, warmups, progression) now
  follows it too; exercise/food names stay in their canonical form on purpose (see
  `docs/decisiones.md`) so the validator's safety cross-check can't silently break.
- Tested with three example cases: one straightforward, one with an injury and a
  vegetarian diet, and one vegan client with a food allergy, to confirm the
  enhanced-review flag fires when it should. The third one also ships the full
  adherence loop's artifacts (a filled-in checklist PDF and the resulting
  Check-in data) so the loop is visible without having to read code to
  understand what it produces.
- An optional **bloodwork PDF** can be attached to the intake — out-of-range markers
  are extracted (best-effort, bilingual) and automatically force enhanced review,
  same defense-in-depth pattern as injuries and allergies
  (see [`agents/analytics_parser.py`](agents/analytics_parser.py)).
- A real **Gmail draft** can be created for the approved plan — never sent
  automatically, by design (see [`mcp/gmail_client.py`](mcp/gmail_client.py)):
  the trainer reviews and sends it themselves from their own Gmail. The draft
  carries a brief note plus two generated PDFs (see
  [`agents/pdf_generador.py`](agents/pdf_generador.py)): the diet plan, and a
  fillable check-in form for the routine.
- Every real new-client plan is automatically **saved to Notion** as a
  persistent record (see [`mcp/notion_connector.py`](mcp/notion_connector.py))
  — a lightweight CRM outside the browser session, which otherwise forgets
  everything on refresh. Example-client demo runs are deliberately excluded.
- The free rule engine is no longer a template mill: exercise picks and the
  narrative text (progression notes, client messages, meal-timing guidance)
  are chosen per client from a seeded pool of equivalent, on-voice phrasings
  (see [`agents/variacion.py`](agents/variacion.py)) — two similar clients no
  longer get byte-identical drafts, while regenerating the *same* client
  still reproduces the same plan every time.
- A second **Check-ins** Notion database logs the client's interaction history
  (joined to the main record by email). A "Check if it was sent" button confirms
  whether the trainer actually sent the Gmail draft (not just created it) and, on a
  confirmed send, ticks it off and logs the check-in automatically. That history
  is also visible directly in the panel itself (an "Adherence history" section
  next to the Gmail controls) — no need to open Notion just to see how a
  returning client has been doing.
- On the public demo, approving a plan (and unlocking Notion/Gmail) is gated
  behind a shared password, so a random visitor can't write to the trainer's
  real accounts just by clicking through.
- An **automatic inbox trigger** (see [`main.py`](main.py)) runs two independent
  jobs on a schedule: it scans the trainer's Gmail inbox for a filled-in
  checklist PDF clients send back once they've actually started their plan,
  reads its form field values, and logs a summarized check-in row per reply
  (days completed, notes, a rough adherence rating); and it scans for a
  filled-in **intake** PDF a prospective client emailed back, runs the full
  pipeline on it, and logs a heads-up record to Notion — no trainer typing
  required, though the trainer still reviews and approves the plan exactly as
  before. Both jobs dedupe by Gmail message ID so a scheduled re-scan never
  double-logs the same reply. Runs free on a GitHub Actions cron
  ([`.github/workflows/inbox_trigger.yml`](.github/workflows/inbox_trigger.yml)).
- The panel also accepts that same filled-in **intake PDF** directly: instead
  of retyping a client's answers by hand, the trainer can upload the PDF a
  prospect sent back (see [`agents/pdf_intake.py`](agents/pdf_intake.py)) and
  review/approve it through the exact same flow as a manually typed intake.
  The blank form itself is a real, committed artifact
  ([`examples/blank_intake_form.pdf`](examples/blank_intake_form.pdf)) — what
  the trainer actually shares with a prospect to get the loop started.
- A **client-facing portal** (magic link, no password): the trainer can send a
  client a private link to view a summary of their plan and log a check-in
  directly — no PDF round-trip needed. Links are signed, stateless, and
  self-expiring (see [`agents/portal_tokens.py`](agents/portal_tokens.py)), so
  no separate database of issued links is needed. Sessions completed can
  exceed what was planned (an explicit "I trained more than planned" checkbox
  covers a genuine extra session); diet days followed can't exceed the check-in
  period, since that bound is definitional rather than a target. The moment a
  client submits a check-in, the trainer's own inbox gets an automatic summary
  plus a short, rule-based suggested next step — this is one of only two
  places in the whole project where Gmail actually **sends** a real email
  instead of only creating a draft, and both send to the trainer's side of the
  relationship, never to a client without review — a deliberate, narrow
  exception (see [`docs/decisiones.md`](docs/decisiones.md)) to the "never
  sends automatically" guarantee everywhere else in this project. The
  check-in form can also log the client's current weight (optional) — closing
  a loop the generated plan itself already promised ("adjusted based on real
  weight ... over the first few weeks") but had no mechanism for until now.
- A **"Revise client"** section lets the trainer look up a past client by
  email and reopen their exact intake form, pre-filled with everything they
  originally entered, to edit and regenerate — approving updates that same
  Notion record in place rather than creating a duplicate. This is a real,
  deliberate architecture change: Notion now stores each client's complete
  profile (chunked across a `rich_text` property), not just a summary — a
  trade-off the project owner chose explicitly after seeing the lighter
  alternative (see [`docs/decisiones.md`](docs/decisiones.md)).

## What it doesn't include yet

- Richer, more nuanced generative-AI writing — today's draft comes from deterministic
  rules based on the method plus seeded per-client variety (see above); an optional
  generative-AI layer (`motor="llm"`) is already designed and ready to switch on when
  it makes sense.

---

## Architecture

Full design rationale, the orchestrator's state diagram, and the automation loop
(intake PDF → inbox trigger → portal → revise-client) live in
[`docs/arquitectura.md`](docs/arquitectura.md). In short:

```
Client intake → routine_agent + diet_agent (motor="reglas"|"llm", same output schema)
             → validator_agent (ALWAYS rule-based, re-derives risk from raw profile)
             → verdict: aprobado_automatico | revision_reforzada
             → human review (ALWAYS — no plan is ever auto-sent)
             → Notion "Clients" record saved + Gmail draft created
             → trainer confirms the send → Notion "Email Sent" + "Check-ins" row
```

Two things worth knowing before reading the code:

- **Two interchangeable engines, one schema.** `routine_agent`/`diet_agent` take
  `motor="reglas"` (free, deterministic Python, default) or `motor="llm"` (Anthropic
  API, tool-use forced output) — both return the exact same output schema, so
  nothing downstream cares which one ran. The rule engine is what every demo, test,
  and the live deploy actually runs; `motor="llm"` is designed but deliberately
  never exercised against the real (paid) API in this project — see the
  [Free-only guardrail](#free-only-guardrail) below.
- **The safety gate (`validator_agent.py`) is never the LLM path** — a rule-based
  gate that independently re-derives risk from the raw client profile and
  cross-checks generated content against `exercise_bank.py`/`food_bank.py`, rather
  than trusting the generation agents' self-reported warnings.

`docs/decisiones.md` is the full chronological decision log (every trade-off, with
its "why"); [`docs/highlights.md`](docs/highlights.md) is the 1-page,
interview-ready condensed version of the same log.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | See `pyproject.toml` (`target-version`) and CI's `setup-python`. |
| Rule engines | Standard library only (`agents/rutina_reglas.py`, `agents/dieta_reglas.py`, `agents/variacion.py`) | The default, free path — no dependency can break it. |
| Optional generative layer | [Anthropic API](https://docs.anthropic.com/) (`agents/routine_agent.py`, `agents/diet_agent.py`, `motor="llm"`) | Forced structured output via tool use; same schema as the rule engine. |
| UI | [Streamlit](https://streamlit.io/) (`ui/app.py`) | Fast to build a real trainer-facing panel without a separate frontend/backend split. |
| PDF generation/reading | [reportlab](https://www.reportlab.com/) + [pypdf](https://pypdf.readthedocs.io/) (`agents/pdf_generador.py`, `agents/pdf_intake.py`) | Free, no system dependencies, no OCR service — fillable forms with a fixed, known field set. |
| Bloodwork PDF parsing | [pdfplumber](https://github.com/jsvine/pdfplumber) (`agents/analytics_parser.py`) | Best-effort text extraction, bilingual keyword matching — no paid OCR/vision API. |
| Email | [Gmail API](https://developers.google.com/gmail/api) via `google-api-python-client` (`mcp/gmail_client.py`) | OAuth-scoped so most of the codebase can only create drafts, never send — see the module's own docstring. |
| Persistent record | [Notion API](https://developers.notion.com/) via `notion-client` (`mcp/notion_connector.py`) | Free integration token, no OAuth flow, doubles as a lightweight CRM. |
| Automation | [GitHub Actions](https://github.com/features/actions) cron (`.github/workflows/inbox_trigger.yml`, `.github/workflows/ci.yml`) | Free tier, no server to run/maintain. |
| Hosting (live demo) | [Streamlit Community Cloud](https://streamlit.io/cloud) | Free tier; sleeps after inactivity. |
| Tests | [pytest](https://pytest.org/) (`tests/`) | Rule engines, validator, orchestrator, connectors (mocked network), PDF round-trips. |
| Lint | [ruff](https://docs.astral.sh/ruff/) (`pyproject.toml`) | Correctness rules only (`E`, `F`, `W`, `I`) — deliberately not naming/docstring rules, since this project keeps Python identifiers in Spanish on purpose. |

No database beyond Notion, no message queue, no container orchestration — the
project's scale doesn't call for any of that, and the free-only guardrail below
rules out anything that would.

## Repository structure

```
TrainFitter/
├── README.md                        This document
├── CLAUDE.md                        Working notes / standing conventions for Claude Code
├── LICENSE                          MIT
├── main.py                          Automatic inbox trigger (adherence check-ins + new-client intakes, run via cron)
├── pyproject.toml                   Ruff configuration
├── pytest.ini                       Pytest configuration (testpaths = tests)
├── conftest.py                      Root-level pytest fixture wiring
├── requirements.txt                 Python dependencies (annotated: what's optional and why)
├── .env.example                     Template for local secrets — copy to .env
├── docs/
│   ├── metodo_entrenador.md         Trainer's methodology (knowledge base)
│   ├── arquitectura.md              System design, data flow, and the automation loop
│   ├── decisiones.md                Technical decision log, chronological, by phase
│   ├── highlights.md                1-page cheat sheet of the best design decisions
│   └── base_conocimiento/           Evidence-backed notes (training/nutrition/adherence)
├── admission/
│   └── ficha_cliente_template.md    Client intake form (source of truth for the schema)
├── agents/                          Routine, diet, validator, orchestrator, PDF generation (+ intake form), seeded variety, portal tokens, adherence parsing
├── tests/                           Pytest suite (rule engines, validator, orchestrator, connectors, PDF round-trips)
├── ui/                              Trainer's panel + client portal view (Streamlit)
├── mcp/                             Connectors: Gmail (draft + portal-link/notification send + adherence-reply/intake detection), Notion (Clients + Check-ins)
├── .github/workflows/               CI (every push) and the inbox trigger's cron schedule
├── .streamlit/                      Streamlit theme configuration
├── .devcontainer/                   Dev Container definition (optional, for a reproducible local setup)
├── assets/                          Cropped.jpg (banner), icon.png (favicon/sidebar mark), logo.jpg (source archive)
├── examples/                        Example clients, sample outputs, blank/filled intake and checklist PDFs
└── .gitignore
```

---

## Installation

Prerequisite: Python 3.12 (CI pins this version; other 3.x versions likely work
but aren't tested).

```bash
git clone https://github.com/serpeigd/TrainFitter.git
cd TrainFitter
```

The **default, free pipeline needs no dependencies at all** — `rutina_reglas.py`,
`dieta_reglas.py`, and the orchestrator are pure standard-library Python. Everything
below is opt-in, one piece at a time:

```bash
# Everything (UI, PDF gen/parsing, Gmail, Notion, tests, lint) in one go:
pip install -r requirements.txt

# Or just what you need, e.g. only the visual panel:
pip install streamlit
```

`requirements.txt` documents, next to each dependency, exactly what it's for and
why it's optional — read it before trimming the list.

## Configuration

Copy the template and fill in only what you plan to use — every integration in
this project degrades to "off" (not "broken") when its configuration is missing:

```bash
cp .env.example .env
```

### Environment variables (`.env`, local dev)

| Variable | Required for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | `motor="llm"` (optional generative layer) | Never exercised against the real API in this project by default — see [Free-only guardrail](#free-only-guardrail). |
| `NOTION_API_KEY` | Saving/reading Clients & Check-ins records | Notion integration token (no OAuth flow) — see `mcp/notion_connector.py`'s module docstring for setup steps. |
| `NOTION_DATABASE_ID` | Same as above | The "Clients" database. |
| `NOTION_CHECKINS_DATABASE_ID` | Adherence history / check-ins | The separate "Check-ins" database, joined to Clients by email (not a Notion relation). |
| `APP_APPROVAL_PASSWORD` | Gating the "Approve" button | Unset = no gate (fine for local dev). Set on any public deployment so a random visitor can't write to your real Notion/Gmail. |
| `PORTAL_SECRET_KEY` | Client portal magic links | Any long random string, used to sign links (HMAC-SHA256). Rotating it invalidates every outstanding link — see `agents/portal_tokens.py`. |
| `PORTAL_BASE_URL` | Building a clickable portal link | Defaults to `http://localhost:8501`; set to your real deployment's URL (e.g. `https://trainfitter.streamlit.app`) in production. |
| `TRAINER_NOTIFICATION_EMAIL` | Automatic trainer notification on a portal check-in | Unset = notification skipped. Never used to email a client. |

Gmail's own credentials are **not** `.env` variables — locally, `mcp/gmail_client.py`
reads two gitignored files at the repo root instead:

| File | Required for | Notes |
|---|---|---|
| `credentials.json` | Any Gmail feature (draft creation, send-detection, portal-link/notification send, inbox scanning) | An OAuth Desktop-app credential from Google Cloud Console — see `mcp/gmail_client.py`'s module docstring for the full setup steps and current OAuth scopes (`gmail.compose`, `gmail.readonly`, `gmail.send`). |
| `token.json` | Same as above | Generated automatically on first run via the OAuth consent flow; cached so you're not re-prompted every run. Delete it to force re-consent after a scope change. |

### Cloud secrets (Streamlit Community Cloud / GitHub Actions)

Neither platform lets you upload arbitrary files as secrets, so `credentials.json`/
`token.json` are bridged from plain key/value secrets instead:

| Secret | Where it's read | Notes |
|---|---|---|
| `GMAIL_CREDENTIALS_JSON` | Streamlit Cloud secrets, GitHub Actions repo secrets | Full JSON content of `credentials.json`. Materialized to disk by `ui/app.py`'s `_materializar_secretos_gmail()` (Streamlit) or `inbox_trigger.yml`'s "Write Gmail credentials from secrets" step (GitHub Actions). |
| `GMAIL_TOKEN_JSON` | Same as above | Full JSON content of `token.json`. |

On Streamlit Cloud, every `.env` variable above is also set as a regular
Streamlit secret (same names, `st.secrets`/`os.environ` are bridged automatically by
`python-dotenv` + Streamlit's own secrets-to-env behavior). On GitHub Actions,
`inbox_trigger.yml` passes `NOTION_API_KEY`/`NOTION_DATABASE_ID`/
`NOTION_CHECKINS_DATABASE_ID` through as job secrets (see the workflow file) —
`ci.yml` needs none of these, since it only ever runs the free rule engine.

---

## Usage

### Option 1 — Live demo (fastest, nothing to install)

👉 **[trainfitter.streamlit.app](https://trainfitter.streamlit.app/)**

Hosted free on Streamlit Community Cloud, running the same rule engine as local —
no API key needed. Note: free-tier apps sleep after inactivity, so the first load
may take a few seconds to wake up.

### Option 2 — Visual panel, locally

```bash
pip install streamlit
streamlit run ui/app.py
```

Opens in your browser. Pick an example client or fill out a new intake form, and
you'll watch the plan get generated live. This is the trainer's main entry point —
it's also where a client lands when they open a portal magic link
(`?portal_token=...`), rendered as a client-only view instead of the trainer panel.

### Option 3 — Terminal (nothing to install)

The default pipeline is pure standard Python, no API key or account needed:

```bash
python agents/run_pipeline_demo.py
```

This runs the full pipeline (routine → diet → validator) on the three example
clients and prints the state trail and final result to the terminal.

You can also run each piece separately:
```bash
python agents/run_routine_demo.py         # routine agent only
python agents/run_manual_pipeline_demo.py # routine + diet + validator, no orchestrator
```

### Option 4 — Automatic inbox trigger (`main.py`)

This is the project's **second entry point**: instead of a human opening the
panel, it scans the trainer's Gmail inbox on a schedule and processes what it
finds — filled-in adherence checklists and filled-in new-client intake PDFs —
logging results to Notion without any manual step. In production it runs on a
free GitHub Actions cron ([`.github/workflows/inbox_trigger.yml`](.github/workflows/inbox_trigger.yml),
daily by default, plus `workflow_dispatch` for an on-demand run from the Actions
tab). To run it by hand (needs `credentials.json`/`token.json` and the `NOTION_*`
variables configured, same as the panel's Gmail/Notion features):

```bash
python main.py
```

It never creates a Gmail draft or sends anything — the trainer still reviews and
approves every plan through `ui/app.py`, exactly as with a manually typed intake.

**Optional — real generative-AI layer:** the agents also accept `motor="llm"` to use
the Anthropic API instead of the rule engine. To try it:
```bash
pip install -r requirements.txt
```
then copy `.env.example` to `.env` and set your `ANTHROPIC_API_KEY`.

## Available commands

| Command | What it does | Needs |
|---|---|---|
| `streamlit run ui/app.py` | Launch the trainer's panel (and the client portal view) | `pip install streamlit` |
| `python agents/run_pipeline_demo.py` | Run the full pipeline on the three example clients, print the state trail | Nothing (standard library only) |
| `python agents/run_routine_demo.py` | Run only the routine agent on the example clients | Nothing |
| `python agents/run_manual_pipeline_demo.py` | Run routine + diet + validator without the orchestrator | Nothing |
| `python main.py` | Run the inbox trigger's two jobs once (adherence check-ins + new intakes) | `credentials.json`/`token.json`, `NOTION_*` |
| `pytest` | Run the full test suite | `pip install pytest` (plus the connectors' packages for their mocked-network tests — see `requirements.txt`) |
| `ruff check .` | Lint (same check CI runs) | `pip install ruff` |
| `python -m py_compile agents/*.py mcp/*.py ui/app.py main.py` | Fast syntax check of every module (part of CI) | Nothing |

This is the same sequence `.github/workflows/ci.yml` runs on every push: syntax
check → lint → example-client schema validation → full rule-engine pipeline →
test suite.

## Roadmap

- **Richer generative writing.** `motor="llm"` is already designed (same output
  schema as the rule engine, forced tool-use output) but deliberately never
  exercised against the real, paid Anthropic API in this project — see
  [Free-only guardrail](#free-only-guardrail).
- Everything else planned so far has shipped — see `docs/decisiones.md` for the
  full chronological log of what was considered and either built or explicitly
  deferred.

## Limitations

- **`motor="llm"` is unverified against the real API.** It's designed and unit-testable
  against fixtures, but this project has never spent real money calling the actual
  Anthropic API — treat it as a documented design, not a proven path, until exercised.
- **A "Revise client" doesn't re-attach the original intake's bloodwork PDF.** Notion
  now stores a client's complete profile for reload/edit, but `st.file_uploader` has
  no Streamlit API to pre-seed a file — a revision's bloodwork attachment has to be
  re-uploaded by the trainer if still relevant. Disclosed in `_cargar_ficha_para_revisar()`'s
  own docstring.
- **One Gmail code path is covered only by mocked-network tests, not a live inbox.**
  `buscar_intakes_nuevos()`'s search/parse mechanics can't be proven end-to-end against
  a real inbox: injecting a synthetic incoming message via `messages().insert()`
  needs a broader OAuth scope than this project's deliberately narrow grants allow
  (403, `Insufficient Permission`) — a genuine, disclosed testing gap, not a bug
  papered over. See `docs/decisiones.md` and `docs/highlights.md` #9.
- **All content is fictional.** Client names, injuries, and other health/fitness
  details throughout this project (the trainer's persona, `examples/cliente_ejemplo_*.json`,
  the knowledge base) are made up for demo purposes — see `docs/metodo_entrenador.md`.
- **Nothing here is medical advice.** The system never diagnoses or prescribes; any
  injury, condition, pregnancy, medication, or out-of-range bloodwork marker forces
  human review, never an automated clinical decision.

## Free-only guardrail

TrainFitter's core promise is **fully free, no paid API key required**. The *only*
piece that would ever need one is the optional `motor="llm"` path (pay-per-token
Anthropic API) — it's designed but deliberately never exercised against the real
API in this project. Every other feature — the visual panel, the bloodwork parser,
the Gmail/Notion connectors, the client portal, the automatic inbox trigger, the
live demo itself — runs on local libraries or a service's free tier.

## FAQ

**Does TrainFitter ever email a client without a human looking at it first?**
No, with one narrow, disclosed exception: the client portal's magic link itself
has to reach the client's inbox to be useful, so `gmail_client.enviar_enlace_portal()`
sends that one email (a fixed template, one variable slot) once the trainer
clicks a gated button. Every plan (routine + diet) always goes out only as a
Gmail **draft** that the trainer reviews and sends themselves. See
`docs/highlights.md` #3 and #10 for the full reasoning.

**Does it cost anything to run?**
No. The default pipeline needs no API key at all. Every optional integration
(Gmail, Notion, the Streamlit host, GitHub Actions) uses a free tier or a
free API. The only path that would ever cost money (`motor="llm"`) is
designed but never actually called in this project.

**What happens with sensitive data (injuries, allergies, pregnancy, bloodwork)?**
It's collected in the intake specifically so the plan can be adapted safely, and
it always forces enhanced human review (`revision_reforzada`) rather than being
silently absorbed into the draft. The validator never trusts the generation
agents' self-reported flags — it independently re-derives risk from the raw
profile every time. See `docs/arquitectura.md`'s "Clinical personalization layer."

**Why isn't LangGraph/CrewAI/AutoGen involved?**
The pipeline is a short, explicit sequence (routine → diet → validate) with one
real branch (verdict), modeled as a plain state dataclass
(`agents/orchestrator.py`) instead of a graph framework — see
`docs/highlights.md` #4. Nothing about the current scope has needed cyclic
agent behavior or dynamic re-planning that would justify the extra dependency.

**Why are some identifiers in Spanish?**
A deliberate, documented scoping decision: all prose, comments, docs, and commit
messages are English, but Python identifiers, dict/JSON keys, and literal state
values (e.g. `perfil_cliente`, `revision_reforzada`) stay in Spanish, matching the
domain language the trainer's own method (`docs/metodo_entrenador.md`) is written
in. See `docs/decisiones.md`.

## Running the tests

Free — no API key needed, covers the rule engines, the validator's safety cross-checks,
the full orchestrator pipeline, the connectors (mocked network), and PDF round-trips:

```bash
pip install pytest
pytest
```

This is the same command CI runs on every push (`.github/workflows/ci.yml`).

## License

[MIT](LICENSE) — see the LICENSE file.
