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
  version of the same log (17 decisions, ~2 pages) — update it when a change adds
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
no new ones. Two follow-ups shipped the same day, both requested
directly: the disclosed "Revise client" bloodwork gap is closed not by
re-attaching the original PDF (still not possible) but by not needing to
— `_campos_formulario_desde_perfil()` now also pre-seeds
`analitica_previa`, and `_formulario_ficha_nueva()` falls back to the
already-extracted markers already living inside "Full Profile (JSON)"
when no new PDF is uploaded, with a caption making that explicit; a real
uploaded PDF still takes priority and replaces them outright. Verified
live that a carried-forward out-of-range marker still triggers
`revision_reforzada`, exactly as a freshly-parsed one would. And the
client portal now shows a client their own check-in history
(`_render_historial_checkins()`, pulled out of `_panel_aprobacion()` and
shared with `_vista_portal_cliente()` rather than duplicated) — scoped by
the signed token's own email, never something a client could type in to
see someone else's data.

A **"Clients"** section (4th tab in `ui/app.py`) gives the trainer a
roster of every real client at a glance — `notion_connector.
listar_clientes()` plus `ultimo_checkin_por_cliente()` (one query
against the whole Check-ins database, grouped by email in Python, since
Notion has no native "latest row per group" query), joined by email, with
a client whose most recent rating was Low flagged with ⚠️
(`_etiqueta_atencion()`). `_render_historial_checkins()` also gained a
trend chart (`_render_grafico_tendencia()`, weight and adherence rating
over time via `st.line_chart()`) shown in both places that function
already runs — the trainer's per-client view and the client's own portal
view. A real crash was caught live-testing this (not by the test suite,
which never renders a real page): `st.line_chart()` needs Altair, which
turned out not to actually be present in a real running instance despite
streamlit declaring it as a dependency — opening the portal with 2+
weight check-ins on file raised `ModuleNotFoundError` and broke the whole
page. Fixed two ways: `altair`/`pandas` are now explicit dependencies in
`requirements.txt`, and the chart-rendering code also catches
`ImportError`/`ModuleNotFoundError` defensively, same pattern already
used for reportlab/pypdf/pdfplumber elsewhere in this project.

A real privacy gap in the public demo was found and fixed the same day the
"Clients" tab shipped: neither that tab nor "Revise client" had any gate at
all, so on a deployment with `APP_APPROVAL_PASSWORD` set (the public demo),
anyone could see real clients' emails (Clients) or a client's full profile
including health data (Revise client) just by clicking a tab — no button
click, no side effect needed. `_gate_datos_clientes()` now fronts both
sections with the same `APPROVAL_PASSWORD` already gating the Approve
button, unlocked once per browser session (`st.session_state
["clientes_desbloqueado"]`) rather than re-prompted per view, since browsing
a roster is a repeated look-around action, not one consequential click. On
local dev (password unset) both sections render exactly as before. Verified
live: both sections show only a password prompt until unlocked, a wrong
password is rejected, the correct one unlocks both at once, and a page
reload re-locks them. `_cargar_ficha_para_revisar()`'s lookup now also
re-checks `APPROVAL_PASSWORD` on every "Load" click (not just once per
session, like `_dialogo_aprobacion()`'s per-click check for Approve) —
the session-level unlock alone meant anyone at an already-unlocked
session could pull up any client's full health profile just by knowing
their email; a wrong password now blocks the click before
`buscar_cliente_por_email()` is even called. The gate's own prompt text
also dropped the "same password used to approve a plan" hint (an
unnecessary tell), and the client-facing "this was sent on purpose by
your trainer" reassurance lines were removed from the diet/routine and
portal-link email bodies at the project owner's request — the
guarantee they described is still fully enforced in code, only the
explanatory text in the email itself was cut.

The diet PDF's flat "suggested sources" lists became a real 7-day meal
plan (breakfast/lunch/dinner/snacks), requested directly by the project
owner. New module `agents/planificador_comidas.py` builds it from the same
macro targets `dieta_reglas.py` already computes, drawing foods *only*
from `food_bank.py`'s existing `fuentes_*_para(perfil)` candidate pools —
no second, unchecked path into the raw food banks, so
`validator_agent.py`'s existing allergy cross-check covers the weekly plan
automatically. A 4th food category, `FUENTES_VERDURA` (vegetables/fruit),
was added and wired into that same cross-check. Every food now carries
approximate `macros_100g` (standard reference values) so portions can be
solved from the client's targets — deliberately not gram-perfect, same
"estimate, adjust from real progress" philosophy the diet's own client
message already states. Synergy pairing (non-heme iron + vitamin C in the
same meal, dinner getting the day's largest fat share) is mechanical, not
just a static tip, grounded in
`docs/base_conocimiento/sinergias_nutrientes.md`'s own table. Two
portion-realism bugs — whole-cut meat/fish as a "snack," 500g+ of fruit as
a dinner's main carb — were caught only by generating and reading a real
week, fixed with targeted candidate-pool filters, and locked in as
regression tests. `plan_semanal`'s own food names are the one deliberate
exception to "food names stay canonical English" (nothing safety-critical
string-matches against its prose, unlike `fuentes_*_sugeridas`), so
`food_bank.nombre_mostrado()` runs at description-build time instead of at
render time. The diet PDF gained a styled weekly-plan table (teal header,
alternating rows, kept together across page breaks); `ui/app.py`'s
trainer-facing panel shows the identical plan in a matching expander, so
approving doesn't require opening the PDF first. Both fields are optional
— a draft without them (an older one, a hand-built fixture, or a future
`motor="llm"` response) renders exactly as before, section omitted rather
than crashing. `ENTREGAR_BORRADOR_DIETA_TOOL`'s schema gained the matching
fields, keeping the "two interchangeable engines, one schema" invariant
intact. Verified live in both languages: PDF table renders correctly
(visually inspected), the on-screen panel shows the identical plan, and a
vegan + nut-allergy profile never leaked a restricted food into a real
generated week.

The "Upload a filled intake PDF" section can now email the blank form to
a prospect and check for their reply, both from the panel directly,
requested directly by the project owner. `mcp/gmail_client.py`'s
`enviar_formulario_intake()` is a third, narrow addition to the
`gmail.send` exception (a fixed template with no variable slots at all —
not even a name, since nothing about the prospect is known yet).
`buscar_intakes_nuevos()` gained an optional `remitente` parameter (a
`from:` search qualifier) so the same function serves both `main.py`'s
scheduled whole-inbox scan and the panel's one-prospect "check for a
reply" button — no duplicated search logic. Both new actions are gated
behind `APPROVAL_PASSWORD` (re-checked per click) on any deployment where
it's set: sending is a real email to an address a public-demo visitor
could type in, and checking for a reply pulls back a specific prospect's
personal data just from their email — the same class of exposure
"Revisar cliente" is already gated against. Verified live against the
real Gmail account: the read-only "check" path executed for real (a
made-up address correctly came back "not found"), and the password gate
was confirmed to block "Send blank form" before any network call. The
actual send path is covered by mocked-network tests rather than
triggering a real send during verification, matching this project's bar
for every other real-world side effect.

Both rule engines now actually use most of what the intake form
collects, instead of quietly ignoring several fields — a request that
started as one new diet field and grew, mid-conversation, into a much
larger one after the project owner was asked (and answered) four scoping
questions. Reading `rutina_reglas.py`/`dieta_reglas.py` first surfaced a
real, disclosed gap: `experiencia.nivel` changed only label text, not
actual volume; `minutos_por_sesion`, disliked foods/restrictions, and
every `estilo_de_vida` field were collected and never read anywhere.
**Routine:** volume by level (-1 set for beginners, +1 for advanced on
compound work, grounded in `docs/base_conocimiento/entrenamiento.md`'s
own already-written MEV/MAV/MRV section), a complexity bias toward
machine/dumbbell/bodyweight over barbell lifts for beginners (derived
from each exercise's own equipment, no new field to maintain), a further
-1 set when the client reported high stress or under 6h sleep (stacks
with the level adjustment, both clamped at a shared floor of 2), and
real session-length-aware trimming (`minutos_por_sesion` under 45/30
minutes now actually shortens the session, trimming from the end so the
main compound lifts survive). **Diet:** disliked foods/restrictions now
genuinely exclude (`food_bank.alimentos_no_deseados()`, matched by food
name rather than category, accent-insensitive, explicitly never treated
as a safety concern — no `advertencias_revision_humana`, unlike a real
allergy); a new `nutricion.inquietud_principal` field plus pooled
free-text scanning (goal-in-own-words, nutrition context, free notes)
feeds `food_bank.preferencias_blandas()`, which detects `"reducir_gluten"`
(excludes only the `gluten` tag, deliberately keeping `gluten_trazas`
foods like oats — a real, tested distinction from an actual gluten
allergy) and `"antiinflamatorio"`, plus two structured lifestyle signals
(`"estres_alto_o_sueno_bajo"`, `"trabajo_sedentario"`) that bias (not
exclude) meal selection toward magnesium/fiber-tagged foods via
`planificador_comidas._sesgar_por_preferencias()`. Verified statistically,
not just read: salmon's share of lunch/dinner protein picks went from a
13% baseline to 80% once "antiinflamatorio" was active, averaged across
15 client IDs. The antiinflammatory tip's own wording is diet-type
aware (never names oily fish for a vegetarian/vegan client) — caught by
generating a real vegetarian example client's plan, not by inspection.
Two of the three example clients already had disliked foods on file that
were silently ignored before this fix (`cliente_ejemplo_1`: oily fish;
`cliente_ejemplo_2`: tofu) — regenerating their plans now shows those
foods genuinely gone, a real bug fix on data that already existed.
`cliente_ejemplo_2` also picked up a real `inquietud_principal` value to
demonstrate the new field. 341 tests passing (up from 297), and the full
feature verified live end-to-end through the actual running app.

Four follow-up improvements, requested directly, all shipped the same
day. **`motor="llm"`'s request/response/error-handling code is now
tested** (`tests/test_routine_agent.py`, `tests/test_diet_agent.py`) via
a fake `anthropic` module injected straight into `sys.modules`
(`tests/conftest.py`'s `fake_anthropic` fixture) — no real package
install, no API key, no network, no cost, and it exercises the actual
code path (system prompt, forced tool use, every documented error) the
never-called real API path shares. **CI now measures coverage**
(`pytest --cov`, `--cov-fail-under=90`, scoped to `agents/`+`mcp/` via
`pyproject.toml`'s `[tool.coverage.run]` — `ui/app.py`/`main.py`
deliberately excluded, verified live instead) — the real number is 97%;
reading the report surfaced (and closed) a handful of genuinely untested
branches, most notably two Spanish-language paths in
`validator_agent.py`, the safety gate, that had never been exercised in
that language at all. **A shared brute-force counter** now fronts every
password-gated action in `ui/app.py` (Approve, the Clients/Revise-client
section gate, Revise client's per-lookup check, the intake-email flow) —
5 wrong guesses locks `APPROVAL_PASSWORD` out for 2 minutes regardless of
which gate was tried, verified live including confirming the *correct*
password is also rejected during the lockout. **`docs/highlights.md`**
picked up three new entries for this session's most defensible calls
(the layered privacy fix, personalization verified statistically rather
than eyeballed, and the `fake_anthropic` testing technique) — 15 total
now, up from 11.

Three real bugs caught by live use of the deployed app, all fixed the
same day: the plan email repeated the client's name three times and read
as a wall of text (`gmail_client._construir_cuerpo_email()` was adding
its own greeting on top of one already baked into each of
`mensaje_para_el_cliente`'s two halves — fixed with `_quitar_saludo()`
plus labeled "🏋️ Your routine"/"🍽️ Your diet" sections); one of
`rutina_reglas.py`'s four English message variants read as broken
English (reworded, independent of `docs/metodo_entrenador.md`'s own
"real phrases from the trainer" list, which stays untouched); and
Google Drive's/Gmail's built-in PDF preview can't fill the checklist
form (a viewer limitation, not a bug in the PDF — both language versions
of the plan email now suggest downloading and opening it in a real PDF
app). Separately, the password gate shared one unlock flag across
"Revise client" and "Clients," so proving the password once silently
unlocked both — `_gate_datos_clientes()` now takes a `seccion` argument
so each gets its own flag. And two entry points used to skip the human
review step entirely: "Revise client" let the trainer type up a brand
new client from scratch (now only renders once a real client has been
loaded by email), and confirming an uploaded/found intake PDF used to
generate a plan directly from parsed fields with no one looking at them
first (now pre-fills the same shared form for review, same pattern as
"Revise client"). See `docs/decisiones.md` for the full write-up of all
five.

A new intake field, `experiencia.nivel_compromiso` (`"chill"`/`"normal"`/
`"tryhard"`, default `"normal"` — a no-op, so existing clients are
unaffected), personalizes both engines further: routine volume shifts by
±1 set (stacking with, not replacing, the existing level/stress-sleep
adjustments, same shared floor) and unlocks a small curated pool of more
technically demanding "niche" exercises
(`exercise_bank.py`/`rutina_reglas._candidatos()`); diet calorie
aggressiveness scales via `AJUSTE_COMPROMISO_MULTIPLICADOR` — magnitude
only, capped so tryhard still lands within the method's own "moderate,
never aggressive" deficit range — and unlocks four curated niche foods
(kimchi, natto, farro, algae oil) plus evidence-based supplement tips
(creatine/protein/caffeine, skipping whatever the client already reports
taking in the new `salud.suplementos_actuales` field). That same new
field is cross-checked against `medicacion_habitual` in
`validator_agent.py` — supplements alongside regular medication forces
`revision_reforzada`, grounded in
`docs/base_conocimiento/suplementacion.md`'s own safety rule, since this
project doesn't attempt a real interaction database. 402 tests passing
(up from 383), 97.4% coverage, verified against the real rule-engine
output (set counts, kcal targets, niche-item sampling, supplement-skip
logic all checked directly, not just asserted in tests).

`_render_dashboard_clientes()` adds a fleet-level dashboard (4 KPI
metrics + 2 bar charts: verdict mix, latest-adherence mix), reusing the
exact same `listar_clientes()`/`ultimo_checkin_por_cliente()` results
`_panel_todos_los_clientes()` already fetches — zero new Notion queries.
Verified live against the real workspace. Separately, traced why a
client's checklist PDF forwarded (rather than replied) into the inbox
isn't picked up by the scheduled scan: `buscar_respuestas_adherencia()`'s
`In-Reply-To` check is load-bearing, not incidental — a
blank-but-structurally-intact checklist (the trainer's own sent
original) computes to a real "Low" rating rather than `None` in
`leer_checklist_pdf()`, so dropping that check risks a false adherence
entry. Documented as a real, disclosed gap rather than fixed under time
pressure — see `docs/decisiones.md`.

Four follow-ups shipped the same day, all from actually using the app
for a day: the "Clients"/"Revise client" password-gate split above got
**reverted** back to one shared flag — the project owner's own call,
made *because* "Clients" lost its roster table (see next) and stopped
showing any individual client's data at all, so the split's original
premise stopped applying. "Clients" is now the dashboard *only* — the
per-client roster table (name/email/goal/verdict/last-check-in) is gone,
in favor of Notion's own database view for looking up one record; the
now-dead `_etiqueta_atencion()`/`clients_col_*` code was removed with
it. `crear_borrador()`'s adherence checklist PDF attachment is opt-in
now (`incluir_checklist: bool = False`, a checkbox in the approval panel
default-unchecked) rather than automatic — the client portal is the
intended default way to log adherence now, so mailing a PDF-and-reply
loop by default just duplicated it with more friction. And a real
asymmetry got closed: the routine never had its own standalone PDF the
way the diet always did (only a brief mention in the email body) — new
`generar_pdf_rutina()` mirrors the diet PDF's structure exactly and is
now always attached alongside it. Every session also gained a real,
evidence-grounded `nota_esfuerzo` (reps-in-reserve effort cueing —
compounds 1-2 RIR, isolation 0-1 RIR), backed by two sources actually
read for this change (see `docs/base_conocimiento/entrenamiento.md`'s
new "Effort and proximity to failure" section) and shown in the PDF, the
on-screen review, and threaded into `routine_agent.py`'s system prompt.
The plan email itself is shorter and more scannable — a real bullet list
for attachments instead of a paragraph, plus exactly one 👉 key-point
line per section pulled straight from the plan. 415 tests passing (up
from 402), 97.5% coverage. Not re-verified live in the browser this
round (a port conflict with another concurrent session blocked it) —
disclosed rather than claimed; due for a live spot-check next session.

A real production crash got reported and fixed the same day: a
`TypeError` inside `crear_borrador()` (PDF generation against a real
client's data, redacted by Streamlit Cloud's own privacy behavior) was
propagating past `ui/app.py`'s narrow
`except (GmailClientError, ImportError, ModuleNotFoundError)` clause and
crashing the whole app instead of just failing the draft button. Fixed
by wrapping the PDF/email-body-building step and re-raising anything it
throws as `GmailClientError` — the one type the caller already handles —
locked in with a test that forces `generar_pdf_rutina()` to raise and
confirms it's converted. The exact triggering data was never reproduced
locally despite testing every example client plus a battery of
adversarial profiles; the fix contains the *category* of bug regardless.
Separately, `nutricion.inquietud_principal` became a preset dropdown
(None/Anti-inflammatory/Lower gluten/Other) instead of free text — the
presets store the exact phrase `food_bank.py`'s existing bilingual
keyword matching already recognizes, so no matching-logic changes were
needed, and a new public `food_bank.categoria_inquietud_conocida()`
reverse-maps a previously-saved free-text concern back onto the right
preset (or "Other," text intact) when loading a client for revision.
419 tests passing (up from 415).

A client can now **like a meal from their own portal** and have it bias
(not pin) toward reappearing in their next generated week — scoped with
two clarifying questions first (who picks: client, via the portal; how
"repeat" works: bias future generation, not lock to an exact weekday),
plus a real blocker surfaced mid-investigation and confirmed separately:
the portal never had access to the full weekly plan, only a 2000-char
summary, a deliberate prior design now reversed the same way "Full
Profile (JSON)" was. Each meal `planificador_comidas._construir_comida()`
builds now also carries structured food picks (`tipo_interno`,
`proteina`, `carbohidrato`, `grasa`) alongside its rendered description,
so liking a meal never needs parsing food names back out of prose. Two
new Notion properties: "Weekly Meal Plan (JSON)" (trainer-written,
portal-read) and "Liked Meals (JSON)" (the one property the portal ever
*writes*, kept separate so a client's like can never race with a
trainer's concurrent edit). `_sesgar_por_favoritos()` reuses liked meals
~60% of the time a match is still safe/valid, verified statistically
across 20 client IDs. **Real setup dependency, disclosed**: needs those
two properties added manually to the real Notion "Clients" database
before it actually works — degrades gracefully until then. 430 tests
passing (up from 419).

The "Weekly Meal Plan (JSON)"/"Liked Meals (JSON)" Notion properties the
meal-favoriting feature needed have been added to the real "TrainFitter
Clients" database (via Notion's own schema API, not a manual click), and
the whole loop was verified against the live workspace, not just mocked
tests: a real client record's plan was saved, read back through the same
function the portal calls, a real like was recorded, and regenerating the
diet 15 times reproduced the liked meal ~55% of the time — matching the
~60% design target. Three more dietary-concern dropdown presets shipped
the same day — "Gut health," "More fiber," "More iron (anemia)" — each
reusing a sinergia tag the food bank already carries (no new food data
needed), deliberately excluding any preset without real backing behind it.
439 tests passing (up from 430).

Three roadmap follow-ups shipped together: **exercise-liking**, mirroring
meal-liking exactly for the routine side (each generated exercise now
also carries its slot's `grupo`/`tipo`; new "Weekly Routine (JSON)"/
"Liked Exercises (JSON)" Notion properties, added to the real database;
new `rutina_reglas._sesgar_por_favoritos()` biases exercise selection
toward `perfil["experiencia"]["ejercicios_favoritos"]` ~60% of the time a
match is still safe; verified live against the real "PEPE" test client —
a liked exercise reappeared ~74% of the time across 30 regenerations).
**A weight-trend nudge**: new `agents/adherencia_parser.tendencia_peso()`
flags a real mismatch between logged weight and the goal's expected
direction (only for `perdida_grasa`/`hipertrofia` — goals with no clear
direction are deliberately never checked), shown as a warning banner in
both the trainer's and the client's check-in history views and included
in the trainer notification email; never touches calorie math
automatically. **Safer forward-detection**: `buscar_respuestas_adherencia()`
now accepts a genuine forward from the client (previously rejected
alongside the trainer's own sent copy, which was the only case the
`In-Reply-To` gate actually needed to exclude) by checking the sender
against the authenticated account's own address via `getProfile()`; a
new independent safety net, `checklist_tiene_contenido_real()`, still
catches a blank-but-structurally-intact checklist before it's ever
logged as fabricated adherence data. 471 tests passing (up from 439),
97% coverage.

The supplement-interaction warning is now specific, not just generic: new
`agents/suplementos_interacciones.py` holds a curated (not exhaustive)
table of 12 supplement categories mapped to the medication classes they
have a documented interaction with (vitamin K/anticoagulants, iron/
calcium/magnesium/zinc chelating antibiotics or levothyroxine, high-dose
omega-3/vitamin E/turmeric raising bleeding risk with anticoagulants,
vitamin D/thiazides/digoxin, ashwagandha, St. John's Wort, quercetin —
each verified against real sources: NIH ODS, NCCIH, PubMed/PMC, MDedge,
patient.info). `pares_interaccion_declarados()` adds a specific, named
message on top of `validator_agent.py`'s existing generic "supplements +
medication → flag" check when a recognized pair matches — the generic
check still always fires regardless, so an unrecognized combination is
never silently let through. Creatine/protein powder/beta-alanine/
collagen (this project's actual recommended supplements) are absent from
the table on purpose — no relevant interaction at normal doses. 487 tests
passing (up from 471), 100% coverage on the new module, 97% overall.

The commitment dial's naming/framing changed after a direct correction
mid-implementation: `experiencia.nivel_compromiso`'s values are now
**`basico`/`normal`/`avanzado`/`tryhard`** (was `chill`/`normal`/
`tryhard`, with a `saludable` fourth tier briefly added and renamed
before shipping — see `docs/decisiones.md`), reframed around "how much
detail/guidance do you want" rather than "how demanding," with `tryhard`
explicitly confirmed as the literal ceiling (the most complete
routine+diet this project can currently produce). `avanzado` unlocks the
same creatine/protein/magnesium/omega-3 supplement tips
`dieta_reglas._consejos_suplementos()` already had (caffeine stays
`tryhard`-only); numbers (`AJUSTE_SERIES_POR_COMPROMISO`,
`AJUSTE_COMPROMISO_MULTIPLICADOR`) deliberately stay a no-op for
`avanzado` — detail and physical demand are treated as different axes,
not coupled just because one increased. The field itself moved from
"Training experience" to "Goal" in both intake paths (`ui/app.py`,
`agents/pdf_intake.py`) — it's about how the client wants to pursue the
goal, not their training background. Separately, `food_bank.py`'s
"Pea protein (powder)" became "Protein powder (plant-based)" — generic
per direct request, with the concrete reason (it's the one candidate
that's plant-based rather than animal-derived, unlike whey, which is why
it's a vegan-diet candidate at all) now in a code comment instead of
implied by the name. A real bug the linter caught (not a human review):
adding a second `"avanzado"` key to `ui/app.py`'s flat, cross-field
`OPTION_LABELS` dict silently overwrote `experiencia.nivel`'s own
existing "Advanced" entry — `ruff`'s `F601` flagged the repeated
dictionary key; fixed by sharing one label between both fields. 494
tests passing (up from 487, largely renamed rather than net-new), lint
clean, all six `examples/output_*.json` regenerated.

The commitment dial now genuinely changes the routine and diet, not just
the label — a direct follow-up the same day, after `avanzado` turned out
to still be a functional no-op besides supplement tips.
**Routine**: exercise complexity now stacks with training experience,
not replaces it — `rutina_reglas._preferir_alta_complejidad_primero()`
(the mirror of the existing low-complexity bias) reorders candidates
toward more technically demanding variants for `tryhard`, and `basico`
gets the low-complexity bias regardless of the client's own experience
level. A genuine beginner who picks `tryhard` still gets the simple
version — training experience is a safety signal that outranks a
detail-level preference, confirmed by a dedicated test, not assumed.
**Diet**: `food_bank.py` gained a `"comun"` tag (defaults to `True`,
same pattern as `"nicho"`) marking tofu/tempeh/edamame/seitan/
"Protein powder (plant-based)"/quinoa/seeds as specialty rather than
everyday; new `planificador_comidas._sesgar_por_nivel_compromiso()`
leans `basico`'s actual weekly picks toward the common ones ~85% of the
time a match exists (bias, not exclusion — falls back to the full pool
if nothing common is left). Separately, the mechanical iron+vitamin-C
pairing, the "largest fat portion" dinner note, and
`dieta_reglas._consejos_sinergias()`'s general nutrient-timing tips —
previously shown to every client regardless of level — are now gated to
`avanzado`/`tryhard` via a new `aplicar_sinergias` flag; a client's own
explicit soft preferences (anti-inflammatory, more fiber, etc.) stay
active at every level, since suppressing a direct request isn't the
same thing as toning down automatic "friki" pairing logic. Both
`motor="llm"` prompts were rewritten for the same behavior, keeping
engine parity. 502 tests passing (up from 494), lint clean, all
`examples/output_*.json` regenerated — diffs landed exactly where
expected (client 1's `tryhard` routine changed, its diet didn't;
clients 2/3's `normal` diets changed, their routines didn't).

Same-day follow-up: `avanzado` still read as "normal + supplement tips,"
not a real middle step. Now: routine exercises lean toward dumbbell
("media") complexity via `_preferir_complejidad_media_primero()`, a
real 4-step spectrum with `basico`/`normal`/`tryhard`; diet picks lean
toward `food_bank.py`'s `"comun": False` specialty foods (50% pull,
mirroring `basico`'s 85% pull the other way) — both stop short of the
curated `"nicho"` pool, which stays `tryhard`-exclusive. Caught and
fixed two now-stale `resumen_enfoque` sentences that still claimed
`avanzado` didn't touch training/food choice. 505 tests passing.

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
