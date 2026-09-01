import json
from datetime import UTC, datetime

import pandas as pd

from qts import automation
from qts.automation import (
    cooldown_active,
    drawdown_stop_triggered,
    market_is_open,
    quote_is_current,
)


def test_nse_market_window() -> None:
    assert market_is_open(datetime(2026, 8, 31, 4, 0, tzinfo=UTC))
    assert not market_is_open(datetime(2026, 8, 31, 3, 0, tzinfo=UTC))
    assert not market_is_open(datetime(2026, 8, 30, 4, 0, tzinfo=UTC))


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
    assert state["equity_history"][0]["nifty"] == 25_000
