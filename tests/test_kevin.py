"""
tests/test_kevin.py
Valida los "hecho cuando" de KE-1 a KE-6 (06_TAREAS_TU_KEVIN_LUCIA.docx)
contra la data real de Data V1.0 RC2.

Correr con:
    cd nexus-vault
    python -m pytest tests/test_kevin.py -v
"""

import json

import pytest

from backend.load_core import CoreData, load_core
from backend.load_extra import load_extra
from backend.team_formation import (
    armar_canasta,
    candidatos,
    form_team,
    hole,
)
from backend import score as score_mod


# ---------------------------------------------------------------------------
# Fixtures compartidas (se cargan una sola vez para todos los tests)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def core() -> CoreData:
    return load_core()


@pytest.fixture(scope="module")
def extra():
    return load_extra()


# ---------------------------------------------------------------------------
# KE-1: load_core.py
# ---------------------------------------------------------------------------
def test_ke1_conteos_reales(core: CoreData):
    c = core.counts()
    assert c["needs"] == 42
    assert c["projects"] == 320
    assert c["theses"] == 650
    assert c["researchers"] == 180


def test_ke1_sin_bom_en_columnas(core: CoreData):
    # El bug clásico: la primera columna sale como '﻿need_id'.
    assert "need_id" in next(iter(core.needs.values()))
    assert not any(k.startswith("﻿") for k in next(iter(core.needs.values())))


def test_ke1_need001_existe_con_texto_real(core: CoreData):
    need = core.needs["NEED-001"]
    assert need["title"].startswith("Predicción")


# ---------------------------------------------------------------------------
# KE-2: puentes
# ---------------------------------------------------------------------------
def test_ke2_proyectos_de_no_vacio(core: CoreData):
    proyectos = core.proyectos_de("INV-124")
    assert proyectos, "proyectos_de(INV-124) no debería devolver vacío"
    assert "PRJ-001" in proyectos  # confirmado a mano contra researcher_project.csv


def test_ke2_investigadores_de_es_reciproco(core: CoreData):
    for proyecto in core.investigadores_de("PRJ-001"):
        assert "PRJ-001" in core.proyectos_de(proyecto)


def test_ke2_asesores_de_tesis(core: CoreData):
    asesores = core.asesores_de("THS-001")
    assert asesores == ["INV-114"]  # dato real de thesis_advisor.csv


# ---------------------------------------------------------------------------
# KE-3: candidatos
# ---------------------------------------------------------------------------
def test_ke3_candidatos_need001_no_vacio(core: CoreData, extra):
    need_text = " ".join(
        str(core.needs["NEED-001"].get(f, "") or "")
        for f in ["title", "description", "context", "expected_impact"]
    )
    t, _ = score_mod.vectorize(need_text)
    cands = candidatos(t, core, extra)
    total = sum(len(v) for v in cands.values())
    assert total > 0, "candidatos() no debe devolver vacío para NEED-001"


# ---------------------------------------------------------------------------
# KE-5: hole (probado en aislamiento, sin depender del catálogo real)
# ---------------------------------------------------------------------------
def test_ke5_hole_con_grafo_controlado():
    core_falso = CoreData(data_dir="fake")
    core_falso.researchers_by_project_idx = {"PRJ-X": ["INV-A", "INV-B"]}
    core_falso.advisors_by_thesis_idx = {"THS-X": ["INV-C"]}

    # el investigador YA está en el proyecto -> no es hueco
    assert hole(core_falso, "PROJECT", "PRJ-X", "INV-A") is False
    # investigador nuevo para ese proyecto -> hueco real
    assert hole(core_falso, "PROJECT", "PRJ-X", "INV-Z") is True
    # mismo chequeo del lado de tesis/asesor
    assert hole(core_falso, "THESIS", "THS-X", "INV-C") is False
    assert hole(core_falso, "THESIS", "THS-X", "INV-Z") is True


# ---------------------------------------------------------------------------
# KE-4 / KE-6: armar_canasta + form_team, sobre las 42 necesidades reales
# ---------------------------------------------------------------------------
NEED_IDS = [f"NEED-{i:03d}" for i in range(1, 43)]


@pytest.mark.parametrize("need_id", NEED_IDS)
def test_ke4_ke6_form_team_no_revienta_y_es_json_valido(need_id, core, extra):
    """Prueba de fuego: las 42 necesidades reales, cero excepciones,
    salida siempre serializable a JSON (esto es lo que Lucía consume)."""
    resultado = form_team(need_id, core=core, extra=extra)

    # siempre serializable
    json.dumps(resultado, ensure_ascii=False)

    assert resultado["status"] in {"GENERADA", "ANTECEDENTE_EXISTENTE", "INSUFICIENTE"}

    if resultado["status"] != "INSUFICIENTE":
        # KE-4: "4 tipos distintos"
        tipos = {m["tipo"] for m in resultado["team"]}
        assert len(resultado["team"]) == 4
        assert len(tipos) == 4
        assert tipos <= {"PROJECT", "THESIS", "RESEARCHER", "CAPABILITY", "SUBJECT"}

    if resultado["status"] == "GENERADA":
        assert resultado["hole"] is True
        assert resultado["propuesta"] is not None
        assert resultado["propuesta"]["tag"] == "GENERADO (plantilla)"

    if resultado["status"] == "ANTECEDENTE_EXISTENTE":
        assert resultado["hole"] is False
        assert resultado["propuesta"] is None


def test_ke6_texto_libre_no_registrado_no_revienta(core, extra):
    """El evaluador puede escribir un tema que el equipo no ensayó (HU6 /
    doc D3): form_team no debe asumir que 'query' es siempre un NEED-xxx."""
    resultado = form_team(
        "necesitamos entender abandono y riesgo académico en primer semestre",
        core=core,
        extra=extra,
    )
    json.dumps(resultado, ensure_ascii=False)
    assert resultado["query"]["need_id"] is None


def test_resumen_cobertura(core, extra, capsys):
    """No es un assert estricto: imprime cuántas de las 42 necesidades caen
    en cada status con el catálogo-stub actual, para que quede registrado
    qué tanto hace falta el catálogo/embeddings definitivos de 'TÚ'."""
    conteo = {"GENERADA": 0, "ANTECEDENTE_EXISTENTE": 0, "INSUFICIENTE": 0}
    for need_id in NEED_IDS:
        r = form_team(need_id, core=core, extra=extra)
        conteo[r["status"]] += 1
    print(f"\nResumen sobre las 42 necesidades reales (catálogo-stub): {conteo}")
    assert sum(conteo.values()) == 42
