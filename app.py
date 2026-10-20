import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from engine.core import Backtester
from engine.metrics import compute_metrics
from strategies.examples import EMACross, RSIMeanReversion
from data import loader
from engine import indicators as ind

st.set_page_config(page_title="MT5 Studio", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0d0f12; color: #d1d5db; }
    [data-testid="stSidebar"] { background-color: #16191f; border-right: 1px solid #2a2e38; }
    h1, h2, h3 { color: #e5e7eb; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    div.stButton > button { background-color: #2563eb; color: white; border-radius: 4px; border: none; width: 100%; font-weight: bold; }
    div.stButton > button:hover { background-color: #1d4ed8; }
    .metric-box { background-color: #16191f; padding: 10px; border-radius: 4px; border: 1px solid #2a2e38; text-align: center; }
    .metric-label { font-size: 11px; color: #9ca3af; text-transform: uppercase; }
    .metric-value { font-size: 18px; font-weight: bold; color: #f3f4f6; }
    .metric-green { color: #22c55e !important; }
    .metric-red { color: #ef4444 !important; }
</style>
""", unsafe_allow_html=True)

st.title("📊 MT5 Strategy Studio")
st.caption("Professional Event-Driven Backtesting Terminal")

# ডেটা ক্যাশ করে রাখার ফাংশন, যাতে বারবার রিলোড না লাগে
@st.cache_data
def get_synthetic(n):
    return loader.synthetic_data(n)

with st.sidebar:
    st.header("⚙️ Settings")
    
    with st.expander("Account & Execution", expanded=True):
        deposit = st.number_input("Initial Deposit", 100.0, 1000000.0, 10000.0, 500.0)
        commission = st.number_input("Commission / lot", 0.0, 100.0, 0.0, 0.5)
        spread = st.number_input("Spread (price units)", 0.0, 100.0, 0.0, 0.01, format="%.5f")
        contract = st.number_input("Contract size", 1.0, 1000000.0, 1.0, 1.0)
        
    with st.expander("Market Data", expanded=True):
        src = st.selectbox("Data Source", ["Synthetic (Test)", "CSV Upload"])
        if src == "Synthetic (Test)":
            # এখানে min_value=100, step=500 করা হয়েছে যাতে ২০০০ বা ৫০ হাজার সবই নেওয়া যায়
            n = st.number_input("Number of Bars", min_value=100, max_value=100000, value=2000, step=500)
            st.session_state["df"] = get_synthetic(n)
        else:
            f = st.file_uploader("Upload CSV", type=["csv"])
            if f:
                try:
                    st.session_state["df"] = loader.load_csv(f)
                except Exception as e:
                    st.error(str(e))
                    st.session_state["df"] = None
            else:
                st.session_state["df"] = None
                
    with st.expander("Strategy Builder", expanded=True):
        choice = st.selectbox("Select Strategy", ["EMA Cross", "RSI Mean Reversion"])
        if choice == "EMA Cross":
            fast = st.number_input("Fast EMA", 5, 100, 20)
            slow = st.number_input("Slow EMA", 20, 500, 50)
            size = st.number_input("Position Size", 0.01, 100.0, 1.0)
            strat = EMACross(fast=fast, slow=slow, size=size)
        else:
            period = st.number_input("RSI Period", 5, 50, 14)
            os_ = st.number_input("Oversold", 10, 50, 30)
            ob_ = st.number_input("Overbought", 50, 90, 70)
            slp = st.number_input("SL %", 0.1, 20.0, 2.0) / 100
            tpp = st.number_input("TP %", 0.1, 50.0, 4.0) / 100
            strat = RSIMeanReversion(period=period, oversold=os_, overbought=ob_, sl_pct=slp, tp_pct=tpp)
            
    run_btn = st.button("▶ Run Backtest", type="primary")

# সেশন স্টেট থেকে ডেটা নেওয়া (যাতে রান বাটনে ক্লিক করলে ডেটা হারিয়ে না যায়)
df = st.session_state.get("df")
if df is None:
    st.warning("👈 Please load data in the sidebar. (সাইডবার থেকে ডেটা লোড করুন)")
else:
    if run_btn:
        with st.spinner("Simulating market..."):
            bt = Backtester(df=df, strategy=strat, symbol="TEST", timeframe="1h",
                            initial_deposit=deposit, commission_per_lot=commission,
                            spread=spread, contract_size=contract)
            res = bt.run()
            metrics = compute_metrics(res["trades"], res["equity_curve"], deposit)
            st.session_state["result"] = res
            st.session_state["metrics"] = metrics

    res = st.session_state.get("result")
    m = st.session_state.get("metrics")

    if res and m:
        st.markdown("### Performance Report")
        
        def metric_html(label, value, is_pct=False, color_reverse=False):
            color_class = ""
            if isinstance(value, (int, float)):
                if value > 0: color_class = "metric-green" if not color_reverse else "metric-red"
                elif value < 0: color_class = "metric-red" if not color_reverse else "metric-green"
            fmt_val = f"{value:.2f}" if isinstance(value, float) else str(value)
            if is_pct and isinstance(value, float): fmt_val += "%"
            return f"""<div class="metric-box"><div class="metric-label">{label}</div><div class="metric-value {color_class}">{fmt_val}</div></div>"""

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.markdown(metric_html("Net Profit", m['net_profit']), unsafe_allow_html=True)
        with c2: st.markdown(metric_html("Profit Factor", m['profit_factor'] or 0), unsafe_allow_html=True)
        with c3: st.markdown(metric_html("Total Trades", m['total_trades']), unsafe_allow_html=True)
        with c4: st.markdown(metric_html("Win Rate", m['win_rate'] or 0, is_pct=True), unsafe_allow_html=True)
        with c5: st.markdown(metric_html("Max Drawdown", m['max_drawdown'], color_reverse=True), unsafe_allow_html=True)
        
        c6, c7, c8, c9, c10 = st.columns(5)
        with c6: st.markdown(metric_html("Expected Payoff", m['net_profit']/max(1, m['total_trades'])), unsafe_allow_html=True)
        with c7: st.markdown(metric_html("Recovery Factor", m['recovery_factor'] or 0), unsafe_allow_html=True)
        with c8: st.markdown(metric_html("Sharpe Ratio", m['sharpe'] or 0), unsafe_allow_html=True)
        with c9: st.markdown(metric_html("Sortino Ratio", m['sortino'] or 0), unsafe_allow_html=True)
        with c10: st.markdown(metric_html("Max DD %", m['max_drawdown_pct'], is_pct=True, color_reverse=True), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        bars = res["bars"]
        close = bars["close"]
        if choice == "EMA Cross":
            ema_fast = ind.ema(close, fast)
            ema_slow = ind.ema(close, slow)
        else:
            ema_fast = ind.ema(close, 20)
            ema_slow = ind.ema(close, 50)

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2], vertical_spacing=0.02)

        fig.add_trace(go.Candlestick(x=bars["time"], open=bars["open"], high=bars["high"],
                                     low=bars["low"], close=bars["close"], name="Price",
                                     increasing_line_color='#22c55e', decreasing_line_color='#ef4444',
                                     increasing_fillcolor='#22c55e', decreasing_fillcolor='#ef4444'), row=1, col=1)
        
        fig.add_trace(go.Scatter(x=bars["time"], y=ema_fast, mode="lines", name=f"EMA Fast", line=dict(color="#facc15", width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=bars["time"], y=ema_slow, mode="lines", name=f"EMA Slow", line=dict(color="#ef4444", width=1.5)), row=1, col=1)

        colors = ['#22c55e' if c >= o else '#ef4444' for c, o in zip(bars["close"], bars["open"])]
        fig.add_trace(go.Bar(x=bars["time"], y=bars["volume"], name="Volume", marker_color=colors, opacity=0.5), row=2, col=1)

        if res["trades"]:
            buys = [t for t in res["trades"] if t.side == "buy"]
            sells = [t for t in res["trades"] if t.side == "sell"]
            if buys:
                fig.add_trace(go.Scatter(x=[t.entry_time for t in buys], y=[t.entry_price for t in buys], mode="markers", marker=dict(symbol="triangle-up", color="#22c55e", size=10), name="Buy Entry"), row=1, col=1)
                fig.add_trace(go.Scatter(x=[t.exit_time for t in buys], y=[t.exit_price for t in buys], mode="markers", marker=dict(symbol="x", color="#9ca3af", size=8), name="Buy Exit"), row=1, col=1)
            if sells:
                fig.add_trace(go.Scatter(x=[t.entry_time for t in sells], y=[t.entry_price for t in sells], mode="markers", marker=dict(symbol="triangle-down", color="#ef4444", size=10), name="Sell Entry"), row=1, col=1)
                fig.add_trace(go.Scatter(x=[t.exit_time for t in sells], y=[t.exit_price for t in sells], mode="markers", marker=dict(symbol="x", color="#9ca3af", size=8), name="Sell Exit"), row=1, col=1)

        fig.update_layout(
            template="plotly_dark", height=600, margin=dict(l=10, r=10, t=30, b=10),
            xaxis_rangeslider_visible=False, plot_bgcolor="#0d0f12", paper_bgcolor="#0d0f12",
            hovermode="x unified", dragmode="pan", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#2a2e38")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#2a2e38", side="right")
        
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

        st.markdown("### Trade History")
        if res["trades"]:
            df_trades = pd.DataFrame([{
                "ID": t.id, "Type": t.side.upper(), "Entry Time": t.entry_time,
                "Entry Price": round(t.entry_price, 5), "Exit Time": t.exit_time,
                "Exit Price": round(t.exit_price, 5) if t.exit_price else None,
                "Size": t.size, "Net P/L": round(t.pnl, 2), "Reason": t.exit_reason
            } for t in res["trades"]])
            st.dataframe(df_trades, use_container_width=True, height=300)
            csv = df_trades.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export Trade History (CSV)", csv, "mt5_trades.csv", "text/csv")
        else:
            st.info("No trades were executed during this backtest.")
