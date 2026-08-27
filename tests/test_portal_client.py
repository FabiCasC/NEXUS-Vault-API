"""
tests/test_portal_client.py
Prueba backend/portal_client.py SIN llamar a la API real de Portal (se
mockea requests.post) — no gasta tu key en cada corrida de pytest.
"""

from unittest.mock import MagicMock, patch

from backend import portal_client


def test_apagado_por_defecto(monkeypatch):
    # PORTAL_SECRET y su fallback API_EDUCACION_SECRET (que puede venir
    # cargado por dotenv en otros tests del mismo proceso de pytest).
    monkeypatch.delenv("PORTAL_SECRET", raising=False)
    monkeypatch.delenv("API_EDUCACION_SECRET", raising=False)
    assert portal_client.portal_enabled() is False
    assert portal_client.publish_activity("test", {"a": 1}) is False


def test_publica_con_el_contrato_correcto(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET", "sk-fake-para-test")
    monkeypatch.setenv("PORTAL_API_URL", "https://api.useportal.co")
    monkeypatch.setenv("PORTAL_CHANNEL_ID", "nexus-vault-activity")

    fake_resp = MagicMock(ok=True, status_code=200)
    with patch("requests.post", return_value=fake_resp) as mock_post:
        ok = portal_client.publish_activity("propuesta_generada", {"need": "NEED-019"})

    assert ok is True
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.useportal.co/v1/channels/nexus-vault-activity/messages"
    assert kwargs["headers"]["authorization"] == "Bearer sk-fake-para-test"
    assert kwargs["json"]["type"] == "propuesta_generada"
    assert kwargs["json"]["content"] == {"need": "NEED-019"}


def test_respuesta_no_ok_no_revienta(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET", "sk-fake-para-test")
    fake_resp = MagicMock(ok=False, status_code=401, text="unauthorized")
    with patch("requests.post", return_value=fake_resp):
        assert portal_client.publish_activity("test", {}) is False


def test_falla_de_red_no_revienta(monkeypatch):
    monkeypatch.setenv("PORTAL_SECRET", "sk-fake-para-test")
    import requests

    with patch("requests.post", side_effect=requests.RequestException("sin red")):
        assert portal_client.publish_activity("test", {}) is False
