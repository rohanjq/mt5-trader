# UT Bot M1 + M15 Bias

**Status**: INACTIVE (available for config)
**Backtest**: Not tested individually at 1:1 RR yet
**Type**: Simplified multi-TF trend following

## How it works

Simpler version of gold_utbot_trend — uses M1 signal + M15 bias (skips M5), adds EMA50 M5 and VWAP as trend filters. Higher frequency than the 3-TF version.

## Expression

```yaml
- name: "gold_utbot_m1_m15"
  enabled: true
  priority: 40
  sl_dollars: 4.0
  reward_ratio: 1.0
  breakeven_pct: 0.0
  partial_tp: false
  description: "UT Bot M1 signal + M15 bias + M5 trend + VWAP"
  buy:
    - utbot_M1.closed_signal == BUY
    - utbot_M15.closed_bias == BULLISH
    - ema50_M5.closed_price_vs_ema == ABOVE
    - vwap_M1.closed_price_vs_vwap == ABOVE
  sell:
    - utbot_M1.closed_signal == SELL
    - utbot_M15.closed_bias == BEARISH
    - ema50_M5.closed_price_vs_ema == BELOW
    - vwap_M1.closed_price_vs_vwap == BELOW
```
