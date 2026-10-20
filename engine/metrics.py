import numpy as np
import pandas as pd


def compute_metrics(trades, equity_curve, initial_deposit):
    m = {"initial_deposit": initial_deposit}
    if not trades:
        m.update({
            "final_balance": initial_deposit, "final_equity": initial_deposit,
            "net_profit": 0.0, "gross_profit": 0.0, "gross_loss": 0.0,
            "profit_factor": None, "total_trades": 0,
            "winning_trades": 0, "losing_trades": 0, "win_rate": None,
            "avg_win": None, "avg_loss": None,
            "largest_win": 0.0, "largest_loss": 0.0,
            "max_drawdown": 0.0, "max_drawdown_pct": 0.0,
            "sharpe": None, "sortino": None, "recovery_factor": None,
        })
        return m

    pnls = np.array([t.pnl for t in trades], dtype=float)
    wins = pnls[pnls > 0]
    losses = pnls[pnls < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    net_profit = float(pnls.sum())
    final_balance = initial_deposit + net_profit

    eq = equity_curve["equity"].values.astype(float) if len(equity_curve) else np.array([initial_deposit])
    running_max = np.maximum.accumulate(eq)
    dd = eq - running_max
    dd_pct = (dd / np.where(running_max == 0, 1, running_max)) * 100
    max_dd = float(-dd.min()) if len(dd) else 0.0
    max_dd_pct = float(-dd_pct.min()) if len(dd_pct) else 0.0

    rets = np.diff(eq) / np.where(eq[:-1] == 0, 1, eq[:-1])
    sharpe = float(np.sqrt(252) * rets.mean() / rets.std()) if len(rets) > 1 and rets.std() > 0 else None
    downside = rets[rets < 0]
    sortino = float(np.sqrt(252) * rets.mean() / downside.std()) if len(downside) > 1 and downside.std() > 0 else None

    m.update({
        "final_balance": final_balance, "final_equity": float(eq[-1]),
        "net_profit": net_profit, "gross_profit": gross_profit, "gross_loss": gross_loss,
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "total_trades": len(trades),
        "winning_trades": int(len(wins)), "losing_trades": int(len(losses)),
        "win_rate": (len(wins) / len(trades) * 100) if trades else None,
        "avg_win": float(wins.mean()) if len(wins) else None,
        "avg_loss": float(losses.mean()) if len(losses) else None,
        "largest_win": float(wins.max()) if len(wins) else 0.0,
        "largest_loss": float(losses.min()) if len(losses) else 0.0,
        "max_drawdown": max_dd, "max_drawdown_pct": max_dd_pct,
        "sharpe": sharpe, "sortino": sortino,
        "recovery_factor": (net_profit / max_dd) if max_dd > 0 else None,
    })
    return m
