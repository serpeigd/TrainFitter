# Seguridad — Poblaciones especiales y señales de derivación

> Esta nota existe para dar respaldo real a las reglas de seguridad del método
> (`docs/metodo_entrenador.md` §7-§8) y a la lógica de `agents/validator_agent.py`.
> **No convierte al sistema en un servicio clínico**: el objetivo es que el entrenador
> (y el propio sistema) sepan reconocer cuándo algo necesita ojos de un profesional
> antes de seguir, con criterios reconocidos, no solo intuición.

## Embarazo — ejercicio (ACOG)

El Colegio Americano de Ginecología y Obstetricia (ACOG) recomienda, para embarazos
sin complicaciones y con visto bueno médico:
- **150 min/semana de actividad aeróbica moderada** (objetivo progresivo: 20-30
  min/día la mayoría de los días).
- **Entrenamiento de fuerza también recomendado**, no solo cardio — reduce riesgo de
  diabetes gestacional y de trastornos hipertensivos.
- **Intensidad de referencia:** RPE (esfuerzo percibido) 13-15/20 en escala de Borg, o
  el "test del habla" (si puedes mantener una conversación mientras entrenas, la
  intensidad es adecuada).

**Aplicación en TrainFitter:** el sistema NUNCA diseña el ajuste específico de
embarazo — eso es del profesional. Lo que sí hace: reconocer `embarazo_o_lactancia.aplica`
en la ficha y disparar `revisión_reforzada` siempre, sin excepción (ya implementado en
`validator_agent.py`).

## Señales de alarma que exigen derivación médica antes de entrenar (base ACSM)

Con independencia de lo que diga la ficha de admisión, si en el seguimiento el
cliente reporta alguna de estas señales, el entrenador debe parar y derivar, no
"adaptar la rutina":
- Dolor u opresión en el pecho, palpitaciones no explicadas por el esfuerzo.
- Mareo o pérdida de conocimiento durante el ejercicio.
- Falta de aire claramente desproporcionada al esfuerzo.
- Hinchazón repentina, fiebre alta o infección sistémica activa.
- Cualquier dolor articular agudo (no la fatiga muscular normal).

**Aplicación en TrainFitter:** esto es contenido para el **entrenador humano** en el
seguimiento, no algo que el sistema pueda detectar desde una ficha estática — se deja
documentado aquí para que quede recogido en la base de conocimiento y, en el futuro,
se pueda convertir en una pregunta de seguimiento post-entrega del plan.

## Lesión de rodilla (p. ej. tras reconstrucción de LCA) — por qué se restringe la flexión profunda

La lógica de `agents/exercise_bank.py` excluye ejercicios de flexión profunda de
rodilla (sentadilla libre, zancada larga) cuando hay una lesión de rodilla declarada,
y prioriza alternativas de rango controlado (prensa de piernas, extensión de
cuádriceps con carga moderada). Esto no es arbitrario: guías de rehabilitación tras
reconstrucción de LCA recomiendan, en fases tempranas/intermedias, **restringir el
trabajo de carga alta a un rango de flexión de 0-80°** y dosificar el esfuerzo con
RPE 6-8/10 en vez de al fallo, progresando según molestia e hinchazón — no según
sensación subjetiva de "aguantar el ligamento".

**Aplicación en TrainFitter:** esto respalda por qué el motor de reglas adapta en vez
de simplemente prohibir sentadilla — y por qué, aun adaptando bien, el caso **sigue
exigiendo revisión reforzada**: el rango exacto seguro depende de la fase de
rehabilitación de cada persona, algo que ni el sistema ni el entrenador (sin ser su
fisioterapeuta) pueden determinar solo con una ficha.

## Contraindicaciones generales de actividad física (referencia ACSM)

Existen condiciones donde la actividad física está contraindicada hasta resolución
médica: infarto reciente, angina inestable, arritmia cardíaca no controlada,
insuficiencia cardíaca descompensada, embolia pulmonar aguda, infección sistémica
aguda con fiebre. Ninguna de estas se puede descartar desde una ficha de admisión de
fitness — son responsabilidad del cribado médico previo, no de este sistema.

**Aplicación en TrainFitter:** refuerza por qué el método (§8) es tajante en que
`enfermedades_o_condiciones` no declaradas o dudosas se marcan siempre para revisión,
nunca se asume que "seguro que no es nada".

## Fuentes consultadas (verificadas, julio 2026)
- [ACOG — Physical Activity and Exercise During Pregnancy and the Postpartum Period](https://www.acog.org/clinical/clinical-guidance/committee-opinion/articles/2020/04/physical-activity-and-exercise-during-pregnancy-and-the-postpartum-period)
- [ACL Reconstruction Rehabilitation: Clinical Data, Biologic Healing, and Criterion-Based Milestones (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9460090/)
- ACSM Guidelines for Exercise Testing and Prescription — contraindicaciones absolutas/relativas (síntesis de referencia estándar del sector)
