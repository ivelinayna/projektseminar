"""
Tests for src.features annualisation of the energy aggregates.

Regression test for the full_load_hours bug: histories span 0.88-4.72
years, so first-to-last deltas must be normalised to one year (8760 h)
before dividing by peak power.

Runs standalone (no raw data needed):

    python -m tests.test_features          # plain-assert runner
    python -m pytest tests/test_features.py
"""

import numpy as np
import pandas as pd

from src.features import features_for_meter


def _dummy_meter(start: str, hours: int) -> pd.DataFrame:
    """Constant-load meter: 1 kWh per hour, peak 10 kW."""
    ts = pd.date_range(start, periods=hours, freq="h")
    df = pd.DataFrame({
        "energy": np.arange(hours, dtype=float),  # +1 kWh/h
        "flow": 100.0,
        "power": 10.0,
        "dt": 25.0,
        "vl": 70.0,
        "rt": 45.0,
        "volume": np.arange(hours, dtype=float) * 0.1,
    })
    df = df.set_index(ts.rename("Timestamp"))
    df["month"] = df.index.month
    df["hour"] = df.index.hour
    return df


def test_energy_normalised_to_one_year():
    # Two full years of history (2 * 8760 h, starts and ends in the same
    # calendar month so seasonal masks behave identically per year).
    df = _dummy_meter("2022-01-01", 2 * 8760)
    f = features_for_meter(df)
    # Span between first and last timestamp is 2*8760 - 1 hours; energy
    # delta over that span is (2*8760 - 1) kWh -> exactly 8760 kWh/year.
    assert np.isclose(f["energy_kwh_year"], 8760.0, rtol=1e-3)
    # full_load_hours = 8760 kWh / 10 kW = 876 h, not 1752 h.
    assert np.isclose(f["full_load_hours"], 876.0, rtol=1e-3)


def test_single_year_unchanged():
    df = _dummy_meter("2022-01-01", 8760)
    f = features_for_meter(df)
    assert np.isclose(f["energy_kwh_year"], 8760.0, rtol=1e-3)
    assert np.isclose(f["full_load_hours"], 876.0, rtol=1e-3)


def test_volume_normalised_to_one_year():
    df = _dummy_meter("2022-01-01", 2 * 8760)
    f = features_for_meter(df)
    assert np.isclose(f["volume_m3_year"], 876.0, rtol=1e-3)


if __name__ == "__main__":
    test_energy_normalised_to_one_year()
    test_single_year_unchanged()
    test_volume_normalised_to_one_year()
    print("all feature tests passed")
