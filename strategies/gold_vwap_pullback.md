# VWAP Pullback Continuation

**Status**: INACTIVE (available for config)
**Backtest**: Not individually tested at 1:1 RR yet
**Type**: Pullback / mean-reversion in trend

## How it works

Enters after a pullback into VWAP zone during an established M5 trend. RSI2 extreme oversold confirms the dip, then RSI14 > 50 and EMA9 above confirm recovery. EMA200 M15 for macro trend.

## Expression

```yaml
- name: "gold_vwap_pullback"
  enabled: true
  priority: 30
  sl_dollars: 4.2
  reward_ratio: 1.0
  breakeven_pct: 0.0
  partial_tp: false
  description: "VWAP pullback continuation (M5 trend + M1 RSI reclaim)"
  buy:
    - ema200_M15.closed_price_vs_ema == ABOVE
    - ema21_M5.closed_price_vs_ema == ABOVE
    - ema50_M5.closed_price_vs_ema == ABOVE
    - adx14_M5.closed_trend_strength in WEAK_TREND,TRENDING,STRONG_TREND
    - rsi2_M1.closed_zone == EXTREME_OS
    - ema9_M1.closed_price_vs_ema == ABOVE
    - rsi14_M1.closed_rsi > 50
    - vwap_M1.closed_price_vs_vwap == ABOVE
  sell:
    - ema200_M15.closed_price_vs_ema == BELOW
    - ema21_M5.closed_price_vs_ema == BELOW
    - ema50_M5.closed_price_vs_ema == BELOW
    - adx14_M5.closed_trend_strength in WEAK_TREND,TRENDING,STRONG_TREND
    - rsi2_M1.closed_zone == EXTREME_OB
    - ema9_M1.closed_price_vs_ema == BELOW
    - rsi14_M1.closed_rsi < 50
    - vwap_M1.closed_price_vs_vwap == BELOW
```
