# Supplementation — Evidence-Based

> Philosophy: few supplements, only the ones with solid backing. Real food comes
> first; a supplement **complements**, it never replaces.

## Creatine (monohydrate)
- **What it does:** raises phosphocreatine reserves → regenerates ATP faster during
  short, intense efforts. Backed benefits: strength, muscle mass, high-intensity
  performance, recovery; a possible cognitive effect (still under study).
- **Dose:** 3-5 g/day (~0.09 g/kg), **a single daily dose**.
- **Timing:** slight edge post-workout or with a meal, but **consistency matters more
  than timing**. Also taken on rest days.
- **Loading phase:** optional (0.3 g/kg/day for 5-7 days saturates in 1 week;
  without loading, you get there in 3-4 weeks just the same). Same result, different
  path.
- **Myths:** doesn't cause baldness (no evidence); the initial +1-2 kg is
  **intramuscular water**, not fat. Keep hydration up.
- **Creapure vs. generic monohydrate:** Creapure = higher certified purity;
  quality generic monohydrate is just as effective and cheaper.

## Protein powder
- **Whey concentrate (70-80%):** affordable, well tolerated. Default choice.
- **Whey isolate (~90%):** less fat/lactose; useful when cutting or with mild
  intolerance.
- **Casein:** slow digestion → before bed.
- **Pea protein:** vegan, rich in lysine; for vegans or intolerances.
- It's a tool to **hit the protein target**, not essential if food already covers it.

## Caffeine
- **What it does:** improves sprint performance, power output, and technical tasks.
- **Dose:** 3-6 mg/kg, taken 45-60 min before training.
- **Note:** individual sensitivity varies a lot; avoid in the hours before bed (it
  affects sleep, which is the foundation of recovery — see
  `estilo_vida_longevidad.md`).

## Beta-alanine
- **What it does:** improves performance in high-intensity efforts lasting 1-4
  minutes (buffers muscle acidity).
- **Dose:** 4-6 g/day, **in split doses** (~1.6 g), for at least 2-4 weeks to notice
  an effect — not a one-off supplement like caffeine.
- **Known side effect:** tingling (paresthesia), harmless; reduced by splitting the
  dose.

## Safety rule
Any supplement with a possible interaction with medication or a condition (e.g.
blood thinners ↔ vitamin K, iron/calcium ↔ certain drugs) → **flag for human
review**, never recommend by default.

## Known interaction pairs (curated, not exhaustive)

`agents/suplementos_interacciones.py` cross-checks a client's declared
supplements against their declared medication for these specific,
well-documented pairs, and adds a named explanation on top of the generic
safety-rule flag above. This is a curated set covering the supplements this
project actually discusses, not an attempt at a real drug-interaction
database — an unrecognized supplement/medication combination still always
gets the generic flag, just without the extra detail.

| Supplement | Interacts with | Mechanism | Certainty |
|---|---|---|---|
| Vitamin K | Anticoagulants (warfarin, acenocoumarol) | Direct mechanistic antagonism — vitamin K is a cofactor for the same clotting factors these drugs block; a sudden change in intake swings the drug's effect | High — the best-documented supplement-drug interaction there is |
| Iron / Calcium / Magnesium / Zinc | Tetracyclines, quinolones | Chelation — these divalent/trivalent minerals form an insoluble complex with the antibiotic in the gut, cutting absorption by up to ~90%; standard guidance is to separate doses by 2-6h | High — well-characterized pharmacokinetics |
| Iron / Calcium / Magnesium | Levothyroxine, bisphosphonates | Same chelation mechanism, reduces absorption of the drug; standard guidance is ≥4h separation for levothyroxine | High |
| Magnesium | Potassium-sparing diuretics (spironolactone, amiloride) | Reduced magnesium excretion can lead to accumulation, especially with impaired kidney function | Moderate — risk is real but conditional on renal function |
| High-dose omega-3 (≥2-3 g/day EPA/DHA) / high-dose vitamin E | Anticoagulants, antiplatelets (warfarin, aspirin, clopidogrel) | Both have a mild antiplatelet/anticoagulant effect on their own that can add to the drug's, raising bleeding risk — case reports exist at high combined doses | Moderate — normal supplemental doses alone are not flagged as risky by NIH ODS, but the combination with an anticoagulant is |
| High-dose vitamin D | Thiazide diuretics, digoxin | Can raise blood calcium; thiazides already reduce calcium excretion (additive hypercalcemia risk), and hypercalcemia raises arrhythmia risk in someone on digoxin | Moderate-high |
| Ashwagandha | Sedatives/benzodiazepines, thyroid hormone, immunosuppressants | Can potentiate sedation, raise thyroid hormone levels, or work against an immunosuppressant's purpose (it has an immune-stimulating effect) | Moderate — smaller evidence base than the pairs above |
| High-dose turmeric/curcumin | Anticoagulants, antiplatelets, chemotherapy | Mild anticoagulant effect at high doses; some chemotherapy protocols interact via CYP metabolism | Moderate |
| St. John's Wort | SSRIs, oral contraceptives, anticoagulants, immunosuppressants | Induces the liver enzyme CYP3A4, speeding up clearance of many drugs and reducing their effectiveness; with SSRIs specifically, risk of serotonin syndrome instead | High — the canonical example that "natural" doesn't mean "no interaction" |
| Quercetin | Quinolones, chemotherapy | Can interfere with antibiotic absorption or chemotherapy drug metabolism | Lower — least-studied pair in this table |

**Not included on purpose:** creatine, protein powder, beta-alanine, and collagen
have no known clinically relevant medication interaction at the doses this
project recommends — see the sections above.

## Sources consulted (verified, July 2026 / August 2026)
- [ISSN Position Stand: Beta-Alanine](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4501114/)
- [NIH ODS — Dietary Supplements for Exercise and Athletic Performance](https://ods.od.nih.gov/factsheets/ExerciseAndAthleticPerformance-HealthProfessional/)
- [NIH ODS — Vitamin K Health Professional Fact Sheet](https://ods.od.nih.gov/factsheets/VitaminK-HealthProfessional/) (vitamin K ↔ anticoagulants)
- [NIH ODS — Magnesium Health Professional Fact Sheet](https://ods.od.nih.gov/factsheets/Magnesium-HealthProfessional/) (magnesium ↔ potassium-sparing diuretics, renal function)
- Mineral chelation with tetracyclines/quinolones: standard clinical pharmacology reference, cross-checked via [Drugs.com interaction reports](https://www.drugs.com/drug-interactions/magnesium-glycinate-with-tetracycline-3906-0-2173-0.html)
- Iron/calcium ↔ levothyroxine timing: [patient.info — Levothyroxine and calcium interaction](https://patient.info/medication-interactions/levothyroxine-and-calcium-interaction), [patient.info — Iron and levothyroxine interaction](https://patient.info/medication-interactions/iron-and-levothyroxine-interaction)
- Vitamin D ↔ thiazides/digoxin: [MDedge — Hypercalcemia From Diuretics and Vitamin D](https://www.mdedge.com/fedprac/article/87711/hypercalcemia-diuretics-and-vitamin-d)
- High-dose omega-3/vitamin E ↔ anticoagulants: [PubMed — Subdural hematoma after a fall in an elderly patient taking high-dose omega-3 fatty acids with warfarin and aspirin](https://pubmed.ncbi.nlm.nih.gov/17192169/)
- St. John's Wort: [NCCIH — St. John's Wort and Depression, In Depth](https://www.nccih.nih.gov/health/st-johns-wort-and-depression-in-depth)
