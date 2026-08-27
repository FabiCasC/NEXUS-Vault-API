"""
backend/catalog.py
Dueño real: TÚ (ver 06_TAREAS_TU_KEVIN_LUCIA.docx, tarea YO-B1).

⚠️ ESTO ES UN STUB DE ARRANQUE, NO EL ENTREGABLE FINAL.
Lo dejo aquí solo para que backend/team_formation.py (KEVIN) tenga algo
real contra qué correr mientras "TÚ" construye catalogo_v1.csv definitivo
(15-25 skills, revisadas a mano contra la data). Reemplázalo sin miedo:
team_formation.py solo necesita que exista una función `catalog()` que
devuelva una lista de dicts con las llaves skill_id / nombre / pistas.

Las 18 pistas de abajo salen de texto real que aparece en el dataset
(faculties.csv, institutional_capabilities.csv, research_lines.csv,
institutional_needs.csv) — no están inventadas, pero son un punto de
partida rápido, no un catálogo curado.
"""

from typing import Dict, List, TypedDict


class Skill(TypedDict):
    skill_id: str
    nombre: str
    pistas: List[str]  # palabras/frases en minúscula que deben aparecer en el texto


_CATALOG: List[Skill] = [
    {"skill_id": "SK_PERMANENCIA", "nombre": "Permanencia y deserción estudiantil",
     "pistas": ["permanencia estudiantil", "deserción", "abandono", "riesgo académico"]},
    {"skill_id": "SK_TRAYECTORIAS", "nombre": "Trayectorias educativas",
     "pistas": ["trayectorias educativas", "trayectoria académica"]},
    {"skill_id": "SK_ANALITICA", "nombre": "Analítica y ciencia de datos",
     "pistas": ["analítica", "ciencia de datos", "datos"]},
    {"skill_id": "SK_ML", "nombre": "Aprendizaje automático / IA",
     "pistas": ["aprendizaje automático", "inteligencia artificial", "machine learning"]},
    {"skill_id": "SK_SISTEMAS_INT", "nombre": "Sistemas inteligentes",
     "pistas": ["sistemas inteligentes"]},
    {"skill_id": "SK_IOT", "nombre": "Internet de las cosas",
     "pistas": ["internet de las cosas", "iot"]},
    {"skill_id": "SK_SENALES", "nombre": "Procesamiento de señales / optimización",
     "pistas": ["procesamiento de señales", "optimización"]},
    {"skill_id": "SK_SOFTWARE", "nombre": "Ingeniería de software y arquitecturas",
     "pistas": ["ingeniería de software", "arquitecturas digitales", "arquitectura de software"]},
    {"skill_id": "SK_SALUD_DIGITAL", "nombre": "Salud digital y bienestar",
     "pistas": ["salud digital", "bienestar", "salud pública", "prevención"]},
    {"skill_id": "SK_TRANSF_DIGITAL", "nombre": "Transformación digital",
     "pistas": ["transformación digital", "automatización"]},
    {"skill_id": "SK_PEDAGOGIA", "nombre": "Pedagogía y formación",
     "pistas": ["pedagogía", "formación", "currículo", "competencias"]},
    {"skill_id": "SK_INTERDISC", "nombre": "Investigación interdisciplinaria",
     "pistas": ["interdisciplinar", "articulación interdisciplinaria"]},
    {"skill_id": "SK_INNOVACION", "nombre": "Innovación e investigación aplicada",
     "pistas": ["innovación", "investigación aplicada"]},
    {"skill_id": "SK_AMBIENTE", "nombre": "Sostenibilidad y ambiente",
     "pistas": ["ambiente", "sostenibilidad"]},
    {"skill_id": "SK_REDES", "nombre": "Redes y sistemas distribuidos",
     "pistas": ["redes", "sistemas distribuidos", "cloud"]},
    {"skill_id": "SK_NLP", "nombre": "Procesamiento de lenguaje natural",
     "pistas": ["lenguaje natural", "nlp", "texto"]},
    {"skill_id": "SK_RECOMENDACION", "nombre": "Sistemas de recomendación",
     "pistas": ["recomendación", "recomendador"]},
    {"skill_id": "SK_VISUALIZACION", "nombre": "Visualización y dashboards",
     "pistas": ["visualización", "dashboard", "exploración"]},
]

_BY_ID: Dict[str, Skill] = {s["skill_id"]: s for s in _CATALOG}


def catalog() -> List[Skill]:
    """Lista de skills del catálogo cerrado. Kevin no inventa nombres nuevos:
    team_formation.py solo debe iterar esta lista, nunca hardcodear un skill."""
    return _CATALOG


def skill_by_id(skill_id: str) -> Skill:
    return _BY_ID[skill_id]
