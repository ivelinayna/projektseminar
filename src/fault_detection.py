"""
Rule-based fault detection from HAST features.

This is the *baseline*: simple thresholds expressing domain knowledge.
The Excel inspections gave us the fault frequencies; the synth_data
generator embeds those same patterns; this module finds them by rule.

Later iterations will replace these rules with a trained classifier
(probably a tree ensemble) using the inspection records as labels, but
having the rule-based baseline first lets us:

  * validate the feature pipeline (do the features distinguish faults?)
  * benchmark any ML model against (must beat the rules)
  * surface plain-language reasons in the dashboard
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass
class FaultFlag:
    fault: str
    severity: str   # "warn" | "alarm"
    reason: str


def detect_faults(features: pd.Series) -> List[FaultFlag]:
    """Return a list of fault flags raised by the rule book.

    Each rule encodes one of the ÜZ anomaly families plus the fault
    types observed in the optimisation Excel.
    """
    flags: List[FaultFlag] = []
    f = features

    # --- excess return temperature (poor heat transfer secondary side) ---
    if f.get("rt_mean_winter", 0) > 48:
        flags.append(FaultFlag(
            "excess_rt", "alarm",
            f"winter return temperature {f['rt_mean_winter']:.1f} °C "
            f"(target ≤ 45 °C)",
        ))
    elif f.get("rt_above_50_share_loaded", 0) > 0.30:
        flags.append(FaultFlag(
            "excess_rt", "warn",
            f"return > 50 °C in {f['rt_above_50_share_loaded']*100:.0f} % "
            f"of loaded hours",
        ))

    # --- continuous flow / leakage (no shutoff in summer) ----------------
    # Real DHW is bursty; if median flow in summer is > 0 the valve isn't
    # closing properly. Median is robust to genuine DHW draws.
    if f.get("summer_flow_baseline", 0) > 25:
        flags.append(FaultFlag(
            "continuous_flow", "alarm",
            f"summer median flow {f['summer_flow_baseline']:.0f} l/h "
            f"(should be ~0 outside DHW draws)",
        ))
    elif f.get("summer_idle_flow_median", 0) > 15:
        # Even at low load, flow doesn't drop -> probably stuck valve
        flags.append(FaultFlag(
            "continuous_flow", "warn",
            f"flow during low-load summer hours: "
            f"{f['summer_idle_flow_median']:.0f} l/h",
        ))

    # --- filter fouling: flow ceiling drifting downward through the year -
    slope = f.get("flow_ceiling_slope_per_month", 0)
    if slope < -3:
        flags.append(FaultFlag(
            "fouled_filter", "alarm",
            f"95th-percentile flow drops {-slope:.1f} l/h per month "
            f"(filter clogging signature)",
        ))

    # --- low ΔT under load -> fouling or hydraulic issue -----------------
    if f.get("dt_mean_loaded", 30) < 15:
        flags.append(FaultFlag(
            "low_spreading", "warn",
            f"mean ΔT under load only {f['dt_mean_loaded']:.1f} K "
            f"(target > 20 K)",
        ))

    # --- chronic over-spec: peak nowhere near contracted load ------------
    if f.get("peak_load_share", 1.0) < 0.40:
        flags.append(FaultFlag(
            "oversized_contract", "warn",
            f"peak power only {f['peak_load_share']*100:.0f} % of contracted",
        ))

    # --- control hysteresis: short-period flow oscillation ---------------
    if f.get("flow_short_cycle_power", 0) > 0.07:
        flags.append(FaultFlag(
            "control_hysteresis", "alarm",
            f"4–12 h flow oscillation carries "
            f"{f['flow_short_cycle_power']*100:.0f} % of total flow variance",
        ))

    return flags


def classify_one(features: pd.Series) -> str:
    """Pick the single most-likely fault label (or 'healthy')."""
    flags = detect_faults(features)
    if not flags:
        return "healthy"
    # Prefer alarms over warnings; among same severity, first rule wins.
    flags.sort(key=lambda x: 0 if x.severity == "alarm" else 1)
    return flags[0].fault


def classify_dataframe(features_df: pd.DataFrame) -> pd.DataFrame:
    """Apply the rules to every row; return predictions + reasons."""
    out = features_df.copy()
    preds, reasons = [], []
    for _, row in features_df.iterrows():
        flags = detect_faults(row)
        if not flags:
            preds.append("healthy")
            reasons.append("")
            continue
        flags.sort(key=lambda x: 0 if x.severity == "alarm" else 1)
        preds.append(flags[0].fault)
        reasons.append("; ".join(f"[{f.severity}] {f.reason}" for f in flags))
    out["predicted_fault"] = preds
    out["reasons"] = reasons
    return out


def confusion(pred: pd.Series, truth: pd.Series) -> pd.DataFrame:
    """Confusion matrix between predicted and true fault labels."""
    return pd.crosstab(truth.rename("truth"), pred.rename("pred"),
                       margins=True, margins_name="all")


if __name__ == "__main__":
    from pathlib import Path
    from . import load_data as ld
    from .features import features_for_directory

    nodes = ld.load_logical_nodes()
    feats = features_for_directory(Path("data/raw/synthetic/meters"), nodes)
    res = classify_dataframe(feats)

    truth = pd.read_csv("data/raw/synthetic/faults_truth.csv")
    merged = res.merge(truth[["Zählernummer", "fault"]], on="Zählernummer")
    merged = merged.rename(columns={"fault": "true_fault"})

    print("Predicted fault distribution:")
    print(merged["predicted_fault"].value_counts().to_string())
    print()
    print("Confusion (true × predicted):")
    print(confusion(merged["predicted_fault"], merged["true_fault"]).to_string())

    correct = (merged["predicted_fault"] == merged["true_fault"]).sum()
    print(f"\nAccuracy: {correct}/{len(merged)} = {correct/len(merged)*100:.0f} %")
