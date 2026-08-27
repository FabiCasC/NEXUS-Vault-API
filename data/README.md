# Datos

Este proyecto **no** copia el dataset dentro del repo. Por defecto,
`backend/load_core.py` y `backend/load_extra.py` buscan la carpeta
`KNOWLEDGE_NEXUS_LATAM_DATA_V1_RC2_PARTICIPANTS` un nivel arriba de
`nexus-vault/` (donde ya está hoy en la máquina del equipo).

Para usar otra ubicación (por ejemplo, cuando el evaluador entregue una
versión nueva del dataset el día del hackathon):

```bash
export DATA_DIR="/ruta/a/KNOWLEDGE_NEXUS_LATAM_DATA_V1_RC2_PARTICIPANTS"
```

o en Windows (PowerShell):

```powershell
$env:DATA_DIR = "C:\ruta\a\KNOWLEDGE_NEXUS_LATAM_DATA_V1_RC2_PARTICIPANTS"
```
