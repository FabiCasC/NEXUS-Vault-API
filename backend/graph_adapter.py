"""
backend/graph_adapter.py
Dueño: KEVIN.

Traductor entre dos mundos:
  - team_formation.form_team()  -> devuelve un EQUIPO (status/team/hole/propuesta)
  - lo que espera app.py de Lucía -> un GRAFO {root, nodes, edges}
    (ver README de NEXUS-Vault-Frontend, sección "Contrato esperado de form_team.py")

Este archivo no inventa datos nuevos: solo re-empaqueta lo que ya devuelve
form_team() en la forma de nodos/aristas que su graph_view.py ya sabe pintar.
"""

from __future__ import annotations

from typing import Optional

# Tipo -> nombre de archivo real del dataset (para el campo "source.file")
_SOURCE_FILE = {
    "NEED": "institutional_needs.csv",
    "PROJECT": "projects.csv",
    "THESIS": "theses.csv",
    "RESEARCHER": "researchers.csv",
    "CAPABILITY": "institutional_capabilities.csv",
    "SUBJECT": "subjects.csv",
}


def _member_phrase(member: dict) -> str:
    """Usa la primera evidencia (skill + fragmento citado del CSV) como frase.
    Si no hay evidencias no debería pasar (candidatos() exige relevance>0),
    pero por seguridad no revienta si llegara a faltar."""
    evidencias = member.get("evidencias") or []
    if not evidencias:
        return ""
    primera = evidencias[0]
    return f"Coincide con la habilidad '{primera['skill_id']}': \"{primera['fragmento']}\""


def _member_node(member: dict) -> dict:
    tipo = member["tipo"]
    return {
        "id": member["id"],
        "type": tipo,
        "label": member["titulo"],
        "phrase": _member_phrase(member),
        # NOTA: aún no rastreamos en qué columna exacta cayó la pista (eso
        # requeriría que score.vectorize devuelva el nombre del campo, no
        # solo el fragmento). Por ahora "field" queda como aproximación.
        "source": {"file": _SOURCE_FILE.get(tipo, "?"), "id": member["id"], "field": "title"},
        "skills": [e["skill_id"] for e in member.get("evidencias", [])],
        "generated": False,  # los miembros del equipo son siempre piezas reales del ZIP
    }


def _need_node(query: dict) -> dict:
    need_id = query.get("need_id")
    node = {
        "id": need_id or "QUERY",
        "type": "NEED",
        "label": query.get("text", ""),
        "phrase": query.get("text", ""),
        "generated": False,
    }
    if need_id:
        node["source"] = {"file": _SOURCE_FILE["NEED"], "id": need_id, "field": "title"}
    return node


def to_graph(resultado: dict) -> dict:
    """Convierte la salida de form_team() al esquema {root, nodes, edges}
    documentado en el README de NEXUS-Vault-Frontend."""
    root_node = _need_node(resultado["query"])
    root_id = root_node["id"]
    nodes = [root_node]
    edges = []

    if resultado["status"] == "INSUFICIENTE":
        # Igual que su default.json: grafo mínimo, sin inventar conexiones.
        return {"root": root_id, "need_id": root_node.get("source", {}).get("id"),
                "nodes": nodes, "edges": edges, "mensaje": resultado.get("mensaje", "")}

    team_nodes = {m["tipo"]: _member_node(m) for m in resultado["team"]}
    nodes.extend(team_nodes.values())

    if resultado["status"] == "GENERADA":
        prop = resultado["propuesta"]
        prop_id = f"PROP-{root_id}"
        nodes.append({
            "id": prop_id,
            "type": "PROP",
            "label": prop["title"],
            "phrase": prop["question"],
            "generated": True,
        })
        edges.append({"source": root_id, "target": prop_id, "label": "cubierta por", "generated": True})
        for tipo, node in team_nodes.items():
            edges.append({"source": prop_id, "target": node["id"], "label": "incluye", "generated": True})

    else:  # ANTECEDENTE_EXISTENTE: ya existe, no hay nada "generado"
        antecedente = next(n for n in team_nodes.values() if n["type"] in ("PROJECT", "THESIS"))
        edges.append({"source": root_id, "target": antecedente["id"], "label": "cubierta por", "generated": False})
        for tipo, node in team_nodes.items():
            if node["id"] == antecedente["id"]:
                continue
            edges.append({"source": antecedente["id"], "target": node["id"], "label": "vinculado a", "generated": False})

    return {
        "root": root_id,
        "need_id": root_node.get("source", {}).get("id"),
        "nodes": nodes,
        "edges": edges,
        "status": resultado["status"],
        "coverage_score": resultado["coverage_score"],
    }
