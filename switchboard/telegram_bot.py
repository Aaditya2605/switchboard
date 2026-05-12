from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass(frozen=True)
class TelegramBotConfig:
    token: str
    allowed_chat_ids: set[int] = field(default_factory=set)


class TelegramAPI(Protocol):
    def call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]: ...


class UrlLibTelegramAPI:
    def __init__(self, token: str):
        self.token = token

    def call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = urllib.parse.urlencode(payload or {}).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/{method}",
            data=data,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))


def load_bot_config() -> TelegramBotConfig:
    token = os.environ.get("SWITCHBOARD_TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("SWITCHBOARD_TELEGRAM_BOT_TOKEN is required")
    allowed_raw = os.environ.get("SWITCHBOARD_TELEGRAM_ALLOWED_CHAT_IDS", "")
    allowed = {int(part.strip()) for part in allowed_raw.split(",") if part.strip()}
    return TelegramBotConfig(token=token, allowed_chat_ids=allowed)


class TelegramBot:
    def __init__(self, config: TelegramBotConfig, api: TelegramAPI | None = None):
        self.config = config
        self.api = api or UrlLibTelegramAPI(config.token)
        self.offset: int | None = None

    def poll_once(self, handler: Callable[[str], str], timeout: int = 30) -> int:
        payload: dict[str, Any] = {"timeout": timeout}
        if self.offset is not None:
            payload["offset"] = self.offset
        response = self.api.call("getUpdates", payload)
        handled = 0
        for update in response.get("result", []):
            update_id = update.get("update_id")
            if update_id is not None:
                self.offset = max(self.offset or 0, int(update_id) + 1)
            message = update.get("message") or {}
            text = message.get("text")
            chat = message.get("chat") or {}
            chat_id = chat.get("id")
            if not text or chat_id is None:
                continue
            chat_id = int(chat_id)
            if self.config.allowed_chat_ids and chat_id not in self.config.allowed_chat_ids:
                continue
            reply = handler(text)
            self.send_message(chat_id, reply)
            handled += 1
        if self.offset is not None:
            self.api.call("getUpdates", {"offset": self.offset, "timeout": 0})
        return handled

    def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        return self.api.call("sendMessage", {"chat_id": chat_id, "text": text})

    def set_webhook(self, url: str) -> dict[str, Any]:
        return self.api.call("setWebhook", {"url": url})

    def delete_webhook(self) -> dict[str, Any]:
        return self.api.call("deleteWebhook", {})

    def webhook_info(self) -> dict[str, Any]:
        return self.api.call("getWebhookInfo", {})
