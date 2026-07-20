"""
Exploratory data profiling of the real ÜZ meter CSV exports.

Read-only data audit before the real time series get wired into the
feature pipeline. Answers, with actual numbers:

  1. inventory: meters, per-meter time range, hourly datapoints, gaps
  2. cumulative counters (Energy kWh, Volume m³): monotonicity,
     long constant stretches, backward jumps
  3. negative Volume-flow / Power readings per meter (% share)
  4. robust distributions (median, p10, p90) of Power, ΔT, Vorlauf,
     Rücklauf - per meter and pooled over all rows
  5. how many meters map to a HAST address in Nodes_Edges.ods

Deliberately makes NO filtering / clipping / exclusion decision - it
only flags conspicuous meters so the team can decide.

Outputs:

  data/processed/timeseries_profile.csv   full per-meter metric table
  docs/datensichtung.md                   generated report (contains
                                          Zählernummern - do not publish)

Usage:

    python -m src.profile_timeseries
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .load_timeseries import DATA_DIR, discover_meter_files, load_meter_timeseries

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORT = ROOT / "docs" / "datensichtung.md"

# Report-only flag thresholds (nothing is filtered based on these)
GAP_HOURS = 1.5            # timestamp step above this counts as a gap
CONST_DAYS_FLAG = 7        # Energy counter flat for >= this many days
NEG_SHARE_FLAG = 0.30      # >= 30 % negative flow or power readings
ZERO_SHARE_FLAG = 0.90     # >= 90 % of hours with power <= 0
SHORT_HISTORY_DAYS = 365   # less than one year of data (features need ~1 y)

COLS = {
    "Energy (kWh)": "energy",
    "Volume flow (l/h)": "flow",
    "Power (kW)": "power",
    "Temperature difference (°C)": "dt",
    "Flow temperature (°C)": "vl",
    "Return temperature (°C)": "rt",
    "Volume (m³)": "volume",
}


def _longest_zero_run_hours(series: pd.Series, step_hours: pd.Series) -> float:
    """Longest consecutive stretch (in hours) where the diff is exactly 0.

    Approximates duration by summing the actual timestamp steps inside
    the run, so data gaps inside a flat stretch are counted as elapsed
    time (a counter that is flat across a gap is still flat).
    """
    d = series.diff()
    flat = d == 0
    if not flat.any():
        return 0.0
    run_id = (~flat).cumsum()
    return float(step_hours.groupby(run_id[flat]).sum().max())


def profile_meter(zid: int, df: pd.DataFrame) -> dict:
    df = df.rename(columns=COLS)
    ts = df["Timestamp"]
    step_h = ts.diff().dt.total_seconds() / 3600.0

    span_h = (ts.iloc[-1] - ts.iloc[0]).total_seconds() / 3600.0
    gaps = step_h[step_h > GAP_HOURS]

    m: dict = {
        "Zählernummer": zid,
        "n_rows": len(df),
        "ts_min": ts.iloc[0],
        "ts_max": ts.iloc[-1],
        "span_days": round(span_h / 24, 1),
        "coverage_pct": round(100 * len(df) / max(span_h + 1, 1), 1),
        "n_gaps": int(len(gaps)),
        "max_gap_days": round(float(gaps.max()) / 24, 2) if len(gaps) else 0.0,
        "missing_hours": round(float((gaps - 1).sum()), 0) if len(gaps) else 0.0,
    }

    # --- cumulative counters ------------------------------------------------
    for col in ("energy", "volume"):
        d = df[col].diff()
        m[f"{col}_monotonic"] = bool((d.dropna() >= 0).all())
        m[f"{col}_n_drops"] = int((d < 0).sum())
        m[f"{col}_max_drop"] = float(d.min()) if (d < 0).any() else 0.0
        m[f"{col}_zero_diff_share"] = round(float((d == 0).mean()), 3)
        m[f"{col}_longest_const_days"] = round(
            _longest_zero_run_hours(df[col], step_h) / 24, 1)

    # --- negative / zero readings -------------------------------------------
    m["flow_neg_pct"] = round(100 * float((df["flow"] < 0).mean()), 1)
    m["power_neg_pct"] = round(100 * float((df["power"] < 0).mean()), 1)
    m["flow_zero_pct"] = round(100 * float((df["flow"] == 0).mean()), 1)
    m["power_le0_pct"] = round(100 * float((df["power"] <= 0).mean()), 1)

    # --- robust distributions -----------------------------------------------
    for col in ("power", "dt", "vl", "rt"):
        v = df[col].astype(float)
        m[f"{col}_p10"] = round(float(v.quantile(0.10)), 2)
        m[f"{col}_median"] = round(float(v.median()), 2)
        m[f"{col}_p90"] = round(float(v.quantile(0.90)), 2)

    return m


def profile_all(data_dir: Path = DATA_DIR
                ) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Profile every meter.

    Returns (per-meter table, pooled row sample, schema issues). Meters
    whose files violate the expected 8-column schema are skipped and
    reported, not silently dropped.
    """
    meters = discover_meter_files(data_dir)
    rows, pooled, schema_issues = [], [], []
    for zid in sorted(meters):
        try:
            df = load_meter_timeseries(zid, data_dir)
        except ValueError as e:
            schema_issues.append(str(e))
            continue
        rows.append(profile_meter(zid, df))
        pooled.append(df[list(COLS)[2:6]].astype("float32"))  # power..rt
    prof = pd.DataFrame(rows)

    # topology match
    try:
        from . import load_data as ld
        known = set(ld.load_logical_nodes()["Zählernummer"].astype(int))
        prof["in_topology"] = prof["Zählernummer"].isin(known)
    except Exception:
        prof["in_topology"] = pd.NA

    return prof, pd.concat(pooled, ignore_index=True), schema_issues


# --- report ------------------------------------------------------------------

def _md_table(df: pd.DataFrame) -> str:
    """Minimal GitHub-markdown table (avoids the tabulate dependency)."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def write_report(prof: pd.DataFrame, pooled: pd.DataFrame,
                 schema_issues: list[str] | None = None,
                 out_path: Path = REPORT) -> Path:
    n = len(prof)
    schema_issues = schema_issues or []
    today = pd.Timestamp.today().date()

    flag_const = prof[prof["energy_longest_const_days"] >= CONST_DAYS_FLAG]
    flag_neg = prof[(prof["flow_neg_pct"] >= NEG_SHARE_FLAG * 100)
                    | (prof["power_neg_pct"] >= NEG_SHARE_FLAG * 100)]
    flag_zero = prof[prof["power_le0_pct"] >= ZERO_SHARE_FLAG * 100]
    flag_short = prof[prof["span_days"] < SHORT_HISTORY_DAYS]
    flag_drops = prof[(prof["energy_n_drops"] > 0) | (prof["volume_n_drops"] > 0)]

    pooled_cols = {"Power (kW)": "Power (kW)",
                   "Temperature difference (°C)": "ΔT (K)",
                   "Flow temperature (°C)": "Vorlauf (°C)",
                   "Return temperature (°C)": "Rücklauf (°C)"}
    pooled_stats = pd.DataFrame({
        "Größe": list(pooled_cols.values()),
        "p10": [round(float(pooled[c].quantile(0.10)), 2) for c in pooled_cols],
        "Median": [round(float(pooled[c].median()), 2) for c in pooled_cols],
        "p90": [round(float(pooled[c].quantile(0.90)), 2) for c in pooled_cols],
    })

    across = pd.DataFrame({
        "Kennzahl je Zähler": ["Median Power (kW)", "Median ΔT (K)",
                               "Median Vorlauf (°C)", "Median Rücklauf (°C)",
                               "Zeitspanne (Tage)", "Abdeckung (%)",
                               "Anteil Fluss < 0 (%)", "Anteil Power ≤ 0 (%)"],
        "p10": [prof[c].quantile(0.10).round(2) for c in
                ("power_median", "dt_median", "vl_median", "rt_median",
                 "span_days", "coverage_pct", "flow_neg_pct", "power_le0_pct")],
        "Median": [prof[c].median().round(2) for c in
                   ("power_median", "dt_median", "vl_median", "rt_median",
                    "span_days", "coverage_pct", "flow_neg_pct", "power_le0_pct")],
        "p90": [prof[c].quantile(0.90).round(2) for c in
                ("power_median", "dt_median", "vl_median", "rt_median",
                 "span_days", "coverage_pct", "flow_neg_pct", "power_le0_pct")],
    })

    def zlist(sub: pd.DataFrame, cols: list[str]) -> str:
        if sub.empty:
            return "_keine_\n"
        sub = sub[["Zählernummer"] + cols].copy()
        sub["Zählernummer"] = sub["Zählernummer"].astype(int)
        for c in cols:  # ints that became float via DataFrame casting
            if sub[c].dtype.kind == "f" and (sub[c] % 1 == 0).all():
                sub[c] = sub[c].astype(int)
        return _md_table(sub.sort_values(cols[-1], ascending=False)) + "\n"

    n_topo = int(prof["in_topology"].sum())
    n_mono_e = int(prof["energy_monotonic"].sum())
    n_mono_v = int(prof["volume_monotonic"].sum())

    lines = f"""# Datensichtung: echte Zähler-Zeitreihen

Generiert am {today} von `src/profile_timeseries.py` (read-only, keine
Filterung). Datenbasis: CSV-Exporte in `data/raw/`, eingelesen über
`src.load_timeseries` (Export-Generationen gemergt, Duplikate entfernt).

> **Datenschutz:** Dieser Report enthält Zählernummern. Nicht in
> öffentliche Artefakte, Review-ZIPs oder Präsentationen übernehmen.
> Die vollständige Metrik-Tabelle liegt (gitignored) unter
> `data/processed/timeseries_profile.csv`.

## 0. Schema-Abweichungen

{len(schema_issues)} Zähler konnten nicht profiliert werden, weil
mindestens eine Exportdatei vom 8-Spalten-Schema abweicht:

{chr(10).join('- `' + s + '`' for s in schema_issues) if schema_issues else '_keine_'}

Diese Zähler fehlen in allen folgenden Zahlen.

## 1. Inventar und Abdeckung

- **{n} Zähler** profiliert, gesamt {prof['n_rows'].sum():,} Datenpunkte.
- Gesamtzeitraum: {prof['ts_min'].min()} bis {prof['ts_max'].max()}.
- Historie je Zähler: Median {prof['span_days'].median():.0f} Tage,
  Minimum {prof['span_days'].min():.0f}, Maximum {prof['span_days'].max():.0f} Tage.
- **{len(flag_short)} Zähler haben weniger als {SHORT_HISTORY_DAYS} Tage
  Historie** (Feature-Berechnung erwartet ~1 Jahr).
- Abdeckung (Datenpunkte / erwartete Stunden im Zeitraum): Median
  {prof['coverage_pct'].median():.1f} %, Minimum {prof['coverage_pct'].min():.1f} %.
- Lücken (> {GAP_HOURS} h zwischen Punkten): Median {prof['n_gaps'].median():.0f}
  Lücken je Zähler, größte Einzellücke im Bestand
  {prof['max_gap_days'].max():.1f} Tage.

### Zähler mit kurzer Historie (< {SHORT_HISTORY_DAYS} Tage)

{zlist(flag_short, ['ts_min', 'ts_max', 'span_days'])}

## 2. Kumulative Zähler (Energy kWh, Volume m³)

- Energy monoton steigend: **{n_mono_e} von {n}** Zählern
  ({n - n_mono_e} mit Rücksprüngen).
- Volume monoton steigend: **{n_mono_v} von {n}** Zählern.
- **{len(flag_const)} Zähler** haben Phasen von ≥ {CONST_DAYS_FLAG} Tagen
  mit komplett konstantem Energy-Zählerstand. Hinweis zur Interpretation:
  Im Sommer kann ein konstanter Zähler legitim sein (kein Verbrauch);
  konstante Phasen über Wochen oder im Winter deuten eher auf
  eingefrorene Werte im Export hin.

### Zähler mit Rücksprüngen im kumulativen Zähler

{zlist(flag_drops, ['energy_n_drops', 'energy_max_drop', 'volume_n_drops'])}

### Zähler mit ≥ {CONST_DAYS_FLAG} Tagen konstantem Energy-Stand (Top nach Dauer)

{zlist(flag_const.nlargest(15, 'energy_longest_const_days'), ['energy_longest_const_days', 'energy_zero_diff_share', 'span_days'])}

## 3. Negative Messwerte

- Anteil Stunden mit Volume flow < 0: Median {prof['flow_neg_pct'].median():.1f} %,
  p90 {prof['flow_neg_pct'].quantile(0.9):.1f} %, Maximum {prof['flow_neg_pct'].max():.1f} %.
- Anteil Stunden mit Power < 0: Median {prof['power_neg_pct'].median():.1f} %,
  p90 {prof['power_neg_pct'].quantile(0.9):.1f} %, Maximum {prof['power_neg_pct'].max():.1f} %.
- **{len(flag_neg)} Zähler** liegen über der Auffälligkeitsschwelle
  ({NEG_SHARE_FLAG:.0%} negative Fluss- oder Leistungswerte).
- **{len(flag_zero)} Zähler** haben ≥ {ZERO_SHARE_FLAG:.0%} Stunden mit
  Power ≤ 0 (fast nur Null-/Negativwerte).

### Zähler mit hohem Negativanteil

{zlist(flag_neg, ['flow_neg_pct', 'power_neg_pct'])}

### Zähler mit ≥ {ZERO_SHARE_FLAG:.0%} Power ≤ 0

{zlist(flag_zero, ['power_le0_pct', 'flow_zero_pct', 'power_median'])}

## 4. Robuste Verteilungen der Kerngrößen

### Gepoolt über alle {len(pooled):,} Stundenwerte

{_md_table(pooled_stats)}

### Streuung der Je-Zähler-Kennzahlen (p10 / Median / p90 über {n} Zähler)

{_md_table(across)}

Die vollständige Tabelle pro Zähler (alle Metriken dieses Reports)
liegt unter `data/processed/timeseries_profile.csv`.

## 5. Zuordnung zur logischen Topologie

- **{n_topo} von {n} Zählern** stehen mit ihrer Zählernummer in
  `Nodes_Edges.ods` (Sheet `Nodes`).
- {n - n_topo} Zähler fehlen dort - mutmaßlich Zählertausch; Kandidat
  für die Auflösung ist `Zuordnung.xlsx` (siehe
  [naechste-schritte.md](naechste-schritte.md)).

### CSV-Zähler ohne Topologie-Eintrag

{zlist(prof[~prof['in_topology'].astype(bool)], ['ts_min', 'ts_max', 'span_days'])}

## 6. Offene Fragen für die nächste Etappe

Keine Entscheidung getroffen - zu klären im Team / mit ÜZ:

1. Wie behandeln wir Zähler mit lang konstanten Zählerständen -
   Exportfehler bei ÜZ nachfragen oder betroffene Zeiträume maskieren?
2. Negative Flüsse/Leistungen: Messrauschen um Null (clippen?) oder
   systematisch (Zähler ausschließen)? Die Verteilung oben trennt
   beide Fälle.
3. Analysefenster: letztes volles Jahr je Zähler vs. fixes
   Kalenderjahr - {len(flag_short)} Zähler unterschreiten ein Jahr.
4. Zählertausch-Stitching über `Zuordnung.xlsx` für die
   {n - n_topo} Zähler ohne Topologie-Eintrag.
"""
    out_path.write_text(lines, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, default=REPORT)
    args = p.parse_args()

    print("→ profiling real meter CSVs (read-only)")
    prof, pooled, schema_issues = profile_all()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    prof.to_csv(PROCESSED / "timeseries_profile.csv", index=False)
    print(f"  → {PROCESSED / 'timeseries_profile.csv'} ({len(prof)} meters)")
    for s in schema_issues:
        print(f"  ! schema issue: {s}")

    out = write_report(prof, pooled, schema_issues, args.report)
    print(f"  → {out}")

    print(f"\nmeters: {len(prof)} | rows: {prof['n_rows'].sum():,} "
          f"| range: {prof['ts_min'].min()} .. {prof['ts_max'].max()}")
    print(f"energy monotonic: {int(prof['energy_monotonic'].sum())}/{len(prof)} "
          f"| const >= {CONST_DAYS_FLAG}d: "
          f"{int((prof['energy_longest_const_days'] >= CONST_DAYS_FLAG).sum())}")
    print(f"flow neg pct: median {prof['flow_neg_pct'].median():.1f} "
          f"max {prof['flow_neg_pct'].max():.1f}")
    print(f"in topology: {int(prof['in_topology'].sum())}/{len(prof)}")
