# BUY Strategy Research Findings

## Approach

Testing BUY strategies on **sell-heavy 60-day data** (2026-04-09 to 2026-06-08).
If a BUY strategy profits in a bearish market, it has genuine edge.

## Phase 1: Single-Condition Screening (74 strategies)

Ran all 74 single-condition BUY expressions on 60-day data. Most lose money alone — expected,
since a single condition is too broad. Best survivors (closest to breakeven):

| Expression | PF | Trades | Net |
|-----------|---:|-------:|----:|
| `rsi14_M5.closed_rsi < 40` | 1.00 | 369 | +204 |
| `ema50_M15.ema_slope == RISING` | 0.98 | 87 | -570 |
| `rsi14_M5.closed_cross == CROSS_UP_30` | 0.95 | 122 | -1,380 |
| `dc_M15.closed_lower_wick_rej is TRUE` | 0.93 | 221 | -2,783 |
| `dc_M5.closed_lower_wick_rej is TRUE` | 0.93 | 472 | -7,163 |

**Key insight:** EMA50 M15 rising was the most selective (87 trades) and closest to profitable alone.

## Phase 2: Filter Layering on 1-Week Data

Tested combinations with extra filters on `sample.csv` (1 week):

### Best filter: `candle_M1.closed_is_bullish is TRUE`
- Adds confirmation that the entry candle is green
- Improved most strategies by 0.05-0.10 PF

### EMA50 is the standout indicator family
- `ema50_M15.closed_price_vs_ema == ABOVE` → PF 1.01
- `ema50_M15.ema_slope == RISING` → PF 1.04
- Other EMAs (9, 21, 200) all worse

### MACD M15 bull flip
- PF 1.22, 19 trades, DD 9.9% — best single result on 1-week data
- Event-driven (histogram flip) = precise entries

## Phase 3: Combo Discovery

### The Winner: EMA50 Rising + DC M15 Wick Rejection + UT Bot H1 Bullish

**Logic:** Uptrend (EMA50 rising) + price bounces off channel floor (DC wick rej) + hourly trend confirms (UT Bot H1 bullish). Classic "buy the dip in an uptrend at support."

#### 60-day results (the real test):

| SL | RR | Trades | WR% | PF | Net | DD% |
|---:|---:|-------:|----:|---:|----:|----:|
| 3.0 | 2.0 | 32 | 50.0% | **1.88** | +$10,200 | 22.6% |
| 3.0 | 1.5 | 32 | 53.1% | **1.63** | +$5,834 | 22.5% |
| 4.0 | 1.5 | 32 | 53.1% | **1.64** | +$5,826 | 22.5% |
| 5.0 | 1.0 | 31 | 61.3% | **1.57** | +$3,650 | 22.9% |
| 6.0 | 1.0 | 31 | 61.3% | **1.52** | +$3,636 | 18.9% |
| 3.0 | 1.0 | 32 | 59.4% | **1.42** | +$2,967 | 22.9% |

10 out of 18 SL/RR combinations were profitable.

#### Recommended settings:
- **Production pick: SL=4, RR=1.5** — PF 1.64, 53% WR, +$5,826, DD 22.5%
- **Conservative: SL=5, RR=1.0** — PF 1.57, 61% WR, +$3,650, DD 22.9%
- **Aggressive: SL=3, RR=2.0** — PF 1.88, 50% WR, +$10,200, DD 22.6%

## Key Lessons

### DC Wick Rejection Timeframe
| TF | 60d Trades | 60d PF | Verdict |
|:---|----------:|---------:|:--------|
| M1 | ~many | 0.74 | Too noisy |
| M3 | 263 | 0.88 | Overfits on small data, fails on 60d |
| M5 | ~100+ | 0.93 | Borderline |
| **M15** | **32** | **1.42-1.88** | **Winner — real structural signal** |

**Rule:** Use M15+ for structural signals (DC zones, wick rejections). Lower timeframes produce too many false signals.

### DC M3 Overfitting Example
- 1-week `sample.csv`: DC M3 + UT M15 → PF 2.24, 25 trades ★
- 60-day `XAUUSD_M1_60d.csv`: same combo → PF 0.88, 263 trades ✗

The 1-week result was a lucky sample. Always validate on the longest dataset available.

### UT Bot Bias Timeframe (1-week data, not yet validated on 60d)
| TF | Best PF | Consistency |
|:---|--------:|:------------|
| M10 | 2.12 | 9/9 profitable |
| M15 | 2.24 | 8/9 profitable |
| H1 | 1.88 | 10/18 profitable (60d validated) |

H1 is the only one validated on 60-day data. M10/M15 results are from 1-week only.

### SL/RR Patterns
- **Tight SL (3-5) beats wide SL (7.5-10)** — this strategy catches bounce entries where rejection is quick
- **RR 1.0-1.5 is the safe zone** — higher RR drops win rate too much
- **Above SL=6, PF collapses** — holding losers too long

## Strategy Expression (ready for config)

```yaml
name: ema50_dc_wick_h1_buy
enabled: true
priority: 50
sl_dollars: 4.0
reward_ratio: 1.5
breakeven_pct: 0.0
partial_tp: false
description: "EMA50 M15 rising + DC M15 lower wick rejection + UT Bot H1 bullish"
buy:
  - ema50_M15.ema_slope == RISING
  - dc_M15.closed_lower_wick_rej is TRUE
  - utbot_H1.closed_bias == BULLISH
sell: []
```

## Next Steps

- [ ] Validate UT Bot M10/M15 bias versions on 60-day data
- [ ] Test with breakeven_pct 0.3-0.5 to lock in profits
- [ ] Add liquidity swing zones as a new indicator (support/resistance from pivot structure)
- [ ] Build sell-side strategies using same methodology
- [ ] Get bullish 60-day data sample to cross-validate
