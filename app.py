from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from qts.config import load_config
from qts.data import load_ohlcv, validate_ohlcv
from qts.paper import execute_paper_fill, mark_to_market
from qts.providers import alpha_vantage_daily, yahoo_chart
from qts.readiness import check_ibkr
from qts.safety import evaluate_live_gate
from qts.strategy import backtest, metrics

ROOT = Path(__file__).parent
st.set_page_config(page_title="Quant Trading Workbench", page_icon="📈", layout="wide")
st.title("Money Workspace")
st.caption("Markets, forecasting, and royalty research in one safe workspace.")

INDIAN_STOCKS = {
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Infosys": "INFY.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "Nifty 50 index": "^NSEI",
}


@st.cache_data(ttl=900, show_spinner=False)
def load_indian_stock(ticker: str):
    return yahoo_chart(ticker, period="5y", interval="1d")


def render_indian_lab() -> None:
    st.caption("Phase 1 · Indian cash equities · delayed-data paper research")
    page = st.sidebar.radio(
        "Indian stock lab",
        ["Overview", "Strategy", "Backtest vs forward", "Paper trading", "Data quality"],
    )
    name = st.sidebar.selectbox("NSE instrument", list(INDIAN_STOCKS))
    symbol = INDIAN_STOCKS[name]
    fast = st.sidebar.slider("Fast average", 5, 60, 20)
    slow = st.sidebar.slider("Slow average", fast + 5, 200, 80)
    cost = st.sidebar.number_input("Estimated one-way cost (bps)", 0.0, 100.0, 10.0)
    try:
        dataset = load_indian_stock(symbol)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        st.error(f"Market data could not be loaded: {exc}")
        return
    frame = dataset.frame
    report = validate_ohlcv(frame)
    result = backtest(frame, fast, slow, cost)
    latest = float(frame.close.iloc[-1])
    signal = int(result.signal.iloc[-1])
    signal_label = {1: "LONG", 0: "CASH", -1: "EXIT (shorting disabled)"}[signal]
    st.info(
        f"Source: Yahoo Finance · {symbol} · latest observation {frame.timestamp.iloc[-1]}. This feed may be delayed and is not exchange-grade real-time data."
    )

    if page == "Overview":
        columns = st.columns(5)
        columns[0].metric("Instrument", symbol)
        columns[1].metric("Latest close", f"₹{latest:,.2f}")
        columns[2].metric("Model signal", signal_label)
        columns[3].metric("Rows", f"{len(frame):,}")
        columns[4].metric("Data quality", "PASS" if report.valid else "REVIEW")
        st.plotly_chart(
            px.line(frame, x="timestamp", y="close", title=f"{name} closing price"),
            use_container_width=True,
        )
        st.warning("A model signal is a research output, not a recommendation.")
    elif page == "Strategy":
        st.write(
            f"Long when the {fast}-day average is above the {slow}-day average; otherwise cash. The position is shifted one day to avoid look-ahead."
        )
        st.json(metrics(result))
        st.plotly_chart(
            px.line(result, x="timestamp", y=["close", "fast_ma", "slow_ma"]),
            use_container_width=True,
        )
        st.plotly_chart(
            px.line(result, x="timestamp", y="equity", title="Historical growth of ₹1 before tax"),
            use_container_width=True,
        )
    elif page == "Backtest vs forward":
        split = max(slow + 5, int(len(frame) * 0.8))
        development = backtest(frame.iloc[:split].copy(), fast, slow, cost)
        forward = backtest(frame.iloc[max(0, split - slow) :].copy(), fast, slow, cost)
        forward = forward[forward.timestamp >= frame.timestamp.iloc[split]].copy()
        comparison = pd.DataFrame(
            [
                {"window": "Development 80%", **metrics(development)},
                {"window": "Forward 20%", **metrics(forward)},
            ]
        )
        st.dataframe(comparison, use_container_width=True)
        st.plotly_chart(
            px.line(
                forward, x="timestamp", y="equity", title="Untouched historical forward window"
            ),
            use_container_width=True,
        )
        st.caption(
            "True forward paper results begin when dated paper fills are collected from today onward."
        )
    elif page == "Paper trading":
        key = f"paper_{symbol}"
        if key not in st.session_state:
            st.session_state[key] = {"cash": 100_000.0, "position": 0, "fills": []}
        account = st.session_state[key]
        equity = mark_to_market(account["cash"], account["position"], latest)
        columns = st.columns(4)
        columns[0].metric("Paper cash", f"₹{account['cash']:,.2f}")
        columns[1].metric("Shares", account["position"])
        columns[2].metric("Marked equity", f"₹{equity:,.2f}")
        columns[3].metric("Signal", signal_label)
        quantity = st.number_input("Paper quantity", 1, 100, 1)
        buy, sell, reset = st.columns(3)
        try:
            side = (
                "BUY"
                if buy.button("Simulate buy", type="primary")
                else "SELL"
                if sell.button("Simulate sell")
                else None
            )
            if side:
                account["cash"], account["position"], fill = execute_paper_fill(
                    account["cash"],
                    account["position"],
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=latest,
                    fee_bps=cost,
                )
                account["fills"].append(asdict(fill))
                st.rerun()
            if st.button("Apply current strategy signal"):
                strategy_side = None
                strategy_quantity = 0
                if signal == 1 and account["position"] == 0:
                    strategy_side, strategy_quantity = "BUY", 1
                elif signal != 1 and account["position"] > 0:
                    strategy_side, strategy_quantity = "SELL", account["position"]
                if strategy_side:
                    account["cash"], account["position"], fill = execute_paper_fill(
                        account["cash"],
                        account["position"],
                        symbol=symbol,
                        side=strategy_side,
                        quantity=strategy_quantity,
                        price=latest,
                        fee_bps=cost,
                    )
                    account["fills"].append(asdict(fill))
                    st.rerun()
                st.info("The paper account already matches the current strategy signal.")
        except ValueError as exc:
            st.error(str(exc))
        if reset.button("Reset paper account"):
            st.session_state.pop(key, None)
            st.rerun()
        ledger = pd.DataFrame(account["fills"])
        st.dataframe(ledger, use_container_width=True)
        if not ledger.empty:
            st.download_button(
                "Download paper ledger",
                ledger.to_csv(index=False),
                f"{symbol}_paper_ledger.csv",
                "text/csv",
            )
        st.warning(
            "This paper ledger is session-only. Download it after each session; durable scheduled tracking is the next milestone."
        )
    else:
        st.json(report.__dict__)
        st.dataframe(frame.tail(100), use_container_width=True)


workspace = st.sidebar.selectbox(
    "Workspace",
    [
        "Indian stocks · Phase 1",
        "US stocks · Phase 2",
        "Global markets · Phase 3",
        "MES futures · Future",
        "Royalty intelligence · Future",
    ],
)
if workspace == "Indian stocks · Phase 1":
    render_indian_lab()
    st.stop()
if workspace != "MES futures · Future":
    title = workspace.split(" ·")[0]
    st.header(title)
    if title == "US stocks":
        st.info(
            "Phase 2: US equities will reuse the validated Indian-stock workflow with "
            "US-specific costs, hours, benchmarks, and data sources."
        )
    elif title == "Global markets":
        st.info("Phase 3: other exchanges will be added market by market after Phase 2 passes.")
    else:
        st.info(
            "Future module: pharmaceutical research, sales scenarios, royalty valuation, "
            "risk analysis, and an investment dossier. The existing RoyaltyIQ repository "
            "will remain intact until migration is tested."
        )
    st.warning(
        "Future modules are research tools, not investment advice or automated trading systems."
    )
    st.stop()

page = st.sidebar.radio(
    "Dashboard", ["Overview", "Data", "Strategy", "Validation", "IBKR readiness", "Safety gates"]
)
config_name = st.sidebar.selectbox(
    "Configuration", ["production-paper.yaml", "staging.yaml", "production-live.yaml"]
)
config = load_config(ROOT / "configs" / config_name)
st.sidebar.info(f"Mode: {config['environment'].upper()}")

demo_path = ROOT / "data" / "sample" / "mes_demo.csv"
source = st.sidebar.selectbox(
    "Data source", ["Synthetic demo", "Yahoo MES proxy", "CSV upload", "Alpha Vantage stock demo"]
)
upload = st.sidebar.file_uploader("OHLCV CSV", type="csv") if source == "CSV upload" else None
try:
    source_note = "Synthetic demonstration data; software validation only."
    research_grade = False
    if source == "Yahoo MES proxy":
        dataset = yahoo_chart()
        frame, source_note, research_grade = dataset.frame, dataset.note, dataset.research_grade
    elif source == "Alpha Vantage stock demo":
        key = st.secrets.get("ALPHA_VANTAGE_API_KEY", "")
        dataset = alpha_vantage_daily("IBM", key)
        frame, source_note, research_grade = dataset.frame, dataset.note, dataset.research_grade
    else:
        frame = load_ohlcv(upload if upload else demo_path)
        if upload:
            source_note = "User-supplied CSV; provenance and contract construction require review."
except (OSError, ValueError, TypeError, KeyError) as exc:
    st.error(f"Could not load data: {exc}")
    st.stop()
report = validate_ohlcv(frame)
st.info(source_note)

if page == "Overview":
    result = backtest(frame)
    stats = metrics(result)
    cols = st.columns(5)
    cols[0].metric("Data rows", report.rows)
    cols[1].metric("Data quality", "PASS" if report.valid else "FAIL")
    cols[2].metric("Mode", config["environment"].upper())
    cols[3].metric(
        "Live orders", "LOCKED" if not evaluate_live_gate(config).allowed else "UNLOCKED"
    )
    cols[4].metric("Research grade", "YES" if research_grade else "NO")
    st.plotly_chart(
        px.line(result, x="timestamp", y="equity", title="Demonstration equity curve"),
        use_container_width=True,
    )
    st.warning(
        "Bundled sample data is synthetic and proves software behavior only. It is not evidence of a profitable strategy."
    )
elif page == "Data":
    st.subheader("OHLCV quality")
    st.json(report.__dict__)
    st.plotly_chart(
        px.line(frame, x="timestamp", y="close", title="Close price"), use_container_width=True
    )
    st.dataframe(frame.tail(100), use_container_width=True)
elif page == "Strategy":
    fast = st.slider("Fast moving average", 2, 60, 20)
    slow = st.slider("Slow moving average", fast + 1, 200, 80)
    cost = st.number_input("One-way cost (basis points)", 0.0, 100.0, 1.0)
    result = backtest(frame, fast, slow, cost)
    st.json(metrics(result))
    st.plotly_chart(
        px.line(result, x="timestamp", y=["equity", "fast_ma", "slow_ma"]), use_container_width=True
    )
elif page == "Validation":
    rows = []
    for multiplier in (1, 1.5, 2, 3):
        stat = metrics(backtest(frame, cost_bps=multiplier))
        stat["cost_multiplier"] = multiplier
        rows.append(stat)
    st.subheader("Cost stress")
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    st.info(
        "Production promotion also requires real-data walk-forward, parameter stability, permutation, and paper-fill reconciliation evidence. See PRODUCTION_READINESS.md."
    )
elif page == "IBKR readiness":
    status = check_ibkr(config["ibkr"]["host"], int(config["ibkr"]["port"]))
    st.metric("Endpoint", "REACHABLE" if status.reachable else "OFFLINE")
    st.code(f"{status.host}:{status.port}")
    st.write(status.message)
    st.warning(
        "Reachability is not authentication, account confirmation, market-data entitlement, or permission to transmit orders."
    )
else:
    gate = evaluate_live_gate(config)
    st.metric("Live transmission", "ALLOWED" if gate.allowed else "BLOCKED")
    for reason in gate.reasons:
        st.write(f"❌ {reason}")
    st.json({"risk": config["risk"], "execution": config["execution"]})
