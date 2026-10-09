"""
Kennzahl Performance (kWh/m3) und Regression gegen die Aussentemperatur.

Vorlage ist die UEZ-Folie "Vergleich Gesamteffizienz vor und nach der
Optimierung von HAST".

Kennzahl
--------
- entnommene Energie je m3 Heizwasser = volumenstromgewichtete Spreizung
- 1 kWh/m3 entspricht etwa 0,86 K (1 m3 Wasser nimmt je Kelvin rund
  1,163 kWh auf)
- hoch ist gut: niedriger Ruecklauf, wenig Netzverluste
- wird gegen die Aussentemperatur aufgetragen, weil sie im Milden
  abfaellt

Kumulative Kanaele
------------------
Energie und Volumen sind Zaehlerstaende. `tagesdifferenzen` bildet
Stundendifferenzen und verwirft einzelne Intervalle bei:
- Ruecksprung des Zaehlerstands (Ueberlauf, Geraetetausch)
- Messluecke
- physikalisch unmoeglichem Sprung
Der Tag bleibt erhalten, `n_stunden` zeigt, wie viele Stunden er noch hat.

Filter
------
- Tage mit sehr kleinem Volumen liefern instabile Quotienten, deshalb
  der Parameter `min_volume_m3`
- jeder Tag traegt die Flags `volumen_zu_klein`, `ausserhalb_band`,
  `abdeckung_gering` und die Sammelspalte `gueltig`
- `filterbilanz` zaehlt, wie viele Tage an welchem Filter haengen bleiben

Gegenprobe
----------
`spreizung_k` (Kennzahl in Kelvin) muss ungefaehr zu `dt_gewichtet`
(gemessene, durchflussgewichtete Spreizung) passen. Wenn nicht, passen
die Kanaele des Zaehlers nicht zusammen.

Clusterrobuste Fehler
---------------------
Tage derselben Station sind nicht unabhaengig. `ols`, `regression` und
`interaktionsmodell` nehmen deshalb `cluster` (Zaehlernummer) und
rechnen die Sandwich-Schaetzung. Ohne `cluster` gilt die Standardformel,
das ist nur fuer den direkten Nachbau der Folie sinnvoll.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Union

import numpy as np
import pandas as pd

#Waermekapazitaet von Wasser bei Fernwaerme-Temperaturen, kWh je m3 und K.
#4,19 kJ/(kg K) * 1000 kg/m3 / 3600 s/h = 1,163 kWh/(m3 K)
KWH_PRO_M3_K = 1.163

#Mindestvolumen je Tag. 0,5 m3 entspricht bei 20 K Spreizung rund 12 kWh -
#darunter ist der Quotient Rauschen. Parameter, keine Konstante.
MIN_VOLUME_M3 = 0.5

#Plausibilitaetsband der Kennzahl in kWh/m3. Die Obergrenze entspricht
#rund 60 K Spreizung und liegt damit ueber jeder realen Fernwaerme-HAST;
#die Untergrenze laesst kleine negative Werte aus der Abtastung zu.
BAND_KWH_M3 = (-2.0, 70.0)

#Maximaler Abstand zweier Messpunkte, der noch als ein Stundenintervall
#gilt. Der ÜZ-Export steht nominell stuendlich, einzelne Minutenversaetze
#bleiben damit drin, eine echte Luecke nicht.
MAX_GAP_HOURS = 2

#Mindestzahl gueltiger Stundenintervalle je Tag (von 24)
MIN_STUNDEN = 20

#Leistungsschwelle "unter Last", identisch zu features.features_for_meter
LAST_SCHWELLE_KW = 0.5

#Gruppennamen der Vorher/Nachher-Zerlegung
GRUPPE_VOR = "unoptimiert"
GRUPPE_NACH = "optimiert"

TimestampLike = Union[str, pd.Timestamp]


#--------------------------------------------------------------------------
#Tagesreihe je Zaehler
#--------------------------------------------------------------------------

def tagesdifferenzen(df: pd.DataFrame,
                     max_gap_hours: int = MAX_GAP_HOURS,
                     max_energy_step_kwh: float = 5000.0,
                     max_volume_step_m3: float = 100.0) -> pd.DataFrame:
    """Kumulative Kanaele differenzieren und je Kalendertag aufsummieren.

    `df` erwartet das Schema von `features.features_for_meter`: Spalten
    ``energy`` (kWh, kumulativ), ``volume`` (m3, kumulativ) sowie
    optional ``power``, ``dt``, ``rt``, ``flow`` auf einem
    DatetimeIndex.

    Ein Stundenintervall geht nur in den Tag ein, wenn der Abstand zum
    Vorgaenger hoechstens `max_gap_hours` betraegt, beide Zaehlerstaende
    nicht zurueckspringen und der Sprung unter den beiden Obergrenzen
    bleibt. Die Obergrenzen fangen Geraetetausch und Exportartefakte ab,
    bei denen der Zaehlerstand nach vorne springt statt zurueck.

    Rueckgabe: eine Zeile je Kalendertag mit ``energie_kwh``,
    ``volumen_m3``, ``n_stunden`` (gueltige Intervalle), ``n_verworfen``,
    dazu ``dt_gewichtet``, ``rt_mean_loaded`` und ``t_stunden_last``
    als Gegenprobe aus den Momentankanaelen.
    """
    for spalte in ("energy", "volume"):
        if spalte not in df.columns:
            raise KeyError(
                f"Spalte '{spalte}' fehlt - vorhanden: {list(df.columns)}")
    if len(df) == 0:
        return pd.DataFrame(columns=["datum", "energie_kwh", "volumen_m3",
                                     "n_stunden", "n_verworfen",
                                     "dt_gewichtet", "rt_mean_loaded",
                                     "t_stunden_last"])

    w = df.sort_index()
    idx = pd.DatetimeIndex(w.index)
    abstand_h = pd.Series(idx, index=idx).diff().dt.total_seconds() / 3600.0

    d_energie = pd.to_numeric(w["energy"], errors="coerce").diff()
    d_volumen = pd.to_numeric(w["volume"], errors="coerce").diff()

    gueltig = (
        abstand_h.notna() & (abstand_h > 0) & (abstand_h <= max_gap_hours)
        & d_energie.notna() & d_volumen.notna()
        #Ruecksprung: Ueberlauf oder Geraetetausch, kein Verbrauch
        & (d_energie >= 0) & (d_volumen >= 0)
        & (d_energie <= max_energy_step_kwh)
        & (d_volumen <= max_volume_step_m3)
    )
    #das erste Intervall hat keinen Vorgaenger und ist damit nie gueltig
    gueltig.iloc[0] = False

    teil = pd.DataFrame({
        "datum": idx.normalize(),
        "d_energie": d_energie.to_numpy(),
        "d_volumen": d_volumen.to_numpy(),
        "gueltig": gueltig.to_numpy(),
    }, index=idx)

    for spalte in ("power", "dt", "rt", "flow"):
        teil[spalte] = (pd.to_numeric(w[spalte], errors="coerce").to_numpy()
                        if spalte in w.columns else np.nan)

    rows = []
    for datum, g in teil.groupby("datum", sort=True):
        ok = g["gueltig"]
        last = g["power"] > LAST_SCHWELLE_KW
        gewicht = g.loc[last, "flow"]
        summe_gewicht = gewicht.sum(skipna=True) if len(gewicht) else 0.0
        if summe_gewicht > 0:
            dt_gew = float((gewicht * g.loc[last, "dt"]).sum(skipna=True)
                           / summe_gewicht)
        else:
            dt_gew = np.nan
        rows.append({
            "datum": pd.Timestamp(datum),
            "energie_kwh": float(g.loc[ok, "d_energie"].sum()),
            "volumen_m3": float(g.loc[ok, "d_volumen"].sum()),
            "n_stunden": int(ok.sum()),
            "n_verworfen": int((~ok).sum()),
            "dt_gewichtet": dt_gew,
            "rt_mean_loaded": (float(g.loc[last, "rt"].mean())
                               if last.any() else np.nan),
            "t_stunden_last": int(last.sum()),
        })
    return pd.DataFrame(rows).reset_index(drop=True)


def tagesperformance(df: pd.DataFrame,
                     min_volume_m3: float = MIN_VOLUME_M3,
                     band: Sequence[float] = BAND_KWH_M3,
                     min_stunden: int = MIN_STUNDEN,
                     max_gap_hours: int = MAX_GAP_HOURS) -> pd.DataFrame:
    """Tagesreihe der Kennzahl Performance fuer eine Zaehlerreihe.

    Spalten zusaetzlich zu `tagesdifferenzen`:

        performance       Energie je Volumen in kWh/m3
        spreizung_k       dieselbe Groesse in Kelvin
        dt_abweichung_k   spreizung_k minus dt_gewichtet
        volumen_zu_klein  Tagesvolumen unter `min_volume_m3`
        ausserhalb_band   Kennzahl ausserhalb `band`
        abdeckung_gering  weniger als `min_stunden` gueltige Intervalle
        gueltig           keines der drei Flags gesetzt

    Es wird nichts entfernt. Wer nur die belastbaren Tage will, filtert
    selbst auf ``gueltig``; `filterbilanz` zeigt vorher, was das kostet.
    """
    tab = tagesdifferenzen(df, max_gap_hours=max_gap_hours)
    if len(tab) == 0:
        for spalte in ("performance", "spreizung_k", "dt_abweichung_k"):
            tab[spalte] = pd.Series(dtype=float)
        for spalte in ("volumen_zu_klein", "ausserhalb_band",
                       "abdeckung_gering", "gueltig"):
            tab[spalte] = pd.Series(dtype=bool)
        return tab

    unten, oben = float(band[0]), float(band[1])
    klein = tab["volumen_m3"] < float(min_volume_m3)
    with np.errstate(divide="ignore", invalid="ignore"):
        perf = np.where(klein, np.nan,
                        tab["energie_kwh"] / tab["volumen_m3"].replace(0, np.nan))
    tab["performance"] = perf
    tab["spreizung_k"] = tab["performance"] / KWH_PRO_M3_K
    tab["dt_abweichung_k"] = tab["spreizung_k"] - tab["dt_gewichtet"]

    tab["volumen_zu_klein"] = klein
    tab["ausserhalb_band"] = (tab["performance"].notna()
                              & ~tab["performance"].between(unten, oben))
    tab["abdeckung_gering"] = tab["n_stunden"] < int(min_stunden)
    tab["gueltig"] = ~(tab["volumen_zu_klein"] | tab["ausserhalb_band"]
                       | tab["abdeckung_gering"]) & tab["performance"].notna()
    return tab


def performance_tabelle(serien: Mapping[int, pd.DataFrame],
                        min_volume_m3: float = MIN_VOLUME_M3,
                        band: Sequence[float] = BAND_KWH_M3,
                        min_stunden: int = MIN_STUNDEN,
                        max_gap_hours: int = MAX_GAP_HOURS) -> pd.DataFrame:
    """`tagesperformance` ueber alle Zaehler, gestapelt zu einer Langtabelle.

    `serien` bildet Zaehlernummer auf die stuendliche Reihe ab. Die
    Rueckgabe traegt ``meter`` als erste Spalte; Stationen ohne
    verwertbare Historie erscheinen gar nicht, was `filterbilanz` ueber
    die Zaehlerzahl sichtbar macht.
    """
    frames = []
    for zid, df in sorted(serien.items()):
        if df is None or len(df) == 0:
            continue
        tab = tagesperformance(df, min_volume_m3=min_volume_m3, band=band,
                               min_stunden=min_stunden,
                               max_gap_hours=max_gap_hours)
        if len(tab) == 0:
            continue
        tab.insert(0, "meter", int(zid))
        frames.append(tab)
    if not frames:
        return pd.DataFrame(columns=["meter", "datum", "performance"])
    return pd.concat(frames, ignore_index=True)


def filterbilanz(tab: pd.DataFrame) -> pd.DataFrame:
    """Wie viele Tagesreihen an welcher Bedingung haengen bleiben.

    Die Bedingungen ueberschneiden sich, die Zeilen addieren sich
    deshalb nicht auf die Gesamtzahl. Genau so gehoert die Tabelle in
    die Doku: sie beantwortet "woran liegt es", nicht "wie viel bleibt".
    """
    n = len(tab)
    if n == 0:
        return pd.DataFrame(columns=["bedingung", "tage", "anteil"])
    zeilen = [
        ("Tagesreihen gesamt", n),
        ("Volumen unter Schwelle", int(tab["volumen_zu_klein"].sum())),
        ("ausserhalb Plausibilitaetsband", int(tab["ausserhalb_band"].sum())),
        ("Abdeckung unter Mindeststunden", int(tab["abdeckung_gering"].sum())),
        ("gueltig", int(tab["gueltig"].sum())),
    ]
    out = pd.DataFrame(zeilen, columns=["bedingung", "tage"])
    out["anteil"] = out["tage"] / n
    return out


#--------------------------------------------------------------------------
#Aussentemperatur
#--------------------------------------------------------------------------

def tagesmittel_temperatur(t_out: pd.DataFrame,
                           min_stunden: int = MIN_STUNDEN) -> pd.DataFrame:
    """Tagesmittel der Aussentemperatur aus der Stundenreihe von `weather`.

    Erwartet die Spalten ``timestamp`` und ``t_out``. Tage mit weniger
    als `min_stunden` Messwerten bekommen NaN statt eines Mittels aus
    halben Tagen - ein halber Wintertag mittelt sich sonst zu mild.
    """
    for spalte in ("timestamp", "t_out"):
        if spalte not in t_out.columns:
            raise KeyError(
                f"Spalte '{spalte}' fehlt - vorhanden: {list(t_out.columns)}")
    w = t_out.copy()
    w["datum"] = pd.DatetimeIndex(w["timestamp"]).normalize()
    g = w.groupby("datum")["t_out"]
    out = pd.DataFrame({"t_out_tag": g.mean(), "n_stunden_t": g.count()})
    out.loc[out["n_stunden_t"] < int(min_stunden), "t_out_tag"] = np.nan
    return out.reset_index()


def mit_aussentemperatur(tab: pd.DataFrame,
                         t_out: pd.DataFrame,
                         min_stunden: int = MIN_STUNDEN) -> pd.DataFrame:
    """Tagesmittel der Aussentemperatur an die Performancetabelle joinen."""
    tages_t = tagesmittel_temperatur(t_out, min_stunden=min_stunden)
    return tab.merge(tages_t[["datum", "t_out_tag"]], on="datum", how="left")


#--------------------------------------------------------------------------
#Gruppenzuordnung vorher / nachher
#--------------------------------------------------------------------------

def gruppe_fester_stichtag(tab: pd.DataFrame,
                           stichtag: TimestampLike,
                           spalte: str = "gruppe") -> pd.DataFrame:
    """Variante A: ein gemeinsamer Stichtag fuer alle Stationen.

    Das ist die Zerlegung der ÜZ-Folie. Sie ist nur dann korrekt, wenn
    alle Begehungen nahe beim Stichtag liegen; bei gestaffelten Terminen
    landen Tage einer noch nicht begangenen Station faelschlich in
    ``optimiert``.
    """
    d = pd.Timestamp(stichtag).normalize()
    out = tab.copy()
    out[spalte] = np.where(pd.DatetimeIndex(out["datum"]) > d,
                           GRUPPE_NACH, GRUPPE_VOR)
    return out


def gruppe_je_station(tab: pd.DataFrame,
                      begehungsdatum: Mapping[int, TimestampLike],
                      spalte: str = "gruppe",
                      puffer_tage: int = 0) -> pd.DataFrame:
    """Variante B: jede Station trennt an ihrem eigenen Begehungsdatum.

    `begehungsdatum` bildet Zaehlernummer auf das massgebliche Datum ab;
    bei mehreren Begehungen je Station gehoert die Auswahl in den Aufruf
    und nicht hierher. Stationen ohne Eintrag bekommen NaN in `spalte`
    und bleiben damit in der Tabelle, ohne in eine Gruppe zu geraten.

    `puffer_tage` blendet ein symmetrisches Fenster um den Begehungstag
    aus (Einregelphase). 0 schliesst nur den Begehungstag selbst aus.

    Tage ohne Gruppe tragen einen Fehlwert; ob pandas daraus None oder
    NaN macht, haengt von der Version ab, deshalb immer mit `isna`
    pruefen und nicht auf None vergleichen.
    """
    out = tab.copy()
    datum = pd.DatetimeIndex(out["datum"])
    trenn = out["meter"].map(
        lambda m: pd.Timestamp(begehungsdatum[m]).normalize()
        if m in begehungsdatum else pd.NaT)
    trenn = pd.DatetimeIndex(trenn)
    abstand = (datum - trenn).days

    werte = np.full(len(out), np.nan, dtype=object)
    vor = np.asarray(abstand < -int(puffer_tage)) & ~np.asarray(trenn.isna())
    nach = np.asarray(abstand > int(puffer_tage)) & ~np.asarray(trenn.isna())
    werte[vor] = GRUPPE_VOR
    werte[nach] = GRUPPE_NACH
    out[spalte] = pd.Series(werte, index=out.index, dtype="object")
    out["tage_zur_begehung"] = abstand
    return out


#--------------------------------------------------------------------------
#Regression
#--------------------------------------------------------------------------

def _t_quantil(p: float, dof: int) -> float:
    """Zweiseitiges t-Quantil; faellt ohne scipy auf die Normalnaeherung."""
    try:
        from scipy import stats
        return float(stats.t.ppf(p, dof))
    except Exception:
        #1,96 deckt den hier relevanten Fall grosser Fallzahlen ab
        return 1.959963984540054


def _t_pwert(t: float, dof: int) -> float:
    try:
        from scipy import stats
        return float(2 * stats.t.sf(abs(t), dof))
    except Exception:
        from math import erfc, sqrt
        return float(erfc(abs(t) / sqrt(2.0)))


def ols(X: np.ndarray, y: np.ndarray,
        gewichte: Optional[np.ndarray] = None,
        alpha: float = 0.05,
        cluster: Optional[np.ndarray] = None) -> dict:
    """Kleinste Quadrate mit Standardfehlern, Konfidenz- und p-Werten.

    `X` enthaelt die Regressoren **ohne** Achsenabschnitt, der wird hier
    angehaengt. Rueckgabe: ``beta``, ``se``, ``t``, ``p``, ``ci_low``,
    ``ci_high`` (je ein Array in der Reihenfolge Achsenabschnitt, dann
    die Spalten von `X`), dazu ``r2``, ``n``, ``dof`` und die
    Kovarianzmatrix ``cov``.

    `gewichte` sind Beobachtungsgewichte (gewichtete Kleinste Quadrate).
    Sie beeinflussen die Schaetzung, nicht die Fallzahl.

    `cluster` enthaelt je Beobachtung eine Gruppenkennung, hier die
    Zaehlernummer. Ohne sie unterstellt die Formel unabhaengige
    Beobachtungen; Tage derselben Station sind das nicht, die
    Standardfehler faellen dann deutlich zu klein aus. Mit `cluster`
    wird die Sandwich-Schaetzung mit der ueblichen Korrektur
    ``G/(G-1) * (n-1)/(n-k)`` verwendet und ``dof`` auf ``G-1``
    gesetzt. Die Punktschaetzung aendert sich dadurch nicht.
    """
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    y = np.asarray(y, dtype=float)
    D = np.column_stack([np.ones(len(y)), X])
    n, k = D.shape
    dof = n - k
    if dof <= 0:
        raise ValueError(f"zu wenige Beobachtungen: n={n}, Parameter={k}")

    if gewichte is None:
        Dw, yw = D, y
        w = np.ones(n)
    else:
        w = np.asarray(gewichte, dtype=float)
        if np.any(w < 0):
            raise ValueError("Gewichte muessen nichtnegativ sein")
        wurzel = np.sqrt(w)[:, None]
        Dw, yw = D * wurzel, y * np.sqrt(w)

    beta, *_ = np.linalg.lstsq(Dw, yw, rcond=None)
    resid = yw - Dw @ beta
    s2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.pinv(Dw.T @ Dw)
    if cluster is None:
        cov = s2 * xtx_inv
        dof_test = dof
    else:
        gruppen = np.asarray(cluster)
        if len(gruppen) != n:
            raise ValueError(
                f"cluster hat {len(gruppen)} Eintraege, Daten haben {n}")
        meat = np.zeros((k, k))
        for g in pd.unique(gruppen):
            maske = gruppen == g
            summe = Dw[maske].T @ resid[maske]
            meat += np.outer(summe, summe)
        n_gruppen = int(len(pd.unique(gruppen)))
        if n_gruppen <= k:
            raise ValueError(
                f"zu wenige Cluster ({n_gruppen}) fuer {k} Parameter")
        korrektur = (n_gruppen / (n_gruppen - 1)) * ((n - 1) / (n - k))
        cov = korrektur * (xtx_inv @ meat @ xtx_inv)
        dof_test = n_gruppen - 1
    se = np.sqrt(np.diag(cov))

    mittel = float(np.average(y, weights=w))
    ss_tot = float(np.sum(w * (y - mittel) ** 2))
    ss_res = float(resid @ resid)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan

    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, beta / se, np.nan)
    q = _t_quantil(1 - alpha / 2, dof_test)
    return {
        "beta": beta, "se": se, "t": t,
        "p": np.array([_t_pwert(v, dof_test) for v in t]),
        "ci_low": beta - q * se, "ci_high": beta + q * se,
        "r2": r2, "n": int(n), "dof": int(dof_test), "cov": cov,
        "s2": s2, "alpha": float(alpha),
        "n_cluster": (int(len(pd.unique(np.asarray(cluster))))
                      if cluster is not None else None),
    }


def regression(tab: pd.DataFrame,
               x: str = "t_out_tag",
               y: str = "performance",
               gewicht: Optional[str] = None,
               alpha: float = 0.05,
               cluster: Optional[str] = None) -> dict:
    """Einfache Regression Performance gegen Aussentemperatur.

    Rueckgabe in der Sprache der Folie: ``steigung``,
    ``achsenabschnitt``, ``r2``, ``n``, dazu Konfidenzintervall und
    p-Wert der Steigung. Zeilen mit NaN in `x`, `y` oder `gewicht`
    fallen heraus, ihre Zahl steht in ``n_verworfen``.

    `cluster` ist der Spaltenname der Clustervariablen, in der Regel
    ``meter`` - siehe `ols`.
    """
    spalten = [x, y] + ([gewicht] if gewicht else [])
    w = tab[spalten + ([cluster] if cluster else [])].copy()
    w[spalten] = w[spalten].apply(pd.to_numeric, errors="coerce")
    w = w.dropna()
    verworfen = len(tab) - len(w)
    if len(w) < 3:
        return {"steigung": np.nan, "achsenabschnitt": np.nan, "r2": np.nan,
                "n": int(len(w)), "n_verworfen": int(verworfen),
                "steigung_ci": (np.nan, np.nan), "steigung_p": np.nan,
                "steigung_se": np.nan, "fit": None}

    fit = ols(w[[x]].to_numpy(), w[y].to_numpy(),
              gewichte=w[gewicht].to_numpy() if gewicht else None,
              alpha=alpha,
              cluster=w[cluster].to_numpy() if cluster else None)
    return {
        "steigung": float(fit["beta"][1]),
        "achsenabschnitt": float(fit["beta"][0]),
        "r2": float(fit["r2"]),
        "n": fit["n"],
        "n_verworfen": int(verworfen),
        "steigung_se": float(fit["se"][1]),
        "steigung_ci": (float(fit["ci_low"][1]), float(fit["ci_high"][1])),
        "steigung_p": float(fit["p"][1]),
        "n_cluster": fit["n_cluster"],
        "fit": fit,
    }


def regression_je_gruppe(tab: pd.DataFrame,
                         gruppe: str = "gruppe",
                         x: str = "t_out_tag",
                         y: str = "performance",
                         gewicht: Optional[str] = None,
                         reihenfolge: Sequence[str] = (GRUPPE_VOR, GRUPPE_NACH),
                         alpha: float = 0.05,
                         cluster: Optional[str] = None) -> pd.DataFrame:
    """Je Gruppe eine Gerade, als Tabelle im Stil der Folie."""
    rows = []
    for name in reihenfolge:
        teil = tab[tab[gruppe] == name]
        r = regression(teil, x=x, y=y, gewicht=gewicht, alpha=alpha,
                       cluster=cluster)
        rows.append({
            "gruppe": name,
            "n": r["n"],
            "steigung": r["steigung"],
            "achsenabschnitt": r["achsenabschnitt"],
            "r2": r["r2"],
            "steigung_ci_low": r["steigung_ci"][0],
            "steigung_ci_high": r["steigung_ci"][1],
            "steigung_p": r["steigung_p"],
            "t_out_mittel": pd.to_numeric(teil[x], errors="coerce").mean(),
            "meter": teil["meter"].nunique() if "meter" in teil.columns else np.nan,
        })
    return pd.DataFrame(rows)


def interaktionsmodell(tab: pd.DataFrame,
                       gruppe: str = "gruppe",
                       x: str = "t_out_tag",
                       y: str = "performance",
                       gewicht: Optional[str] = None,
                       referenz: str = GRUPPE_VOR,
                       alpha: float = 0.05,
                       cluster: Optional[str] = None) -> dict:
    """Gemeinsames Modell beider Gruppen mit Interaktionsterm.

        y = b0 + b1 * t + b2 * g + b3 * (t * g),    g = 1 fuer "nachher"

    `b2` ist der Niveauunterschied bei 0 Grad C, `b3` der
    Steigungsunterschied. Der Test auf `b3` ist die Aussage, die auf der
    Folie fehlt: zwei getrennte Geraden zeigen einen Unterschied, sagen
    aber nicht, ob er von Null unterscheidbar ist.
    """
    spalten = [x, y, gruppe] + ([gewicht] if gewicht else [])
    if cluster:
        spalten = spalten + [cluster]
    w = tab[spalten].dropna().copy()
    w[x] = pd.to_numeric(w[x], errors="coerce")
    w[y] = pd.to_numeric(w[y], errors="coerce")
    w = w.dropna(subset=[x, y])
    stufen = [s for s in w[gruppe].unique() if s != referenz]
    if len(stufen) != 1:
        raise ValueError(
            f"Interaktionsmodell braucht genau zwei Gruppen, gefunden: "
            f"{sorted(w[gruppe].unique())}")
    andere = stufen[0]

    g = (w[gruppe] == andere).to_numpy(dtype=float)
    t = w[x].to_numpy(dtype=float)
    X = np.column_stack([t, g, t * g])
    fit = ols(X, w[y].to_numpy(dtype=float),
              gewichte=w[gewicht].to_numpy() if gewicht else None, alpha=alpha,
              cluster=w[cluster].to_numpy() if cluster else None)

    return {
        "referenz": referenz,
        "vergleich": andere,
        "steigung_referenz": float(fit["beta"][1]),
        "niveaudifferenz": float(fit["beta"][2]),
        "steigungsdifferenz": float(fit["beta"][3]),
        "steigungsdifferenz_se": float(fit["se"][3]),
        "steigungsdifferenz_ci": (float(fit["ci_low"][3]),
                                  float(fit["ci_high"][3])),
        "steigungsdifferenz_p": float(fit["p"][3]),
        "niveaudifferenz_p": float(fit["p"][2]),
        "r2": float(fit["r2"]),
        "n": fit["n"],
        "n_cluster": fit["n_cluster"],
        "fit": fit,
    }


def delta_am_bezugspunkt(steigung_vor: float, achsenabschnitt_vor: float,
                         steigung_nach: float, achsenabschnitt_nach: float,
                         t_ref: float) -> dict:
    """Abstand der beiden Geraden an der Bezugstemperatur.

    Dieselbe Definition wie auf der ÜZ-Folie: absolute Differenz der
    Geradenwerte bei `t_ref` und diese Differenz bezogen auf den Wert
    der unoptimierten Geraden.
    """
    y_vor = achsenabschnitt_vor + steigung_vor * t_ref
    y_nach = achsenabschnitt_nach + steigung_nach * t_ref
    delta = y_nach - y_vor
    return {
        "t_ref": float(t_ref),
        "y_vor": float(y_vor),
        "y_nach": float(y_nach),
        "delta_kwh_m3": float(delta),
        "delta_k": float(delta / KWH_PRO_M3_K),
        "delta_prozent": float(delta / y_vor * 100.0) if y_vor != 0 else np.nan,
    }


def delta_aus_interaktion(modell: dict, t_ref: float,
                          alpha: float = 0.05) -> dict:
    """Delta am Bezugspunkt samt Konfidenzintervall aus dem Gesamtmodell.

    Der Abstand der Geraden bei `t_ref` ist ``b2 + b3 * t_ref``; seine
    Varianz folgt aus der Kovarianzmatrix des gemeinsamen Modells. Die
    getrennten Fits liefern dieses Intervall nicht, weil sie die
    Kovarianz der beiden Geraden nicht kennen.
    """
    fit = modell["fit"]
    c = np.array([0.0, 0.0, 1.0, float(t_ref)])
    delta = float(c @ fit["beta"])
    var = float(c @ fit["cov"] @ c)
    se = float(np.sqrt(max(var, 0.0)))
    q = _t_quantil(1 - alpha / 2, fit["dof"])
    t_stat = delta / se if se > 0 else np.nan
    return {
        "t_ref": float(t_ref),
        "delta_kwh_m3": delta,
        "delta_se": se,
        "delta_ci": (delta - q * se, delta + q * se),
        "delta_p": _t_pwert(t_stat, fit["dof"]) if se > 0 else np.nan,
    }


#--------------------------------------------------------------------------
#Ueberdeckung der Temperaturbereiche
#--------------------------------------------------------------------------

def temperaturueberdeckung(tab: pd.DataFrame,
                           gruppe: str = "gruppe",
                           x: str = "t_out_tag",
                           t_ref: Optional[float] = None,
                           quantile: Sequence[float] = (0.05, 0.25, 0.5,
                                                        0.75, 0.95)
                           ) -> pd.DataFrame:
    """Verteilung der Aussentemperatur je Gruppe, plus Belegung bei `t_ref`.

    Decken die beiden Gruppen unterschiedliche Temperaturbereiche ab,
    vergleichen die zwei Regressionen unterschiedliche Abschnitte der
    x-Achse, und der Wert am Bezugspunkt ist fuer mindestens eine Gruppe
    extrapoliert statt gemessen. Die Spalte ``n_nahe_t_ref`` zaehlt die
    Tage im Band ±2 K um `t_ref`.
    """
    rows = []
    for name, teil in tab.groupby(gruppe, sort=False):
        werte = pd.to_numeric(teil[x], errors="coerce").dropna()
        row = {"gruppe": name, "n": int(len(werte)),
               "mittel": float(werte.mean()) if len(werte) else np.nan}
        for q in quantile:
            row[f"q{int(q * 100):02d}"] = (float(werte.quantile(q))
                                           if len(werte) else np.nan)
        if t_ref is not None and len(werte):
            nahe = werte.between(t_ref - 2.0, t_ref + 2.0)
            row["n_nahe_t_ref"] = int(nahe.sum())
            row["anteil_nahe_t_ref"] = float(nahe.mean())
            row["t_ref_im_bereich"] = bool(werte.min() <= t_ref <= werte.max())
        rows.append(row)
    return pd.DataFrame(rows)


#--------------------------------------------------------------------------
#Grafik
#--------------------------------------------------------------------------

def blasen_aggregat(tab: pd.DataFrame,
                    klassenbreite: float = 2.0,
                    x: str = "t_out_tag",
                    y: str = "performance",
                    groesse: str = "volumen_m3",
                    gruppe: str = "gruppe",
                    meter: str = "meter") -> pd.DataFrame:
    """Stationstage zu Blasen je Station und Temperaturklasse verdichten.

    Die Folie zeigt einige Dutzend Blasen, unsere Tagesreihe bringt
    Zehntausende Punkte, die als Streudiagramm nur noch eine Farbfläche
    ergeben. Hier wird deshalb je Station, Gruppe und Temperaturklasse
    ein Punkt gebildet: `x` ist die Klassenmitte, `y` das mit dem Volumen
    gewichtete Mittel der Kennzahl - also genau Energiesumme durch
    Volumensumme der Klasse - und `groesse` die Volumensumme.

    Das ist ausschliesslich eine Darstellungshilfe. Die Regression laeuft
    weiter auf den Tageswerten, weil die Verdichtung Stationen mit wenig
    Verbrauch dasselbe Gewicht gaebe wie Stationen mit viel.
    """
    w = tab.copy()
    w[x] = pd.to_numeric(w[x], errors="coerce")
    w[y] = pd.to_numeric(w[y], errors="coerce")
    w[groesse] = pd.to_numeric(w[groesse], errors="coerce")
    w = w.dropna(subset=[x, y, groesse])
    if len(w) == 0:
        return pd.DataFrame(columns=[meter, gruppe, x, y, groesse, "tage"])

    breite = float(klassenbreite)
    w["_klasse"] = np.floor(w[x] / breite) * breite + breite / 2.0
    w["_beitrag"] = w[y] * w[groesse]

    g = w.groupby([meter, gruppe, "_klasse"], sort=True, dropna=False)
    out = g.agg(_summe=("_beitrag", "sum"), _vol=(groesse, "sum"),
                tage=(y, "size")).reset_index()
    out = out[out["_vol"] > 0]
    out[y] = out["_summe"] / out["_vol"]
    out = out.rename(columns={"_klasse": x, "_vol": groesse})
    return out[[meter, gruppe, x, y, groesse, "tage"]].reset_index(drop=True)


def blasendiagramm(tab: pd.DataFrame,
                   fits: pd.DataFrame,
                   t_ref: float,
                   delta: Optional[dict] = None,
                   x: str = "t_out_tag",
                   y: str = "performance",
                   groesse: str = "volumen_m3",
                   gruppe: str = "gruppe",
                   titel: str = "Performance vor und nach der Begehung",
                   farben: Optional[Mapping[str, str]] = None,
                   ax=None):
    """Blasendiagramm mit beiden Regressionsgeraden im Stil der ÜZ-Folie.

    `fits` ist die Tabelle aus `regression_je_gruppe`, `delta` das
    Ergebnis von `delta_am_bezugspunkt`. Punktgroesse skaliert mit
    `groesse` (Tagesvolumen), beide Gruppen sind farblich getrennt. Die
    Geraden werden nur ueber den in der jeweiligen Gruppe belegten
    Temperaturbereich gezeichnet, damit die Grafik keine Extrapolation
    suggeriert, die die Daten nicht hergeben.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 6))
    stile = {GRUPPE_VOR: {"farbe": "#4b5bbf", "linie": "--"},
             GRUPPE_NACH: {"farbe": "#c62828", "linie": "-"}}
    if farben:
        for name, farbe in farben.items():
            stile.setdefault(name, {"farbe": farbe, "linie": "-"})
            stile[name]["farbe"] = farbe

    vol = pd.to_numeric(tab.get(groesse, pd.Series(dtype=float)),
                        errors="coerce")
    bezug = vol.quantile(0.95) if vol.notna().any() and vol.max() > 0 else None

    for name in fits["gruppe"]:
        teil = tab[tab[gruppe] == name]
        if len(teil) == 0:
            continue
        stil = stile.get(name, {"farbe": "#555555", "linie": "-"})
        if bezug and bezug > 0:
            s = 10 + 120 * (pd.to_numeric(teil[groesse], errors="coerce")
                            / bezug).clip(upper=1.5).fillna(0)
        else:
            s = 18
        ax.scatter(teil[x], teil[y], s=s, alpha=0.35,
                   color=stil["farbe"], edgecolors="none",
                   label=f"{name} (n = {len(teil)})")

        zeile = fits.loc[fits["gruppe"] == name].iloc[0]
        werte_x = pd.to_numeric(teil[x], errors="coerce").dropna()
        if len(werte_x) and pd.notna(zeile["steigung"]):
            xs = np.linspace(werte_x.min(), werte_x.max(), 50)
            ys = zeile["achsenabschnitt"] + zeile["steigung"] * xs
            ax.plot(xs, ys, stil["linie"], color=stil["farbe"], linewidth=2.2,
                    label=(f"{name}: y = {zeile['steigung']:.3f}x "
                           f"{zeile['achsenabschnitt']:+.2f}"))

    if delta is not None:
        ax.plot([t_ref, t_ref], [delta["y_vor"], delta["y_nach"]],
                color="black", linewidth=1.4)
        ax.annotate(
            f"Δ = {delta['delta_prozent']:.1f} %\n"
            f"Δy = {delta['delta_kwh_m3']:.2f} kWh/m³\n"
            f"bei {t_ref:.1f} °C",
            xy=(t_ref, (delta["y_vor"] + delta["y_nach"]) / 2),
            xytext=(12, 0), textcoords="offset points",
            va="center", fontsize=10,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="black", alpha=0.85))

    ax.set_xlabel("Außentemperatur (Tagesmittel) in °C")
    ax.set_ylabel("Performance in kWh/m³")
    ax.set_title(titel)
    ax.grid(alpha=0.25)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    return ax
