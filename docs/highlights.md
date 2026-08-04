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

## 7. A display-only translation layer, kept separate from a safety cross-check

Making generated content follow the UI's EN/ES toggle looked like a simple
find-and-replace at first. It isn't: `validator_agent.py` cross-checks a
draft's exercise/food *names* against the client's declared injuries and
allergies by exact string match. If those names changed language with the
UI, that match would silently stop firing — a language preference quietly
disabling a safety check. The fix keeps exercise/food `"nombre"` values
canonical (English, always) and adds a separate, display-only
`nombre_mostrado()` helper called exclusively from the UI's rendering code,
never from generation or validation. An explicit test locks in that
invariant so a future refactor can't reintroduce the bug by accident.

## 8. Variety without an LLM: seeded, not random

The free rule engines used to give two similar clients the exact same
exercises and near-identical boilerplate messages — a real "template
mill" problem, but neither an LLM (breaks the free-only guardrail) nor
true randomness (undermines the "regenerate = same draft" trust the
validator's own determinism principle depends on, and makes tests flaky)
felt like the right fix. `agents/variacion.py` seeds a `random.Random`
from each client's own `id_cliente`: the same client always regenerates
the same plan, but different clients no longer collide. Zero new
dependencies, zero cost — `random` is standard library — and the
resulting variety is still fully assertable in tests (same client twice →
equal; N distinct clients → more than one distinct result).

## 9. A structured form beats free text for safety-critical intake, and a real test gap got written down instead of hidden

Automating new-client intake (a prospect emails back a filled PDF, the
pipeline runs unattended) touches the exact fields `validator_agent.py`
exists to defend — injuries, allergies, pregnancy. Free-text parsing (even
via an LLM, which the free-only guardrail rules out anyway) means trusting
a parser's coverage on safety-critical data; a fillable PDF form
(`agents/pdf_intake.py`) only ever produces a fixed, known set of field
names, so reading it back is never inference, just a lookup. Separately,
one function in this feature (`buscar_intakes_nuevos()`) couldn't be
proven end-to-end against a real inbox — Gmail's API rejects injecting a
synthetic incoming message under the deliberately narrow `gmail.compose`
scope (403, `Insufficient Permission`; that scope can create drafts, not
insert arbitrary mail). Rather than widen the scope just to make one test
more realistic, that gap is disclosed directly in `decisiones.md` and
covered instead by mocked-network tests plus real-credentials coverage of
every other moving part — the same standard applied to every claim this
project makes about what its test suite actually proves.

---

*For the full "why," including things that were tried and reverted, see*
[`decisiones.md`](decisiones.md).
