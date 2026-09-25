"""Hand-calculated M10 coverage for robust monthly anomaly detection."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_trends.anomalies import detect_anomalies
from wiki_trends.models import AnomalyDetectionMethod, AnomalyDirection, MonthlyPageview, ObservationStatus


def test_returns_no_anomaly_for_a_stable_series_with_nonzero_mad() -> None:
    result = detect_anomalies(_series([95, 100, 105, 100, 95, 105]))

    assert result.anomalies == []
    assert result.method is AnomalyDetectionMethod.ROBUST_Z_MAD
    assert result.limitation is None


def test_detects_a_clear_high_anomaly_with_the_specified_robust_z_score() -> None:
    result = detect_anomalies(_series([95, 100, 105] * 8 + [2_000]))

    assert len(result.anomalies) == 1
    anomaly = result.anomalies[0]
    assert anomaly.month == "2026-01"
    assert anomaly.views == 2_000
    assert anomaly.direction is AnomalyDirection.HIGH
    assert anomaly.score == pytest.approx(256.31)
    assert anomaly.method is AnomalyDetectionMethod.ROBUST_Z_MAD


def test_detects_an_extreme_low_value() -> None:
    result = detect_anomalies(_series([95, 100, 105] * 8 + [0]))

    assert len(result.anomalies) == 1
    assert result.anomalies[0].direction is AnomalyDirection.LOW
    assert result.anomalies[0].views == 0


def test_uses_iqr_fallback_when_mad_is_zero_but_spread_is_meaningful() -> None:
    result = detect_anomalies(_series([0, 0, 0, 0, 0, 1, 2, 3, 100]))

    assert [(anomaly.views, anomaly.method) for anomaly in result.anomalies] == [
        (100, AnomalyDetectionMethod.IQR_FALLBACK)
    ]


def test_records_limitation_without_failing_for_a_constant_series() -> None:
    result = detect_anomalies(_series([100] * 24))

    assert result.anomalies == []
    assert result.method is None
    assert result.limitation is not None
    assert "MAD and IQR are zero" in result.limitation


def test_excludes_unknown_months_from_anomaly_statistics() -> None:
    series = _series([95, 100, 105, 100, 95, 105])
    series.append(MonthlyPageview(month=date(2026, 7, 1), status=ObservationStatus.UNKNOWN))

    result = detect_anomalies(series)

    assert result.observed_months == 6
    assert result.anomalies == []


def test_rejects_duplicate_months() -> None:
    duplicate_month = date(2024, 1, 1)

    with pytest.raises(ValueError, match="at most one observation"):
        detect_anomalies(
            [
                MonthlyPageview(month=duplicate_month, views=100),
                MonthlyPageview(month=duplicate_month, views=200),
            ]
        )


def _series(values: list[int]) -> list[MonthlyPageview]:
    """Create a contiguous series beginning in January 2024."""
    return [
        MonthlyPageview(month=date(2024 + index // 12, index % 12 + 1, 1), views=value)
        for index, value in enumerate(values)
    ]
