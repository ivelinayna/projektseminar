"""Loader for the ÜZ walkthrough records and the address -> meter directory.

Two source files, both in ``data/raw``:

* ``Zuordnung.xlsx`` - the authoritative address -> meter mapping, one sheet
  per year. This is the *only* complete directory we have. ``Nodes_Edges.ods``
  (used by ``load_data.load_logical_nodes``) is missing 16 of the addresses
  that appear in the walkthrough records, so joins built on it silently lose
  a quarter of the data.
* ``20252810_Ergebnis_Optimierung_FW(45).xlsx`` - the walkthrough records.
  133 columns behind a two-row header. ``inspections.py`` extracts a tidy
  subset of 21; this module keeps the columns that describe *what was
  changed*: the graded change category, the visit times, heating and DHW
  schedules before/after, and the setpoints before/after.

Why both live here and not in a notebook: resolving an address to its meter
number is data access, not analysis, and every downstream evaluation needs
the same answer.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .load_data import DATA_DIR, _normalize_address

ZUORDNUNG_XLSX = DATA_DIR / "Zuordnung.xlsx"
BEGEHUNGEN_XLSX = DATA_DIR / "20252810_Ergebnis_Optimierung_FW(45).xlsx"

#: Typos found in the walkthrough sheet that block the address join.
#: "Fleiderstraße" for "Fliederstraße" costs four meters on its own.
ADDRESS_TYPOS = {
    "fleiderstrasse": "fliederstrasse",
}


def _fix_typos(key: str) -> str:
    for wrong, right in ADDRESS_TYPOS.items():
        key = key.replace(wrong, right)
    return key


def _key(value: object) -> str:
    """Normalised join key: the '-str.' / '-straße' spellings collapse to one form."""
    return _fix_typos(_normalize_address(value))


# --------------------------------------------------------------------------
# Zuordnung.xlsx - address -> meter
# --------------------------------------------------------------------------

def load_zuordnung(path: Path = ZUORDNUNG_XLSX) -> pd.DataFrame:
    """Return every (address, meter, year) triple in the directory.

    The 2024 and 2025 sheets carry a combined ``Abnahmestelle`` column; the
    2026 sheet splits street and house number. Both shapes are normalised to
    the same join key.
    """
    parts: List[pd.DataFrame] = []
    sheets = pd.ExcelFile(path).sheet_names

    for sheet in sheets:
        df = pd.read_excel(path, sheet_name=sheet, header=0)
        cols = list(df.columns)
        meter = df[cols[0]]
        if len(cols) > 3 and "Hausnr" in str(cols[2]):
            address = (df[cols[1]].astype(str).str.strip() + " "
                       + df[cols[2]].astype(str).str.strip())
        else:
            address = df[cols[2]]
        parts.append(pd.DataFrame({"meter": meter, "address": address, "year": sheet}))

    out = pd.concat(parts, ignore_index=True)
    out["meter"] = pd.to_numeric(out["meter"], errors="coerce")
    out = out.dropna(subset=["meter", "address"])
    out["meter"] = out["meter"].astype("int64")
    out["key"] = out["address"].map(_key)
    return out[out["key"].str.len() > 3].reset_index(drop=True)


def meter_changes(zuordnung: Optional[pd.DataFrame] = None) -> Dict[str, List[int]]:
    """Addresses served by more than one meter number over the years.

    A before/after comparison that straddles such a change compares two
    devices, not two states of one station - always check against this.
    """
    z = load_zuordnung() if zuordnung is None else zuordnung
    per_address = z.groupby("key")["meter"].apply(lambda s: sorted(set(s)))
    return {k: v for k, v in per_address.items() if len(v) > 1}


def address_to_meter(
    available: Optional[set] = None,
    zuordnung: Optional[pd.DataFrame] = None,
) -> Dict[str, int]:
    """Map join key -> meter number, one meter per address.

    Pass ``available`` (the meter ids we actually hold time series for) to
    prefer a meter with data whenever an address has several. Without it the
    lowest meter id wins, which may well be one that was swapped out.
    """
    z = load_zuordnung() if zuordnung is None else zuordnung
    picked: Dict[str, int] = {}
    for key, group in z.groupby("key"):
        candidates = sorted(set(group["meter"]))
        with_data = [m for m in candidates if available and m in available]
        picked[key] = with_data[0] if with_data else candidates[0]
    return picked


# --------------------------------------------------------------------------
# Ergebnis_Optimierung - the walkthrough records
# --------------------------------------------------------------------------

#: Columns recovered from the wide sheet. ``inspections.py`` keeps none of
#: these except the free text, yet they are what says *what was changed*.
_WANTED = {
    "nr": "Nr.",
    "datum": "Datum",
    "strasse": "Straßenname",
    "hausnr": "Hausnummer",
    "kategorie": "Kategorie",
    "sonstiges": "Sonstiges",
    "heizzeit_alt_von": "Heizzeiten RW alt|von",
    "heizzeit_alt_bis": "Heizzeiten RW alt|bis",
    "heizzeit_neu_von": "Heizzeiten RW neu|von",
    "heizzeit_neu_bis": "Heizzeiten RW neu|bis",
    "tww_alt_von": "TWW-Bereitung alt|von",
    "tww_alt_bis": "TWW-Bereitung alt|bis",
    "tww_neu_von": "TWW-Bereitung neu|von",
    "tww_neu_bis": "TWW-Bereitung neu|bis",
}

#: Setpoint columns come in adjacent alt/neu pairs under one heading.
_SETPOINT_PAIRS = {
    "rw_soll_tag": "RW Soll Tag",
    "rw_soll_nacht": "RW Soll Nacht",
    "tww_soll": "TWW Soll",
}


def load_begehungen(path: Path = BEGEHUNGEN_XLSX) -> pd.DataFrame:
    """Return one row per walkthrough with the change-describing columns.

    The sheet has a two-row header: row 0 carries the group heading (merged
    across its columns, hence the forward fill), row 1 the sub-label
    ('von'/'bis', 'alt'/'neu'). Labels repeat, so columns are addressed by
    position rather than by name.
    """
    raw = pd.read_excel(path, sheet_name="Tabelle1", header=None)
    heading = raw.iloc[0].ffill()
    sub = raw.iloc[1]
    labels = [f"{a}|{b}" if pd.notna(b) else str(a) for a, b in zip(heading, sub)]
    body = raw.iloc[3:].reset_index(drop=True)

    def position(pattern: str) -> int:
        for i, label in enumerate(labels):
            if pattern in str(label):
                return i
        raise KeyError(f"column {pattern!r} not found in {path.name}")

    data = {name: body.iloc[:, position(pat)].values for name, pat in _WANTED.items()}

    # "Dauer (Uhrzeit)" spans two unlabelled columns: start and end of the visit.
    duration = [i for i, label in enumerate(labels) if "Dauer" in str(label)]
    data["von"] = body.iloc[:, duration[0]].values
    data["bis"] = body.iloc[:, duration[1]].values

    # Setpoints: the heading sits on the 'alt' column, 'neu' is the next one.
    for name, pattern in _SETPOINT_PAIRS.items():
        i = position(pattern)
        data[f"{name}_alt"] = body.iloc[:, i].values
        data[f"{name}_neu"] = body.iloc[:, i + 1].values

    out = pd.DataFrame(data)
    out = out[out["strasse"].notna()].copy()
    out["datum"] = pd.to_datetime(out["datum"], errors="coerce")
    out["key"] = (out["strasse"].astype(str).str.strip() + " "
                  + out["hausnr"].astype(str).str.strip()).map(_key)
    out["heizzeit_geaendert"] = (
        out["heizzeit_alt_von"].notna() & out["heizzeit_neu_von"].notna()
        & ((out["heizzeit_alt_von"].astype(str) != out["heizzeit_neu_von"].astype(str))
           | (out["heizzeit_alt_bis"].astype(str) != out["heizzeit_neu_bis"].astype(str)))
    )
    return out.reset_index(drop=True)


def begehungen_mit_zaehler(available: Optional[set] = None) -> pd.DataFrame:
    """Walkthroughs joined to their meter number.

    ``available`` is passed straight through to :func:`address_to_meter`;
    supply the meter ids you hold time series for so addresses with a meter
    swap resolve to one you can actually evaluate.
    """
    beg = load_begehungen()
    zuordnung = load_zuordnung()
    lookup = address_to_meter(available=available, zuordnung=zuordnung)
    changed = meter_changes(zuordnung)

    beg["meter"] = beg["key"].map(lookup)
    beg["meter_gewechselt"] = beg["key"].isin(changed)
    return beg


def visit_hours(row: pd.Series) -> Optional[tuple]:
    """(start_hour, end_hour) of the visit, or None when no time was recorded."""
    def hour(value: object) -> Optional[int]:
        match = re.search(r"(\d{1,2}):(\d{2})", str(value))
        return int(match.group(1)) if match else None

    start = hour(row.get("von"))
    if start is None:
        return None
    return start, (hour(row.get("bis")) or start)


if __name__ == "__main__":
    z = load_zuordnung()
    beg = begehungen_mit_zaehler()
    print(f"Zuordnung : {len(z)} Eintraege, {z['key'].nunique()} Adressen, "
          f"{z['meter'].nunique()} Zaehler")
    print(f"Begehungen: {len(beg)}, davon {beg['meter'].notna().sum()} mit Zaehlernummer, "
          f"{beg['datum'].notna().sum()} mit Datum, {beg['von'].notna().sum()} mit Uhrzeit")
    print(f"Kategorien: {beg['kategorie'].value_counts().to_dict()}")
    print(f"Heizzeit geaendert bei {int(beg['heizzeit_geaendert'].sum())} Stationen")
    print(f"Adressen mit Zaehlerwechsel: {meter_changes(z)}")
