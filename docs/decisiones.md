# Log de decisiones técnicas

> Registro cronológico de las decisiones de diseño de TrainFitter, fase a fase.
> Sirve para retomar el proyecto y para explicarlo (entrevistas, cliente técnico).

---

## Fase 0 — Scaffold + método del entrenador

**Decisión principal.** Proyecto en **Python puro + SDK de Anthropic**, no low-code.

**Por qué.** El objetivo es de aprendizaje: entender agentes, orquestación y MCP de
**bajo nivel**. Una herramienta low-code (p. ej. n8n, Make) escondería justo lo que
se quiere aprender. Python + SDK oficial da control total sobre prompts, estado y
manejo de errores, y produce un código legible que se puede explicar en una entrevista.

**Otras decisiones de esta fase:**

- **`docs/` en vez de `files/`.** El diagrama del enunciado nombraba `files/`, pero
  todas las tareas y todas las fases posteriores referencian `docs/`. Se usa `docs/`
  para evitar rutas rotas y por ser el nombre convencional.
- **Raíz del repo = `TrainFitter/`.** El enunciado nombraba `piloto-de-planes/` como
  raíz, pero ya se trabajaba dentro de una carpeta `TrainFitter/`. Anidar sería
  redundante; se usa `TrainFitter/` como raíz.
- **Documentación separada del código.** El método del entrenador vive en un `.md`
  legible (`docs/metodo_entrenador.md`) que hará de base de conocimiento consultable
  por los agentes. En la Fase 5 podrá leerse desde Notion en lugar de un archivo local.
- **Prioridad: claridad y comentarios didácticos** sobre optimización prematura, por
  ser proyecto de portfolio/aprendizaje.
- **Humano en el bucle desde el diseño.** La revisión y aprobación humana antes del
  envío es un requisito de arquitectura, no un añadido posterior.

**Pendiente / a revisar en próximas fases:**

- Confirmar el *string* exacto de modelo de Anthropic a usar (Fase 2).
- Decidir formato de salida de los borradores: Markdown vs JSON (Fase 2).
