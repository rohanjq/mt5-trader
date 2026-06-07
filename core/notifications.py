"""Pushover push notifications for trade events.

Sends notifications on: trade opened, trade closed, breakeven, runner TP hit.
Uses stdlib urllib — no extra dependencies needed.

Config (in config.yaml):
    notifications:
      enabled: true
      pushover_user_key: "uossifvqjkvrzm4e4766tvvhcz8aww"
      pushover_app_token: ""  # set in PUSHOVER_APP_TOKEN env or here

Or set environment variables:
    PUSHOVER_USER_KEY=...
    PUSHOVER_APP_TOKEN=...
"""
from __future__ import annotations

import logging
import os
import threading
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Config

log = logging.getLogger(__name__)

PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"


class PushoverNotifier:
    """Non-blocking Pushover push notification sender."""

    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def _enabled(self) -> bool:
        return bool(self._config.get("notifications.enabled", False))

    @property
    def _user_key(self) -> str:
        return os.environ.get(
            "PUSHOVER_USER_KEY",
            self._config.get("notifications.pushover_user_key", ""),
        )

    @property
    def _app_token(self) -> str:
        return os.environ.get(
            "PUSHOVER_APP_TOKEN",
            self._config.get("notifications.pushover_app_token", ""),
        )

    def send(self, message: str, title: str = "MT5 Trader", priority: int = 0) -> None:
        """Send a Pushover notification (non-blocking).

        Priority: -2 (lowest) to 2 (emergency). Default 0 (normal).
        """
        if not self._enabled:
            return
        if not self._user_key or not self._app_token:
            log.warning("Pushover notification skipped — missing user_key or app_token")
            return

        # Fire and forget in a daemon thread to not block trading
        t = threading.Thread(
            target=self._send_sync,
            args=(message, title, priority),
            daemon=True,
        )
        t.start()

    def _send_sync(self, message: str, title: str, priority: int) -> None:
        try:
            data = urllib.parse.urlencode({
                "token": self._app_token,
                "user": self._user_key,
                "message": message,
                "title": title,
                "priority": str(priority),
            }).encode("utf-8")

            req = urllib.request.Request(PUSHOVER_API_URL, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    log.warning("Pushover returned status %d", resp.status)
        except Exception:
            log.exception("Failed to send Pushover notification")
