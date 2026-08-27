"""
backend/team_formation.py
Dueño: KEVIN.

Arma la "canasta" (equipo mínimo real) que mejor cubre una necesidad
institucional: 1 antecedente (PROJECT o THESIS) + 1 investigador (RESEARCHER)
+ 1 capacidad institucional (CAPABILITY) + 1 asignatura (SUBJECT). Ver
01_PROPUESTA_NEXUS_VAULT.docx secciones 3-6 para el porqué de cada pieza.

Cadena de responsabilidad (KE-1 a KE-6):
    KE-1/KE-2  -> backend.load_core.load_core()      (KEVIN, ya resuelto)
    (capacidades/asignaturas) -> backend.load_extra.load_extra()  (TÚ, stub aquí)
    KE-3       -> candidatos()
    KE-4       -> armar_canasta()  (usa backend.score.j_score, de TÚ)
    KE-5       -> hole()
    KE-6       -> form_team()

Contrato de salida de form_team(): ver el docstring de esa función. Es lo
que Lucía importa en el frontend — si cambias las llaves del dict, avísale
antes de la reunión de las 13:00 (o mejor, no las cambies).
"""

from __future__ import annotations

from functools import lru_cache
from itertools import product
from typing import Dict, List, Optional, Tuple

from backend.load_core import CoreData, load_core
from backend.load_extra import ExtraData, load_extra
from backend import score as score_mod

# Umbral de cobertura mínima para publicar una propuesta (doc 01 §5.5: τ≈0.6).
TAU = 0.6

# Cuántos candidatos por categoría se preseleccionan antes de buscar la
# mejor combinación (doc 01 dice "candidato; todavía no es el equipo").
TOP_N = 5

# Qué campos de texto se usan para vectorizar cada tipo de entidad.
_TEXT_FIELDS = {
    "NEED": ["title", "description", "context", "expected_impact"],
    "PROJECT": ["title", "problem_statement", "abstract", "general_objective",
                "methodology", "expected_results", "application_context",
                "keywords", "disciplinary_area"],
    "THESIS": ["title", "abstract", "problem_statement", "general_objective",
               "methodology", "main_results", "conclusions", "keywords",
               "research_area", "application_context"],
    "RESEARCHER": ["profile_summary", "research_interests",
                   "methodological_expertise", "application_domains",
                   "academic_background"],
    "CAPABILITY": ["capability_name", "description", "application_domains"],
    "SUBJECT": ["subject_name", "description", "purpose", "main_topics",
                "disciplinary_area"],
}

_TITLE_FIELD = {
    "PROJECT": "title", "THESIS": "title", "RESEARCHER": "full_name",
    "CAPABILITY": "capability_name", "SUBJECT": "subject_name", "NEED": "title",
}


def _text_of(row: dict, entity_type: str) -> str:
    fields = _TEXT_FIELDS[entity_type]
    return " ".join(str(row.get(f, "") or "") for f in fields)


def _title_of(row: dict, entity_type: str) -> str:
    return str(row.get(_TITLE_FIELD[entity_type], "")) or "(sin título)"


# ---------------------------------------------------------------------------
# Carga perezosa de datos (para que form_team("NEED-001") funcione solo,
# sin que quien lo llama tenga que pasarle core/extra a mano).
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _cached_core() -> CoreData:
    return load_core()


@lru_cache(maxsize=1)
def _cached_extra() -> ExtraData:
    return load_extra()


# ---------------------------------------------------------------------------
# KE-3: candidatos
# ---------------------------------------------------------------------------
class Candidate(dict):
    """dict con llaves: id, type, row, vector, evidencias, relevance."""


def _build_candidates(core: CoreData, extra: ExtraData) -> Dict[str, List[Candidate]]:
    """Construye, sin puntuar todavía, el pool de candidatos por categoría.
    ANTECEDENT junta PROJECT + THESIS porque para la canasta cualquiera de
    los dos sirve como antecedente (doc 01 §1)."""
    pool: Dict[str, List[Candidate]] = {
        "ANTECEDENT": [],
        "RESEARCHER": [],
        "CAPABILITY": [],
        "SUBJECT": [],
    }
    for pid, row in core.projects.items():
        pool["ANTECEDENT"].append(Candidate(id=pid, type="PROJECT", row=row))
    for tid, row in core.theses.items():
        pool["ANTECEDENT"].append(Candidate(id=tid, type="THESIS", row=row))
    for rid, row in core.researchers.items():
        pool["RESEARCHER"].append(Candidate(id=rid, type="RESEARCHER", row=row))
    for cid, row in extra.capabilities.items():
        pool["CAPABILITY"].append(Candidate(id=cid, type="CAPABILITY", row=row))
    for sid, row in extra.subjects.items():
        pool["SUBJECT"].append(Candidate(id=sid, type="SUBJECT", row=row))
    return pool


def candidatos(
    need_vector: Dict[str, float],
    core: CoreData,
    extra: ExtraData,
    top_n: int = TOP_N,
) -> Dict[str, List[Candidate]]:
    """KE-3: nodos cuyo vector de skills pisa el vector de la necesidad (t),
    quedándonos con los top_n más relevantes por categoría.

    'Hecho cuando' (doc de tareas): para NEED-001 esto no devuelve vacío.
    """
    raw_pool = _build_candidates(core, extra)
    scored: Dict[str, List[Candidate]] = {}

    for categoria, items in raw_pool.items():
        puntuados: List[Candidate] = []
        for cand in items:
            texto = _text_of(cand["row"], cand["type"])
            vector, evidencias = score_mod.vectorize(texto)
            relevancia = score_mod.coverage_score(need_vector, [vector])
            if relevancia <= 0:
                continue  # sin ninguna skill en común: no es candidato
            cand["vector"] = vector
            cand["evidencias"] = evidencias
            cand["relevance"] = relevancia
            puntuados.append(cand)
        puntuados.sort(key=lambda c: c["relevance"], reverse=True)
        scored[categoria] = puntuados[:top_n]

    return scored


# ---------------------------------------------------------------------------
# KE-5: hole
# ---------------------------------------------------------------------------
def hole(core: CoreData, antecedent_type: str, antecedent_id: str, researcher_id: str) -> bool:
    """True  -> el investigador NO figura ya en ese antecedente
                (researcher_project.csv / thesis_advisor.csv)
                => la combinación es una oportunidad genuinamente nueva.
    False -> el investigador ya está vinculado a ese antecedente
                => no es hueco, es un antecedente que ya existe con ese equipo.
    """
    if antecedent_type == "PROJECT":
        vinculados = core.investigadores_de(antecedent_id)
    elif antecedent_type == "THESIS":
        vinculados = core.asesores_de(antecedent_id)
    else:
        raise ValueError(f"antecedent_type desconocido: {antecedent_type}")
    return researcher_id not in vinculados


# ---------------------------------------------------------------------------
# KE-4: armar_canasta
# ---------------------------------------------------------------------------
def armar_canasta(
    need_vector: Dict[str, float],
    core: CoreData,
    extra: ExtraData,
    top_n: int = TOP_N,
) -> Optional[dict]:
    """Prueba combinaciones (antecedente x investigador x capacidad x
    asignatura) entre los candidatos preseleccionados y devuelve la que
    maximiza J(E). Con top_n=5 son a lo sumo 5^4=625 combinaciones: trivial
    en tiempo, y ya evita comparar contra las 320+650+180+... filas completas.

    Devuelve None si a alguna categoría no le queda ni un candidato
    (doc 01 §5.5: "si la cobertura es baja se dice que no hay piezas
    suficientes"; aquí es el caso extremo de que ni siquiera hay candidato).
    """
    cands = candidatos(need_vector, core, extra, top_n=top_n)
    if any(len(cands[c]) == 0 for c in ("ANTECEDENT", "RESEARCHER", "CAPABILITY", "SUBJECT")):
        return {"cands": cands, "best": None}

    mejor = None
    mejor_j = float("-inf")
    for antecedente, investigador, capacidad, asignatura in product(
        cands["ANTECEDENT"], cands["RESEARCHER"], cands["CAPABILITY"], cands["SUBJECT"]
    ):
        h = hole(core, antecedente["type"], antecedente["id"], investigador["id"])
        team_vectors = [antecedente["vector"], investigador["vector"],
                        capacidad["vector"], asignatura["vector"]]
        j = score_mod.j_score(need_vector, team_vectors, hole=h)
        if j > mejor_j:
            mejor_j = j
            mejor = {
                "antecedente": antecedente,
                "investigador": investigador,
                "capacidad": capacidad,
                "asignatura": asignatura,
                "hole": h,
                "j_score": j,
                "coverage_score": score_mod.coverage_score(need_vector, team_vectors),
            }

    return {"cands": cands, "best": mejor}


# ---------------------------------------------------------------------------
# Redacción de la propuesta cuando hay hueco (KE-6: "plantilla si no Gemini")
# ---------------------------------------------------------------------------
def generate_proposal_text(best: dict, need_title: str) -> dict:
    """Plantilla determinística (sin Gemini). Si USE_GEMINI=1 y "TÚ" conecta
    la API más adelante, esta función es el punto donde debería enchufarse
    (mismo formato de salida: title/question/tag)."""
    inv_nombre = _title_of(best["investigador"]["row"], "RESEARCHER")
    cap_nombre = _title_of(best["capacidad"]["row"], "CAPABILITY")
    sub_nombre = _title_of(best["asignatura"]["row"], "SUBJECT")
    ant_nombre = _title_of(best["antecedente"]["row"], best["antecedente"]["type"])

    title = f"Propuesta: articular a {inv_nombre} con {cap_nombre} y {sub_nombre}"
    question = (
        f"¿Puede el equipo formado por {inv_nombre}, la capacidad "
        f"'{cap_nombre}' y la asignatura '{sub_nombre}' cubrir la necesidad "
        f"'{need_title}', partiendo del antecedente '{ant_nombre}'?"
    )
    return {"title": title, "question": question, "tag": "GENERADO (plantilla)"}


# ---------------------------------------------------------------------------
# Viabilidad simple (lo que YO-C2 pinta como badge alta/media/baja)
# ---------------------------------------------------------------------------
def _viabilidad(cands: Dict[str, List[Candidate]]) -> str:
    hay_inv = len(cands.get("RESEARCHER", [])) > 0
    hay_cap = len(cands.get("CAPABILITY", [])) > 0
    if hay_inv and hay_cap:
        return "alta"
    if hay_inv or hay_cap:
        return "media"
    return "baja"


def _member_dict(cand: Candidate, tag: str) -> dict:
    return {
        "tipo": cand["type"],
        "id": cand["id"],
        "titulo": _title_of(cand["row"], cand["type"]),
        "tag": tag,
        "relevance": round(cand["relevance"], 4),
        "evidencias": cand["evidencias"],
    }


def _discarded_sample(cands: Dict[str, List[Candidate]], best: dict, k: int = 2) -> List[dict]:
    """HU5 / YO-C3: un par de descartados por categoría, con motivo."""
    elegidos_ids = {
        best["antecedente"]["id"], best["investigador"]["id"],
        best["capacidad"]["id"], best["asignatura"]["id"],
    }
    out = []
    for categoria, items in cands.items():
        restantes = [c for c in items if c["id"] not in elegidos_ids][:k]
        for c in restantes:
            out.append({
                "tipo": c["type"],
                "id": c["id"],
                "titulo": _title_of(c["row"], c["type"]),
                "motivo": f"relevancia {c['relevance']:.2f}, no maximizó J(E) para esta necesidad",
            })
    return out


# ---------------------------------------------------------------------------
# KE-6: form_team — el contrato que usa el frontend
# ---------------------------------------------------------------------------
def form_team(
    query: str,
    core: Optional[CoreData] = None,
    extra: Optional[ExtraData] = None,
    top_n: int = TOP_N,
) -> dict:
    """Punto de entrada único. `query` es un need_id (ej. 'NEED-001') o un
    texto libre escrito por el evaluador.

    Esquema de salida (avisar a Lucía si esto cambia):
    {
      "query": {"need_id": str|None, "text": str},
      "need_evidencias": [{"skill_id","score","fragmento"}, ...],
      "status": "GENERADA" | "ANTECEDENTE_EXISTENTE" | "INSUFICIENTE",
      "viabilidad": "alta"|"media"|"baja",
      "coverage_score": float,
      "j_score": float,
      "hole": bool,
      "team": [ {"tipo","id","titulo","tag","relevance","evidencias"}, ... ] | [],
      "discarded": [ {"tipo","id","titulo","motivo"}, ... ],
      "propuesta": {"title","question","tag"} | None,
    }
    """
    core = core or _cached_core()
    extra = extra or _cached_extra()

    need_row = core.needs.get(query)
    if need_row is not None:
        need_text = _text_of(need_row, "NEED")
        need_title = need_row.get("title", query)
    else:
        need_text = query
        need_title = query

    # use_llm=True SOLO aquí: 1 llamada por consulta, nunca por candidato
    # (candidatos() vectoriza ~1300 filas del dataset y debe quedarse en
    # matching por palabra clave, o el costo/latencia se dispara).
    need_vector, need_evidencias = score_mod.vectorize(need_text, use_llm=True)

    resultado = armar_canasta(need_vector, core, extra, top_n=top_n)
    cands = resultado["cands"]
    best = resultado["best"]
    viabilidad = _viabilidad(cands)

    base = {
        "query": {"need_id": query if need_row is not None else None, "text": need_title},
        "need_evidencias": need_evidencias,
        "viabilidad": viabilidad,
    }

    if best is None:
        base.update({
            "status": "INSUFICIENTE",
            "coverage_score": 0.0,
            "j_score": 0.0,
            "hole": False,
            "team": [],
            "discarded": [],
            "propuesta": None,
            "mensaje": "No hay piezas suficientes en Data V1.0 para esta necesidad.",
        })
        return base

    if best["coverage_score"] < TAU:
        status = "INSUFICIENTE"
        propuesta = None
    elif best["hole"]:
        status = "GENERADA"
        propuesta = generate_proposal_text(best, need_title)
    else:
        status = "ANTECEDENTE_EXISTENTE"
        propuesta = None

    team = [
        _member_dict(best["antecedente"], "INSTITUCIONAL"),
        _member_dict(best["investigador"], "INSTITUCIONAL"),
        _member_dict(best["capacidad"], "INSTITUCIONAL"),
        _member_dict(best["asignatura"], "INSTITUCIONAL"),
    ]

    base.update({
        "status": status,
        "coverage_score": round(best["coverage_score"], 4),
        "j_score": round(best["j_score"], 4),
        "hole": best["hole"],
        "team": team,
        "discarded": _discarded_sample(cands, best),
        "propuesta": propuesta,
    })
    return base


if __name__ == "__main__":
    import json
    resultado = form_team("NEED-001")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
