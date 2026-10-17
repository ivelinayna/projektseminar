"""
Kennlinienüberwachung als labelfreie Anomalieerkennung.

Idee: nicht Stationen untereinander vergleichen (dafür sind sie zu
verschieden), sondern jede Station mit sich selbst. Die Kennlinie aus
`stationsbilder.kennlinienfit` ist das Modell je Station:
log V = a + b · log P sagt, wie viel Wasser bei der aktuellen Leistung
laufen sollte. Das braucht keine Labels.

Zwei Kanäle
-----------
Parameterkanal:
- Kennlinie rollierend über ein Fenster von Tagen
- beobachtet Steigung, R², Residuenstreuung und Niveau über die Zeit
- Sprung in der Steigung = Ereignis, langsames Abdriften = schleichender
  Defekt

Residuenkanal:
- feste Kennlinie einer Referenzperiode, Abweichung je Stunde
- reagiert schneller, braucht aber eine gesunde Referenzperiode
- bei durchgehend auffälligen Stationen funktioniert das nicht, dort
  bleibt nur der Quervergleich

Witterung
---------
Die Leistung steht auf der x-Achse. Eine kalte Woche schiebt die Punkte
die Kennlinie entlang, ändert aber weder Steigung noch Achsenabschnitt.
Eine Witterungsbereinigung ist deshalb nicht nötig.

Validierung
-----------
- der Monitor läuft blind über die Historie, gezählt wird, wie oft ein
  Alarm in die Nähe eines Begehungstermins fällt
- `zufallsbasis` rechnet aus, welche Trefferquote gleich viele zufällig
  gesetzte Alarme erreichen würden

Grenzen
-------
Stillstand ist unsichtbar (kein Durchfluss, kein Punkt). Dafür braucht
es den Stillstandsanteil aus `stationsbilder.carpetmatrix`.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import stationsbilder as sb
from . import ternaer as tn

#Fensterbreite fuer den rollierenden Fit. 14 Tage wie in
#window_features.py, damit die Fenster zwischen den Modulen vergleichbar
#bleiben. Kuerzer wird die Steigung unruhig, laenger verschmiert der
#Sprung.
FENSTER_TAGE = 14
SCHRITT_TAGE = 1

#Obergrenze, auf die ein Fenster gedehnt werden darf, wenn 14 Tage nicht
#genug Betriebsstunden enthalten. Ohne diese Dehnung ist der Monitor im
#Sommer blind: 68956351 laeuft im Juli nur knapp zwei Stunden am Tag,
#ein starres 14-Tage-Fenster kommt dort nie auf 30 Punkte - und genau in
#diese Luecke faellt der bekannte Reparaturtermin im September.
MAX_FENSTER_TAGE = 60

MIN_PUNKTE = sb.MIN_PUNKTE

#Mindestzahl Betriebsstunden an einem Tag, damit der Tagesmedian des
#Residuums gebildet wird. Darunter schwankt er zu stark.
MIN_STUNDEN_TAG = 3

#Schwelle fuer den Sprungscore. Der Score ist robust z-artig normiert,
#3 entspricht also grob drei Standardabweichungen der taeglichen
#Veraenderung. Gesetzt, nicht hergeleitet.
ALARM_SCHWELLE = 3.0

#Zwei Alarme naeher beieinander beschreiben dasselbe Ereignis.
MINDESTABSTAND_TAGE = 30

#Fenster, in dem ein Alarm als Treffer fuer einen Begehungstermin gilt.
TOLERANZ_TAGE = 30

PARAMETER = ("steigung",)

QUELLE_PARAMETER = "parameter"
QUELLE_RESIDUUM = "residuum"

FENSTER_SPALTEN = ["datum", "n", "breite_tage", "steigung",
                   "achsenabschnitt", "r2", "residuum_sd",
                   "power_median_kw", "flow_median_lh",
                   "dt_median_k", "rt_median_c"]


def _ordinal(werte) -> np.ndarray:
    """Kalendertag als fortlaufende ganze Zahl."""
    idx = pd.DatetimeIndex(pd.to_datetime(werte)).normalize()
    return (idx - pd.Timestamp("1970-01-01")).days.to_numpy()


def _datum(ordinale) -> pd.DatetimeIndex:
    return pd.Timestamp("1970-01-01") + pd.to_timedelta(
        np.asarray(ordinale, dtype="int64"), unit="D")


def _arrays(tab: pd.DataFrame) -> dict:
    """Punkttabelle in sortierte Arrays umbauen, Filter einmal anwenden.

    Derselbe Filter wie in `stationsbilder.kennlinienfit`: nur Stunden
    mit positiver Leistung, positivem Durchfluss und positiver
    Spreizung. Danach sind alle Fensterausschnitte schon sauber und der
    Fit im Fenster kostet nur noch ein paar Vektoroperationen.
    """
    leer = {"ordinal": np.zeros(0, dtype="int64"), "lp": np.zeros(0),
            "lf": np.zeros(0), "power": np.zeros(0), "flow": np.zeros(0),
            "dt": np.zeros(0), "rt": np.zeros(0),
            "zeit": pd.DatetimeIndex([])}
    if len(tab) == 0:
        return leer
    for spalte in ("power_kw", "flow_lh", "dt_k"):
        if spalte not in tab.columns:
            return leer

    maske = ((tab["power_kw"] > 0) & (tab["flow_lh"] > 0)
             & (tab["dt_k"] > 0)).fillna(False)
    teil = tab[maske]
    if len(teil) == 0:
        return leer

    zeitspalte = "zeit" if "zeit" in teil.columns else "datum"
    zeit = pd.DatetimeIndex(pd.to_datetime(teil[zeitspalte]))
    reihenfolge = np.argsort(zeit.to_numpy(), kind="stable")
    teil = teil.iloc[reihenfolge]
    zeit = zeit[reihenfolge]

    power = teil["power_kw"].to_numpy(dtype=float)
    flow = teil["flow_lh"].to_numpy(dtype=float)
    rt = (teil["rt_c"].to_numpy(dtype=float) if "rt_c" in teil.columns
          else np.full(len(teil), np.nan))
    return {"ordinal": _ordinal(zeit), "lp": np.log(power),
            "lf": np.log(flow), "power": power, "flow": flow,
            "dt": teil["dt_k"].to_numpy(dtype=float), "rt": rt,
            "zeit": zeit}


def _fit(lp: np.ndarray, lf: np.ndarray, min_punkte: int) -> dict:
    """Ausgleichsgerade auf vorbereiteten Arrays.

    Rechnet dasselbe wie `stationsbilder.kennlinienfit`, nimmt aber
    Arrays statt einer Tabelle entgegen. Ein Test hält fest, dass beide
    auf denselben Daten dasselbe liefern.
    """
    leer = {"steigung": np.nan, "achsenabschnitt": np.nan, "r2": np.nan,
            "residuum_sd": np.nan, "n": int(len(lp))}
    if len(lp) < int(min_punkte):
        return leer
    var_p = float(np.var(lp))
    if not np.isfinite(var_p) or var_p <= 1e-12:
        return leer

    steigung = float(np.mean((lp - lp.mean()) * (lf - lf.mean())) / var_p)
    achsenabschnitt = float(lf.mean() - steigung * lp.mean())
    residuen = lf - (achsenabschnitt + steigung * lp)
    var_f = float(np.var(lf))
    r2 = float(1.0 - np.var(residuen) / var_f) if var_f > 1e-12 else np.nan
    return {"steigung": steigung, "achsenabschnitt": achsenabschnitt,
            "r2": r2, "residuum_sd": float(np.std(residuen)),
            "n": int(len(lp))}


def fensterreihe(tab: pd.DataFrame,
                 fenster_tage: int = FENSTER_TAGE,
                 schritt_tage: int = SCHRITT_TAGE,
                 min_punkte: int = MIN_PUNKTE,
                 max_fenster_tage: int = MAX_FENSTER_TAGE) -> pd.DataFrame:
    """Kennlinienparameter über ein gleitendes Fenster.

    Eine Zeile je Fenster, datiert auf den letzten Tag des Fensters.
    Das Raster ist lückenlos: Fenster ohne genug Betriebsstunden
    erscheinen mit ``n`` und leeren Parametern, damit die Zeitreihe
    gleichmäßig bleibt und die Sprungerkennung darauf rechnen kann.

    Die Breite ist nicht starr. Reichen ``fenster_tage`` nicht für
    ``min_punkte`` Betriebsstunden, wird das Fenster nach hinten gedehnt,
    höchstens auf ``max_fenster_tage``. Im Winter bleibt es damit bei 14
    Tagen und der Sprung bleibt scharf datiert, im Sommer liefert es
    überhaupt erst einen Wert. Die tatsächlich benutzte Breite steht in
    ``breite_tage``.
    """
    arr = _arrays(tab)
    if len(arr["ordinal"]) == 0:
        return pd.DataFrame(columns=FENSTER_SPALTEN)

    breite = max(int(fenster_tage), 1)
    maxbreite = max(int(max_fenster_tage), breite)
    schritt = max(int(schritt_tage), 1)
    ord_min = int(arr["ordinal"][0])
    ord_max = int(arr["ordinal"][-1])
    enden = np.arange(ord_min + breite - 1, ord_max + 1, schritt,
                      dtype="int64")
    if len(enden) == 0:
        enden = np.array([ord_max], dtype="int64")

    links = np.searchsorted(arr["ordinal"], enden - breite + 1, side="left")
    frueheste = np.searchsorted(arr["ordinal"], enden - maxbreite + 1,
                                side="left")
    rechts = np.searchsorted(arr["ordinal"], enden, side="right")
    #gedehnt wird nur so weit, wie min_punkte es verlangen
    gedehnt = np.maximum(frueheste, rechts - int(min_punkte))
    links = np.minimum(links, gedehnt)

    zeilen = []
    for ende, a, b in zip(enden, links, rechts):
        fit = _fit(arr["lp"][a:b], arr["lf"][a:b], min_punkte)
        zeile = {"datum": ende, "n": fit["n"], "steigung": fit["steigung"],
                 "achsenabschnitt": fit["achsenabschnitt"], "r2": fit["r2"],
                 "residuum_sd": fit["residuum_sd"]}
        if b > a:
            zeile["breite_tage"] = int(ende - int(arr["ordinal"][a]) + 1)
            zeile["power_median_kw"] = float(np.median(arr["power"][a:b]))
            zeile["flow_median_lh"] = float(np.median(arr["flow"][a:b]))
            zeile["dt_median_k"] = float(np.median(arr["dt"][a:b]))
            with np.errstate(invalid="ignore"):
                zeile["rt_median_c"] = float(np.nanmedian(arr["rt"][a:b])) \
                    if np.isfinite(arr["rt"][a:b]).any() else np.nan
        else:
            zeile["breite_tage"] = breite
            for spalte in ("power_median_kw", "flow_median_lh",
                           "dt_median_k", "rt_median_c"):
                zeile[spalte] = np.nan
        zeilen.append(zeile)

    out = pd.DataFrame(zeilen)
    out["datum"] = _datum(out["datum"].to_numpy())
    return out[FENSTER_SPALTEN]


def referenzfit(tab: pd.DataFrame,
                referenz_tage: Optional[int] = None,
                bis=None,
                min_punkte: int = MIN_PUNKTE) -> dict:
    """Kennlinie der Referenzperiode, gegen die später gemessen wird.

    Ohne Argumente wird die gesamte Historie benutzt. Das ist die
    ehrlichste Voreinstellung, solange niemand weiß, wann eine Station
    gesund war; der Preis ist, dass ein langer Defekt die Referenz
    mitprägt und das Residuum dann klein bleibt. ``referenz_tage``
    schneidet stattdessen die ersten Tage der Historie heraus, ``bis``
    endet an einem festen Datum.
    """
    if len(tab) == 0:
        return _fit(np.zeros(0), np.zeros(0), min_punkte)
    arr = _arrays(tab)
    if len(arr["ordinal"]) == 0:
        return _fit(np.zeros(0), np.zeros(0), min_punkte)

    maske = np.ones(len(arr["ordinal"]), dtype=bool)
    if referenz_tage is not None:
        grenze = int(arr["ordinal"][0]) + int(referenz_tage) - 1
        maske &= arr["ordinal"] <= grenze
    if bis is not None:
        maske &= arr["ordinal"] <= int(_ordinal([bis])[0])
    return _fit(arr["lp"][maske], arr["lf"][maske], min_punkte)


def stundenresiduum(tab: pd.DataFrame, fit: Mapping) -> pd.DataFrame:
    """Abweichung jeder Betriebsstunde von der Referenzkennlinie.

    Das Residuum ist log(gemessener Durchfluss) minus
    log(erwarteter Durchfluss). Positiv heißt, die Station zieht mehr
    Wasser als ihre eigene Kennlinie erwarten lässt - das Muster eines
    offenen Ventils. Weil in Logarithmen gerechnet wird, ist der Wert
    einheitenlos und zwischen Stationen vergleichbar: 0,69 entspricht
    dem Faktor 2.
    """
    spalten = ["zeit", "datum", "residuum"]
    if not np.isfinite(float(fit.get("steigung", np.nan))):
        return pd.DataFrame(columns=spalten)
    arr = _arrays(tab)
    if len(arr["ordinal"]) == 0:
        return pd.DataFrame(columns=spalten)

    erwartet = fit["achsenabschnitt"] + fit["steigung"] * arr["lp"]
    out = pd.DataFrame({"zeit": arr["zeit"],
                        "datum": _datum(arr["ordinal"]),
                        "residuum": arr["lf"] - erwartet})
    return out


def tagesresiduum(residuen: pd.DataFrame,
                  min_stunden: int = MIN_STUNDEN_TAG) -> pd.DataFrame:
    """Tagesmedian des Residuums auf lückenlosem Kalenderraster.

    Der Median statt des Mittels, damit einzelne Ausreißerstunden den
    Tag nicht kippen. Tage mit zu wenig Betriebsstunden bleiben leer
    statt geschätzt; das Raster selbst bleibt vollständig, damit die
    Sprungerkennung Abstände richtig zählt.
    """
    spalten = ["datum", "n", "residuum_median", "residuum_streuung"]
    if len(residuen) == 0:
        return pd.DataFrame(columns=spalten)

    ordinal = _ordinal(residuen["datum"])
    werte = residuen["residuum"].to_numpy(dtype=float)
    tab = pd.DataFrame({"ordinal": ordinal, "residuum": werte})
    g = tab.groupby("ordinal")["residuum"]
    roh = pd.DataFrame({"n": g.size(), "residuum_median": g.median(),
                        "residuum_streuung": g.std()})

    raster = np.arange(int(ordinal.min()), int(ordinal.max()) + 1,
                       dtype="int64")
    roh = roh.reindex(raster)
    roh["n"] = roh["n"].fillna(0).astype(int)
    zu_duenn = roh["n"] < int(min_stunden)
    roh.loc[zu_duenn, ["residuum_median", "residuum_streuung"]] = np.nan

    out = roh.reset_index(names="ordinal")
    out["datum"] = _datum(out["ordinal"].to_numpy())
    return out[spalten]


def sprungscore(werte,
                fenster_tage: int = FENSTER_TAGE,
                min_seite: Optional[int] = None,
                max_abstand_tage: int = MAX_FENSTER_TAGE) -> np.ndarray:
    """Robuster Sprungscore auf einer täglichen Zeitreihe.

    Für jeden Tag wird der Median der nächstgelegenen Werte danach gegen
    den Median der nächstgelegenen Werte davor gestellt. Diese Differenz
    wird durch ihre eigene robuste Streuung geteilt, gemessen als
    mittlere absolute Abweichung über die ganze Reihe. Der Score ist
    damit z-artig und ohne Annahme über die Verteilung: ein Wert von 3
    heißt, der Sprung ist dreimal so groß wie die übliche Schwankung
    dieser Station.

    Nicht die Werte eines starren Zeitfensters, sondern die ``min_seite``
    nächstgelegenen vorhandenen Werte werden verglichen, und zwar nur
    innerhalb von ``max_abstand_tage``. Sonst fällt der Score genau dort
    aus, wo eine Station wenig läuft - im Sommer -, und übersieht
    Sprünge am Rand der Heizperiode.

    Bewusst kein Mittelwert und keine Standardabweichung, weil beide
    auf genau die Ausreißer reagieren, die hier gefunden werden sollen.
    Die Reihe muss auf einem lückenlosen Tagesraster liegen; fehlende
    Werte dürfen NaN sein.
    """
    reihe = np.asarray(werte, dtype=float)
    breite = max(int(fenster_tage), 1)
    mindest = int(min_seite) if min_seite is not None else max(breite // 2, 1)
    grenze = max(int(max_abstand_tage), breite)
    diff = np.full(len(reihe), np.nan)
    if len(reihe) == 0:
        return diff

    da = np.where(np.isfinite(reihe))[0]
    if len(da) < 2 * mindest:
        return diff

    for i in range(len(reihe)):
        pos = int(np.searchsorted(da, i, side="left"))
        vor = da[max(pos - mindest, 0):pos]
        nach = da[pos:pos + mindest]
        if len(vor) < mindest or len(nach) < mindest:
            continue
        if i - int(vor[0]) > grenze or int(nach[-1]) - i > grenze:
            continue
        diff[i] = float(np.median(reihe[nach]) - np.median(reihe[vor]))

    endlich = diff[np.isfinite(diff)]
    if len(endlich) < 3:
        return np.full(len(reihe), np.nan)
    streuung = float(np.median(np.abs(endlich - np.median(endlich))))
    if streuung <= 1e-12:
        streuung = float(np.std(endlich))
    if streuung <= 1e-12:
        return np.full(len(reihe), np.nan)
    return diff / (1.4826 * streuung)


def alarme(datum,
           score,
           schwelle: float = ALARM_SCHWELLE,
           mindestabstand_tage: int = MINDESTABSTAND_TAGE) -> pd.DataFrame:
    """Lokale Maxima des Sprungscores oberhalb der Schwelle.

    Zwei Tage nebeneinander beschreiben denselben Sprung, deshalb wird
    der stärkste Tag genommen und seine Nachbarschaft unterdrückt.
    """
    spalten = ["datum", "score", "richtung"]
    werte = np.asarray(score, dtype=float)
    tage = pd.DatetimeIndex(pd.to_datetime(datum))
    kandidaten = np.where(np.isfinite(werte)
                          & (np.abs(werte) >= float(schwelle)))[0]
    if len(kandidaten) == 0:
        return pd.DataFrame(columns=spalten)

    ordinal = _ordinal(tage)
    kandidaten = kandidaten[np.argsort(-np.abs(werte[kandidaten]))]
    gewaehlt = []
    for i in kandidaten:
        if all(abs(int(ordinal[i]) - int(ordinal[j])) >= int(mindestabstand_tage)
               for j in gewaehlt):
            gewaehlt.append(i)

    gewaehlt.sort()
    return pd.DataFrame({
        "datum": tage[gewaehlt],
        "score": werte[gewaehlt],
        "richtung": np.where(werte[gewaehlt] > 0, "hoch", "runter"),
    })


def monitor_station(df: pd.DataFrame,
                    meter: int,
                    fenster_tage: int = FENSTER_TAGE,
                    min_punkte: int = MIN_PUNKTE,
                    referenz_tage: Optional[int] = None,
                    parameter: Sequence[str] = PARAMETER,
                    schwelle: float = ALARM_SCHWELLE,
                    mindestabstand_tage: int = MINDESTABSTAND_TAGE,
                    min_stunden: int = MIN_STUNDEN_TAG) -> dict:
    """Beide Kanäle für eine Station rechnen.

    Rückgabe mit ``fenster`` (Parameterzeitreihe samt Score je
    beobachtetem Parameter), ``residuum`` (Tagesreihe samt Score),
    ``alarme`` (beide Kanäle in einer Tabelle) und ``abdeckung``
    (erster und letzter Tag, Zahl der Kalendertage).
    """
    tab = sb.punkttabelle(df, meter, aufloesung="stunde")

    fenster = fensterreihe(tab, fenster_tage=fenster_tage,
                           min_punkte=min_punkte)
    stuecke = []
    for name in parameter:
        if name not in fenster.columns:
            raise ValueError(f"unbekannter Parameter: {name}")
        spalte = f"score_{name}"
        fenster[spalte] = (sprungscore(fenster[name].to_numpy(dtype=float),
                                       fenster_tage=fenster_tage)
                           if len(fenster) else np.zeros(0))
        if len(fenster):
            teil = alarme(fenster["datum"], fenster[spalte],
                          schwelle=schwelle,
                          mindestabstand_tage=mindestabstand_tage)
            teil.insert(0, "quelle", QUELLE_PARAMETER)
            teil.insert(1, "kennzahl", name)
            stuecke.append(teil)

    fit = referenzfit(tab, referenz_tage=referenz_tage, min_punkte=min_punkte)
    tagesreihe = tagesresiduum(stundenresiduum(tab, fit),
                               min_stunden=min_stunden)
    if len(tagesreihe):
        tagesreihe["score_residuum"] = sprungscore(
            tagesreihe["residuum_median"].to_numpy(dtype=float),
            fenster_tage=fenster_tage)
        teil = alarme(tagesreihe["datum"], tagesreihe["score_residuum"],
                      schwelle=schwelle,
                      mindestabstand_tage=mindestabstand_tage)
        teil.insert(0, "quelle", QUELLE_RESIDUUM)
        teil.insert(1, "kennzahl", "residuum_median")
        stuecke.append(teil)

    alarmtabelle = (pd.concat(stuecke, ignore_index=True) if stuecke
                    else pd.DataFrame(columns=["quelle", "kennzahl", "datum",
                                               "score", "richtung"]))
    alarmtabelle.insert(0, "meter", int(meter))

    quelle_tage = pd.concat([
        pd.Series(fenster["datum"] if len(fenster) else [], dtype="datetime64[ns]"),
        pd.Series(tagesreihe["datum"] if len(tagesreihe) else [], dtype="datetime64[ns]"),
    ])
    if len(quelle_tage):
        erster, letzter = quelle_tage.min(), quelle_tage.max()
        tage = int((letzter - erster).days) + 1
    else:
        erster = letzter = pd.NaT
        tage = 0
    abdeckung = pd.DataFrame([{"meter": int(meter), "erster_tag": erster,
                               "letzter_tag": letzter, "tage": tage,
                               "referenz_n": int(fit.get("n", 0)),
                               "referenz_steigung": fit.get("steigung",
                                                            np.nan)}])

    for frame in (fenster, tagesreihe):
        if len(frame):
            frame.insert(0, "meter", int(meter))
    return {"fenster": fenster, "residuum": tagesreihe,
            "alarme": alarmtabelle, "abdeckung": abdeckung}


def monitor_alle(serien: Mapping[int, pd.DataFrame],
                 fortschritt: bool = False,
                 **kwargs) -> Dict[str, pd.DataFrame]:
    """`monitor_station` über alle Stationen, Ergebnisse gestapelt."""
    teile: Dict[str, list] = {"fenster": [], "residuum": [], "alarme": [],
                              "abdeckung": []}
    gesamt = len(serien)
    for i, (meter, df) in enumerate(sorted(serien.items()), start=1):
        ergebnis = monitor_station(df, int(meter), **kwargs)
        for schluessel, frame in ergebnis.items():
            if len(frame):
                teile[schluessel].append(frame)
        if fortschritt and (i % 10 == 0 or i == gesamt):
            print(f"{i}/{gesamt} Stationen")

    out = {}
    for schluessel, liste in teile.items():
        out[schluessel] = (pd.concat(liste, ignore_index=True) if liste
                           else pd.DataFrame())
    return out


def validiere(alarmtabelle: pd.DataFrame,
              begehungsdatum: Mapping[int, object],
              toleranz_tage: int = TOLERANZ_TAGE) -> pd.DataFrame:
    """Alarme gegen die bekannten Begehungstermine halten.

    Eine Zeile je Station, Quelle und Termin. ``abstand_tage`` ist der
    Abstand des nächstgelegenen Alarms, positiv wenn der Alarm nach dem
    Termin liegt. Stationen ohne Alarm in dieser Quelle erscheinen mit
    leerem Abstand und ``treffer`` auf False, damit sie nicht still aus
    der Quote fallen.
    """
    spalten = ["meter", "quelle", "kennzahl", "begehung", "alarm",
               "abstand_tage", "score", "richtung", "treffer"]
    if len(alarmtabelle) == 0:
        return pd.DataFrame(columns=spalten)

    paare = alarmtabelle[["quelle", "kennzahl"]].drop_duplicates()
    zeilen = []
    for meter, roh in begehungsdatum.items():
        termine = roh if isinstance(roh, (list, tuple, set, pd.Series)) else [roh]
        for termin in termine:
            t = pd.Timestamp(pd.to_datetime(termin)).normalize()
            for _, paar in paare.iterrows():
                teil = alarmtabelle[
                    (alarmtabelle["meter"] == int(meter))
                    & (alarmtabelle["quelle"] == paar["quelle"])
                    & (alarmtabelle["kennzahl"] == paar["kennzahl"])]
                zeile = {"meter": int(meter), "quelle": paar["quelle"],
                         "kennzahl": paar["kennzahl"], "begehung": t,
                         "alarm": pd.NaT, "abstand_tage": np.nan,
                         "score": np.nan, "richtung": None, "treffer": False}
                if len(teil):
                    abstand = (pd.DatetimeIndex(teil["datum"]).normalize()
                               - t).days.to_numpy()
                    i = int(np.argmin(np.abs(abstand)))
                    zeile["alarm"] = pd.Timestamp(teil["datum"].iloc[i])
                    zeile["abstand_tage"] = int(abstand[i])
                    zeile["score"] = float(teil["score"].iloc[i])
                    zeile["richtung"] = teil["richtung"].iloc[i]
                    zeile["treffer"] = bool(abs(abstand[i]) <= int(toleranz_tage))
                zeilen.append(zeile)
    return pd.DataFrame(zeilen, columns=spalten)


def zufallsbasis(alarmtabelle: pd.DataFrame,
                 abdeckung: pd.DataFrame,
                 begehungsdatum: Mapping[int, object],
                 toleranz_tage: int = TOLERANZ_TAGE) -> pd.DataFrame:
    """Trefferquote, die zufällig gesetzte Alarme erreichen würden.

    Je Station deckt ein Alarm ein Fenster von 2·Toleranz + 1 Tagen ab.
    Bei k zufällig über die Historie verteilten Alarmen liegt die
    Wahrscheinlichkeit, einen festen Termin zu treffen, bei
    1 − (1 − Fenster/Historie)^k. Der Mittelwert über alle Stationen ist
    die Quote, die der Monitor schlagen muss, um überhaupt etwas zu
    zeigen.
    """
    spalten = ["quelle", "kennzahl", "stationen", "alarme_je_station",
               "erwartete_quote"]
    if len(alarmtabelle) == 0 or len(abdeckung) == 0:
        return pd.DataFrame(columns=spalten)

    tage = abdeckung.set_index("meter")["tage"].to_dict()
    fenster = 2 * int(toleranz_tage) + 1
    zeilen = []
    for (quelle, kennzahl), teil in alarmtabelle.groupby(["quelle",
                                                          "kennzahl"]):
        anzahl = teil.groupby("meter").size().to_dict()
        wahrscheinlich, k_je = [], []
        for meter in begehungsdatum:
            historie = int(tage.get(int(meter), 0))
            if historie <= fenster:
                continue
            k = int(anzahl.get(int(meter), 0))
            k_je.append(k)
            wahrscheinlich.append(1.0 - (1.0 - fenster / historie) ** k)
        if not wahrscheinlich:
            continue
        zeilen.append({"quelle": quelle, "kennzahl": kennzahl,
                       "stationen": len(wahrscheinlich),
                       "alarme_je_station": float(np.mean(k_je)),
                       "erwartete_quote": float(np.mean(wahrscheinlich))})
    return pd.DataFrame(zeilen, columns=spalten)


def trefferquote(pruefung: pd.DataFrame) -> pd.DataFrame:
    """Treffer je Quelle zusammenfassen."""
    spalten = ["quelle", "kennzahl", "faelle", "treffer", "quote",
               "median_abstand_tage"]
    if len(pruefung) == 0:
        return pd.DataFrame(columns=spalten)
    zeilen = []
    for (quelle, kennzahl), teil in pruefung.groupby(["quelle", "kennzahl"]):
        getroffen = teil[teil["treffer"]]
        zeilen.append({
            "quelle": quelle, "kennzahl": kennzahl, "faelle": int(len(teil)),
            "treffer": int(len(getroffen)),
            "quote": float(len(getroffen) / len(teil)),
            "median_abstand_tage": (float(getroffen["abstand_tage"].abs()
                                          .median())
                                    if len(getroffen) else np.nan),
        })
    return pd.DataFrame(zeilen, columns=spalten)
