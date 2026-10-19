"""
Fallsammlung zur Begehungswirkung im Ternärbild.

Das Team wollte die Fälle sehen, in denen ein Ternärdiagramm eine
Effizienzsteigerung zeigt und gleichzeitig eine Begehung stattgefunden
hat. Dieses Modul stellt die Bausteine dafür bereit: den saisongleichen
Vorher-Nachher-Schnitt, eine Kontrollgruppe aus Stationen ohne Begehung
und die Kennzahlen, mit denen sich beide Gruppen vergleichen lassen.

Zwei Entscheidungen stecken drin, die das Ergebnis tragen.

Erstens wird saisongleich verglichen. Der Gruppenschnitt in
`src/ternaer.py` teilt die ganze Historie am Begehungsdatum, und weil
fast alle Termine im Spätsommer und Herbst 2024 liegen, steht dann ein
Vorher aus mehreren Jahren einem Nachher aus einem Winter gegenüber.
Wer so vergleicht, misst vor allem die Jahreszeit. Hier wird deshalb
nur Winter gegen Winter gestellt.

Zweitens bekommen Stationen ohne Begehung ein Pseudodatum, das aus der
Verteilung der echten Termine gezogen wird. Damit liegt die Kontroll-
gruppe im selben Kalenderfenster und eine Veränderung, die alle
Stationen gleichzeitig betrifft, fällt in beiden Gruppen an.

Begehungen ohne Datum in der Excel gehören in keine der beiden Gruppen.
Begangen wurden sie, nur lässt sich der Zeitpunkt nicht zuordnen.
"""

from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import ternaer as tn

MIN_PUNKTE = 30

#ab dieser Steigerung gilt ein Fall als deutlich; gesetzt, nicht hergeleitet
SCHWELLE_STEIGERUNG = 2.0

#Modulationsanteil, ab dem eine Station als spreizungsdominiert gilt
SCHWELLE_SPREIZUNG = 0.6

#Befundkategorien aus src/befundcodes.py, die einen koerperlichen Eingriff
#an der Hydraulik bedeuten. Nur solche Eingriffe koennen die Kennlinie und
#damit das Ternaerbild verschieben.
MECHANISCH = ["schmutzfaenger", "ventil_stellantrieb", "pumpe",
              "zirkulation", "hydraulik_volumenstrom"]


def kontrollgruppe(meter: Iterable[int],
                   begehungsdatum: Mapping[int, object],
                   ausschluss: Optional[Iterable[int]] = None,
                   seed: int = 42) -> dict:
    """Pseudodatum je Station ohne Begehung, gezogen aus den echten Terminen.

    Dadurch hat die Kontrollgruppe dieselbe Saisonlage wie die
    Begehungsgruppe. ``ausschluss`` nimmt die Zähler auf, deren Begehung
    ohne Datum in der Tabelle steht - die gehören in keine Gruppe.
    """
    termine = sorted(pd.Timestamp(d) for d in begehungsdatum.values())
    if not termine:
        return {}
    raus = set(begehungsdatum) | set(ausschluss or ())
    ohne = sorted(set(meter) - raus)
    rng = np.random.default_rng(seed)
    gezogen = rng.integers(0, len(termine), size=len(ohne))
    return {m: termine[int(i)] for m, i in zip(ohne, gezogen)}


def _leere_werte() -> dict:
    """Platzhalterzeile, damit Stationen ohne Punkte nicht still verschwinden."""
    werte = {"n_vorher": 0, "n_nachher": 0}
    for name in ("perf", "mod_dt", "streuung"):
        werte[f"{name}_vorher"] = np.nan
        werte[f"{name}_nachher"] = np.nan
    return werte


def _panelwerte(tab: pd.DataFrame, meter: int) -> dict:
    """Vorher und Nachher einer Station zu einer Zeile zusammenziehen."""
    k = tn.kennzahlen(tab, "gruppe_begehung",
                      [tn.GRUPPE_VORHER, tn.GRUPPE_NACHHER],
                      meter=meter).set_index("gruppe")
    v, n = tn.GRUPPE_VORHER, tn.GRUPPE_NACHHER
    return {
        "n_vorher": int(k.loc[v, "n"]),
        "n_nachher": int(k.loc[n, "n"]),
        "perf_vorher": k.loc[v, "performance_median"],
        "perf_nachher": k.loc[n, "performance_median"],
        "mod_dt_vorher": k.loc[v, "anteil_mod_dt"],
        "mod_dt_nachher": k.loc[n, "anteil_mod_dt"],
        "streuung_vorher": k.loc[v, "streuung"],
        "streuung_nachher": k.loc[n, "streuung"],
    }


def effekt_je_station(serien: Mapping[int, pd.DataFrame],
                      datum: Mapping[int, object],
                      begangen: Iterable[int],
                      saison: Optional[str] = tn.GRUPPE_WINTER,
                      min_punkte: int = MIN_PUNKTE,
                      aufloesung: str = "stunde") -> pd.DataFrame:
    """Vorher-Nachher-Effekt je Station, wahlweise auf eine Saison begrenzt.

    ``saison=None`` nimmt die gesamte Historie und entspricht dem
    naiven Schnitt aus Notebook 12. Stationen ohne Punkte fallen nicht
    still heraus, sie stehen mit n = 0 in der Tabelle.
    """
    begangen = set(begangen)
    rows = []
    for meter, df in sorted(serien.items()):
        if meter not in datum:
            continue
        tab = tn.stationstabelle(df, meter, aufloesung=aufloesung,
                                 begehungsdatum=datum[meter])
        if len(tab) == 0:
            zeile = {"meter": meter, "begehung": meter in begangen,
                     "datum": pd.Timestamp(datum[meter])}
            zeile.update(_leere_werte())
            rows.append(zeile)
            continue
        teil = tab if saison is None else tab[tab["gruppe_saison"] == saison]
        zeile = {"meter": meter, "begehung": meter in begangen,
                 "datum": pd.Timestamp(datum[meter])}
        zeile.update(_panelwerte(teil, meter))
        rows.append(zeile)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["d_perf"] = out["perf_nachher"] - out["perf_vorher"]
    out["d_mod_dt"] = out["mod_dt_nachher"] - out["mod_dt_vorher"]
    out["d_streuung"] = out["streuung_nachher"] - out["streuung_vorher"]
    out["genug"] = ((out["n_vorher"] >= min_punkte)
                    & (out["n_nachher"] >= min_punkte))
    return out


def cliffs_delta(x: Sequence[float], y: Sequence[float]) -> float:
    """Rangbasierte Effektstärke zwischen zwei Stichproben.

    Liegt zwischen -1 und +1 und sagt, wie oft ein Wert aus ``x`` größer
    ist als einer aus ``y``. Anders als ein p-Wert hängt das Maß nicht
    am Stichprobenumfang, was bei 14 gegen 26 Stationen der Punkt ist.
    """
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    y = np.asarray([v for v in y if np.isfinite(v)], dtype=float)
    if not len(x) or not len(y):
        return float("nan")
    groesser = sum(int((xi > y).sum()) for xi in x)
    kleiner = sum(int((xi < y).sum()) for xi in x)
    return (groesser - kleiner) / (len(x) * len(y))


def gruppenvergleich(tab: pd.DataFrame,
                     gruppenspalte: str,
                     wert: str = "d_perf") -> pd.DataFrame:
    """Je Gruppe Anzahl, Median, Mittel und Anteil positiver Fälle."""
    rows = []
    for gruppe, teil in tab.groupby(gruppenspalte, observed=True):
        s = teil[wert].dropna()
        rows.append({
            "gruppe": gruppe,
            "n": int(len(s)),
            "median": float(s.median()) if len(s) else np.nan,
            "mittel": float(s.mean()) if len(s) else np.nan,
            "anteil_positiv": float((s > 0).mean()) if len(s) else np.nan,
        })
    return pd.DataFrame(rows)


def markiere_mechanisch(tab: pd.DataFrame,
                        labels: pd.DataFrame,
                        kategorien: Sequence[str] = MECHANISCH) -> pd.DataFrame:
    """Spalte ``mechanisch`` aus den kodierten Freitextbefunden anhängen.

    ``labels`` ist die Ausgabe von `befundcodes.labels_je_zaehler`.
    Stationen ohne Notiz gelten als nicht mechanisch; das ist die
    vorsichtige Richtung, weil eine fehlende Notiz kein Beleg für einen
    Eingriff ist.
    """
    out = tab.copy()
    lab = labels.set_index("meter")
    vorhanden = [c for c in kategorien if c in lab.columns]
    treffer = lab[vorhanden].fillna(0).sum(axis=1) > 0
    out["mechanisch"] = out["meter"].map(treffer).fillna(False).astype(bool)
    if "n_befunde" in lab.columns:
        out["n_befunde"] = out["meter"].map(lab["n_befunde"])
    return out


def screening(quer: pd.DataFrame,
              schwelle: float = SCHWELLE_SPREIZUNG,
              quantil: float = 0.25,
              spalte_mod: str = "anteil_mod_dt",
              spalte_perf: str = "performance_median") -> dict:
    """Wie gut findet der Modulationsanteil die schwachen Stationen?

    Rückgabe mit ``genauigkeit`` (wie viele der ausgewählten Stationen
    wirklich schwach sind), ``trefferanteil`` (wie viele der schwachen
    Stationen gefunden werden) und ``basisrate`` zum Vergleich. Ohne die
    Basisrate daneben sieht jede Genauigkeit gut aus.
    """
    t = quer.dropna(subset=[spalte_mod, spalte_perf])
    grenze = float(t[spalte_perf].quantile(quantil))
    gewaehlt = t[spalte_mod] > schwelle
    schwach = t[spalte_perf] <= grenze
    tp = int((gewaehlt & schwach).sum())
    fp = int((gewaehlt & ~schwach).sum())
    fn = int((~gewaehlt & schwach).sum())
    return {
        "grenze": grenze,
        "n": int(len(t)),
        "gewaehlt": tp + fp,
        "schwach": tp + fn,
        "treffer": tp,
        "genauigkeit": tp / (tp + fp) if (tp + fp) else np.nan,
        "trefferanteil": tp / (tp + fn) if (tp + fn) else np.nan,
        "basisrate": float(schwach.mean()),
    }
