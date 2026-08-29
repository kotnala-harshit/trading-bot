from qts.risk_plan import size_long_position


def test_position_plan_respects_caps():
    plan = size_long_position(1_000_000, 1_000)
    assert plan.shares == 100
    assert plan.allocation == 100_000
    assert plan.risk_at_stop == 5_000
    assert plan.stop_price == 950


def test_expensive_share_respects_allocation():
    assert size_long_position(1_000_000, 100_000).shares == 1
