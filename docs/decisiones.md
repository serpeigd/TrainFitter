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

---

## Fase 0b — Incorporación del material real del entrenador + capa clínica

Tras el scaffold, el entrenador aportó material propio en `AA_files_Training/` (su
rutina real, PDFs de hipertrofia, nutrición, creatina/proteína, sinergias de absorción,
longevidad, hábitos de vida). Decisiones tomadas:

- **Base de conocimiento destilada (`docs/base_conocimiento/`).** Se separa el *criterio*
  (método, nivel "system prompt") del *detalle técnico consultable* (nivel "RAG"). Cinco
  notas: entrenamiento, nutrición, suplementación, sinergias de nutrientes y estilo de
  vida/longevidad, más un índice/manifiesto que mapea cada tema a su PDF fuente. Esta
  estructura lógica se podrá migrar a Notion en la Fase 5 sin cambios.
- **Método enriquecido con contenido real** (números de proteína 0.8/1.6-2.4/1.2-2.2,
  creatina 3-5 g, hipertrofia sarcoplasmática vs miofibrilar, cardio Zona 2 / Zona 4-5,
  sinergias de absorción). Pilares nuevos: **suplementación** y **estilo de vida/longevidad**.
  El documento creció por encima de las 600-900 palabras iniciales al ampliarse el alcance;
  se asume el trade-off a favor de reflejar bien el método.
- **Capa de personalización clínica (nueva).** La admisión capturará alergias,
  enfermedades, embarazo/lactancia, medicación, peso/altura/edad y lesiones; además se
  podrá adjuntar una **analítica en PDF** que *modula* las recomendaciones no clínicas
  (futuro `agents/analytics_parser.py`). Regla dura reforzada: el sistema **no diagnostica
  ni prescribe**; cualquier marcador fuera de rango / patología / embarazo / medicación /
  lesión fuerza `revisión_reforzada`. Documentado en método §7-§8 y arquitectura.
- **Privacidad (decisión importante).** `AA_files_Training/` contiene material personal
  del entrenador (pesos propios, guiones de vlog). Se añade a `.gitignore` y **no se sube**
  al repo público; solo se versiona la ciencia destilada (no personal) en
  `docs/base_conocimiento/`. Reversible si el entrenador prefiere incluirlos.

**Pendiente / a revisar:**

- Contrastar las cifras del material con fuentes científicas actualizadas (ISSN/ACSM,
  metaanálisis) usando búsqueda web en fases posteriores, y citar fuentes en la KB.
- Definir rangos de referencia de la analítica y el mapeo marcador → señal dietética
  (Fase 3, junto al agente de dieta y el validador).
- Destilar el resto de PDFs pendientes (alimentos clave, micronutrientes, hormonas, etc.)
  si aportan al criterio.
