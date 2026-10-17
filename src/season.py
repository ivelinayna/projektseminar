"""
Saisonsegmente für die HAST-Analyse.

Hintergrund: Im Sommer ist der Wärmebedarf so niedrig, dass Rücklauf-
und Spreizungsfeatures vor allem Rauschen zeigen. Ausgewertet wird
deshalb getrennt nach Segmenten.

Vier Segmente am Stundenraster:

    kernwinter        Dez, Jan, Feb
    uebergang_spaet   Mär, Apr
    sommer            Mai bis Aug
    uebergang_frueh   Sep, Okt (und vorläufig Nov)

- `add_season_segment` hängt das Segment als Spalte an und filtert nichts
- November ist nicht festgelegt: Standard ist `uebergang_frueh`, über
  `month_map` änderbar
- `coldest_february_weeks` bestimmt die zwei kältesten Februarwochen aus
  der Außentemperatur
"""

from __future__ import annotations

from typing import Mapping, Optional

import numpy as np
import pandas as pd

KERNWINTER = "kernwinter"
UEBERGANG_SPAET = "uebergang_spaet"
SOMMER = "sommer"
UEBERGANG_FRUEH = "uebergang_frueh"

SEGMENT_ORDER = [KERNWINTER, UEBERGANG_SPAET, SOMMER, UEBERGANG_FRUEH]

SEASON_MONTHS: Mapping[int, str] = {
    12: KERNWINTER, 1: KERNWINTER, 2: KERNWINTER,
    3: UEBERGANG_SPAET, 4: UEBERGANG_SPAET,
    5: SOMMER, 6: SOMMER, 7: SOMMER, 8: SOMMER,
    9: UEBERGANG_FRUEH, 10: UEBERGANG_FRUEH,
    #November ist in der Meeting-Vorgabe offen, siehe Modul-Docstring
    11: UEBERGANG_FRUEH,
}


def season_of_month(month: int,
                    month_map: Optional[Mapping[int, str]] = None) -> str:
    """Segmentname für einen Kalendermonat (1-12)."""
    mapping = SEASON_MONTHS if month_map is None else month_map
    try:
        return mapping[int(month)]
    except KeyError:
        raise ValueError(f"kein Saisonsegment für Monat {month}") from None


def add_season_segment(df: pd.DataFrame,
                       timestamp_col: Optional[str] = None,
                       month_map: Optional[Mapping[int, str]] = None,
                       column: str = "season") -> pd.DataFrame:
    """Kopie von `df` mit Saisonsegment als kategorialer Spalte.

    Die Zeitbasis kommt aus `timestamp_col`; ohne Angabe wird ein
    DatetimeIndex erwartet. Es wird nichts gefiltert - Sommerstunden
    bleiben in der Tabelle und sind nur als `sommer` markiert.
    """
    out = df.copy()
    if timestamp_col is None:
        idx = pd.DatetimeIndex(out.index)
    else:
        if timestamp_col not in out.columns:
            raise KeyError(
                f"Spalte '{timestamp_col}' fehlt - vorhanden: {list(out.columns)}")
        idx = pd.DatetimeIndex(out[timestamp_col])

    mapping = SEASON_MONTHS if month_map is None else month_map
    labels = [season_of_month(m, mapping) for m in idx.month]
    categories = [c for c in SEGMENT_ORDER if c in set(mapping.values())]
    categories += [c for c in dict.fromkeys(mapping.values())
                   if c not in categories]
    out[column] = pd.Categorical(labels, categories=categories, ordered=False)
    return out


def coldest_february_weeks(temp: pd.DataFrame,
                           n_days: int = 14,
                           timestamp_col: str = "timestamp",
                           column: str = "t_out",
                           min_coverage: float = 0.8) -> pd.DataFrame:
    """Kälteste zusammenhängende `n_days`-Periode im Februar, je Jahr.

    Die Periode wird datengetrieben über das gleitende Mittel der
    Außentemperatur bestimmt, nicht auf feste Kalenderwochen gesetzt.
    Das Fenster liegt vollständig innerhalb des Februars, kann also in
    einem Nicht-Schaltjahr auf 15 Startpositionen fallen.

    Rückgabe (eine Zeile je Jahr, aufsteigend):

        year, start, end, t_out_mean, n_hours, coverage

    `n_hours` zählt die tatsächlich vorhandenen Messwerte im Fenster,
    `coverage` deren Anteil an den Kalenderstunden. Jahre, deren bestes
    Fenster unter `min_coverage` liegt, erscheinen mit NaN in
    `t_out_mean` statt zu verschwinden - eine Messlücke soll sichtbar
    bleiben und nicht als kalte Phase durchgehen.
    """
    if n_days <= 0:
        raise ValueError("n_days muss positiv sein")
    if timestamp_col not in temp.columns:
        raise KeyError(
            f"Spalte '{timestamp_col}' fehlt - vorhanden: {list(temp.columns)}")
    if column not in temp.columns:
        raise KeyError(
            f"Spalte '{column}' fehlt - vorhanden: {list(temp.columns)}")

    s = pd.Series(pd.to_numeric(temp[column], errors="coerce").to_numpy(),
                  index=pd.DatetimeIndex(temp[timestamp_col])).sort_index()
    window = n_days * 24

    rows = []
    for year in sorted({int(y) for y in s.index.year}):
        feb_start = pd.Timestamp(year=year, month=2, day=1)
        feb_end_excl = pd.Timestamp(year=year, month=3, day=1)
        grid = pd.date_range(feb_start, feb_end_excl - pd.Timedelta(hours=1),
                             freq="h")
        feb = s[(s.index >= feb_start) & (s.index < feb_end_excl)]
        feb = feb[~feb.index.duplicated(keep="first")].reindex(grid)
        if len(grid) < window:
            continue

        counts = feb.notna().rolling(window).sum()
        means = feb.rolling(window, min_periods=1).mean()

        #nur ausreichend belegte Fenster duerfen das Minimum stellen, sonst
        #gewinnt ein Fenster aus einer einzelnen kalten Stunde
        eligible = counts >= min_coverage * window
        if eligible.any():
            end = means[eligible].idxmin()
        elif (counts > 0).any():
            end = counts.idxmax()
        else:
            continue
        start = end - pd.Timedelta(hours=window - 1)
        n_hours = int(counts.loc[end])
        coverage = n_hours / window
        mean = float(means.loc[end]) if coverage >= min_coverage else np.nan
        rows.append({
            "year": year,
            "start": start,
            "end": end,
            "t_out_mean": mean,
            "n_hours": n_hours,
            "coverage": coverage,
        })

    return pd.DataFrame(rows, columns=["year", "start", "end", "t_out_mean",
                                       "n_hours", "coverage"])
