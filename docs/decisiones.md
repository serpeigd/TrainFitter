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

---

## Fase 2 — Agente de rutina

- **Modelo: `claude-sonnet-5`.** Descartado Opus (razonamiento más caro/profundo del
  que necesita "redactar una rutina siguiendo un método ya documentado") y Haiku (se
  prioriza calidad de personalización — el resultado lo revisa un profesional, pero
  debe llegarle ya bien pensado, no genérico). Sonnet 5 es el punto medio correcto para
  este agente; se reevaluará por agente si algún caso concreto lo justifica.
- **Salida estructurada por *tool use*, no Markdown libre.** Se fuerza al modelo a
  responder rellenando un esquema fijo (`entregar_borrador_rutina`) en vez de pedirle
  JSON en texto y parsearlo. Motivo: el validador (Fase 3) necesita recorrer los
  ejercicios en código para cruzarlos con las lesiones del cliente, y el orquestador
  (Fase 4) necesita estado programático. Convertir JSON → Markdown/HTML bonito para el
  email (Fase 5/6) es un paso trivial; parsear prosa hacia atrás no lo es. Se guarda
  como `.json`, no `.md`.
- **Qué parte de la base de conocimiento recibe el agente.** Además del método
  completo, se le pasan las notas de `entrenamiento.md` y `estilo_vida_longevidad.md`
  (relevantes para diseñar una rutina). Las notas de nutrición/suplementación quedan
  para el agente de dieta (Fase 3) — cada agente recibe solo lo que necesita, no toda
  la KB de golpe.
- **Seguridad en dos capas.** El propio `routine_agent` ya adapta ejercicios ante
  lesiones/condiciones mencionadas en el perfil y rellena `advertencias_revision_humana`
  — pero esto es una primera pasada, no el control formal. La comprobación exhaustiva y
  el veredicto (`aprobado_automático` / `revisión_reforzada`) es responsabilidad del
  **agente validador** (Fase 3), que no se ha implementado todavía.
- **Manejo de errores:** clase `RoutineAgentError` propia; se distingue explícitamente
  API key ausente (mensaje que apunta a `.env.example`), timeout, error de conexión,
  error de la API, y respuesta sin bloque `tool_use` (respuesta malformada).
- **`agents/knowledge.py`** nuevo: helper compartido para leer `docs/metodo_entrenador.md`
  y notas de `docs/base_conocimiento/` por nombre. Lo reutilizarán `diet_agent` y
  `validator_agent` en la Fase 3 para no duplicar lógica de lectura de archivos.
- **No se ejecutó el demo en esta sesión** (no hay `ANTHROPIC_API_KEY` configurada en
  este entorno). Se verificó únicamente que el código compila (`py_compile`) sin errores
  de sintaxis. Pendiente: que el entrenador ejecute `python agents/run_routine_demo.py`
  con su propia clave y confirme que el borrador generado tiene sentido antes de dar por
  buena la Fase 2.

---

## Pivote — Motor de reglas gratuito por defecto (antes de seguir a Fase 3)

El entrenador pidió explícitamente aparcar el requisito de API key y tener una
**versión gratuita totalmente funcional**. Esto cambia el diseño de fondo del
pipeline, no solo la Fase 2:

- **Cada agente generador (`routine_agent`, `diet_agent`) expone un parámetro
  `motor`: `"reglas"` (por defecto) o `"llm"` (opcional).** Ambos devuelven exactamente
  el mismo esquema de salida, así que el validador y el orquestador son agnósticos a
  cuál se usó — no hubo que tocarlos al añadir el motor de reglas.
  - **Por qué no se descarta el motor LLM:** el objetivo del proyecto sigue siendo
    aprender a montar agentes con el SDK de Anthropic. El código de tool use de la
    Fase 2 se conserva íntegro (renombrado a función privada `_generar_borrador_*_llm`)
    y queda listo para activarse el día que haya API key, sin rediseñar nada.
  - **Import perezoso de `anthropic`:** se mueve `import anthropic` de nivel de módulo
    a dentro de la función `_llm`, así que quien solo usa `motor="reglas"` ni siquiera
    necesita tener el paquete instalado. El pipeline por defecto es **100% Python
    estándar, cero dependencias de terceros**.
- **Motor de reglas de rutina (`agents/exercise_bank.py` + `agents/rutina_reglas.py`):**
  banco de ~40 ejercicios reales (inspirados en la rutina propia del entrenador de la
  Fase 0b) etiquetados por grupo muscular, material necesario y contraindicaciones
  (rodilla/hombro/lumbar). El motor elige split según días/semana (full body ≤3,
  torso-pierna =4, push/pull/legs ≥5), selecciona ejercicios que el cliente puede hacer
  con su material, aplica los rangos del método (básico 5-8, aislamiento 10-15) y
  **excluye/sustituye ejercicios contraindicados por lesiones declaradas**, dejando el
  motivo en `advertencias_revision_humana`.
- **Detección de lesiones por texto libre (`agents/perfil_utils.py`):** función
  `tags_lesiones()` que busca palabras clave (rodilla/hombro/lumbar) en `zona` +
  `descripcion` de la ficha. Es una simplificación deliberada (matching de substring,
  no NLP real) documentada como limitación conocida — suficiente para el MVP y para
  que el validador pueda re-derivarla de forma independiente.
- **Verificado con ejecución real** (ya no hace falta esperar a que el entrenador
  configure una clave): `python agents/run_routine_demo.py` sobre ambos clientes de
  ejemplo confirma que la lesión de rodilla de `cliente_002` excluye "Sentadilla con
  barra" y la sustituye por "Prensa de piernas" / "Curl femoral" / "Puente de glúteo",
  con nota explicativa en cada ejercicio adaptado.

---

## Fase 3 — Agente de dieta + agente validador

- **Motor de reglas de dieta (`agents/food_bank.py` + `agents/dieta_reglas.py`):**
  calorías vía Mifflin-St Jeor (BMR) × factor de actividad derivado de
  días de entreno/semana y pasos diarios, con ajuste por objetivo (hipertrofia +10%,
  recomposición -5%, pérdida de grasa -18%, salud general 0%) — todo tomado de
  `docs/base_conocimiento/nutricion.md`. Proteína por objetivo usando el punto medio
  del rango del método (p.ej. hipertrofia → 2.0 g/kg). Banco de alimentos filtrado por
  tipo de dieta (omnívora/vegetariana/vegana) y por alergias/intolerancias declaradas
  (excluye lácteos, gluten, frutos secos, huevo, soja, pescado según corresponda).
  Añade consejos de `sinergias_nutrientes.md` cuando el perfil los justifica (hierro +
  vitamina C y separar café/té del hierro en dietas vegetarianas/veganas).
- **`agents/diet_agent.py`** sigue el mismo patrón dual-motor que `routine_agent.py`.
  El system prompt del motor LLM deja explícito que **no debe ajustar nada por
  patologías/embarazo/medicación por su cuenta**: eso se marca en
  `advertencias_revision_humana`, nunca se resuelve solo (método §7-§8).
- **`agents/validator_agent.py` es intencionadamente SIEMPRE reglas**, nunca LLM — a
  diferencia de rutina/dieta, no es una elección temporal por falta de API key. Un
  gate de seguridad debe ser determinista y auditable: la misma entrada debe dar
  siempre el mismo veredicto y cualquiera debe poder leer el código y saber qué se
  comprueba exactamente.
- **Defensa en profundidad, no solo agregación.** El validador no confía en que
  rutina/dieta ya se auto-marcaron bien: vuelve a leer el perfil crudo de forma
  independiente, Y ADEMÁS cruza cada ejercicio concreto del borrador contra
  `exercise_bank` (¿algún ejercicio contraindicado se coló?) y cada alimento sugerido
  contra `food_bank` (¿alguna sugerencia choca con una alergia declarada?). Esto
  importa sobre todo de cara al futuro motor LLM: si algún día se equivoca al
  autoevaluarse, el validador lo pilla igualmente.
- **Alergias añadidas a los disparadores de `revisión_reforzada`.** El método §8
  original no las listaba explícitamente (solo lesiones/patologías/embarazo/
  medicación); se añaden porque una alergia mal gestionada puede ser grave — extensión
  razonable, documentada aquí para que quede claro que es una decisión nueva.
- **Probado con ejecución real** sobre ambos clientes
  (`python agents/run_manual_pipeline_demo.py`): `cliente_001` →
  `aprobado_automatico`; `cliente_002` → `revision_reforzada` con 3 motivos concretos
  (lesión de rodilla, advertencia de rutina asociada, y una nota sobre "cansancio
  frecuente" sin analítica adjunta que queda marcada para pedir en el seguimiento en
  vez de inventar una interpretación clínica).

---

## Fase 4 — Orquestador

- **Estado explícito vía `PipelineState` (dataclass), no variables sueltas.** El
  estado del pipeline es un dato de primera clase — se puede loguear, inspeccionar o
  (en la Fase 5+) persistir en Notion sin cambiar la lógica del orquestador. La lista
  `ESTADOS` en `agents/orchestrator.py` es, literalmente, el diagrama de flujo.
- **Transiciones:** `ficha_recibida → rutina_generada → dieta_generada → validado →
  (pendiente_aprobacion_humana | pendiente_revision_reforzada)`, con una rama `error`
  si algún agente lanza excepción. Cada transición se loguea con marca de tiempo.
- **Ambas ramas de éxito exigen aprobación humana** — `aprobado_automatico` solo
  significa "sin motivos de revisión reforzada", nunca "envíalo sin mirar". Esto es
  deliberado: el principio de humano-en-el-bucle no depende del veredicto del
  validador, es una propiedad del propio orquestador.
- **Probado con ejecución real de punta a punta**
  (`python agents/run_pipeline_demo.py`) sobre ambos clientes: se ve el recorrido de
  estados completo en terminal y el resultado final coincide con lo verificado en la
  Fase 3.

---

## Investigación externa — ampliación de la base de conocimiento con fuentes verificadas

El entrenador pidió reforzar la KB más allá de su material propio, buscando evidencia
externa (estudios, posicionamientos de sociedades científicas, divulgación
science-based tipo Jeff Nippard) y creando skills para que este proceso sea repetible.

- **Qué se investigó y qué cambió** (ver `docs/base_conocimiento/*` → sección "Fuentes
  consultadas" de cada nota para los enlaces):
  - `entrenamiento.md`: se añade el marco de **landmarks de volumen (MEV/MAV/MRV)** de
    Renaissance Periodization/Mike Israetel, con nota de que el "10 series/semana" del
    método original es un punto de entrada razonable, no el marco completo. Se añade
    guía de deload y de por qué la alta frecuencia no es para todos.
  - `nutricion.md`: la tabla de proteína se refina con el meta-análisis de **Morton et
    al. 2018** (satura ~1.6 g/kg/día, techo razonable ~2.2) y el **position stand de la
    ISSN 2017** (1.4-2.0 g/kg/día suficiente para la mayoría). Se añade el dato real de
    **fibra** (USDA: 22-28 g/día mujeres, 28-34 g/día hombres) y el **ritmo de pérdida
    de grasa sostenible** (0.5-1% del peso corporal/semana), sustituyendo la
    descripción cualitativa vaga por un rango accionable.
  - `suplementacion.md`: se añaden **cafeína** (3-6 mg/kg, 45-60 min pre-entreno) y
    **beta-alanina** (4-6 g/día repartidos, 2-4 semanas para notar efecto), ambos con
    respaldo ISSN — el método original solo cubría creatina y proteína.
  - `estilo_vida_longevidad.md`: cita de referencia (Sleep Foundation) para el rango de
    sueño, sin cambiar el rango ya correcto del método.
  - **Nota nueva: `seguridad_poblaciones_especiales.md`.** Directamente ligada a la
    capa clínica: guía de ejercicio en embarazo (ACOG — 150 min/semana, RPE 13-15 o
    test del habla), señales de alarma que exigen derivación médica inmediata (base
    ACSM), y el respaldo real de por qué se restringe la flexión profunda de rodilla
    tras lesión (guías de rehabilitación de LCA: rango ~0-80°, dosificar por RPE 6-8/10
    en vez de al fallo). Esta nota existe para que las reglas de `validator_agent.py`
    y `exercise_bank.py` no sean solo "sentido común programado", sino que tengan
    detrás una razón citable.
- **Código actualizado para reflejar la investigación, no solo la documentación:**
  - `agents/dieta_reglas.py`: `PROTEINA_G_POR_KG["salud_general"]` sube de 1.2 a **1.4**
    (rango ISSN para personas que entrenan, no sedentarias — el valor anterior venía
    de una lectura de "mantenimiento" más pensada para alguien sedentario).
  - `agents/rutina_reglas.py`: las notas que el motor genera para ejercicios adaptados
    por lesión de rodilla ahora referencian el criterio real (rango controlado, esfuerzo
    moderado tipo RPE) en vez de un texto genérico de "controla el rango de movimiento".
  - `agents/routine_agent.py` y `agents/diet_agent.py`: el motor LLM (cuando se active)
    recibe también `seguridad_poblaciones_especiales.md` como parte de su contexto.
- **Reconciliación con la decisión de la Fase 0c** ("no hace falta poner citas, que
  esto se actualice solo"): esa decisión hablaba de no depender de citas estáticas
  como mecanismo *permanente* de frescura — no de nunca citar nada. Investigar y citar
  fuentes reales en una pasada de trabajo concreta es buena práctica y no sustituye la
  idea de que, en el futuro, el motor LLM siga contrastando con evidencia reciente en
  tiempo de generación (eso sigue siendo el plan a más largo plazo).
- **Skills de proyecto creadas** (`.claude/skills/`):
  - `actualizar-base-conocimiento`: codifica el proceso de esta misma investigación
    (dónde buscar, cómo citar, cuándo ampliar nota existente vs. crear una nueva, cómo
    sincronizar código y documentación, qué registrar en este log) para que sea
    repetible sin tener que redescubrirlo cada vez.
  - `nuevo-cliente-prueba`: permite generar y probar un cliente de ejemplo ad-hoc a
    partir de una descripción en lenguaje natural, sin que el entrenador tenga que
    escribir JSON a mano — útil para explorar casos límite del validador.

---

## Fase 5-lite — Panel del entrenador (UI con Streamlit)

Ante la elección explícita del entrenador entre seguir con Notion/Gmail reales, seguir
ampliando la KB, o construir una interfaz, se optó por la **UI**: el pipeline ya
funciona de punta a punta pero solo es usable por alguien cómodo con una terminal.

- **Streamlit sobre alternativas.** Python puro (coherente con el resto del proyecto,
  sin añadir un stack de frontend separado), suficiente para un panel interno, y
  permite iterar rápido. Se descartó FastAPI+HTML a propósito por ahora: más control,
  pero más superficie para un paso que es "hacerlo demostrable", no "producto final".
- **Refactor de `agents/orchestrator.py`: `on_transition` como callback en vez de
  `print()` dentro de `transicionar()`.** El logging por consola era una decisión de
  la Fase 4 que acoplaba el orquestador a la terminal. Se extrae a un callback
  opcional (por defecto sigue logueando a consola, así que `run_pipeline_demo.py` no
  cambia de comportamiento) para que la UI pueda pintar el mismo recorrido de estados
  en pantalla. Es el tipo de cambio que conviene hacer *cuando aparece el segundo
  consumidor* del dato, no antes — hacerlo en la Fase 4 hubiera sido especular sobre
  una UI que todavía no existía.
- **`ui/app.py`:** dos formas de generar un plan — elegir un cliente de `examples/`,
  o rellenar un formulario nuevo que espeja la ficha de admisión y produce el mismo
  JSON que consumen los agentes. Resultado: veredicto, rutina por sesión (tabla de
  ejercicios), dieta (macros + fuentes + sinergias), descargas en JSON, y un botón de
  aprobación **explícitamente marcado como simulado** (el envío real es Fase 5+ con
  Gmail) — coherente con que el sistema nunca envía nada por su cuenta.
- **Bug real encontrado y corregido durante las pruebas: `st.form` bloqueaba los
  campos condicionales.** El diseño inicial metía el checkbox "¿tiene lesión?" y los
  campos de zona/descripción dentro de un único `st.form`. Al probarlo en el
  navegador (ver más abajo), marcar el checkbox nunca revelaba los campos siguientes:
  Streamlit no reejecuta el script dentro de un formulario hasta el envío, así que la
  UI no podía reaccionar a mitad de rellenar el formulario. Se solucionó quitando
  `st.form` y usando widgets sueltos con `key` explícita + un botón normal al final.
  Es exactamente el tipo de bug que solo aparece probando de verdad, no leyendo el
  código — motivo por el que se dedicó tiempo a verificarlo en un navegador real en
  vez de darlo por bueno tras compilar.
- **Verificación real, con límites honestos.** Se lanzó `streamlit run ui/app.py` vía
  `preview_start` (con `.claude/launch.json` nuevo) y se confirmó en el navegador: el
  camino "feliz" completo (cliente de ejemplo → plan generado → rutina con tablas de
  ejercicios → dieta con métricas → veredicto de aprobación → descargas) renderiza
  correctamente de principio a fin. El entorno de pruebas de este chat no tiene el
  panel de navegador visible (`screenshot`/`read_page` fallan intermitentemente sin
  compositing activo), lo que dificultó automatizar el desplegable de selección de
  cliente y la escritura sintética en el formulario para probar específicamente el
  caso con lesión (`revisión_reforzada`) de principio a fin en la UI. Esa rama de
  código (`st.warning` + lista de motivos) es estructuralmente idéntica a la rama de
  éxito ya verificada, y la lógica que decide el veredicto (`validator_agent.py`) está
  probada exhaustivamente por CLI — pero queda anotado aquí como verificación
  pendiente de confirmar visualmente por el entrenador, no como algo dado por sentado
  sin más.
- **Dependencias nuevas:** `streamlit>=1.38.0` en `requirements.txt`, marcado como
  opcional (el pipeline en modo "reglas" sigue sin necesitar nada). `.streamlit/config.toml`
  con tema propio (verde azulado, `#0F766E`). `.streamlit/secrets.toml` añadido al
  `.gitignore` por si en el futuro se necesitan credenciales ahí.
- **Instalación de Streamlit en este entorno tuvo fricción** (errores intermitentes de
  `pip` al escribir los `.exe` de consola en `C:\Python312\Scripts`, aparentemente por
  bloqueo de archivo transitorio). Se resolvió reintentando la instalación; el módulo
  quedó importable y funcional. Si el entrenador ve el mismo error al instalar, no es
  un problema del proyecto — reintentar `pip install streamlit` suele bastar.

**Pendiente para cuando el entrenador lo pruebe él mismo:**
- Confirmar visualmente el caso de revisión reforzada en la UI (`streamlit run ui/app.py`,
  pestaña "Cliente de ejemplo" → Javier Ruiz, o pestaña "Nueva ficha" marcando una lesión).
- Decidir si la UI necesita algo más antes de considerarla "lista para enseñar a un
  cliente potencial" (¿logo?, ¿nombre de dominio si se despliega?, etc. — fuera de
  alcance de esta fase).
