"""
backend/load_core.py
Dueño: KEVIN — los demás no editan este archivo (ver 06_TAREAS_TU_KEVIN_LUCIA).

Carga el núcleo institucional desde Data V1.0 RC2 sin modificar los CSV
originales:
    - institutional_needs.csv   -> needs
    - projects.csv               -> projects
    - theses.csv                 -> theses
    - researchers.csv            -> researchers

Y arma los "puentes" (KE-2) que convierten esas tablas sueltas en un grafo
navegable:
    - researcher_project.csv  -> quién trabajó en qué proyecto
    - thesis_advisor.csv      -> quién asesoró qué tesis
    - project_group.csv       -> a qué grupo pertenece cada proyecto
      (más el campo group_id que ya trae projects.csv de fábrica)

Uso:
    from backend.load_core import load_core
    core = load_core()                       # usa DATA_DIR por defecto o env var
    core.needs["NEED-001"]                   # -> dict con la fila completa
    core.projects_by_researcher("INV-124")   # -> ["PRJ-001", ...]

Definición de "hecho" (KE-1 / KE-2, ver doc de tareas):
    - Conteos ~42 needs / 320 projects / 650 theses / 180 researchers.
    - proyectos_de(INV-xxx) devuelve una lista (no vacía para investigadores
      que sí aparecen en researcher_project.csv).
Ambos casos están cubiertos por tests/test_kevin.py.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Resolución de la carpeta de datos
# ---------------------------------------------------------------------------
# nexus-vault/backend/load_core.py -> _THIS_DIR
# nexus-vault/                     -> _REPO_ROOT
# Hackaton_Lu_Fabi/                -> _PROJECT_ROOT (donde vive el dataset hoy)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
_PROJECT_ROOT = os.path.dirname(_REPO_ROOT)
_DEFAULT_DATA_DIR = os.path.join(
    _PROJECT_ROOT, "KNOWLEDGE_NEXUS_LATAM_DATA_V1_RC2_PARTICIPANTS"
)


def _resolve_data_dir(data_dir: Optional[str] = None) -> str:
    """DATA_DIR explícito > variable de entorno > carpeta por defecto del repo."""
    resolved = data_dir or os.environ.get("DATA_DIR") or _DEFAULT_DATA_DIR
    if not os.path.isdir(resolved):
        raise FileNotFoundError(
            "No encuentro la carpeta de datos en:\n"
            f"  {resolved}\n"
            "Soluciones:\n"
            "  1) Define la variable de entorno DATA_DIR apuntando al ZIP "
            "descomprimido de KNOWLEDGE_NEXUS_LATAM_DATA_V1_RC2_PARTICIPANTS, o\n"
            "  2) Pasa data_dir='ruta/al/dataset' a load_core()."
        )
    return resolved


# ---------------------------------------------------------------------------
# Helpers de limpieza (BOM y nulos) — usados aquí y reutilizables por
# backend/load_extra.py (TÚ) para no duplicar el bug del ﻿.
# ---------------------------------------------------------------------------
def strip_bom(df: pd.DataFrame) -> pd.DataFrame:
    """Quita un BOM (\\ufeff) que haya sobrevivido en el nombre de alguna
    columna. Con encoding='utf-8-sig' no debería hacer falta, pero queda
    como red de seguridad si alguien lee un CSV con otro encoding."""
    df.columns = [c.replace("﻿", "") for c in df.columns]
    return df


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """BOM fuera + NaN -> '' para que concatenar texto nunca reviente."""
    df = strip_bom(df)
    return df.fillna("")


def _read_csv(path: str) -> pd.DataFrame:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No existe el archivo esperado: {path}")
    # utf-8-sig: si el CSV trae BOM, pandas lo descarta solo al parsear
    # el nombre de la primera columna (evita el bug 'ufeffneed_id').
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    return clean_df(df)


def _index_by_id(df: pd.DataFrame, id_col: str) -> Dict[str, dict]:
    if id_col not in df.columns:
        raise KeyError(
            f"Esperaba una columna '{id_col}' y no está. Columnas reales: "
            f"{list(df.columns)}"
        )
    df = df.drop_duplicates(subset=[id_col], keep="first")
    return df.set_index(id_col, drop=False).to_dict(orient="index")


def _group_list(df: pd.DataFrame, key_col: str, value_col: str) -> Dict[str, List[str]]:
    """{key -> [value, value, ...]} preservando el orden del CSV."""
    out: Dict[str, List[str]] = {}
    for key, value in zip(df[key_col], df[value_col]):
        out.setdefault(key, []).append(value)
    return out


# ---------------------------------------------------------------------------
# Contenedor principal
# ---------------------------------------------------------------------------
@dataclass
class CoreData:
    data_dir: str

    needs: Dict[str, dict] = field(default_factory=dict)
    projects: Dict[str, dict] = field(default_factory=dict)
    theses: Dict[str, dict] = field(default_factory=dict)
    researchers: Dict[str, dict] = field(default_factory=dict)

    # filas crudas de los puentes, por si algo necesita el 'role'/'relation'
    researcher_project_raw: List[dict] = field(default_factory=list)
    thesis_advisor_raw: List[dict] = field(default_factory=list)
    project_group_raw: List[dict] = field(default_factory=list)

    # índices derivados (KE-2)
    projects_by_researcher_idx: Dict[str, List[str]] = field(default_factory=dict)
    researchers_by_project_idx: Dict[str, List[str]] = field(default_factory=dict)
    theses_by_advisor_idx: Dict[str, List[str]] = field(default_factory=dict)
    advisors_by_thesis_idx: Dict[str, List[str]] = field(default_factory=dict)
    projects_by_group_idx: Dict[str, List[str]] = field(default_factory=dict)

    # ---- accesores tipo "función" que pide el doc de tareas -------------
    def proyectos_de(self, researcher_id: str) -> List[str]:
        """KE-2: proyectos_de(INV-xxx) -> lista de project_id."""
        return list(self.projects_by_researcher_idx.get(researcher_id, []))

    def investigadores_de(self, project_id: str) -> List[str]:
        return list(self.researchers_by_project_idx.get(project_id, []))

    def tesis_asesoradas_por(self, researcher_id: str) -> List[str]:
        return list(self.theses_by_advisor_idx.get(researcher_id, []))

    def asesores_de(self, thesis_id: str) -> List[str]:
        return list(self.advisors_by_thesis_idx.get(thesis_id, []))

    def proyectos_del_grupo(self, group_id: str) -> List[str]:
        return list(self.projects_by_group_idx.get(group_id, []))

    def get_entity(self, entity_id: str) -> Optional[dict]:
        """Busca un id sin saber a priori el tipo (NEED-/PRJ-/THS-/INV-)."""
        for table in (self.needs, self.projects, self.theses, self.researchers):
            if entity_id in table:
                return table[entity_id]
        return None

    def counts(self) -> Dict[str, int]:
        return {
            "needs": len(self.needs),
            "projects": len(self.projects),
            "theses": len(self.theses),
            "researchers": len(self.researchers),
        }

    def summary(self) -> str:
        c = self.counts()
        return (
            f"needs={c['needs']} projects={c['projects']} "
            f"theses={c['theses']} researchers={c['researchers']} "
            f"| data_dir={self.data_dir}"
        )


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def load_core(data_dir: Optional[str] = None) -> CoreData:
    """Carga needs/projects/theses/researchers + puentes. No modifica los
    CSV originales (solo lectura)."""
    data_dir = _resolve_data_dir(data_dir)

    needs_df = _read_csv(os.path.join(data_dir, "03_knowledge_needs", "institutional_needs.csv"))
    projects_df = _read_csv(os.path.join(data_dir, "03_knowledge_needs", "projects.csv"))
    theses_df = _read_csv(os.path.join(data_dir, "03_knowledge_needs", "theses.csv"))
    researchers_df = _read_csv(os.path.join(data_dir, "02_people_curriculum", "researchers.csv"))

    researcher_project_df = _read_csv(
        os.path.join(data_dir, "03_knowledge_needs", "researcher_project.csv")
    )
    thesis_advisor_df = _read_csv(
        os.path.join(data_dir, "03_knowledge_needs", "thesis_advisor.csv")
    )
    project_group_df = _read_csv(
        os.path.join(data_dir, "03_knowledge_needs", "project_group.csv")
    )

    core = CoreData(
        data_dir=data_dir,
        needs=_index_by_id(needs_df, "need_id"),
        projects=_index_by_id(projects_df, "project_id"),
        theses=_index_by_id(theses_df, "thesis_id"),
        researchers=_index_by_id(researchers_df, "researcher_id"),
        researcher_project_raw=researcher_project_df.to_dict(orient="records"),
        thesis_advisor_raw=thesis_advisor_df.to_dict(orient="records"),
        project_group_raw=project_group_df.to_dict(orient="records"),
    )

    core.projects_by_researcher_idx = _group_list(
        researcher_project_df, "researcher_id", "project_id"
    )
    core.researchers_by_project_idx = _group_list(
        researcher_project_df, "project_id", "researcher_id"
    )
    core.theses_by_advisor_idx = _group_list(thesis_advisor_df, "researcher_id", "thesis_id")
    core.advisors_by_thesis_idx = _group_list(thesis_advisor_df, "thesis_id", "researcher_id")
    core.projects_by_group_idx = _group_list(project_group_df, "group_id", "project_id")

    return core


if __name__ == "__main__":
    # Prueba manual rápida: python -m backend.load_core
    c = load_core()
    print(c.summary())
    print("Proyectos de INV-124:", c.proyectos_de("INV-124"))
    print("NEED-001:", c.needs.get("NEED-001", {}).get("title"))
