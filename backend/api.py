"""
backend/api.py
Dueño: KEVIN.

Levanta NEXUS Vault como servidor HTTP para que el frontend (repo aparte,
proceso aparte) pueda llamarlo por red en vez de por import de Python.

Correr:
    cd nexus-vault
    uvicorn backend.api:app --reload --port 8000

Lucía debe pegarle a (desde su repo, con `requests` o `httpx`):
    GET http://localhost:8000/health
    GET http://localhost:8000/form-team?need_id=NEED-001
    GET http://localhost:8000/form-team?free_text=deserción en primer año

La respuesta ya viene en el formato {root, nodes, edges} que su
graph_view.py sabe pintar (ver backend/graph_adapter.py).
"""

from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.graph_adapter import to_graph
from backend.team_formation import form_team

app = FastAPI(title="NEXUS Vault API", version="0.1")

# Hackathon: sin usuarios reales, CORS abierto para no perder tiempo
# depurando origins mientras cada quien prueba desde su propia máquina/puerto.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/form-team")
def form_team_endpoint(
    need_id: Optional[str] = Query(default=None),
    free_text: Optional[str] = Query(default=None),
) -> dict:
    query = need_id or free_text
    if not query:
        return {"error": "Manda need_id (ej. NEED-001) o free_text en la URL."}
    resultado = form_team(query)
    return to_graph(resultado)
