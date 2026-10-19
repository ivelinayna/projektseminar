"""
Dynamikkennzahlen der Ruecklauftemperatur.

Bisher beschreiben `features.py` und `clustervalidierung.py` ein
Niveau: wie warm ist der Ruecklauf, wie gross ist die Spreizung, wie
haeufig steht die Station still. Aus dem Betreuermeeting stammt der
Hinweis, dass der Weg zu benennbaren Fehlern ueber die Aenderung
laeuft und nicht ueber das Niveau. Ein festsitzendes oder dauerhaft
offenes Ventil und ein zerschossener Regler sind daran zu erkennen,
wie schnell sich der Ruecklauf aendert und wie schnell sich diese
Aenderung selbst aendert; Regelparameter haben dagegen nur geringen
wahrnehmbaren Einfluss.

Was hier gerechnet wird
-----------------------
`ableitungen` bildet die erste Ableitung in K je Stunde und die zweite
in K je Stunde im Quadrat. `tagesdynamik` verdichtet beides auf einen
Kalendertag, zusammen mit der Kopplung zwischen Vor- und Ruecklauf und
dem Anteil der Laststunden, in denen sich der Ruecklauf praktisch
nicht bewegt. `lastwechsel` sucht Lastspruenge und misst, wie lange
der Ruecklauf braucht, bis er den Grossteil seiner Reaktion hinter
sich hat.

Messluecken
-----------
Eine Ableitung ueber eine Luecke hinweg ist Unsinn: zwischen zwei
Messpunkten im Abstand von drei Tagen steht keine Aenderung je Stunde,
sondern ein Mittelwert ueber alles, was dazwischen passiert ist. Jede
Differenz wird deshalb nur gebildet, wenn der Abstand zum Vorgaenger
hoechstens `MAX_SCHRITT_H` betraegt, und sie wird durch den
tatsaechlichen Abstand geteilt statt durch die nominelle Stunde. Die
zweite Ableitung braucht zusaetzlich, dass auch das vorangehende
Intervall gueltig war. Verworfene Stellen werden NaN, nicht 0 - eine
0 waere die Aussage "keine Aenderung" und damit falsch.

Vorzeichen
----------
Die Kennzahlen arbeiten durchweg mit Betraegen. Ob der Ruecklauf
gerade steigt oder faellt, ist fuer die Frage nach der Beweglichkeit
der Station ohne Belang; interessant ist, wie weit er sich ueberhaupt
bewegt.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd

#Maximaler Abstand zweier Messpunkte, zwischen denen noch differenziert
#wird. Der UEZ-Export steht nominell stuendlich, einzelne Minutenversaetze
#und eine ausgefallene Stunde bleiben damit drin, eine echte Luecke nicht.
MAX_SCHRITT_H = 1.5

#Leistungsschwelle "unter Last", identisch zu features.features_for_meter
LAST_SCHWELLE_KW = 0.5

#Unterhalb dieser Aenderungsrate gilt der Ruecklauf als stehend. 0,05 K/h
#sind bei stuendlicher Abtastung rund die Aufloesung der Temperaturkanaele.
TRAEGE_SCHWELLE_K_H = 0.05

#Mindestzahl Stunden, aus denen eine Tageskennzahl gebildet wird
MIN_STUNDEN_TAG = 12

#Lastsprung, ab dem ein Lastwechsel als solcher zaehlt, in kW
MIN_SPRUNG_KW = 1.0

#Fenster nach einem Lastsprung, in dem die Reaktion gesucht wird
REAKTIONSFENSTER_H = 6

#Anteil der Gesamtreaktion, der als "Grossteil" gilt (Zeitkonstante eines
#Systems erster Ordnung)
REAKTIONSANTEIL = 0.63


def _schrittweite(index: pd.DatetimeIndex) -> pd.Series:
    """Abstand zum jeweiligen Vorgaenger in Stunden, erste Zeile NaN."""
    idx = pd.DatetimeIndex(index)
    return pd.Series(idx, index=idx).diff().dt.total_seconds() / 3600.0


def ableitungen(df: pd.DataFrame,
                spalten: Sequence[str] = ("rt",),
                max_schritt_h: float = MAX_SCHRITT_H) -> pd.DataFrame:
    """Erste und zweite Ableitung je Spalte auf dem Zeitindex von `df`.

    `df` erwartet das Schema von `features.features_for_meter`, also
    einen DatetimeIndex und die Messkanaele als Spalten. Rueckgabe ist
    ein DataFrame auf demselben Index mit ``<spalte>_d1`` in Einheit je
    Stunde und ``<spalte>_d2`` in Einheit je Stunde im Quadrat, dazu
    ``schritt_h`` als Nachweis, welcher Abstand tatsaechlich benutzt
    wurde.

    Ungueltige Stellen sind NaN. Das betrifft die erste Zeile, jede
    Stelle nach einer Luecke und bei der zweiten Ableitung zusaetzlich
    die Stelle direkt danach.
    """
    w = df.sort_index()
    idx = pd.DatetimeIndex(w.index)
    schritt = _schrittweite(idx)
    gueltig = schritt.notna() & (schritt > 0) & (schritt <= float(max_schritt_h))

    out = pd.DataFrame(index=idx)
    out["schritt_h"] = np.where(gueltig.to_numpy(), schritt.to_numpy(), np.nan)
    for spalte in spalten:
        if spalte not in w.columns:
            raise KeyError(
                f"Spalte '{spalte}' fehlt - vorhanden: {list(w.columns)}")
        werte = pd.to_numeric(w[spalte], errors="coerce")
        d1 = werte.diff().to_numpy() / schritt.to_numpy()
        d1 = np.where(gueltig.to_numpy(), d1, np.nan)
        d1 = pd.Series(d1, index=idx)
        #zweite Ableitung nur dort, wo auch der Vorgaenger eine gueltige
        #erste Ableitung hat - sonst differenziert man ueber die Luecke
        d2 = d1.diff().to_numpy() / schritt.to_numpy()
        d2 = np.where(gueltig.to_numpy() & d1.shift(1).notna().to_numpy(),
                      d2, np.nan)
        out[f"{spalte}_d1"] = d1.to_numpy()
        out[f"{spalte}_d2"] = d2
    return out


def lastwechsel(df: pd.DataFrame,
                min_sprung_kw: float = MIN_SPRUNG_KW,
                fenster_h: int = REAKTIONSFENSTER_H,
                anteil: float = REAKTIONSANTEIL,
                max_schritt_h: float = MAX_SCHRITT_H) -> pd.DataFrame:
    """Lastspruenge und die Reaktionszeit des Ruecklaufs danach.

    Ein Lastwechsel ist eine Stunde, in der die Leistung gegenueber der
    Vorstunde um mehr als `min_sprung_kw` steigt. Gemessen wird, wie
    lange es dauert, bis der Ruecklauf `anteil` seiner gesamten
    Auslenkung innerhalb der naechsten `fenster_h` Stunden erreicht hat.
    Das ist die Zeitkonstante eines Systems erster Ordnung, nicht der
    volle Einschwingvorgang - der ist bei stuendlicher Abtastung nicht
    sauber zu fassen.

    Enthaelt das Fenster eine Luecke, wird der Fall uebersprungen; die
    Spalte ``vollstaendig`` haelt fest, wie viele Spruenge das betrifft.
    Ohne Auslenkung des Ruecklaufs (Betrag unter 0,2 K) bleibt die
    Reaktionszeit NaN, weil eine Zeit bis zu einer Aenderung, die nicht
    stattfindet, keine Bedeutung hat.

    Rueckgabe: eine Zeile je Lastsprung mit ``timestamp``, ``datum``,
    ``sprung_kw``, ``rt_auslenkung_k``, ``reaktionszeit_h`` und
    ``vollstaendig``.
    """
    spalten = ["timestamp", "datum", "sprung_kw", "rt_auslenkung_k",
               "reaktionszeit_h", "vollstaendig"]
    for spalte in ("power", "rt"):
        if spalte not in df.columns:
            raise KeyError(
                f"Spalte '{spalte}' fehlt - vorhanden: {list(df.columns)}")
    if len(df) < 3:
        return pd.DataFrame(columns=spalten)

    w = df.sort_index()
    idx = pd.DatetimeIndex(w.index)
    schritt = _schrittweite(idx).to_numpy()
    leistung = pd.to_numeric(w["power"], errors="coerce").to_numpy()
    ruecklauf = pd.to_numeric(w["rt"], errors="coerce").to_numpy()
    d_last = np.diff(leistung, prepend=np.nan)
    schritt_ok = (schritt > 0) & (schritt <= float(max_schritt_h))

    zeilen = []
    kandidaten = np.where(schritt_ok & (d_last > float(min_sprung_kw)))[0]
    for i in kandidaten:
        ende = min(len(w), i + int(fenster_h) + 1)
        fenster_schritt = schritt[i + 1:ende]
        vollstaendig = bool(len(fenster_schritt) == int(fenster_h)
                            and np.all((fenster_schritt > 0)
                                       & (fenster_schritt <= float(max_schritt_h))))
        start_rt = ruecklauf[i - 1] if i > 0 else np.nan
        verlauf = ruecklauf[i:ende]
        zeile = {"timestamp": idx[i], "datum": idx[i].normalize(),
                 "sprung_kw": float(d_last[i]),
                 "rt_auslenkung_k": np.nan, "reaktionszeit_h": np.nan,
                 "vollstaendig": vollstaendig}
        if vollstaendig and np.isfinite(start_rt) and np.all(np.isfinite(verlauf)):
            abweichung = verlauf - start_rt
            j_max = int(np.argmax(np.abs(abweichung)))
            gesamt = float(abweichung[j_max])
            zeile["rt_auslenkung_k"] = gesamt
            if abs(gesamt) >= 0.2:
                ziel = float(anteil) * gesamt
                erreicht = np.where(np.abs(abweichung[:j_max + 1]) >= abs(ziel))[0]
                if len(erreicht):
                    #Stundenzahl ab dem Sprung selbst
                    zeile["reaktionszeit_h"] = float(
                        np.sum(schritt[i + 1:i + 1 + int(erreicht[0])]))
        zeilen.append(zeile)

    if not zeilen:
        return pd.DataFrame(columns=spalten)
    return pd.DataFrame(zeilen)[spalten]


def tagesdynamik(df: pd.DataFrame,
                 min_stunden: int = MIN_STUNDEN_TAG,
                 traege_schwelle: float = TRAEGE_SCHWELLE_K_H,
                 last_schwelle_kw: float = LAST_SCHWELLE_KW,
                 max_schritt_h: float = MAX_SCHRITT_H,
                 mit_lastwechsel: bool = True) -> pd.DataFrame:
    """Dynamikkennzahlen je Kalendertag fuer eine Zaehlerreihe.

    Spalten der Rueckgabe

        rt_d1_abs_mean    mittlerer Betrag der Ruecklaufaenderung, K/h
        rt_d1_abs_p95     oberes Perzentil derselben Groesse
        rt_d2_abs_mean    mittlerer Betrag der zweiten Ableitung, K/h^2
        rt_d2_abs_p95     oberes Perzentil derselben Groesse
        rt_spanne_k       Tagesspanne des Ruecklaufs
        rt_traege_anteil  Anteil der Laststunden mit praktisch stehendem
                          Ruecklauf
        rt_vl_kopplung    Korrelation zwischen Vor- und Ruecklauf
        n_dyn             Zahl der gueltigen Ableitungsstellen
        n_last            Zahl der Laststunden
        reaktionszeit_h   Median der Reaktionszeiten der an diesem Tag
                          beginnenden Lastspruenge
        n_lastwechsel     Zahl dieser Lastspruenge

    Tage mit weniger als `min_stunden` gueltigen Ableitungsstellen
    bekommen NaN in den Dynamikspalten; die Zeile bleibt mit ihren
    Zaehlern stehen, damit sichtbar ist, warum nichts dasteht.

    `rt_vl_kopplung` ist die Korrelation der beiden Temperaturkanaele
    ueber den Tag. Laeuft der Ruecklauf dem Vorlauf hinterher, statt
    von der Abnahme bestimmt zu sein, geht sie gegen 1 - das ist die
    Signatur, die man bei einem dauerhaft offenen Ventil erwartet. Sie
    beweist den Kurzschluss nicht, sie ist damit vereinbar.
    """
    spalten = ["datum", "rt_d1_abs_mean", "rt_d1_abs_p95", "rt_d2_abs_mean",
               "rt_d2_abs_p95", "rt_spanne_k", "rt_traege_anteil",
               "rt_vl_kopplung", "n_dyn", "n_last", "reaktionszeit_h",
               "n_lastwechsel"]
    if len(df) == 0:
        return pd.DataFrame(columns=spalten)

    w = df.sort_index()
    abl = ableitungen(w, ("rt",), max_schritt_h=max_schritt_h)
    teil = pd.DataFrame({
        "datum": pd.DatetimeIndex(w.index).normalize(),
        "rt": pd.to_numeric(w["rt"], errors="coerce").to_numpy(),
        "d1": abl["rt_d1"].to_numpy(),
        "d2": abl["rt_d2"].to_numpy(),
    })
    teil["vl"] = (pd.to_numeric(w["vl"], errors="coerce").to_numpy()
                  if "vl" in w.columns else np.nan)
    teil["power"] = (pd.to_numeric(w["power"], errors="coerce").to_numpy()
                     if "power" in w.columns else np.nan)

    teil["d1_abs"] = teil["d1"].abs()
    teil["d2_abs"] = teil["d2"].abs()
    teil["last"] = teil["power"] > float(last_schwelle_kw)
    teil["d1_last_abs"] = teil["d1_abs"].where(teil["last"])
    teil["traege"] = (teil["d1_last_abs"] < float(traege_schwelle)
                      ).astype(float).where(teil["d1_last_abs"].notna())
    #Korrelation ueber die Summenformel, damit kein groupby-apply je Tag
    #noetig ist; nur Stunden mit beiden Temperaturen gehen ein
    paar = teil["rt"].notna() & teil["vl"].notna()
    teil["rt_p"] = teil["rt"].where(paar)
    teil["vl_p"] = teil["vl"].where(paar)
    teil["rtvl"] = teil["rt_p"] * teil["vl_p"]
    teil["rt2"] = teil["rt_p"] ** 2
    teil["vl2"] = teil["vl_p"] ** 2

    g = teil.groupby("datum", sort=True)
    out = pd.DataFrame({
        "rt_d1_abs_mean": g["d1_abs"].mean(),
        "rt_d1_abs_p95": g["d1_abs"].quantile(0.95),
        "rt_d2_abs_mean": g["d2_abs"].mean(),
        "rt_d2_abs_p95": g["d2_abs"].quantile(0.95),
        "rt_spanne_k": g["rt"].max() - g["rt"].min(),
        "rt_traege_anteil": g["traege"].mean(),
        "n_dyn": g["d1"].count(),
        "n_last": g["last"].sum(),
        "n_d1_last": g["d1_last_abs"].count(),
        "n_paar": g["rt_p"].count(),
        "s_rt": g["rt_p"].sum(), "s_vl": g["vl_p"].sum(),
        "s_rtvl": g["rtvl"].sum(), "s_rt2": g["rt2"].sum(),
        "s_vl2": g["vl2"].sum(),
    })
    n = out["n_paar"]
    zaehler_kov = out["s_rtvl"] - out["s_rt"] * out["s_vl"] / n
    var_rt = out["s_rt2"] - out["s_rt"] ** 2 / n
    var_vl = out["s_vl2"] - out["s_vl"] ** 2 / n
    nenner = np.sqrt(var_rt * var_vl)
    out["rt_vl_kopplung"] = np.where(
        (n >= int(min_stunden)) & (var_rt > 0) & (var_vl > 0),
        zaehler_kov / nenner.replace(0, np.nan), np.nan)

    genug = out["n_dyn"] >= int(min_stunden)
    for spalte in ("rt_d1_abs_mean", "rt_d1_abs_p95", "rt_d2_abs_mean",
                   "rt_d2_abs_p95", "rt_spanne_k", "rt_traege_anteil",
                   "rt_vl_kopplung"):
        out.loc[~genug, spalte] = np.nan
    out.loc[out["n_d1_last"] < 3, "rt_traege_anteil"] = np.nan
    out["n_dyn"] = out["n_dyn"].astype(int)
    out["n_last"] = out["n_last"].astype(int)
    out["reaktionszeit_h"] = np.nan
    out["n_lastwechsel"] = 0
    out = out.reset_index()
    if mit_lastwechsel:
        ereignisse = lastwechsel(w, max_schritt_h=max_schritt_h)
        if len(ereignisse):
            agg = ereignisse.groupby("datum").agg(
                reaktionszeit_h=("reaktionszeit_h", "median"),
                n_lastwechsel=("reaktionszeit_h", "size"))
            out = out.drop(columns=["reaktionszeit_h", "n_lastwechsel"])
            out = out.merge(agg.reset_index(), on="datum", how="left")
            out["n_lastwechsel"] = out["n_lastwechsel"].fillna(0).astype(int)
    return out[spalten]


def dynamik_tabelle(serien: Mapping[int, pd.DataFrame],
                    min_stunden: int = MIN_STUNDEN_TAG,
                    traege_schwelle: float = TRAEGE_SCHWELLE_K_H,
                    max_schritt_h: float = MAX_SCHRITT_H,
                    mit_lastwechsel: bool = True,
                    zaehler: Optional[Sequence[int]] = None) -> pd.DataFrame:
    """`tagesdynamik` ueber alle Zaehler, gestapelt zu einer Langtabelle.

    `serien` bildet Zaehlernummer auf die stuendliche Reihe ab. Die
    Rueckgabe traegt ``meter`` als erste Spalte, dieselbe Benennung wie
    in `performance.py` und `jahresvergleich.py`.
    """
    auswahl = set(zaehler) if zaehler is not None else None
    frames = []
    for zid, df in sorted(serien.items()):
        if auswahl is not None and zid not in auswahl:
            continue
        if df is None or len(df) == 0:
            continue
        tab = tagesdynamik(df, min_stunden=min_stunden,
                           traege_schwelle=traege_schwelle,
                           max_schritt_h=max_schritt_h,
                           mit_lastwechsel=mit_lastwechsel)
        if len(tab) == 0:
            continue
        tab.insert(0, "meter", int(zid))
        frames.append(tab)
    if not frames:
        return pd.DataFrame(columns=["meter", "datum"])
    return pd.concat(frames, ignore_index=True)
