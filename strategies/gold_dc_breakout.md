# DC Compression Breakout

**Status**: ACTIVE (in config-gold.yaml)
**Backtest**: PF 1.10 | WR 40% | 20 trades/week
**Secondary strategy** — low frequency, higher conviction breakout entries.

## How it works

Waits for Donchian Channel compression + Bollinger Band squeeze (low volatility), then enters on expansion when ATR confirms momentum and ADX shows trending. EMA200+EMA50 filter for higher TF trend.

## Expression

```yaml
- name: "gold_dc_breakout"
  enabled: true
  priority: 40
  sl_dollars: 6.0
  reward_ratio: 1.0
  breakeven_pct: 0.0
  partial_tp: false
  description: "Compression breakout (DC+BB squeeze → expansion)"
  buy:
    - ema50_M5.closed_price_vs_ema == ABOVE
    - ema200_M5.closed_price_vs_ema == ABOVE
    - dc_M1.dc_compressed is TRUE
    - bb20d2_M1.bb_squeeze is TRUE
    - atr14_M1.volatility_state in EXPANDING,ABOVE_AVG
    - dc_M1.closed_price_zone == UPPER
    - adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND
    - vwap_M1.closed_price_vs_vwap == ABOVE
  sell:
    - ema50_M5.closed_price_vs_ema == BELOW
    - ema200_M5.closed_price_vs_ema == BELOW
    - dc_M1.dc_compressed is TRUE
    - bb20d2_M1.bb_squeeze is TRUE
    - atr14_M1.volatility_state in EXPANDING,ABOVE_AVG
    - dc_M1.closed_price_zone == LOWER
    - adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND
    - vwap_M1.closed_price_vs_vwap == BELOW
```
