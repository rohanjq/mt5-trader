from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ── Signal models ──────────────────────────────────────────────────────────────

class SignalDirection(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True)
class Signal:
    source: str
    direction: SignalDirection
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Filter models ──────────────────────────────────────────────────────────────

class FilterVerdict(enum.Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    MODIFY = "MODIFY"


@dataclass
class FilterResult:
    verdict: FilterVerdict
    reason: str = ""
    modifications: dict[str, Any] = field(default_factory=dict)


# ── Trade models ───────────────────────────────────────────────────────────────

class TradeState(enum.Enum):
    IDLE = "IDLE"
    SIGNAL_RECEIVED = "SIGNAL_RECEIVED"
    FILTERS_PASSED = "FILTERS_PASSED"
    EXECUTED = "EXECUTED"
    MONITORING = "MONITORING"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class TradeDirection(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class TradeRequest:
    direction: TradeDirection
    symbol: str
    volume: float
    signal: Signal
    sl: float = 0.0
    tp: float = 0.0
    risk_dollars: float = 0.0
    breakeven_pct: float = 0.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: TradeState = TradeState.SIGNAL_RECEIVED
    rejection_reason: str = ""


@dataclass
class TradeRecord:
    id: str
    direction: TradeDirection
    symbol: str
    volume: float
    entry_price: float
    entry_time: datetime
    signal_source: str
    ticket: int = 0
    sl: float = 0.0
    tp: float = 0.0
    risk_dollars: float = 0.0
    breakeven_pct: float = 0.0
    exit_price: float = 0.0
    exit_time: datetime | None = None
    profit: float = 0.0
    state: TradeState = TradeState.EXECUTED
    comment: str = ""

    @property
    def is_open(self) -> bool:
        return self.state in (TradeState.EXECUTED, TradeState.MONITORING)

    @property
    def is_win(self) -> bool:
        return self.profit > 0

    @property
    def duration_seconds(self) -> float:
        end = self.exit_time or datetime.now()
        return (end - self.entry_time).total_seconds()
