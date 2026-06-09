from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Generator

from mt5linux import MetaTrader5

from core.config import Config

log = logging.getLogger(__name__)


class MT5Client:
    """Thread-safe wrapper around the rpyc MT5 bridge."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._mt5: MetaTrader5 | None = None
        self._lock = threading.Lock()
        self._connected = False

    # ── connection ─────────────────────────────────────────────────────────

    def connect(self) -> bool:
        with self._lock:
            if self._connected:
                return True
            host = self._config.get("mt5.host", "localhost")
            port = self._config.get("mt5.port", 8001)
            try:
                self._mt5 = MetaTrader5(host=host, port=port)
                if not self._mt5.initialize():
                    log.error("MT5 initialize() failed")
                    self._mt5 = None
                    return False
                self._connected = True
                info = self._mt5.terminal_info()
                if info:
                    log.info("Connected to MT5: %s", info.name)
                return True
            except Exception:
                log.exception("Failed to connect to MT5 at %s:%s", host, port)
                self._mt5 = None
                return False

    def disconnect(self) -> None:
        with self._lock:
            if self._mt5 and self._connected:
                try:
                    self._mt5.shutdown()
                except Exception:
                    log.exception("Error during MT5 shutdown")
                finally:
                    self._connected = False
                    self._mt5 = None
                    log.info("Disconnected from MT5")

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def mt5(self) -> MetaTrader5:
        if not self._mt5:
            raise RuntimeError("MT5 not connected")
        return self._mt5

    # ── market data ────────────────────────────────────────────────────────

    def get_account_info(self) -> Any:
        """Get MT5 account info (balance, equity, margin, etc.)."""
        try:
            with self._lock:
                return self.mt5.account_info()
        except Exception:
            log.warning("get_account_info failed — bridge may be disconnected")
            self._connected = False
            return None

    def get_tick(self, symbol: str | None = None) -> Any:
        symbol = symbol or self._config.get("trading.symbol", "XAUUSD")
        try:
            with self._lock:
                return self.mt5.symbol_info_tick(symbol)
        except Exception:
            log.warning("get_tick failed for %s — bridge may be disconnected", symbol)
            self._connected = False
            return None

    def get_symbol_info(self, symbol: str | None = None) -> Any:
        symbol = symbol or self._config.get("trading.symbol", "XAUUSD")
        try:
            with self._lock:
                return self.mt5.symbol_info(symbol)
        except Exception:
            log.warning("get_symbol_info failed for %s — bridge may be disconnected", symbol)
            self._connected = False
            return None

    # ── order execution ────────────────────────────────────────────────────

    def send_order(self, request: dict) -> Any:
        try:
            with self._lock:
                log.info("Sending order: %s", request)
                result = self.mt5.order_send(request)
                if result and result.retcode == 10009:
                    log.info("Order executed: ticket=%s", result.order)
                else:
                    retcode = result.retcode if result else "None"
                    comment = result.comment if result else "no result"
                    log.error("Order failed: retcode=%s comment=%s", retcode, comment)
                return result
        except Exception:
            log.exception("send_order failed — bridge may be disconnected")
            self._connected = False
            return None

    def buy(self, volume: float | None = None, symbol: str | None = None,
             sl: float = 0.0, tp: float = 0.0) -> Any:
        symbol = symbol or self._config.get("trading.symbol", "XAUUSD")
        volume = volume or self._config.get("trading.volume", 0.001)
        tick = self.get_tick(symbol)
        if not tick:
            log.error("Cannot get tick for %s", symbol)
            return None
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": self.mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": self._config.get("trading.deviation", 20),
            "magic": self._config.get("trading.magic", 100),
            "comment": "bot buy",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_FOK,
        }
        if sl > 0:
            request["sl"] = float(sl)
        if tp > 0:
            request["tp"] = float(tp)
        return self.send_order(request)

    def sell(self, volume: float | None = None, symbol: str | None = None,
              sl: float = 0.0, tp: float = 0.0) -> Any:
        symbol = symbol or self._config.get("trading.symbol", "XAUUSD")
        volume = volume or self._config.get("trading.volume", 0.001)
        tick = self.get_tick(symbol)
        if not tick:
            log.error("Cannot get tick for %s", symbol)
            return None
        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": self.mt5.ORDER_TYPE_SELL,
            "price": tick.bid,
            "deviation": self._config.get("trading.deviation", 20),
            "magic": self._config.get("trading.magic", 100),
            "comment": "bot sell",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_FOK,
        }
        if sl > 0:
            request["sl"] = float(sl)
        if tp > 0:
            request["tp"] = float(tp)
        return self.send_order(request)

    def close_position(self, ticket: int, volume: float, direction: str, symbol: str | None = None) -> Any:
        symbol = symbol or self._config.get("trading.symbol", "XAUUSD")
        tick = self.get_tick(symbol)
        if not tick:
            log.error("Cannot get tick for close")
            return None

        if direction == "BUY":
            close_type = self.mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            close_type = self.mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = {
            "action": self.mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": self._config.get("trading.deviation", 20),
            "magic": self._config.get("trading.magic", 100),
            "comment": "bot close",
            "type_time": self.mt5.ORDER_TIME_GTC,
            "type_filling": self.mt5.ORDER_FILLING_FOK,
        }
        return self.send_order(request)

    def get_positions(self, symbol: str | None = None) -> list:
        symbol = symbol or self._config.get("trading.symbol", "XAUUSD")
        try:
            with self._lock:
                positions = self.mt5.positions_get(symbol=symbol)
                return list(positions) if positions else []
        except Exception:
            log.warning("get_positions failed — bridge may be disconnected")
            self._connected = False
            return []

    def get_recent_deals(self, symbol: str | None = None, hours: float = 4.0) -> list:
        """Get all deals from the last N hours for a given symbol."""
        from datetime import datetime, timedelta, timezone
        symbol = symbol or self._config.get("trading.symbol", "XAUUSD")
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)
        try:
            with self._lock:
                deals = self.mt5.history_deals_get(start, now, symbol=symbol)
                return list(deals) if deals else []
        except Exception:
            log.warning("get_recent_deals failed — bridge may be disconnected")
            self._connected = False
            return []

    def get_deals_by_position(self, position_id: int) -> list:
        """Get deal history for a specific position ticket."""
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        try:
            with self._lock:
                deals = self.mt5.history_deals_get(
                    now - timedelta(hours=24), now, position=position_id
                )
                if not deals:
                    return []
                # rpyc may ignore 'position' kwarg — filter client-side
                filtered = []
                for d in deals:
                    pos = getattr(d, 'position_id', None) or getattr(d, 'position', None)
                    if pos == position_id:
                        filtered.append(d)
                return filtered
        except Exception:
            log.warning("get_deals_by_position failed — bridge may be disconnected")
            self._connected = False
            return []

    def modify_position(self, ticket: int, sl: float = 0.0, tp: float = 0.0,
                        symbol: str | None = None) -> Any:
        """Modify SL/TP of an open position using TRADE_ACTION_SLTP."""
        symbol = symbol or self._config.get("trading.symbol", "XAUUSD")
        request = {
            "action": self.mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
        }
        if sl > 0:
            request["sl"] = float(sl)
        if tp > 0:
            request["tp"] = float(tp)
        try:
            with self._lock:
                log.info("Modifying position %s: sl=%.2f tp=%.2f", ticket, sl, tp)
                result = self.mt5.order_send(request)
                if result and result.retcode == 10009:
                    log.info("Position %s modified successfully", ticket)
                else:
                    retcode = result.retcode if result else "None"
                    comment = result.comment if result else "no result"
                    log.error("Position modify failed: retcode=%s comment=%s", retcode, comment)
                return result
        except Exception:
            log.exception("modify_position failed — bridge may be disconnected")
            self._connected = False
            return None
