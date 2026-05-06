"""
Quick analysis of HAST inspection findings.

The optimisation Excel ('Ergebnis_Optimierung_FW_45') contains 67 on-site
inspection records. Each row notes what was found wrong and what was fixed
(filter cleaned, valve replaced, control parameters changed, etc.). This
gives us a *labelled* corpus of real-world fault types - perfect for fault
detection and predictive maintenance modelling later.

This module produces a flat, analysis-friendly DataFrame and a simple
fault-frequency summary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from . import load_data as ld


# Maintenance-action columns in the wide inspection sheet (in original order).
# These are yes/no flags for what the technician did.
MAINTENANCE_FLAGS = [
    "Filter  gereinigt",
    "Vertragsleistung alt",
    "Vertragsleistung neu",
    "Durchfluss neu  eingestellt",
    "Leitungen  neu gedämmt ",
    "Stellmotor  getauscht",
    "Stellventil  getauscht",
    "Regler  getauscht",
    "Sonstiges",
]


def tidy_inspections(raw: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Return a tidy view of the inspection sheet.

    Output columns:
      address_norm, datum, anlagen_konfig, vertrag_alt_kw, vertrag_neu_kw,
      filter_gereinigt, durchfluss_neu, daemmung_neu, stellmotor_getauscht,
      stellventil_getauscht, regler_getauscht, vertrag_changed,
      sonstiges, n_actions
    """
    if raw is None:
        raw = ld.load_inspections()

    df = pd.DataFrame()
    df["address_norm"] = raw["address_norm"]
    df["datum"]        = raw.iloc[:, 1]
    df["strasse"]      = raw.iloc[:, 2]
    df["hausnummer"]   = raw.iloc[:, 3]
    df["anlagen_konfig"] = raw.iloc[:, 6]   # 'Anlagen-konfiguration'
    df["station_typ"]    = raw.iloc[:, 7]
    df["zusatzheizung"]  = raw.iloc[:, 8]
    df["personen"]       = raw.iloc[:, 9]
    df["wohnflaeche"]    = raw.iloc[:, 10]
    df["bj"]             = raw.iloc[:, 11]

    # yes/no findings (column names contain newlines from the multi-row header)
    df["filter_gereinigt"]      = _yn(raw["Filter\ngereinigt"])
    df["durchfluss_neu"]        = _yn(raw["Durchfluss neu\neingestellt"])
    df["daemmung_neu"]          = _yn(raw["Leitungen\nneu gedämmt"])
    df["stellmotor_getauscht"]  = _yn(raw["Stellmotor\ngetauscht"])
    df["stellventil_getauscht"] = _yn(raw["Stellventil\ngetauscht"])
    df["regler_getauscht"]      = _yn(raw["Regler\ngetauscht"])

    df["vertrag_alt_kw"] = pd.to_numeric(raw["Vertragsleistung alt"], errors="coerce")
    df["vertrag_neu_kw"] = pd.to_numeric(raw["Vertragsleistung neu"], errors="coerce")
    df["vertrag_changed"] = (
        df["vertrag_alt_kw"].notna()
        & df["vertrag_neu_kw"].notna()
        & (df["vertrag_alt_kw"] != df["vertrag_neu_kw"])
    )

    # 'Sonstiges' appears twice (column + comment); take both
    sonst_cols = [c for c in raw.columns if c == "Sonstiges"]
    df["sonstiges"] = (raw[sonst_cols].astype(str)
                       .apply(lambda r: " | ".join(str(x) for x in r
                                                   if str(x) not in ("nan", "")),
                              axis=1))

    action_cols = [
        "filter_gereinigt", "durchfluss_neu", "daemmung_neu",
        "stellmotor_getauscht", "stellventil_getauscht", "regler_getauscht",
    ]
    df["n_actions"] = df[action_cols].sum(axis=1) + df["vertrag_changed"].astype(int)
    return df


def fault_summary(tidy: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Aggregate fault / action counts across inspections."""
    if tidy is None:
        tidy = tidy_inspections()
    cols = [
        "filter_gereinigt", "durchfluss_neu", "daemmung_neu",
        "stellmotor_getauscht", "stellventil_getauscht", "regler_getauscht",
        "vertrag_changed",
    ]
    counts = tidy[cols].sum().sort_values(ascending=False)
    out = pd.DataFrame({
        "fault_indicator": counts.index,
        "n_haust": counts.values.astype(int),
        "share_pct": (counts.values / len(tidy) * 100).round(1),
    })
    return out


# --- helpers --------------------------------------------------------------

def _yn(s: pd.Series) -> pd.Series:
    """Map German yes/no/cleaning column to bool. NaN/empty -> False."""
    return (
        s.astype(str)
        .str.strip()
        .str.lower()
        .isin({"ja", "yes", "x", "1", "true"})
    )


if __name__ == "__main__":
    tidy = tidy_inspections()
    print(f"Tidy inspections: {len(tidy)} rows")
    print()
    print(fault_summary(tidy).to_string(index=False))
    print()
    print(f"Mean actions per inspection: {tidy['n_actions'].mean():.2f}")
    print(f"Inspections with >=3 actions: "
          f"{(tidy['n_actions']>=3).sum()} of {len(tidy)}")
