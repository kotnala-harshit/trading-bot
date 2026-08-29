from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from qts.config import load_config
from qts.data import load_ohlcv, validate_ohlcv
from qts.readiness import check_ibkr
from qts.safety import evaluate_live_gate
from qts.strategy import backtest, metrics

ROOT = Path(__file__).parent
st.set_page_config(page_title="Quant Trading Workbench", page_icon="📈", layout="wide")
st.title("Quant Trading Workbench")
st.caption("Research and operational readiness console — order placement is not exposed in this dashboard.")

page = st.sidebar.radio("Dashboard", ["Overview", "Data", "Strategy", "Validation", "IBKR readiness", "Safety gates"])
config_name = st.sidebar.selectbox("Configuration", ["production-paper.yaml", "staging.yaml", "production-live.yaml"])
config = load_config(ROOT / "configs" / config_name)
st.sidebar.info(f"Mode: {config['environment'].upper()}")

demo_path = ROOT / "data" / "sample" / "mes_demo.csv"
upload = st.sidebar.file_uploader("Optional OHLCV CSV", type="csv")
try:
    frame = load_ohlcv(upload if upload else demo_path)
except (OSError, ValueError, TypeError) as exc:
    st.error(f"Could not load data: {exc}")
    st.stop()
report = validate_ohlcv(frame)

if page == "Overview":
    result = backtest(frame)
    stats = metrics(result)
    cols = st.columns(4)
    cols[0].metric("Data rows", report.rows)
    cols[1].metric("Data quality", "PASS" if report.valid else "FAIL")
    cols[2].metric("Mode", config["environment"].upper())
    cols[3].metric("Live orders", "LOCKED" if not evaluate_live_gate(config).allowed else "UNLOCKED")
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
