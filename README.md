<p align="center">
  <img src="assets/Cropped.jpg" alt="TrainFitter" width="100%">
</p>

# TrainFitter

[![CI](https://github.com/serpeigd/TrainFitter/actions/workflows/ci.yml/badge.svg)](https://github.com/serpeigd/TrainFitter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B.svg?logo=streamlit&logoColor=white)](https://trainfitter.streamlit.app/)
[![Free, no paid API key required](https://img.shields.io/badge/cost-100%25%20free-brightgreen.svg)](#free-only-by-design)

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

TrainFitter **never sends anything to the client on its own**. Everything it produces
is a **draft for your review**. It doesn't replace your professional judgment or
medical advice: any injury, condition, or clinical adjustment is always flagged for
you to review personally.

---

## What it includes right now

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
- The diet is a real **7-day meal plan** (breakfast/lunch/dinner/snacks), not
  just flat lists of suggested foods — built by
  [`agents/planificador_comidas.py`](agents/planificador_comidas.py) from the
  same free rule engine, still 100% free and deterministic per client.
  Portions are solved from the client's own kcal/macro targets, and
  absorption-synergy pairings (e.g. a plant-iron food paired with a
  vitamin-C source in the same meal) are applied structurally, grounded in
  [`docs/base_conocimiento/sinergias_nutrientes.md`](docs/base_conocimiento/sinergias_nutrientes.md)
  — not just listed as a separate tip. Renders as a styled table in the diet
  PDF and in the trainer's on-screen review, in whichever language the UI
  is set to.
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
  the trainer actually shares with a prospect to get the loop started. The
  panel can also send that blank form and check for a reply directly: a
  real, sent (not drafted) email — the third and narrowest of the three
  deliberate exceptions to "never sends automatically" (a fixed template
  with no variable content at all), gated behind the approval password on
  a public deployment the same way "Revisar cliente" is.
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
  alternative (see [`docs/decisiones.md`](docs/decisiones.md)). A previously
  uploaded bloodwork PDF doesn't need re-uploading on a revision either —
  the markers already extracted from it are kept and still feed the same
  safety check, verified live against a real out-of-range marker.
- The client portal also shows a client their own check-in history, not
  just today's — the same view the trainer already has, scoped to that
  client's own signed link so there's no way to see anyone else's data.
- A **"Clients"** tab gives the trainer a roster of every real client at a
  glance — most recent check-in and rating included, with a ⚠️ flag on
  anyone whose adherence just dropped — instead of looking each one up by
  email individually. Check-in history (both the trainer's and the
  client's own) now includes a simple trend chart for weight and adherence
  over time, reusing the same data already being logged.
- Both **"Revise client"** and **"Clients"** display real clients' personal
  data (emails at minimum; "Revise client" surfaces full health details) —
  on the public demo, both are gated behind the same shared password that
  already protects the "Approve" button, unlocked once per browser session
  rather than re-checked on every click. "Revise client"'s actual
  email lookup goes further: it re-checks that same password on every
  single load (not just the once-per-session unlock), since a shared or
  already-unlocked session shouldn't let anyone pull up any client's full
  profile just by knowing their email. Unset locally, same as everywhere
  else.
- Both rule engines now genuinely use most of what the intake form collects,
  instead of quietly ignoring several fields (a real, disclosed gap found by
  reading the code before writing any). **Routine:** volume and exercise
  complexity now actually scale by training level (grounded in
  [`docs/base_conocimiento/entrenamiento.md`](docs/base_conocimiento/entrenamiento.md)'s
  own MEV/MAV/MRV guidance), a short session (`minutos_por_sesion`) now
  really trims the number of exercises instead of being silently ignored,
  and high stress/short sleep keeps volume a bit more conservative — every
  adjustment explained in plain language, never silent. **Diet:** disliked
  foods and additional restrictions now actually get excluded (matched
  against each food's own name, accent-insensitive); a new "main dietary
  concern" field (e.g. anti-inflammatory, lower gluten) plus free-text
  scanning across the whole form biases the weekly plan toward matching
  foods — verified statistically, not just eyeballed (salmon's share of
  lunch/dinner protein picks went from a 13% baseline to 80% once
  "anti-inflammatory" was requested, averaged across 15 clients) — while
  staying diet-type aware (never suggests oily fish to a vegetarian/vegan
  client) and never confusing a soft preference with a real declared
  allergy.

## What it doesn't include yet

- Richer, more nuanced generative-AI writing — today's draft comes from deterministic
  rules based on the method plus seeded per-client variety (see above); an optional
  generative-AI layer (`motor="llm"`) is already designed and ready to switch on when
  it makes sense.

## Known limitations

Disclosed here the same way they're disclosed in [`docs/decisiones.md`](docs/decisiones.md)
— a passing test suite and a working demo shouldn't be read as claiming more than what's
actually been verified:

- **`motor="llm"` is designed but never exercised against the real Anthropic API.** The
  rule engine (`motor="reglas"`) is what every example, test, and the live demo actually
  run — see [Free-only by design](#free-only-by-design) below.
- **`buscar_intakes_nuevos()` (new-client intake scanning in `mcp/gmail_client.py`) is
  covered by mocked-network tests only, not a real inbox end-to-end.** Injecting a
  synthetic *incoming* message via Gmail's `messages().insert()` needs a broader OAuth
  scope than this project's deliberately narrow `gmail.compose` grants (`403 Insufficient
  Permission`) — every other Gmail code path (drafts, sends, adherence-reply scanning)
  *is* verified against a real mailbox; this one specific test gap is a documented
  trade-off, not an oversight. See `docs/decisiones.md`'s "Automated new-client intake"
  entry.
- **A revision can't re-attach the original bloodwork PDF.** Streamlit's `file_uploader`
  has no API for pre-seeding a file, so `_cargar_ficha_para_revisar()` can't offer the
  original upload back. This no longer loses safety-relevant data, though: the *extracted
  markers* from that PDF are stored in Notion's "Full Profile (JSON)" and carried forward
  automatically on a revision (verified live — a carried-forward out-of-range marker still
  forces `revision_reforzada`) — only the raw file itself isn't recoverable.
- **The client portal's "view your plan" screen is bounded by a truncated summary**, not
  the full generated routine/diet JSON — it reads back the same ≤2000-character summary
  `guardar_registro_cliente()` saves to Notion's Clients database, by design (see
  `docs/decisiones.md`'s portal entry): no second full-plan storage layer was added just
  for that screen.
- **A magic link can't be revoked individually once issued.** `agents/portal_tokens.py`'s
  tokens are stateless (no database to remove one from) — the only ways to invalidate a
  link early are its own expiry (7 days by default) or rotating `PORTAL_SECRET_KEY`,
  which invalidates *every* outstanding link at once.
- **The Streamlit Community Cloud free tier sleeps after inactivity.** The first request
  after a period of no traffic triggers a cold start (can take up to a minute); this is a
  hosting trade-off, not an application bug.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Matches CI (`.github/workflows/ci.yml`) and `pyproject.toml`'s `target-version` |
| Generation engines | Standard-library rule engines (default) + optional Anthropic API tool-use | Free by default; same output schema either way (see [`docs/arquitectura.md`](docs/arquitectura.md)) |
| UI | [Streamlit](https://streamlit.io/) | Fast, free-tier-hostable Python UI, no separate frontend build |
| PDF generation/parsing | [`reportlab`](https://www.reportlab.com/), [`pypdf`](https://pypi.org/project/pypdf/), [`pdfplumber`](https://github.com/jsvine/pdfplumber) | Fillable forms (intake, checklist) + bloodwork text extraction, all local, no OCR service |
| Email | Gmail API (`google-api-python-client`), scoped OAuth (`gmail.compose` → `gmail.readonly` → `gmail.send` for exactly one function) | Free tier, real inbox, scope-enforced draft-only behavior almost everywhere (see `docs/highlights.md` #3 and #10) |
| Persistence / lightweight CRM | Notion API (`notion-client`) — "Clients" + "Check-ins" databases | Free tier, no infra to run, human-readable outside the app too |
| Automation | GitHub Actions cron (`.github/workflows/inbox_trigger.yml`) | Free tier, no server to keep running |
| Tests | `pytest` | Deterministic rule engine + mocked-network coverage for Gmail/Notion |
| Lint | `ruff` | Core correctness rules only — see `pyproject.toml`'s note on why stricter naming rules are deliberately off (Spanish identifiers are intentional, see [`CLAUDE.md`](CLAUDE.md)) |
| Hosting | Streamlit Community Cloud (free tier) | [trainfitter.streamlit.app](https://trainfitter.streamlit.app/), auto-redeploys on push to `master` |

## Configuration

Every environment variable is **optional** — the default pipeline (`motor="reglas"`,
no PDF/Gmail/Notion features) needs none of them. Copy [`.env.example`](.env.example) to
`.env` and fill in only what the features you want to try actually need:

| Variable | Needed for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | `motor="llm"` (optional generative-AI engine) | Pay-per-token — see [Free-only by design](#free-only-by-design) |
| `NOTION_API_KEY`, `NOTION_DATABASE_ID`, `NOTION_CHECKINS_DATABASE_ID` | Notion connector (`mcp/notion_connector.py`) | Free Notion integration token; `NOTION_DATABASE_ID` is "Clients", `NOTION_CHECKINS_DATABASE_ID` is the separate "Check-ins" database |
| `APP_APPROVAL_PASSWORD` | Gating the "Approve" button, plus the "Revise client" and "Clients" sections, on a public deployment | Leave unset for local dev; set on any public deployment so a random visitor can't write to real Notion/Gmail or browse real clients' personal data |
| `PORTAL_SECRET_KEY` | Client portal magic links (`agents/portal_tokens.py`) | Any long random string; rotating it invalidates every outstanding link |
| `PORTAL_BASE_URL` | Building a clickable portal link | Defaults to `http://localhost:8501`; set to the real deployment URL in production |
| `TRAINER_NOTIFICATION_EMAIL` | Automatic trainer notification on a client check-in | Optional; unset = notification skipped entirely, the check-in itself still saves |

The Gmail connector (`mcp/gmail_client.py`) is configured separately, via
`credentials.json`/`token.json` from an OAuth consent flow (see that module's docstring
for the exact setup) — not plain environment variables, since it needs an interactive
browser authorization step. On Streamlit Community Cloud and GitHub Actions, where
there's no filesystem to persist those two files across restarts, their JSON content is
instead stored as the `GMAIL_CREDENTIALS_JSON`/`GMAIL_TOKEN_JSON` secrets and
materialized back to disk at startup (`ui/app.py`'s `_materializar_secretos_gmail()`,
`.github/workflows/inbox_trigger.yml`'s equivalent step) — local dev just uses the two
files directly.

## Free-only by design

TrainFitter's core promise: **fully free, no paid API key required.** The *only* piece
that would ever cost money is the optional `motor="llm"` path (pay-per-token Anthropic
API) — it's fully designed and schema-compatible with `motor="reglas"`, but deliberately
never exercised against the real API in this repo's tests, examples, or the live demo.
Every other feature (PDF generation/parsing, Gmail, Notion, hosting, CI, the cron trigger)
runs on local libraries or free-tier services. See `CLAUDE.md` and
[`docs/decisiones.md`](docs/decisiones.md#free-only-guardrail) for the full reasoning.

## Roadmap / next steps

Nothing here is committed — these are the next candidate improvements, roughly in order
of how directly they follow from what's already disclosed above:

- Actually exercise `motor="llm"` end-to-end against the real Anthropic API (currently
  designed but untested for real) to compare draft quality against the rule engine.
- Widen `buscar_intakes_nuevos()`'s real-inbox test coverage if a safe way to do so is
  found that doesn't require broadening the Gmail OAuth scope beyond what it needs.
- A way to revoke a single portal magic link early, without rotating the shared secret
  key for every client at once.
- Expanding the knowledge base (`docs/base_conocimiento/`) — see the `update-knowledge-base`
  project skill for the process already used to add the adherence/behavior-change note.

## FAQ

**Does this cost anything to run?** No — the default engine, PDF generation/parsing, the
Streamlit UI, and the free tiers of Notion/Gmail/GitHub Actions/Streamlit Cloud are all
free. The only optional paid piece is `motor="llm"`, off by default. See
[Free-only by design](#free-only-by-design).

**Will it ever email or message a client without a human clicking something first?** No.
Every plan is a draft until a trainer explicitly approves it, and the only three functions
in the whole codebase that send real email (`enviar_enlace_portal()`,
`enviar_notificacion_checkin()`, `enviar_formulario_intake()`) either require the trainer
to click a gated button, or notify the *trainer's own inbox*, never a client or
prospect, automatically. See `docs/highlights.md` #3 and #10.

**The live demo looks like it's not responding — is it broken?** Probably just asleep.
Streamlit Community Cloud's free tier spins down an inactive app; the first request after
a while wakes it back up, which can take up to a minute. Reload after a short wait.

**Why are some variable/dict-key names in Spanish?** A deliberate, documented scoping
exception — see `CLAUDE.md`'s "Standing conventions" and `docs/decisiones.md`. Prose,
comments, docs, and commit messages are English throughout; domain identifiers
(`perfil_cliente`, `revision_reforzada`, etc.) stay Spanish on purpose and aren't "bugs"
to fix.

## Repository structure

```
TrainFitter/
├── README.md                        This document
├── CLAUDE.md                        Project instructions / working notes (conventions, status)
├── main.py                          Automatic inbox trigger (adherence check-ins + new-client intakes, run via cron)
├── docs/
│   ├── metodo_entrenador.md         Trainer's methodology (knowledge base)
│   ├── arquitectura.md              System design and flow
│   ├── decisiones.md                Technical decision log, by phase
│   ├── highlights.md                1-page cheat sheet of the best design decisions
│   └── base_conocimiento/           Evidence-backed notes (training, nutrition, adherence, safety) the rule engines draw on
├── admission/
│   └── ficha_cliente_template.md    Client intake form
├── agents/                          Routine, diet, weekly meal planner, validator, orchestrator, PDF generation (+ intake form), seeded variety, portal tokens
├── tests/                           Pytest suite (rule engines, validator, orchestrator, connectors)
├── ui/                              Trainer's panel (Streamlit)
├── mcp/                             Connectors: Gmail (draft + portal-link send + adherence-reply/intake detection), Notion (Clients + Check-ins)
├── .github/workflows/               CI (every push) and the inbox trigger's cron schedule
├── assets/                          Cropped.jpg (banner), icon.png (favicon/sidebar mark), logo.jpg (source archive)
├── examples/                        Example clients and sample outputs
├── requirements.txt                 Python dependencies
├── pyproject.toml                   Ruff lint config
├── .env.example                     Template for optional env vars (see Configuration below)
└── .gitignore
```

## How to try it

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
you'll watch the plan get generated live.

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

**Optional — real generative-AI layer:** the agents also accept `motor="llm"` to use
the Anthropic API instead of the rule engine. To try it:
```bash
pip install -r requirements.txt
```
then copy `.env.example` to `.env` and set your `ANTHROPIC_API_KEY`.

### Option 4 — Automatic inbox trigger (the cron job, run manually)

`main.py` is what `.github/workflows/inbox_trigger.yml` runs on a schedule. It needs
real Gmail (`credentials.json`/`token.json`) and Notion credentials to do anything
useful — see [Configuration](#configuration) — but can be run by hand for testing:

```bash
python main.py
```

Scans the inbox once for adherence check-in replies and new-client intake PDFs, logs
what it finds to Notion, and exits — it never creates a Gmail draft or sends anything.

## Running the tests

Free — no API key needed, covers the rule engines, the validator's safety cross-checks,
and the full orchestrator pipeline:

```bash
pip install pytest
pytest
```

This is the same command CI runs on every push (`.github/workflows/ci.yml`).

## Commands quick reference

| Command | What it does | Needs an API key / credentials? |
|---|---|---|
| `python agents/run_pipeline_demo.py` | Full pipeline (routine → diet → validator) on the 3 example clients | No |
| `python agents/run_routine_demo.py` | Routine agent only | No |
| `python agents/run_manual_pipeline_demo.py` | Routine + diet + validator, no orchestrator | No |
| `streamlit run ui/app.py` | Trainer's visual panel, locally | No (Notion/Gmail features degrade gracefully if unset) |
| `python main.py` | Inbox trigger: scans for adherence replies + new intakes, logs to Notion | Yes — Gmail + Notion credentials |
| `pytest` | Full test suite | No |
| `ruff check .` | Lint | No |
| `python -m py_compile agents/*.py mcp/*.py ui/app.py main.py` | Syntax check (also run in CI) | No |
