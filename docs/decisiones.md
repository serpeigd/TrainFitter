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

---

## Fase 0c — Aclaraciones del entrenador: criterio evolutivo, ciencia dinámica, modulación activa

Tres respuestas del entrenador a las preguntas abiertas de la Fase 0b, con impacto en
diseño:

- **El método es un punto de partida, no ley fija.** Los valores numéricos (reps,
  g/kg, dosis) son defaults razonables que el entrenador ajusta caso a caso. Se añade
  `docs/metodo_entrenador.md` §0 dejándolo explícito para los agentes.
  - **Por qué:** cada cliente es distinto (genética, respuesta individual) y el
    entrenador no quiere que el sistema trate sus cifras como reglas rígidas.
  - **Implicación a futuro (fuera de alcance ahora):** cuando el entrenador revise y
    edite borradores generados por la IA, esas ediciones son **datos de entrenamiento
    reales** ("borrador IA → corrección del entrenador"). Con suficiente volumen, se
    podrá afinar el criterio del sistema hacia el suyo específico. No se implementa
    aún; queda anotado como dirección futura (posible Fase 8+: registro de ediciones +
    aprendizaje de preferencias).
- **No se fijan citas científicas estáticas en la KB.** El entrenador prefiere que el
  sistema esté siempre actualizado a la evidencia más reciente en vez de "congelar"
  referencias en `docs/base_conocimiento/`.
  - **Por qué:** una nota estática con citas envejece; la ciencia nutricional/deportiva
    se actualiza.
  - **Cómo aplicar:** en fases de agentes (2+), evaluar dar a `routine_agent`/`diet_agent`
    acceso a búsqueda web para contrastar con evidencia reciente en tiempo de generación,
    en vez de depender solo de la KB estática. La KB sigue siendo la base del *criterio y
    estilo* del entrenador, no la fuente de verdad científica.
- **La modulación clínica debe ser ACTIVA, no solo de detección de riesgo.** El
  objetivo final: rutina + dieta + suplementación + hábitos salen cuadrados entre sí a
  partir del perfil completo (analítica, enfermedades, alergias, genética, contexto),
  maximizando sinergias nutricionales y potenciando beneficios — no limitarse a marcar
  lo peligroso.
  - **Por qué:** es el objetivo de producto declarado por el entrenador; "máxima
    personalización" es el valor central de TrainFitter frente a una plantilla genérica.
  - **Cómo aplicar:** `docs/metodo_entrenador.md` §7 actualizado con ejemplos de
    modulación activa (ferritina baja → hierro+vitamina C; vit. D baja → timing con
    grasa; lípidos altos → ajuste de perfil graso/fibra). **La regla de seguridad no
    cambia**: modular activamente no es diagnosticar ni prescribir — el borrador
    modulado sigue disparando `revisión_reforzada` ante cualquier señal clínica, y
    sigue esperando aprobación humana antes de enviarse. El diseño técnico del
    `analytics_parser` y el mapeo marcador→ajuste se abordan en la Fase 3.

**Cómo se trabaja el repo (aclarado a petición del entrenador).** Git es el backbone de
código y versionado durante todo el proyecto, incluidas las Fases 0-4 (desarrollo 100%
local, sin dependencias externas). Notion entra recién en la **Fase 5** como fuente viva
del método (en vez de leer `docs/metodo_entrenador.md` como archivo local) y como base
de datos de estado de clientes/pipelines — pero **no sustituye a git**: el código, los
agentes y el historial de decisiones siguen viviendo y versionándose aquí.

---

## Fase 1 — Ficha de admisión + clientes de ejemplo

- **`admission/ficha_cliente_template.md`** redactado como formulario 100% orientado al
  cliente final: lenguaje llano, sin jerga, con la explicación de por qué se pide cada
  dato de salud (para personalizar y cuidar, nunca para "cerrar puertas"). Incluye las
  preguntas clínicas definidas en la Fase 0b/0c (lesiones, enfermedades, embarazo/
  lactancia, medicación, analítica opcional) integradas de forma natural, no como un
  cuestionario médico frío.
- **Esquema JSON de cliente** (usado por ambos ejemplos y que consumirán los agentes):
  `datos_basicos`, `objetivo`, `experiencia`, `disponibilidad`, `salud` (con
  `lesiones`, `enfermedades_o_condiciones`, `embarazo_o_lactancia`,
  `medicacion_habitual`, alergias/intolerancias, `analitica_adjunta` como placeholder
  para la Fase 3+), `nutricion` y `estilo_de_vida`. Se añade `en_sus_palabras` /
  `detalle` / `contexto` como campos de texto libre en varias secciones: el método
  prioriza entender a la persona, no solo rellenar casillas.
- **`cliente_ejemplo_1.json` (caso normal):** experiencia intermedia, 4 días/semana,
  gimnasio completo, sin lesiones ni condiciones, dieta omnívora sin restricciones
  complejas. Sirve de caso base para validar que el pipeline produce un buen borrador
  sin activar ninguna alerta.
- **`cliente_ejemplo_2.json` (caso complejo, para probar el validador):** combina
  **lesión antigua de rodilla** (LCA, controlada pero con molestias en sentadilla
  profunda — debe activar `revisión_reforzada` y excluir/adaptar ese patrón de
  movimiento) con **vegetarianismo** (relevante para el agente de dieta y las sinergias
  de absorción de proteína/hierro) e intolerancia leve a la lactosa. Se añadió también
  una nota de "cansancio frecuente" sin analítica adjunta, a propósito, como gancho
  narrativo para cuando se implemente el modulador de analítica (Fase 3+): hoy el
  sistema no tiene con qué interpretarlo, así que debe quedar como texto libre sin
  inventar un diagnóstico.
- **`analitica_adjunta`** se deja modelado en el esquema pero **sin uso real todavía**
  (`tiene: false` en ambos ejemplos): implementar el parser real es tarea de Fase 3+,
  no de Fase 1.
