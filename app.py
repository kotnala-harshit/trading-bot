from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from qts.config import load_config
from qts.data import load_ohlcv, validate_ohlcv
from qts.providers import alpha_vantage_daily, yahoo_chart
from qts.readiness import check_ibkr
from qts.safety import evaluate_live_gate
from qts.strategy import backtest, metrics

ROOT = Path(__file__).parent
st.set_page_config(page_title="Quant Trading Workbench", page_icon="📈", layout="wide")
st.title("Money Workspace")
st.caption("Markets, forecasting, and royalty research in one safe workspace.")

workspace = st.sidebar.selectbox(
    "Workspace",
    ["MES futures lab", "Stock forecasting · future", "Royalty intelligence · future"],
)
if workspace != "MES futures lab":
    title = workspace.split(" ·")[0]
    st.header(title)
    if title == "Stock forecasting":
        st.info(
            "Future module: Alpha Vantage stock data, transparent baseline forecasts, "
            "walk-forward comparison, uncertainty ranges, and model monitoring."
        )
    else:
        st.info(
            "Future module: pharmaceutical research, sales scenarios, royalty valuation, "
            "risk analysis, and an investment dossier. The existing RoyaltyIQ repository "
            "will remain intact until migration is tested."
        )
    st.warning("Future modules are research tools, not investment advice or automated trading systems.")
    st.stop()

page = st.sidebar.radio("Dashboard", ["Overview", "Data", "Strategy", "Validation", "IBKR readiness", "Safety gates"])
config_name = st.sidebar.selectbox("Configuration", ["production-paper.yaml", "staging.yaml", "production-live.yaml"])
config = load_config(ROOT / "configs" / config_name)
st.sidebar.info(f"Mode: {config['environment'].upper()}")

demo_path = ROOT / "data" / "sample" / "mes_demo.csv"
source = st.sidebar.selectbox("Data source", ["Synthetic demo", "Yahoo MES proxy", "CSV upload", "Alpha Vantage stock demo"])
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
    cols[3].metric("Live orders", "LOCKED" if not evaluate_live_gate(config).allowed else "UNLOCKED")
    cols[4].metric("Research grade", "YES" if research_grade else "NO")
    st.plotly_chart(px.line(result, x="timestamp", y="equity", title="Demonstration equity curve"), use_container_width=True)
    st.warning("Bundled sample data is synthetic and proves software behavior only. It is not evidence of a profitable strategy.")
elif page == "Data":
    st.subheader("OHLCV quality")
    st.json(report.__dict__)
    st.plotly_chart(px.line(frame, x="timestamp", y="close", title="Close price"), use_container_width=True)
    st.dataframe(frame.tail(100), use_container_width=True)
elif page == "Strategy":
    fast = st.slider("Fast moving average", 2, 60, 20)
    slow = st.slider("Slow moving average", fast + 1, 200, 80)
    cost = st.number_input("One-way cost (basis points)", 0.0, 100.0, 1.0)
    result = backtest(frame, fast, slow, cost)
    st.json(metrics(result))
    st.plotly_chart(px.line(result, x="timestamp", y=["equity", "fast_ma", "slow_ma"]), use_container_width=True)
elif page == "Validation":
    rows = []
    for multiplier in (1, 1.5, 2, 3):
        stat = metrics(backtest(frame, cost_bps=multiplier))
        stat["cost_multiplier"] = multiplier
        rows.append(stat)
    st.subheader("Cost stress")
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
    st.info("Production promotion also requires real-data walk-forward, parameter stability, permutation, and paper-fill reconciliation evidence. See PRODUCTION_READINESS.md.")
elif page == "IBKR readiness":
    status = check_ibkr(config["ibkr"]["host"], int(config["ibkr"]["port"]))
    st.metric("Endpoint", "REACHABLE" if status.reachable else "OFFLINE")
    st.code(f"{status.host}:{status.port}")
    st.write(status.message)
    st.warning("Reachability is not authentication, account confirmation, market-data entitlement, or permission to transmit orders.")
else:
    gate = evaluate_live_gate(config)
    st.metric("Live transmission", "ALLOWED" if gate.allowed else "BLOCKED")
    for reason in gate.reasons:
        st.write(f"❌ {reason}")
    st.json({"risk": config["risk"], "execution": config["execution"]})
