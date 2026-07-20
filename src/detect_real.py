"""
Run the existing feature + rule-based detection pipeline on the REAL
meter time series - defensively, based on the quality classification.

Selection funnel (nothing is deleted, only selected):

    all meters with CSV exports
      -> quality_class == "auswertbar"        (src/meter_quality.py)
      -> zugeordnet == True                   (Zählernummer in Nodes_Edges.ods)

Per selected meter the analysis window (most recent WINDOW_DAYS, see
meter_quality) is materialised as data/processed/real_meters_window/
<Zählernummer>.csv - the exact layout `features.features_for_directory`
already consumes, so features.py / fault_detection.py run unchanged.

Ground truth: the on-site inspection records, joined via
Zählernummer -> address_norm. Evaluation is primarily BINARY
(predicted any fault vs. inspection recorded any measure), because the
mapping from predicted fault types to maintenance measures is an
ASSUMPTION (see FAULT_TO_MEASURE below) that the team still has to
confirm. Meters without an inspection record have UNKNOWN truth - they
are never counted as "healthy confirmed".

Outputs:

    data/processed/real_meters_window/*.csv
    data/processed/features_real.csv
    data/processed/predictions_real.csv
    docs/echte-daten-integration.md          (generated report)

Usage:

    python -m src.detect_real
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from . import load_data as ld
from .fault_detection import classify_dataframe
from .features import features_for_directory
from .inspections import tidy_inspections
from .load_timeseries import DATA_DIR, load_meter_timeseries
from .meter_quality import (MIN_WINDOW_COVERAGE_PCT, WINDOW_DAYS,
                            classify_all)
from .profile_timeseries import _md_table

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
WINDOW_DIR = PROCESSED / "real_meters_window"
REPORT = ROOT / "docs" / "echte-daten-integration.md"

# ASSUMPTION (to be confirmed with the team / ÜZ technicians): which
# inspection measure would plausibly follow from each predicted fault.
# Used only for the secondary per-fault evaluation, never for selection.
FAULT_TO_MEASURE = {
    "fouled_filter": ["filter_gereinigt"],
    "continuous_flow": ["durchfluss_neu"],
    "excess_rt": ["durchfluss_neu"],
    "low_spreading": ["durchfluss_neu"],
    "oversized_contract": ["vertrag_changed"],
    "control_hysteresis": ["stellmotor_getauscht", "stellventil_getauscht"],
}

MEASURE_COLS = ["filter_gereinigt", "durchfluss_neu", "daemmung_neu",
                "stellmotor_getauscht", "stellventil_getauscht",
                "regler_getauscht", "vertrag_changed"]


def load_quality(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Read meter_quality.csv, computing it first if absent."""
    path = PROCESSED / "meter_quality.csv"
    if not path.exists():
        print("  meter_quality.csv missing - classifying now")
        df = classify_all(data_dir)
        PROCESSED.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        return df
    return pd.read_csv(path, parse_dates=["ts_min", "ts_max", "window_start"])


def materialize_windows(quality: pd.DataFrame,
                        data_dir: Path = DATA_DIR,
                        out_dir: Path = WINDOW_DIR) -> pd.DataFrame:
    """Write the analysis-window slice of every selected meter."""
    sel = quality[(quality["quality_class"] == "auswertbar")
                  & (quality["zugeordnet"] == True)]  # noqa: E712
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.csv"):  # no stale meters from earlier runs
        old.unlink()
    for _, row in sel.iterrows():
        zid = int(row["Zählernummer"])
        df = load_meter_timeseries(zid, data_dir)
        win = df[df["Timestamp"] > pd.Timestamp(row["window_start"])]
        win.to_csv(out_dir / f"{zid}.csv", index=False)
    return sel


def join_ground_truth(predictions: pd.DataFrame,
                      nodes: pd.DataFrame) -> pd.DataFrame:
    """Attach inspection findings per meter via Zählernummer -> address."""
    tidy = tidy_inspections()
    tidy["datum"] = pd.to_datetime(tidy["datum"], errors="coerce")
    insp = tidy.groupby("address_norm").agg(
        n_inspections=("address_norm", "size"),
        insp_datum_max=("datum", "max"),
        **{c: (c, "any") for c in MEASURE_COLS},
    ).reset_index()
    insp["insp_any_measure"] = insp[MEASURE_COLS].any(axis=1)

    addr = nodes[["Zählernummer", "address_norm"]].copy()
    addr["Zählernummer"] = addr["Zählernummer"].astype(int)
    out = predictions.merge(addr, on="Zählernummer", how="left")
    out = out.merge(insp, on="address_norm", how="left")
    out["inspected"] = out["n_inspections"].notna()
    return out


def evaluate_binary(merged: pd.DataFrame) -> dict:
    """Fault-predicted vs. any-measure-recorded, on inspected meters only."""
    ev = merged[merged["inspected"]].copy()
    ev["pred_fault"] = ev["predicted_fault"] != "healthy"
    ev["truth_fault"] = ev["insp_any_measure"].astype(bool)
    tp = int((ev["pred_fault"] & ev["truth_fault"]).sum())
    fp = int((ev["pred_fault"] & ~ev["truth_fault"]).sum())
    fn = int((~ev["pred_fault"] & ev["truth_fault"]).sum())
    tn = int((~ev["pred_fault"] & ~ev["truth_fault"]).sum())
    return {
        "n_eval": len(ev), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else float("nan"),
        "recall": tp / (tp + fn) if tp + fn else float("nan"),
        "base_rate": ev["truth_fault"].mean() if len(ev) else float("nan"),
        "crosstab": pd.crosstab(ev["truth_fault"].rename("Begehung: Massnahme"),
                                ev["pred_fault"].rename("Baseline: Fehler"),
                                margins=True, margins_name="alle"),
    }


def evaluate_per_fault(merged: pd.DataFrame) -> pd.DataFrame:
    """Per predicted fault type: does the ASSUMED measure show up?"""
    ev = merged[merged["inspected"]]
    rows = []
    for fault, measures in FAULT_TO_MEASURE.items():
        pred = ev[ev["predicted_fault"] == fault]
        has_measure = ev[measures].any(axis=1)
        n_measure = int(has_measure.sum())
        hit = int(pred[measures].any(axis=1).sum()) if len(pred) else 0
        rows.append({
            "predicted_fault": fault,
            "angenommene Massnahme": " / ".join(measures),
            "n_vorhergesagt (inspiziert)": len(pred),
            "davon Massnahme dokumentiert": hit,
            "n_HAST mit Massnahme": n_measure,
            "davon so vorhergesagt": int(
                (ev["predicted_fault"] == fault)[has_measure].sum()),
        })
    return pd.DataFrame(rows)


# --- report ------------------------------------------------------------------

def rule_firing_shares(feats: pd.DataFrame) -> pd.DataFrame:
    """Share of meters on which each baseline rule condition holds.

    Mirrors the thresholds in fault_detection.detect_faults - keep in
    sync when rules change. Diagnostic only.
    """
    rules = [
        ("excess_rt (alarm)", "rt_mean_winter > 48 °C",
         feats["rt_mean_winter"] > 48),
        ("excess_rt (warn)", "RT > 50 °C in > 30 % der Laststunden",
         feats["rt_above_50_share_loaded"] > 0.30),
        ("continuous_flow (alarm)", "Sommer-Medianfluss > 25 l/h",
         feats["summer_flow_baseline"] > 25),
        ("fouled_filter (alarm)", "p95-Fluss-Trend < -3 l/h pro Monat",
         feats["flow_ceiling_slope_per_month"] < -3),
        ("low_spreading (warn)", "ΔT unter Last < 15 K",
         feats["dt_mean_loaded"] < 15),
        ("oversized_contract (warn)", "Spitzenlast < 40 % Anschlusswert",
         feats["peak_load_share"] < 0.40),
        ("control_hysteresis (alarm)", "4-12h-FFT-Anteil > 7 %",
         feats["flow_short_cycle_power"] > 0.07),
    ]
    return pd.DataFrame([
        {"Regel": name, "Bedingung": cond,
         "feuert bei": f"{mask.mean()*100:.0f} % der Zähler"}
        for name, cond, mask in rules
    ])


def write_report(quality: pd.DataFrame, sel: pd.DataFrame,
                 merged: pd.DataFrame, binary: dict,
                 per_fault: pd.DataFrame, feats: pd.DataFrame,
                 out_path: Path = REPORT) -> Path:
    today = pd.Timestamp.today().date()
    n_all = len(quality)
    cls_counts = quality["quality_class"].value_counts()

    def members(cls: str) -> str:
        sub = quality[quality["quality_class"] == cls]
        if sub.empty:
            return "_keine_"
        return ", ".join(str(int(z)) for z in sorted(sub["Zählernummer"]))

    pred_dist = (merged["predicted_fault"].value_counts()
                 .rename_axis("predicted_fault").reset_index(name="n"))

    excluded_assigned = quality[(quality["zugeordnet"] == True)  # noqa: E712
                                & (quality["quality_class"] != "auswertbar")]
    unassigned_ok = quality[(quality["zugeordnet"] == False)  # noqa: E712
                            & (quality["quality_class"] == "auswertbar")]

    win_min = pd.to_datetime(sel["window_start"]).min().date()
    win_max = pd.to_datetime(sel["ts_max"]).max().date()
    insp_max = merged["insp_datum_max"].max()
    insp_min = pd.to_datetime(
        tidy_inspections()["datum"], errors="coerce").min()

    lines = f"""# Integration der echten Zeitreihen

Generiert am {today} von `src/detect_real.py`. Baut auf der
Datensichtung ([datensichtung.md](datensichtung.md)) und der
Qualitätsklassifikation (`src/meter_quality.py`) auf.

> **Datenschutz:** enthält Zählernummern - nicht in öffentliche
> Artefakte oder Review-ZIPs übernehmen.

## 1. Auswahltrichter

| Stufe | Zähler |
|---|---|
| CSV-Exporte vorhanden | {n_all} |
| davon `auswertbar` | {cls_counts.get('auswertbar', 0)} |
| davon zusätzlich topologie-zugeordnet → **ausgewertet** | {len(sel)} |

Qualitätsklassen (Schwellen als Konstanten in `src/meter_quality.py`;
Analysefenster = letzte {WINDOW_DAYS} Tage je Zähler, Mindestabdeckung
{MIN_WINDOW_COVERAGE_PCT:.0f} %):

| Klasse | n | Zählernummern |
|---|---|---|
| auswertbar | {cls_counts.get('auswertbar', 0)} | (siehe `data/processed/meter_quality.csv`) |
| geringe_abdeckung | {cls_counts.get('geringe_abdeckung', 0)} | {members('geringe_abdeckung')} |
| verdaechtig_netzseitig | {cls_counts.get('verdaechtig_netzseitig', 0)} | {members('verdaechtig_netzseitig')} |
| inaktiv | {cls_counts.get('inaktiv', 0)} | {members('inaktiv')} |
| schema_abweichend | {cls_counts.get('schema_abweichend', 0)} | {members('schema_abweichend')} |

- {len(excluded_assigned)} topologie-zugeordnete Zähler fallen wegen
  Qualität heraus (alle `geringe_abdeckung`).
- {len(unassigned_ok)} auswertbare Zähler sind **nicht zugeordnet**
  (Zählertausch-Kandidaten, Stitching über `Zuordnung.xlsx` steht aus)
  und bleiben deshalb vorerst außen vor - nicht gelöscht.

## 2. Analysefenster

Je Zähler die letzten {WINDOW_DAYS} Tage vor seinem jüngsten
Datenpunkt; materialisiert unter `data/processed/real_meters_window/`.
Fenster über alle ausgewerteten Zähler: {win_min} bis {win_max}.
Rohwerte bleiben unverändert (keine Clipping-/Filterentscheidung);
`features.py` wurde minimal robustifiziert (Monats-Trend ignoriert
Monate ohne Daten, statt sie als Durchfluss 0 zu werten).

## 3. Baseline-Ergebnis auf echten Daten

Vorhersageverteilung über die {len(merged)} ausgewerteten Zähler:

{_md_table(pred_dist)}

### Binäre Bewertung (nur die {binary['n_eval']} inspizierten Zähler)

Bewertet wird: „Baseline meldet irgendeinen Fehler" gegen „Begehung
dokumentierte irgendeine Maßnahme". Zähler ohne Begehung haben
**unbekannte** Wahrheit und werden nicht bewertet.

- Basisrate: {binary['base_rate']*100:.0f} % der inspizierten Zähler
  hatten mindestens eine Maßnahme - die Messlatte für „besser als
  alles-melden" liegt entsprechend hoch.
- Precision {binary['precision']*100:.0f} %, Recall {binary['recall']*100:.0f} %
  (TP {binary['tp']}, FP {binary['fp']}, FN {binary['fn']}, TN {binary['tn']}).

{_md_table(binary['crosstab'].reset_index())}

### Je Fehlertyp (Mapping ist eine ANNAHME, siehe `FAULT_TO_MEASURE`)

{_md_table(per_fault)}

### Warum die Baseline alles meldet: Regel-Auslösung auf echten Daten

{_md_table(rule_firing_shares(feats))}

Zentrale Diagnose: Die FFT-Regel für `control_hysteresis` ist auf
echten Daten wertlos, weil reales Zapfverhalten von Natur aus im
4-12h-Band oszilliert - sie dominiert die Vorhersagen. Der hohe
Rücklauf ist dagegen vermutlich ein ECHTES Netzphänomen (deckt sich
mit der ÜZ-Problembeschreibung), aber die Schwelle trennt nicht
zwischen normal-für-dieses-Netz und auffällig. `peak_load_share` liegt
real im Median bei {feats['peak_load_share'].median():.2f} - stündliche
Spitzen ÜBERSTEIGEN die Vertragsleistung, die Synthetik nahm ~70 % an;
die `oversized_contract`-Regel ist damit real wirkungslos.

## 4. Ehrliche Einordnung

1. **Zeitliche Verzerrung:** Die Begehungen ({insp_min.date() if pd.notna(insp_min) else 'Datum unklar'}
   bis {insp_max.date() if pd.notna(insp_max) else 'Datum unklar'}) liegen teils VOR oder IM
   Analysefenster. Wo eine Maßnahme den Fehler behoben hat, misst die
   Baseline bereits den reparierten Zustand - ein „verpasster" Fehler
   kann schlicht schon behoben sein. Die Zahlen oben sind deshalb eine
   Untergrenze für den Recall auf unbehobenen Fehlern.
2. **Mapping-Annahme:** Fehlertyp → Maßnahme (z. B. excess_rt →
   Durchfluss neu) ist plausibel, aber nicht mit ÜZ validiert.
3. **Begehung ≠ vollständige Wahrheit:** Eine dokumentierte Maßnahme
   heißt nicht, dass der zugehörige Fehler im Fenster sichtbar war;
   keine Maßnahme heißt nicht, dass die Station fehlerfrei ist.
4. **Schwellen sind Synthetik-kalibriert:** Die Regelschwellen stammen
   aus den synthetischen Daten; eine Rekalibrierung auf echten Daten
   (mit dieser Ground Truth) ist der nächste logische Schritt.

## 5. Offene Punkte für ÜZ / Team

1. **Netzseitige Zähler bestätigen:** {members('verdaechtig_netzseitig')}
   - hohe Leistung + hoher Negativanteil; vermutlich Erzeuger-/
   Netzmessung, keine HAST.
2. **Inaktive Zähler klären:** {members('inaktiv')} - still­gelegt,
   nie in Betrieb, oder Exportfehler?
3. **Eingefrorene Zählerstände** (60 Zähler mit ≥ 7 Tagen konstantem
   Energy-Stand, siehe Datensichtung) - Exportproblem oder real?
4. **Schema-Abweichung:** Export für Zähler {members('schema_abweichend')}
   ohne ΔT-Spalte neu anfordern (oder ΔT aus Vorlauf−Rücklauf ableiten).
5. **Zählertausch-Stitching** über `Zuordnung.xlsx` für die nicht
   zugeordneten Zähler.
6. **Fehlertyp→Maßnahme-Mapping** fachlich bestätigen.
"""
    out_path.write_text(lines, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, default=REPORT)
    args = p.parse_args()

    print("→ loading quality classification")
    quality = load_quality()

    print("→ materialising analysis windows for auswertbar+zugeordnet meters")
    sel = materialize_windows(quality)
    print(f"  {len(sel)} meters → {WINDOW_DIR}")

    print("→ extracting features and running the rule-based baseline")
    nodes = ld.load_logical_nodes()
    feats = features_for_directory(WINDOW_DIR, nodes)
    feats.to_csv(PROCESSED / "features_real.csv", index=False)
    res = classify_dataframe(feats)

    print("→ joining inspection ground truth")
    merged = join_ground_truth(res, nodes)
    merged.to_csv(PROCESSED / "predictions_real.csv", index=False)
    print(f"  → {PROCESSED / 'features_real.csv'}")
    print(f"  → {PROCESSED / 'predictions_real.csv'}")

    binary = evaluate_binary(merged)
    per_fault = evaluate_per_fault(merged)
    out = write_report(quality, sel, merged, binary, per_fault, feats,
                       args.report)
    print(f"  → {out}")

    print()
    print("predicted fault distribution (real data):")
    print(merged["predicted_fault"].value_counts().to_string())
    print(f"\ninspected: {binary['n_eval']}/{len(merged)} | "
          f"base rate {binary['base_rate']*100:.0f} % | "
          f"precision {binary['precision']*100:.0f} % | "
          f"recall {binary['recall']*100:.0f} %")
    print(binary["crosstab"].to_string())
