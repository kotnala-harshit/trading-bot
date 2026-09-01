import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.us_phase2_research import simulate


def test_us_research_simulation_is_finite():
    dates = pd.date_range("2020-01-01", periods=400, freq="B", tz="UTC")
    frames = {
        f"STOCK{offset}": pd.DataFrame(
            {
                "timestamp": dates,
                "open": [100 + offset + day * (offset + 1) / 100 for day in range(400)],
                "close": [100 + offset + day * (offset + 1) / 100 for day in range(400)],
            }
        )
        for offset in range(6)
    }
    benchmark = pd.DataFrame(
        {"timestamp": dates, "close": [100 + day / 100 for day in range(400)]}
    )
    result = simulate(frames, benchmark, dates[0].tz_localize(None), dates[-1].tz_localize(None))
    assert result["cagr"] > 0
    assert -1 < result["max_drawdown"] <= 0
    assert set(result).issuperset({"3m", "6m", "9m", "12m"})
