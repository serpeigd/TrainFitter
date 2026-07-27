# Safety — Special Populations and Red Flags

> This note exists to give real backing to the method's safety rules
> (`docs/metodo_entrenador.md` §7-§8) and to the logic in
> `agents/validator_agent.py`. **It doesn't turn the system into a clinical
> service**: the goal is for the trainer (and the system itself) to recognize when
> something needs a professional's eyes before moving forward, based on recognized
> criteria — not just intuition.

## Pregnancy — exercise (ACOG)

The American College of Obstetricians and Gynecologists (ACOG) recommends, for
uncomplicated pregnancies with medical clearance:
- **150 min/week of moderate aerobic activity** (progressive target: 20-30 min/day
  most days).
- **Strength training is also recommended**, not just cardio — it lowers the risk of
  gestational diabetes and hypertensive disorders.
- **Reference intensity:** RPE (perceived exertion) 13-15/20 on the Borg scale, or
  the "talk test" (if you can hold a conversation while training, the intensity is
  appropriate).

**Application in TrainFitter:** the system NEVER designs the specific pregnancy
adjustment — that's the professional's job. What it does do: recognize
`embarazo_o_lactancia.aplica` in the intake and always trigger `revisión_reforzada`,
no exceptions (already implemented in `validator_agent.py`).

## Red flags requiring medical referral before training (ACSM-based)

Regardless of what the intake form says, if the client reports any of these signs
during follow-up, the trainer should stop and refer out — not "adapt the routine":
- Chest pain or tightness, palpitations not explained by the effort level.
- Dizziness or loss of consciousness during exercise.
- Shortness of breath clearly out of proportion to the effort.
- Sudden swelling, high fever, or an active systemic infection.
- Any acute joint pain (not normal muscle fatigue).

**Application in TrainFitter:** this is content for the **human trainer** during
follow-up, not something the system can detect from a static intake form — it's
documented here so it's captured in the knowledge base and could, in the future,
become a post-delivery follow-up question.

## Knee injury (e.g. after ACL reconstruction) — why deep flexion gets restricted

The logic in `agents/exercise_bank.py` excludes deep-knee-flexion exercises (free
squat, long lunges) when a knee injury is declared, and prioritizes controlled-range
alternatives (leg press, moderate-load leg extension). This isn't arbitrary:
post-ACL-reconstruction rehab guidelines recommend, in early/intermediate phases,
**restricting high-load work to a 0-80° flexion range** and dosing effort by
RPE 6-8/10 instead of to failure, progressing based on soreness and swelling — not
on a subjective feeling of "the graft can take it."

**Application in TrainFitter:** this backs up why the rule engine adapts instead of
simply banning squats outright — and why, even when adapted well, the case **still
requires enhanced review**: the exact safe range depends on each person's
rehabilitation phase, which neither the system nor the trainer (unless they're that
person's physical therapist) can determine from an intake form alone.

## General contraindications to physical activity (ACSM reference)

Some conditions make physical activity contraindicated until medically resolved:
recent heart attack, unstable angina, uncontrolled cardiac arrhythmia, decompensated
heart failure, acute pulmonary embolism, acute systemic infection with fever. None of
these can be ruled out from a fitness intake form — that's the responsibility of
prior medical screening, not of this system.

**Application in TrainFitter:** reinforces why the method (§8) is unequivocal that
undeclared or uncertain `enfermedades_o_condiciones` always get flagged for review —
never assumed to be "probably nothing."

## Sources consulted (verified, July 2026)
- [ACOG — Physical Activity and Exercise During Pregnancy and the Postpartum Period](https://www.acog.org/clinical/clinical-guidance/committee-opinion/articles/2020/04/physical-activity-and-exercise-during-pregnancy-and-the-postpartum-period)
- [ACL Reconstruction Rehabilitation: Clinical Data, Biologic Healing, and Criterion-Based Milestones (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9460090/)
- ACSM Guidelines for Exercise Testing and Prescription — absolute/relative contraindications (standard industry reference summary)
