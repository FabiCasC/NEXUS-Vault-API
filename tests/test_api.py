"""
tests/test_api.py
Prueba el servidor HTTP (backend/api.py) y el adaptador de grafo
(backend/graph_adapter.py) contra la data real, usando TestClient
(no necesita un puerto real abierto para correr en CI/local).
"""

from fastapi.testclient import TestClient

from backend.api import app
from backend.team_formation import form_team

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_form_team_endpoint_sin_query_da_error_claro():
    r = client.get("/form-team")
    assert r.status_code == 200
    assert "error" in r.json()


def test_form_team_endpoint_need001_no_revienta():
    r = client.get("/form-team", params={"need_id": "NEED-001"})
    assert r.status_code == 200
    data = r.json()
    assert data["root"] == "NEED-001"
    assert data["nodes"][0]["type"] == "NEED"


def test_form_team_endpoint_devuelve_grafo_completo_cuando_hay_propuesta():
    """Busca la primera NEED real que dé GENERADA y valida el esquema EXACTO
    que espera nexus-vault-frontend2 (services/team_api.py + graph_view.py +
    note_panel.py): nodes con id/type/label/generado/evidencia/frase,
    edges con source/target/weight/dashed. Nombres en español, no en inglés."""
    encontrado = False
    for i in range(1, 43):
        need_id = f"NEED-{i:03d}"
        if form_team(need_id)["status"] != "GENERADA":
            continue
        encontrado = True
        r = client.get("/form-team", params={"need_id": need_id})
        data = r.json()

        tipos = {n["type"] for n in data["nodes"]}
        assert tipos == {"NEED", "PROJECT", "RESEARCHER", "CAPABILITY", "SUBJECT", "PROP"} or \
               tipos == {"NEED", "THESIS", "RESEARCHER", "CAPABILITY", "SUBJECT", "PROP"}

        for n in data["nodes"]:
            assert {"id", "type", "label", "generado"} <= n.keys()
            # los miembros institucionales (no NEED ni PROP) deben traer evidencia real
            if n["type"] not in ("NEED", "PROP"):
                assert n.get("evidencia") is not None
                assert {"archivo", "id", "campo"} <= n["evidencia"].keys()
                assert n.get("frase")  # no vacío: es la cita del CSV

        node_ids = {n["id"] for n in data["nodes"]}
        for e in data["edges"]:
            assert {"source", "target", "weight", "dashed"} <= e.keys()
            assert e["source"] in node_ids
            assert e["target"] in node_ids
        break
    assert encontrado, "Ninguna NEED real dio GENERADA; no se pudo probar el caso feliz"
