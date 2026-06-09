from __future__ import annotations

import copy
import logging
import threading
import time
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_DEFAULT_CONFIG: dict[str, Any] = {
    "mt5": {
        "host": "localhost",
        "port": 8001,
    },
    "trading": {
        "symbol": "XAUUSD",
        "volume": 0.001,
        "magic": 100,
        "deviation": 20,
        "filling": "FOK",
        "sl_dollars": 100.0,
        "reward_ratio": 1.25,
    },
    "signals": {
        "poll_interval": 2.0,
        "csv_dir": "../MetaTrader5-Docker/data/signals",
    },
    "filters": {
        "cooldown_seconds": 30,
        "max_consecutive_losses": 3,
        "pause_after_consecutive_minutes": 15,
        "max_daily_loss": -1,
    },
    "exit_rules": {
        "signal_reversal_exit": False,
        "breakeven_pct": 65.0,
        "trailing_stop_dollars": 0.0,
    },
    "logging": {
        "level": "INFO",
    },
}


class Config:
    """Thread-safe, hot-reloadable YAML configuration."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).resolve()
        self._data: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._watcher_thread: threading.Thread | None = None
        self._last_mtime: float = 0.0
        self.load()

    # ── public API ─────────────────────────────────────────────────────────

    def load(self) -> None:
        with self._lock:
            base = copy.deepcopy(_DEFAULT_CONFIG)
            if self._path.exists():
                with open(self._path) as f:
                    user = yaml.safe_load(f) or {}
                self._deep_merge(base, user)
                self._last_mtime = self._path.stat().st_mtime
                log.info("Config loaded from %s", self._path)
            else:
                log.warning("Config file not found at %s — using defaults", self._path)
            self._data = base

    def get(self, dotpath: str, default: Any = None) -> Any:
        """Retrieve a value by dotted path, e.g. ``trading.volume``."""
        with self._lock:
            node = self._data
            for key in dotpath.split("."):
                if isinstance(node, dict):
                    node = node.get(key)
                else:
                    return default
                if node is None:
                    return default
            return node

    def set_runtime(self, dotpath: str, value: Any) -> None:
        """Set a value at runtime (in-memory only, not persisted)."""
        with self._lock:
            keys = dotpath.split(".")
            node = self._data
            for key in keys[:-1]:
                node = node.setdefault(key, {})
            node[keys[-1]] = value

    def snapshot(self) -> dict[str, Any]:
        """Return a deep copy of the entire config."""
        import copy
        with self._lock:
            return copy.deepcopy(self._data)

    # ── hot-reload watcher ─────────────────────────────────────────────────

    def start_watching(self) -> None:
        if self._watcher_thread is not None:
            return
        self._stop_event.clear()
        self._watcher_thread = threading.Thread(
            target=self._watch_loop, daemon=True, name="config-watcher"
        )
        self._watcher_thread.start()
        log.info("Config hot-reload watcher started")

    def stop_watching(self) -> None:
        self._stop_event.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=5)
            self._watcher_thread = None

    def _watch_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self._path.exists():
                    mtime = self._path.stat().st_mtime
                    if mtime != self._last_mtime:
                        log.info("Config file changed — reloading")
                        self.load()
            except Exception:
                log.exception("Error checking config file")
            time.sleep(2)

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> None:
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                Config._deep_merge(base[k], v)
            else:
                base[k] = v
