"""
Wartungspriorisierung: transparenter, scorebasierter Prioritaets-Index
je auswertbarer, topologie-zugeordneter Station.

AUSDRUECKLICH KEINE VORHERSAGE und kein ML: eine gewichtete Summe
normalisierter, direkt gemessener bzw. dokumentierter Groessen -
"priorisierte Handlungsempfehlung auf Basis aktueller Messwerte",
keine Ausfallprognose. Jede Komponente ist einzeln im Output sichtbar,
damit jede Empfehlung erklaerbar bleibt.

Komponenten (jeweils auf 0..1 normalisiert, Gewichte unten):

  ruecklauf   wie weit der mittlere Winter-Ruecklauf ueber der
              Gruen-Schwelle liegt - zentraler Effizienz-Indikator (UEZ)
  last        Anschlusswert (log-skaliert): Ineffizienz grosser
              Verbraucher wirkt staerker aufs Netz -> leichter Aufschlag
  begehung    Informationsluecke: keine dokumentierte Begehung = voller
              Aufschlag, sonst anteilig nach Alter der letzten Begehung

Stationen mit Datenqualitaetsproblemen (Qualitaetsklasse nicht
"auswertbar", keine Zeitreihen, kein Winterwert) bekommen KEINEN Score,
sondern die separate Klasse "erst Daten klaeren" - Datenprobleme werden
nicht mit Effizienz-Auffaelligkeiten vermischt.

Output: data/processed/priority_scores.csv (alle Einzelkomponenten,
Beitraege in Punkten, Klartext-Begruendung).

    python -m src.priority
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

# --- Gewichte und Schwellen: STARTWERTE, fachlich mit UEZ zu validieren -----

# Gewichte der Komponenten; muessen sich zu 1 summieren. Der Ruecklauf
# dominiert bewusst (zentraler Effizienz-Indikator laut UEZ).
W_RUECKLAUF = 0.60
W_LAST = 0.15
W_BEGEHUNG = 0.25

# Ruecklauf-Normalisierung: 0 bei <= RT_ZIEL_C (Gruen-Schwelle der
# Dashboard-Ampel), 1 bei >= RT_ZIEL_C + RT_SPANNE_C.
RT_ZIEL_C = 45.0
RT_SPANNE_C = 15.0

# Begehungs-Alter, ab dem der volle Aufschlag gilt (2 Jahre). Keine
# dokumentierte Begehung zaehlt immer als voller Aufschlag.
BEGEHUNG_MAX_TAGE = 730

# Klartext-Einstufung des Gesamtscores (0..100 Punkte).
SCORE_HOCH = 55.0
SCORE_MITTEL = 30.0

assert abs(W_RUECKLAUF + W_LAST + W_BEGEHUNG - 1.0) < 1e-9


def _load(path: Path, cmd: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} fehlt - erzeugen mit: {cmd}")
    return pd.read_csv(path)


def compute_scores(today: pd.Timestamp | None = None) -> pd.DataFrame:
    """Prioritaets-Score je Station aus den vorhandenen Artefakten.

    `today` bestimmt das Begehungs-Alter (Default: heute) - der Score
    ist damit bewusst zeitabhaengig, das Alter einer Begehung waechst.
    """
    today = pd.Timestamp.today().normalize() if today is None else today

    geo = _load(PROCESSED / "hast_geocoded.csv",
                "python -m src.main --geocode")
    quality = _load(PROCESSED / "meter_quality.csv",
                    "python -m src.meter_quality")
    feats = _load(PROCESSED / "features_real.csv",
                  "python -m src.detect_real")
    insp = _load(PROCESSED / "inspections_tidy.csv", "python -m src.main")

    df = geo[["Zählernummer", "address", "address_norm",
              "Anschlusswert"]].copy()
    df["Zählernummer"] = df["Zählernummer"].astype(int)
    q = quality[["Zählernummer", "quality_class", "zugeordnet"]].copy()
    q["Zählernummer"] = q["Zählernummer"].astype(int)
    df = df.merge(q, on="Zählernummer", how="left")
    f = feats[["Zählernummer", "rt_mean_winter"]].copy()
    f["Zählernummer"] = f["Zählernummer"].astype(int)
    df = df.merge(f, on="Zählernummer", how="left")

    insp = insp.copy()
    insp["datum"] = pd.to_datetime(insp["datum"], errors="coerce")
    last = insp.groupby("address_norm")["datum"].max().rename("begehung_datum")
    df = df.merge(last, on="address_norm", how="left")
    df["tage_seit_begehung"] = (today - df["begehung_datum"]).dt.days

    # --- Klasse: nur saubere Daten werden priorisiert ----------------------
    scorable = (df["quality_class"].eq("auswertbar")
                & df["zugeordnet"].fillna(False).astype(bool)
                & df["rt_mean_winter"].notna())
    df["prio_klasse"] = np.where(scorable, "priorisieren",
                                 "erst Daten klaeren")

    # --- Komponenten (0..1) -------------------------------------------------
    df["comp_ruecklauf"] = ((df["rt_mean_winter"] - RT_ZIEL_C)
                            / RT_SPANNE_C).clip(0, 1)
    kw = df["Anschlusswert"].astype(float)
    df["comp_last"] = np.log1p(kw) / np.log1p(kw.max())
    df["comp_begehung"] = np.where(
        df["begehung_datum"].isna(), 1.0,
        (df["tage_seit_begehung"] / BEGEHUNG_MAX_TAGE).clip(0, 1))

    # --- gewichtete Beitraege in Punkten (Summe = Score, max 100) ----------
    df["beitrag_ruecklauf"] = (100 * W_RUECKLAUF * df["comp_ruecklauf"]).round(1)
    df["beitrag_last"] = (100 * W_LAST * df["comp_last"]).round(1)
    df["beitrag_begehung"] = (100 * W_BEGEHUNG * df["comp_begehung"]).round(1)
    df["prio_score"] = (df["beitrag_ruecklauf"] + df["beitrag_last"]
                        + df["beitrag_begehung"]).round(1)

    # kein Score fuer "erst Daten klaeren" - Datenluecke ist kein Effizienzbefund
    for c in ["comp_ruecklauf", "beitrag_ruecklauf", "prio_score"]:
        df.loc[~scorable, c] = np.nan

    df["begruendung_prio"] = df.apply(_klartext, axis=1)
    return df.sort_values("prio_score", ascending=False,
                          na_position="last").reset_index(drop=True)


def _klartext(r: pd.Series) -> str:
    """Ein nachvollziehbarer Satz, warum diese Station diese Prioritaet hat."""
    if r["prio_klasse"] != "priorisieren":
        grund = (r["quality_class"] if pd.notna(r["quality_class"])
                 else "keine Zeitreihen vorhanden")
        return (f"Erst Daten klären ({grund}) — keine Priorisierung, "
                f"solange die Datenlage unklar ist.")

    score = r["prio_score"]
    stufe = ("Hohe" if score >= SCORE_HOCH
             else "Mittlere" if score >= SCORE_MITTEL else "Niedrige")
    teile = []
    rt = r["rt_mean_winter"]
    if r["comp_ruecklauf"] >= 0.6:
        teile.append(f"Winter-Rücklauf {rt:.0f} °C deutlich über "
                     f"Zielwert ({RT_ZIEL_C:.0f} °C)")
    elif r["comp_ruecklauf"] > 0:
        teile.append(f"Winter-Rücklauf {rt:.0f} °C über Zielwert "
                     f"({RT_ZIEL_C:.0f} °C)")
    else:
        teile.append(f"Winter-Rücklauf {rt:.0f} °C im Zielbereich")
    if r["comp_last"] >= 0.7:
        teile.append(f"großer Anschlusswert ({r['Anschlusswert']:.0f} kW)")
    if pd.isna(r["begehung_datum"]):
        teile.append("keine dokumentierte Begehung")
    elif r["comp_begehung"] >= 0.5:
        teile.append(f"letzte Begehung liegt "
                     f"{r['tage_seit_begehung'] / 30:.0f} Monate zurück")
    return f"{stufe} Priorität: " + "; ".join(teile) + "."


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path,
                   default=PROCESSED / "priority_scores.csv")
    args = p.parse_args()

    print("→ berechne Prioritäts-Scores (transparente gewichtete Summe, "
          "keine Vorhersage)")
    df = compute_scores()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"  → {args.out}")

    sc = df[df["prio_klasse"] == "priorisieren"]
    print(f"\n{len(sc)} Stationen priorisiert, "
          f"{len(df) - len(sc)} 'erst Daten klären'")
    print(f"Score: Median {sc['prio_score'].median():.1f}, "
          f"max {sc['prio_score'].max():.1f} von 100")
    print("\nTop 10:")
    cols = ["Zählernummer", "address", "prio_score",
            "beitrag_ruecklauf", "beitrag_last", "beitrag_begehung"]
    print(sc.head(10)[cols].to_string(index=False))
