"""
backend/score.py
Dueño real: TÚ (tareas YO-B2 a YO-B6 en 06_TAREAS_TU_KEVIN_LUCIA.docx).

⚠️ STUB DE ARRANQUE — implementa las fórmulas del doc 01_PROPUESTA_NEXUS_VAULT
con matching por palabra clave (lo que YO-B2 pide como primer paso: "si una
pista está en el texto, score 0.8; si no, 0"). Cuando tengas tiempo, súbele
el cosine con sentence-transformers sin tocar las firmas de las funciones
(vectorize, coverage, overlap, J) para que team_formation.py (KEVIN) no
tenga que cambiar nada.

Fórmulas (ver doc 01, sección 5):
    s_vk        -> vectorize()
    c_k(E)      -> coverage()
    D(E)        -> overlap()
    J(E)        -> j_score()
"""

from __future__ import annotations

from itertools import combinations
from typing import Dict, List, Tuple, TypedDict

from backend.catalog import catalog

# Pesos fijos declarados en código (doc 01, sección 5.5).
LAMBDA = 0.15  # costo por tamaño de equipo
MU = 0.25      # penalización por solapamiento (D)
GAMMA = 0.35   # bono si hay hueco real (oportunidad nueva)


class Evidence(TypedDict):
    skill_id: str
    score: float
    fragmento: str


def skill_score(texto: str, skill: dict) -> Tuple[float, str]:
    """YO-B2: para una skill, ¿el texto la evidencia?
    0.8 si alguna pista aparece literalmente en el texto, 0 si no.
    Devuelve también el fragmento (pista encontrada) como evidencia citable.
    """
    texto_low = (texto or "").lower()
    for pista in skill["pistas"]:
        if pista in texto_low:
            return 0.8, pista
    return 0.0, ""


def vectorize(texto: str, use_llm: bool = False) -> Tuple[Dict[str, float], List[Evidence]]:
    """YO-B3: vector s (o t si el texto es una necesidad) de largo K,
    más la lista de evidencias con score > 0 (citas obligatorias, doc 01 §4.7).

    use_llm=True SOLO debe usarse sobre el texto de la consulta (1 llamada
    por búsqueda), NUNCA sobre cada candidato del pool. team_formation.py
    vectoriza ~1300 filas del dataset por consulta (proyectos+tesis+
    investigadores+capacidades+asignaturas) — llamar a un LLM por cada una
    sería carísimo y lentísimo. Por eso el default es False, y candidatos()
    nunca lo activa. Con use_llm=True, y si además USE_LLM=1 + OPENAI_API_KEY
    están configurados (ver backend/llm_skills.py), se suma lo que el LLM
    encuentre —con cita verificada contra el texto— para las skills que el
    matching por palabra clave no detectó, sin pisar nunca una evidencia ya
    encontrada por palabra clave. Si el LLM está apagado o falla, el
    comportamiento es idéntico al de antes (cero regresión).
    """
    vec: Dict[str, float] = {}
    evidencias: List[Evidence] = []
    for skill in catalog():
        score, fragmento = skill_score(texto, skill)
        vec[skill["skill_id"]] = score
        if score > 0:
            evidencias.append({"skill_id": skill["skill_id"], "score": score, "fragmento": fragmento})

    if use_llm and any(v == 0 for v in vec.values()):
        from backend.llm_skills import llm_enabled, label_skills_llm

        if llm_enabled():
            for llm_ev in label_skills_llm(texto):
                skill_id = llm_ev["skill_id"]
                if vec.get(skill_id, 0) > 0:
                    continue  # ya evidenciado por palabra clave, no lo pisamos
                vec[skill_id] = llm_ev["score"]
                evidencias.append(llm_ev)

    return vec, evidencias


def coverage(team_vectors: List[Dict[str, float]]) -> Dict[str, float]:
    """YO-B4: c_k(E) = 1 - producto(1 - s_vk) sobre los miembros del equipo."""
    c: Dict[str, float] = {}
    for skill in catalog():
        k = skill["skill_id"]
        prod = 1.0
        for s_v in team_vectors:
            prod *= (1.0 - s_v.get(k, 0.0))
        c[k] = 1.0 - prod
    return c


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    norm_a = sum(v * v for v in a.values()) ** 0.5
    norm_b = sum(v * v for v in b.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def overlap(team_vectors: List[Dict[str, float]]) -> float:
    """YO-B5: D(E) = suma de cosenos entre cada par de miembros del equipo.
    Dos miembros iguales/clones -> D alto -> penaliza en J."""
    if len(team_vectors) < 2:
        return 0.0
    return sum(_cosine(a, b) for a, b in combinations(team_vectors, 2))


def j_score(
    need_vector: Dict[str, float],
    team_vectors: List[Dict[str, float]],
    hole: bool,
    lambda_=LAMBDA,
    mu=MU,
    gamma=GAMMA,
) -> float:
    """YO-B6: J(E) = sum_k t_k*c_k(E) - lambda*|E| - mu*D(E) + gamma*H(E)."""
    c = coverage(team_vectors)
    cobertura = sum(need_vector.get(k, 0.0) * c_k for k, c_k in c.items())
    tamano = lambda_ * len(team_vectors)
    solapamiento = mu * overlap(team_vectors)
    hueco = gamma * (1.0 if hole else 0.0)
    return cobertura - tamano - solapamiento + hueco


def coverage_score(need_vector: Dict[str, float], team_vectors: List[Dict[str, float]]) -> float:
    """Atajo usado por team_formation para rankear sin pesos de tamaño/hole,
    solo cobertura pura (sum t_k * c_k) — útil para preseleccionar candidatos."""
    c = coverage(team_vectors)
    return sum(need_vector.get(k, 0.0) * c_k for k, c_k in c.items())
