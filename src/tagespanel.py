"""
Panel auf Station mal Tag.

Die bisherigen Auswertungen arbeiten auf drei Ebenen: eine Zeile je
Station (`features.py`), eine Zeile je Betriebsstunde
(`clustervalidierung.py`) und zwei Fenster je Begehung
(`jahresvergleich.py`). Die Anomalieerkennung braucht eine vierte, die
zwischen Stunde und Station liegt. Ein Tag ist kurz genug, um eine
Veraenderung zeitlich zu verorten, und lang genug, um den Tagesgang
herauszumitteln - auf Stundenebene ist jede Nacht ein Ausreisser.

Das Panel fuehrt zusammen, was in den vorhandenen Modulen schon steckt,
und rechnet nichts doppelt:

    performance.tagesperformance   Energie und Volumen aus den
                                   kumulativen Kanaelen, mit der dort
                                   gepflegten Qualitaetslogik
    dynamik.tagesdynamik           Ableitungen des Ruecklaufs
    clustervalidierung             Stundencluster, hier als Zeitanteil
                                   je Betriebszustand und Tag
    weather / season               Aussentemperatur, Heizgradstunden,
                                   Saisonsegment

Eigene Rechnung sind nur die Tagesmittel der Momentankanaele
(`tagesbasis`) und die Umrechnung der Stundencluster in Zeitanteile
(`zustandsanteile`).

Gefiltert wird hier nichts. Das Panel enthaelt auch Tage mit wenigen
Messstunden und Tage im Stillstand; jede Zeile traegt ihre
Stundenzahlen mit, und die Detektoren in `anomalie.py` entscheiden
selbst, was sie davon benutzen. Ein stiller Dropout waere an dieser
Stelle besonders schaedlich, weil ein ausgefallener Tag selbst ein
Hinweis sein kann.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import dynamik as dyn
from . import performance as pf
from . import season as sn

LAST_SCHWELLE_KW = pf.LAST_SCHWELLE_KW

#Mindestzahl Messstunden, ab der ein Tag als ausreichend belegt gilt.
#Parameter, keine Konstante: fuer die Detektoren in anomalie.py ist er
#die wichtigste Stellschraube zwischen Fallzahl und Verlaesslichkeit.
MIN_STUNDEN_TAG = 20

#Spalten, die `tagesbasis` aus den Momentankanaelen bildet
BASIS_SPALTEN = ["rt_mean", "rt_median", "rt_p95", "vl_mean", "dt_mean",
                 "dt_mean_loaded", "flow_mean", "flow_median", "power_mean",
                 "power_max", "last_anteil", "n_stunden_basis"]


def tagesbasis(df: pd.DataFrame,
               last_schwelle_kw: float = LAST_SCHWELLE_KW) -> pd.DataFrame:
    """Tagesmittel und Tagesspitzen der Momentankanaele einer Zaehlerreihe.

    `df` erwartet das Schema von `features.features_for_meter`.
    `rt_mean` mittelt ueber alle Stunden, `dt_mean_loaded` nur ueber die
    Laststunden - beides steht nebeneinander, weil der Mittelwert ueber
    alle Stunden im Sommer von Stillstandsstunden dominiert wird und die
    Groesse unter Last dann auf wenigen Stunden steht.
    """
    if len(df) == 0:
        return pd.DataFrame(columns=["datum"] + BASIS_SPALTEN)
    w = df.sort_index()
    teil = pd.DataFrame({"datum": pd.DatetimeIndex(w.index).normalize()})
    for spalte in ("rt", "vl", "dt", "flow", "power"):
        teil[spalte] = (pd.to_numeric(w[spalte], errors="coerce").to_numpy()
                        if spalte in w.columns else np.nan)

    last = teil["power"] > float(last_schwelle_kw)
    teil["_last"] = last
    g = teil.groupby("datum", sort=True)
    out = pd.DataFrame({
        "rt_mean": g["rt"].mean(),
        "rt_median": g["rt"].median(),
        "rt_p95": g["rt"].quantile(0.95),
        "vl_mean": g["vl"].mean(),
        "dt_mean": g["dt"].mean(),
        "flow_mean": g["flow"].mean(),
        "flow_median": g["flow"].median(),
        "power_mean": g["power"].mean(),
        "power_max": g["power"].max(),
        "last_anteil": g["_last"].mean(),
        "n_stunden_basis": g["rt"].size(),
    })
    unter_last = teil[last]
    if len(unter_last):
        out["dt_mean_loaded"] = unter_last.groupby("datum")["dt"].mean()
    else:
        out["dt_mean_loaded"] = np.nan
    return out.reset_index()[["datum"] + BASIS_SPALTEN]


def zustandsanteile(stundencluster: pd.DataFrame,
                    cluster_spalte: str = "cluster",
                    meter_spalte: str = "Zählernummer",
                    zeit_spalte: str = "timestamp",
                    praefix: str = "anteil_c") -> pd.DataFrame:
    """Zeitanteil je Betriebszustand und Tag aus dem Stundenclustering.

    Eingabe ist das Stundenpanel aus `clustervalidierung.lade_stundenpanel`
    mit angehaengter Clusterspalte, also genau das Objekt, mit dem
    Notebook 09 arbeitet. Rueckgabe hat eine Zeile je Station und Tag mit
    einer Anteilsspalte je Cluster (Zeilensumme 1) und
    ``n_stunden_cluster``.

    Die Anteile sind bewusst auf die geclusterten Stunden normiert und
    nicht auf 24. Eine Stunde, die mangels vollstaendiger Messwerte gar
    nicht geclustert wurde, gehoert in keinen Zustand; sie steht in
    ``n_stunden_cluster`` und kann dort gefiltert werden.
    """
    for spalte in (cluster_spalte, meter_spalte, zeit_spalte):
        if spalte not in stundencluster.columns:
            raise KeyError(f"Spalte '{spalte}' fehlt - vorhanden: "
                           f"{list(stundencluster.columns)}")
    w = pd.DataFrame({
        "meter": stundencluster[meter_spalte].astype(int).to_numpy(),
        "datum": pd.DatetimeIndex(stundencluster[zeit_spalte]).normalize(),
        "cluster": stundencluster[cluster_spalte].to_numpy(),
    })
    zaehlung = (w.groupby(["meter", "datum", "cluster"]).size()
                .unstack("cluster", fill_value=0).sort_index(axis=1))
    gesamt = zaehlung.sum(axis=1)
    anteile = zaehlung.div(gesamt, axis=0)
    anteile.columns = [f"{praefix}{int(c)}" for c in anteile.columns]
    anteile["n_stunden_cluster"] = gesamt.astype(int)
    return anteile.reset_index()


def tagestemperatur(t_out: pd.DataFrame,
                    t_heiz: float = 15.0,
                    min_stunden: int = MIN_STUNDEN_TAG) -> pd.DataFrame:
    """Tagesmittel der Aussentemperatur und Heizgradstunden je Tag.

    Baut auf `performance.tagesmittel_temperatur` auf und ergaenzt die
    Tagessumme der Heizgradstunden aus `weather.heating_degree_hours`.
    Die Heizgradstunden eines Tages werden nur gebildet, wenn der Tag
    `min_stunden` Messwerte hat - sonst saehe ein halb belegter
    Wintertag mild aus.
    """
    from . import weather

    tages_t = pf.tagesmittel_temperatur(t_out, min_stunden=min_stunden)
    hdh = weather.heating_degree_hours(t_out, t_heiz=t_heiz)
    hilfs = pd.DataFrame({
        "datum": pd.DatetimeIndex(t_out["timestamp"]).normalize(),
        "hdh": hdh.to_numpy(),
    })
    g = hilfs.groupby("datum")["hdh"]
    summe = pd.DataFrame({"heizgradstunden": g.sum(min_count=1),
                          "n_stunden_hdh": g.count()}).reset_index()
    summe.loc[summe["n_stunden_hdh"] < int(min_stunden),
              "heizgradstunden"] = np.nan
    out = tages_t.merge(summe, on="datum", how="outer")
    return out.sort_values("datum").reset_index(drop=True)


def baue_tagespanel(serien: Mapping[int, pd.DataFrame],
                    stundencluster: Optional[pd.DataFrame] = None,
                    t_out: Optional[pd.DataFrame] = None,
                    t_heiz: float = 15.0,
                    min_stunden: int = MIN_STUNDEN_TAG,
                    mit_dynamik: bool = True,
                    zaehler: Optional[Sequence[int]] = None) -> pd.DataFrame:
    """Panel Station mal Tag aus allen Bausteinen.

    Rueckgabe hat ``meter`` und ``datum`` als Schluessel, dazu die
    Tagesbasis, die Energie- und Volumenkennzahlen aus
    `performance.tagesperformance`, die Dynamikkennzahlen, die
    Zustandsanteile aus dem Stundenclustering und den Witterungskontext.
    ``genug_stunden`` markiert Tage mit mindestens `min_stunden`
    Messstunden; gefiltert wird nicht.

    Fehlende Bausteine sind erlaubt: ohne `stundencluster` fehlen die
    Anteilsspalten, ohne `t_out` die Witterungsspalten. Die Detektoren
    pruefen selbst, was vorhanden ist.
    """
    auswahl = set(zaehler) if zaehler is not None else None
    frames = []
    for zid, df in sorted(serien.items()):
        if auswahl is not None and zid not in auswahl:
            continue
        if df is None or len(df) == 0:
            continue
        basis = tagesbasis(df)
        if len(basis) == 0:
            continue
        basis.insert(0, "meter", int(zid))
        if {"energy", "volume"}.issubset(df.columns):
            perf = pf.tagesperformance(df, min_stunden=min_stunden)
            spalten = ["datum", "energie_kwh", "volumen_m3", "n_stunden",
                       "performance", "spreizung_k", "rt_mean_loaded",
                       "gueltig"]
            basis = basis.merge(perf[spalten], on="datum", how="left")
            basis = basis.rename(columns={"gueltig": "performance_gueltig"})
        frames.append(basis)

    if not frames:
        return pd.DataFrame(columns=["meter", "datum"])
    panel = pd.concat(frames, ignore_index=True)

    if mit_dynamik:
        dynamiktab = dyn.dynamik_tabelle(serien, zaehler=zaehler)
        if len(dynamiktab):
            panel = panel.merge(dynamiktab, on=["meter", "datum"], how="left")

    if stundencluster is not None and len(stundencluster):
        anteile = zustandsanteile(stundencluster)
        panel = panel.merge(anteile, on=["meter", "datum"], how="left")

    if t_out is not None and len(t_out):
        wetter = tagestemperatur(t_out, t_heiz=t_heiz, min_stunden=min_stunden)
        panel = panel.merge(wetter[["datum", "t_out_tag", "heizgradstunden"]],
                            on="datum", how="left")

    panel = sn.add_season_segment(panel, timestamp_col="datum")
    panel["monat"] = pd.DatetimeIndex(panel["datum"]).month
    panel["genug_stunden"] = panel["n_stunden_basis"] >= int(min_stunden)
    vorne = ["meter", "datum", "season", "monat", "genug_stunden"]
    return panel[vorne + [c for c in panel.columns if c not in vorne]]


def panelbilanz(panel: pd.DataFrame) -> pd.DataFrame:
    """Wie viele Stationstage an welcher Bedingung haengen.

    Die Bedingungen ueberschneiden sich, die Zeilen addieren sich
    deshalb nicht auf die Gesamtzahl - dieselbe Lesart wie bei
    `performance.filterbilanz`.
    """
    n = len(panel)
    if n == 0:
        return pd.DataFrame(columns=["bedingung", "tage", "anteil"])
    zeilen = [("Stationstage gesamt", n),
              ("genug Messstunden", int(panel["genug_stunden"].sum()))]
    if "last_anteil" in panel.columns:
        zeilen.append(("Tag ohne jede Laststunde",
                       int((panel["last_anteil"] == 0).sum())))
    if "rt_d1_abs_mean" in panel.columns:
        zeilen.append(("Dynamik gerechnet",
                       int(panel["rt_d1_abs_mean"].notna().sum())))
    if "n_stunden_cluster" in panel.columns:
        zeilen.append(("Zustandsanteile vorhanden",
                       int(panel["n_stunden_cluster"].notna().sum())))
    if "t_out_tag" in panel.columns:
        zeilen.append(("Aussentemperatur vorhanden",
                       int(panel["t_out_tag"].notna().sum())))
    out = pd.DataFrame(zeilen, columns=["bedingung", "tage"])
    out["anteil"] = out["tage"] / n
    return out
