from pathlib import Path

import pandas as pd
import streamlit as st

from qts.dashboard import phase_snapshot

st.set_page_config(page_title="Three-phase trading research", layout="wide")
st.title("Trading research / Paper operations")
phase = st.sidebar.radio("Phase", ["INDIA", "US", "GLOBAL"]).lower()
snapshot = phase_snapshot(Path(__file__).resolve().parent, phase)
st.warning("LIVE ORDERS DISABLED · TRANSMIT_ORDERS FALSE · INTERNAL PAPER EXECUTION")
cols = st.columns(4)
for column, key in zip(cols, ["environment", "provider", "data_mode", "reconciliation"]):
    column.metric(key.replace("_", " ").title(), snapshot[key])
st.info(snapshot["status"])
st.subheader(snapshot["promotion"]["status"])
st.subheader("Portfolio performance")
history = snapshot["history"]
if len(history) > 1:
    benchmark = [point.get("benchmark", point.get("nifty")) for point in history]
    st.line_chart(pd.DataFrame({"Portfolio": [point["equity"] / history[0]["equity"] - 1 for point in history], snapshot["benchmark_label"]: [value / benchmark[0] - 1 for value in benchmark]}, index=pd.to_datetime([point["timestamp"] for point in history])))
    st.caption("Cumulative return since the first recorded observation.")
else:
    st.caption("Portfolio/benchmark chart begins after two successful observations.")
st.dataframe([{"metric": k, "value": str(v) if v is not None else "Not measured"} for k, v in snapshot["metrics"].items()], hide_index=True)
st.caption("Currency: " + snapshot["currency"] + "; return, exposure and drawdown values are decimal ratios.")
for title, key in [("Holdings", "holdings"), ("Orders", "orders"), ("Legacy fills", "legacy_fills"), ("Candidate rankings", "candidates")]:
    st.subheader(title)
    if snapshot[key]:
        st.dataframe(snapshot[key], hide_index=True)
    else:
        st.caption("No records available")
with st.expander("Risk, data quality and system health"):
    st.json({k: v for k, v in snapshot.items() if k not in {"metrics", "holdings", "orders", "legacy_fills", "history"}})
st.caption("Read-only recorded state. No live feed is connected by opening this interface.")
