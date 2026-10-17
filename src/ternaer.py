"""
Ternärdiagramme je Station.

Vorlage ist die ÜZ-Folie „Analyse der Betriebsdaten ausgewählter HAST":
Punktwolke im Dreieck aus Leistung, Volumenstrom und Spreizung,
eingefärbt nach Performance.

Dieses Modul baut die Darstellung für jede Station, in zwei Schnitten:

    Begehung   vorher, Umbauphase (Fenster um den Begehungstag), nachher
    Saison     Winter (Dez–Feb), Übergang (Sep–Nov, Mär–Apr), Sommer

Jeweils auf Stunden- und auf Tagesebene. Die Stunde behält den Tagesgang
(Regelbewegung), der Tag zeigt den Betriebspunkt.

Normierung
----------
- jeder Kanal wird auf das 95. Perzentil derselben Station normiert und
  auf [0, 1] gekappt, danach auf Summe 1 gebracht
- normiert wird über die ganze Historie, damit die Panels einer Station
  vergleichbar bleiben
- das Diagramm sagt dadurch nichts über die Größe der Station, nur über
  das Regelverhalten

Modulationszerlegung
--------------------
Aus P = c · V · ΔT folgt log P = log V + log ΔT + const und damit

    cov(log P, log V) / var(log P) + cov(log P, log ΔT) / var(log P) = 1

- die Summanden sind `anteil_mod_flow` und `anteil_mod_dt`
- `anteil_mod_dt` nahe 1: Volumenstrom fast konstant, geregelt wird über
  die Spreizung
- `anteil_mod_flow` nahe 1: geregelt wird über den Volumenstrom
- Werte außerhalb von [0, 1]: die Kanäle laufen gegenläufig

Performance (Farbe)
-------------------
- Tagesebene: aus `performance.tagesperformance`, also aus den
  Zählerständen
- Stundenebene: momentane Spreizung mal 1,163 kWh/(m³·K), weil der
  Energiezähler stündlich zu grob auflöst. Die Farbe ist dort fast
  dasselbe wie die ΔT-Achse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import performance as pf
from . import season as sn

KWH_PRO_M3_K = pf.KWH_PRO_M3_K

#Spaltennamen der materialisierten Exporte aus load_timeseries
SPALTEN_MAP = {
    "Energy (kWh)": "energy",
    "Volume flow (l/h)": "flow",
    "Power (kW)": "power",
    "Temperature difference (°C)": "dt",
    "Flow temperature (°C)": "vl",
    "Return temperature (°C)": "rt",
    "Volume (m³)": "volume",
}

#Ecken des Dreiecks: Volumenstrom links unten, Spreizung rechts unten,
#Leistung oben - dieselbe Anordnung wie auf der ÜZ-Folie
ECKEN = {
    "flow": (0.0, 0.0),
    "dt": (1.0, 0.0),
    "power": (0.5, float(np.sqrt(3.0) / 2.0)),
}

ACHSENTITEL = {
    "flow": "Volumenstrom",
    "dt": "Spreizung",
    "power": "Leistung",
}

ANTEILSSPALTEN = ["anteil_flow", "anteil_dt", "anteil_power"]

#Referenzquantil der stationseigenen Normierung
REFERENZ_QUANTIL = 0.95

#Mindestvolumen je Stunde fuer die Zaehlervariante der Performance.
#0,05 m3 entspricht 50 l/h; darunter teilt man zwei Quantisierungsstufen
#durcheinander.
MIN_VOLUMEN_STUNDE_M3 = 0.05

#Fenster um den Begehungstag, das als Umbauphase gilt. Siehe NB 08:
#waehrend Einstellung und Reparatur herrschen Sonderzustaende.
PUFFER_TAGE = 7

GRUPPE_VORHER = "vorher"
GRUPPE_UMBAU = "umbauphase"
GRUPPE_NACHHER = "nachher"
BEGEHUNGSGRUPPEN = [GRUPPE_VORHER, GRUPPE_UMBAU, GRUPPE_NACHHER]

GRUPPE_WINTER = "winter"
GRUPPE_UEBERGANG = "uebergang"
GRUPPE_SOMMER = "sommer"
SAISONGRUPPEN = [GRUPPE_WINTER, GRUPPE_UEBERGANG, GRUPPE_SOMMER]

#Zusammenfassung der vier Segmente aus season.py auf die drei Panels
SEGMENT_AUF_GRUPPE = {
    sn.KERNWINTER: GRUPPE_WINTER,
    sn.UEBERGANG_SPAET: GRUPPE_UEBERGANG,
    sn.UEBERGANG_FRUEH: GRUPPE_UEBERGANG,
    sn.SOMMER: GRUPPE_SOMMER,
}

WERTSPALTEN = ["power_kw", "flow_lh", "dt_k", "performance"]


def lade_serien(meter_dir: Path,
                zaehler: Optional[Iterable[int]] = None
                ) -> Dict[int, pd.DataFrame]:
    """Materialisierte Zählerexporte als Dict Zählernummer → Stundenreihe.

    Erwartet den Ordner, den ``python -m src.load_timeseries --materialize``
    schreibt. Rückgabe trägt das Schema von `features.features_for_meter`
    auf einem DatetimeIndex, Duplikate je Stunde fallen bis auf den
    letzten Eintrag weg.
    """
    meter_dir = Path(meter_dir)
    auswahl = None if zaehler is None else {int(z) for z in zaehler}
    serien: Dict[int, pd.DataFrame] = {}
    for csv in sorted(meter_dir.glob("*.csv")):
        try:
            zid = int(csv.stem)
        except ValueError:
            continue
        if auswahl is not None and zid not in auswahl:
            continue
        df = pd.read_csv(csv, parse_dates=["Timestamp"]).rename(
            columns=SPALTEN_MAP)
        df = df.set_index("Timestamp").sort_index()
        df.index = pd.DatetimeIndex(df.index).floor("h")
        serien[zid] = df[~df.index.duplicated(keep="last")]
    return serien


def stundenwerte(df: pd.DataFrame,
                 last_schwelle_kw: float = pf.LAST_SCHWELLE_KW,
                 perf_quelle: str = "momentan",
                 min_volumen_m3: float = MIN_VOLUMEN_STUNDE_M3,
                 max_gap_hours: int = pf.MAX_GAP_HOURS) -> pd.DataFrame:
    """Eine Zeile je Betriebsstunde mit den drei Kanälen und der Farbgröße.

    Rückgabe: ``zeit``, ``datum``, ``power_kw``, ``flow_lh``, ``dt_k``,
    ``performance``. Enthalten sind nur Stunden unter Last mit positivem
    Durchfluss und positiver Spreizung - Stillstandsstunden haben im
    Ternärdiagramm keinen definierten Punkt, weil alle drei Kanäle null
    sind.

    `perf_quelle` wählt die Farbgröße. ``momentan`` rechnet die gemessene
    Spreizung über 1,163 kWh/(m³·K) um, ``zaehler`` bildet den Quotienten
    aus den kumulativen Kanälen und ist bei grober Zählerauflösung
    unbrauchbar (siehe Modul-Docstring).
    """
    if perf_quelle not in ("momentan", "zaehler"):
        raise ValueError("perf_quelle muss 'momentan' oder 'zaehler' sein")
    spalten = ["zeit", "datum"] + WERTSPALTEN
    if len(df) == 0:
        return pd.DataFrame(columns=spalten)

    w = df.sort_index()
    idx = pd.DatetimeIndex(w.index)
    out = pd.DataFrame({"zeit": idx, "datum": idx.normalize()})
    for quelle, ziel in (("power", "power_kw"), ("flow", "flow_lh"),
                         ("dt", "dt_k")):
        out[ziel] = (pd.to_numeric(w[quelle], errors="coerce").to_numpy()
                     if quelle in w.columns else np.nan)

    if perf_quelle == "momentan":
        out["performance"] = out["dt_k"] * KWH_PRO_M3_K
    else:
        abstand_h = (pd.Series(idx, index=idx).diff()
                     .dt.total_seconds().to_numpy() / 3600.0)
        d_e = pd.to_numeric(w.get("energy"), errors="coerce").diff().to_numpy()
        d_v = pd.to_numeric(w.get("volume"), errors="coerce").diff().to_numpy()
        ok = ((abstand_h > 0) & (abstand_h <= max_gap_hours)
              & (d_e >= 0) & (d_v >= float(min_volumen_m3)))
        with np.errstate(divide="ignore", invalid="ignore"):
            perf = np.where(ok, d_e / np.where(d_v > 0, d_v, np.nan), np.nan)
        unten, oben = pf.BAND_KWH_M3
        out["performance"] = np.where((perf >= unten) & (perf <= oben),
                                      perf, np.nan)

    gueltig = ((out["power_kw"] > float(last_schwelle_kw))
               & (out["flow_lh"] > 0) & (out["dt_k"] > 0))
    out = out[gueltig.fillna(False)]
    return out[spalten].reset_index(drop=True)


def tageswerte(df: pd.DataFrame,
               min_volume_m3: float = pf.MIN_VOLUME_M3,
               min_stunden: int = pf.MIN_STUNDEN) -> pd.DataFrame:
    """Eine Zeile je gültigem Kalendertag mit den drei Kanälen.

    Aufsetzpunkt ist `performance.tagesperformance`, es wird nur die
    dort als ``gueltig`` markierte Teilmenge übernommen. Die drei Kanäle
    werden so gebildet, dass P = c · V · ΔT exakt gilt: mittlere Leistung
    ist Tagesenergie je gültiger Stunde, mittlerer Durchfluss das
    Tagesvolumen je gültiger Stunde, die Spreizung die Kennzahl
    ``spreizung_k``. Die aus den Momentankanälen gemittelte Spreizung
    wäre damit nicht konsistent und bliebe in der Varianzzerlegung
    unerklärt.
    """
    spalten = ["zeit", "datum"] + WERTSPALTEN
    if len(df) == 0:
        return pd.DataFrame(columns=spalten)

    tab = pf.tagesperformance(df, min_volume_m3=min_volume_m3,
                              min_stunden=min_stunden)
    tab = tab[tab["gueltig"]].copy()
    if len(tab) == 0:
        return pd.DataFrame(columns=spalten)

    stunden = tab["n_stunden"].replace(0, np.nan)
    out = pd.DataFrame({
        "zeit": pd.DatetimeIndex(tab["datum"]),
        "datum": pd.DatetimeIndex(tab["datum"]),
        "power_kw": tab["energie_kwh"] / stunden,
        "flow_lh": tab["volumen_m3"] * 1000.0 / stunden,
        "dt_k": tab["spreizung_k"],
        "performance": tab["performance"],
    })
    out = out[(out["power_kw"] > 0) & (out["flow_lh"] > 0) & (out["dt_k"] > 0)]
    return out[spalten].reset_index(drop=True)


def ternaerkoordinaten(tab: pd.DataFrame,
                       quantil: float = REFERENZ_QUANTIL,
                       min_nenner: float = 1e-9) -> pd.DataFrame:
    """Kopie von `tab` mit den drei Anteilen und den normierten Kanälen.

    Normiert wird auf das `quantil` der übergebenen Tabelle, also auf
    die Station als Ganzes. Werte oberhalb des Quantils werden auf 1
    gekappt; das betrifft definitionsgemäß 5 Prozent der Zeilen und
    verhindert, dass ein einzelner Lastspitzenwert die ganze Wolke in
    die Ecke drückt.
    """
    out = tab.copy()
    for quelle, ziel in (("flow_lh", "flow_n"), ("dt_k", "dt_n"),
                         ("power_kw", "power_n")):
        werte = pd.to_numeric(out[quelle], errors="coerce")
        nenner = float(werte.quantile(quantil)) if len(werte) else np.nan
        if not np.isfinite(nenner) or nenner <= min_nenner:
            out[ziel] = np.nan
        else:
            out[ziel] = (werte / nenner).clip(lower=0.0, upper=1.0)

    summe = out[["flow_n", "dt_n", "power_n"]].sum(axis=1, skipna=False)
    summe = summe.where(summe > min_nenner)
    for anteil, norm in zip(ANTEILSSPALTEN, ["flow_n", "dt_n", "power_n"]):
        out[anteil] = out[norm] / summe
    return out


def ternaer_xy(anteil_flow, anteil_dt, anteil_power):
    """Anteile auf die Kartesischen Koordinaten des Dreiecks abbilden."""
    a_flow = np.asarray(anteil_flow, dtype=float)
    a_dt = np.asarray(anteil_dt, dtype=float)
    a_power = np.asarray(anteil_power, dtype=float)
    x = (ECKEN["flow"][0] * a_flow + ECKEN["dt"][0] * a_dt
         + ECKEN["power"][0] * a_power)
    y = (ECKEN["flow"][1] * a_flow + ECKEN["dt"][1] * a_dt
         + ECKEN["power"][1] * a_power)
    return x, y


def begehungsgruppe(tab: pd.DataFrame,
                    begehungsdatum,
                    puffer_tage: int = PUFFER_TAGE,
                    spalte: str = "gruppe_begehung") -> pd.DataFrame:
    """Kopie von `tab` mit vorher / umbauphase / nachher.

    `begehungsdatum` darf None sein; dann bleibt die Spalte leer, und
    die Station bekommt in der Grafik nur die Saisonzeile. Bei mehreren
    Begehungen gehört die Auswahl in den Aufruf.
    """
    out = tab.copy()
    if begehungsdatum is None or (isinstance(begehungsdatum, float)
                                  and np.isnan(begehungsdatum)):
        out[spalte] = pd.Series([pd.NA] * len(out), index=out.index,
                                dtype="object")
        return out

    trenn = pd.Timestamp(begehungsdatum).normalize()
    abstand = (pd.DatetimeIndex(out["datum"]) - trenn).days
    werte = np.where(abstand < -int(puffer_tage), GRUPPE_VORHER,
                     np.where(abstand > int(puffer_tage), GRUPPE_NACHHER,
                              GRUPPE_UMBAU))
    out[spalte] = pd.Categorical(werte, categories=BEGEHUNGSGRUPPEN)
    return out


def saisongruppe(tab: pd.DataFrame,
                 spalte: str = "gruppe_saison",
                 month_map: Optional[Mapping[int, str]] = None
                 ) -> pd.DataFrame:
    """Kopie von `tab` mit winter / uebergang / sommer.

    Die Abgrenzung kommt aus `season.py`; die beiden Übergangssegmente
    werden zu einem Panel zusammengefasst, weil Frühjahr und Herbst in
    der Folienlogik denselben Teillastbereich meinen.
    """
    out = sn.add_season_segment(tab, timestamp_col="datum",
                                month_map=month_map, column="_segment")
    werte = [SEGMENT_AUF_GRUPPE.get(str(s)) for s in out["_segment"]]
    out[spalte] = pd.Categorical(werte, categories=SAISONGRUPPEN)
    return out.drop(columns=["_segment"])


def modulationszerlegung(tab: pd.DataFrame, min_punkte: int = 30) -> dict:
    """Varianzanteile der Leistungsmodulation an Durchfluss und Spreizung.

    Rückgabe mit ``anteil_mod_flow``, ``anteil_mod_dt``, deren Summe und
    ``n``. Die Summe muss bis auf die Messabweichung 1 ergeben; weicht
    sie deutlich ab, passen Leistungs-, Durchfluss- und
    Temperaturkanal des Zählers nicht zusammen.
    """
    leer = {"anteil_mod_flow": np.nan, "anteil_mod_dt": np.nan,
            "summe_mod": np.nan, "n": 0}
    if len(tab) == 0:
        return leer
    m = ((tab["power_kw"] > 0) & (tab["flow_lh"] > 0) & (tab["dt_k"] > 0))
    teil = tab[m.fillna(False)]
    if len(teil) < int(min_punkte):
        leer["n"] = int(len(teil))
        return leer

    lp = np.log(teil["power_kw"].to_numpy(dtype=float))
    lf = np.log(teil["flow_lh"].to_numpy(dtype=float))
    ld = np.log(teil["dt_k"].to_numpy(dtype=float))
    var_p = float(np.var(lp))
    if not np.isfinite(var_p) or var_p <= 1e-12:
        leer["n"] = int(len(teil))
        return leer

    cov_f = float(np.mean((lp - lp.mean()) * (lf - lf.mean())))
    cov_d = float(np.mean((lp - lp.mean()) * (ld - ld.mean())))
    anteil_f = cov_f / var_p
    anteil_d = cov_d / var_p
    return {"anteil_mod_flow": anteil_f, "anteil_mod_dt": anteil_d,
            "summe_mod": anteil_f + anteil_d, "n": int(len(teil))}


def kennzahlen(tab: pd.DataFrame,
               gruppenspalte: str,
               gruppen: Sequence[str],
               meter: Optional[int] = None,
               min_punkte: int = 30) -> pd.DataFrame:
    """Eine Zeile je Gruppe mit Schwerpunkt, Streubreite und Modulation.

    Spalten: ``n``, ``schwerpunkt_flow``, ``schwerpunkt_dt``,
    ``schwerpunkt_power``, ``streuung`` (mittlerer Abstand zum
    Schwerpunkt im Dreieck, Kantenlänge 1), ``performance_median``,
    ``anteil_mod_flow``, ``anteil_mod_dt``, ``summe_mod``.

    Gruppen ohne Punkte verschwinden nicht, sondern stehen mit n = 0 und
    NaN in der Tabelle - eine Station ohne Sommerbetrieb ist selbst ein
    Befund.
    """
    rows = []
    for gruppe in gruppen:
        teil = tab[tab[gruppenspalte].astype("object") == gruppe]
        teil = teil.dropna(subset=ANTEILSSPALTEN)
        zeile = {"meter": meter, "gruppe": gruppe, "n": int(len(teil))}
        if len(teil) == 0:
            zeile.update({
                "schwerpunkt_flow": np.nan, "schwerpunkt_dt": np.nan,
                "schwerpunkt_power": np.nan, "streuung": np.nan,
                "performance_median": np.nan,
            })
            zeile.update({k: v for k, v in modulationszerlegung(teil).items()
                          if k != "n"})
            rows.append(zeile)
            continue

        s_flow = float(teil["anteil_flow"].mean())
        s_dt = float(teil["anteil_dt"].mean())
        s_power = float(teil["anteil_power"].mean())
        x, y = ternaer_xy(teil["anteil_flow"], teil["anteil_dt"],
                          teil["anteil_power"])
        xs, ys = ternaer_xy(s_flow, s_dt, s_power)
        zeile.update({
            "schwerpunkt_flow": s_flow,
            "schwerpunkt_dt": s_dt,
            "schwerpunkt_power": s_power,
            "streuung": float(np.mean(np.hypot(x - xs, y - ys))),
            "performance_median": float(teil["performance"].median()),
        })
        zeile.update({k: v for k, v in
                      modulationszerlegung(teil, min_punkte=min_punkte).items()
                      if k != "n"})
        rows.append(zeile)
    return pd.DataFrame(rows)


def zeichne_dreieck(ax, schritt: float = 0.2, ticks: bool = True,
                    schriftgroesse: float = 6.0) -> None:
    """Rahmen, Gitter und Achsenbeschriftung eines leeren Ternärdiagramms."""
    ecken = [ECKEN["flow"], ECKEN["dt"], ECKEN["power"], ECKEN["flow"]]
    ax.plot([p[0] for p in ecken], [p[1] for p in ecken],
            color="0.3", lw=0.9, zorder=1)

    stufen = np.arange(schritt, 1.0, schritt)
    for t in stufen:
        linien = [
            #konstanter Leistungsanteil
            ((1 - t, 0.0, t), (0.0, 1 - t, t)),
            #konstanter Spreizungsanteil
            ((1 - t, t, 0.0), (0.0, t, 1 - t)),
            #konstanter Durchflussanteil
            ((t, 1 - t, 0.0), (t, 0.0, 1 - t)),
        ]
        for a, b in linien:
            x, y = ternaer_xy([a[0], b[0]], [a[1], b[1]], [a[2], b[2]])
            ax.plot(x, y, color="0.85", lw=0.5, zorder=0)

    if ticks:
        for t in stufen:
            xd, yd = ternaer_xy(1 - t, t, 0.0)
            ax.text(xd, yd - 0.035, f"{t:.1f}", ha="center", va="top",
                    fontsize=schriftgroesse, color="0.45")
            xp, yp = ternaer_xy(0.0, 1 - t, t)
            ax.text(xp + 0.028, yp, f"{t:.1f}", ha="left", va="center",
                    fontsize=schriftgroesse, color="0.45")
            xf, yf = ternaer_xy(t, 0.0, 1 - t)
            ax.text(xf - 0.028, yf, f"{t:.1f}", ha="right", va="center",
                    fontsize=schriftgroesse, color="0.45")

    ax.text(ECKEN["power"][0], ECKEN["power"][1] + 0.05,
            ACHSENTITEL["power"], ha="center", va="bottom",
            fontsize=schriftgroesse + 2)
    ax.text(ECKEN["flow"][0] - 0.02, -0.06, ACHSENTITEL["flow"],
            ha="left", va="top", fontsize=schriftgroesse + 2)
    ax.text(ECKEN["dt"][0] + 0.02, -0.06, ACHSENTITEL["dt"],
            ha="right", va="top", fontsize=schriftgroesse + 2)

    ax.set_xlim(-0.14, 1.14)
    ax.set_ylim(-0.17, 1.02)
    ax.set_aspect("equal")
    ax.axis("off")


def zeichne_panel(ax, teil: pd.DataFrame, titel: str,
                  vmin: float, vmax: float,
                  cmap: str = "plasma",
                  punktgroesse: float = 2.0,
                  schwerpunkt: bool = True):
    """Punktwolke einer Gruppe in ein vorbereitetes Dreieck zeichnen."""
    zeichne_dreieck(ax)
    teil = teil.dropna(subset=ANTEILSSPALTEN)
    if len(teil) == 0:
        ax.set_title(f"{titel}\nkeine Daten", fontsize=8)
        return None

    x, y = ternaer_xy(teil["anteil_flow"], teil["anteil_dt"],
                      teil["anteil_power"])
    bild = ax.scatter(x, y, c=teil["performance"], cmap=cmap,
                      vmin=vmin, vmax=vmax, s=punktgroesse, linewidths=0,
                      alpha=0.55, zorder=2, rasterized=True)
    if schwerpunkt:
        xs, ys = ternaer_xy(float(teil["anteil_flow"].mean()),
                            float(teil["anteil_dt"].mean()),
                            float(teil["anteil_power"].mean()))
        ax.plot([xs], [ys], marker="x", color="black", ms=6, mew=1.2,
                zorder=3)
    med = float(teil["performance"].median())
    ax.set_title(f"{titel}\nn = {len(teil)}, Median {med:.1f} kWh/m³",
                 fontsize=8)
    return bild


def stationsgrafik(tab: pd.DataFrame,
                   meter: int,
                   aufloesung: str = "Stunde",
                   adresse: Optional[str] = None,
                   cmap: str = "plasma",
                   punktgroesse: float = 2.0):
    """Ein Bild je Station: Begehungszeile und Saisonzeile nebeneinander.

    `tab` ist die Ausgabe von `ternaerkoordinaten` mit den beiden
    Gruppenspalten. Stationen ohne Begehungsdatum bekommen nur die
    Saisonzeile, damit keine leere Reihe entsteht.
    """
    import matplotlib.pyplot as plt

    zeilen = []
    if "gruppe_begehung" in tab.columns and tab["gruppe_begehung"].notna().any():
        zeilen.append(("gruppe_begehung", BEGEHUNGSGRUPPEN, "Begehung"))
    if "gruppe_saison" in tab.columns:
        zeilen.append(("gruppe_saison", SAISONGRUPPEN, "Saison"))
    if not zeilen:
        raise ValueError("weder Begehungs- noch Saisongruppe vorhanden")

    gueltig = tab.dropna(subset=ANTEILSSPALTEN)
    if len(gueltig):
        vmin = float(gueltig["performance"].quantile(0.05))
        vmax = float(gueltig["performance"].quantile(0.95))
    else:
        vmin, vmax = 0.0, 1.0
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        vmin, vmax = 0.0, 1.0

    fig, axes = plt.subplots(len(zeilen), 3,
                             figsize=(11.0, 3.9 * len(zeilen)),
                             squeeze=False)
    bild = None
    for i, (spalte, gruppen, label) in enumerate(zeilen):
        for j, gruppe in enumerate(gruppen):
            teil = tab[tab[spalte].astype("object") == gruppe]
            b = zeichne_panel(axes[i][j], teil, f"{label}: {gruppe}",
                              vmin, vmax, cmap=cmap,
                              punktgroesse=punktgroesse)
            bild = b if b is not None else bild

    kopf = f"Zähler {meter} – Ternärdiagramm je Zeitabschnitt ({aufloesung})"
    if adresse:
        kopf += f" – {adresse}"
    fig.suptitle(kopf, fontsize=11)
    fig.tight_layout(rect=(0.0, 0.0, 0.92, 0.96))
    if bild is not None:
        cax = fig.add_axes([0.94, 0.12, 0.016, 0.74])
        cb = fig.colorbar(bild, cax=cax)
        cb.set_label("Performance in kWh/m³", fontsize=8)
        cb.ax.tick_params(labelsize=7)
    return fig


def stationstabelle(df: pd.DataFrame,
                    meter: int,
                    aufloesung: str = "stunde",
                    begehungsdatum=None,
                    puffer_tage: int = PUFFER_TAGE,
                    quantil: float = REFERENZ_QUANTIL,
                    perf_quelle: str = "momentan") -> pd.DataFrame:
    """Vollständige Punkttabelle einer Station inklusive beider Gruppen."""
    if aufloesung == "stunde":
        tab = stundenwerte(df, perf_quelle=perf_quelle)
    elif aufloesung == "tag":
        tab = tageswerte(df)
    else:
        raise ValueError("aufloesung muss 'stunde' oder 'tag' sein")
    if len(tab) == 0:
        return tab
    tab = ternaerkoordinaten(tab, quantil=quantil)
    tab = begehungsgruppe(tab, begehungsdatum, puffer_tage=puffer_tage)
    tab = saisongruppe(tab)
    tab.insert(0, "meter", int(meter))
    return tab


def exportiere(serien: Mapping[int, pd.DataFrame],
               out_dir: Path,
               begehungsdatum: Optional[Mapping[int, object]] = None,
               aufloesungen: Sequence[str] = ("stunde", "tag"),
               adressen: Optional[Mapping[int, str]] = None,
               puffer_tage: int = PUFFER_TAGE,
               quantil: float = REFERENZ_QUANTIL,
               dpi: int = 110,
               fortschritt: bool = False) -> pd.DataFrame:
    """Für jede Station je Auflösung ein PNG schreiben und Kennzahlen sammeln.

    Die Bilder landen unter ``out_dir/<aufloesung>/<zaehlernummer>.png``.
    Rückgabe ist die Kennzahlentabelle über alle Stationen, Auflösungen
    und Gruppen - das ist der Teil, mit dem sich anschließend Muster
    suchen lassen; die Bilder sind die Kontrolle dazu.

    Stationen ohne verwertbare Punkte erscheinen mit n = 0 in der
    Tabelle und ohne Bild, damit der Ausfall sichtbar bleibt.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    datum = dict(begehungsdatum or {})
    rows = []
    for n, (meter, df) in enumerate(sorted(serien.items()), start=1):
        for aufl in aufloesungen:
            tab = stationstabelle(df, meter, aufloesung=aufl,
                                  begehungsdatum=datum.get(meter),
                                  puffer_tage=puffer_tage, quantil=quantil)
            for spalte, gruppen in (("gruppe_begehung", BEGEHUNGSGRUPPEN),
                                    ("gruppe_saison", SAISONGRUPPEN)):
                if len(tab) == 0:
                    teil = pd.DataFrame(columns=["meter"] + WERTSPALTEN
                                        + ANTEILSSPALTEN + [spalte])
                else:
                    teil = tab
                k = kennzahlen(teil, spalte, gruppen, meter=meter)
                k.insert(1, "aufloesung", aufl)
                k.insert(2, "schnitt",
                         "begehung" if spalte.endswith("begehung")
                         else "saison")
                rows.append(k)

            if len(tab) == 0:
                continue
            ziel = out_dir / aufl
            ziel.mkdir(parents=True, exist_ok=True)
            fig = stationsgrafik(
                tab, meter,
                aufloesung="Stundenwerte" if aufl == "stunde" else "Tageswerte",
                adresse=None if adressen is None else adressen.get(meter))
            fig.savefig(ziel / f"{meter}.png", dpi=dpi)
            plt.close(fig)
        if fortschritt and n % 10 == 0:
            print(f"{n}/{len(serien)} Stationen", flush=True)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
