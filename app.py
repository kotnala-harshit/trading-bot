from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import plotly.express as px
import streamlit as st

from qts.data import validate_ohlcv
from qts.forecasting import benchmark_forecasts
from qts.paper import execute_paper_fill, mark_to_market
from qts.providers import yahoo_chart
from qts.risk_plan import size_long_position
from qts.strategy import backtest, candidate_score, market_regime_is_positive, metrics

st.set_page_config(page_title="Quant Trading Workbench", page_icon="📈", layout="wide")
st.title("Money Workspace")
st.caption("Markets, forecasting, and royalty research in one safe workspace.")

INDIAN_STOCKS = {
    "ABB India": "ABB.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "Ambuja Cements": "AMBUJACEM.NS",
    "Apollo Hospitals": "APOLLOHOSP.NS",
    "AU Small Finance Bank": "AUBANK.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Bank of Baroda": "BANKBARODA.NS",
    "Bharat Electronics": "BEL.NS",
    "Bharat Forge": "BHARATFORG.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "BSE": "BSE.NS",
    "Canara Bank": "CANBK.NS",
    "Cipla": "CIPLA.NS",
    "Coal India": "COALINDIA.NS",
    "Container Corporation": "CONCOR.NS",
    "Cummins India": "CUMMINSIND.NS",
    "Dixon Technologies": "DIXON.NS",
    "Eternal": "ETERNAL.NS",
    "GAIL": "GAIL.NS",
    "Hindustan Aeronautics": "HAL.NS",
    "Hindustan Copper": "HINDCOPPER.NS",
    "Hindustan Zinc": "HINDZINC.NS",
    "Indian Hotels": "INDHOTEL.NS",
    "Indian Oil": "IOC.NS",
    "ITC": "ITC.NS",
    "JSW Steel": "JSWSTEEL.NS",
    "Larsen & Toubro": "LT.NS",
    "Mahindra & Mahindra": "M&M.NS",
    "Max Healthcare": "MAXHEALTH.NS",
    "NMDC": "NMDC.NS",
    "NTPC": "NTPC.NS",
    "Oil India": "OIL.NS",
    "ONGC": "ONGC.NS",
    "Persistent Systems": "PERSISTENT.NS",
    "Power Finance Corporation": "PFC.NS",
    "Power Grid": "POWERGRID.NS",
    "REC": "RECLTD.NS",
    "State Bank of India": "SBIN.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Tata Power": "TATAPOWER.NS",
    "Tata Steel": "TATASTEEL.NS",
    "Titan": "TITAN.NS",
    "UltraTech Cement": "ULTRACEMCO.NS",
    "Varun Beverages": "VBL.NS",
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
    st.success("Forward paper mandate: ₹10,00,000 · launch Monday 31 August 2026 · starts in cash")
    page = st.sidebar.radio(
        "Indian equity lab",
        [
            "Overview",
            "Forecasting",
            "Trading strategy",
            "Backtest vs forward",
            "₹10L risk plan",
            "Paper trading",
            "Market context",
            "Data quality",
        ],
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
    signal_label = {1: "LONG", 0: "CASH"}[signal]
    strategy_stats = metrics(result)
    try:
        market_regime = market_regime_is_positive(load_indian_stock("^NSEI").frame)
    except (OSError, ValueError, TypeError, KeyError):
        market_regime = False
    risk_gate_passed = market_regime and candidate_score(frame) is not None
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
    elif page == "Forecasting":
        st.subheader("Walk-forward price forecasting benchmarks")
        scores = benchmark_forecasts(frame.close.astype(float).tolist())
        score_frame = pd.DataFrame([asdict(score) for score in scores])
        score_frame["forecast_change_pct"] = (score_frame.next_close / latest - 1) * 100
        st.dataframe(score_frame, use_container_width=True)
        best = scores[0]
        columns = st.columns(3)
        columns[0].metric("Lowest-error model", best.model)
        columns[1].metric("Next-close estimate", f"₹{best.next_close:,.2f}")
        columns[2].metric("Walk-forward direction", f"{best.directional_accuracy_pct:.1f}%")
        st.warning(
            "Price forecasts are uncertain benchmarks, not price targets. Model selection uses walk-forward MAE and must be monitored out of sample."
        )
    elif page == "Trading strategy":
        st.write(
            f"Long when the {fast}-day average is above the {slow}-day average; otherwise cash. The position is shifted one day to avoid look-ahead."
        )
        st.json(strategy_stats)
        st.metric("Deployment gate", "PASS" if risk_gate_passed else "DEFENSIVE — CASH")
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
    elif page == "₹10L risk plan":
        stop_pct = st.slider("Planning stop distance (%)", 2.0, 10.0, 5.0) / 100
        plan = size_long_position(1_000_000, latest, stop_pct=stop_pct)
        columns = st.columns(4)
        columns[0].metric("Simulated capital", "₹10,00,000")
        columns[1].metric("Maximum shares", plan.shares)
        columns[2].metric("Planned allocation", f"₹{plan.allocation:,.0f}")
        columns[3].metric("Risk at stop", f"₹{plan.risk_at_stop:,.0f}")
        st.write(
            f"Planning stop: ₹{plan.stop_price:,.2f}. Maximum 15% per stock, 0.5% risk per position, six positions, long-only."
        )
        st.warning(
            "Stops can gap below the planned price. Risk controls cannot guarantee zero loss."
        )
    elif page == "Paper trading":
        key = f"paper_{symbol}"
        if key not in st.session_state:
            st.session_state[key] = {"cash": 1_000_000.0, "position": 0, "fills": []}
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
            if st.button("Apply current strategy signal", disabled=not risk_gate_passed):
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
            if not risk_gate_passed:
                st.error(
                    "The broad-market, trend, momentum or volatility gate is defensive. The paper account remains in cash."
                )
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
    elif page == "Market context":
        context_symbols = {
            "Nifty 50": "^NSEI",
            "USD/INR": "INR=X",
            "S&P 500": "^GSPC",
            "Nasdaq": "^IXIC",
            "Nikkei 225": "^N225",
            "Crude oil": "CL=F",
            "Gold": "GC=F",
        }
        rows = []
        for label, ticker in context_symbols.items():
            try:
                context = yahoo_chart(ticker, period="5d", interval="1d").frame
                change = (context.close.iloc[-1] / context.close.iloc[-2] - 1) * 100
                rows.append(
                    {
                        "market": label,
                        "symbol": ticker,
                        "latest": context.close.iloc[-1],
                        "change_pct": change,
                    }
                )
            except (OSError, ValueError, TypeError, KeyError):
                rows.append({"market": label, "symbol": ticker, "latest": None, "change_pct": None})
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        st.info(
            "SGX Nifty has been replaced by GIFT Nifty. A licensed or broker-authorized feed is required before using it as a dependable live signal."
        )
    else:
        st.json(report.__dict__)
        st.dataframe(frame.tail(100), use_container_width=True)


workspace = st.sidebar.selectbox(
    "Project",
    [
        "Indian Equity Forecasting & Paper Trading · Primary",
        "US Equities · Phase 2",
        "Other Global Markets · Phase 3",
        "RoyaltyIQ · Phase 4",
        "MES Futures and Derivatives · Phase 5",
    ],
)
if workspace == "Indian Equity Forecasting & Paper Trading · Primary":
    render_indian_lab()
    st.stop()
title = workspace.split(" ·")[0]
st.header(title)
phase_copy = {
    "US Equities": "Phase 2: apply the validated workflow to US equities.",
    "Other Global Markets": "Phase 3: add other exchanges market by market.",
    "RoyaltyIQ": "Phase 4: pharmaceutical research, forecasts, royalty valuation, and risk.",
    "MES Futures and Derivatives": "Phase 5: futures research after cash-equity paper validation.",
}
st.info(phase_copy[title])
st.warning("Future modules are research tools and remain inactive.")
st.stop()
