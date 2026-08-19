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
feature never needed. (This guarantee itself later became conditional on the
validator's own verdict, not universal — see #19.)

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

## 10. The one deliberate exception to "never sends automatically" — asked, not assumed

The client portal's magic link only works if it actually reaches the
client's inbox, which meant widening Gmail's scope from `gmail.compose`
to `gmail.send` — a real trade-off against #3 above, this project's
single most load-bearing safety property. Rather than deciding that
unilaterally under a broad "build everything" instruction, it was put to
the project owner directly as a real choice (widen the scope, or route
just this one email through a separate service and leave Gmail
untouched). They chose widening it. What stayed non-negotiable: the blast
radius is contained to exactly one function
(`gmail_client.enviar_enlace_portal()`) that's the only caller of
`messages().send()` anywhere in the codebase — locked in by a test that
asserts `drafts().create()` was specifically *not* called — reachable
from one gated button, sending a fixed template with exactly one variable
slot. Escalating a scope is easy to do quietly; this one is on the
record, with the reasoning, because "the code CAN'T send" (see #3) is a
guarantee worth being honest about the moment it stops being absolute.

## 11. A documented architecture reversal, chosen after seeing the real trade-off — not defaulted into

`notion_connector.py`'s original design deliberately stored only a summary per
client ("no second copy of the plan anywhere"). Letting a trainer look up and
revise a past client's plan needed more than that, so two options were scoped
out and put to the project owner explicitly: keep the lean summary-only design
(the trainer retypes a fresh intake to "revise" a client), or store the
client's complete `perfil_cliente` in Notion so it can be reloaded and edited
in place. The owner chose the bigger option. **Why it matters:** reversing a
documented design decision is exactly the kind of hard-to-reverse
architectural call this project treats as something to ask about, not assume
under a broad "build everything" instruction — the same discipline already
applied to the `gmail.send` scope widening (#10). Verified end-to-end against
the real workspace, not just mocked: a saved profile round-tripped byte-for-byte
through save → look-up-by-email, and a revision updated the same Notion page ID
rather than creating a duplicate.

## 12. Degrade a column, not the page — and a real crash a 257-test suite couldn't see

The client roster (`_panel_todos_los_clientes()`) joins two Notion queries in
Python — `listar_clientes()` (every Clients record) and
`ultimo_checkin_por_cliente()` (each client's latest Check-ins row, grouped by
email, since Notion has no native "latest row per group" query). They're kept
as two independently-failable calls on purpose: if the Check-ins query fails,
the roster still renders from the Clients query alone, just without the
adherence column, instead of the whole tab going blank over one degraded
signal. Separately, live-testing the real app (not the test suite, which
never renders an actual Streamlit page) caught a genuine production bug: the
new trend chart's `st.line_chart()` needs Altair, which `streamlit` declares
as a dependency but which turned out to be missing from a real running
instance — opening the client portal with check-in data raised a bare
`ModuleNotFoundError` and crashed the whole page, not just the chart. Fixed
twice over: `altair`/`pandas` became explicit, declared dependencies in
`requirements.txt` instead of relied on transitively, and the chart code also
catches `ImportError`/`ModuleNotFoundError` defensively, matching this
project's existing "a missing optional library degrades a feature, never
crashes the page" pattern (reportlab/pypdf/pdfplumber). **Why it matters:** a
passing test suite is not the same claim as "verified against the real app" —
this project's own disclosed limitations exist precisely because those two
things get conflated elsewhere.

## 13. A privacy gap the trainer caught, fixed in layers instead of with one patch

Two sections ("Clients," "Revise client") displayed real clients' personal data — emails at minimum, full health details for the latter — on the public demo with zero gate, spotted by the project owner just looking at the shipped feature, not from a security review. The fix isn't one check, it's three, each closing a different failure mode: a session-level password unlock in front of both sections (so a visitor can't browse them at all without it), a *per-click* re-check specifically on "Revise client"'s email lookup (a session already unlocked once shouldn't let anyone pull up any client's data just by typing their email — the session-level gate alone doesn't stop that), and a shared brute-force counter across every password-gated action in the file (5 wrong guesses locks the password out for 2 minutes, regardless of which of the four gates you tried it on). **Why it matters:** treating "add a password" as three separable, individually-verifiable safety properties — instead of one gate you either have or don't — is what defense-in-depth actually looks like in a UI layer, not just a validator. All three were verified live, including forcing the lockout for real (5 wrong attempts, then confirming even the *correct* password was rejected during the cooldown).

## 14. Personalization verified statistically, not eyeballed

Extending the free rule engines to bias meal selection toward a client's stated preference (e.g. "anti-inflammatory") could only be checked one of two ways: generate one example and read it, or measure the actual distribution. The second one caught what the first would have missed — a single generated week can't tell you whether a bias is real or a coincidence of the RNG seed. Ran the planner across 15 different client IDs and counted: salmon's share of lunch/dinner protein picks went from a 13% baseline (uniform random across ~13 candidates) to 80% once the preference was active. **Why it matters:** "the AI is personalized" is a claim that's easy to assert and hard to actually demonstrate — a percentage from 15 independent runs is a materially different kind of evidence than a demo screenshot, and it's the same discipline applied earlier to catching real bugs (portion-realism, the antiinflammatory tip naming a food a vegetarian client could never get) by generating real output and checking it, not just reading the code that produces it.

## 15. Testing the code around a call you'll never actually make

`motor="llm"` is designed but deliberately never exercised against the real, paid Anthropic API (see #1, #6) — which meant, until now, its request-building/response-parsing/error-handling code had zero test coverage of any kind, mocked or otherwise, unlike everything else in this project. Fixed by injecting a fake `anthropic` module directly into `sys.modules` (`tests/conftest.py`'s `fake_anthropic` fixture) before the code's own lazy `import anthropic` runs, rather than installing the real package. That single technique unlocked genuine coverage of every documented failure mode (missing key, timeout, connection error, a malformed response) for free, with no API key, no network call, and no new dependency in CI — closing a real, previously-disclosed gap without weakening the free-only guardrail it was disclosed *because of*. Paired with a real coverage report wired into CI (`pytest --cov`, scoped to `agents/`+`mcp/` — `ui/app.py` is deliberately excluded, since it's verified live instead, not with `pytest`) rather than an unmeasured claim of "well tested": the number is 97%, not a guess.

## 16. Reverting a fix the moment its own premise stops being true

A password-gate split (separate unlock flags for "Revise client" and "Clients") shipped one day; the next day it got reverted back to a single shared flag — not a mistake being corrected, but the direct consequence of a second change made the same session: "Clients" stopped showing any individual client's data at all (roster table removed, replaced by an anonymized fleet dashboard). The split existed to stop one kind of exposure (a roster of emails) from silently unlocking a different, more sensitive kind (full health profiles) with one password entry. Once "Clients" had no exposure left to protect against, that reasoning no longer applied — keeping the split anyway would have been friction defending against a problem that no longer existed. **Why it matters:** treating a fix's own justification as something to keep re-checking, not just a decision made once and left alone, is what stops a codebase from accumulating defensive code nobody remembers the reason for.

## 17. A training claim got a real citation before it shipped, not after

The trainer's method already said "leave reps in reserve," but nothing in the generated plan ever operationalized that into an actual number a client would see per session. Before wiring it in, searched for and read two real sources — a 2021 systematic review/meta-analysis on load and volume autoregulation, and a 2023 trial in trained lifters comparing training to failure against ~2 reps in reserve — added them to the knowledge base with their own citations (matching the project's existing "Sources consulted" convention), and only then turned the finding into a concrete rule (compounds: 1-2 RIR; isolation: 0-1 RIR) shown in the PDF, the on-screen review, and the LLM engine's own prompt. **Why it matters:** "evidence-based" is a claim this project makes throughout its knowledge base — the discipline is searching and reading before writing the rule, not writing the rule and hoping something like it exists somewhere.

## 18. A safety gate had two jobs bundled into one condition — splitting them fixed a false negative without reopening the false positive

`buscar_respuestas_adherencia()` rejected every non-reply message to avoid one specific failure: the trainer's own sent copy of a blank checklist re-appearing in its own inbox search and reading as fabricated "Low adherence." That gate (`In-Reply-To` present) also, as a side effect, rejected every genuine forward from a client — a real, reported false negative. The fix wasn't loosening the gate and hoping for the best; it was noticing the gate was doing two unrelated jobs at once and splitting them: check the *sender's address* against the authenticated account's own (via `getProfile()`) to exclude specifically the trainer's own sent mail, and let an already-existing, independent second check (`checklist_tiene_contenido_real()`) keep catching the actual failure mode — a blank-but-structurally-intact checklist — regardless of whether it arrived as a reply or a forward. **Why it matters:** a single boolean condition that happens to prevent two different bad outcomes is fragile — the moment one outcome needs different handling than the other, the condition has to be decomposed into what it was actually checking, not patched with a special case bolted onto the same test.

## 19. A headline guarantee got scoped to where it actually earns its keep, not dropped

"TrainFitter never sends anything on its own" was the project's single most
repeated claim (#3, #10) — and it stayed absolute for three years' worth of
incremental exceptions (#10's portal link, the trainer-notification email),
each one deliberately narrow. This one is different in kind: requested
directly, a plan the validator itself already cleared (no injury, no allergy,
no flagged bloodwork, nothing) now sends automatically, no draft, no click.
The instinct to treat "never sends automatically" as untouchable and push
back wasn't right here — the validator is the actual safety mechanism, not
the human click that follows it; making a *cleared* plan wait for a click
that would change nothing about whether it's safe is friction dressed up as
caution. What stayed non-negotiable, scoped before writing any code rather
than assumed: a `revision_reforzada` verdict is *never* touched by this —
still a draft, still a human, no exceptions — and the public demo still
requires one password confirmation immediately before an automatic send,
since the OAuth-scope-level protection that used to make a stray send
physically impossible (#3) doesn't apply to a function built to call
`messages().send()` on purpose. **Why it matters:** the honest version of
"we never do X" is "we never do X where it matters" — this project's own
docs (`docs/arquitectura.md`, `README.md`) were rewritten in the same change
that shipped the feature, not left stating a guarantee that stopped being
literally true, because a portfolio project's credibility depends on its
claims matching its code more than on any specific claim being maximally
conservative.

---

*For the full "why," including things that were tried and reverted, see*
[`decisiones.md`](decisiones.md).
