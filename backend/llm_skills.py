"""
backend/llm_skills.py
Dueño: KEVIN (extensión sobre el diseño de "TÚ", doc 01 §4.7).

Implementa "Etiquetado restringido y generación anclada" con ChatGPT
(OpenAI) en vez de Gemini — el rol es idéntico al que describe el doc
01_PROPUESTA_NEXUS_VAULT.docx: el LLM SOLO puede elegir skills de la lista
cerrada del catálogo, y CADA afirmación debe venir con una cita textual
literal del texto de origen. Si la cita no aparece tal cual en el texto,
o el skill_id no existe en el catálogo, esa afirmación puntual se descarta
— no se le hace ciego trust a la salida del modelo completa por completo,
pero tampoco se tira todo el resultado por un solo error (verificación
por afirmación, no todo-o-nada).

100% opcional y con fallback: si USE_LLM no está en "1" o no hay
OPENAI_API_KEY, todo el resto del sistema sigue funcionando exactamente
igual que antes (backend/score.py cae solo al matching por palabra clave).
Nunca lanza una excepción hacia afuera: cualquier falla de red, cuota,
JSON mal formado, etc. se traduce en "no hay evidencia LLM para este texto".
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple, TypedDict

from backend.catalog import Skill, catalog

# Confianza asignada a una skill confirmada por el LLM (con cita verificada
# contra el texto fuente). Un poco más alta que el 0.8 del match literal de
# palabra clave, porque pasó una verificación semántica, no solo textual.
_LLM_SCORE = 0.9

_MODEL_DEFAULT = "gpt-4o-mini"


class LlmEvidence(TypedDict):
    skill_id: str
    score: float
    fragmento: str


def llm_enabled() -> bool:
    return os.environ.get("USE_LLM", "0") == "1" and bool(os.environ.get("OPENAI_API_KEY"))


def _build_prompt(texto: str, skills: List[Skill]) -> str:
    catalogo_txt = "\n".join(f"- {s['skill_id']}: {s['nombre']}" for s in skills)
    return (
        "Eres un clasificador de habilidades institucionales. Tienes una lista "
        "CERRADA de habilidades y un texto. Identifica cuáles de esas habilidades "
        "(y SOLO esas, no inventes otras) están evidenciadas en el texto.\n\n"
        "Reglas estrictas:\n"
        "1. Solo puedes usar skill_id que aparezcan en la lista de abajo.\n"
        "2. Para cada habilidad que elijas, cita el fragmento EXACTO del texto "
        "(copiado literal, sin parafrasear) que la sustenta.\n"
        "3. Si ninguna habilidad aplica, responde con una lista vacía.\n"
        "4. Responde SOLO JSON válido, sin texto adicional, con este formato:\n"
        '   {"matches": [{"skill_id": "SK_X", "cita": "fragmento literal del texto"}]}\n\n'
        f"CATÁLOGO CERRADO:\n{catalogo_txt}\n\n"
        f"TEXTO:\n{texto}\n"
    )


def _validate_matches(raw_matches: list, texto: str, valid_ids: set) -> List[LlmEvidence]:
    texto_low = (texto or "").lower()
    evidencias: List[LlmEvidence] = []
    for m in raw_matches:
        skill_id = m.get("skill_id")
        cita = (m.get("cita") or "").strip()
        if skill_id not in valid_ids:
            continue  # el modelo inventó un id que no existe en el catálogo: se descarta
        if not cita or cita.lower() not in texto_low:
            continue  # la cita no es literal del texto: no se puede verificar, se descarta
        evidencias.append({"skill_id": skill_id, "score": _LLM_SCORE, "fragmento": cita})
    return evidencias


def label_skills_llm(texto: str) -> List[LlmEvidence]:
    """Devuelve solo las evidencias que pasaron la verificación (id real +
    cita literal). Lista vacía si el LLM está desactivado o falla por
    cualquier razón — nunca revienta el flujo de team_formation."""
    if not llm_enabled() or not (texto or "").strip():
        return []

    skills = catalog()
    valid_ids = {s["skill_id"] for s in skills}

    try:
        from openai import OpenAI  # import perezoso: si no está instalado, no rompe nada

        client = OpenAI()  # toma OPENAI_API_KEY del entorno
        modelo = os.environ.get("OPENAI_MODEL", _MODEL_DEFAULT)

        resp = client.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": _build_prompt(texto, skills)}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        contenido = resp.choices[0].message.content
        data = json.loads(contenido)
        raw_matches = data.get("matches", [])
        if not isinstance(raw_matches, list):
            return []
        return _validate_matches(raw_matches, texto, valid_ids)

    except Exception as exc:  # red, cuota, JSON inválido, lo que sea: fallback silencioso
        print(f"[llm_skills] LLM no disponible, sigo con matching por palabra clave: {exc}")
        return []
