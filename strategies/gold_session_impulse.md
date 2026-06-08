# Session Impulse EMA ADX

**Status**: INACTIVE (available for config)
**Backtest**: PF 0.95 | WR 42.4% | 66 trades/week — net loser at current settings
**Type**: Trend following / momentum

## How it works

Fires when all timeframes align: EMA200+EMA50 M5 trend, EMA9+EMA21 M1 momentum, ADX trending with bullish DI, ATR expanding, above VWAP. Many conditions = high conviction but loses on whipsaw days.

## Expression

```yaml
- name: "gold_session_impulse"
  enabled: true
  priority: 35
  sl_dollars: 5.0
  reward_ratio: 1.0
  breakeven_pct: 0.0
  partial_tp: false
  description: "Session impulse EMA ADX trend (M5 regime + M1 momentum)"
  buy:
    - ema200_M5.closed_price_vs_ema == ABOVE
    - ema50_M5.closed_price_vs_ema == ABOVE
    - ema50_M5.ema_slope == RISING
    - rsi14_M5.closed_rsi > 55
    - ema9_M1.closed_price_vs_ema == ABOVE
    - ema21_M1.closed_price_vs_ema == ABOVE
    - adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND
    - adx14_M1.closed_di_bias == BULLISH
    - atr14_M1.volatility_state in EXPANDING,ABOVE_AVG
    - bb20d2_M1.bb_squeeze is_not TRUE
    - vwap_M1.closed_price_vs_vwap == ABOVE
  sell:
    - ema200_M5.closed_price_vs_ema == BELOW
    - ema50_M5.closed_price_vs_ema == BELOW
    - ema50_M5.ema_slope == FALLING
    - rsi14_M5.closed_rsi < 45
    - ema9_M1.closed_price_vs_ema == BELOW
    - ema21_M1.closed_price_vs_ema == BELOW
    - adx14_M1.closed_trend_strength in TRENDING,STRONG_TREND
    - adx14_M1.closed_di_bias == BEARISH
    - atr14_M1.volatility_state in EXPANDING,ABOVE_AVG
    - bb20d2_M1.bb_squeeze is_not TRUE
    - vwap_M1.closed_price_vs_vwap == BELOW
```
