"""
Windowed features for HAST time series.

Instead of collapsing a whole meter history into one profile
(src.features.features_for_meter), this module cuts the hourly series
into calendar windows (default 14 days, the Zustandsfenster from
notebook 02) and computes the same feature set per window. The result
is a long table - one row per window - that feeds the clustering
benchmark and the inspection impact analysis (cluster migration over
time).

Quality is flagged, not filtered (team policy: do not drop too much):

    low_coverage   window coverage below min_coverage
    meter_change   window contains a documented meter change - it
                   compares two devices and is fachlich problematisch

energy_kwh_year / volume_m3_year / full_load_hours are normalised to
8760 h/year inside features_for_meter using the actual calendar span
of each window slice (first to last timestamp, gaps keep their true
length) - never by n_hours and never by the full history.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Union

import numpy as np
import pandas as pd

from .features import features_for_meter

# Window metadata columns, kept first in the output table.
META_COLUMNS = [
    "window_start",
    "window_end",
    "n_hours",
    "coverage",
    "low_coverage",
    "meter_change",
]


def features_for_window(df: pd.DataFrame,
                        anschluss_kw: Optional[float] = None,
                        window_start: Optional[pd.Timestamp] = None,
                        window_end: Optional[pd.Timestamp] = None
                        ) -> dict:
    """Compute features_for_meter() on an arbitrary slice plus metadata.

    `window_start`/`window_end` are the calendar bounds of the window
    (inclusive, hourly grid); they default to the first/last timestamp
    of `df`. `coverage` is n_hours over the calendar hours spanned by
    the window, so internal gaps count as missing.
    """
    if len(df) == 0:
        raise ValueError("features_for_window() needs at least one row")

    # features_for_meter() needs month/hour helpers; derive them from the
    # index so any raw slice of the loader output works.
    if "month" not in df.columns or "hour" not in df.columns:
        df = df.copy()
        if "month" not in df.columns:
            df["month"] = df.index.month
        if "hour" not in df.columns:
            df["hour"] = df.index.hour

    f = features_for_meter(df, anschluss_kw=anschluss_kw)

    start = df.index[0] if window_start is None else pd.Timestamp(window_start)
    end = df.index[-1] if window_end is None else pd.Timestamp(window_end)
    calendar_hours = (end - start).total_seconds() / 3600 + 1
    f["window_start"] = start
    f["window_end"] = end
    f["n_hours"] = int(len(df))
    f["coverage"] = len(df) / calendar_hours if calendar_hours > 0 else np.nan
    return f


def windowed_features_for_meter(df: pd.DataFrame,
                                window_days: int = 14,
                                step_days: Optional[int] = None,
                                min_coverage: float = 0.5,
                                meter_changes: Optional[Sequence[Union[pd.Timestamp, str]]] = None,
                                anschluss_kw: Optional[float] = None
                                ) -> pd.DataFrame:
    """Cut one hourly meter series into windows, compute features per window.

    Windows are aligned to calendar midnights starting at the day of the
    first timestamp and cover [start, start + window_days) each; with
    step_days=None they do not overlap. Nothing is dropped: windows
    below min_coverage get low_coverage=True, windows containing a
    meter change timestamp get meter_change=True, and windows without
    any rows appear as metadata-only entries (features NaN) so a gap
    shows up in the output instead of a silent dropout.

    Expects the schema of features_for_meter() (columns energy, flow,
    power, dt, vl, rt, volume on an hourly DatetimeIndex); month/hour
    helper columns are added here if missing.
    """
    if step_days is None:
        step_days = window_days
    if window_days <= 0 or step_days <= 0:
        raise ValueError("window_days and step_days must be positive")

    df = df.sort_index()
    if "month" not in df.columns:
        df["month"] = df.index.month
    if "hour" not in df.columns:
        df["hour"] = df.index.hour

    changes: List[pd.Timestamp] = [pd.Timestamp(t) for t in (meter_changes or [])]

    rows = []
    if len(df) > 0:
        window_len = pd.Timedelta(days=window_days)
        step = pd.Timedelta(days=step_days)
        last = df.index[-1]

        wstart = df.index[0].normalize()
        while wstart <= last:
            wend_excl = wstart + window_len
            window_end = wend_excl - pd.Timedelta(hours=1)
            window_df = df[(df.index >= wstart) & (df.index < wend_excl)]
            if len(window_df) == 0:
                row = {
                    "window_start": wstart,
                    "window_end": window_end,
                    "n_hours": 0,
                    "coverage": 0.0,
                }
            else:
                row = features_for_window(window_df,
                                          anschluss_kw=anschluss_kw,
                                          window_start=wstart,
                                          window_end=window_end)
            row["low_coverage"] = bool(
                np.isnan(row["coverage"]) or row["coverage"] < min_coverage
            )
            row["meter_change"] = any(wstart <= c < wend_excl for c in changes)
            rows.append(row)
            wstart += step

    out = pd.DataFrame(rows)
    if len(out) == 0:
        return out
    cols = META_COLUMNS + [c for c in out.columns if c not in META_COLUMNS]
    return out[cols]
