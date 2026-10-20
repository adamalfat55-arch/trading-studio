from engine import indicators as ind
from strategies.base import Strategy


class EMACross(Strategy):
    def __init__(self, fast=20, slow=50, size=1.0):
        self.fast, self.slow, self.size = fast, slow, size

    def on_bar(self, ctx, bar):
        if len(ctx.bars) < self.slow + 2:
            return None
        close = ctx.bars["close"]
        f = ind.ema(close, self.fast)
        s = ind.ema(close, self.slow)
        fp, sp = float(f.iloc[-2]), float(s.iloc[-2])
        fc, sc = float(f.iloc[-1]), float(s.iloc[-1])
        if ctx.position is None:
            if fp <= sp and fc > sc:
                return ctx.buy(size=self.size)
            if fp >= sp and fc < sc:
                return ctx.sell(size=self.size)
        return None


class RSIMeanReversion(Strategy):
    def __init__(self, period=14, oversold=30, overbought=70,
                 size=1.0, sl_pct=0.02, tp_pct=0.04):
        self.period, self.oversold, self.overbought = period, oversold, overbought
        self.size, self.sl_pct, self.tp_pct = size, sl_pct, tp_pct

    def on_bar(self, ctx, bar):
        if len(ctx.bars) < self.period + 2:
            return None
        r = float(ind.rsi(ctx.bars["close"], self.period).iloc[-2])
        if ctx.position is None:
            if r < self.oversold:
                return ctx.buy(size=self.size, sl=bar.close*(1-self.sl_pct), tp=bar.close*(1+self.tp_pct))
            if r > self.overbought:
                return ctx.sell(size=self.size, sl=bar.close*(1+self.sl_pct), tp=bar.close*(1-self.tp_pct))
        return None
