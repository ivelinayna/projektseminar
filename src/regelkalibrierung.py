"""
Datengetriebene Nachkalibrierung der Regel-Baseline.

Die Regeln in `fault_detection.py` sind die aelteste Komponente des
Projekts. Ihre Schwellen stammen aus der Literatur und aus dem
synthetischen Generator, auf dem sie entworfen wurden. Auf den echten
Zaehlerdaten sind sie nachweislich falsch kalibriert: eine Regel feuert
bei fast allen Stationen, eine andere bei keiner. Beides ist derselbe
Fehler - eine Regel, die nicht trennt, liefert keine Information,
unabhaengig davon, in welche Richtung sie danebenliegt.

Die Konsequenz ist nicht, die Regeln wegzuwerfen. Ihre Fachlogik ist
weiterhin richtig: ein warmer Ruecklauf im Winter ist schlecht, ein
Sommerdurchfluss ohne Abnahme ist schlecht, eine fallende
Durchflussdecke deutet auf einen zusetzenden Filter. Falsch ist nur
die Zahl, ab der es schlecht heisst. Dieses Modul leitet diese Zahl aus
der Verteilung der echten Stationen ab.

Was das Verfahren kann und was nicht
------------------------------------
Eine Quantilschwelle setzt per Konstruktion einen festen Anteil der
Stationen auf auffaellig. Sie beantwortet die Frage "welche Stationen
sind die auffaelligsten" und nicht die Frage "ist diese Station in
Ordnung". Waere das ganze Netz gut eingestellt, wuerde das Verfahren
trotzdem den vorgesehenen Anteil melden. Die Schwellen sind damit eine
Priorisierungshilfe und keine Abnahmekriterien. Welcher Anteil fachlich
angemessen ist, ist eine Entscheidung des Teams und keine
Eigenschaft der Daten; `zielanteil` ist deshalb Parameter.

Lesart der Trefferquoten
------------------------
`trefferquoten` wertet jede Bedingung einzeln aus, auch die, die im
Regelwerk hinter einem `elif` steht. Die Summe der Treffer ist deshalb
groesser als die Zahl der Stationen mit einem Befund. Wer wissen will,
was am Ende als Label herauskommt, nimmt
`fault_detection.classify_dataframe`; wer wissen will, ob eine einzelne
Bedingung trennt, nimmt diese Tabelle.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional

import numpy as np
import pandas as pd

from . import fault_detection as fd

#Je Schwelle: das Feature, die Richtung der Bedingung und der
#Fehlername aus dem Regelwerk. "ueber" heisst, die Regel feuert
#oberhalb der Schwelle.
SPEZIFIKATION: Dict[str, dict] = {
    "rt_mean_winter": {
        "feature": "rt_mean_winter", "richtung": "ueber",
        "fehler": "excess_rt",
        "beschreibung": "Ruecklauf im Winter zu warm"},
    "rt_above_50_share_loaded": {
        "feature": "rt_above_50_share_loaded", "richtung": "ueber",
        "fehler": "excess_rt",
        "beschreibung": "Anteil Laststunden mit Ruecklauf ueber 50 Grad"},
    "summer_flow_baseline": {
        "feature": "summer_flow_baseline", "richtung": "ueber",
        "fehler": "continuous_flow",
        "beschreibung": "Mediandurchfluss im Sommer"},
    "summer_idle_flow_median": {
        "feature": "summer_idle_flow_median", "richtung": "ueber",
        "fehler": "continuous_flow",
        "beschreibung": "Durchfluss in lastfreien Sommerstunden"},
    "flow_ceiling_slope_per_month": {
        "feature": "flow_ceiling_slope_per_month", "richtung": "unter",
        "fehler": "fouled_filter",
        "beschreibung": "Trend der Durchflussdecke je Monat"},
    "dt_mean_loaded": {
        "feature": "dt_mean_loaded", "richtung": "unter",
        "fehler": "low_spreading",
        "beschreibung": "mittlere Spreizung unter Last"},
    "peak_load_share": {
        "feature": "peak_load_share", "richtung": "unter",
        "fehler": "oversized_contract",
        "beschreibung": "Spitzenlast gemessen am Anschlusswert"},
    "flow_short_cycle_power": {
        "feature": "flow_short_cycle_power", "richtung": "ueber",
        "fehler": "control_hysteresis",
        "beschreibung": "Anteil kurzperiodischer Schwankung im Durchfluss"},
}

#Anteil der Stationen, den eine Regel treffen soll. 0,15 ist eine
#Setzung fuer die Auswertung und keine aus den Daten abgeleitete Groesse.
ZIELANTEIL = 0.15

#Mindestzahl Stationen mit Wert, ab der eine Schwelle geschaetzt wird
MIN_STATIONEN = 20


def _bedingung(werte: pd.Series, schwelle: float, richtung: str) -> pd.Series:
    """Boolesche Maske der Regelbedingung, Fehlwerte zaehlen als kein Treffer."""
    x = pd.to_numeric(werte, errors="coerce")
    treffer = x > schwelle if richtung == "ueber" else x < schwelle
    return treffer.fillna(False)


def trefferquoten(features_df: pd.DataFrame,
                  schwellen: Optional[Mapping[str, float]] = None,
                  spezifikation: Mapping[str, dict] = SPEZIFIKATION
                  ) -> pd.DataFrame:
    """Wie viele Stationen jede einzelne Bedingung trifft.

    Rueckgabe je Schwelle: Fehlername, Beschreibung, benutzte Schwelle,
    Zahl der Stationen mit Wert, Zahl der Treffer und der Anteil. Eine
    Regel mit Anteil nahe 0 oder nahe 1 trennt nicht und wird genau so
    in der Tabelle sichtbar.
    """
    s = dict(fd.SCHWELLEN)
    if schwellen:
        s.update(schwellen)
    zeilen = []
    for name, spec in spezifikation.items():
        feature = spec["feature"]
        if feature not in features_df.columns:
            zeilen.append({"schwelle": name, "fehler": spec["fehler"],
                           "beschreibung": spec["beschreibung"],
                           "wert": s.get(name, np.nan), "n_stationen": 0,
                           "treffer": 0, "anteil": np.nan})
            continue
        werte = pd.to_numeric(features_df[feature], errors="coerce")
        maske = _bedingung(werte, s[name], spec["richtung"])
        n = int(werte.notna().sum())
        zeilen.append({
            "schwelle": name, "fehler": spec["fehler"],
            "beschreibung": spec["beschreibung"], "wert": float(s[name]),
            "n_stationen": n, "treffer": int(maske.sum()),
            "anteil": float(maske.sum()) / n if n else np.nan,
        })
    return pd.DataFrame(zeilen)


def kalibriere(features_df: pd.DataFrame,
               zielanteil: float = ZIELANTEIL,
               spezifikation: Mapping[str, dict] = SPEZIFIKATION,
               min_stationen: int = MIN_STATIONEN,
               alt: Optional[Mapping[str, float]] = None) -> tuple:
    """Schwellen aus den Quantilen der echten Verteilungen ableiten.

    Fuer eine Bedingung in Richtung ``ueber`` wird das
    ``1 - zielanteil``-Quantil genommen, in Richtung ``unter`` das
    ``zielanteil``-Quantil. Features mit weniger als `min_stationen`
    Werten behalten ihre alte Schwelle; der Grund steht in der
    Bilanztabelle, es faellt nichts still zurueck.

    Rueckgabe ist das neue Schwellen-Dictionary und eine Bilanz mit
    alter und neuer Schwelle je Regel.
    """
    alt = dict(fd.SCHWELLEN) if alt is None else dict(alt)
    neu = dict(alt)
    zeilen = []
    for name, spec in spezifikation.items():
        feature = spec["feature"]
        werte = (pd.to_numeric(features_df[feature], errors="coerce").dropna()
                 if feature in features_df.columns else pd.Series(dtype=float))
        zeile = {"schwelle": name, "fehler": spec["fehler"],
                 "richtung": spec["richtung"], "alt": alt.get(name, np.nan),
                 "n_stationen": int(len(werte)), "neu": alt.get(name, np.nan),
                 "uebernommen": False, "grund": ""}
        if len(werte) < int(min_stationen):
            zeile["grund"] = (f"weniger als {min_stationen} Stationen mit "
                              f"Wert, alte Schwelle behalten")
            zeilen.append(zeile)
            continue
        q = (1.0 - float(zielanteil) if spec["richtung"] == "ueber"
             else float(zielanteil))
        wert = float(werte.quantile(q))
        neu[name] = wert
        zeile["neu"] = wert
        zeile["uebernommen"] = True
        zeile["quantil"] = q
        zeilen.append(zeile)
    spalten = ["schwelle", "fehler", "richtung", "alt", "neu", "n_stationen",
               "uebernommen", "grund"]
    bilanz = pd.DataFrame(zeilen)
    bilanz = bilanz[[c for c in spalten if c in bilanz.columns]]
    return neu, bilanz


def vorher_nachher(features_df: pd.DataFrame,
                   neu: Mapping[str, float],
                   alt: Optional[Mapping[str, float]] = None,
                   spezifikation: Mapping[str, dict] = SPEZIFIKATION
                   ) -> pd.DataFrame:
    """Trefferquoten vor und nach der Kalibrierung nebeneinander."""
    a = trefferquoten(features_df, alt, spezifikation)
    b = trefferquoten(features_df, neu, spezifikation)
    out = a[["schwelle", "fehler", "beschreibung", "n_stationen"]].copy()
    out["schwelle_alt"] = a["wert"].to_numpy()
    out["treffer_alt"] = a["treffer"].to_numpy()
    out["anteil_alt"] = a["anteil"].to_numpy()
    out["schwelle_neu"] = b["wert"].to_numpy()
    out["treffer_neu"] = b["treffer"].to_numpy()
    out["anteil_neu"] = b["anteil"].to_numpy()
    return out


def labelverteilung(features_df: pd.DataFrame,
                    schwellen: Optional[Mapping[str, float]] = None
                    ) -> pd.Series:
    """Verteilung der vergebenen Fehlerlabels unter einem Schwellensatz.

    Das ist die Sicht des Regelwerks mit seiner `elif`-Logik: je Station
    genau ein Label. Sie beantwortet, was am Ende in einer Trefferliste
    stuende, und nicht, welche Bedingung dafuer verantwortlich war.
    """
    res = fd.classify_dataframe(features_df, schwellen)
    return res["predicted_fault"].value_counts()
