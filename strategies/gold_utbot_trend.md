# UT Bot Multi-TF Trend

**Status**: ACTIVE (in config-gold.yaml)
**Backtest**: PF 1.36 | WR 54.1% | 61 trades/week | DD 21.1%
**Best performer** — highest profit factor and lowest drawdown of all strategies.

## How it works

Fires when UT Bot M1 gives a BUY/SELL signal and M5 + M15 UT Bot bias agrees. VWAP filter ensures we trade with the session flow.

## Expression

```yaml
- name: "gold_utbot_trend"
  enabled: true
  priority: 50
  sl_dollars: 5.0
  reward_ratio: 1.0
  breakeven_pct: 0.0
  partial_tp: false
  description: "UT Bot M1 signal + M5/M15 trend alignment + VWAP"
  buy:
    - utbot_M1.closed_signal == BUY
    - utbot_M5.closed_bias == BULLISH
    - utbot_M15.closed_bias == BULLISH
    - vwap_M1.closed_price_vs_vwap == ABOVE
  sell:
    - utbot_M1.closed_signal == SELL
    - utbot_M5.closed_bias == BEARISH
    - utbot_M15.closed_bias == BEARISH
    - vwap_M1.closed_price_vs_vwap == BELOW
```
