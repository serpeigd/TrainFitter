<p align="center">
  <img src="assets/Cropped.jpg" alt="TrainFitter" width="100%">
</p>

# TrainFitter

[![CI](https://github.com/serpeigd/TrainFitter/actions/workflows/ci.yml/badge.svg)](https://github.com/serpeigd/TrainFitter/actions/workflows/ci.yml)

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
- Tested with two example cases: one straightforward, one with an injury and a
  vegetarian diet, to confirm the enhanced-review flag fires when it should.
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
  confirmed send, ticks it off and logs the check-in automatically.
- On the public demo, approving a plan (and unlocking Notion/Gmail) is gated
  behind a shared password, so a random visitor can't write to the trainer's
  real accounts just by clicking through.
- An **automatic inbox trigger** (see [`main.py`](main.py)) scans the trainer's
  Gmail inbox for a filled-in checklist PDF clients send back once they've
  actually started their plan, reads its form field values, and logs a
  summarized check-in row per reply (days completed, notes, a rough adherence
  rating), deduped so a scheduled re-scan never double-logs the same reply.
  Runs free on a GitHub Actions cron
  ([`.github/workflows/inbox_trigger.yml`](.github/workflows/inbox_trigger.yml)).

## What it doesn't include yet

- Richer, more nuanced generative-AI writing — today's draft comes from deterministic
  rules based on the method plus seeded per-client variety (see above); an optional
  generative-AI layer (`motor="llm"`) is already designed and ready to switch on when
  it makes sense.

## Repository structure

```
TrainFitter/
├── README.md                        This document
├── main.py                          Automatic inbox trigger (adherence check-ins, run via cron)
├── docs/
│   ├── metodo_entrenador.md         Trainer's methodology (knowledge base)
│   ├── arquitectura.md              System design and flow
│   ├── decisiones.md                Technical decision log, by phase
│   └── highlights.md                1-page cheat sheet of the best design decisions
├── admission/
│   └── ficha_cliente_template.md    Client intake form
├── agents/                          Routine, diet, validator, orchestrator, PDF generation, seeded variety
├── tests/                           Pytest suite (rule engines, validator, orchestrator, connectors)
├── ui/                              Trainer's panel (Streamlit)
├── mcp/                             Connectors: Gmail (draft + send/adherence-reply detection), Notion (Clients + Check-ins)
├── .github/workflows/               CI (every push) and the inbox trigger's cron schedule
├── assets/                          Cropped.jpg (banner), icon.png (favicon/sidebar mark), logo.jpg (source archive)
├── examples/                        Example clients and sample outputs
├── requirements.txt                 Python dependencies
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

This runs the full pipeline (routine → diet → validator) on the two example clients
and prints the state trail and final result to the terminal.

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

## Running the tests

Free — no API key needed, covers the rule engines, the validator's safety cross-checks,
and the full orchestrator pipeline:

```bash
pip install pytest
pytest
```

This is the same command CI runs on every push (`.github/workflows/ci.yml`).
