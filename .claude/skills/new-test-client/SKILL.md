---
name: new-test-client
description: Create a new example client in examples/ from a natural-language description, following TrainFitter's JSON schema, and run the pipeline on it to see how the routine/diet/validator respond. Use it when the trainer wants to test a specific case ("try a client who has...", "what would happen if someone came in with...").
---

# Create and test a new example client

Generates quick test cases for the TrainFitter pipeline without the trainer having
to write JSON by hand.

## Process

1. **Read the reference schema** in `examples/cliente_ejemplo_1.json` and
   `examples/cliente_ejemplo_2.json` (and `admission/ficha_cliente_template.md` for
   the context behind each field). Don't invent new fields outside that schema unless
   the trainer explicitly asks for it — if they do, treat it as a real schema change
   and update the agents that consume it too.
2. **Translate the trainer's description into a complete JSON profile**, filling in
   reasonable assumptions for anything unspecified (age, weight, availability...) —
   leaving it incomplete breaks the agents, which assume the full schema is present.
3. **Name the file** `examples/cliente_prueba_<short-description>.json` (don't
   overwrite `cliente_ejemplo_1.json` / `_2.json`, which are the reference cases
   documented in `docs/decisiones.md`).
4. **Run the pipeline on that client** and show the result:
   ```python
   import json
   from orchestrator import ejecutar_pipeline

   profile = json.load(open("examples/cliente_prueba_<name>.json", encoding="utf-8"))
   state = ejecutar_pipeline(profile)
   print(state.veredicto)
   ```
   (run from `agents/`, or adapt the import path).
5. **Comment on the result in the trainer's terms**, not just raw JSON: which split
   it picked, which warnings fired and why, whether the verdict makes sense given the
   described case.
6. If the case reveals a real gap in the rule engine (e.g. an injury that isn't
   detected, a dietary restriction not covered in `food_bank.py`), don't fix it
   silently — tell the trainer what's missing and ask if they want it added.
