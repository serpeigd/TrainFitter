# TrainFitter — Engineering Highlights

A 1-page cheat sheet of the project's most defensible design decisions, for
when you need them in a live conversation instead of digging through
[`decisiones.md`](decisiones.md)'s full log. Each one is a real trade-off,
made on purpose — not a default.

## 1. Two interchangeable engines, one schema

`routine_agent`/`diet_agent` take `motor="reglas"` (free, deterministic
Python, default) or `motor="llm"` (Anthropic API, tool-use forced output) —
both return the *exact same* output schema, so nothing downstream cares
which one ran. **Why it matters:** the whole pipeline was buildable and
testable end-to-end from day one without ever needing a paid key, and
swapping in real generative writing later is a one-line change, not a
rewrite.

## 2. The safety gate is never the LLM

`validator_agent.py` is deliberately rule-based, full stop — not "the free
version of a smarter validator." A safety gate needs to be deterministic and
auditable: the same input always produces the same verdict, and anyone can
read the code and know exactly what's checked. It also doesn't trust
routine/diet's self-reported warnings — it independently re-derives risk
from the raw profile and cross-checks generated content against
`exercise_bank.py`/`food_bank.py` (defense in depth, verified in tests with
hand-built "defective" drafts that don't self-flag, proving the cross-check
catches it anyway).

## 3. "Never sends automatically" is enforced, not promised

The Gmail connector (`mcp/gmail_client.py`) requests only the
`gmail.compose` OAuth scope. That's not a design choice the code has to keep
— Google's API physically rejects a send call under that scope. On a public
demo where anyone can type an arbitrary recipient email, that distinction is
the difference between "the code currently doesn't send" and "the code
*can't*." When the project later needed to detect a real send (to log it in
a Notion "Check-ins" history), the added scope was `gmail.metadata` —
labels and headers only — deliberately not the broader `gmail.readonly`,
which would also have worked but grants full message-body access this
feature never needed.

## 4. An explicit state machine, not loose variables

`orchestrator.py`'s `PipelineState` dataclass makes the pipeline's state a
first-class, inspectable object instead of "whichever variables happen to be
filled in right now." The `on_transition` callback decouples it from *how*
that state gets observed — the console log and the Streamlit UI's live
progress view are two different callbacks over the same state machine, and
the orchestrator has zero knowledge Streamlit exists.

## 5. A translation pass caught a real bug before it shipped

Translating example clients' injury/allergy free text to English would have
silently broken `tags_lesiones()`/`etiquetas_excluidas()`, which only
matched Spanish keywords — disabling `revision_reforzada` for any
English-described injury or allergy. Caught proactively while translating,
not from a bug report, and fixed by making the matching bilingual. A small
example of what "defense in depth" costs if you don't actually check it.

## 6. "Fully free" is a constraint that shaped every later decision

Every optional addition — the bloodwork PDF parser, the Gmail connector, the
test suite, the Streamlit Cloud deploy — was built to need nothing but free
tiers and local libraries. The *only* piece of the entire project that would
ever cost money is `motor="llm"`, and it's designed but deliberately never
exercised against the real API. That's a real constraint that ruled out
easier paths more than once (e.g. OCR services for the bloodwork parser),
not a marketing line.

---

*For the full "why," including things that were tried and reverted, see*
[`decisiones.md`](decisiones.md).
