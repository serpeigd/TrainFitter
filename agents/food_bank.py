"""
Banco de alimentos para el motor de reglas de dieta.

Cada fuente de proteína/comida declara qué tipo de dieta la admite y qué
alergias/intolerancias la excluyen, para poder filtrar por perfil sin
necesidad de que un LLM "razone" sobre restricciones alimentarias básicas.
"""

FUENTES_PROTEINA = [
    {"nombre": "Pechuga de pollo", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "Pavo", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "Ternera magra", "tipos_dieta": {"omnivora"}, "etiquetas": set()},
    {"nombre": "Pescado blanco (merluza, lenguado)", "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}},
    {"nombre": "Salmón / pescado azul", "tipos_dieta": {"omnivora"}, "etiquetas": {"pescado"}},
    {"nombre": "Huevos", "tipos_dieta": {"omnivora", "vegetariana_ovolacto"}, "etiquetas": {"huevo"}},
    {"nombre": "Yogur griego / queso fresco batido", "tipos_dieta": {"omnivora", "vegetariana_ovolacto"}, "etiquetas": {"lacteo"}},
    {"nombre": "Lentejas", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"}},
    {"nombre": "Garbanzos", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"legumbre"}},
    {"nombre": "Tofu", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Tempeh", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Edamame", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"soja"}},
    {"nombre": "Seitán", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": {"gluten"}},
    {"nombre": "Proteína de guisante (en polvo)", "tipos_dieta": {"omnivora", "vegetariana_ovolacto", "vegana"}, "etiquetas": set()},
]

FUENTES_CARBOHIDRATO = [
    {"nombre": "Arroz", "etiquetas": set()},
    {"nombre": "Avena", "etiquetas": {"gluten_trazas"}},
    {"nombre": "Patata / boniato", "etiquetas": set()},
    {"nombre": "Pan integral", "etiquetas": {"gluten"}},
    {"nombre": "Pasta integral", "etiquetas": {"gluten"}},
    {"nombre": "Quinoa", "etiquetas": set()},
    {"nombre": "Legumbres (también aportan carbohidrato)", "etiquetas": {"legumbre"}},
    {"nombre": "Fruta variada", "etiquetas": set()},
]

FUENTES_GRASA = [
    {"nombre": "Aceite de oliva virgen extra", "etiquetas": set()},
    {"nombre": "Aguacate", "etiquetas": set()},
    {"nombre": "Frutos secos (nueces, almendras)", "etiquetas": {"frutos_secos"}},
    {"nombre": "Semillas (chía, lino)", "etiquetas": set()},
    {"nombre": "Pescado azul (EPA/DHA)", "etiquetas": {"pescado"}},
]


def etiquetas_excluidas(perfil: dict) -> set[str]:
    """Alergias/intolerancias del perfil traducidas a etiquetas del banco de alimentos."""
    salud = perfil.get("salud", {})
    texto = " ".join(
        salud.get("alergias_alimentarias", []) + salud.get("intolerancias_alimentarias", [])
    ).lower()

    excluidas = set()
    if "lactosa" in texto or "lácteo" in texto or "lacteo" in texto:
        excluidas.add("lacteo")
    if "gluten" in texto:
        excluidas.add("gluten")
        excluidas.add("gluten_trazas")
    if "fruto" in texto and "seco" in texto:
        excluidas.add("frutos_secos")
    if "huevo" in texto:
        excluidas.add("huevo")
    if "soja" in texto:
        excluidas.add("soja")
    if "pescado" in texto or "marisco" in texto:
        excluidas.add("pescado")
    return excluidas


def fuentes_proteina_para(perfil: dict) -> list[str]:
    tipo_dieta = perfil.get("nutricion", {}).get("tipo_dieta", "omnivora")
    excluidas = etiquetas_excluidas(perfil)
    return [
        f["nombre"] for f in FUENTES_PROTEINA
        if tipo_dieta in f["tipos_dieta"] and not (f["etiquetas"] & excluidas)
    ]


def fuentes_carbohidrato_para(perfil: dict) -> list[str]:
    excluidas = etiquetas_excluidas(perfil)
    return [f["nombre"] for f in FUENTES_CARBOHIDRATO if not (f["etiquetas"] & excluidas)]


def fuentes_grasa_para(perfil: dict) -> list[str]:
    excluidas = etiquetas_excluidas(perfil)
    return [f["nombre"] for f in FUENTES_GRASA if not (f["etiquetas"] & excluidas)]
