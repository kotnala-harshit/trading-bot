from datetime import UTC, datetime, timedelta

import pytest

from qts.broker import Quote
from qts.paper_broker import PaperBroker, deterministic_id, validate_pair
from qts.platform import load_phases, promotion_status

NOW = datetime(2026, 9, 7, 9, tzinfo=UTC)


def quotes(size=1000):
    return ({"A": Quote("A", 100, 99.9, 100.1, NOW.isoformat(), "primary", size, size)},
            {"A": Quote("A", 100, 99.9, 100.1, NOW.isoformat(), "secondary", size, size)})


def test_atomic_restart_and_ids(tmp_path):
    path = tmp_path / "paper.sqlite"
    primary, secondary = quotes()
    broker = PaperBroker(path, "india", 10000)
    first = broker.rebalance("close-20260904", {"A": 19}, primary, secondary, now=NOW)
    state = broker.state()
    assert first["status"] == "COMPLETED"
    assert first["orders"][0]["events"] == ["CREATED", "SUBMITTED", "ACKNOWLEDGED", "FILLED"]
    assert broker.reconciliation()["matched"]
    broker.close()
    broker = PaperBroker(path, "india", 10000)
    assert broker.rebalance("close-20260904", {"A": 19}, primary, secondary, now=NOW) == first
    assert broker.state() == state
    assert broker.db.execute("SELECT count(*) FROM fills").fetchone()[0] == 1
    with pytest.raises(ValueError, match="different targets"):
        broker.rebalance("close-20260904", {"A": 18}, primary, secondary, now=NOW)
    assert deterministic_id("a", {"x": 1, "y": 2}) == deterministic_id("a", {"y": 2, "x": 1})
    broker.close()


def test_stale_divergent_missing_liquidity_and_live_blocked(tmp_path):
    primary, secondary = quotes()
    broker = PaperBroker(tmp_path / "paper.sqlite", "india", 10000)
    result = broker.rebalance("stale", {"A": 10}, primary, secondary, now=NOW + timedelta(minutes=2))
    assert result["status"] == "REJECTED"
    assert broker.state()["cash"] == 10000
    secondary["A"] = Quote("A", 110, 109, 111, NOW.isoformat(), "secondary", 100, 100)
    with pytest.raises(ValueError, match="divergence"):
        validate_pair(primary["A"], secondary["A"], NOW)
    with pytest.raises(PermissionError):
        broker.rebalance("live", {}, {}, {}, transmit_orders=True)
    with pytest.raises(ValueError):
        validate_pair(Quote("A", float("nan")), secondary["A"], NOW)
    broker.close()


def test_partial_fill_cash_fees_and_reconciliation_block(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite", "india", 10000)
    primary, secondary = quotes(size=3)
    result = broker.rebalance("partial", {"A": 10}, primary, secondary, now=NOW)
    assert result["orders"][0]["filled_quantity"] == 3
    assert result["orders"][0]["events"][-2:] == ["PARTIALLY_FILLED", "CANCELLED"]
    assert broker.state()["cash"] == pytest.approx(10000 - 3 * 100.1 * 1.0005 * 1.001)
    assert broker.reconciliation()["matched"]
    with broker.db:
        broker.db.execute("UPDATE accounts SET state=json_set(state,'$.cash',9000)")
    result = broker.rebalance("mismatch", {}, primary, secondary, now=NOW)
    assert result["status"] == "REJECTED"
    assert "Reconciliation failed" in result["error"]
    broker.close()


def test_transaction_failure_rolls_back(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite", "india", 10000)
    broker.db.execute("CREATE TRIGGER fail_fill BEFORE INSERT ON fills BEGIN SELECT RAISE(ABORT, 'disk error'); END")
    primary, secondary = quotes()
    with pytest.raises(Exception, match="disk error"):
        broker.rebalance("failure", {"A": 10}, primary, secondary, now=NOW)
    assert broker.state()["cash"] == 10000
    assert broker.db.execute("SELECT count(*) FROM batches").fetchone()[0] == 0
    broker.close()


def test_phase_gates_fail_closed():
    from pathlib import Path
    config = load_phases(Path(__file__).resolve().parents[1])
    assert config["india"]["max_positions"] == 5
    assert config["transmit_orders"] is False
    gate = promotion_status({}, config["promotion"])
    assert gate["status"] == "NOT READY"
    assert not any(gate["checks"].values())


def test_drawdown_cooldown_blocks_entries(tmp_path):
    broker = PaperBroker(tmp_path / "paper.sqlite", "india", 10000)
    primary, secondary = quotes()
    broker.rebalance("buy", {"A": 19}, primary, secondary, now=NOW)
    # Set an audited high-water mark; a new purchase cannot evade the emergency gate.
    with broker.db:
        broker.db.execute("UPDATE accounts SET state=json_set(state,'$.peak_equity',15000)")
    result = broker.rebalance("blocked", {"A": 19}, primary, secondary, now=NOW)
    assert result["status"] == "REJECTED"
    assert broker.state()["cooldown_until"] is not None
    assert broker.rebalance("exit", {}, primary, secondary, now=NOW)["status"] == "COMPLETED"
    assert broker.reconciliation()["matched"]
    broker.close()


def test_upstox_depth_identity_and_timestamp():
    from qts.upstox import parse_full_quote
    payload = {"status": "success", "data": {"NSE_EQ:TCS": {
        "instrument_token": "NSE_EQ|ISIN", "last_price": 100, "timestamp": NOW.isoformat(),
        "depth": {"buy": [{"price": 99, "quantity": 10}], "sell": [{"price": 101, "quantity": 12}]}}}}
    quote = parse_full_quote(payload, "NSE_EQ|ISIN")
    assert (quote.bid, quote.ask, quote.ask_size, quote.provider) == (99, 101, 12, "upstox")
    with pytest.raises(ValueError):
        parse_full_quote(payload, "WRONG")


def test_realtime_config_loads_and_matches_baseline():
    from qts.config import load_config
    config = load_config("configs/realtime-paper.yaml")
    assert config["execution"]["transmit_orders"] is False
    assert config["risk"]["max_positions"] == 5


def test_two_connections_do_not_duplicate(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    path = tmp_path / "concurrent.sqlite"
    first = PaperBroker(path, "india", 10000)
    first.close()
    def run():
        broker = PaperBroker(path, "india", 10000)
        try:
            primary, secondary = quotes()
            return broker.rebalance("one-intent", {"A": 10}, primary, secondary, now=NOW)
        finally:
            broker.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    broker = PaperBroker(path, "india", 10000)
    assert broker.state()["positions"]["A"]["quantity"] == 10
    broker.close()


def test_streamlit_three_phase_view():
    from pathlib import Path

    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    assert not app.exception
    assert app.sidebar.radio[0].options == ["INDIA", "US", "GLOBAL"]
    for phase in ("US", "GLOBAL"):
        app.sidebar.radio[0].set_value(phase).run()
        assert not app.exception


def test_fyers_validation_adapter():
    from qts.fyers import parse_depth
    payload = {"s": "ok", "d": {"NSE:TCS-EQ": {"ltp": 100, "ltt": NOW.timestamp(),
               "bids": [{"price": 98, "volume": 1}, {"price": 99, "volume": 3}],
               "ask": [{"price": 102, "volume": 2}, {"price": 101, "volume": 4}]}}}
    quote = parse_depth(payload, "NSE:TCS-EQ", "stable-isin")
    assert (quote.symbol, quote.bid, quote.ask, quote.ask_size) == ("stable-isin", 99, 101, 4)
    with pytest.raises(ValueError):
        parse_depth(payload, "UNKNOWN", "stable-isin")
