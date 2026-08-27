# NEXUS Vault

Prototipo para el reto "Knowledge Nexus LATAM: Conectar el conocimiento"
(Hackathon Perú 2026, Talento TECH / TIC). Ver `DOCUMENTOS/` en la raíz del
proyecto para la propuesta completa y el PDF oficial del desafío.

## Instalación

```bash
cd nexus-vault
python -m venv .venv && source .venv/bin/activate   # o .venv\Scripts\activate en Windows
pip install -r requirements.txt
```

## Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `DATA_DIR` | `../KNOWLEDGE_NEXUS_LATAM_DATA_V1_RC2_PARTICIPANTS` | Carpeta del dataset descomprimido |
| `USE_GEMINI` | `0` | `1` para redacción con Gemini; `0` usa plantilla |
| `GEMINI_API_KEY` | — | Solo si `USE_GEMINI=1` |

## Estado actual por módulo

| Archivo | Dueño | Estado |
|---|---|---|
| `backend/load_core.py` | KEVIN | ✅ implementado y probado (42/320/650/180 registros reales) |
| `backend/team_formation.py` | KEVIN | ✅ implementado y probado (42/42 necesidades reales sin errores) |
| `backend/load_extra.py` | TÚ | ⚠️ stub mínimo (solo capabilities+subjects; falta documents/\*.md) |
| `backend/catalog.py` | TÚ | ⚠️ stub de 18 skills por keyword; falta curar contra la data + embeddings |
| `backend/score.py` | TÚ | ⚠️ stub con matching literal (YO-B2); falta el cosine con sentence-transformers |
| `frontend/*` | LUCÍA | pendiente |
| `prompts/*.txt`, Gemini | TÚ | pendiente |

## Cómo correr y probar la parte de KEVIN

```bash
cd nexus-vault
python -m backend.load_core          # smoke test manual
python -m backend.team_formation     # arma la canasta para NEED-001 e imprime el JSON
python -m pytest tests/test_kevin.py -v
```

Los tests corren contra la data real (no contra mocks) y cubren:
- KE-1: conteos exactos de needs/projects/theses/researchers.
- KE-2: `proyectos_de` / `investigadores_de` / `asesores_de`.
- KE-3: `candidatos()` no vacío para NEED-001.
- KE-4/KE-6: `form_team()` corrido contra las **42 necesidades reales** sin
  ninguna excepción, con salida siempre serializable a JSON.
- KE-5: `hole()` probado en aislamiento con un grafo de prueba controlado.

⚠️ Resultado esperable HOY con el catálogo-stub: de las 42 necesidades
reales, solo ~4 llegan a `GENERADA` y 0 a `ANTECEDENTE_EXISTENTE` — el resto
sale `INSUFICIENTE`. **No es un bug**: es la prueba en carne propia de lo
que el PDF del reto advierte sobre similitud léxica vs. pertinencia real.
El número sube en cuanto "TÚ" reemplace `catalog.py`/`score.py` por la
versión con embeddings (doc 01, sección 4.6) — `team_formation.py` no
necesita cambiar nada porque respeta las mismas firmas de función.

## Contrato entre módulos (para no pisarse)

`team_formation.py` solo asume que:
- `load_core.load_core()` devuelve un objeto con `.needs/.projects/.theses/.researchers` y los métodos `proyectos_de/investigadores_de/asesores_de/tesis_asesoradas_por`.
- `load_extra.load_extra()` devuelve un objeto con `.capabilities` y `.subjects` (dict id→fila).
- `score.vectorize(texto) -> (vector, evidencias)`, `score.coverage_score(t, vectores)` y `score.j_score(t, vectores, hole)` existen con esas firmas.
- `catalog.catalog()` devuelve una lista de `{skill_id, nombre, pistas}`.

Mientras esas firmas no cambien, "TÚ" puede reemplazar los tres stubs por
la versión final sin tocar `team_formation.py`, y Lucía puede seguir
importando `form_team()` sin que le cambie el esquema de salida (documentado
en el docstring de `form_team`).
