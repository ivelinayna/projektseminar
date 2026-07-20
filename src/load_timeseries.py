"""
Loader for the real ÜZ meter time-series CSVs.

The exports live directly in ``data/raw/`` as one CSV per meter and
export generation:

    <Zählernummer>__n.csv       older export  (ends ~2024-05)
    <Zählernummer>_2025n.csv    newer export  (ends ~2025-07)

Both generations cover overlapping time ranges, so per meter we
concatenate all files, sort ascending and drop duplicate timestamps.
Column schema is identical to the synthetic data (`synth_data.py`):

    Timestamp, Energy (kWh), Volume flow (l/h), Power (kW),
    Temperature difference (°C), Flow temperature (°C),
    Return temperature (°C), Volume (m³)

Energy and Volume are cumulative counters; the rest are (roughly)
hourly instantaneous values. Known quirks of the raw exports, kept
as-is here so downstream code sees the real data:

  * timestamps are minute-offset (e.g. 13:01) and descending in file order
  * occasional negative flow / power readings (metering noise)
  * per-meter history starts/ends at different dates (2021-2025)

``materialize_meters`` writes one clean ``<Zählernummer>.csv`` per meter
into a target directory, which is exactly the layout that
``features.features_for_directory`` already consumes - the synthetic
pipeline interface stays untouched.

Deliberately NOT decided here (needs a project decision before the real
series feed fault detection): which analysis window to use (the feature
set assumes ~1 year), and how to stitch meter swaps (see Zuordnung.xlsx:
some CSV meter numbers are replacements not present in Nodes_Edges.ods).

CLI:

    python -m src.load_timeseries            # inventory summary
    python -m src.load_timeseries --materialize data/processed/real_meters
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# canonical schema shared with synth_data.py
SCHEMA = [
    "Timestamp",
    "Energy (kWh)",
    "Volume flow (l/h)",
    "Power (kW)",
    "Temperature difference (°C)",
    "Flow temperature (°C)",
    "Return temperature (°C)",
    "Volume (m³)",
]

_FILE_RE = re.compile(r"^(\d+)_.*\.csv$")


def discover_meter_files(data_dir: Path = DATA_DIR) -> dict[int, list[Path]]:
    """Map Zählernummer -> list of export CSVs found in `data_dir`.

    Only files matching ``<digits>_*.csv`` directly in `data_dir` count;
    subdirectories (e.g. data/raw/synthetic/) are not scanned.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(
            f"raw data directory not found: {data_dir} - place the ÜZ "
            "meter CSVs (e.g. 41566330__n.csv) into data/raw/")
    meters: dict[int, list[Path]] = {}
    for f in sorted(data_dir.glob("*.csv")):
        m = _FILE_RE.match(f.name)
        if m:
            meters.setdefault(int(m.group(1)), []).append(f)
    if not meters:
        raise FileNotFoundError(
            f"no meter CSVs matching '<Zählernummer>_*.csv' found in "
            f"{data_dir} - expected files like 41566330__n.csv or "
            "41566330_2025n.csv from the ÜZ export")
    return meters


def load_meter_timeseries(zaehlernummer: int,
                          data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load, merge and clean all export files for one meter.

    Returns a DataFrame in the canonical 8-column schema, sorted by
    ascending Timestamp, duplicate timestamps dropped (the newer export
    generation wins where the files overlap).
    """
    meters = discover_meter_files(data_dir)
    if zaehlernummer not in meters:
        raise FileNotFoundError(
            f"no CSV export for Zählernummer {zaehlernummer} in "
            f"{Path(data_dir)} - expected {zaehlernummer}__n.csv or "
            f"{zaehlernummer}_2025n.csv")
    frames = []
    for path in meters[zaehlernummer]:
        df = pd.read_csv(path, parse_dates=["Timestamp"])
        missing = [c for c in SCHEMA if c not in df.columns]
        if missing:
            raise ValueError(
                f"{path.name}: missing expected columns {missing} - "
                f"got {list(df.columns)}")
        frames.append(df[SCHEMA])
    # concat oldest export first (by its last timestamp), so with
    # keep='last' the newer export generation wins on duplicate timestamps
    frames.sort(key=lambda f: f["Timestamp"].max())
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("Timestamp", kind="stable")
    out = out.drop_duplicates(subset="Timestamp", keep="last")
    return out.reset_index(drop=True)


def materialize_meters(out_dir: Path,
                       data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Write one merged ``<Zählernummer>.csv`` per meter into `out_dir`.

    The resulting directory has the same layout as the synthetic
    ``data/raw/synthetic/meters/`` and can be fed straight into
    ``features.features_for_directory``. Returns an inventory DataFrame
    (one row per meter: files merged, rows, time range).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory = []
    for zid, files in sorted(discover_meter_files(data_dir).items()):
        df = load_meter_timeseries(zid, data_dir)
        df.to_csv(out_dir / f"{zid}.csv", index=False)
        inventory.append({
            "Zählernummer": zid,
            "n_files": len(files),
            "n_rows": len(df),
            "ts_min": df["Timestamp"].min(),
            "ts_max": df["Timestamp"].max(),
        })
    return pd.DataFrame(inventory)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--materialize", type=Path, metavar="DIR",
                   help="write merged per-meter CSVs into DIR")
    args = p.parse_args()

    meters = discover_meter_files()
    n_files = sum(len(v) for v in meters.values())
    print(f"found {n_files} export CSVs for {len(meters)} meters in {DATA_DIR}")

    try:
        from . import load_data as ld
        known = set(ld.load_logical_nodes()["Zählernummer"].astype(int))
        in_topo = len(set(meters) & known)
        print(f"  {in_topo} meters match Nodes_Edges.ods, "
              f"{len(meters) - in_topo} do not (meter swaps? see Zuordnung.xlsx), "
              f"{len(known - set(meters))} topology meters have no CSV")
    except Exception as e:  # topology file missing is fine for a pure inventory
        print(f"  (skipping topology cross-check: {e})")

    if args.materialize:
        inv = materialize_meters(args.materialize)
        print(f"wrote {len(inv)} merged CSVs -> {args.materialize}")
        print(f"  time range: {inv['ts_min'].min()} .. {inv['ts_max'].max()}")
        print(f"  rows per meter: min {inv['n_rows'].min()}, "
              f"median {int(inv['n_rows'].median())}, max {inv['n_rows'].max()}")
