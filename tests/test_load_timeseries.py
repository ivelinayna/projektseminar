"""
Tests for src.load_timeseries using small synthetic dummy CSVs.

Runs standalone (no raw data needed):

    python -m tests.test_load_timeseries          # plain-assert runner
    python -m pytest tests/test_load_timeseries.py
"""

import tempfile
from pathlib import Path

import pandas as pd

from src.load_timeseries import (
    SCHEMA,
    discover_meter_files,
    load_meter_timeseries,
    materialize_meters,
)


def _dummy_frame(start: str, hours: int, energy0: float) -> pd.DataFrame:
    """Hourly dummy rows in the real export style: descending timestamps."""
    ts = pd.date_range(start, periods=hours, freq="h")
    df = pd.DataFrame({
        "Timestamp": ts,
        "Energy (kWh)": [energy0 + i for i in range(hours)],
        "Volume flow (l/h)": 100.0,
        "Power (kW)": 5.0,
        "Temperature difference (°C)": 25.0,
        "Flow temperature (°C)": 70.0,
        "Return temperature (°C)": 45.0,
        "Volume (m³)": 1.0,
    })
    return df.iloc[::-1].reset_index(drop=True)  # exports are descending


def _write_dummy_exports(d: Path) -> None:
    # old export: Jan 1-4 with energy counter A
    _dummy_frame("2024-01-01", 96, energy0=1000).to_csv(
        d / "11111111__n.csv", index=False)
    # new export: Jan 3-6, overlaps Jan 3-4, energy counter B (newer wins)
    _dummy_frame("2024-01-03", 96, energy0=2000).to_csv(
        d / "11111111_2025n.csv", index=False)
    # a second meter with a single file
    _dummy_frame("2024-02-01", 24, energy0=0).to_csv(
        d / "22222222_2025n.csv", index=False)
    # non-meter CSV must be ignored
    pd.DataFrame({"foo": [1]}).to_csv(d / "notes.csv", index=False)


def test_discover_missing_dir_raises():
    try:
        discover_meter_files(Path(tempfile.mkdtemp()) / "does-not-exist")
    except FileNotFoundError as e:
        assert "data/raw" in str(e) or "not found" in str(e)
    else:
        raise AssertionError("expected FileNotFoundError for missing dir")


def test_discover_empty_dir_raises():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            discover_meter_files(Path(tmp))
        except FileNotFoundError as e:
            assert "no meter CSVs" in str(e)
        else:
            raise AssertionError("expected FileNotFoundError for empty dir")


def test_discover_and_grouping():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _write_dummy_exports(d)
        meters = discover_meter_files(d)
        assert set(meters) == {11111111, 22222222}
        assert len(meters[11111111]) == 2
        assert len(meters[22222222]) == 1


def test_merge_sort_dedupe_newer_wins():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _write_dummy_exports(d)
        df = load_meter_timeseries(11111111, d)
        assert list(df.columns) == SCHEMA
        assert df["Timestamp"].is_monotonic_increasing
        assert not df["Timestamp"].duplicated().any()
        # 96h + 96h with 48h overlap -> 144 unique hours
        assert len(df) == 144
        # in the overlap the newer export (energy0=2000) must win
        overlap = df[df["Timestamp"] == pd.Timestamp("2024-01-03 00:00:00")]
        assert overlap["Energy (kWh)"].iloc[0] >= 2000


def test_unknown_meter_raises():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _write_dummy_exports(d)
        try:
            load_meter_timeseries(99999999, d)
        except FileNotFoundError as e:
            assert "99999999" in str(e)
        else:
            raise AssertionError("expected FileNotFoundError for unknown meter")


def test_bad_schema_raises():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _dummy_frame("2024-01-01", 5, 0).drop(
            columns=["Power (kW)"]).to_csv(d / "33333333__n.csv", index=False)
        try:
            load_meter_timeseries(33333333, d)
        except ValueError as e:
            assert "Power (kW)" in str(e)
        else:
            raise AssertionError("expected ValueError for missing column")


def test_materialize_layout_matches_features_input():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        _write_dummy_exports(d)
        out = Path(tmp) / "meters"
        inv = materialize_meters(out, d)
        files = sorted(out.glob("*.csv"))
        # one file per meter, stem is the plain Zählernummer (int-parseable,
        # which is what features.features_for_directory expects)
        assert [f.stem for f in files] == ["11111111", "22222222"]
        assert all(f.stem.isdigit() for f in files)
        assert len(inv) == 2
        assert inv.loc[inv["Zählernummer"] == 11111111, "n_rows"].iloc[0] == 144


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed")
