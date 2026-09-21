"""
Tests for src.window_features (14-day Zustandsfenster etc.).

Synthetic hourly data only - data/raw is empty in this worktree. The
heating meter has a plausible daily load cycle; the constant meter
gives exact expectations for the 8760 h/year normalisation of
energy_kwh_year and full_load_hours per window.

Runs standalone (no raw data needed):

    python -m tests.test_window_features    # plain-assert runner
    python -m pytest tests/test_window_features.py
"""

import numpy as np
import pandas as pd

from src.window_features import features_for_window, windowed_features_for_meter


def _heating_meter(start: str = "2023-01-01", days: int = 70,
                   seed: int = 1) -> pd.DataFrame:
    """Plausible heating curve: base load + daily cycle + noise."""
    rng = np.random.default_rng(seed)
    hours = days * 24
    ts = pd.date_range(start, periods=hours, freq="h")
    hod = ts.hour.to_numpy()
    power = 8.0 + 6.0 * np.sin(2 * np.pi * (hod - 15) / 24) \
        + rng.normal(0, 0.4, hours)
    power = np.clip(power, 0.5, None)
    flow = power * 4.0
    dt = np.clip(22.0 + rng.normal(0, 1.0, hours), 5.0, None)
    df = pd.DataFrame({
        "energy": np.cumsum(power),            # kWh, hourly steps
        "flow": flow,
        "power": power,
        "dt": dt,
        "vl": 70.0,
        "rt": 70.0 - dt,
        "volume": np.cumsum(flow) / 1000.0,    # m³
    }, index=ts.rename("Timestamp"))
    return df


def _constant_meter(start: str, days: int) -> pd.DataFrame:
    """Constant-load meter: 10 kWh per hour, peak 10 kW."""
    hours = days * 24
    ts = pd.date_range(start, periods=hours, freq="h")
    df = pd.DataFrame({
        "energy": np.arange(hours, dtype=float) * 10.0,
        "flow": 100.0,
        "power": 10.0,
        "dt": 25.0,
        "vl": 70.0,
        "rt": 45.0,
        "volume": np.arange(hours, dtype=float),
    }, index=ts.rename("Timestamp"))
    return df


def test_window_count_and_full_coverage():
    # 70 days from a midnight -> exactly 5 non-overlapping 14-day windows.
    out = windowed_features_for_meter(_heating_meter(days=70))
    assert len(out) == 5
    assert (out["n_hours"] == 14 * 24).all()
    assert (out["coverage"] == 1.0).all()
    assert not out["low_coverage"].any()
    assert not out["meter_change"].any()
    # windows tile the calendar without gaps or overlaps
    starts = pd.DatetimeIndex(out["window_start"])
    assert (starts[1:] - starts[:-1] == pd.Timedelta(days=14)).all()


def test_step_days_overlap():
    # 70 days, window 14 d, step 7 d -> starts at day 0,7,...,63.
    out = windowed_features_for_meter(_heating_meter(days=70),
                                      step_days=7)
    assert len(out) == 10
    starts = pd.DatetimeIndex(out["window_start"])
    assert (starts[1:] - starts[:-1] == pd.Timedelta(days=7)).all()


def test_coverage_and_low_coverage_flag_with_gap():
    df = _heating_meter(days=70)
    # 8-day gap (192 h) inside the second window (Jan 15 - Jan 28).
    gap = (df.index >= "2023-01-16") & (df.index < "2023-01-24")
    out = windowed_features_for_meter(df[~gap])
    assert len(out) == 5  # gap shortens the window, no window is lost
    row = out.iloc[1]
    assert row["n_hours"] == 336 - 192
    assert np.isclose(row["coverage"], (336 - 192) / 336)
    assert row["coverage"] < 0.5
    assert bool(row["low_coverage"]) is True
    # all other windows are complete and not flagged
    rest = out.drop(index=out.index[1])
    assert (rest["coverage"] == 1.0).all()
    assert not rest["low_coverage"].any()


def test_meter_change_flag():
    df = _heating_meter(days=70)
    out = windowed_features_for_meter(
        df, meter_changes=[pd.Timestamp("2023-01-20 12:00")])
    assert out["meter_change"].tolist() == [False, True, False, False, False]
    # a change exactly at a window boundary belongs to the later window
    # (windows are [start, end)).
    out = windowed_features_for_meter(
        df, meter_changes=[pd.Timestamp("2023-01-29 00:00")])
    assert out["meter_change"].tolist() == [False, False, True, False, False]


def test_full_load_hours_normalised_per_window():
    # 10 kWh/h, peak 10 kW -> 87600 kWh/year -> 8760 full load hours,
    # independent of how many windows the history is cut into.
    out = windowed_features_for_meter(_constant_meter("2023-01-01", days=30))
    full = out[out["coverage"] == 1.0]
    assert len(full) == 2  # third window is a 2-day stub
    assert np.allclose(full["energy_kwh_year"], 87600.0, rtol=1e-3)
    assert np.allclose(full["full_load_hours"], 8760.0, rtol=1e-3)
    # stub window: 48 of 336 h covered, flagged but kept
    stub = out.iloc[-1]
    assert np.isclose(stub["coverage"], 48 / 336)
    assert bool(stub["low_coverage"]) is True


def test_nan_sparse_window_does_not_crash():
    df = _heating_meter(days=70)
    sparse = (df.index >= "2023-01-29") & (df.index < "2023-02-12")
    df.loc[sparse, ["energy", "flow", "power", "dt", "vl", "rt", "volume"]] = np.nan
    out = windowed_features_for_meter(df)  # must not raise
    assert len(out) == 5
    row = out.iloc[2]
    assert row["n_hours"] == 336  # rows exist, content is NaN
    assert row["coverage"] == 1.0
    assert np.isnan(row["rt_mean_winter"])
    assert np.isnan(row["energy_kwh_year"])


def test_empty_window_kept_as_metadata_row():
    df = _heating_meter(days=70)
    # drop the entire second window (Jan 15 - Jan 28)
    gap = (df.index >= "2023-01-15") & (df.index < "2023-01-29")
    out = windowed_features_for_meter(df[~gap])
    assert len(out) == 5
    row = out.iloc[1]
    assert row["n_hours"] == 0
    assert row["coverage"] == 0.0
    assert bool(row["low_coverage"]) is True
    assert bool(row["meter_change"]) is False
    assert np.isnan(row["rt_mean_winter"])


def test_features_for_window_metadata_on_arbitrary_slice():
    df = _heating_meter(days=70)
    sl = df.loc["2023-02-01":"2023-02-10 23:00"]
    f = features_for_window(sl)
    assert f["window_start"] == sl.index[0]
    assert f["window_end"] == sl.index[-1]
    assert f["n_hours"] == len(sl) == 10 * 24
    assert f["coverage"] == 1.0
    # slice with internal gap: coverage counts missing calendar hours
    sl_gap = sl.drop(sl.index[48:96])
    f_gap = features_for_window(sl_gap)
    assert np.isclose(f_gap["coverage"], (240 - 48) / 240)


def test_output_is_long_format_with_meta_columns_first():
    out = windowed_features_for_meter(_heating_meter(days=70))
    meta = ["window_start", "window_end", "n_hours", "coverage",
            "low_coverage", "meter_change"]
    assert list(out.columns[:6]) == meta
    assert "rt_mean_winter" in out.columns  # feature set passed through


if __name__ == "__main__":
    test_window_count_and_full_coverage()
    test_step_days_overlap()
    test_coverage_and_low_coverage_flag_with_gap()
    test_meter_change_flag()
    test_full_load_hours_normalised_per_window()
    test_nan_sparse_window_does_not_crash()
    test_empty_window_kept_as_metadata_row()
    test_features_for_window_metadata_on_arbitrary_slice()
    test_output_is_long_format_with_meta_columns_first()
    print("all window feature tests passed")
