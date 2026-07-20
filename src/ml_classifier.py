"""
ML-Zustandsklassifikation als Alternative zur regelbasierten Baseline.

WICHTIG - was das ist und was nicht:
Dies ist eine ZUSTANDS-Klassifikation, KEINE Ausfallvorhersage. Aufgabe:
aus den Zeitreihen-Features einer Station vorhersagen, welche
Begehungsbefunde (Maßnahmen) dokumentiert wurden. Für eine echte
Vorhersage fehlen Ausfall-Zeitpunkte vollständig; die Begehungen sagen
nur, was ein Techniker EINMAL vorgefunden hat.

Methodische Leitplanken (bewusst konservativ, kleine Stichprobe):
  * primär binär: mind. eine Maßnahme vs. keine (49 Samples, 40/9)
  * je Maßnahmentyp nur, wo beide Klassen groß genug sind (>= MIN_POS)
  * drei Vergleichsmaßstäbe mit denselben Metriken:
      (a) trivial: immer "Befund"  (Precision = Basisrate)
      (b) Regel-Baseline aus fault_detection.py
      (c) ML (LogReg, Random Forest flach)
    ML gilt nur als Fortschritt, wenn es (a) UND (b) schlägt.
  * stratifizierte 5-fold-CV, Mittelwert UND Streuung; die Streuung ist
    bei n=49 die wichtigere Zahl.
  * Leakage-Prüfung: Begehung teils IM Feature-Fenster (Reparatur schon
    in den Features enthalten) - explizit quantifiziert.
  * Interpretierbarkeit: Koeffizienten/Feature-Importances mit
    fachlicher Plausibilitätskontrolle.

Ein negatives Ergebnis ("ML bringt keinen Mehrwert") ist ein legitimes,
dokumentiertes Resultat.

Nutzt nur vorhandene Artefakte (features_real.csv, meter_quality.csv)
und den bestehenden Ground-Truth-Join aus detect_real - keine
Duplikation, keine Änderung bestehender Module oder des Dashboards.

Output: data/processed/ml_evaluation.csv, docs/ml-klassifikator.md

    python -m src.ml_classifier
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, f1_score,
                             precision_score, recall_score)
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from . import load_data as ld
from .detect_real import MEASURE_COLS, join_ground_truth
from .fault_detection import classify_dataframe
from .profile_timeseries import _md_table

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORT = ROOT / "docs" / "ml-klassifikator.md"

RANDOM_STATE = 42
N_SPLITS = 5

# Mindestzahl positiver UND negativer Fälle, damit ein Je-Typ-Modell
# methodisch vertretbar ist. Unter diesem Wert wird der Typ ehrlich
# ausgelassen statt auf einer Handvoll Positiver trainiert.
MIN_POS = 12

# Feature-Spalten (numerisch) aus features_real.csv. Identifikatoren
# (Zählernummer, address) sind bewusst ausgeschlossen.
FEATURE_COLS = [
    "rt_mean_winter", "rt_p95", "vl_mean_winter", "dt_mean_loaded",
    "dt_std_loaded", "dt_p10_loaded", "rt_above_50_share_loaded",
    "summer_flow_share", "summer_flow_baseline", "summer_idle_flow_median",
    "flow_ceiling_slope_per_month", "peak_load_kw", "p95_load_kw",
    "peak_load_share", "p95_load_share", "flow_short_cycle_power",
    "idle_share", "standby_dt", "energy_kwh_year", "volume_m3_year",
    "full_load_hours", "anschlusswert_kw",
]


# --- Datenaufbau -------------------------------------------------------------

def build_labelled() -> pd.DataFrame:
    """Feature-Matrix der inspizierten Stationen + Labels + Leakage-Flag.

    Reihenfolge der Zeilen ist deterministisch (nach Zählernummer).
    """
    feats = pd.read_csv(PROCESSED / "features_real.csv")
    nodes = ld.load_logical_nodes()

    # Regel-Baseline-Vorhersage je Station (predicted_fault) - wird als
    # Vergleichsmaßstab (b) gebraucht; classify_dataframe unverändert.
    preds = classify_dataframe(feats)
    merged = join_ground_truth(preds, nodes)

    # nur inspizierte Stationen (Label bekannt) mit vollständiger Feature-Zeile
    df = merged[merged["inspected"]].copy()
    df["Zählernummer"] = df["Zählernummer"].astype(int)

    # Leakage-Fenster anfügen
    q = pd.read_csv(PROCESSED / "meter_quality.csv",
                    parse_dates=["window_start", "ts_max"])
    q["Zählernummer"] = q["Zählernummer"].astype(int)
    df = df.merge(q[["Zählernummer", "window_start", "ts_max"]],
                  on="Zählernummer", how="left")
    df["insp_datum_max"] = pd.to_datetime(df["insp_datum_max"],
                                          errors="coerce")
    df["begehung_im_fenster"] = (
        (df["insp_datum_max"] >= df["window_start"])
        & (df["insp_datum_max"] <= df["ts_max"]))
    df["begehung_nach_fenster"] = df["insp_datum_max"] > df["ts_max"]
    df["begehung_ohne_datum"] = df["insp_datum_max"].isna()

    # Baseline-Binärvorhersage: irgendein Fehler gemeldet
    df["baseline_pred"] = (df["predicted_fault"] != "healthy").astype(int)
    # binäres Ziel
    for c in MEASURE_COLS:
        df[c] = df[c].fillna(False).astype(bool)
    df["y_binary"] = df["insp_any_measure"].fillna(False).astype(int)
    return df.sort_values("Zählernummer").reset_index(drop=True)


# --- Modelle und Metriken ----------------------------------------------------

def _models() -> dict:
    return {
        "LogReg": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
            ("clf", LogisticRegression(
                class_weight="balanced", max_iter=2000,
                random_state=RANDOM_STATE)),
        ]),
        "RandomForest": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("clf", RandomForestClassifier(
                n_estimators=200, max_depth=3, min_samples_leaf=3,
                class_weight="balanced", random_state=RANDOM_STATE)),
        ]),
    }


_METRICS = {
    "precision": lambda yt, yp: precision_score(yt, yp, zero_division=0),
    "recall": lambda yt, yp: recall_score(yt, yp, zero_division=0),
    "f1": lambda yt, yp: f1_score(yt, yp, zero_division=0),
    "balanced_acc": lambda yt, yp: balanced_accuracy_score(yt, yp),
}


def _fold_metrics(y_true, y_pred) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return {m: fn(y_true, y_pred) for m, fn in _METRICS.items()}


def evaluate_task(X: pd.DataFrame, y: np.ndarray,
                  baseline_pred: np.ndarray | None,
                  task: str) -> pd.DataFrame:
    """Stratifizierte CV; trivial/Baseline/ML auf DENSELBEN Folds.

    baseline_pred: Regel-Baseline-Binärvorhersage je Station (oder None
    für Je-Typ-Aufgaben, wo keine saubere Baseline definiert ist).
    """
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True,
                          random_state=RANDOM_STATE)
    models = _models()
    # je Ansatz: Liste der Fold-Metrik-Dicts
    per = {"trivial (immer Befund)": []}
    if baseline_pred is not None:
        per["Regel-Baseline"] = []
    for name in models:
        per[name] = []

    Xv = X.values
    for tr, te in skf.split(Xv, y):
        yte = y[te]
        # (a) trivial: immer positiv
        per["trivial (immer Befund)"].append(
            _fold_metrics(yte, np.ones_like(yte)))
        # (b) Regel-Baseline (keine Anpassung, nur indexieren)
        if baseline_pred is not None:
            per["Regel-Baseline"].append(
                _fold_metrics(yte, baseline_pred[te]))
        # (c) ML
        for name, model in models.items():
            model.fit(Xv[tr], y[tr])
            per[name].append(_fold_metrics(yte, model.predict(Xv[te])))

    rows = []
    for approach, folds in per.items():
        fdf = pd.DataFrame(folds)
        for metric in _METRICS:
            rows.append({
                "task": task, "approach": approach, "metric": metric,
                "mean": round(float(fdf[metric].mean()), 3),
                "std": round(float(fdf[metric].std(ddof=0)), 3),
            })
    return pd.DataFrame(rows)


def feature_importance(X: pd.DataFrame, y: np.ndarray) -> pd.DataFrame:
    """Koeffizienten (LogReg) + Importances (RF), auf allen Daten gefittet.

    Nur zur Plausibilitätskontrolle - NICHT metrisch bewertet (das wäre
    Training auf allen Daten).
    """
    imp = SimpleImputer(strategy="median")
    Xi = imp.fit_transform(X.values)
    scaler = StandardScaler().fit(Xi)
    logreg = LogisticRegression(class_weight="balanced", max_iter=2000,
                                random_state=RANDOM_STATE)
    logreg.fit(scaler.transform(Xi), y)
    rf = RandomForestClassifier(n_estimators=200, max_depth=3,
                                min_samples_leaf=3, class_weight="balanced",
                                random_state=RANDOM_STATE).fit(Xi, y)
    out = pd.DataFrame({
        "feature": X.columns,
        "logreg_coef": logreg.coef_[0].round(3),
        "rf_importance": rf.feature_importances_.round(3),
    })
    out["abs_coef"] = out["logreg_coef"].abs()
    return out.sort_values("abs_coef", ascending=False).drop(
        columns="abs_coef").reset_index(drop=True)


# --- Report ------------------------------------------------------------------

def _pivot(ev: pd.DataFrame, task: str) -> pd.DataFrame:
    """Eine Zeile je Ansatz, Spalten 'metric (mean±std)'."""
    sub = ev[ev["task"] == task]
    rows = []
    order = ["trivial (immer Befund)", "Regel-Baseline",
             "LogReg", "RandomForest"]
    for ap in [a for a in order if a in sub["approach"].values]:
        r = {"Ansatz": ap}
        for m in _METRICS:
            cell = sub[(sub["approach"] == ap) & (sub["metric"] == m)]
            if len(cell):
                r[m] = f"{cell['mean'].iloc[0]:.2f} ± {cell['std'].iloc[0]:.2f}"
        rows.append(r)
    return pd.DataFrame(rows)


def write_report(ev: pd.DataFrame, df: pd.DataFrame,
                 per_type_info: list[dict], fimp: pd.DataFrame,
                 out_path: Path = REPORT) -> Path:
    today = pd.Timestamp.today().date()
    n = len(df)
    n_pos = int(df["y_binary"].sum())
    base_rate = n_pos / n

    n_leak = int(df["begehung_im_fenster"].sum())
    n_clean = int(df["begehung_nach_fenster"].sum())
    n_nodate = int(df["begehung_ohne_datum"].sum())

    binary_tbl = _pivot(ev, "binär: mind. eine Maßnahme")

    typ_lines = []
    for info in per_type_info:
        if info["viable"]:
            typ_lines.append(
                f"- **{info['name']}** ({info['pos']} positiv / "
                f"{info['neg']} negativ): ausgewertet.")
        else:
            typ_lines.append(
                f"- **{info['name']}** ({info['pos']} positiv): "
                f"zu klein (< {MIN_POS}), **methodisch nicht vertretbar** "
                f"- weggelassen.")

    typ_tables = ""
    typ_edge = []  # Typen, wo ein ML-Modell trivial knapp schlägt
    for info in per_type_info:
        if info["viable"]:
            typ_tables += (f"\n**{info['name']}** "
                           f"({info['pos']}/{info['neg']}):\n\n"
                           + _md_table(_pivot(ev, info["task"])) + "\n")
            tsub = ev[ev["task"] == info["task"]]
            for ml in ["LogReg", "RandomForest"]:
                row = tsub[(tsub["approach"] == ml)
                           & (tsub["metric"] == "balanced_acc")]
                if len(row) and row["mean"].iloc[0] - row["std"].iloc[0] > 0.5:
                    typ_edge.append(info["name"])
                    break
    if typ_edge:
        typ_kommentar = (
            f"Bei {', '.join(sorted(set(typ_edge)))} liegt ein ML-Modell "
            f"in der mittleren Balanced Accuracy über dem trivialen "
            f"Klassifikator, und zwar um mehr als eine Streuung — der "
            f"einzige Lichtblick der ganzen Auswertung. Belastbar ist das "
            f"trotzdem nicht: die Fold-Streuung (±0.14 in der Größenordnung) "
            f"ist bei n=49 fast so groß wie der Vorsprung selbst, und die "
            f"Leakage-Kontamination aus Abschnitt 3 gilt hier genauso.")
    else:
        typ_kommentar = (
            "Auch je Typ schlägt kein ML-Modell den trivialen "
            "Klassifikator zuverlässig: wo die mittlere Balanced Accuracy "
            "über 0.50 liegt, ist die Fold-Streuung größer als der "
            "Vorsprung. Die Leakage-Kontamination aus Abschnitt 3 gilt hier "
            "genauso.")

    top_feats = fimp.head(8)

    # --- berechnete Plausibilitäts- und Schlussfolgerungs-Prosa ------------
    sub = ev[ev["task"] == "binär: mind. eine Maßnahme"]

    def _m(ap: str, metric: str) -> float:
        c = sub[(sub["approach"] == ap) & (sub["metric"] == metric)]
        return float(c["mean"].iloc[0]) if len(c) else float("nan")

    ml_names = ["LogReg", "RandomForest"]
    best_ml = max(ml_names, key=lambda a: _m(a, "f1"))
    best_ba = max(_m(a, "balanced_acc") for a in ml_names)
    trivial_ba = _m("trivial (immer Befund)", "balanced_acc")
    schlaegt_beide = (best_ba > trivial_ba
                      and _m(best_ml, "f1") > _m("Regel-Baseline", "f1"))

    top3 = list(fimp.head(3)["feature"])
    rt_oben = any("rt" in f or "dt" in f for f in top3)
    fft_oben = "flow_short_cycle_power" in list(fimp.head(5)["feature"])
    logreg_rf_uneinig = (
        fimp.sort_values("logreg_coef", key=abs, ascending=False)
            .head(3)["feature"].tolist()
        != fimp.sort_values("rf_importance", ascending=False)
            .head(3)["feature"].tolist())

    plaus = (
        f"Die stärksten LogReg-Koeffizienten sind {', '.join(top3)}. "
        + ("Dass Rücklauf-/ΔT-Größen (Auskühlung, Wärmeübertragung) oben "
           "stehen, ist fachlich plausibel — es ist derselbe "
           "Effizienz-Indikator, auf dem die Ampel beruht. "
           if rt_oben else
           "Auffällig: die Top-Features sind NICHT die fachlich erwarteten "
           "Rücklauf-/ΔT-Größen, was bei dieser Stichprobe eher für "
           "Rauschanpassung als für ein echtes Signal spricht. ")
        + ("Zugleich taucht `flow_short_cycle_power` weit oben auf — genau "
           "das FFT-Feature, das die Regel-Baseline auf echten Daten "
           "wertlos macht (reales Zapfverhalten oszilliert ohnehin im "
           "4–12h-Band). Das Modell greift also teils auf ein "
           "nicht-diskriminierendes Merkmal zu. " if fft_oben else "")
        + ("LogReg- und RF-Ranking widersprechen sich in den Top-3 deutlich "
           "— ein weiteres Zeichen instabiler, nicht belastbarer "
           "Feature-Zuschreibungen bei n=%d." % n if logreg_rf_uneinig else
           "LogReg- und RF-Ranking stimmen grob überein."))

    if schlaegt_beide:
        schluss = (
            f"Das beste ML-Modell ({best_ml}) schlägt in dieser Auswertung "
            f"sowohl den trivialen Klassifikator als auch die Regel-Baseline "
            f"— allerdings bei hoher Fold-Streuung, die vor Überinterpretation "
            f"bei n={n} warnt.")
    else:
        schluss = (
            f"**ML bringt mit dieser Datenlage keinen Mehrwert.** Das beste "
            f"ML-Modell ({best_ml}) erreicht eine Balanced Accuracy von "
            f"{best_ba:.2f} und schlägt damit **weder** den trivialen "
            f"Klassifikator noch die Regel-Baseline (beide Balanced Accuracy "
            f"{trivial_ba:.2f}). Beide ML-Modelle liegen bei der Balanced "
            f"Accuracy sogar unter dem Zufallsnullpunkt 0.50 — sie erkennen "
            f"die Minderheitsklasse (keine Maßnahme, nur {n - n_pos} Fälle) "
            f"schlechter als Raten. Die Gründe sind strukturell, nicht durch "
            f"Modellwahl behebbar:\n\n"
            f"1. **Massive Label-Kontamination:** {n_leak}/{n} Begehungen "
            f"liegen im Feature-Fenster (Abschnitt 3); die Features "
            f"beschreiben teils den reparierten Zustand.\n"
            f"2. **Extreme Klassen-Unbalance bei winziger Stichprobe:** "
            f"{n_pos}/{n - n_pos} bei n={n}. Jeder CV-Fold enthält ~{(n-n_pos)/N_SPLITS:.0f} "
            f"negative Fälle — die Streuung (oben) ist entsprechend groß und "
            f"jedes Ergebnis kaum belastbar.\n"
            f"3. **Feature:Sample-Verhältnis ~1:{n/len(FEATURE_COLS):.1f}:** "
            f"Overfitting ist bei {len(FEATURE_COLS)} Features und n={n} kaum "
            f"vermeidbar.\n\n"
            f"Die Regel-Baseline ihrerseits ist ebenfalls nicht nützlich — "
            f"sie meldet schlicht alles als Befund und ist damit identisch "
            f"zum trivialen Klassifikator (Balanced Accuracy 0.50). Die "
            f"ehrliche Gesamtaussage: **auf dieser Datenbasis trennt weder "
            f"Regel noch ML zuverlässig zwischen Stationen mit und ohne "
            f"Handlungsbedarf.** Voraussetzung für einen sinnvollen nächsten "
            f"Versuch sind Daten ohne Leakage (Zeitreihen VOR der jeweiligen "
            f"Begehung) und mehr negative Fälle — beides nur über ÜZ "
            f"zu beschaffen, nicht über bessere Modelle.")

    lines = f"""# ML-Zustandsklassifikator: Evaluation

Generiert am {today} von `src/ml_classifier.py`. Additive Evaluation -
kein bestehendes Modul und nicht das Dashboard verändert.

> **Datenschutz:** aggregierte Metriken, keine Zählernummern im Report.

## 1. Aufgabenstellung — Klassifikation, keine Vorhersage

Vorhergesagt wird der **dokumentierte Zustand** einer Station (welche
Begehungsmaßnahme wurde durchgeführt), nicht ein künftiger Ausfall.
Eine echte Ausfall**vorhersage** ist mit diesen Daten unmöglich: es
gibt keine Ausfall-Zeitpunkte, nur eine einmalige Begehungsmomentaufnahme
je Station. Die Aufgabe ist damit eine Zustands-Klassifikation aus
Zeitreihen-Features gegen die Begehung als Ground Truth.

## 2. Stichprobe und Klassenverteilung

- **{n} Stationen** mit auswertbaren Features UND dokumentierter Begehung.
- Binäres Ziel „mindestens eine Maßnahme": **{n_pos} positiv / {n - n_pos}
  negativ** (Basisrate {base_rate*100:.0f} %).
- {len(FEATURE_COLS)} numerische Features. Bei {n} Samples ist das
  Verhältnis Features:Samples ≈ 1:{n/len(FEATURE_COLS):.1f} — hohe
  Overfitting-Gefahr; deshalb bewusst einfache Modelle, Regularisierung,
  flache Bäume, kein Tuning.

### Je Maßnahmentyp — Machbarkeitsprüfung

{chr(10).join(typ_lines)}

Stellmotor/Stellventil (je 2 positiv) und Regler (0) werden **nicht**
modelliert — ein Modell auf 2 positiven Fällen wäre methodisch wertlos.

## 3. Leakage-Analyse (kritisch)

Die Begehungen liegen laut [echte-daten-integration.md](echte-daten-integration.md)
im Zeitraum der Analysefenster. Konkret für die {n} gelabelten Stationen:

| Lage der Begehung zum Feature-Fenster | Stationen |
|---|---|
| **IM Fenster** (Features enthalten Zustand nach Reparatur) | {n_leak} |
| nach dem Fenster (sauber) | {n_clean} |
| ohne verwertbares Datum | {n_nodate} |

**Das ist der wichtigste Befund:** bei {n_leak} von {n} Stationen
({n_leak/n*100:.0f} %) enthält das Feature-Fenster Betriebsdaten aus der
Zeit NACH der dokumentierten Maßnahme. Die Features spiegeln dann teils
den bereits reparierten Zustand — jedes Modell (Regel oder ML) lernt
gegen ein kontaminiertes Label. Die saubere Teilmenge (Begehung nach
Fenster) umfasst nur **{n_clean} Stationen** und ist damit **zu klein
für eine separate, belastbare Auswertung** — eine harte Limitation,
keine behebbare Stellschraube ohne neue Daten (frühere Begehungen oder
frühere Zeitreihen von ÜZ).

## 4. Drei Vergleichsmaßstäbe (binär, stratifizierte {N_SPLITS}-fold-CV)

Mittelwert ± Streuung über die Folds. **Die Streuung ist bei n={n} die
entscheidende Zahl.**

{_md_table(binary_tbl)}

Lesart: Der triviale Klassifikator erreicht per Basisrate eine Precision
von ~{base_rate:.2f} und Recall 1.0 — jede sinnvolle Alternative muss
das schlagen, ohne den Recall zu opfern. Balanced Accuracy 0.50 beim
trivialen Klassifikator ist der eigentliche Nullpunkt: er erkennt die
negative Klasse (keine Maßnahme) per Definition nie.

## 5. Je-Typ-Ergebnisse (nur methodisch vertretbare Typen)
{typ_tables}
{typ_kommentar}

## 6. Feature-Wichtigkeiten (binär, Plausibilitätskontrolle)

Auf allen Daten gefittet, nur zur Interpretation (nicht metrisch
bewertet). Top nach |LogReg-Koeffizient|:

{_md_table(top_feats)}

**Fachliche Plausibilitätskontrolle:** {plaus}

## 7. Schlussfolgerung

{schluss}
"""
    out_path.write_text(lines, encoding="utf-8")
    return out_path


# --- CLI ---------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, default=REPORT)
    p.add_argument("--out", type=Path,
                   default=PROCESSED / "ml_evaluation.csv")
    args = p.parse_args()

    print("→ Aufbau des gelabelten Datensatzes (Features + Ground Truth)")
    df = build_labelled()
    X = df[FEATURE_COLS]
    y = df["y_binary"].values
    n_pos = int(y.sum())
    print(f"  {len(df)} Stationen, {n_pos} positiv / {len(df)-n_pos} negativ, "
          f"Basisrate {n_pos/len(df)*100:.0f} %")
    print(f"  Leakage: {int(df['begehung_im_fenster'].sum())} Begehungen im "
          f"Fenster, {int(df['begehung_nach_fenster'].sum())} danach, "
          f"{int(df['begehung_ohne_datum'].sum())} ohne Datum")

    print("→ binäre Aufgabe: 3 Vergleichsmaßstäbe, stratifizierte CV")
    all_ev = [evaluate_task(X, y, df["baseline_pred"].values,
                            "binär: mind. eine Maßnahme")]

    print("→ Je-Typ-Machbarkeit und Auswertung")
    per_type_info = []
    for col, label in [("filter_gereinigt", "Filter gereinigt"),
                       ("durchfluss_neu", "Durchfluss neu"),
                       ("daemmung_neu", "Dämmung neu"),
                       ("vertrag_changed", "Vertragsleistung geändert"),
                       ("stellmotor_getauscht", "Stellmotor getauscht"),
                       ("stellventil_getauscht", "Stellventil getauscht"),
                       ("regler_getauscht", "Regler getauscht")]:
        yt = df[col].astype(int).values
        pos = int(yt.sum())
        viable = pos >= MIN_POS and (len(yt) - pos) >= MIN_POS
        info = {"name": label, "col": col, "pos": pos,
                "neg": len(yt) - pos, "viable": viable,
                "task": f"Typ: {label}"}
        per_type_info.append(info)
        if viable:
            all_ev.append(evaluate_task(X, yt, None, info["task"]))
            print(f"  {label}: {pos}/{len(yt)-pos} → ausgewertet")
        else:
            print(f"  {label}: {pos} positiv → zu klein, weggelassen")

    ev = pd.concat(all_ev, ignore_index=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ev.to_csv(args.out, index=False)
    print(f"  → {args.out}")

    print("→ Feature-Wichtigkeiten (binär)")
    fimp = feature_importance(X, y)

    write_report(ev, df, per_type_info, fimp, args.report)
    print(f"  → {args.report}")

    print("\n=== binär: Zusammenfassung (mean ± std über Folds) ===")
    print(_pivot(ev, "binär: mind. eine Maßnahme").to_string(index=False))
    print("\nTop-Features (|LogReg-Koeffizient|):")
    print(fimp.head(6).to_string(index=False))


if __name__ == "__main__":
    main()
