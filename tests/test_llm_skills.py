"""
tests/test_llm_skills.py
Prueba backend/llm_skills.py SIN llamar a la API real de OpenAI (se
mockea el cliente) — no necesitas una API key para correr estos tests,
y no gastan cuota de nadie.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend import llm_skills
from backend.catalog import catalog


def _fake_openai_response(matches: list) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=json.dumps({"matches": matches})))]
    return resp


def test_llm_disabled_por_defecto(monkeypatch):
    monkeypatch.delenv("USE_LLM", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm_skills.llm_enabled() is False
    assert llm_skills.label_skills_llm("cualquier texto") == []


def test_llm_requiere_use_llm_y_api_key(monkeypatch):
    monkeypatch.setenv("USE_LLM", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm_skills.llm_enabled() is False  # falta la key

    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-para-test")
    monkeypatch.setenv("USE_LLM", "0")
    assert llm_skills.llm_enabled() is False  # apagado explícitamente


def test_acepta_match_valido_con_cita_literal(monkeypatch):
    monkeypatch.setenv("USE_LLM", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-para-test")

    skill_real = catalog()[0]["skill_id"]
    texto = "La institución necesita fortalecer la permanencia estudiantil urgentemente."

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(
        [{"skill_id": skill_real, "cita": "permanencia estudiantil"}]
    )

    with patch("openai.OpenAI", return_value=fake_client):
        evidencias = llm_skills.label_skills_llm(texto)

    assert len(evidencias) == 1
    assert evidencias[0]["skill_id"] == skill_real
    assert evidencias[0]["fragmento"] == "permanencia estudiantil"
    assert evidencias[0]["score"] == llm_skills._LLM_SCORE


def test_descarta_skill_id_inventado(monkeypatch):
    monkeypatch.setenv("USE_LLM", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-para-test")

    texto = "Texto de prueba sobre optimización de procesos."
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(
        [{"skill_id": "SK_NO_EXISTE_1234", "cita": "optimización de procesos"}]
    )

    with patch("openai.OpenAI", return_value=fake_client):
        evidencias = llm_skills.label_skills_llm(texto)

    assert evidencias == []  # id inventado -> se descarta, no se inventa un lab/skill


def test_descarta_cita_que_no_esta_literal_en_el_texto(monkeypatch):
    monkeypatch.setenv("USE_LLM", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-para-test")

    skill_real = catalog()[0]["skill_id"]
    texto = "Este texto no menciona nada relacionado."
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(
        [{"skill_id": skill_real, "cita": "una frase que no existe en el texto original"}]
    )

    with patch("openai.OpenAI", return_value=fake_client):
        evidencias = llm_skills.label_skills_llm(texto)

    assert evidencias == []  # cita no verificable -> se descarta


def test_falla_de_red_no_revienta_cae_a_lista_vacia(monkeypatch):
    monkeypatch.setenv("USE_LLM", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake-para-test")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = ConnectionError("sin internet")

    with patch("openai.OpenAI", return_value=fake_client):
        evidencias = llm_skills.label_skills_llm("cualquier texto")

    assert evidencias == []


def test_vectorize_sin_llm_no_cambia_comportamiento(monkeypatch):
    """Cero regresión: con USE_LLM apagado (default en el entorno de tests),
    score.vectorize debe comportarse exactamente igual que antes."""
    monkeypatch.delenv("USE_LLM", raising=False)
    from backend import score

    texto = "permanencia estudiantil y riesgo académico"
    vec, evidencias = score.vectorize(texto)
    assert isinstance(vec, dict)
    assert all(0.0 <= v <= 1.0 for v in vec.values())
