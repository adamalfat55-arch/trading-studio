import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from engine.core import Backtester
from engine.metrics import compute_metrics
from strategies.examples import EMACross, RSIMeanReversion
from data import loader

st.set_page_config(page_title="Trading Studio", layout="centered")

CSS = """
<style>
html, body { font-size: 15px; }
.block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 100%; }
h1 { font-size: 1.6rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1.05rem !important; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

st.title("Trading Strategy Studio")
st.caption("Phase 1 - Real event-driven backtesting - Mobile-first")

tabs = st.tabs(["Setup", "Data", "Strategy", "Run", "Results"])

with tabs[0]:
    st.subheader("Account & Execution")
    c1, c2 = st.columns(2)
    with c1:
        deposit = st.number_input("Initial deposit", 100.0, 1_000_000.0, 10000.0, 500.0)
        commission = st.number_input("Commission / lot", 0.0, 100.0, 0.0, 0.5)
    with c2:
        spread = st.number_input("Spread (price units)", 0.0, 100.0, 0.0, 0.01, format="%.5f")
        contract = st.number_input("Contract size", 1.0, 1_000_000.0, 1.0, 1.0)
    st.info("SL/TP within the same candle: SL is assumed first (conservative).")

with tabs[1]:
    st.subheader("Market Data")
    src = st.radio("Source", ["Synthetic (test)", "Binance", "CSV upload"])
    df = None
    if src == "Synthetic (test)":
        n = st.slider("Bars", 500, 5000, 2000, 500)
        df = loader.synthetic_data(n)
        st.warning("Synthetic random-walk - do NOT read as real performance.")
    elif src == "Binance":
        sym = st.text_input("Symbol", "BTCUSDT")
        interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h", "4h", "1d"], index=3)
        lim = st.slider("Bars", 100, 1000, 1000, 100)
        if st.button("Download Binance data"):
            try:
                df = loader.load_binance(sym, interval, lim)
                st.session_state["df"] = df
                st.success("Loaded " + str(len(df)) + " bars")
            except Exception as e:
                st.error("Download failed: " + str(e))
        df = st.session_state.get("df")
    else:
        f = st.file_uploader("CSV (time, open, high, low, close[, volume])", type=["csv"])
        if f:
            try:
                df = loader.load_csv(f)
                st.session_state["df"] = df
                st.success("Loaded " + str(len(df)) + " rows")
            except Exception as e:
                st.error(str(e))
        df = st.session_state.get("df")
    if df is not None:
        st.dataframe(df.tail(5), use_container_width=True)

with tabs[2]:
    st.subheader("Strategy")
    choice = st.selectbox("Select", ["EMA Cross", "RSI Mean Reversion"])
    if choice == "EMA Cross":
        fast = st.slider("Fast EMA", 5, 50, 20)
        slow = st.slider("Slow EMA", 20, 200, 50)
        size = st.number_input("Position size", 0.01, 100.0, 1.0, 0.01)
        strat = EMACross(fast=fast, slow=slow, size=size)
    else:
        period = st.slider("RSI period", 5, 30, 14)
        os_ = st.slider("Oversold", 10, 40, 30)
        ob_ = st.slider("Overbought", 60, 90, 70)
        slp = st.slider("SL %", 0.5, 10.0, 2.0) / 100
        tpp = st.slider("TP %", 0.5, 20.0, 4.0) / 100
        strat = RSIMeanReversion(period=period, oversold=os_, overbought=ob_,
                                 sl_pct=slp, tp_pct=tpp)

with tabs[3]:
    st.subheader("Run Backtest")
    df = st.session_state.get("df")
    if df is None:
        st.error("Load data in the Data tab first.")
    else:
        st.write("Data ready: " + str(len(df)) + " bars")
        if st.button("Run Backtest", type="primary"):
            with st.spinner("Running event-driven simulation..."):
                bt = Backtester(df=df, strategy=strat, symbol="TEST", timeframe="1h",
                                initial_deposit=deposit, commission_per_lot=commission,
                                spread=spread, contract_size=contract)
                res = bt.run()
                metrics = compute_metrics(res["trades"], res["equity_curve"], deposit)
                st.session_state["result"] = res
                st.session_state["metrics"] = metrics
            st.success("Done. " + str(len(res["trades"])) + " trades executed.")

with tabs[4]:
    res = st.session_state.get("result")
    metrics = st.session_state.get("metrics")
    if not res:
        st.info("Run a backtest to see results.")
    else:
        st.subheader("Summary")
        m = metrics
        cols = st.columns(2)
        cols[0].metric("Net Profit", "{:.2f}".format(m["net_profit"]))
        cols[1].metric("Trades", m["total_trades"])
        cols = st.columns(2)
        cols[0].metric("Win Rate", "{:.1f}%".format(m["win_rate"]) if m["win_rate"] is not None else "n/a")
        cols[1].metric("Profit Factor", "{:.2f}".format(m["profit_factor"]) if m["profit_factor"] is not None else "n/a")
        cols = st.columns(2)
        cols[0].metric("Max DD", "{:.2f}".format(m["max_drawdown"]))
        cols[1].metric("Max DD %", "{:.2f}%".format(m["max_drawdown_pct"]))
        cols = st.columns(2)
        cols[0].metric("Sharpe", "{:.2f}".format(m["sharpe"]) if m["sharpe"] is not None else "n/a")
        cols[1].metric("Recovery", "{:.2f}".format(m["recovery_factor"]) if m["recovery_factor"] is not None else "n/a")

        st.subheader("Price & Trades")
        bars = res["bars"]
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.7, 0.3], vertical_spacing=0.05,
                            subplot_titles=("Price & Signals", "Equity"))
        fig.add_trace(go.Candlestick(x=bars["time"], open=bars["open"],
                                     high=bars["high"], low=bars["low"],
                                     close=bars["close"], name="Price"), row=1, col=1)
        if res["trades"]:
            buys = [t for t in res["trades"] if t.side == "buy"]
            sells = [t for t in res["trades"] if t.side == "sell"]
            if buys:
                fig.add_trace(go.Scatter(x=[t.entry_time for t in buys],
                    y=[t.entry_price for t in buys], mode="markers",
                    marker=dict(symbol="triangle-up", color="#22c55e", size=10),
                    name="Buy"), row=1, col=1)
            if sells:
                fig.add_trace(go.Scatter(x=[t.entry_time for t in sells],
                    y=[t.entry_price for t in sells], mode="markers",
                    marker=dict(symbol="triangle-down", color="#ef4444", size=10),
                    name="Sell"), row=1, col=1)
            fig.add_trace(go.Scatter(x=[t.exit_time for t in res["trades"]],
                y=[t.exit_price for t in res["trades"]], mode="markers",
                marker=dict(symbol="x", color="#94a3b8", size=8),
                name="Exit"), row=1, col=1)
        eq = res["equity_curve"]
        fig.add_trace(go.Scatter(x=eq["time"], y=eq["equity"], mode="lines",
                                 name="Equity", line=dict(color="#3b82f6")), row=2, col=1)
        fig.update_layout(height=600, margin=dict(l=0, r=0, t=30, b=0),
                          xaxis_rangeslider_visible=False, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Trades")
        if res["trades"]:
            rows = [{"id": t.id, "side": t.side, "entry": t.entry_time,
                     "entry_px": round(t.entry_price, 5), "exit": t.exit_time,
                     "exit_px": round(t.exit_price, 5) if t.exit_price else None,
                     "size": t.size, "pnl": round(t.pnl, 2),
                     "reason": t.exit_reason} for t in res["trades"]]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, height=300)
            csv = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
            st.download_button("Export trades CSV", csv, "trades.csv", "text/csv")
        else:
            st.info("No trades executed.")

        with st.expander("Execution Logs (last 200)"):
            st.code("\n".join(res["logs"][-200:]) or "(empty)")

st.divider()
st.caption("Phase 1 - all numbers computed from simulated trades. Backtest != live performance.")
