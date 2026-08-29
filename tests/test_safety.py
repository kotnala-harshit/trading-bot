import pytest

from qts.config import load_config
from qts.safety import LIVE_ACK, assert_order_allowed, evaluate_live_gate


def test_live_default_is_blocked():
    assert not evaluate_live_gate(load_config("configs/production-live.yaml"), {}).allowed


def test_all_live_gates_are_required():
    config = load_config("configs/production-live.yaml")
    config["execution"].update(dry_run=False, autonomous_order_transmission=True)
    env = {
        "TRADING_MODE": "live",
        "LIVE_TRADING_ENABLED": "true",
        "LIVE_TRADING_ACK": LIVE_ACK,
        "IBKR_ACCOUNT_CONFIRMED": "true",
    }
    assert evaluate_live_gate(config, env).allowed


def test_paper_is_allowed_by_order_guard():
    assert_order_allowed(load_config("configs/production-paper.yaml"), {})


def test_live_guard_raises():
    with pytest.raises(PermissionError):
        assert_order_allowed(load_config("configs/production-live.yaml"), {})
