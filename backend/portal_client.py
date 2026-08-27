"""
backend/portal_client.py
Dueño: KEVIN.

Integración con Portal (useportal.co) — servicio de canales en tiempo real
(WebSocket) con bandeja de entrada por usuario. Contrato REST replicado del
proyecto hermano ProyectoImpostorDiseño/impostoi (src/lib/portal-server.ts),
que ya lo usa en producción:

    POST {PORTAL_API_URL}/v1/channels/{channel_id}/messages
    Authorization: Bearer {PORTAL_SECRET}
    body: {"senderId": ..., "type": ..., "content": {...}}

Uso en NEXUS Vault: "actividad institucional en vivo". Cada vez que
form_team() genera una propuesta nueva (status=GENERADA), se publica un
evento al canal. Cualquier cliente suscrito (un panel de monitoreo, otra
pestaña, el equipo evaluador) ve en tiempo real qué oportunidades va
descubriendo el sistema — sin necesidad de refrescar ni consultar una por
una. Esto es un argumento concreto para "impacto y escalabilidad": en un
escenario real, distintas facultades podrían observar en vivo el mismo
feed institucional.

100% opcional y con fallback silencioso: si no hay PORTAL_SECRET, o la
llamada falla (red, cuota, canal no configurado), NUNCA rompe el flujo
principal de /form-team. Publicar es un efecto secundario, no una
dependencia dura.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests

_DEFAULT_CHANNEL = "nexus-vault-activity"
_TIMEOUT_SECONDS = 3.0


def _secret() -> str:
    # Nombre canónico PORTAL_SECRET, con fallback a API_EDUCACION_SECRET
    # (así se llama en el .env que ya viene provisto para el track de Educación).
    return os.environ.get("PORTAL_SECRET") or os.environ.get("API_EDUCACION_SECRET", "")


def portal_enabled() -> bool:
    return bool(_secret())


def _config() -> Dict[str, str]:
    return {
        "api_url": os.environ.get("PORTAL_API_URL", "https://api.useportal.co").rstrip("/"),
        "secret": _secret(),
        "channel_id": os.environ.get("PORTAL_CHANNEL_ID", _DEFAULT_CHANNEL),
    }


def publish_activity(event_type: str, content: Dict[str, Any], sender_id: str = "nexus-vault-api") -> bool:
    """Publica un evento al canal de actividad de Portal. Devuelve True si
    se publicó, False si Portal está apagado o la llamada falló — en
    ningún caso lanza una excepción hacia quien la llama (backend/api.py
    no debe fallarle al frontend por un problema de Portal)."""
    if not portal_enabled():
        return False

    cfg = _config()
    url = f"{cfg['api_url']}/v1/channels/{cfg['channel_id']}/messages"

    try:
        resp = requests.post(
            url,
            headers={
                "authorization": f"Bearer {cfg['secret']}",
                "content-type": "application/json",
            },
            json={"senderId": sender_id, "type": event_type, "content": content},
            timeout=_TIMEOUT_SECONDS,
        )
        if not resp.ok:
            print(f"[portal_client] Portal respondió {resp.status_code}: {resp.text[:200]}")
            return False
        print(f"[portal_client] publicado en canal '{cfg['channel_id']}': {event_type}")
        return True
    except requests.RequestException as exc:
        print(f"[portal_client] No se pudo publicar en Portal (sigue la demo igual): {exc}")
        return False
