import json
from datetime import UTC, datetime

from qts import automation
from qts.automation import cooldown_active, market_is_open


def test_nse_market_window() -> None:
    assert market_is_open(datetime(2026, 8, 31, 4, 0, tzinfo=UTC))
    assert not market_is_open(datetime(2026, 8, 31, 3, 0, tzinfo=UTC))
    assert not market_is_open(datetime(2026, 8, 30, 4, 0, tzinfo=UTC))


def test_portfolio_cooldown_expires() -> None:
    now = datetime(2026, 8, 31, 4, 0, tzinfo=UTC)
    assert cooldown_active({"cooldown_until": "2026-09-28T04:00:00+00:00"}, now)
    assert not cooldown_active({"cooldown_until": "2026-08-30T04:00:00+00:00"}, now)


def test_hub_control_can_disable_paper_orders(tmp_path, monkeypatch) -> None:
    control = tmp_path / "paper-trader.json"
    control.write_text(json.dumps({"enabled": False}))
    monkeypatch.setattr(automation, "CONTROL_PATH", control)
    assert not automation.trading_enabled()
