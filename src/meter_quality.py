"""
Quality classification of the real meters before feature extraction.

The data audit (docs/datensichtung.md) showed the raw exports are not
uniformly usable: two meters are completely dead, several look like
network-side measuring points rather than HAST, coverage has large
holes. This module sorts every meter into exactly one class:

    auswertbar              usable for HAST feature extraction
    inaktiv                 mostly zero power/flow over the whole history
    verdaechtig_netzseitig  high power AND many negative readings -
                            probably a plant / network meter, not a HAST
    geringe_abdeckung       too little hourly coverage in the analysis
                            window for reliable features
    schema_abweichend       export file violates the 8-column schema

Classification is deliberately conservative and REPORT-DRIVEN: nothing
is deleted; downstream code decides what to consume. Topology
assignment ("is the Zählernummer in Nodes_Edges.ods?") is a separate
boolean column `zugeordnet`, NOT a quality class - unassigned meters
stay classified so they can be stitched in later via Zuordnung.xlsx.

Output: data/processed/meter_quality.csv

Usage:

    python -m src.meter_quality
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .load_timeseries import DATA_DIR, discover_meter_files, load_meter_timeseries

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

# --- thresholds (tune here; every change shifts who gets analysed) ----------

# Analysis window: the most recent 12 contiguous months per meter.
WINDOW_DAYS = 365

# Minimum share of hours actually present in the analysis window.
# Below this, features like monthly flow trends and FFT oscillation
# become unreliable -> class "geringe_abdeckung".
MIN_WINDOW_COVERAGE_PCT = 60.0

# "inaktiv": share of hours with Power <= 0 over the WHOLE history.
# Catches dead / never-commissioned meters (e.g. 100 % zero for years).
INACTIVE_POWER_LE0_PCT = 90.0

# "verdaechtig_netzseitig": BOTH conditions must hold. HAST rarely
# exceed ~50 kW (largest Anschlusswert is 500 kW but p90 stays low);
# sustained high power combined with a large share of NEGATIVE flow
# readings is the signature of bidirectional network-side metering.
# The two legitimate 500 kW hubs have < 1 % negative readings and are
# not caught by this rule.
NETSIDE_POWER_P90_KW = 100.0
NETSIDE_FLOW_NEG_PCT = 5.0

CLASSES = ("auswertbar", "inaktiv", "verdaechtig_netzseitig",
           "geringe_abdeckung", "schema_abweichend")


def classify_meter(zid: int, data_dir: Path = DATA_DIR) -> dict:
    """Compute quality metrics and the class for one meter."""
    try:
        df = load_meter_timeseries(zid, data_dir)
    except ValueError as e:  # schema violation reported by the loader
        return {"Zählernummer": zid, "quality_class": "schema_abweichend",
                "note": str(e)}

    power = df["Power (kW)"].astype(float)
    flow = df["Volume flow (l/h)"].astype(float)
    ts = df["Timestamp"]

    win_end = ts.iloc[-1]
    win_start = win_end - pd.Timedelta(days=WINDOW_DAYS)
    in_win = ts > win_start
    window_coverage_pct = round(100 * int(in_win.sum()) / (WINDOW_DAYS * 24), 1)

    m = {
        "Zählernummer": zid,
        "n_rows": len(df),
        "ts_min": ts.iloc[0],
        "ts_max": win_end,
        "window_start": win_start,
        "window_coverage_pct": window_coverage_pct,
        "power_le0_pct": round(100 * float((power <= 0).mean()), 1),
        "power_p90_kw": round(float(power.quantile(0.90)), 2),
        "flow_neg_pct": round(100 * float((flow < 0).mean()), 1),
        "note": "",
    }

    # precedence: a dead meter is "inaktiv" even if coverage is also low
    if m["power_le0_pct"] >= INACTIVE_POWER_LE0_PCT:
        m["quality_class"] = "inaktiv"
    elif (m["power_p90_kw"] >= NETSIDE_POWER_P90_KW
          and m["flow_neg_pct"] >= NETSIDE_FLOW_NEG_PCT):
        m["quality_class"] = "verdaechtig_netzseitig"
    elif window_coverage_pct < MIN_WINDOW_COVERAGE_PCT:
        m["quality_class"] = "geringe_abdeckung"
    else:
        m["quality_class"] = "auswertbar"
    return m


def classify_all(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Classify every discovered meter; adds topology assignment."""
    rows = [classify_meter(zid, data_dir)
            for zid in sorted(discover_meter_files(data_dir))]
    df = pd.DataFrame(rows)

    try:
        from . import load_data as ld
        known = set(ld.load_logical_nodes()["Zählernummer"].astype(int))
        df["zugeordnet"] = df["Zählernummer"].isin(known)
    except Exception as e:
        df["zugeordnet"] = pd.NA
        print(f"  ! topology cross-check skipped: {e}")

    return df


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path,
                   default=PROCESSED / "meter_quality.csv")
    args = p.parse_args()

    print("→ classifying meter quality (read-only, nothing deleted)")
    df = classify_all()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"  → {args.out}")
    print()
    print(df["quality_class"].value_counts().to_string())
    print()
    print("zugeordnet (Zählernummer in Nodes_Edges.ods):")
    print(df.groupby("zugeordnet", dropna=False)["quality_class"]
            .value_counts().to_string())
