"""
Kennlinienüberwachung als labelfreie Anomalieerkennung.

Clustering, Regelschwellen und das überwachte Modell sind im Projekt
alle an derselben Stelle gescheitert: sie vergleichen Stationen
untereinander. Die Stationen sind dafür zu verschieden. Ein Haus mit
3 kW und ein Großabnehmer mit 150 kW teilen nur die Physik, deshalb
feuert `fault_detection.control_hysteresis` bei 95 Prozent der
Stationen und deshalb trennt kein k die Profile.

Dieses Modul dreht den Vergleich um. Die Kennlinie aus
`stationsbilder.kennlinienfit` ist ein Modell je Station:
log V = a + b · log P sagt für jede Stunde vorher, wie viel Wasser bei
der gerade gelieferten Leistung laufen sollte. Verglichen wird eine
Station also mit sich selbst. Das macht Schwellen übertragbar, weil
jede Station ihre eigene Streuung mitbringt, und es kommt ohne Labels
aus - der Flaschenhals des Projekts.

Zwei Kanäle
-----------
Der Parameterkanal fittet die Kennlinie rollierend über ein Fenster von
Tagen und beobachtet die Zeitreihe von Steigung, Bestimmtheitsmaß,
Residuenstreuung und Niveau. Ein Sprung in der Steigung ist ein
Ereignis, ein langsames Abdriften ein schleichender Defekt. Aus 24
Rohkanälen werden damit vier Zahlen je Tag.

Der Residuenkanal hält die Kennlinie einer Referenzperiode fest und
misst für jede Stunde die Abweichung davon. Er reagiert schneller, weil
er kein Fenster füllen muss, hängt dafür aber daran, dass die
Referenzperiode den gesunden Zustand beschreibt. Für die 26 Prozent
Stationen, die laut Vierfeldertafel durchgehend auffällig sind, trifft
das nicht zu; dort bleibt nur der Quervergleich über alle Stationen.

Warum das weitgehend witterungsunabhängig ist
---------------------------------------------
Die Leistung steht auf der x-Achse. Eine kalte Woche schiebt die Punkte
die Kennlinie entlang, ändert aber weder Steigung noch Achsenabschnitt.
An 69631918 liegt die Steigung über Winter, Übergang und Sommer
zwischen 1,06 und 1,14. Eine Witterungsbereinigung ist deshalb nicht
nötig, was ein Alarmsystem deutlich einfacher macht.

Validierung ohne Labels
-----------------------
Für 56 Zähler ist ein Begehungsdatum bekannt. Läuft der Monitor blind
über die Historie, lässt sich zählen, wie oft ein Alarm in die Nähe
eines bekannten Termins fällt. `zufallsbasis` rechnet dazu aus, welche
Trefferquote dieselbe Zahl zufällig gesetzter Alarme erreichen würde -
ohne diesen Vergleich ist die Trefferquote wertlos, weil viele Alarme
auf einer langen Historie irgendwann jeden Termin erwischen.

Was der Monitor nicht sieht
---------------------------
Ohne Durchfluss entsteht kein Punkt, Stillstand ist für die Kennlinie
unsichtbar. Eine fälschlich abgeschaltete Station fällt hier nicht auf;
dafür braucht es den Stillstandsanteil aus `stationsbilder.carpetmatrix`
als zweiten Kanal.

Wintervergleich: `wintervergleich` stellt für jede Begehung den
Kernwinter davor neben den Kernwinter danach. Sommer und Herbst bleiben
draußen, weil dort der Wärmebedarf zu gering ist, um die Kennlinie
belastbar zu schätzen. Die Kennzahlen kommen aus `netzvergleich`, damit
Netz- und Wintervergleich dieselben Größen messen.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd
from scipy import stats

from . import stationsbilder as sb
from . import ternaer as tn
from . import netzvergleich as nv

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


def _winterpunkte(tab: pd.DataFrame) -> tuple:
    """Betriebsstunden und ihr Kernwinterlabel (``""`` außerhalb)."""
    betrieb = nv.betriebsstunden(tab)
    return betrieb, nv.heizperiode(betrieb["zeit"])


def winterpaar(tab: pd.DataFrame,
               datum,
               min_stunden: int = nv.MIN_STUNDEN_WINTER,
               puffer_tage: int = tn.PUFFER_TAGE) -> dict:
    """Kernwinter vor und nach einer Begehung samt Stunden.

    Vorwinter ist der jüngste Kernwinter, der vor D - puffer mindestens
    ``min_stunden`` Betriebsstunden hat, Nachwinter der früheste, der sie
    nach D + puffer hat. Genutzt werden nur die Stunden auf der jeweiligen
    Seite. Liegt der Termin selbst im Winter, kann derselbe Winter auf
    beiden Seiten stehen, dann ist ``termin_im_winter`` gesetzt.
    """
    d = pd.Timestamp(datum).normalize()
    out = {"status": "ok", "winter_vor": "", "winter_nach": "",
           "termin_im_winter": bool(nv.heizperiode([d])[0] != ""),
           "teil_vor": None, "teil_nach": None}
    if tab is None or len(tab) == 0:
        out["status"] = "keine_daten"
        return out

    betrieb, w = _winterpunkte(tab)
    if len(betrieb) == 0:
        out["status"] = "keine_daten"
        return out
    zeit = pd.DatetimeIndex(pd.to_datetime(betrieb["zeit"]))
    im_winter = w != ""
    vor = np.asarray(zeit < d - pd.Timedelta(days=puffer_tage)) & im_winter
    nach = np.asarray(zeit >= d + pd.Timedelta(days=puffer_tage + 1)) & im_winter

    def waehle(maske, juengster):
        if not maske.any():
            return None, "leer"
        n = pd.Series(w[maske]).value_counts()
        n = n[n >= int(min_stunden)]
        if len(n) == 0:
            return None, "zu_wenig"
        labels = sorted(n.index, key=nv.winter_ende_jahr)
        return (labels[-1] if juengster else labels[0]), "ok"

    wv, sv = waehle(vor, True)
    wn, sn_ = waehle(nach, False)
    if wv is None:
        out["status"] = "kein_vorwinter" if sv == "leer" else "zu_wenig_punkte"
        return out
    if wn is None:
        out["status"] = "kein_nachwinter" if sn_ == "leer" else "zu_wenig_punkte"
        return out
    out.update({"winter_vor": wv, "winter_nach": wn,
                "teil_vor": betrieb[vor & (w == wv)],
                "teil_nach": betrieb[nach & (w == wn)]})
    return out


def residuum_kreuz(teil_vor: pd.DataFrame,
                   teil_nach: pd.DataFrame,
                   fit_vor: Mapping,
                   quantile: Sequence[float] = (0.05, 0.95)) -> tuple:
    """Medianresiduum der Nachher-Stunden gegen die Vorher-Kennlinie.

    Nur im gemeinsamen Leistungsbereich (Schnitt der 5-95-%-Bereiche von
    log P), damit keine Extrapolation der Vorher-Geraden in einen Bereich
    eingeht, den sie nie gesehen hat. Negativ heißt: nachher weniger
    Durchfluss bei gleicher Leistung. Zweiter Rückgabewert ist der Anteil
    der Nachher-Stunden im gemeinsamen Bereich.
    """
    lp_v = np.log(teil_vor["power_kw"].to_numpy(dtype=float))
    lp_n = np.log(teil_nach["power_kw"].to_numpy(dtype=float))
    lf_n = np.log(teil_nach["flow_lh"].to_numpy(dtype=float))
    if len(lp_v) == 0 or len(lp_n) == 0:
        return np.nan, 0.0
    lo = max(np.quantile(lp_v, quantile[0]), np.quantile(lp_n, quantile[0]))
    hi = min(np.quantile(lp_v, quantile[1]), np.quantile(lp_n, quantile[1]))
    if not lo < hi:
        return np.nan, 0.0
    m = (lp_n >= lo) & (lp_n <= hi)
    if not m.any():
        return np.nan, 0.0
    res = lf_n[m] - (fit_vor["achsenabschnitt"] + fit_vor["steigung"] * lp_n[m])
    return float(np.median(res)), float(m.mean())


VERGLEICH_KENNZAHLEN = tuple(nv.KENNZAHLEN) + tuple(nv.BESCHREIBEND)
VERGLEICH_SPALTEN = ("d_steigung", "d_spreizung_ref_k", "d_residuum_sd",
                     "d_rl_ueber_50_anteil", "d_flow_median_lh",
                     "flow_verhaeltnis", "d_flow_spez_lh_kw", "residuum_kreuz")
MIN_GRUPPE = 2
#Spalten, die jede Zeile des Wintervergleichs hat, auch ohne Ergebnis
GRUNDSPALTEN = ("meter", "datum", "status", "winter_vor", "winter_nach",
                "termin_im_winter", "weitere_begehung")


def _mit_spalten(df: pd.DataFrame, vorn: Sequence[str]) -> pd.DataFrame:
    """Fehlende Spalten als NaN ergänzen, vorhandene Reihenfolge bleibt."""
    return df.reindex(columns=list(dict.fromkeys(
        [*vorn, *df.columns, *VERGLEICH_SPALTEN])))


def _kreuzwerte(teil_vor: pd.DataFrame, teil_nach: pd.DataFrame,
                fit_vor: Mapping) -> dict:
    res, anteil = residuum_kreuz(teil_vor, teil_nach, fit_vor)
    return {"residuum_kreuz": res, "anteil_gemeinsam": anteil}


def _kreuz_ganze_winter(tab: Optional[pd.DataFrame], winter_vor: str,
                        winter_nach: str, min_stunden: int) -> dict:
    """Kreuzresiduum über zwei ganze Kernwinter, für die Kontrollgruppe.

    Fit wie im Wintervergleich über `netzvergleich.kennzahlen_punkte` auf
    den Betriebsstunden des Vorwinters.
    """
    leer = {"residuum_kreuz": np.nan, "anteil_gemeinsam": 0.0}
    if tab is None or len(tab) == 0:
        return leer
    betrieb, w = _winterpunkte(tab)
    tv, tn_ = betrieb[w == winter_vor], betrieb[w == winter_nach]
    fit_vor = nv.kennzahlen_punkte(tv, min_stunden=min_stunden)
    if fit_vor["status"] != "ok" or len(tn_) < int(min_stunden):
        return leer
    return _kreuzwerte(tv, tn_, fit_vor)


def _paarwerte(kv: Mapping, kn: Mapping) -> dict:
    z = {}
    for k in VERGLEICH_KENNZAHLEN:
        z[f"{k}_vor"], z[f"{k}_nach"] = kv[k], kn[k]
        z[f"d_{k}"] = kn[k] - kv[k]
    z["n_stunden_vor"], z["n_stunden_nach"] = kv["n_stunden"], kn["n_stunden"]
    vor = kv["flow_median_lh"]
    z["flow_verhaeltnis"] = kn["flow_median_lh"] / vor if vor > 0 else np.nan
    return z


def wintervergleich(punkte: Mapping[int, pd.DataFrame],
                    begehungen: Mapping,
                    anschlusswerte: Optional[Mapping] = None,
                    markiert: Optional[pd.DataFrame] = None,
                    heizgradstunden: Optional[pd.DataFrame] = None,
                    min_stunden: int = nv.MIN_STUNDEN_WINTER,
                    puffer_tage: int = tn.PUFFER_TAGE) -> pd.DataFrame:
    """Eine Zeile je Begehung: Kernwinter davor gegen Kernwinter danach.

    Volumenstrom steht als Hauptgröße in l/h vorn: Median vorher und
    nachher, Differenz, Verhältnis und der Durchfluss, den beide
    Kennlinien bei derselben Leistung (Median des Vorwinters) vorhersagen.
    Mit ``markiert`` aus `netzvergleich.markiere` kommen Netzrang und
    Auffälligkeit beider Winter dazu, mit ``heizgradstunden`` die
    Witterung. Der Rang bezieht sich auf den ganzen Winter, die
    Kennzahlen hier nur auf die Seite der Begehung.
    """
    aw = nv.int_schluessel(anschlusswerte)
    pkt = nv.int_schluessel(punkte)
    rang = None
    if markiert is not None and len(markiert):
        rang = markiert.assign(meter=markiert["meter"].astype(int)).set_index(
            ["meter", "winter"])[["rang", "auffaellig"]]
    hgs = {}
    if heizgradstunden is not None:
        hgs = dict(zip(heizgradstunden["winter"],
                       heizgradstunden["heizgradstunden"]))

    zeilen = []
    for meter, daten in nv.int_schluessel(begehungen).items():
        termine = sorted({pd.Timestamp(d).normalize() for d in daten})
        tab = pkt.get(meter)
        for d in termine:
            paar = winterpaar(tab, d, min_stunden=min_stunden,
                              puffer_tage=puffer_tage)
            z = {"meter": meter, "datum": d, "status": paar["status"],
                 "winter_vor": paar["winter_vor"],
                 "winter_nach": paar["winter_nach"],
                 "termin_im_winter": paar["termin_im_winter"],
                 "weitere_begehung": False}
            if paar["status"] != "ok":
                zeilen.append(z)
                continue
            tv, tn_ = paar["teil_vor"], paar["teil_nach"]
            start, ende = tv["zeit"].min(), tn_["zeit"].max()
            z["weitere_begehung"] = any(o != d and start <= o <= ende
                                        for o in termine)
            kv = nv.kennzahlen_punkte(tv, aw.get(meter), min_stunden=min_stunden)
            kn = nv.kennzahlen_punkte(tn_, aw.get(meter), min_stunden=min_stunden)
            if kv["status"] != "ok" or kn["status"] != "ok":
                z["status"] = kv["status"] if kv["status"] != "ok" else kn["status"]
                zeilen.append(z)
                continue
            z.update(_paarwerte(kv, kn))
            lp = np.log(kv["p_ref_kw"])
            z["p_ref_kw"] = kv["p_ref_kw"]
            z["flow_bei_pref_vor"] = float(np.exp(kv["achsenabschnitt"]
                                                  + kv["steigung"] * lp))
            z["flow_bei_pref_nach"] = float(np.exp(kn["achsenabschnitt"]
                                                   + kn["steigung"] * lp))
            z.update(_kreuzwerte(tv, tn_, kv))
            if rang is not None:
                for seite, w in (("vor", z["winter_vor"]),
                                 ("nach", z["winter_nach"])):
                    if (meter, w) in rang.index:
                        z[f"rang_{seite}"] = float(rang.loc[(meter, w), "rang"])
                        z[f"auffaellig_{seite}"] = bool(
                            rang.loc[(meter, w), "auffaellig"])
                    else:
                        z[f"rang_{seite}"] = np.nan
                        z[f"auffaellig_{seite}"] = np.nan
                z["d_rang"] = z["rang_nach"] - z["rang_vor"]
            z["heizgradstunden_vor"] = hgs.get(z["winter_vor"], np.nan)
            z["heizgradstunden_nach"] = hgs.get(z["winter_nach"], np.nan)
            zeilen.append(z)
    return _mit_spalten(pd.DataFrame(zeilen), GRUNDSPALTEN)


def winterdifferenz_kontrolle(tabelle: pd.DataFrame,
                              begehungen: Mapping,
                              winter_vor: str = "23/24",
                              winter_nach: str = "24/25",
                              *,
                              punkte: Optional[Mapping[int, pd.DataFrame]] = None,
                              min_stunden: int = nv.MIN_STUNDEN_WINTER,
                              ausschluss: Optional[Iterable] = None,
                              ) -> pd.DataFrame:
    """Dieselben Differenzen für Stationen ohne Begehung.

    ``tabelle`` ist die Ausgabe von `netzvergleich.winterkennzahlen`.
    Ohne diese Kontrollgruppe ließe sich ein Winterunterschied (kälter,
    anderes Nutzerverhalten) nicht von einer Wirkung der Begehung
    trennen. Mit ``punkte`` kommt das Kreuzresiduum dazu, gerechnet über
    die ganzen beiden Kernwinter; ohne bleibt es NaN. ``ausschluss`` nimmt
    die Zähler auf, deren Begehung ohne Datum in der Tabelle steht. Sie
    wurden begangen und gehören deshalb nicht in die Kontrollgruppe, wie
    in `fallsammlung.kontrollgruppe`.
    """
    mit = set(nv.int_schluessel(begehungen)) | {int(m) for m in ausschluss or ()}
    pkt = nv.int_schluessel(punkte)
    t = tabelle[~tabelle["meter"].astype(int).isin(mit)]
    a = t[t["winter"] == winter_vor].set_index("meter")
    b = t[t["winter"] == winter_nach].set_index("meter")
    zeilen = []
    for meter in sorted(set(a.index) & set(b.index)):
        z = {"meter": int(meter), "winter_vor": winter_vor,
             "winter_nach": winter_nach}
        z.update(_paarwerte(a.loc[meter], b.loc[meter]))
        if punkte is not None:
            z.update(_kreuz_ganze_winter(pkt.get(int(meter)), winter_vor,
                                         winter_nach, min_stunden))
        zeilen.append(z)
    return _mit_spalten(pd.DataFrame(zeilen),
                        ("meter", "winter_vor", "winter_nach"))


def gruppenvergleich(vergleich: pd.DataFrame,
                     kontrolle: pd.DataFrame,
                     spalten: Sequence[str] = VERGLEICH_SPALTEN,
                     paar: Optional[Sequence[str]] = ("23/24", "24/25"),
                     ) -> pd.DataFrame:
    """Begehungsfälle gegen Kontrollgruppe, Mann-Whitney zweiseitig.

    Mit ``paar`` gehen nur Begehungsfälle und Kontrollzeilen mit genau
    diesem Winterpaar ein, damit beide Gruppen dieselben zwei Winter
    vergleichen. Ein kleiner p-Wert ist ein Hinweis darauf, dass sich die
    Begehungsfälle anders entwickelt haben als der Rest des Netzes, kein
    Wirkungsnachweis.

    Hat eine Station mehrere Begehungen mit demselben Winterpaar, geht nur
    der früheste Termin ein. Sonst stünde dieselbe Station mehrfach im
    Test, und die Beobachtungen wären nicht unabhängig. ``n_begehung``
    zählt deshalb Stationen je Winterpaar, nicht Begehungen.
    """
    v = vergleich[vergleich["status"] == "ok"]
    k = kontrolle
    if paar is not None:
        v = v[(v["winter_vor"] == paar[0]) & (v["winter_nach"] == paar[1])]
        if {"winter_vor", "winter_nach"} <= set(k.columns):
            k = k[(k["winter_vor"] == paar[0]) & (k["winter_nach"] == paar[1])]
    schluessel = ["meter", "winter_vor", "winter_nach"]
    if set(schluessel) <= set(v.columns):
        if "datum" in v.columns:
            v = v.sort_values(["meter", "datum"], kind="stable")
        v = v.drop_duplicates(subset=schluessel, keep="first")
    zeilen = []
    for s in spalten:
        x = (pd.to_numeric(v[s], errors="coerce").dropna().to_numpy()
             if s in v.columns else np.array([]))
        y = (pd.to_numeric(k[s], errors="coerce").dropna().to_numpy()
             if s in k.columns else np.array([]))
        p = np.nan
        if len(x) >= MIN_GRUPPE and len(y) >= MIN_GRUPPE:
            p = float(stats.mannwhitneyu(x, y, alternative="two-sided")[1])
        zeilen.append({"spalte": s, "n_begehung": len(x),
                       "median_begehung": float(np.median(x)) if len(x) else np.nan,
                       "n_kontrolle": len(y),
                       "median_kontrolle": float(np.median(y)) if len(y) else np.nan,
                       "p_mw": p})
    return pd.DataFrame(zeilen)
