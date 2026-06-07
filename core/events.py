"""Centralized event log for the trading system.

Any component can push events. The dashboard reads them for display.
Thread-safe ring buffer — keeps the last N events.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class EventLevel(Enum):
    INFO = "INFO"
    TRADE = "TRADE"
    BLOCK = "BLOCK"
    WARN = "WARN"
    EXIT = "EXIT"


@dataclass
class Event:
    level: EventLevel
    message: str
    timestamp: float = field(default_factory=time.time)


class EventLog:
    """Thread-safe ring buffer of recent system events."""

    _instance: EventLog | None = None
    _lock_cls = threading.Lock()

    def __init__(self, maxlen: int = 100) -> None:
        self._events: deque[Event] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> EventLog:
        """Get the singleton instance."""
        if cls._instance is None:
            with cls._lock_cls:
                if cls._instance is None:
                    cls._instance = EventLog()
        return cls._instance

    def push(self, level: EventLevel, message: str) -> None:
        with self._lock:
            self._events.append(Event(level=level, message=message))

    def recent(self, n: int = 20) -> list[Event]:
        with self._lock:
            return list(self._events)[-n:]

    def info(self, message: str) -> None:
        self.push(EventLevel.INFO, message)

    def trade(self, message: str) -> None:
        self.push(EventLevel.TRADE, message)

    def block(self, message: str) -> None:
        self.push(EventLevel.BLOCK, message)

    def warn(self, message: str) -> None:
        self.push(EventLevel.WARN, message)

    def exit_event(self, message: str) -> None:
        self.push(EventLevel.EXIT, message)
