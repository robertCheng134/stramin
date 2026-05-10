import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from integrations.telegram_sender import send_message


def test_telegram_sender_missing_env_fails_safely(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = send_message("hello")

    assert result["success"] is False
    assert result["reason"] == "missing_telegram_env"


def test_telegram_sender_success(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return Response()

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setattr("integrations.telegram_sender.requests.post", fake_post)

    result = send_message("hello")

    assert result["success"] is True
    assert calls[0]["url"].endswith("/bottoken/sendMessage")
    assert calls[0]["json"] == {"chat_id": "chat", "text": "hello"}
