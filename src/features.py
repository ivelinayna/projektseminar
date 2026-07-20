"""
Feature engineering for HAST time series.

Each meter CSV (one year, hourly) collapses into ~25 numeric features
per HAST. Features are designed to surface the three anomaly families
called out by ÜZ Mainfranken plus the fault types we observed in the
optimisation Excel:

    rt_mean_winter        excessive return temperature (winter, the regime that matters)
    rt_p95                upper-tail RT - flags chronic poor cooling
    dt_mean_loaded        ΔT under load (low ΔT = poor heat transfer / fouling)
    dt_std_loaded         noisy ΔT - control hysteresis indicator
    summer_flow_share     fraction of summer hours with nonzero flow (continuous flow / leakage)
    summer_flow_baseline  median flow in July/August (continuous flow proxy)
    flow_ceiling_drop     trend of the 95th-percentile flow over the year (filter fouling)
    peak_load_share       max(power) / Anschlusswert  (oversized if low)
    p95_load_share        same with 95th percentile
    flow_oscillation      6 h periodicity power in the flow signal (control hysteresis)
    standby_dt            dT during near-zero load periods (insulation losses)
    energy_kwh_year       annual energy
    volume_m3_year        annual volume
    full_load_hours       energy / peak power - efficiency hint

Some features are NaN if the input is too sparse; downstream models must
handle that.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def _load_meter_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Timestamp"])
    df = df.rename(columns={
        "Energy (kWh)": "energy",
        "Volume flow (l/h)": "flow",
        "Power (kW)": "power",
        "Temperature difference (°C)": "dt",
        "Flow temperature (°C)": "vl",
        "Return temperature (°C)": "rt",
        "Volume (m³)": "volume",
    })
    df = df.set_index("Timestamp").sort_index()
    df["month"] = df.index.month
    df["hour"] = df.index.hour
    return df


def features_for_meter(df: pd.DataFrame,
                       anschluss_kw: Optional[float] = None) -> dict:
    """Compute HAST-level features from one year of hourly meter data."""
    f = {}

    # --- regime masks -----------------------------------------------------
    winter = df["month"].isin([12, 1, 2, 3])
    summer = df["month"].isin([6, 7, 8])
    loaded = df["power"] > 0.5  # delivering meaningful heat

    # --- temperatures -----------------------------------------------------
    f["rt_mean_winter"] = df.loc[winter, "rt"].mean()
    f["rt_p95"] = df["rt"].quantile(0.95)
    f["vl_mean_winter"] = df.loc[winter, "vl"].mean()
    f["dt_mean_loaded"] = df.loc[loaded, "dt"].mean()
    f["dt_std_loaded"] = df.loc[loaded, "dt"].std()
    f["dt_p10_loaded"] = df.loc[loaded, "dt"].quantile(0.1)

    # ÜZ anomaly: RT too high under load -> bad spreading (often >50 °C
    # with VL ~70 °C is a red flag).
    f["rt_above_50_share_loaded"] = (df.loc[loaded, "rt"] > 50).mean()

    # --- continuous flow / leakage ---------------------------------------
    summer_flow = df.loc[summer, "flow"]
    f["summer_flow_share"] = (summer_flow > 5).mean()
    f["summer_flow_baseline"] = summer_flow.median()
    # Heat for "DHW only" days in summer should be ~constant low; high
    # flow with low ΔT in summer means circulation losses or leakage.
    summer_lowload = summer & (df["power"] < 0.5)
    f["summer_idle_flow_median"] = df.loc[summer_lowload, "flow"].median()

    # --- filter fouling: descending flow ceiling --------------------------
    # Months without any data are dropped, not treated as flow 0 - real
    # exports have multi-week gaps that would otherwise fake a collapse.
    # x is the calendar month index so gaps keep their true spacing.
    monthly_p95_flow = df["flow"].resample("ME").quantile(0.95).dropna()
    if monthly_p95_flow.size >= 6:
        idx = monthly_p95_flow.index
        x = idx.year * 12 + idx.month
        slope = np.polyfit(x - x[0], monthly_p95_flow.values, 1)[0]
        f["flow_ceiling_slope_per_month"] = slope
    else:
        f["flow_ceiling_slope_per_month"] = np.nan

    # --- load utilisation -------------------------------------------------
    peak = df["power"].max()
    p95 = df["power"].quantile(0.95)
    f["peak_load_kw"] = peak
    f["p95_load_kw"] = p95
    if anschluss_kw and anschluss_kw > 0:
        f["peak_load_share"] = peak / anschluss_kw
        f["p95_load_share"] = p95 / anschluss_kw
    else:
        f["peak_load_share"] = np.nan
        f["p95_load_share"] = np.nan

    # --- control hysteresis: power at 6 h period in flow signal -----------
    flow = df["flow"].values.astype(float)
    flow = flow - np.nanmean(flow)
    if len(flow) > 0 and np.nanstd(flow) > 0:
        # Sample a year-long FFT, look for energy at 4 h - 12 h cycles
        spec = np.abs(np.fft.rfft(np.nan_to_num(flow)))
        freqs = np.fft.rfftfreq(len(flow), d=1.0)  # cycles per hour
        mask = (freqs >= 1 / 12) & (freqs <= 1 / 4)
        f["flow_short_cycle_power"] = (spec[mask] ** 2).sum() / (spec ** 2).sum()
    else:
        f["flow_short_cycle_power"] = np.nan

    # --- standby / idle losses --------------------------------------------
    idle = df["power"] < 0.2
    f["idle_share"] = idle.mean()
    f["standby_dt"] = df.loc[idle, "dt"].mean()

    # --- annual aggregates ------------------------------------------------
    f["energy_kwh_year"] = df["energy"].iloc[-1] - df["energy"].iloc[0]
    f["volume_m3_year"] = df["volume"].iloc[-1] - df["volume"].iloc[0]
    f["full_load_hours"] = f["energy_kwh_year"] / max(peak, 0.1)

    return f


def features_for_directory(meter_dir: Path,
                            nodes_df: Optional[pd.DataFrame] = None
                            ) -> pd.DataFrame:
    """Compute features for every CSV in `meter_dir`.

    `nodes_df` (Nodes_Edges Nodes sheet) is optional; if supplied, the
    output table joins each Zählernummer to address + Anschlusswert.
    """
    rows = []
    for csv in sorted(Path(meter_dir).glob("*.csv")):
        try:
            zid = int(csv.stem)
        except ValueError:
            continue
        df = _load_meter_csv(csv)
        kw = None
        if nodes_df is not None:
            row = nodes_df[nodes_df["Zählernummer"] == zid]
            if len(row):
                kw = float(row["Anschlusswert"].iloc[0])
        feats = features_for_meter(df, anschluss_kw=kw)
        feats["Zählernummer"] = zid
        if nodes_df is not None and len(row):
            feats["address"] = row["Straße"].iloc[0]
            feats["anschlusswert_kw"] = kw
        rows.append(feats)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    from . import load_data as ld
    nodes = ld.load_logical_nodes()
    feats = features_for_directory(Path("data/raw/synthetic/meters"), nodes)
    print(f"computed features for {len(feats)} HAST")
    print()
    # Quick describe of the most ML-useful columns
    cols = ["rt_mean_winter", "dt_mean_loaded", "dt_std_loaded",
            "summer_flow_baseline", "flow_ceiling_slope_per_month",
            "peak_load_share", "flow_short_cycle_power"]
    print(feats[cols].describe().round(2).to_string())
