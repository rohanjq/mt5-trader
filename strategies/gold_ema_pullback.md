# EMA Pullback with VWAP

**Status**: INACTIVE (available for config)
**Backtest**: Not tested individually yet
**Type**: Pullback entry in established trend

## How it works

Enters when M5 EMA50+EMA200 confirm trend, EMA50 slope is rising, RSI14 crosses back above 50 (reclaims momentum), and price is above VWAP.

## Expression

```yaml
- name: "gold_ema_pullback"
  enabled: true
  priority: 42
  sl_dollars: 4.0
  reward_ratio: 1.0
  breakeven_pct: 0.0
  partial_tp: false
  description: "EMA pullback + VWAP filter (M5 trend + M1 RSI)"
  buy:
    - ema50_M5.closed_price_vs_ema == ABOVE
    - ema200_M5.closed_price_vs_ema == ABOVE
    - ema50_M5.ema_slope == RISING
    - rsi14_M1.closed_cross in CROSS_UP_50,CROSS_UP_52
    - vwap_M1.closed_price_vs_vwap == ABOVE
  sell:
    - ema50_M5.closed_price_vs_ema == BELOW
    - ema200_M5.closed_price_vs_ema == BELOW
    - ema50_M5.ema_slope == FALLING
    - rsi14_M1.closed_cross == CROSS_DOWN_50
    - vwap_M1.closed_price_vs_vwap == BELOW
```
