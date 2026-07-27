---
name: nuevo-cliente-prueba
description: Crea un nuevo cliente de ejemplo en examples/ a partir de una descripción en lenguaje natural, siguiendo el esquema JSON de TrainFitter, y ejecuta el pipeline sobre él para ver cómo responde rutina/dieta/validador. Úsala cuando el entrenador quiera probar un caso concreto ("prueba con un cliente que tenga...", "qué pasaría si llega alguien con...").
---

# Crear y probar un cliente de ejemplo nuevo

Genera casos de prueba rápidos para el pipeline de TrainFitter sin que el entrenador
tenga que escribir JSON a mano.

## Proceso

1. **Lee el esquema de referencia** en `examples/cliente_ejemplo_1.json` y
   `examples/cliente_ejemplo_2.json` (y `admission/ficha_cliente_template.md` para el
   contexto de cada campo). No inventes campos nuevos fuera de ese esquema salvo que
   el entrenador lo pida explícitamente — si lo pide, valóralo como un cambio de
   esquema real y actualiza también los agentes que lo consumen.
2. **Traduce la descripción del entrenador a JSON completo**, rellenando con supuestos
   razonables lo que no se especifique (edad, peso, disponibilidad...) — dejarlo
   incompleto rompe los agentes, que asumen el esquema entero.
3. **Nombra el archivo** `examples/cliente_prueba_<descripcion-corta>.json` (no
   sobrescribas `cliente_ejemplo_1.json` / `_2.json`, que son los casos de referencia
   documentados en `docs/decisiones.md`).
4. **Ejecuta el pipeline sobre ese cliente** y muestra el resultado:
   ```python
   import json
   from orchestrator import ejecutar_pipeline

   perfil = json.load(open("examples/cliente_prueba_<nombre>.json", encoding="utf-8"))
   estado = ejecutar_pipeline(perfil)
   print(estado.veredicto)
   ```
   (ejecutar desde `agents/`, o adaptar el import path).
5. **Comenta el resultado en términos del entrenador**, no solo en JSON crudo: qué
   split eligió, qué advertencias saltaron y por qué, si el veredicto tiene sentido
   dado el caso descrito.
6. Si el caso revela un hueco real en el motor de reglas (p. ej. una lesión que no se
   detecta, una restricción alimentaria sin cubrir en `food_bank.py`), no lo arregles
   silenciosamente: dile al entrenador qué falta y pregunta si quiere que se añada.
