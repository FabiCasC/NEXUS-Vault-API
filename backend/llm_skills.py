"""
backend/llm_skills.py
Dueño: KEVIN (extensión sobre el diseño de "TÚ", doc 01 §4.7).

Implementa "Etiquetado restringido y generación anclada": el LLM SOLO
puede elegir skills de la lista cerrada del catálogo, y CADA afirmación
debe venir con una cita textual literal del texto de origen. Si la cita
no aparece tal cual en el texto, o el skill_id no existe en el catálogo,
esa afirmación puntual se descarta (verificación por afirmación, no
todo-o-nada).

Multi-proveedor con fallback automático (se prueban en este orden):
    1. Gemini   (GEMINI_API_KEY)  — el proveedor que pedía el diseño original
    2. ChatGPT  (OPENAI_API_KEY)  — respaldo si Gemini falla o no está configurado
Si ambos fallan o ninguno está configurado, cae al matching por palabra
clave de siempre (cero regresión). Nunca lanza una excepción hacia afuera.

Para ver en la consola del backend cuál proveedor respondió en cada
consulta, busca las líneas "[llm_skills] ...".
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

_OPENAI_MODEL_DEFAULT = "gpt-4o-mini"
_GEMINI_MODEL_DEFAULT = "gemini-3.6-flash"


class LlmEvidence(TypedDict):
    skill_id: str
    score: float
    fragmento: str


def llm_enabled() -> bool:
    tiene_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    return os.environ.get("USE_LLM", "0") == "1" and tiene_key


def _build_prompt(texto: str, skills: List[Skill]) -> str:
    # Incluir las "pistas" (no solo el nombre) le da al modelo contexto real
    # de qué cubre cada skill, para que razone semánticamente (ej. relacionar
    # "predicción de riesgo" con analítica de datos) y no solo repita
    # coincidencias literales de palabra — que es justo lo que ya hace el
    # matching por keyword y lo que este paso está para complementar.
    catalogo_txt = "\n".join(
        f"- {s['skill_id']}: {s['nombre']} (ejemplos de lo que cubre: {', '.join(s['pistas'])})"
        for s in skills
    )
    return (
        "Eres un clasificador de habilidades institucionales. Tienes una lista "
        "CERRADA de habilidades y un texto. Identifica cuáles de esas habilidades "
        "(y SOLO esas, no inventes otras) están evidenciadas en el texto, aunque "
        "el texto use palabras distintas a las de la lista (ej. 'predicción de "
        "riesgo académico' puede evidenciar una habilidad de analítica de datos, "
        "aunque el texto no diga 'analítica' ni 'datos' literalmente).\n\n"
        "Reglas estrictas:\n"
        "1. Solo puedes usar skill_id que aparezcan en la lista de abajo.\n"
        "2. Para cada habilidad que elijas, cita el fragmento EXACTO del texto "
        "(copiado literal, sin parafrasear) que la sustenta — el fragmento citado "
        "puede sustentar más de una habilidad a la vez si aplica a varias.\n"
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


def _parse_json_matches(contenido: str) -> list:
    data = json.loads(contenido)
    raw_matches = data.get("matches", [])
    return raw_matches if isinstance(raw_matches, list) else []


def _call_gemini(texto: str, skills: List[Skill]) -> list:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY no configurada")

    import google.generativeai as genai  # import perezoso: si no está instalado, no rompe nada

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    modelo = os.environ.get("GEMINI_MODEL", _GEMINI_MODEL_DEFAULT)
    model = genai.GenerativeModel(
        modelo,
        generation_config={"response_mime_type": "application/json"},
    )
    resp = model.generate_content(_build_prompt(texto, skills))
    return _parse_json_matches(resp.text)


def _call_openai(texto: str, skills: List[Skill]) -> list:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY no configurada")

    from openai import OpenAI  # import perezoso: si no está instalado, no rompe nada

    client = OpenAI()  # toma OPENAI_API_KEY del entorno
    modelo = os.environ.get("OPENAI_MODEL", _OPENAI_MODEL_DEFAULT)
    resp = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": _build_prompt(texto, skills)}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return _parse_json_matches(resp.choices[0].message.content)


# Orden de intento: Gemini primero (el proveedor del diseño original),
# ChatGPT como respaldo si Gemini falla o no está configurado.
_PROVEEDORES = [("gemini", _call_gemini), ("chatgpt", _call_openai)]


def label_skills_llm(texto: str) -> List[LlmEvidence]:
    """Devuelve solo las evidencias que pasaron la verificación (id real +
    cita literal). Lista vacía si el LLM está desactivado o si TODOS los
    proveedores configurados fallan — nunca revienta el flujo de
    team_formation."""
    if not llm_enabled() or not (texto or "").strip():
        return []

    skills = catalog()
    valid_ids = {s["skill_id"] for s in skills}

    for nombre, llamar in _PROVEEDORES:
        try:
            raw_matches = llamar(texto, skills)
            evidencias = _validate_matches(raw_matches, texto, valid_ids)
            print(f"[llm_skills] {nombre} respondió: {len(evidencias)} skill(s) verificada(s)")
            return evidencias
        except Exception as exc:  # red, cuota, JSON inválido, key ausente, lo que sea
            print(f"[llm_skills] {nombre} no disponible ({exc}), probando siguiente proveedor")
            continue

    print("[llm_skills] ningún proveedor disponible, sigo con matching por palabra clave")
    return []
