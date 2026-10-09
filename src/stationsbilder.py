"""
Drei Stationsbilder als Ergänzung zum Ternärdiagramm.

Schwächen des Ternärdiagramms aus `ternaer.py`:
- P = c · V · ΔT ist ein Produkt, die Normierung auf Summe 1 ist ein
  Kunstgriff
- das Niveau (kW, l/h) geht verloren
- dieselbe physikalische Änderung verschiebt einen Punkt je nach
  Ausgangslage in eine andere Richtung

Kennlinie
---------
- Volumenstrom gegen Leistung, beide Achsen logarithmisch
- die Steigung der Ausgleichsgeraden ist identisch mit `anteil_mod_flow`
  aus der Modulationszerlegung
- Isolinien konstanter Spreizung sind Geraden mit Steigung 1
- R² zeigt, wie fest eine Station auf ihrer Kennlinie sitzt

Carpet
------
- Heatmap über Kalendertag und Tagesstunde, eingefärbt nach Rücklauf und
  nach Durchfluss
- zeigt Stillstand (weiße Fläche), Zeitprogramme, Nachtabsenkung,
  Zirkulation im Sommer und Regimewechsel nach einer Reparatur

Dauerlinie
----------
- sortierte Werte gegen den Zeitanteil, je Saison und je Begehungsfenster
- beantwortet: wie viele Stunden liegt der Rücklauf über einer Schwelle

Farbe
-----
Durchgehend die Rücklauftemperatur. Die Performance wäre auf
Stundenebene nur eine Umrechnung der Spreizung.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import performance as pf
from . import season as sn
from . import ternaer as tn

KWH_PRO_M3_K = pf.KWH_PRO_M3_K

BEGEHUNGSGRUPPEN = tn.BEGEHUNGSGRUPPEN
SAISONGRUPPEN = tn.SAISONGRUPPEN

#Isolinien konstanter Spreizung im Kennlinienbild
ISO_SPREIZUNG_K = (10.0, 20.0, 30.0, 40.0, 50.0)

#Schwelle, ab der ein Ruecklauf als zu warm gilt. Offen gesetzt, die
#Begruendung muss aus der Netzfahrweise kommen und nicht aus den Daten.
RUECKLAUF_SCHWELLE_C = 50.0

#Stundenfenster fuer die Nachtabsenkung. Nacht bewusst ohne die Stunden
#um Mitternacht, damit ein spaetes Duschprogramm nicht hineinfaellt.
NACHT_STUNDEN = (1, 2, 3, 4, 5)
TAG_STUNDEN = (9, 10, 11, 12, 13, 14, 15, 16, 17)

#Mindestpunktzahl fuer einen Kennlinienfit. Unter 30 Punkten ist die
#Steigung nicht belastbar, dieselbe Grenze wie in ternaer.kennzahlen.
MIN_PUNKTE = 30

DAUERLINIEN_QUANTILE = (0.10, 0.50, 0.90)


def _ruecklauf_stunde(df: pd.DataFrame, zeiten) -> np.ndarray:
    """Rücklauf zu den Zeitstempeln einer Punkttabelle."""
    if "rt" not in df.columns or len(zeiten) == 0:
        return np.full(len(zeiten), np.nan)
    reihe = pd.to_numeric(df["rt"], errors="coerce")
    reihe = reihe[~reihe.index.duplicated(keep="last")]
    return reihe.reindex(pd.DatetimeIndex(zeiten)).to_numpy(dtype=float)


def _ruecklauf_tag(df: pd.DataFrame, daten) -> np.ndarray:
    """Tagesmittel des Rücklaufs unter Last zu den Tagen einer Tabelle."""
    if len(daten) == 0:
        return np.full(len(daten), np.nan)
    tab = pf.tagesdifferenzen(df)
    if len(tab) == 0 or "rt_mean_loaded" not in tab.columns:
        return np.full(len(daten), np.nan)
    reihe = pd.Series(tab["rt_mean_loaded"].to_numpy(dtype=float),
                      index=pd.DatetimeIndex(tab["datum"]))
    reihe = reihe[~reihe.index.duplicated(keep="last")]
    return reihe.reindex(pd.DatetimeIndex(daten)).to_numpy(dtype=float)


def punkttabelle(df: pd.DataFrame,
                 meter: int,
                 aufloesung: str = "stunde",
                 begehungsdatum=None,
                 puffer_tage: int = tn.PUFFER_TAGE) -> pd.DataFrame:
    """Punkttabelle einer Station mit Rücklauf als zusätzlicher Spalte.

    Setzt auf `ternaer.stationstabelle` auf, damit Filter, Gruppen und
    Tagesaggregation identisch sind und die Bilder derselben Station
    zwischen den Darstellungen vergleichbar bleiben. Ergänzt wird
    ``rt_c``: auf Stundenebene der gemessene Rücklauf, auf Tagesebene
    sein Mittel über die Laststunden.
    """
    tab = tn.stationstabelle(df, meter, aufloesung=aufloesung,
                             begehungsdatum=begehungsdatum,
                             puffer_tage=puffer_tage)
    if len(tab) == 0:
        tab = tab.copy()
        tab["rt_c"] = pd.Series(dtype=float)
        return tab

    if aufloesung == "stunde":
        tab["rt_c"] = _ruecklauf_stunde(df, tab["zeit"])
    else:
        tab["rt_c"] = _ruecklauf_tag(df, tab["datum"])
    return tab


def kennlinienfit(tab: pd.DataFrame, min_punkte: int = MIN_PUNKTE) -> dict:
    """Ausgleichsgerade log(Volumenstrom) über log(Leistung).

    Rückgabe mit ``steigung``, ``achsenabschnitt``, ``r2``,
    ``residuum_sd``, ``dt_median_k`` und ``n``. Die Steigung ist
    dieselbe Zahl wie ``anteil_mod_flow`` aus
    `ternaer.modulationszerlegung`; das Residuenstreumaß ist neu und
    misst, wie fest die Station auf ihrer Kennlinie sitzt.

    Die Steigung liest sich direkt: 1 heißt reine Durchflussmodulation
    bei konstanter Spreizung, 0 heißt konstanter Volumenstrom und reine
    Spreizungsmodulation.
    """
    leer = {"steigung": np.nan, "achsenabschnitt": np.nan, "r2": np.nan,
            "residuum_sd": np.nan, "dt_median_k": np.nan, "n": 0}
    if len(tab) == 0:
        return leer
    m = ((tab["power_kw"] > 0) & (tab["flow_lh"] > 0) & (tab["dt_k"] > 0))
    teil = tab[m.fillna(False)]
    if len(teil) < int(min_punkte):
        leer["n"] = int(len(teil))
        return leer

    lp = np.log(teil["power_kw"].to_numpy(dtype=float))
    lf = np.log(teil["flow_lh"].to_numpy(dtype=float))
    var_p = float(np.var(lp))
    if not np.isfinite(var_p) or var_p <= 1e-12:
        leer["n"] = int(len(teil))
        return leer

    steigung = float(np.mean((lp - lp.mean()) * (lf - lf.mean())) / var_p)
    achsenabschnitt = float(lf.mean() - steigung * lp.mean())
    residuen = lf - (achsenabschnitt + steigung * lp)
    var_f = float(np.var(lf))
    r2 = float(1.0 - np.var(residuen) / var_f) if var_f > 1e-12 else np.nan
    return {"steigung": steigung, "achsenabschnitt": achsenabschnitt,
            "r2": r2, "residuum_sd": float(np.std(residuen)),
            "dt_median_k": float(teil["dt_k"].median()),
            "n": int(len(teil))}


def kennlinienkennzahlen(tab: pd.DataFrame,
                         gruppenspalte: str,
                         gruppen: Sequence[str],
                         meter: Optional[int] = None,
                         min_punkte: int = MIN_PUNKTE) -> pd.DataFrame:
    """Eine Zeile je Gruppe mit Kennlinienparametern und Niveau.

    Im Unterschied zu `ternaer.kennzahlen` stehen hier die absoluten
    Mediane von Leistung und Durchfluss mit in der Tabelle. Das ist
    genau die Information, die die Normierung des Ternärdiagramms
    verwirft.
    """
    rows = []
    for gruppe in gruppen:
        teil = tab[tab[gruppenspalte].astype("object") == gruppe] \
            if gruppenspalte in tab.columns else tab.iloc[0:0]
        zeile = {"meter": meter, "gruppe": gruppe, "n": int(len(teil))}
        fit = kennlinienfit(teil, min_punkte=min_punkte)
        zeile.update({k: v for k, v in fit.items() if k != "n"})
        for spalte, name in (("power_kw", "power_median_kw"),
                             ("flow_lh", "flow_median_lh"),
                             ("rt_c", "rt_median_c"),
                             ("performance", "performance_median")):
            werte = pd.to_numeric(teil[spalte], errors="coerce") \
                if spalte in teil.columns else pd.Series(dtype=float)
            zeile[name] = float(werte.median()) if werte.notna().any() \
                else np.nan
        rows.append(zeile)
    return pd.DataFrame(rows)


def _kurzzahl(wert, _pos=None) -> str:
    """Achsenbeschriftung als Klartextzahl statt in Zehnerpotenzen."""
    if wert <= 0:
        return ""
    if wert >= 100:
        return f"{wert:.0f}"
    if wert >= 1:
        return f"{wert:g}"
    return f"{wert:.2f}".rstrip("0").rstrip(".")


def zeichne_kennlinie(ax, teil: pd.DataFrame, titel: str,
                      vmin: float, vmax: float,
                      grenzen: Optional[Sequence[float]] = None,
                      cmap: str = "coolwarm",
                      punktgroesse: float = 2.0,
                      min_punkte: int = MIN_PUNKTE):
    """Punktwolke einer Gruppe als log-log-Kennlinie mit Ausgleichsgerade."""
    import matplotlib.ticker as mticker

    teil = teil.dropna(subset=["power_kw", "flow_lh"])
    teil = teil[(teil["power_kw"] > 0) & (teil["flow_lh"] > 0)]
    ax.set_xscale("log")
    ax.set_yscale("log")
    #auf schmalen Wertebereichen beschriftet matplotlib auch die
    #Zwischenticks, die Labels laufen dann ineinander
    for achse in (ax.xaxis, ax.yaxis):
        achse.set_major_locator(mticker.LogLocator(base=10.0,
                                                   subs=(1.0, 2.0, 5.0),
                                                   numticks=12))
        achse.set_major_formatter(mticker.FuncFormatter(_kurzzahl))
        achse.set_minor_formatter(mticker.NullFormatter())
    ax.set_xlabel("Leistung in kW", fontsize=8)
    ax.set_ylabel("Volumenstrom in l/h", fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, which="major", color="0.9", lw=0.5)

    if grenzen is None or not np.all(np.isfinite(grenzen)):
        if len(teil) == 0:
            ax.set_title(f"{titel}\nkeine Daten", fontsize=8)
            return None
        grenzen = (float(teil["power_kw"].min()), float(teil["power_kw"].max()),
                   float(teil["flow_lh"].min()), float(teil["flow_lh"].max()))
    x0, x1, y0, y1 = [float(g) for g in grenzen]
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    #Isolinien konstanter Spreizung: V = P / (c * dT), im log-log eine
    #Gerade der Steigung 1
    p_linie = np.array([x0, x1], dtype=float)
    for dt in ISO_SPREIZUNG_K:
        v = p_linie * 1000.0 / (KWH_PRO_M3_K * dt)
        ax.plot(p_linie, v, color="0.75", lw=0.5, ls=":", zorder=0)
        if y0 <= v[1] <= y1:
            ax.annotate(f"{dt:.0f} K", xy=(p_linie[1], v[1]),
                        xytext=(-2, 2), textcoords="offset points",
                        fontsize=5.5, color="0.5", ha="right", va="bottom")

    if len(teil) == 0:
        ax.set_title(f"{titel}\nkeine Daten", fontsize=8)
        return None

    bild = ax.scatter(teil["power_kw"], teil["flow_lh"], c=teil["rt_c"],
                      cmap=cmap, vmin=vmin, vmax=vmax, s=punktgroesse,
                      linewidths=0, alpha=0.5, zorder=2, rasterized=True)

    fit = kennlinienfit(teil, min_punkte=min_punkte)
    if np.isfinite(fit["steigung"]):
        xx = np.geomspace(max(x0, 1e-6), x1, 50)
        yy = np.exp(fit["achsenabschnitt"] + fit["steigung"] * np.log(xx))
        ax.plot(xx, yy, color="black", lw=1.1, zorder=3)
        kopf = (f"{titel}\nn = {len(teil)}, Steigung {fit['steigung']:.2f}, "
                f"r² {fit['r2']:.2f}")
    else:
        kopf = f"{titel}\nn = {len(teil)}, Steigung nicht belastbar"
    ax.set_title(kopf, fontsize=8)
    return bild


def _farbgrenzen(tab: pd.DataFrame, spalte: str = "rt_c",
                 unten: float = 0.05, oben: float = 0.95):
    werte = pd.to_numeric(tab.get(spalte), errors="coerce") \
        if spalte in tab.columns else pd.Series(dtype=float)
    werte = werte.dropna()
    if len(werte) == 0:
        return 20.0, 70.0
    vmin = float(werte.quantile(unten))
    vmax = float(werte.quantile(oben))
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return 20.0, 70.0
    return vmin, vmax


def _achsengrenzen(tab: pd.DataFrame, rand: float = 1.15):
    teil = tab[(tab["power_kw"] > 0) & (tab["flow_lh"] > 0)]
    if len(teil) == 0:
        return None
    x0 = float(teil["power_kw"].quantile(0.001)) / rand
    x1 = float(teil["power_kw"].quantile(0.999)) * rand
    y0 = float(teil["flow_lh"].quantile(0.001)) / rand
    y1 = float(teil["flow_lh"].quantile(0.999)) * rand
    if not np.all(np.isfinite([x0, x1, y0, y1])) or x1 <= x0 or y1 <= y0:
        return None
    return (x0, x1, y0, y1)


def _zeilen(tab: pd.DataFrame):
    zeilen = []
    if "gruppe_begehung" in tab.columns and tab["gruppe_begehung"].notna().any():
        zeilen.append(("gruppe_begehung", BEGEHUNGSGRUPPEN, "Begehung"))
    if "gruppe_saison" in tab.columns:
        zeilen.append(("gruppe_saison", SAISONGRUPPEN, "Saison"))
    return zeilen


def kennliniengrafik(tab: pd.DataFrame,
                     meter: int,
                     aufloesung: str = "Stundenwerte",
                     cmap: str = "coolwarm",
                     punktgroesse: float = 2.0):
    """Ein Bild je Station: Begehungszeile und Saisonzeile als Kennlinien.

    Alle Panels teilen Achsengrenzen und Farbskala, damit die
    Verschiebung zwischen zwei Zeitabschnitten ablesbar bleibt und nicht
    von der Skalierung weggerechnet wird.
    """
    import matplotlib.pyplot as plt

    zeilen = _zeilen(tab)
    if not zeilen:
        raise ValueError("weder Begehungs- noch Saisongruppe vorhanden")
    vmin, vmax = _farbgrenzen(tab)
    grenzen = _achsengrenzen(tab)

    fig, axes = plt.subplots(len(zeilen), 3,
                             figsize=(11.5, 3.7 * len(zeilen)),
                             squeeze=False)
    bild = None
    for i, (spalte, gruppen, label) in enumerate(zeilen):
        for j, gruppe in enumerate(gruppen):
            teil = tab[tab[spalte].astype("object") == gruppe]
            b = zeichne_kennlinie(axes[i][j], teil, f"{label}: {gruppe}",
                                  vmin, vmax, grenzen=grenzen, cmap=cmap,
                                  punktgroesse=punktgroesse)
            bild = b if b is not None else bild

    fig.suptitle(f"Zähler {meter} – Kennlinie Volumenstrom über Leistung "
                 f"({aufloesung})", fontsize=11)
    fig.tight_layout(rect=(0.0, 0.0, 0.92, 0.95))
    if bild is not None:
        cax = fig.add_axes([0.94, 0.12, 0.016, 0.74])
        cb = fig.colorbar(bild, cax=cax)
        cb.set_label("Rücklauf in °C", fontsize=8)
        cb.ax.tick_params(labelsize=7)
    return fig


def carpetmatrix(df: pd.DataFrame, kanal: str = "rt",
                 log: bool = False) -> pd.DataFrame:
    """Matrix Tagesstunde × Kalendertag für einen Messkanal.

    Zeilen sind die Stunden 0 bis 23, Spalten alle Kalendertage zwischen
    erstem und letztem Messwert, auch die ohne Daten. Fehlende Stunden
    bleiben NaN und damit im Bild weiß - der Stillstand ist hier
    Information und kein Filterfall.
    """
    if kanal not in df.columns or len(df) == 0:
        return pd.DataFrame(index=range(24))
    reihe = pd.to_numeric(df[kanal], errors="coerce")
    idx = pd.DatetimeIndex(df.index)
    werte = reihe.to_numpy(dtype=float)
    if log:
        with np.errstate(divide="ignore", invalid="ignore"):
            werte = np.where(werte > 0, np.log10(np.where(werte > 0, werte,
                                                          np.nan)), np.nan)

    tab = pd.DataFrame({"datum": idx.normalize(), "stunde": idx.hour,
                        "wert": werte})
    tab = tab.dropna(subset=["wert"])
    if len(tab) == 0:
        return pd.DataFrame(index=range(24))
    gitter = tab.pivot_table(index="stunde", columns="datum", values="wert",
                             aggfunc="mean")
    alle_tage = pd.date_range(idx.normalize().min(), idx.normalize().max(),
                              freq="D")
    return gitter.reindex(index=range(24), columns=alle_tage)


def carpetkennzahlen(df: pd.DataFrame,
                     meter: Optional[int] = None,
                     ruecklauf_schwelle: float = RUECKLAUF_SCHWELLE_C) -> dict:
    """Kennzahlen, die aus dem Tag-Stunde-Raster folgen.

    ``nachtabsenkung_k`` ist der Medianunterschied des Rücklaufs
    zwischen Tag- und Nachtstunden im Kernwinter; ein Wert nahe null
    heißt, dass die Station rund um die Uhr dieselbe Temperatur fährt.
    ``sommer_nacht_anteil`` ist der Anteil der Sommernächte mit
    Durchfluss und damit ein Hinweis auf Zirkulations- oder
    Speicherverluste. ``stillstand_anteil`` zählt die Stunden ohne
    Durchfluss über die gesamte Historie.
    """
    leer = {"meter": meter, "nachtabsenkung_k": np.nan,
            "sommer_nacht_anteil": np.nan, "stillstand_anteil": np.nan,
            "rt_ueber_schwelle_anteil": np.nan, "n_stunden": 0}
    if len(df) == 0:
        return leer

    idx = pd.DatetimeIndex(df.index)
    tab = pd.DataFrame({
        "stunde": idx.hour,
        "monat": idx.month,
        "rt": pd.to_numeric(df.get("rt"), errors="coerce").to_numpy(
            dtype=float) if "rt" in df.columns else np.nan,
        "flow": pd.to_numeric(df.get("flow"), errors="coerce").to_numpy(
            dtype=float) if "flow" in df.columns else np.nan,
    })
    tab["segment"] = [sn.season_of_month(int(m)) for m in tab["monat"]]

    winter = tab[tab["segment"] == sn.KERNWINTER]
    nacht = winter[winter["stunde"].isin(NACHT_STUNDEN)]["rt"]
    tagsueber = winter[winter["stunde"].isin(TAG_STUNDEN)]["rt"]
    absenkung = (float(tagsueber.median() - nacht.median())
                 if nacht.notna().any() and tagsueber.notna().any() else np.nan)

    sommernacht = tab[(tab["segment"] == sn.SOMMER)
                      & (tab["stunde"].isin(NACHT_STUNDEN))]["flow"]
    sommer_anteil = (float((sommernacht > 0).mean())
                     if sommernacht.notna().any() else np.nan)

    flow = tab["flow"]
    stillstand = float((flow <= 0).mean()) if flow.notna().any() else np.nan
    rt = tab["rt"].dropna()
    ueber = (float((rt > float(ruecklauf_schwelle)).mean())
             if len(rt) else np.nan)

    return {"meter": meter, "nachtabsenkung_k": absenkung,
            "sommer_nacht_anteil": sommer_anteil,
            "stillstand_anteil": stillstand,
            "rt_ueber_schwelle_anteil": ueber, "n_stunden": int(len(tab))}


def carpetgrafik(df: pd.DataFrame,
                 meter: int,
                 begehungsdatum=None,
                 cmap_rt: str = "coolwarm",
                 cmap_flow: str = "viridis"):
    """Zwei Heatmaps je Station: Rücklauf und Durchfluss über Tag und Stunde.

    Der Durchfluss wird logarithmisch eingefärbt, weil zwischen
    Zirkulationsdurchfluss und Volllast zwei Größenordnungen liegen.
    Ein eingetragenes Begehungsdatum erscheint als senkrechte Linie.
    """
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    kanaele = [("rt", "Rücklauf in °C", cmap_rt, False),
               ("flow", "Volumenstrom in l/h (log)", cmap_flow, True)]
    fig, axes = plt.subplots(len(kanaele), 1, figsize=(12.0, 6.2),
                             sharex=True, squeeze=False)
    for i, (kanal, label, cmap, log) in enumerate(kanaele):
        ax = axes[i][0]
        gitter = carpetmatrix(df, kanal=kanal, log=log)
        ax.set_ylabel("Tagesstunde", fontsize=8)
        ax.set_yticks([0, 6, 12, 18, 24])
        ax.tick_params(labelsize=7)
        if gitter.shape[1] == 0:
            ax.set_title(f"{label} – keine Daten", fontsize=9)
            continue

        werte = gitter.to_numpy(dtype=float)
        endlich = werte[np.isfinite(werte)]
        if len(endlich) == 0:
            ax.set_title(f"{label} – keine Daten", fontsize=9)
            continue
        vmin = float(np.quantile(endlich, 0.02))
        vmax = float(np.quantile(endlich, 0.98))
        if vmax <= vmin:
            vmin, vmax = float(endlich.min()), float(endlich.max()) + 1e-6

        x0 = mdates.date2num(gitter.columns[0].to_pydatetime())
        x1 = mdates.date2num(gitter.columns[-1].to_pydatetime())
        bild = ax.imshow(werte, aspect="auto", origin="lower",
                         extent=(x0, x1, 0, 24), cmap=cmap,
                         vmin=vmin, vmax=vmax, interpolation="nearest")
        ax.xaxis_date()
        ax.set_title(label, fontsize=9)
        if begehungsdatum is not None and not (
                isinstance(begehungsdatum, float) and np.isnan(begehungsdatum)):
            ax.axvline(mdates.date2num(
                pd.Timestamp(begehungsdatum).to_pydatetime()),
                color="black", lw=1.0, ls="--")
        cb = fig.colorbar(bild, ax=ax, pad=0.01, fraction=0.025)
        cb.ax.tick_params(labelsize=7)
        if log:
            cb.set_label("log10", fontsize=7)

    axes[-1][0].tick_params(axis="x", labelsize=7)
    fig.suptitle(f"Zähler {meter} – Betriebsbild über Tag und Stunde",
                 fontsize=11)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    return fig


def dauerlinie(werte) -> tuple:
    """Zeitanteil und absteigend sortierte Werte einer Reihe.

    Rückgabe ist das Paar aus Anteilsachse in Prozent und sortierten
    Werten. Der Punkt bei 10 Prozent liest sich als „an 10 Prozent der
    Zeit liegt der Wert darüber".
    """
    reihe = pd.to_numeric(pd.Series(werte), errors="coerce").dropna()
    if len(reihe) == 0:
        return np.array([]), np.array([])
    sortiert = np.sort(reihe.to_numpy(dtype=float))[::-1]
    anteil = (np.arange(1, len(sortiert) + 1) / len(sortiert)) * 100.0
    return anteil, sortiert


def dauerlinienkennzahlen(tab: pd.DataFrame,
                          gruppenspalte: str,
                          gruppen: Sequence[str],
                          meter: Optional[int] = None,
                          spalte: str = "rt_c",
                          schwelle: float = RUECKLAUF_SCHWELLE_C
                          ) -> pd.DataFrame:
    """Dauerlinienpunkte und Überschreitungsanteil je Gruppe.

    ``p10`` ist der Wert, der an 10 Prozent der Zeit überschritten wird,
    ``p90`` entsprechend an 90 Prozent. Die Spanne zwischen beiden misst,
    wie weit eine Station ihren Betriebspunkt verschiebt.
    """
    rows = []
    for gruppe in gruppen:
        teil = tab[tab[gruppenspalte].astype("object") == gruppe] \
            if gruppenspalte in tab.columns else tab.iloc[0:0]
        werte = pd.to_numeric(teil.get(spalte), errors="coerce").dropna() \
            if spalte in teil.columns else pd.Series(dtype=float)
        zeile = {"meter": meter, "gruppe": gruppe, "groesse": spalte,
                 "n": int(len(werte))}
        for q in DAUERLINIEN_QUANTILE:
            name = f"p{int(q * 100):02d}"
            zeile[name] = (float(werte.quantile(1.0 - q)) if len(werte)
                           else np.nan)
        zeile["spanne_p10_p90"] = (zeile["p10"] - zeile["p90"]
                                   if len(werte) else np.nan)
        zeile["ueber_schwelle_anteil"] = (float((werte > float(schwelle)).mean())
                                          if len(werte) else np.nan)
        rows.append(zeile)
    return pd.DataFrame(rows)


def zeichne_dauerlinie(ax, tab: pd.DataFrame, gruppenspalte: str,
                       gruppen: Sequence[str], spalte: str, titel: str,
                       achse: str, schwelle: Optional[float] = None) -> bool:
    """Dauerlinien aller Gruppen einer Station in eine Achse zeichnen."""
    getroffen = False
    for gruppe in gruppen:
        teil = tab[tab[gruppenspalte].astype("object") == gruppe] \
            if gruppenspalte in tab.columns else tab.iloc[0:0]
        werte = teil.get(spalte) if spalte in teil.columns \
            else pd.Series(dtype=float)
        anteil, sortiert = dauerlinie(werte)
        if len(anteil) == 0:
            continue
        ax.plot(anteil, sortiert, lw=1.2,
                label=f"{gruppe} (n = {len(sortiert)})")
        getroffen = True
    ax.set_xlim(0, 100)
    ax.set_xlabel("Anteil der Zeit in Prozent", fontsize=8)
    ax.set_ylabel(achse, fontsize=8)
    ax.tick_params(labelsize=7)
    ax.grid(True, color="0.9", lw=0.5)
    if schwelle is not None:
        ax.axhline(float(schwelle), color="0.4", lw=0.8, ls="--")
    ax.set_title(titel, fontsize=9)
    if getroffen:
        ax.legend(fontsize=7, frameon=False)
    else:
        ax.set_title(f"{titel}\nkeine Daten", fontsize=9)
    return getroffen


def dauerliniengrafik(tab_stunde: pd.DataFrame,
                      tab_tag: pd.DataFrame,
                      meter: int,
                      schwelle: float = RUECKLAUF_SCHWELLE_C):
    """Vier Dauerlinien je Station: Rücklauf und Performance, beide Schnitte.

    Links steht der Rücklauf auf Stundenbasis, weil dort die
    Überschreitungsstunden stehen, rechts die Performance auf
    Tagesbasis, weil sie nur dort aus den Zählerständen kommt.
    """
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.0), squeeze=False)
    schnitte = [("gruppe_saison", SAISONGRUPPEN, "Saison"),
                ("gruppe_begehung", BEGEHUNGSGRUPPEN, "Begehung")]
    for i, (spalte, gruppen, label) in enumerate(schnitte):
        zeichne_dauerlinie(axes[i][0], tab_stunde, spalte, gruppen, "rt_c",
                           f"Rücklauf nach {label} (Stundenwerte)",
                           "Rücklauf in °C", schwelle=schwelle)
        zeichne_dauerlinie(axes[i][1], tab_tag, spalte, gruppen,
                           "performance",
                           f"Performance nach {label} (Tageswerte)",
                           "Performance in kWh/m³")
    fig.suptitle(f"Zähler {meter} – Dauerlinien", fontsize=11)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    return fig


def exportiere(serien: Mapping[int, pd.DataFrame],
               out_dir: Path,
               begehungsdatum: Optional[Mapping[int, object]] = None,
               bilder: Sequence[str] = ("kennlinie", "carpet", "dauerlinie"),
               aufloesungen: Sequence[str] = ("stunde", "tag"),
               puffer_tage: int = tn.PUFFER_TAGE,
               schwelle: float = RUECKLAUF_SCHWELLE_C,
               dpi: int = 110,
               fortschritt: bool = False) -> Dict[str, pd.DataFrame]:
    """Alle drei Darstellungen je Station schreiben und Kennzahlen sammeln.

    Ablage unter ``out_dir/kennlinie/<aufloesung>/<zaehler>.png``,
    ``out_dir/carpet/<zaehler>.png`` und
    ``out_dir/dauerlinie/<zaehler>.png``. Rückgabe sind drei Tabellen
    unter den Schlüsseln ``kennlinie``, ``carpet`` und ``dauerlinie`` -
    die Bilder sind die Kontrolle, ausgewertet wird über die Tabellen.

    Stationen ohne verwertbare Punkte erscheinen mit n = 0 in den
    Tabellen und ohne Bild, damit der Ausfall sichtbar bleibt.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    datum = dict(begehungsdatum or {})
    zeilen_kennlinie, zeilen_carpet, zeilen_dauer = [], [], []

    for n, (meter, df) in enumerate(sorted(serien.items()), start=1):
        tabellen = {}
        for aufl in aufloesungen:
            tabellen[aufl] = punkttabelle(df, meter, aufloesung=aufl,
                                          begehungsdatum=datum.get(meter),
                                          puffer_tage=puffer_tage)

        if "kennlinie" in bilder:
            for aufl, tab in tabellen.items():
                for spalte, gruppen, schnitt in (
                        ("gruppe_begehung", BEGEHUNGSGRUPPEN, "begehung"),
                        ("gruppe_saison", SAISONGRUPPEN, "saison")):
                    teil = tab if len(tab) and spalte in tab.columns \
                        else pd.DataFrame(columns=list(tab.columns) + [spalte])
                    k = kennlinienkennzahlen(teil, spalte, gruppen,
                                             meter=meter)
                    k.insert(1, "aufloesung", aufl)
                    k.insert(2, "schnitt", schnitt)
                    zeilen_kennlinie.append(k)
                if len(tab) == 0:
                    continue
                ziel = out_dir / "kennlinie" / aufl
                ziel.mkdir(parents=True, exist_ok=True)
                fig = kennliniengrafik(
                    tab, meter,
                    aufloesung="Stundenwerte" if aufl == "stunde"
                    else "Tageswerte")
                fig.savefig(ziel / f"{meter}.png", dpi=dpi,
                            bbox_inches="tight")
                plt.close(fig)

        if "carpet" in bilder:
            zeilen_carpet.append(carpetkennzahlen(df, meter=meter))
            if len(df):
                ziel = out_dir / "carpet"
                ziel.mkdir(parents=True, exist_ok=True)
                fig = carpetgrafik(df, meter,
                                   begehungsdatum=datum.get(meter))
                fig.savefig(ziel / f"{meter}.png", dpi=dpi,
                            bbox_inches="tight")
                plt.close(fig)

        if "dauerlinie" in bilder:
            tab_s = tabellen.get("stunde", pd.DataFrame())
            tab_t = tabellen.get("tag", pd.DataFrame())
            for spalte, gruppen, schnitt in (
                    ("gruppe_begehung", BEGEHUNGSGRUPPEN, "begehung"),
                    ("gruppe_saison", SAISONGRUPPEN, "saison")):
                for quelle, groesse in ((tab_s, "rt_c"),
                                        (tab_t, "performance")):
                    teil = quelle if len(quelle) and spalte in quelle.columns \
                        else pd.DataFrame(columns=list(quelle.columns)
                                          + [spalte])
                    d = dauerlinienkennzahlen(teil, spalte, gruppen,
                                              meter=meter, spalte=groesse,
                                              schwelle=schwelle)
                    d.insert(1, "schnitt", schnitt)
                    zeilen_dauer.append(d)
            if len(tab_s) or len(tab_t):
                ziel = out_dir / "dauerlinie"
                ziel.mkdir(parents=True, exist_ok=True)
                fig = dauerliniengrafik(tab_s, tab_t, meter,
                                        schwelle=schwelle)
                fig.savefig(ziel / f"{meter}.png", dpi=dpi,
                            bbox_inches="tight")
                plt.close(fig)

        if fortschritt and n % 10 == 0:
            print(f"{n}/{len(serien)} Stationen", flush=True)

    def _sammle(teile):
        return (pd.concat(teile, ignore_index=True) if teile
                else pd.DataFrame())

    return {"kennlinie": _sammle(zeilen_kennlinie),
            "carpet": (pd.DataFrame(zeilen_carpet) if zeilen_carpet
                       else pd.DataFrame()),
            "dauerlinie": _sammle(zeilen_dauer)}
