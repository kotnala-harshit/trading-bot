from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import sqrt
from statistics import mean

import numpy as np

Forecaster = Callable[[list[float]], float]


def naive(values: list[float]) -> float:
    return values[-1]


def moving_average_5(values: list[float]) -> float:
    return mean(values[-5:])


def drift(values: list[float]) -> float:
    window = values[-20:]
    return window[-1] + (window[-1] - window[0]) / max(1, len(window) - 1)


def linear_trend_20(values: list[float]) -> float:
    window = values[-20:]
    if len(window) < 2:
        return window[-1]
    x = np.arange(len(window), dtype=float)
    slope, intercept = np.polyfit(x, np.asarray(window), 1)
    return max(0.0, float(intercept + slope * len(window)))


@dataclass(frozen=True)
class ForecastScore:
    model: str
    next_close: float
    mae: float
    rmse: float
    directional_accuracy_pct: float
    observations: int


def score_model(
    values: list[float], name: str, model: Forecaster, minimum_train: int = 40
) -> ForecastScore:
    if len(values) <= minimum_train:
        raise ValueError("Insufficient history for walk-forward forecasting")
    predictions: list[float] = []
    actuals: list[float] = []
    directions: list[bool] = []
    for index in range(minimum_train, len(values)):
        history = values[:index]
        prediction = model(history)
        actual = values[index]
        predictions.append(prediction)
        actuals.append(actual)
        directions.append((prediction >= history[-1]) == (actual >= history[-1]))
    errors = [prediction - actual for prediction, actual in zip(predictions, actuals)]
    return ForecastScore(
        model=name,
        next_close=model(values),
        mae=mean(abs(error) for error in errors),
        rmse=sqrt(mean(error * error for error in errors)),
        directional_accuracy_pct=mean(directions) * 100,
        observations=len(actuals),
    )


def benchmark_forecasts(values: list[float]) -> list[ForecastScore]:
    models: list[tuple[str, Forecaster]] = [
        ("Naive last close", naive),
        ("5-day average", moving_average_5),
        ("20-day drift", drift),
        ("20-day linear trend", linear_trend_20),
    ]
    return sorted(
        (score_model(values, name, model) for name, model in models), key=lambda score: score.mae
    )
