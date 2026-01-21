import pytest

from src.app import compute_metric


def test_compute_metric() -> None:
    assert compute_metric(3) == 6


def test_compute_metric_rejects_negative() -> None:
    with pytest.raises(ValueError):
        compute_metric(-1)
