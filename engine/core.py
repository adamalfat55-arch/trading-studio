from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import pandas as pd


@dataclass
class Bar:
    time: pd.Timestamp
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Trade:
    id: int
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    size: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    commission: float = 0.0


@dataclass
class Context:
    symbol: str
    timeframe: str
    bars: pd.DataFrame
    i: int
    balance: float
    equity: float
    position: Optional[Trade]
    trades: List[Trade]
    params: Dict[str, Any] = field(default_factory=dict)

    def buy(self, size=1.0, sl=None, tp=None):
        return ("open", "buy", size, sl, tp)

    def sell(self, size=1.0, sl=None, tp=None):
        return ("open", "sell", size, sl, tp)

    def close(self):
        return ("close", None, 0, None, None)


class Backtester:
    def __init__(self, df, strategy, symbol, timeframe,
                 initial_deposit=10000.0, commission_per_lot=0.0,
                 spread=0.0, contract_size=1.0, params=None):
        self.df = df.reset_index(drop=True)
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.initial_deposit = float(initial_deposit)
        self.balance = float(initial_deposit)
        self.commission = float(commission_per_lot)
        self.spread = float(spread)
        self.contract_size = float(contract_size)
        self.params = params or {}
        self.trade_id = 0
        self.trades = []
        self.position = None
        self.equity_rows = []
        self.logs = []

    def _fill(self, raw, side):
        half = self.spread / 2.0
        return raw + half if side == "buy" else raw - half

    def _open(self, side, size, sl, tp, ts, price):
        fill = self._fill(price, side)
        comm = self.commission * size
        t = Trade(self.trade_id, side, ts, fill, size, sl, tp, commission=comm)
        self.trade_id += 1
        self.position = t
        self.logs.append(f"[{ts}] OPEN {side} {size}@{fill:.5f}")

    def _close(self, ts, price, reason):
        if not self.position:
            return
        t = self.position
        fill = self._fill(price, "sell" if t.side == "buy" else "buy")
        pnl = (fill - t.entry_price) * t.size * self.contract_size if t.side == "buy" else (t.entry_price - fill) * t.size * self.contract_size
        pnl -= t.commission
        t.exit_time, t.exit_price, t.exit_reason, t.pnl = ts, fill, reason, pnl
        self.balance += pnl
        self.trades.append(t)
        self.position = None
        self.logs.append(f"[{ts}] CLOSE {t.side} @{fill:.5f} pnl={pnl:.2f} ({reason})")

    def _check_sl_tp(self, bar):
        if not self.position:
            return
        t = self.position
        if t.side == "buy":
            if t.sl is not None and bar.low <= t.sl:
                self._close(bar.time, min(bar.open, t.sl), "SL"); return
            if t.tp is not None and bar.high >= t.tp:
                self._close(bar.time, max(bar.open, t.tp), "TP"); return
        else:
            if t.sl is not None and bar.high >= t.sl:
                self._close(bar.time, max(bar.open, t.sl), "SL"); return
            if t.tp is not None and bar.low <= t.tp:
                self._close(bar.time, min(bar.open, t.tp), "TP"); return

    def _equity(self, price):
        if not self.position:
            return self.balance
        t = self.position
        open_pnl = (price - t.entry_price) * t.size * self.contract_size if t.side == "buy" else (t.entry_price - price) * t.size * self.contract_size
        return self.balance + open_pnl - t.commission

    def run(self):
        self.strategy.on_start(self.params)
        for i in range(len(self.df)):
            row = self.df.iloc[i]
            bar = Bar(row["time"], float(row["open"]), float(row["high"]),
                      float(row["low"]), float(row["close"]), float(row.get("volume", 0.0)))
            self._check_sl_tp(bar)
            visible = self.df.iloc[: i + 1]
            ctx = Context(symbol=self.symbol, timeframe=self.timeframe,
                          bars=visible, i=i, balance=self.balance,
                          equity=self._equity(bar.close),
                          position=self.position, trades=list(self.trades),
                          params=self.params)
            action = self.strategy.on_bar(ctx, bar)
            if action and action[0] == "open" and self.position is None:
                _, side, size, sl, tp = action
                self._open(side, size, sl, tp, bar.time, bar.close)
            elif action and action[0] == "close" and self.position:
                self._close(bar.time, bar.close, "manual")
            self.equity_rows.append({"time": bar.time, "balance": self.balance,
                                     "equity": self._equity(bar.close), "close": bar.close})
        if self.position:
            last = self.df.iloc[-1]
            self._close(last["time"], last["close"], "end_of_data")
            self.equity_rows.append({"time": last["time"], "balance": self.balance,
                                     "equity": self.balance, "close": last["close"]})
        self.strategy.on_end(self.params)
        return {"trades": self.trades, "equity_curve": pd.DataFrame(self.equity_rows),
                "bars": self.df, "logs": self.logs,
                "initial_deposit": self.initial_deposit, "final_balance": self.balance}
