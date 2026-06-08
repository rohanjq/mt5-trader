"""Statistics computation and reporting for backtest results."""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

from backtest.simulator import ClosedTrade, Simulator

log = logging.getLogger(__name__)


def compute_stats(simulator: Simulator) -> dict:
    """Compute comprehensive statistics from the simulator results."""
    trades = simulator.closed_trades

    # Separate main and runner trades
    main_trades = [t for t in trades if not t.is_runner]
    runner_trades = [t for t in trades if t.is_runner]

    stats = {
        "summary": _summary(trades, simulator),
        "by_direction": {
            "long": _direction_stats([t for t in main_trades if t.direction == "BUY"]),
            "short": _direction_stats([t for t in main_trades if t.direction == "SELL"]),
        },
        "by_strategy": _strategy_stats(main_trades),
        "by_exit": _exit_stats(main_trades),
        "runners": _summary_basic(runner_trades) if runner_trades else None,
        "drawdown": {
            "max_drawdown_pct": round(simulator.max_drawdown, 2),
            "peak_balance": round(simulator.peak_balance, 2),
        },
    }
    return stats


def _summary(trades: list[ClosedTrade], sim: Simulator) -> dict:
    """Overall summary statistics."""
    main_trades = [t for t in trades if not t.is_runner]
    if not main_trades:
        return {"total_trades": 0, "net_profit": 0}

    wins = [t for t in main_trades if t.profit > 0]
    losses = [t for t in main_trades if t.profit < 0]
    breakevens = [t for t in main_trades if t.profit == 0]

    gross_profit = sum(t.profit for t in wins) if wins else 0
    gross_loss = abs(sum(t.profit for t in losses)) if losses else 0
    net_profit = sum(t.profit for t in main_trades)

    # Average win/loss
    avg_win = gross_profit / len(wins) if wins else 0
    avg_loss = gross_loss / len(losses) if losses else 0

    # Profit factor
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Win rate
    win_rate = len(wins) / len(main_trades) * 100

    # Average trade duration
    durations = [(t.exit_time - t.entry_time).total_seconds() / 60 for t in main_trades]
    avg_duration = sum(durations) / len(durations)

    # Expectancy = (win_rate × avg_win) - (loss_rate × avg_loss)
    expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)

    # Max consecutive losses
    max_consec_loss = _max_consecutive(main_trades, lambda t: t.profit < 0)
    max_consec_win = _max_consecutive(main_trades, lambda t: t.profit > 0)

    # Return on initial
    roi = (sim.balance - sim.initial_balance) / sim.initial_balance * 100

    return {
        "total_trades": len(main_trades),
        "wins": len(wins),
        "losses": len(losses),
        "breakevens": len(breakevens),
        "win_rate_pct": round(win_rate, 1),
        "net_profit": round(net_profit, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "expectancy": round(expectancy, 2),
        "avg_duration_min": round(avg_duration, 1),
        "max_consecutive_wins": max_consec_win,
        "max_consecutive_losses": max_consec_loss,
        "initial_balance": round(sim.initial_balance, 2),
        "final_balance": round(sim.balance, 2),
        "roi_pct": round(roi, 1),
    }


def _summary_basic(trades: list[ClosedTrade]) -> dict:
    """Basic summary for a subset of trades."""
    if not trades:
        return {"count": 0}
    wins = [t for t in trades if t.profit > 0]
    net = sum(t.profit for t in trades)
    return {
        "count": len(trades),
        "wins": len(wins),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "net_profit": round(net, 2),
    }


def _direction_stats(trades: list[ClosedTrade]) -> dict:
    return _summary_basic(trades)


def _strategy_stats(trades: list[ClosedTrade]) -> dict:
    """Per-strategy breakdown."""
    by_strat: dict[str, list[ClosedTrade]] = {}
    for t in trades:
        name = t.rule_name.replace("_runner", "")
        by_strat.setdefault(name, []).append(t)

    result = {}
    for name, strats in sorted(by_strat.items()):
        wins = [t for t in strats if t.profit > 0]
        losses = [t for t in strats if t.profit < 0]
        net = sum(t.profit for t in strats)
        gross_win = sum(t.profit for t in wins) if wins else 0
        gross_loss = abs(sum(t.profit for t in losses)) if losses else 0

        result[name] = {
            "trades": len(strats),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(len(wins) / len(strats) * 100, 1) if strats else 0,
            "net_profit": round(net, 2),
            "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf"),
            "avg_profit": round(net / len(strats), 2) if strats else 0,
        }
    return result


def _exit_stats(trades: list[ClosedTrade]) -> dict:
    """Breakdown by exit reason."""
    by_exit: dict[str, list[ClosedTrade]] = {}
    for t in trades:
        by_exit.setdefault(t.exit_reason, []).append(t)

    result = {}
    for reason, ts in sorted(by_exit.items()):
        result[reason] = {
            "count": len(ts),
            "net_profit": round(sum(t.profit for t in ts), 2),
        }
    return result


def _max_consecutive(trades: list[ClosedTrade], predicate) -> int:
    max_run = 0
    current = 0
    for t in trades:
        if predicate(t):
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run


# ── Output formatting ─────────────────────────────────────────────────────────

def print_report(stats: dict, simulator: Simulator) -> None:
    """Print a formatted backtest report to the console."""
    try:
        from tabulate import tabulate
    except ImportError:
        tabulate = None

    s = stats["summary"]
    print("\n" + "=" * 70)
    print("                    BACKTEST RESULTS")
    print("=" * 70)

    if s.get("total_trades", 0) == 0:
        print("\nNo trades executed.")
        print("=" * 70)
        return

    # Summary
    rows = [
        ["Total Trades", s["total_trades"]],
        ["Win Rate", f"{s['win_rate_pct']}%"],
        ["Net Profit", f"${s['net_profit']:+.2f}"],
        ["ROI", f"{s['roi_pct']:+.1f}%"],
        ["Profit Factor", f"{s['profit_factor']:.2f}"],
        ["Expectancy", f"${s['expectancy']:+.2f}"],
        ["", ""],
        ["Wins / Losses / BE", f"{s['wins']} / {s['losses']} / {s['breakevens']}"],
        ["Avg Win", f"${s['avg_win']:.2f}"],
        ["Avg Loss", f"${s['avg_loss']:.2f}"],
        ["Avg Duration", f"{s['avg_duration_min']:.0f} min"],
        ["Max Consec. Wins", s["max_consecutive_wins"]],
        ["Max Consec. Losses", s["max_consecutive_losses"]],
        ["", ""],
        ["Initial Balance", f"${s['initial_balance']:.2f}"],
        ["Final Balance", f"${s['final_balance']:.2f}"],
        ["Max Drawdown", f"{stats['drawdown']['max_drawdown_pct']:.1f}%"],
        ["Peak Balance", f"${stats['drawdown']['peak_balance']:.2f}"],
    ]

    if tabulate:
        print(tabulate(rows, tablefmt="simple"))
    else:
        for label, val in rows:
            if label:
                print(f"  {label:<25} {val}")
            else:
                print()

    # Direction breakdown
    print("\n── By Direction ──")
    for dir_name in ("long", "short"):
        d = stats["by_direction"][dir_name]
        if d.get("count", 0) > 0:
            print(f"  {dir_name.upper()}: {d['count']} trades, "
                  f"{d['win_rate_pct']}% win, ${d['net_profit']:+.2f}")

    # Strategy breakdown
    if stats["by_strategy"]:
        print("\n── By Strategy ──")
        strat_rows = []
        for name, st in stats["by_strategy"].items():
            strat_rows.append([
                name,
                st["trades"],
                f"{st['win_rate_pct']}%",
                f"${st['net_profit']:+.2f}",
                f"{st['profit_factor']:.2f}",
                f"${st['avg_profit']:+.2f}",
            ])
        if tabulate:
            print(tabulate(
                strat_rows,
                headers=["Strategy", "Trades", "Win%", "Net P&L", "PF", "Avg"],
                tablefmt="simple",
            ))
        else:
            for row in strat_rows:
                print(f"  {row[0]:<30} {row[1]:>3} trades  {row[2]:>6}  {row[3]:>10}  PF={row[4]}")

    # Exit breakdown
    if stats["by_exit"]:
        print("\n── By Exit Reason ──")
        for reason, data in stats["by_exit"].items():
            print(f"  {reason:<15} {data['count']:>4} trades  ${data['net_profit']:+.2f}")

    # Runners
    if stats.get("runners"):
        r = stats["runners"]
        print(f"\n── Runners ──")
        print(f"  {r['count']} trades, {r['win_rate_pct']}% win, ${r['net_profit']:+.2f}")

    print("\n" + "=" * 70)


def print_trade_log(simulator: Simulator, limit: int = 50) -> None:
    """Print individual trade log."""
    trades = [t for t in simulator.closed_trades if not t.is_runner]
    if not trades:
        print("No trades to display.")
        return

    try:
        from tabulate import tabulate
    except ImportError:
        tabulate = None

    shown = trades[:limit] if limit else trades
    rows = []
    for t in shown:
        rows.append([
            t.entry_time.strftime("%m/%d %H:%M"),
            t.direction[:1],
            t.rule_name[:25],
            f"{t.entry_price:.2f}",
            f"{t.exit_price:.2f}",
            f"${t.profit:+.2f}",
            t.exit_reason,
        ])

    print(f"\n── Trade Log (showing {len(shown)}/{len(trades)}) ──")
    if tabulate:
        print(tabulate(
            rows,
            headers=["Time", "Dir", "Strategy", "Entry", "Exit", "P&L", "Exit"],
            tablefmt="simple",
        ))
    else:
        for row in rows:
            print(f"  {row[0]}  {row[1]}  {row[2]:<25}  {row[3]}→{row[4]}  {row[5]:>8}  {row[6]}")


def save_results(stats: dict, simulator: Simulator, path: str | Path) -> None:
    """Save detailed results to JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Trade log
    trade_log = []
    for t in simulator.closed_trades:
        trade_log.append({
            "id": t.id,
            "direction": t.direction,
            "rule": t.rule_name,
            "entry_price": round(t.entry_price, 5),
            "entry_time": t.entry_time.isoformat(),
            "exit_price": round(t.exit_price, 5),
            "exit_time": t.exit_time.isoformat(),
            "volume": t.volume,
            "profit": round(t.profit, 2),
            "exit_reason": t.exit_reason,
            "is_runner": t.is_runner,
        })

    output = {
        "stats": stats,
        "trades": trade_log,
        "equity_curve_length": len(simulator.equity_curve),
    }

    # Handle inf values for JSON serialization
    def clean(obj):
        if isinstance(obj, float) and (obj == float("inf") or obj == float("-inf")):
            return str(obj)
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean(v) for v in obj]
        return obj

    with open(path, "w") as f:
        json.dump(clean(output), f, indent=2)

    log.info("Results saved to %s", path)
    print(f"\nResults saved to {path}")
