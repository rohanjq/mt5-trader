# MT5 Trader - Project Overview

## Architecture
- Python 3.12, uv package manager, mt5linux + rpyc (localhost:8001)
- Signal CSVs written by MQL5 EA (SignalMaster.mq5) at `../MetaTrader5-Docker/data/signals/`
- YAML expression rules evaluate signal conditions → trade via MT5
- Symbols: XAUUSD (magic=200), BTCUSDT (magic=100)
- Broker: PXBT Trading MT5 Terminal (demo)

## Key Files
- `core/engine.py` — main loop, reads signals, evaluates rules
- `core/mt5_client.py` — MT5 rpyc bridge (get_tick uses self._lock)
- `rules/expression.py` — YAML expression parser, regex: `^([\w.]+)\.(\w+)\s+...`
- `trade/initiator.py` — risk sizing, order execution, runner split
- `trade/manager.py` — position monitoring, SL/TP tracking, deal history P&L
- `signals/generic.py` — reads `<SYMBOL>_<indicator>_<TF>.csv` key-value CSVs
- `config-gold.yaml`, `config-btc.yaml` — strategy configs

## Signal Sources (Gold)
utbot(M1,M3,M5,M15), dc(M1,M5,M15), ema9(M1), ema21(M1,M5), ema50(M5,M15),
ema200(M5,M15), rsi14(M1,M5,M15), rsi2(M1), adx14(M1,M5), macd12_26_9(M1),
stoch5_3_3(M1), bb20d2(M1), atr14(M1,M5), vwap(M1,M5)

## Gold Strategies (7)
1. gold_vwap_pullback (8 conds, SL $4.20, RR 1.25)
2. gold_session_impulse (11 conds, SL $5, RR 1.5)
3. gold_dc_breakout (8 conds, SL $6, RR 1.8)
4. gold_bb_range_fade (7 conds, SL $3, RR 1.0)
5. gold_utbot_trend (4 conds, SL $5, RR 1.25)
6. gold_ema_pullback (5 conds, SL $4, RR 1.25)
7. gold_utbot_m1_m15 (2 conds, SL $4, RR 1.2)

## Risk Sizing
risk_amount = balance × (risk_pct/100), cash_per_lot = (sl_dollars/tick_size) × tick_value
volume = risk_amount / cash_per_lot, split 80% main (with TP) + 20% runner (no TP)

## Known Issues Fixed
- rpyc ignores `position=` kwarg in history_deals_get → filter client-side
- get_tick after order hangs (deadlock) → use result.price instead
- VWAP dist_pct is already percentage (×100 in EA), not fraction
- Runner closes count as separate consecutive losses (not yet fixed)

## Deploy
Server: `git pull && uv sync && uv run python main.py --config config-gold.yaml`
GitHub: https://github.com/rohanjq/mt5-trader (branch: main)
MQL5 EA repo: /Users/rohan.arora/repos/MetaTrader5-Docker
