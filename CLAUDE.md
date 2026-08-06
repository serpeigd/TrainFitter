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
to check on demand whether a draft's thread now contains a sent message
(originally needed only `gmail.metadata` — labels/headers only; see below
for why the scope later grew to `gmail.readonly`). `mcp/notion_connector.py`
saves a summarized record
(name/date/goal/level/verdict/summary) to a "Clients" Notion database, and
backfills the client's email onto that record once a Gmail draft is
created for them (`actualizar_email_cliente()`). A second "Check-ins"
Notion database (joined to Clients by email, not a relation property)
logs one row per interaction: `ui/app.py`'s "Check if it was sent" button
calls `verificar_envio()`, and on a confirmed real send, ticks "Email
Sent" on the Clients record (`marcar_email_enviado()`) and adds a
"Plan sent" row to Check-ins (`crear_registro_checkin()`) — trainer-
triggered, not a background job (stateless Streamlit app, no push
infra). `main.py` is a second, genuinely automated trigger: scheduled via
`.github/workflows/inbox_trigger.yml` (GitHub Actions cron, free tier), it
scans the inbox for a filled-in checklist PDF clients send back after
starting their plan (`crear_borrador()` attaches one, alongside a plain
diet PDF — both generated by `agents/pdf_generador.py`, which also reads
the form field values back out of a reply — a fillable PDF form replaced
an earlier plain-text-attachment design; see `docs/decisiones.md`), and
logs an "Adherence check-in" row per reply, deduped against Notion by
Gmail message ID (`existe_checkin_para_mensaje()`) rather than a Gmail
label — see `mcp/gmail_client.py`'s docstring for why. That history is
also readable directly from `ui/app.py` (`notion_connector.historial_checkins()`,
an "Adherence history" expander next to the Gmail controls) — previously
only ever visible by opening Notion itself. This is what pushed
the Gmail scope from `gmail.metadata` to `gmail.readonly` (a real
permission jump, deliberately accepted — see that same docstring).
Notion-save and Gmail-draft-creation are gated behind the
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
never by generation/validation) covers on-screen translation instead. The
free rule engines (`rutina_reglas.py`/`dieta_reglas.py`) are no longer a
template mill: `agents/variacion.py` seeds a `random.Random` from each
client's `id_cliente` so exercise picks and narrative-text phrasing
(`progresion`, `mensaje_para_el_cliente`, `distribucion_comidas`) vary
across different clients while staying perfectly stable if the *same*
client's plan is regenerated — free, no LLM, no new dependency (see
`docs/decisiones.md`). CI (`.github/workflows/ci.yml`) runs the free
rule-engine pipeline + test suite + lint end-to-end on every push — no
secrets needed; `inbox_trigger.yml` (main.py's cron) is separate and does
need secrets, so it isn't part of CI. Gmail re-authorization (both locally
and on Streamlit Cloud/GitHub Actions, for the `gmail.readonly` scope) has
already been done by the project owner. `agents/pdf_intake.py` generates a
fillable **intake** PDF (`examples/blank_intake_form.pdf` is the shipped
blank artifact, mirroring the checklist PDF's own example) and reads a
filled-in one back into a full `perfil_cliente` dict — same fillable-form
safety-critical-data reasoning as the adherence checklist, with the
schema's free-form `lesiones` list deliberately flattened to one
checkbox + one text field (a real, documented simplification; see
`docs/decisiones.md`). `main.py`'s `procesar_intakes_nuevos()` job
(`mcp/gmail_client.py`'s `buscar_intakes_nuevos()`) scans the inbox for a
filled-in intake PDF a prospect emailed back, runs the real pipeline on
it, and logs a heads-up record to Notion's Clients database (deduped by
Gmail message ID via `notion_connector.existe_cliente_para_mensaje()`,
same pattern as the adherence check-ins) — it never creates a Gmail draft
or sends anything, preserving the human-in-the-loop guarantee. `ui/app.py`
also accepts that same filled-in intake PDF directly: a file uploader in
the "New Client" section (`_cargar_ficha_desde_pdf()`) lets the trainer
skip retyping a client's answers and feed the parsed profile into the
exact same review/approve flow as a manually typed intake. One piece of
this feature couldn't be verified against a real inbox end-to-end —
`buscar_intakes_nuevos()`'s Gmail search/parse mechanics are covered by
mocked-network tests instead, since injecting a synthetic incoming
message via `messages().insert()` needs a broader scope than the
project's deliberately narrow `gmail.compose` grants (403 Insufficient
Permission) — a genuine, disclosed testing limitation, not a gap papered
over. A client-facing **portal** (magic link, no password) lets a client
view a summary of their plan and log a check-in directly —
`agents/portal_tokens.py` issues stateless, signed, self-expiring links
(HMAC-SHA256, standard library only, no token database); `ui/app.py`
renders a client-only view instead of the whole trainer panel when a
valid `?portal_token=...` query param is present
(`_vista_portal_cliente()`); the portal's own check-in form reuses
`agents/adherencia_parser.py`'s existing `resumir_adherencia()`/
`valoracion_desde_ratios()` and `notion_connector.crear_registro_checkin()`
rather than a parallel implementation; and `notion_connector.
obtener_registro_cliente()` reads back the same summarized Clients record
`guardar_registro_cliente()` already saves — no new Notion database, no
second copy of the full plan persisted anywhere. Sending the link for
real required widening Gmail's scope to `gmail.send` — the one
deliberate, narrow exception to this project's "never sends
automatically" guarantee, confirmed with the project owner before being
built (not assumed under the broader "build everything" instruction) and
contained to exactly one function
(`gmail_client.enviar_enlace_portal()`), one gated button, and a fixed
one-variable-slot email template; see `docs/decisiones.md` for the full
reasoning. The project owner has since re-authorized Gmail locally
(confirmed via a real, read-only `getProfile()` call — `token.json` now
carries `gmail.send`) and set a real `PORTAL_SECRET_KEY` — verified
end-to-end against the project owner's own real Notion record and a real
sent email. Live-testing it surfaced two check-in-form corrections, both
shipped the same day: the completed/total number inputs switched from
`st.form` to standalone widgets (same reasoning as
`_formulario_ficha_nueva()`) so "completed" can react live and never
exceed "total"; and that cap turned out to only be correct for diet days
(a hard, definitional bound) — routine sessions genuinely can exceed the
plan (an extra session), so that field instead gained an explicit
"I trained more than planned" checkbox that raises its ceiling, rather
than either blocking a real value or silently allowing any number. Both
totals now default to 7 (a full week). A second new function,
`gmail_client.enviar_notificacion_checkin()`, is the only other place
that calls `messages().send()`: the moment a client submits a portal
check-in, it mails a summary plus a rule-based suggested next step (new
`agents/adherencia_parser.py` function `sugerencia_seguimiento()`,
grounded in the same evidence backing this whole loop) to the trainer's
own inbox (`TRAINER_NOTIFICATION_EMAIL`, optional, unset = skipped) —
genuinely automatic, but never a client-facing send, so it doesn't touch
the "never contacts a client automatically" guarantee; best-effort,
wired so its failure can never block the actual Notion check-in from
being saved. The project owner has since pasted the matching secrets
(`GMAIL_TOKEN_JSON`, `PORTAL_SECRET_KEY`, `PORTAL_BASE_URL`,
`NOTION_CHECKINS_DATABASE_ID`) into Streamlit Cloud and confirmed the
public demo works end to end. Two portal check-in UX fixes shipped the
same day, both caught by live-testing against the real Notion record:
"completed" now reacts live to "total" (needed standalone widgets, not
`st.form`), and sessions-completed no longer hard-caps at planned (a
client can genuinely train more than scheduled — an "I trained more than
planned" checkbox raises the ceiling instead; diet days keeps its hard
cap, since that bound is definitional). A Notion connection-error crash
was also found and fixed the same day: every network-touching function
in `mcp/notion_connector.py` now catches `httpx.HTTPError` alongside
`notion_client`'s `APIResponseError` — a transport-level failure (DNS,
timeout, connection reset) was previously propagating uncaught and
crashing the whole Streamlit app.

The Clients Notion database now also stores each client's complete
`perfil_cliente` (`"Full Profile (JSON)"`, chunked across `rich_text`
blocks — `agents/pdf_intake.py`-style form data at Notion's 2000-char
block limit) — a real, deliberate reversal of `obtener_registro_cliente()`'s
original "no second copy of the plan anywhere" design, chosen explicitly
by the project owner (not assumed) once the two options were scoped out.
This powers a new **"Revise client"** section in `ui/app.py`
(`_cargar_ficha_para_revisar()`): the trainer looks up a past client by
email (`notion_connector.buscar_cliente_por_email()`), the exact same
`_formulario_ficha_nueva()` form used for new intakes opens pre-filled
with their saved data (`_campos_formulario_desde_perfil()` pre-seeds
`st.session_state` — the standard Streamlit pattern, no changes to that
form itself), and re-approving calls `actualizar_registro_cliente()`
(`pages.update()`, not `pages.create()`) so the same Clients record gets
corrected in place rather than duplicated — matching the "one master
record per client" principle `notion_connector.py`'s docstring already
states for Email/Email Sent. Verified against the real workspace: a
generated plan round-tripped through save → look-up-by-email exactly
byte for byte, then a revision (changed weight, regenerated) updated the
same page ID rather than creating a new one — then confirmed again
through an actual browser session (load → the form visibly pre-filled
with the loaded client's real weight/goal/level). One real, disclosed
gap: bloodwork PDFs can't be pre-loaded into a revision (`file_uploader`
has no Streamlit API for that), so a revision doesn't re-attach the
original intake's bloodwork.

This also finally gave the trainer's own claim about weight a real
mechanism: `dieta_reglas.py`'s generated message has always said the
plan "gets adjusted based on real weight ... over the first few weeks",
but nothing let that number go anywhere until now. The portal's check-in
form gained an optional weight field (`"Weight (kg)"` on Check-ins),
shown in the trainer's existing adherence-history view and mentioned in
the trainer notification email — reusing all three existing surfaces,
no new ones.

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
| Per-client seeded variety (exercise picks, phrasing) | `agents/variacion.py` |
| Validator | `agents/validator_agent.py` |
| Orchestrator | `agents/orchestrator.py` |
| Exercise/food banks | `agents/exercise_bank.py`, `agents/food_bank.py` |
| Bloodwork parser | `agents/analytics_parser.py` |
| Diet/checklist PDF generation + reading | `agents/pdf_generador.py` |
| Intake PDF generation + reading | `agents/pdf_intake.py` |
| Client portal magic-link tokens (signed, stateless) | `agents/portal_tokens.py` |
| Adherence summary formatting (rating, Notion text, suggested next step) | `agents/adherencia_parser.py` |
| Gmail connector (draft + portal-link send + adherence-reply/new-intake search) | `mcp/gmail_client.py` |
| Notion connector (auto-save + check-ins) | `mcp/notion_connector.py` |
| Automatic inbox trigger (cron; adherence + new intakes) | `main.py`, `.github/workflows/inbox_trigger.yml` |
| Streamlit UI | `ui/app.py` |
| Tests | `tests/` (`conftest.py` fixture + `test_*.py` per module) |
| Example clients/outputs | `examples/` |
| Knowledge base (RAG-level) | `docs/base_conocimiento/*.md` |
| Trainer's method (judgment-level) | `docs/metodo_entrenador.md` |
