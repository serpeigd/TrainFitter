# TrainFitter

**Un asistente que te ayuda a preparar borradores de rutinas y dietas para tus
clientes, replicando tu método y tu criterio — más rápido, sin perder tu sello.**

> *"Enseña a tu cuerpo que quien manda es tu mente."*

---

## ¿Qué problema resuelve?

Cuando entrenas online, el cuello de botella no es entrenar: es el **tiempo** que
inviertes en redactar cada rutina y cada dieta desde cero para cada cliente nuevo.
Horas de trabajo repetitivo que te restan de lo que de verdad importa —el seguimiento
y la relación con la persona—.

TrainFitter toma la **ficha de admisión** de un cliente y genera un **primer borrador**
de su rutina y su dieta siguiendo *tu* metodología documentada: tu forma de progresar
cargas, tu manera de plantear la nutrición flexible, tu tono cercano y pedagógico, y
los mitos que rechazas. Tú te limitas a **revisar, ajustar y aprobar**.

## ¿Qué recibes?

- Un **borrador de rutina** adaptado al nivel, material y disponibilidad del cliente.
- Un **borrador de dieta** flexible, ajustado a sus preferencias y restricciones.
- Un **aviso automático** cuando un caso necesita tu revisión reforzada (por ejemplo,
  una lesión o una condición clínica), para que nada delicado se te escape.

La personalización va más allá del objetivo: la ficha recoge **datos de salud**
(alergias, enfermedades, embarazo, medicación, peso) e incluso permite adjuntar una
**analítica** para afinar la dieta. Todo lo clínico se marca para que lo revises **tú**;
el sistema nunca diagnostica ni prescribe.

## Cómo funciona (en una frase)

Ficha del cliente → borrador de rutina → borrador de dieta → revisión de seguridad
automática → **tú apruebas antes de enviar**.

## Lo más importante: tú tienes la última palabra

TrainFitter **nunca envía nada al cliente por su cuenta**. Todo lo que produce es un
**borrador para tu revisión**. No sustituye tu criterio profesional ni el consejo
médico: cualquier lesión, patología o ajuste clínico se marca siempre para que lo
revises tú personalmente.

---

## Qué incluye ahora mismo

Este repositorio se construye fase a fase, como proyecto de aprendizaje. Ahora mismo:

- El **pipeline completo funciona de verdad**: ficha del cliente → rutina → dieta →
  validación de seguridad → estado listo para tu aprobación. **Gratis, sin ninguna
  clave ni cuenta que configurar** — el motor por defecto es determinista, no depende
  de ningún servicio externo.
- Un **panel visual** (no solo terminal): sube o crea la ficha de un cliente, mira el
  plan generarse, revisa rutina y dieta con tablas y gráficas, y aprueba — todo desde
  el navegador.
- Probado con dos casos de ejemplo: uno sin complicaciones y otro con una lesión y
  una dieta vegetariana, para comprobar que el aviso de revisión reforzada salta
  cuando debe.

## Qué NO incluye todavía

- Conexión con email/Notion para enviar borradores reales (llega en fases posteriores).
- Generación por IA generativa de texto más rico y matizado — hoy el borrador sale de
  reglas deterministas basadas en el método; una capa opcional con IA generativa
  (motor="llm") ya está diseñada para cuando tenga sentido activarla.

## Estructura del repositorio

```
TrainFitter/
├── README.md                        Este documento
├── docs/
│   ├── metodo_entrenador.md         Metodología del entrenador (base de conocimiento)
│   ├── arquitectura.md              Diseño y flujo del sistema
│   └── decisiones.md                Log de decisiones técnicas por fase
├── admission/
│   └── ficha_cliente_template.md    Formulario de admisión
├── agents/                          Rutina, dieta, validador y orquestador
├── ui/                              Panel del entrenador (Streamlit)
├── mcp/                             Conectores MCP: Notion, Gmail (Fase 5)
├── templates/                       Plantillas de email/planes (Fase 5)
├── examples/                        Clientes y salidas de ejemplo
├── requirements.txt                 Dependencias de Python
└── .gitignore
```

## Cómo probarlo

### Opción 1 — Panel visual (recomendado)

```bash
pip install streamlit
streamlit run ui/app.py
```

Se abre en el navegador. Elige un cliente de ejemplo o rellena una ficha nueva, y
verás el plan generarse en vivo.

### Opción 2 — Terminal (sin instalar nada)

El pipeline por defecto es Python estándar puro, sin ninguna clave ni cuenta:

```bash
python agents/run_pipeline_demo.py
```

Esto ejecuta el pipeline completo (rutina → dieta → validador) sobre los dos clientes
de ejemplo y muestra en la terminal el recorrido de estados y el resultado final.

También puedes ejecutar cada pieza por separado:
```bash
python agents/run_routine_demo.py         # solo el agente de rutina
python agents/run_manual_pipeline_demo.py # rutina + dieta + validador, sin orquestador
```

**Opcional — capa con IA generativa real:** los agentes también aceptan
`motor="llm"` para usar la API de Anthropic en vez de las reglas. Si quieres probarlo:
```bash
pip install -r requirements.txt
```
y copia `.env.example` a `.env` con tu `ANTHROPIC_API_KEY`.
