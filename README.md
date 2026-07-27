# TrainFitter

[![CI](https://github.com/serpeigd/TrainFitter/actions/workflows/ci.yml/badge.svg)](https://github.com/serpeigd/TrainFitter/actions/workflows/ci.yml)

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
  approve — all from the browser.
- Tested with two example cases: one straightforward, one with an injury and a
  vegetarian diet, to confirm the enhanced-review flag fires when it should.

## What it doesn't include yet

- A real email/Notion connection to send drafts (coming in a later phase).
- Richer, more nuanced generative-AI writing — today's draft comes from deterministic
  rules based on the method; an optional generative-AI layer (`motor="llm"`) is
  already designed and ready to switch on when it makes sense.

## Repository structure

```
TrainFitter/
├── README.md                        This document
├── docs/
│   ├── metodo_entrenador.md         Trainer's methodology (knowledge base)
│   ├── arquitectura.md              System design and flow
│   └── decisiones.md                Technical decision log, by phase
├── admission/
│   └── ficha_cliente_template.md    Client intake form
├── agents/                          Routine, diet, validator, and orchestrator
├── tests/                           Pytest suite (rule engines, validator, orchestrator)
├── ui/                              Trainer's panel (Streamlit)
├── mcp/                             MCP connectors: Notion, Gmail (Phase 5)
├── templates/                       Email/plan templates (Phase 5)
├── examples/                        Example clients and sample outputs
├── requirements.txt                 Python dependencies
└── .gitignore
```

## How to try it

### Option 1 — Visual panel (recommended)

```bash
pip install streamlit
streamlit run ui/app.py
```

Opens in your browser. Pick an example client or fill out a new intake form, and
you'll watch the plan get generated live.

### Option 2 — Terminal (nothing to install)

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
