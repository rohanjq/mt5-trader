# Bollinger VWAP Range Fade

**Status**: INACTIVE (available for config)
**Backtest**: PF 0.66 | WR 42.9% | 21 trades/week — consistent loser
**Type**: Mean reversion / range trading

## How it works

Enters when ADX shows ranging market, RSI15 is neutral (45-55), price re-enters Bollinger Bands from outside, and is near VWAP. Designed for sideways days but fails when trends develop.

## Expression

```yaml
- name: "gold_bb_range_fade"
  enabled: true
  priority: 45
  sl_dollars: 3.0
  reward_ratio: 1.0
  breakeven_pct: 0.0
  partial_tp: false
  description: "BB VWAP range fade (ADX ranging + BB re-entry)"
  buy:
    - adx14_M5.closed_trend_strength == RANGING
    - rsi14_M15.closed_rsi > 45
    - rsi14_M15.closed_rsi < 55
    - bb20d2_M1.closed_reenter_from_below is TRUE
    - bb20d2_M1.bb_squeeze is_not TRUE
    - vwap_M1.running_dist_pct < 3.0
    - vwap_M1.running_dist_pct > -3.0
  sell:
    - adx14_M5.closed_trend_strength == RANGING
    - rsi14_M15.closed_rsi > 45
    - rsi14_M15.closed_rsi < 55
    - bb20d2_M1.closed_reenter_from_above is TRUE
    - bb20d2_M1.bb_squeeze is_not TRUE
    - vwap_M1.running_dist_pct < 3.0
    - vwap_M1.running_dist_pct > -3.0
```
