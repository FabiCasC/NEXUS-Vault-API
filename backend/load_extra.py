"""
backend/load_extra.py
Dueño real: TÚ (tareas YO-A1 a YO-A4 en 06_TAREAS_TU_KEVIN_LUCIA.docx).

⚠️ STUB DE ARRANQUE — solo carga institutional_capabilities.csv y
subjects.csv (lo mínimo que team_formation.py necesita para armar la
canasta: 1 CAP + 1 SUB). Falta lo que sí es tarea tuya: competencies.csv,
document_catalog.csv y sobre todo `load_markdown(need/project/thesis)`
para leer documents/*.md cuando exista source_document. Reemplaza este
archivo cuando lo tengas — team_formation.py solo necesita que
`load_extra()` siga devolviendo un objeto con `.capabilities` y `.subjects`
(dict id -> fila).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from backend.load_core import _index_by_id, _read_csv, _resolve_data_dir  # reutiliza helpers de KEVIN


@dataclass
class ExtraData:
    capabilities: Dict[str, dict] = field(default_factory=dict)
    subjects: Dict[str, dict] = field(default_factory=dict)

    def counts(self) -> Dict[str, int]:
        return {"capabilities": len(self.capabilities), "subjects": len(self.subjects)}


def load_extra(data_dir: Optional[str] = None) -> ExtraData:
    data_dir = _resolve_data_dir(data_dir)

    caps_df = _read_csv(os.path.join(data_dir, "01_institution", "institutional_capabilities.csv"))
    subs_df = _read_csv(os.path.join(data_dir, "02_people_curriculum", "subjects.csv"))

    return ExtraData(
        capabilities=_index_by_id(caps_df, "capability_id"),
        subjects=_index_by_id(subs_df, "subject_id"),
    )


if __name__ == "__main__":
    extra = load_extra()
    print(extra.counts())
