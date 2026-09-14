import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from qts import automation, us_automation
from qts.automation import (
    cooldown_active,
    drawdown_stop_triggered,
    market_is_open,
    quote_is_current,
)
from qts.dashboard import performance_chart
from qts.us_automation import exposure, us_market_is_open
from qts.us_automation import quote_is_current as us_quote_is_current


def test_nse_market_window() -> None:
    assert market_is_open(datetime(2026, 8, 31, 4, 0, tzinfo=UTC))
    assert not market_is_open(datetime(2026, 8, 31, 3, 0, tzinfo=UTC))
    assert not market_is_open(datetime(2026, 8, 30, 4, 0, tzinfo=UTC))


def test_us_market_window_and_defensive_exposure() -> None:
    assert us_market_is_open(datetime(2026, 9, 1, 15, 0, tzinfo=UTC))
    assert not us_market_is_open(datetime(2026, 9, 1, 12, 0, tzinfo=UTC))
    dates = pd.date_range("2025-01-01", periods=220, freq="B", tz="UTC")
    rising = pd.DataFrame({"timestamp": dates, "close": range(100, 320)})
    assert 0 < exposure(rising) <= 0.40
    assert exposure(rising.assign(close=list(range(320, 100, -1)))) == 0


def test_us_chart_uses_spy_and_current_session_marks() -> None:
    history = [{"timestamp": "2026-09-01T14:00:00+00:00", "equity": 10_000, "benchmark": 600}, {"timestamp": "2026-09-01T14:05:00+00:00", "equity": 10_100, "benchmark": 603}]
    assert "SPY adjusted total-return proxy" in performance_chart(history, "SPY adjusted total-return proxy")
    assert us_quote_is_current(pd.Timestamp("2026-09-01T14:00:00Z"), "2026-09-01")
    assert not us_quote_is_current(pd.Timestamp("2026-08-31T14:00:00Z"), "2026-09-01")


def test_us_observation_records_portfolio_and_spy(monkeypatch) -> None:
    frame = pd.DataFrame({"timestamp": [pd.Timestamp("2026-09-01T15:00:00Z")], "close": [100.0]})
    monkeypatch.setattr(us_automation, "fetch", lambda symbol, review: SimpleNamespace(frame=frame.assign(close=200.0 if symbol == "SPY" else 100.0)))
    state = {"cash": 9_000, "positions": {"ABC": {"quantity": 10}}, "peak_equity": 10_000}
    us_automation.record_observation(state, datetime(2026, 9, 1, 15, 5, tzinfo=UTC))
    assert state["last_equity"] == 10_000
    assert state["equity_history"][-1]["benchmark"] == 200
    assert "no orders" in state["status"]


def test_portfolio_cooldown_expires() -> None:
    now = datetime(2026, 8, 31, 4, 0, tzinfo=UTC)
    assert cooldown_active({"cooldown_until": "2026-09-28T04:00:00+00:00"}, now)
    assert not cooldown_active({"cooldown_until": "2026-08-30T04:00:00+00:00"}, now)


def test_drawdown_stop_is_reserved_for_emergencies() -> None:
    assert not drawdown_stop_triggered(-0.05, True)
    assert not drawdown_stop_triggered(-0.20, False)
    assert drawdown_stop_triggered(-0.20, True)


def test_quote_must_be_from_current_india_session() -> None:
    assert quote_is_current(pd.Timestamp("2026-09-01T09:00:00Z"), "2026-09-01")
    assert not quote_is_current(pd.Timestamp("2026-08-31T09:00:00Z"), "2026-09-01")


def test_hub_control_can_disable_paper_orders(tmp_path, monkeypatch) -> None:
    control = tmp_path / "paper-trader.json"
    control.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(automation, "CONTROL_PATH", control)
    assert not automation.trading_enabled()


def test_observation_workflows_run_on_weekdays() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("paper-trader.yml", "us-paper-trader.yml"):
        workflow = (root / ".github" / "workflows" / name).read_text()
        assert "  schedule:\n" in workflow
        assert "* * 1-5" in workflow


def test_dashboard_records_and_renders_portfolio_history(tmp_path, monkeypatch) -> None:
    page = tmp_path / "index.html"
    monkeypatch.setattr(automation, "PAGE_PATH", page)
    monkeypatch.setattr(automation, "LEDGER_PATH", tmp_path / "ledger.csv")
    state = {
        "cash": 500_000,
        "last_equity": 1_010_000,
        "peak_equity": 1_020_000,
        "positions": {},
        "sessions_since_review": 1,
        "status": "Paper monitoring",
    }
    automation.record_history(state, "2026-09-01T09:00:00+00:00", 25_000)
    automation.render_page(state, {})
    output = page.read_text()
    assert "Portfolio performance" in output
    assert "Risk monitor" in output
    assert "Recent activity" in output
    assert "US equities · Phase 2" in output
    assert "Phase 2.5" not in output
    assert "Other global markets · Phase 3" in output
    assert state["equity_history"][0]["nifty"] == 25_000
