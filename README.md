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

## Qué NO incluye esta fase (Fase 0)

Este repositorio está en construcción, fase a fase, como proyecto de aprendizaje.
Ahora mismo contiene únicamente:

- La **documentación del método** del entrenador (base de conocimiento).
- La **arquitectura prevista** del sistema.
- El **registro de decisiones** técnicas.

Todavía **no** hay agentes funcionando, ni conexión con email/Notion, ni generación
real de planes. Eso llega en las siguientes fases.

## Estructura del repositorio

```
TrainFitter/
├── README.md                        Este documento
├── docs/
│   ├── metodo_entrenador.md         Metodología del entrenador (base de conocimiento)
│   ├── arquitectura.md              Diseño y flujo del sistema
│   └── decisiones.md                Log de decisiones técnicas por fase
├── admission/
│   └── ficha_cliente_template.md    Formulario de admisión (se completa en Fase 1)
├── agents/                          Agentes de IA (Fase 2+)
├── mcp/                             Conectores MCP: Notion, Gmail (Fase 5)
├── templates/                       Plantillas de email/planes (Fase 5)
├── examples/                        Clientes y salidas de ejemplo (Fase 1+)
├── requirements.txt                 Dependencias de Python
└── .gitignore
```

## Cómo probarlo (modo desarrollo)

1. Crea un entorno virtual e instala dependencias:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Copia `.env.example` a `.env` y añade tu clave de la API de Anthropic:
   ```
   ANTHROPIC_API_KEY=tu-clave-aqui
   ```
3. Ejecuta la demo del agente de rutina sobre un cliente de ejemplo:
   ```bash
   python agents/run_routine_demo.py
   ```
   El borrador se guarda en `examples/output_rutina_1.json`.
