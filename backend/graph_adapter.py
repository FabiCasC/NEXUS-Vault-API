"""
backend/graph_adapter.py
Dueño: KEVIN.

Traductor entre dos mundos:
  - team_formation.form_team()  -> devuelve un EQUIPO (status/team/hole/propuesta)
  - lo que espera el frontend (nexus-vault-frontend2, services/team_api.py +
    components/note_panel.py) -> un GRAFO {nodes, edges} con esta forma EXACTA:

        node: {id, type, label, generado: bool, evidencia: {archivo, id, campo} | None, frase}
        edge: {source, target, weight: float, dashed: bool}

    OJO: los nombres de campo son en español (generado/evidencia/archivo/
    campo/frase), no en inglés. Si esto vuelve a cambiar del lado del
    frontend, este es el único archivo que hay que tocar.
"""

from __future__ import annotations

import hashlib
from typing import Optional

# Tipo -> nombre de archivo real del dataset (para "evidencia.archivo")
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
        "frase": _member_phrase(member),
        # NOTA: aún no rastreamos en qué columna exacta cayó la pista (eso
        # requeriría que score.vectorize devuelva el nombre del campo, no
        # solo el fragmento). Por ahora "campo" queda como aproximación.
        "evidencia": {"archivo": _SOURCE_FILE.get(tipo, "?"), "id": member["id"], "campo": "title"},
        "skills": [e["skill_id"] for e in member.get("evidencias", [])],
        "generado": False,  # los miembros del equipo son siempre piezas reales del ZIP
    }


def _local_id(texto: str) -> str:
    """Id estable para una idea libre que no vino de un NEED-xxx real
    (mismo patrón que ya usa el frontend en su propio fallback local:
    NEED-LOCAL-<hash6>), para que dos ideas distintas no compartan id."""
    return f"NEED-LOCAL-{hashlib.md5(texto.encode('utf-8')).hexdigest()[:6]}"


def _need_node(query: dict) -> dict:
    need_id = query.get("need_id")
    texto = query.get("text", "")
    node = {
        "id": need_id or _local_id(texto),
        "type": "NEED",
        "label": texto,
        "title": texto,  # app.py arma el mensaje de confirmación con .get("title")
        "frase": texto,
        "generado": need_id is None,  # si no vino de un NEED-xxx real, es una idea nueva
    }
    if need_id:
        node["evidencia"] = {"archivo": _SOURCE_FILE["NEED"], "id": need_id, "campo": "title"}
    return node


def to_graph(resultado: dict) -> dict:
    """Convierte la salida de form_team() al esquema {nodes, edges} que
    consume services/team_api.py + components/graph_view.py + note_panel.py."""
    root_node = _need_node(resultado["query"])
    root_id = root_node["id"]
    need_id = root_node.get("evidencia", {}).get("id")
    nodes = [root_node]
    edges = []

    if resultado["status"] == "INSUFICIENTE":
        # Grafo mínimo, sin inventar conexiones.
        return {"root": root_id, "need_id": need_id, "nodes": nodes, "edges": edges,
                "status": resultado["status"], "mensaje": resultado.get("mensaje", "")}

    team_nodes = {m["tipo"]: (m, _member_node(m)) for m in resultado["team"]}
    nodes.extend(node for _, node in team_nodes.values())
    coverage = resultado["coverage_score"]

    if resultado["status"] == "GENERADA":
        prop = resultado["propuesta"]
        prop_id = f"PROP-{root_id}"
        nodes.append({
            "id": prop_id,
            "type": "PROP",
            # Etiqueta corta a propósito: el título completo (largo) se ve
            # al hacer clic (nota), no compite por espacio en el grafo.
            "label": "🔮 Propuesta generada",
            "frase": f"{prop['title']}. {prop['question']}",
            "generado": True,
        })
        edges.append({"source": root_id, "target": prop_id, "weight": coverage, "dashed": True})
        for member, node in team_nodes.values():
            edges.append({"source": prop_id, "target": node["id"], "weight": member["relevance"], "dashed": True})

    else:  # ANTECEDENTE_EXISTENTE: ya existe, no hay nada generado
        antecedente_member, antecedente_node = next(
            (m, n) for m, n in team_nodes.values() if n["type"] in ("PROJECT", "THESIS")
        )
        edges.append({"source": root_id, "target": antecedente_node["id"], "weight": coverage, "dashed": False})
        for member, node in team_nodes.values():
            if node["id"] == antecedente_node["id"]:
                continue
            edges.append({
                "source": antecedente_node["id"], "target": node["id"],
                "weight": member["relevance"], "dashed": False,
            })

    return {
        "root": root_id,
        "need_id": need_id,
        "nodes": nodes,
        "edges": edges,
        "status": resultado["status"],
        "coverage_score": coverage,
    }
