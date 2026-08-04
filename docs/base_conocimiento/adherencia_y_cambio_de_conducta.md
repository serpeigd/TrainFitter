# Adherence and Behavior Change

> `docs/metodo_entrenador.md` §1 states the method's priorities explicitly:
> **"1) Adherence · 2) Safety · 3) Progress."** Adherence outranks even progress —
> the best program on paper is worthless if the client doesn't actually do it. This
> note exists to back that #1 priority with real evidence, the same way
> `seguridad_poblaciones_especiales.md` backs the safety rules, and it's the direct
> basis for the automatic adherence check-in loop
> (`agents/pdf_generador.py`, `agents/adherencia_parser.py`, `main.py`).

## Self-monitoring alone helps — pairing it with a human response helps more

A 2022 systematic review and meta-analysis (85 studies, 12,057 participants) compared
physical-activity interventions that combined self-monitoring with an additional
component (goal-setting, counseling, feedback) against self-monitoring alone. The
combined approach increased daily step count by an average of **926 steps/day** more
than self-monitoring alone right after the intervention — but that extra benefit
shrank to **413 steps/day** at follow-up, roughly half. Phone/video counseling was
the single largest driver (~1,129 additional steps/day); a prescribed goal alone
added ~600 steps/day.

**Application in TrainFitter:** the adherence check-in loop was deliberately built as
more than "log it and forget it." `agents/adherencia_parser.py`'s
`valoracion_desde_ratios()` turns a client's reply into a quick Low/Medium/High
signal specifically so the **trainer** — a human — can triage and follow up where it
matters, not so the system can handle it alone. That function's own docstring
already states this design intent independently of this research: *"the trainer's
own read of the free-text notes always matters more than this number."* The evidence
here confirms that instinct was right — self-monitoring's real value shows up in
what a human does with it afterward, and that benefit fades without that follow-up.

## Tracking frequency predicts success better than time spent tracking

A 24-week electronic dietary self-monitoring study (Harvey et al., 2019, *Obesity*,
n=142) found that participants who lost ≥5% of body weight logged into their
food diary significantly more often per day than those who lost less (1.6 vs. 2.4
log-ins/day for the <5% vs. ≥5% weight-loss groups, p<0.001). Time spent per
session dropped from ~23 min/day in month 1 to ~15 min/day by month 6 among those
still tracking — the habit got faster with repetition, not just less frequent.

**Application in TrainFitter:** the checklist PDF (`agents/pdf_generador.py`'s
`generar_pdf_checklist()`) is deliberately minimal — one checkbox per session plus
two short free-text questions, fillable in under a minute. Friction, not
thoroughness, is the thing actively minimized: a client who can complete it quickly
is more likely to actually send it back every time, which the evidence above ties
directly to real outcomes.

## Missing a day doesn't undo the habit

A widely-cited habit-formation study (Lally, van Jaarsveld, Potts & Wardle, 2010,
*European Journal of Social Psychology*, n=96, 84 days of daily self-report) found
the median time for a new habit to reach ~95% automaticity was **66 days**, ranging
18–254 days across individuals — much longer than the popular "21 days" claim.
Critically, **missing a single day of the target behavior did not measurably disrupt
the automaticity curve.**

**Application in TrainFitter:** this matches the tone already baked into the
checklist's own instructions — *"Nothing here is graded: the more honest it is, the
better"* — and into the trainer's documented style more broadly
(`docs/metodo_entrenador.md`). The Low/Medium/High rating is a rough sort/filter
signal for the trainer's attention, not a pass/fail grade handed to the client: one
skipped session or an off week isn't evidence that "adherence has broken down," and
nothing in this system should read it that way.

## Sources consulted (verified, August 2026)
- [Do physical activity interventions combining self-monitoring with other components provide an additional benefit compared with self-monitoring alone? A systematic review and meta-analysis (British Journal of Sports Medicine, 2022)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9685716/)
- [Log Often, Lose More: Electronic Dietary Self-Monitoring for Weight Loss (Obesity, 2019)](https://pubmed.ncbi.nlm.nih.gov/30801989/)
- [How Are Habits Formed: Modelling Habit Formation in the Real World (European Journal of Social Psychology, 2010)](https://onlinelibrary.wiley.com/doi/abs/10.1002/ejsp.674)
