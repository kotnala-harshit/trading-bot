import pytest

from qts.forecasting import benchmark_forecasts, linear_trend_20, score_model


def test_linear_forecast_and_walk_forward_scores():
    values = [100 + index * 2 for index in range(80)]
    assert linear_trend_20(values) == pytest.approx(260)
    score = score_model(values, "linear", linear_trend_20)
    assert score.mae < 1e-8
    assert score.directional_accuracy_pct == 100


def test_benchmark_returns_models_sorted_by_mae():
    scores = benchmark_forecasts([100 + index * 0.5 for index in range(100)])
    assert len(scores) == 4
    assert [score.mae for score in scores] == sorted(score.mae for score in scores)
