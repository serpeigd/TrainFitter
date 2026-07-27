"""
Panel del entrenador — interfaz Streamlit de TrainFitter.

Convierte el pipeline (hasta ahora solo accesible por CLI) en algo que un
entrenador sin conocimientos técnicos podría usar: elegir o crear una ficha,
generar el plan, ver el recorrido de estados en vivo, revisar rutina + dieta,
y "aprobar" (simulado — el envío real llega con la integración de Gmail).

Cómo ejecutarla (desde la raíz del repo):
    pip install streamlit
    streamlit run ui/app.py
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
EXAMPLES_DIR = REPO_ROOT / "examples"

# Los módulos de agents/ se importan entre sí como paquetes "planos" (import
# knowledge, import routine_agent...), así que necesitan agents/ en sys.path
# igual que cuando se ejecutan sus propios scripts run_*_demo.py.
sys.path.insert(0, str(AGENTS_DIR))

from orchestrator import ejecutar_pipeline  # noqa: E402

st.set_page_config(
    page_title="TrainFitter — Panel del entrenador",
    page_icon="💪",
    layout="wide",
)

ETIQUETAS_ESTADO = {
    "rutina_generada": "Rutina generada",
    "dieta_generada": "Dieta generada",
    "validado": "Validado",
    "pendiente_aprobacion_humana": "Listo para tu aprobación",
    "pendiente_revision_reforzada": "Necesita revisión reforzada",
    "error": "Error al generar el plan",
}

OBJETIVOS = {
    "hipertrofia": "Ganar músculo (hipertrofia)",
    "perdida_grasa": "Perder grasa",
    "recomposicion_corporal": "Recomposición (perder grasa y ganar músculo)",
    "salud_general": "Salud general",
}

MATERIAL_OPCIONES = [
    "maquinas_guiadas", "poleas", "barras_y_discos", "mancuernas", "bancos", "bicicleta_estatica",
]


def _lista_desde_texto(texto: str) -> list[str]:
    """'a, b,, c' -> ['a', 'b', 'c']. Vacío o solo espacios -> []."""
    if not texto:
        return []
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "cliente"


# ---------------------------------------------------------------------------
# Construcción del perfil desde la ficha nueva (formulario)
# ---------------------------------------------------------------------------

def _formulario_ficha_nueva() -> dict | None:
    # NO se usa st.form aquí a propósito: dentro de un form, Streamlit no vuelve
    # a ejecutar el script hasta que se pulsa el botón de envío, así que un
    # checkbox ("¿tiene lesión?") no puede revelar campos condicionales — se
    # comprobó en pruebas manuales que con st.form el campo de "zona de la
    # lesión" nunca llegaba a aparecer. Con widgets sueltos, cada interacción
    # reejecuta el script y la UI puede reaccionar de inmediato.
    st.subheader("1. Datos básicos")
    c1, c2, c3 = st.columns(3)
    nombre = c1.text_input("Nombre completo", key="nombre")
    edad = c2.number_input("Edad", min_value=14, max_value=100, value=30, key="edad")
    sexo = c3.selectbox("Sexo", ["mujer", "hombre"], key="sexo")
    c4, c5 = st.columns(2)
    peso_kg = c4.number_input("Peso actual (kg)", min_value=30.0, max_value=250.0, value=70.0, step=0.5, key="peso")
    altura_cm = c5.number_input("Altura (cm)", min_value=120, max_value=230, value=170, key="altura")

    st.subheader("2. Objetivo")
    principal = st.selectbox("Objetivo principal", list(OBJETIVOS), format_func=lambda k: OBJETIVOS[k], key="objetivo")
    en_sus_palabras = st.text_area("En sus propias palabras (opcional)", key="en_sus_palabras")

    st.subheader("3. Experiencia entrenando")
    c6, c7 = st.columns(2)
    nivel = c6.selectbox("Nivel", ["principiante", "intermedio", "avanzado"], key="nivel")
    anios_entrenando = c7.number_input("Años entrenando (aprox.)", min_value=0.0, max_value=50.0, value=0.5, step=0.5, key="anios")
    detalle_experiencia = st.text_area("Detalle de su experiencia (opcional)", key="detalle_experiencia")

    st.subheader("4. Disponibilidad")
    c8, c9 = st.columns(2)
    dias_por_semana = c8.slider("Días disponibles a la semana", 1, 6, 4, key="dias")
    minutos_por_sesion = c9.number_input("Minutos por sesión", min_value=15, max_value=180, value=60, step=5, key="minutos")
    lugar_entreno = st.selectbox(
        "Dónde entrena",
        ["gimnasio_completo", "gimnasio_pequeno", "casa_con_material", "casa_sin_material"],
        key="lugar_entreno",
    )
    material_disponible = st.multiselect("Material disponible", MATERIAL_OPCIONES, default=MATERIAL_OPCIONES, key="material")

    st.subheader("5. Salud")
    st.caption("Nada de esto le cierra puertas — cuanto más sepamos, mejor podemos cuidar el plan.")
    tiene_lesion = st.checkbox("¿Tiene alguna lesión (actual o antigua)?", key="tiene_lesion")
    zona_lesion = descripcion_lesion = ""
    estado_lesion = "antigua_controlada"
    if tiene_lesion:
        zona_lesion = st.text_input("Zona de la lesión (p. ej. rodilla izquierda)", key="zona_lesion")
        descripcion_lesion = st.text_area("Descripción (qué pasó, si duele actualmente)", key="descripcion_lesion")
        estado_lesion = st.selectbox("Estado", ["antigua_controlada", "activa"], key="estado_lesion")

    c10, c11 = st.columns(2)
    enfermedades_texto = c10.text_input("Enfermedades o condiciones (separadas por coma)", key="enfermedades")
    medicacion_texto = c11.text_input("Medicación habitual (separada por coma)", key="medicacion")

    embarazo = st.checkbox("¿Está embarazada o en periodo de lactancia?", key="embarazo")
    detalle_embarazo = st.text_input("Detalle", key="detalle_embarazo") if embarazo else ""

    c12, c13 = st.columns(2)
    alergias_texto = c12.text_input("Alergias alimentarias (separadas por coma)", key="alergias")
    intolerancias_texto = c13.text_input("Intolerancias alimentarias (separadas por coma)", key="intolerancias")

    analitica_pdf = st.file_uploader("Analítica de sangre (PDF, opcional)", type=["pdf"], key="analitica")

    st.subheader("6. Alimentación")
    tipo_dieta = st.selectbox("Tipo de dieta", ["omnivora", "vegetariana_ovolacto", "vegana"], key="tipo_dieta")
    c14, c15 = st.columns(2)
    restricciones_texto = c14.text_input("Restricciones adicionales (coma)", key="restricciones")
    no_le_gustan_texto = c15.text_input("Alimentos que no le gustan (coma)", key="no_le_gustan")
    comidas_al_dia = st.number_input("Comidas al día preferidas", min_value=2, max_value=6, value=4, key="comidas")
    contexto_nutricion = st.text_area("Contexto (cocina, tiempo, presupuesto...)", key="contexto")

    st.subheader("7. Estilo de vida")
    c16, c17, c18 = st.columns(3)
    horas_sueno = c16.number_input("Horas de sueño promedio", min_value=3.0, max_value=12.0, value=7.0, step=0.5, key="sueno")
    estres = c17.selectbox("Nivel de estrés percibido", ["bajo", "medio", "alto"], key="estres")
    pasos = c18.number_input("Pasos diarios aprox.", min_value=0, max_value=30000, value=6000, step=500, key="pasos")
    tipo_trabajo = st.text_input("Tipo de trabajo / día a día", key="tipo_trabajo")

    st.subheader("8. Notas libres")
    notas_libres = st.text_area("Cualquier otra cosa que quiera contarnos", key="notas_libres")

    enviado = st.button("Crear ficha y generar plan", type="primary", key="enviar_ficha")

    if not enviado:
        return None

    if not nombre.strip():
        st.error("El nombre es obligatorio.")
        return None

    ahora = datetime.now(timezone.utc)
    perfil = {
        "id_cliente": f"cliente_ui_{_slug(nombre)}",
        "fecha_admision": ahora.date().isoformat(),
        "datos_basicos": {
            "nombre": nombre.strip(),
            "edad": int(edad),
            "sexo": sexo,
            "peso_kg": float(peso_kg),
            "altura_cm": float(altura_cm),
        },
        "objetivo": {"principal": principal, "en_sus_palabras": en_sus_palabras.strip()},
        "experiencia": {
            "nivel": nivel,
            "anios_entrenando": float(anios_entrenando),
            "detalle": detalle_experiencia.strip(),
        },
        "disponibilidad": {
            "dias_por_semana": int(dias_por_semana),
            "minutos_por_sesion": int(minutos_por_sesion),
            "lugar_entreno": lugar_entreno,
            "material_disponible": material_disponible,
        },
        "salud": {
            "lesiones": (
                [{
                    "zona": zona_lesion.strip() or "no especificada",
                    "descripcion": descripcion_lesion.strip(),
                    "estado": estado_lesion,
                    "activa_actualmente": estado_lesion == "activa",
                }] if tiene_lesion else []
            ),
            "enfermedades_o_condiciones": _lista_desde_texto(enfermedades_texto),
            "embarazo_o_lactancia": {"aplica": embarazo, "detalle": detalle_embarazo.strip()},
            "medicacion_habitual": _lista_desde_texto(medicacion_texto),
            "alergias_alimentarias": _lista_desde_texto(alergias_texto),
            "intolerancias_alimentarias": _lista_desde_texto(intolerancias_texto),
            "analitica_adjunta": {
                "tiene": analitica_pdf is not None,
                "archivo": analitica_pdf.name if analitica_pdf is not None else None,
                "fecha": ahora.date().isoformat() if analitica_pdf is not None else None,
                "notas": "",
            },
        },
        "nutricion": {
            "tipo_dieta": tipo_dieta,
            "restricciones": _lista_desde_texto(restricciones_texto),
            "alimentos_que_no_le_gustan": _lista_desde_texto(no_le_gustan_texto),
            "comidas_al_dia_preferidas": int(comidas_al_dia),
            "contexto": contexto_nutricion.strip(),
        },
        "estilo_de_vida": {
            "horas_sueno_promedio": float(horas_sueno),
            "nivel_estres_percibido": estres,
            "tipo_trabajo": tipo_trabajo.strip(),
            "pasos_diarios_aprox": int(pasos),
        },
        "notas_libres": notas_libres.strip(),
    }
    return perfil


# ---------------------------------------------------------------------------
# Selección de cliente de ejemplo
# ---------------------------------------------------------------------------

def _selector_cliente_ejemplo() -> dict | None:
    rutas = sorted(EXAMPLES_DIR.glob("cliente_ejemplo_*.json")) + sorted(EXAMPLES_DIR.glob("cliente_prueba_*.json"))
    if not rutas:
        st.info("No hay clientes de ejemplo en examples/.")
        return None

    perfiles = {ruta.name: json.loads(ruta.read_text(encoding="utf-8")) for ruta in rutas}
    etiquetas = {
        nombre: f"{perfil['datos_basicos']['nombre']} ({nombre})" for nombre, perfil in perfiles.items()
    }
    seleccion = st.selectbox("Cliente de ejemplo", list(perfiles), format_func=lambda k: etiquetas[k])
    perfil = perfiles[seleccion]

    with st.expander("Ver ficha completa (JSON)"):
        st.json(perfil)

    return perfil if st.button("Generar plan para este cliente", type="primary") else None


# ---------------------------------------------------------------------------
# Ejecución del pipeline + resultado
# ---------------------------------------------------------------------------

def _ejecutar_y_mostrar(perfil: dict) -> None:
    with st.status("Generando el plan...", expanded=True) as status:
        def _al_transicionar(_cliente_id: str, nuevo_estado: str) -> None:
            status.write(f"✅ {ETIQUETAS_ESTADO.get(nuevo_estado, nuevo_estado)}")

        estado = ejecutar_pipeline(perfil, on_transition=_al_transicionar)
        status.update(
            label="Plan generado" if not estado.error else "Error al generar el plan",
            state="error" if estado.error else "complete",
        )

    if estado.error:
        st.error(f"No se pudo generar el plan: {estado.error}")
        return

    st.divider()
    _mostrar_veredicto(estado.veredicto)

    col_rutina, col_dieta = st.columns(2)
    with col_rutina:
        _mostrar_rutina(estado.borrador_rutina)
    with col_dieta:
        _mostrar_dieta(estado.borrador_dieta)

    st.divider()
    _panel_aprobacion(estado)


def _mostrar_veredicto(veredicto: dict) -> None:
    if veredicto["veredicto"] == "revision_reforzada":
        st.warning("⚠️ **Revisión reforzada** — este caso necesita tu atención antes de aprobar.")
        for motivo in veredicto["motivos"]:
            st.markdown(f"- {motivo}")
    else:
        st.success(
            "✅ **Sin motivos de revisión reforzada.** Aun así, sigue esperando tu aprobación "
            "antes de enviarse — TrainFitter nunca envía nada por su cuenta."
        )


def _mostrar_rutina(rutina: dict) -> None:
    st.markdown("### 🏋️ Rutina")
    st.caption(rutina["resumen_enfoque"])
    st.markdown(
        f"**Split:** {rutina['split'].replace('_', ' ')} · "
        f"**Días/semana:** {rutina['dias_por_semana']} · "
        f"**Duración:** {rutina['duracion_sesion_min']} min"
    )

    for sesion in rutina["sesiones"]:
        with st.expander(sesion["dia"]):
            st.caption(sesion["calentamiento"])
            filas = [
                {
                    "Ejercicio": e["nombre"],
                    "Series": e["series"],
                    "Reps": e["repeticiones"],
                    "Descanso": f"{e['descanso_seg']}s",
                    "Notas": e["notas"],
                }
                for e in sesion["ejercicios"]
            ]
            st.table(filas)
            if sesion.get("cardio_opcional"):
                st.caption(f"Cardio: {sesion['cardio_opcional']}")

    with st.expander("Progresión y mensaje para el cliente"):
        st.markdown(f"**Progresión:** {rutina['progresion']}")
        st.markdown(f"**Para el cliente:** {rutina['mensaje_para_el_cliente']}")

    st.download_button(
        "Descargar rutina (JSON)",
        data=json.dumps(rutina, ensure_ascii=False, indent=2),
        file_name="rutina.json",
        mime="application/json",
    )


def _mostrar_dieta(dieta: dict) -> None:
    st.markdown("### 🍽️ Dieta")
    st.caption(dieta["resumen_enfoque"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Kcal/día", dieta["calorias_objetivo_kcal"])
    m2.metric("Proteína", f"{dieta['macros']['proteina_g']} g")
    m3.metric("Grasa", f"{dieta['macros']['grasa_g']} g")
    m4.metric("Carbohidratos", f"{dieta['macros']['carbohidratos_g']} g")

    st.caption(dieta["distribucion_comidas"])

    c1, c2, c3 = st.columns(3)
    c1.markdown("**Proteína**\n" + "\n".join(f"- {f}" for f in dieta["fuentes_proteina_sugeridas"]))
    c2.markdown("**Carbohidrato**\n" + "\n".join(f"- {f}" for f in dieta["fuentes_carbohidrato_sugeridas"]))
    c3.markdown("**Grasa**\n" + "\n".join(f"- {f}" for f in dieta["fuentes_grasa_sugeridas"]))

    if dieta["consejos_sinergias"]:
        with st.expander("Consejos de sinergias nutricionales"):
            for consejo in dieta["consejos_sinergias"]:
                st.markdown(f"- {consejo}")

    with st.expander("Mensaje para el cliente"):
        st.markdown(dieta["mensaje_para_el_cliente"])

    st.download_button(
        "Descargar dieta (JSON)",
        data=json.dumps(dieta, ensure_ascii=False, indent=2),
        file_name="dieta.json",
        mime="application/json",
    )


def _panel_aprobacion(estado) -> None:
    st.markdown("### Aprobación del entrenador")
    st.caption(
        "Este botón simula tu aprobación dentro de esta demo. El envío real al cliente "
        "(borrador de email) llega con la integración de Gmail — todavía no implementada."
    )
    if st.button("✅ Aprobar y marcar como listo para enviar", type="primary"):
        st.success(
            f"Marcado como aprobado a las {datetime.now().strftime('%H:%M:%S')}. "
            "En una versión conectada a Gmail, esto dejaría un borrador de email esperando tu envío manual."
        )


# ---------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------

st.title("💪 TrainFitter — Panel del entrenador")
st.caption('"Enseña a tu cuerpo que quien manda es tu mente."')
st.markdown(
    "Genera un borrador de rutina y dieta a partir de la ficha de un cliente. "
    "**Todo lo que ves aquí es un borrador**: nada se envía sin tu aprobación."
)

tab_ejemplo, tab_nueva = st.tabs(["📋 Cliente de ejemplo", "📝 Nueva ficha"])

perfil_generado = None
with tab_ejemplo:
    perfil_generado = _selector_cliente_ejemplo()
with tab_nueva:
    perfil_nuevo = _formulario_ficha_nueva()
    if perfil_nuevo is not None:
        perfil_generado = perfil_nuevo

if perfil_generado is not None:
    st.session_state["ultimo_perfil"] = perfil_generado

if "ultimo_perfil" in st.session_state and perfil_generado is not None:
    _ejecutar_y_mostrar(st.session_state["ultimo_perfil"])
