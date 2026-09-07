import numpy as np
import pandas as pd
import pytest

from qts.research import eligible_members, rank_at, simulate


def dataset():
    days = pd.bdate_range("2020-01-01", periods=330)
    close = 100 * np.cumprod(1 + .001 + np.sin(np.arange(330)) * .005)
    prices = pd.DataFrame({"date": days, "security_id": "stable-id", "open": close * .999,
                           "close": close, "raw_close": close, "traded_value": 200_000_000,
                           "quality_ok": True})
    members = pd.DataFrame({"security_id": ["stable-id"], "effective_from": [days[0]],
                            "effective_to": [pd.Timestamp("2030-01-01")], "known_at": [days[0]]})
    return prices, members


def test_no_lookahead_and_membership():
    prices, members = dataset()
    day = prices.date.iloc[260]
    before = rank_at(prices, members, day)
    altered = prices.copy()
    altered.loc[altered.date >= day, "close"] *= 100
    pd.testing.assert_series_equal(before, rank_at(altered, members, day))
    members["known_at"] = day + pd.Timedelta(days=1)
    assert not eligible_members(members, day)
    assert rank_at(prices, members, day).empty


def test_cost_stress_and_missing_holding_block():
    prices, members = dataset()
    free, _ = simulate(prices, members, review=20, cost_bps=0)
    costly, _ = simulate(prices, members, review=20, cost_bps=50)
    assert costly.equity.iloc[-1] < free.equity.iloc[-1]
    assert costly.costs.iloc[-1] > 0
    missing = prices.drop(index=prices.index[281])
    # A second security supplies the exchange session that the held security lacks.
    extra = prices.iloc[[281]].assign(security_id="other")
    with pytest.raises(ValueError, match="held security"):
        simulate(pd.concat([missing, extra]), members, review=20)


def test_security_identity_reuse_and_raw_immutability(tmp_path):
    from qts.storage import resolve_security, store_raw
    master = pd.DataFrame({"security_id": ["old", "new"], "provider": ["x", "x"],
                           "symbol": ["ABC", "ABC"], "valid_from": pd.to_datetime(["2000-01-01", "2020-01-01"]),
                           "valid_to": pd.to_datetime(["2020-01-01", "2030-01-01"]),
                           "known_at": pd.to_datetime(["2000-01-01", "2020-01-01"])})
    assert resolve_security(master, "x", "ABC", "2010-01-01") == "old"
    assert resolve_security(master, "x", "ABC", "2021-01-01") == "new"
    path = store_raw(tmp_path, b'{"price":100}')
    assert store_raw(tmp_path, b'{"price":100}') == path
    assert store_raw(tmp_path, b'{"price":101}') != path
    assert path.read_bytes() == b'{"price":100}'


def test_planner_uses_completed_session_and_one_target():
    from qts.planning import plan_targets
    prices, members = dataset()
    settings = {"lookback": 63, "min_history": 252, "min_price": 50,
                "min_median_traded_value": 100000000, "keep_rank": 10,
                "max_positions": 5, "max_weight": .20}
    day = prices.date.iloc[260]
    plan = plan_targets("india", settings, {"cash": 10000, "positions": {}}, prices, members, day)
    again = plan_targets("india", settings, {"cash": 10000, "positions": {}}, prices, members, day)
    assert plan == again
    assert list(plan["targets"]) == ["stable-id"]
    assert pd.Timestamp(plan["signal_at"]).tz_localize(None) < day
