"""Vergleichsgruppe nach Wärmemenge im Kernwinter.

Der Netzvergleich stellt jede Station neben alle übrigen Stationen des
Winters. Hier wird jede Station nur mit den k Stationen verglichen, die im
selben Winter am ähnlichsten viel Wärme abgenommen haben. Die Frage
dahinter: Ist eine Station, die im Netz Mittelmaß ist, unter Häusern mit
ähnlichem Verbrauch schlecht, oder umgekehrt?

Die Wärmemenge ist die mittlere Leistung der Betriebsstunden im Kernwinter
mal die Stunden des Kernwinters. Lücken in der Reihe zählen damit nicht
als wenig Verbrauch. Weil die Punkttabelle nur Stunden mit Leistung über
null enthält, ist das ein Größenmaß für die Gruppenbildung und keine
Wärmebilanz.

Danach gelten dieselben Regeln wie im Netzvergleich (`netzvergleich.markiere`).
"""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from . import netzvergleich as nv

K_GRUPPE = 15
K_SENSITIVITAET = (10, 15, 25)
ENERGIE_SPALTEN = ["meter", "winter", "n_punkte", "mittlere_leistung_kw",
                   "waermemenge_kwh"]
VERGLEICH_SPALTEN = ["winter", "n", "auffaellig_netz", "auffaellig_gruppe",
                     "beide", "jaccard", "spearman", "neu", "weg"]


def _kernwinter_stunden(label: str) -> float:
    ende = nv.winter_ende_jahr(label)
    start = pd.Timestamp(ende - 1, 12, 1)
    return (pd.Timestamp(ende, 3, 1) - start) / pd.Timedelta(hours=1)


def winterenergie(punkte: Mapping[int, pd.DataFrame],
                  min_punkte: int = nv.MIN_STUNDEN_WINTER) -> pd.DataFrame:
    """Hochgerechnete Wärmemenge je Station und Kernwinter in kWh."""
    zeilen = []
    for meter, tab in punkte.items():
        if tab is None or len(tab) == 0:
            continue
        w = nv.heizperiode(tab["zeit"])
        leistung = pd.to_numeric(tab["power_kw"], errors="coerce")
        df = pd.DataFrame({"winter": w, "p": leistung.to_numpy()})
        df = df[(df["winter"] != "") & df["p"].notna()]
        for winter, g in df.groupby("winter"):
            if len(g) < int(min_punkte):
                continue
            p = float(g["p"].mean())
            zeilen.append({"meter": int(meter), "winter": winter,
                           "n_punkte": int(len(g)),
                           "mittlere_leistung_kw": p,
                           "waermemenge_kwh": p * _kernwinter_stunden(winter)})
    out = pd.DataFrame(zeilen, columns=ENERGIE_SPALTEN)
    return out.sort_values(["winter", "meter"]).reset_index(drop=True)


def gruppenbezug(tabelle: pd.DataFrame,
                 energie: pd.DataFrame,
                 k: int = K_GRUPPE,
                 referenz_ausschluss: Sequence[int] = nv.REFERENZ_AUSSCHLUSS,
                 min_stationen: int = nv.MIN_STATIONEN_WINTER,
                 kennzahlen: Mapping[str, int] = nv.KENNZAHLEN) -> pd.DataFrame:
    """z-Werte je Kennzahl gegen die k Stationen mit nächster Wärmemenge.

    Die Gruppe besteht aus Referenzstationen (ohne ``referenz_ausschluss``
    und ohne die Station selbst) desselben Winters, gemessen am Abstand
    der logarithmierten Wärmemenge. Stationen ohne Wärmemenge fallen auf
    den Netzbezug zurück (``bezug = "netz"``), Winter mit zu wenigen
    Stationen bleiben wie im Netzvergleich ohne z-Wert. ``gruppe_faktor``
    ist das Verhältnis größte zu kleinster Wärmemenge in der Gruppe.
    """
    netz = nv.netzbezug(tabelle, referenz_ausschluss=referenz_ausschluss,
                        min_stationen=min_stationen, kennzahlen=kennzahlen)
    out = netz.merge(energie[["meter", "winter", "waermemenge_kwh"]],
                     on=["meter", "winter"], how="left")
    out["gruppe_n"] = 0
    out["gruppe_faktor"] = np.nan
    for _, idx in out.groupby("winter").groups.items():
        w = out.loc[idx]
        if (w["bezug"] == "zu_klein").all():
            continue
        ref = w[w["in_referenz"] & (w["waermemenge_kwh"] > 0)]
        log_ref = np.log(ref["waermemenge_kwh"].to_numpy(dtype=float))
        for i in w.index[w["waermemenge_kwh"] > 0]:
            eigen = ref.index != i
            abstand = np.abs(log_ref[eigen]
                             - np.log(out.at[i, "waermemenge_kwh"]))
            wahl = ref[eigen].iloc[np.argsort(abstand, kind="stable")[:int(k)]]
            if len(wahl) < 2:
                continue
            for kz, vz in kennzahlen.items():
                out.at[i, f"z_{kz}"] = nv.robust_z([out.at[i, kz]], wahl[kz],
                                                   vz)[0]
            e = wahl["waermemenge_kwh"]
            out.at[i, "gruppe_n"] = int(len(wahl))
            out.at[i, "gruppe_faktor"] = float(e.max() / e.min())
            out.at[i, "bezug"] = "gruppe"
    return out


def vergleiche(netz: pd.DataFrame, gruppe: pd.DataFrame) -> pd.DataFrame:
    """Je Winter: Überlappung der Auffälligen und Rangkorrelation des Scores."""
    m = netz[["meter", "winter", "score", "auffaellig"]].merge(
        gruppe[["meter", "winter", "score", "auffaellig"]],
        on=["meter", "winter"], suffixes=("_netz", "_gruppe"))
    zeilen = []
    for w, g in m.groupby("winter"):
        a = set(g.loc[g["auffaellig_netz"], "meter"].astype(int))
        b = set(g.loc[g["auffaellig_gruppe"], "meter"].astype(int))
        s = g[["score_netz", "score_gruppe"]].dropna()
        rho = (float(stats.spearmanr(s["score_netz"], s["score_gruppe"])[0])
               if len(s) >= 3 else np.nan)
        zeilen.append({"winter": w, "n": int(len(s)),
                       "auffaellig_netz": len(a), "auffaellig_gruppe": len(b),
                       "beide": len(a & b),
                       "jaccard": len(a & b) / len(a | b) if a | b else np.nan,
                       "spearman": rho,
                       "neu": sorted(b - a), "weg": sorted(a - b)})
    out = pd.DataFrame(zeilen, columns=VERGLEICH_SPALTEN)
    if len(out):
        out["_j"] = out["winter"].map(nv.winter_ende_jahr)
        out = out.sort_values("_j").drop(columns="_j").reset_index(drop=True)
    return out
