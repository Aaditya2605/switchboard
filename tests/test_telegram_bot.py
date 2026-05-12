import json

import pytest

from switchboard.telegram_bot import TelegramBot, TelegramBotConfig, load_bot_config


class FakeAPI:
    def __init__(self, updates=None):
        self.updates = updates or []
        self.calls = []

    def call(self, method, payload=None):
        self.calls.append((method, payload or {}))
        if method == "getUpdates":
            return {"ok": True, "result": self.updates}
        return {"ok": True, "result": True}


def test_load_bot_config_requires_env_token(monkeypatch):
    monkeypatch.delenv("SWITCHBOARD_TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ValueError):
        load_bot_config()


def test_load_bot_config_reads_token_and_allowed_chats(monkeypatch):
    monkeypatch.setenv("SWITCHBOARD_TELEGRAM_BOT_TOKEN", "123:secret")
    monkeypatch.setenv("SWITCHBOARD_TELEGRAM_ALLOWED_CHAT_IDS", "111, 222")

    config = load_bot_config()

    assert config.token == "123:secret"
    assert config.allowed_chat_ids == {111, 222}


def test_poll_once_replies_to_allowed_chat():
    api = FakeAPI(
        [
            {
                "update_id": 10,
                "message": {"chat": {"id": 111}, "text": "/agents"},
            }
        ]
    )
    bot = TelegramBot(TelegramBotConfig(token="[REDACTED]", allowed_chat_ids={111}), api=api)

    handled = bot.poll_once(lambda text: f"handled {text}")

    assert handled == 1
    assert ("sendMessage", {"chat_id": 111, "text": "handled /agents"}) in api.calls
    assert any(method == "getUpdates" and payload.get("offset") == 11 for method, payload in api.calls)


def test_poll_once_ignores_unauthorized_chat():
    api = FakeAPI(
        [
            {
                "update_id": 10,
                "message": {"chat": {"id": 999}, "text": "/agents"},
            }
        ]
    )
    bot = TelegramBot(TelegramBotConfig(token="[REDACTED]", allowed_chat_ids={111}), api=api)

    handled = bot.poll_once(lambda text: "should not run")

    assert handled == 0
    assert all(method != "sendMessage" for method, _ in api.calls)


def test_webhook_methods_call_bot_api():
    api = FakeAPI()
    bot = TelegramBot(TelegramBotConfig(token="[REDACTED]"), api=api)

    bot.set_webhook("https://example.com/hook")
    bot.delete_webhook()
    bot.webhook_info()

    assert ("setWebhook", {"url": "https://example.com/hook"}) in api.calls
    assert ("deleteWebhook", {}) in api.calls
    assert ("getWebhookInfo", {}) in api.calls
