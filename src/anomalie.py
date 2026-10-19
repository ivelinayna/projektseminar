"""
Anomalieerkennung ohne Fehlerlabels.

Ausgangslage
------------
Der ueberwachte Weg ist im Projekt gescheitert und als Negativbefund
dokumentiert (`docs/ml-klassifikator.md`): Balanced Accuracy 0,33 und
0,42 gegen 0,50 trivial, 84 Prozent der Fenster mit Label-Leakage, bei
n gleich 49 nur neun negative Faelle. Auch der Ground-Truth-Join auf
die Begehungen trennt nicht, die Basisrate liegt bei rund 77 Prozent.
Dieses Modul geht deshalb davon aus, dass es keine tragfaehigen Labels
gibt, und baut nichts, was von ihnen abhaengt.

Anomaliebegriff
---------------
Anomal ist nicht, was von einem Label abweicht, sondern was vom
physikalisch erwartbaren Verhalten abweicht. Bei gegebener
Aussentemperatur und gegebener Abnahme laesst sich sagen, welcher
Ruecklauf zu erwarten waere; die Abweichung nach oben ist das Signal.
Der Ruecklauf ist dabei die zentrale Guetegroesse der Fernwaerme - ein
zu warmer Ruecklauf bedeutet hohe Netzverluste und schlechte
Auskuehlung.

Zwei Bezugsrahmen, beide mit einem Haken
----------------------------------------
Das netzweite Modell vergleicht jede Station mit dem Rest des Netzes.
Es findet auch eine Station, die von Anfang an schlecht laeuft, bestraft
aber bauartbedingte Unterschiede: eine Fussbodenheizung und ein alter
Radiatorkreis haben verschiedene Ruecklaufniveaus, ohne dass einer
davon defekt waere. Das stationseigene Modell vergleicht jede Station
mit ihrer eigenen Vergangenheit. Es ist gegen Bauart und Groesse
immun, kann aber per Konstruktion keine chronisch schlechte Station
finden: deren Residuum ist im Mittel null, weil der eigene schlechte
Zustand die Erwartung ist. Beide Varianten stehen deshalb
nebeneinander und werden nicht gegeneinander ausgetauscht.

Persistenz
----------
Aus den Meetings stammt die Vorgabe, dass echte Anomalien ueber
laengere Zeit bestehen. Ein Score, der an drei Tagen im Jahr hoch ist,
ist kein Befund, sondern Wetter. `persistente_tage` verlangt deshalb,
dass ein Tag in einem gleitenden Fenster von `fenster` Tagen
mindestens `min_tage` auffaellige Nachbarn hat. Beide Groessen sind
Parameter, ihre Wirkung auf die Trefferliste gehoert in jede
Auswertung.

Validierung ohne Labels
-----------------------
Die Begehungen liefern ein Pruefsignal, das ohne Fehlerlabels
auskommt. Nach Notebook 07 senken sie den Ruecklauf im Wintervergleich
gepaart um 1,60 K und im Diff-in-Diff gegen 49 Kontrollzaehler um
1,90 K bei p gleich 0,010. Ein brauchbarer Anomaliescore muss nach
einer Begehung sinken, und bei den Kontrollstationen im selben
Zeitraum nicht. `begehungsvalidierung` und `diff_in_diff` rechnen genau
das, mit demselben gepaarten Test und derselben Kontrollgruppenlogik
wie Notebook 07. Ein Detektor, der diese Pruefung nicht besteht,
gehoert nicht in die Abgabe.

Kausalitaet
-----------
Keine der Zahlen hier zeigt, dass eine Begehung einen Score senkt. Die
besuchten Stationen wurden nicht zufaellig ausgewaehlt. Belegbar ist
nur, dass die Bewegung des Scores mit der Intervention zusammenfaellt
und bei den Kontrollstationen ausbleibt.
"""

from __future__ import annotations

from typing import Callable, Dict, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import performance as pf

#Namen der Detektoren, als Spaltenpraefix und in den Ergebnistabellen
D_RESID_NETZ = "residuum_netz"
D_RESID_STATION = "residuum_station"
D_IFOREST = "isolation_forest"
D_ZUSTAND = "zustandsanteil"
D_DYNAMIK = "dynamik"

#Standardpraediktoren des Erwartungswertmodells: Witterung und Abnahme
PRAEDIKTOREN = ("t_out_tag", "last_anteil", "power_mean")

#Zielgroesse des Erwartungswertmodells. Der Ruecklaufmedian ueber alle
#Stunden eines Tages und nicht der Mittelwert ueber die Laststunden:
#die Zahl der Laststunden schwankt im Winter von Tag zu Tag, der
#Mittelwert steht dann je Tag auf verschieden vielen Stunden. Die
#Gegenprobe in Notebook 10 zeigt den Unterschied deutlich - die
#bekannte Ruecklaufsenkung nach einer Begehung ist auf `rt_median`
#messbar und auf `rt_mean_loaded` nicht.
ZIEL = "rt_median"

#Mindestzahl Tage, aus denen ein stationseigenes Modell geschaetzt wird
MIN_TAGE_MODELL = 60

#Mindestzahl Tage, aus denen ein Stationsscore gebildet wird
MIN_TAGE_SCORE = 10

#Quantil ueber alle Stationstage, ab dem ein Tag als auffaellig gilt
SCHWELLENQUANTIL = 0.90

#Persistenzfenster in Kalendertagen und Mindestzahl auffaelliger Tage darin
PERSISTENZ_FENSTER = 14
PERSISTENZ_MIN_TAGE = 7

SEED = 42


#--------------------------------------------------------------------------
#Erwartungswertmodell
#--------------------------------------------------------------------------

def _modellmaske(panel: pd.DataFrame,
                 ziel: str,
                 praediktoren: Sequence[str],
                 nur_belegte_tage: bool = True) -> pd.Series:
    """Zeilen, die in eine Schaetzung eingehen koennen."""
    maske = pd.Series(True, index=panel.index)
    for spalte in (ziel, *praediktoren):
        if spalte not in panel.columns:
            raise KeyError(f"Spalte '{spalte}' fehlt - vorhanden: "
                           f"{list(panel.columns)}")
        maske &= pd.to_numeric(panel[spalte], errors="coerce").notna()
    if nur_belegte_tage and "genug_stunden" in panel.columns:
        maske &= panel["genug_stunden"].fillna(False).astype(bool)
    return maske


def erwartungsmodell_netz(panel: pd.DataFrame,
                          ziel: str = ZIEL,
                          praediktoren: Sequence[str] = PRAEDIKTOREN,
                          name: str = D_RESID_NETZ,
                          nur_belegte_tage: bool = True) -> tuple:
    """Netzweites Erwartungswertmodell des Ruecklaufs.

    Geschaetzt wird eine gemeinsame Gerade ueber alle Stationstage. Die
    Standardfehler kommen aus `performance.ols` mit der Zaehlernummer
    als Cluster, weil Tage derselben Station nicht unabhaengig sind.

    Rueckgabe ist das Panel mit den Spalten ``erwartet_<name>`` und
    ``score_<name>`` (gemessen minus erwartet, positiv heisst waermer
    als erwartet) sowie ein Modell-Dictionary mit Koeffizienten,
    Standardfehlern, p-Werten, R-Quadrat und Fallzahlen.

    Der Haken dieser Variante gehoert in jede Auswertung: bauartbedingt
    hohe Ruecklaeufe sehen hier aus wie ein Fehler. Das Modell kann
    nicht zwischen einer schlecht eingestellten und einer anders
    gebauten Station unterscheiden.
    """
    maske = _modellmaske(panel, ziel, praediktoren, nur_belegte_tage)
    out = panel.copy()
    out[f"erwartet_{name}"] = np.nan
    out[f"score_{name}"] = np.nan
    if int(maske.sum()) <= len(praediktoren) + 1:
        return out, {"n": int(maske.sum()), "beta": None,
                     "grund": "zu wenige verwertbare Stationstage"}

    teil = out.loc[maske]
    X = teil[list(praediktoren)].to_numpy(dtype=float)
    y = teil[ziel].to_numpy(dtype=float)
    cluster = teil["meter"].to_numpy() if "meter" in teil.columns else None
    modell = pf.ols(X, y, cluster=cluster)
    beta = modell["beta"]
    erwartet = beta[0] + X @ beta[1:]
    out.loc[maske, f"erwartet_{name}"] = erwartet
    out.loc[maske, f"score_{name}"] = y - erwartet

    info = {
        "modus": "netzweit", "ziel": ziel,
        "praediktoren": list(praediktoren),
        "n_tage": int(maske.sum()),
        "n_stationen": int(teil["meter"].nunique()) if cluster is not None else None,
        "r2": float(modell["r2"]),
        "beta": {n: float(b) for n, b in
                 zip(["achsenabschnitt", *praediktoren], beta)},
        "se": {n: float(s) for n, s in
               zip(["achsenabschnitt", *praediktoren], modell["se"])},
        "p": {n: float(p) for n, p in
              zip(["achsenabschnitt", *praediktoren], modell["p"])},
    }
    return out, info


def erwartungsmodell_station(panel: pd.DataFrame,
                             ziel: str = ZIEL,
                             praediktoren: Sequence[str] = PRAEDIKTOREN,
                             name: str = D_RESID_STATION,
                             min_tage: int = MIN_TAGE_MODELL,
                             nur_belegte_tage: bool = True) -> tuple:
    """Stationseigenes Erwartungswertmodell: jede Station gegen sich selbst.

    Fuer jede Station wird dieselbe Gerade auf ihrer eigenen Historie
    geschaetzt. Stationen mit weniger als `min_tage` verwertbaren Tagen
    bekommen NaN und erscheinen mit Grund in der Bilanztabelle.

    Der Haken ist strukturell und laesst sich nicht wegparametrieren:
    das Residuum einer Station ist im Mittel null. Eine Station, die
    ueber die gesamte Historie zu warm zurueckgibt, faellt hier nicht
    auf, weil ihr schlechter Zustand die Erwartung bildet. Die Variante
    taugt fuer Veraenderungen im Zeitverlauf, nicht fuer chronische
    Zustaende.
    """
    maske = _modellmaske(panel, ziel, praediktoren, nur_belegte_tage)
    out = panel.copy()
    out[f"erwartet_{name}"] = np.nan
    out[f"score_{name}"] = np.nan

    bilanz = []
    for zid, g in out.loc[maske].groupby("meter"):
        if len(g) < int(min_tage):
            bilanz.append({"meter": int(zid), "n_tage": len(g),
                           "geschaetzt": False,
                           "grund": f"weniger als {min_tage} verwertbare Tage"})
            continue
        X = g[list(praediktoren)].to_numpy(dtype=float)
        y = g[ziel].to_numpy(dtype=float)
        if np.linalg.matrix_rank(np.column_stack([np.ones(len(y)), X])) \
                < X.shape[1] + 1:
            bilanz.append({"meter": int(zid), "n_tage": len(g),
                           "geschaetzt": False,
                           "grund": "Praediktoren linear abhaengig"})
            continue
        beta, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(y)), X]), y,
                                   rcond=None)
        erwartet = beta[0] + X @ beta[1:]
        out.loc[g.index, f"erwartet_{name}"] = erwartet
        out.loc[g.index, f"score_{name}"] = y - erwartet
        bilanz.append({"meter": int(zid), "n_tage": len(g), "geschaetzt": True,
                       "grund": ""})

    spalten = ["meter", "n_tage", "geschaetzt", "grund"]
    return out, pd.DataFrame(bilanz, columns=spalten)


#--------------------------------------------------------------------------
#Weitere Detektoren
#--------------------------------------------------------------------------

def score_isolation_forest(panel: pd.DataFrame,
                           merkmale: Sequence[str],
                           name: str = D_IFOREST,
                           contamination: float = 0.05,
                           n_estimators: int = 300,
                           seed: int = SEED,
                           nur_belegte_tage: bool = True) -> tuple:
    """Isolation Forest auf dem Tagespanel, ein Score je Stationstag.

    Das Verfahren kennt keine Physik; es sucht Tage, die sich im
    Merkmalsraum leicht abtrennen lassen. Das ist bewusst die
    kontrastierende Gegenposition zum Erwartungswertmodell: findet der
    Wald dieselben Stationen, stuetzt das den Befund, findet er andere,
    muss die Differenz erklaert werden.

    Zeilen mit Fehlwerten in `merkmale` bekommen NaN, es wird nichts
    imputiert - ein imputierter Tag waere ein erfundener Tag. Der Score
    ist so gedreht, dass hohe Werte auffaellig heissen.
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    fehlend = [s for s in merkmale if s not in panel.columns]
    if fehlend:
        raise KeyError(f"Spalten {fehlend} fehlen - vorhanden: "
                       f"{list(panel.columns)}")
    out = panel.copy()
    maske = pd.Series(True, index=out.index)
    for spalte in merkmale:
        maske &= pd.to_numeric(out[spalte], errors="coerce").notna()
    if nur_belegte_tage and "genug_stunden" in out.columns:
        maske &= out["genug_stunden"].fillna(False).astype(bool)

    out[f"score_{name}"] = np.nan
    if int(maske.sum()) < 50:
        return out, {"n_tage": int(maske.sum()),
                     "grund": "zu wenige verwertbare Stationstage"}

    X = StandardScaler().fit_transform(
        out.loc[maske, list(merkmale)].to_numpy(dtype=float))
    wald = IsolationForest(n_estimators=n_estimators,
                           contamination=contamination,
                           random_state=seed).fit(X)
    #score_samples ist umso kleiner, je anomaler - Vorzeichen drehen
    out.loc[maske, f"score_{name}"] = -wald.score_samples(X)
    info = {"n_tage": int(maske.sum()), "merkmale": list(merkmale),
            "contamination": float(contamination), "seed": int(seed)}
    return out, info


def score_zustand(panel: pd.DataFrame,
                  spalten: Sequence[str],
                  name: str = D_ZUSTAND) -> pd.DataFrame:
    """Zeitanteil in den uebergebenen Betriebszustaenden als Tagesscore.

    `spalten` sind die Anteilsspalten aus `tagespanel.zustandsanteile`,
    die fachlich als auffaellig gelten - im Projekt der Zustand mit
    hohem normiertem Durchfluss bei kleiner Spreizung, in Notebook 09
    als Verdacht auf hydraulischen Kurzschluss benannt. Der Score ist
    die Summe dieser Anteile und liegt damit zwischen 0 und 1.
    """
    fehlend = [s for s in spalten if s not in panel.columns]
    if fehlend:
        raise KeyError(f"Spalten {fehlend} fehlen - vorhanden: "
                       f"{list(panel.columns)}")
    out = panel.copy()
    out[f"score_{name}"] = out[list(spalten)].sum(axis=1, min_count=1)
    return out


def robuster_z(werte: pd.Series) -> pd.Series:
    """Standardisierung ueber Median und MAD statt Mittel und Streuung.

    Mittelwert und Standardabweichung werden von genau den Ausreissern
    gezogen, die gesucht sind. Ist der MAD null, bleibt die Spalte NaN -
    eine konstante Groesse traegt keine Information und soll nicht durch
    eine Division durch fast null kuenstlich gross werden.
    """
    x = pd.to_numeric(werte, errors="coerce")
    median = x.median()
    mad = (x - median).abs().median()
    if not np.isfinite(mad) or mad <= 0:
        return pd.Series(np.nan, index=x.index)
    return (x - median) / (1.4826 * mad)


def score_dynamik(panel: pd.DataFrame,
                  gewichte: Optional[Mapping[str, float]] = None,
                  name: str = D_DYNAMIK) -> tuple:
    """Zusammengesetzter Dynamikscore aus den Ableitungskennzahlen.

    Die Vorzeichen folgen der Ueberlegung aus dem Betreuermeeting. Ein
    Ruecklauf, der dem Vorlauf folgt (`rt_vl_kopplung` hoch) und sich
    unter Last kaum bewegt (`rt_traege_anteil` hoch), wird nicht von der
    Abnahme bestimmt - das ist mit einem dauerhaft offenen oder
    festsitzenden Ventil vereinbar. Eine stark schwankende zweite
    Ableitung (`rt_d2_abs_mean` hoch) ist mit einer unruhigen Regelung
    vereinbar.

    Beide Teile zeigen auf verschiedene Fehlerbilder und werden
    trotzdem addiert; das ist die Schwaeche dieses Detektors und der
    Grund, warum er neben dem Erwartungswertmodell steht und nicht
    statt seiner.

    Eine Kennzahl, deren MAD ueber alle Stationstage null ist, traegt
    keine Information und wird mit Begruendung uebergangen, statt den
    ganzen Score auf NaN zu ziehen. Welche Kennzahlen eingegangen sind
    und welche nicht, steht in der zweiten Rueckgabe.
    """
    if gewichte is None:
        gewichte = {"rt_vl_kopplung": 1.0, "rt_traege_anteil": 1.0,
                    "rt_d2_abs_mean": 0.5}
    fehlend = [s for s in gewichte if s not in panel.columns]
    if fehlend:
        raise KeyError(f"Spalten {fehlend} fehlen - vorhanden: "
                       f"{list(panel.columns)}")
    out = panel.copy()
    teile, benutzt, verworfen = [], [], {}
    for spalte, gewicht in gewichte.items():
        z = robuster_z(out[spalte])
        if z.notna().sum() == 0:
            verworfen[spalte] = ("MAD ueber alle Stationstage null, "
                                 "keine Streuung zu standardisieren")
            continue
        teile.append(float(gewicht) * z)
        benutzt.append(spalte)
    if not teile:
        out[f"score_{name}"] = np.nan
    else:
        out[f"score_{name}"] = pd.concat(teile, axis=1).sum(
            axis=1, min_count=len(teile))
    info = {"benutzt": benutzt, "verworfen": verworfen,
            "gewichte": {k: float(v) for k, v in gewichte.items()
                         if k in benutzt},
            "n_tage": int(out[f"score_{name}"].notna().sum())}
    return out, info


#--------------------------------------------------------------------------
#Persistenz
#--------------------------------------------------------------------------

def tagesschwelle(panel: pd.DataFrame,
                  spalte: str,
                  quantil: float = SCHWELLENQUANTIL) -> float:
    """Globale Schwelle als Quantil ueber alle Stationstage.

    Die Schwelle kommt aus der Verteilung der echten Daten und nicht
    aus der Literatur. Sie legt fest, welcher Anteil der Stationstage
    ueberhaupt auffaellig heissen kann; `quantil` gleich 0,90 heisst
    also: 10 Prozent der Tage sind Kandidaten, bevor die Persistenz
    greift.
    """
    x = pd.to_numeric(panel[spalte], errors="coerce").dropna()
    if len(x) == 0:
        return float("nan")
    return float(x.quantile(float(quantil)))


def persistente_tage(panel: pd.DataFrame,
                     spalte: str,
                     schwelle: Optional[float] = None,
                     quantil: float = SCHWELLENQUANTIL,
                     fenster: int = PERSISTENZ_FENSTER,
                     min_tage: int = PERSISTENZ_MIN_TAGE) -> tuple:
    """Auffaellige und persistent auffaellige Tage markieren.

    Ein Tag ist auffaellig, wenn sein Score ueber der Schwelle liegt. Er
    ist persistent auffaellig, wenn in dem auf ihm endenden Fenster von
    `fenster` Kalendertagen mindestens `min_tage` auffaellige Tage
    liegen. Gezaehlt wird ueber den Kalender und nicht ueber Zeilen,
    damit eine Messluecke das Fenster nicht stillschweigend verlaengert.

    Rueckgabe ist das Panel mit den Spalten ``auffaellig_<spalte>`` und
    ``persistent_<spalte>`` sowie die benutzte Schwelle.
    """
    out = panel.copy()
    if schwelle is None:
        schwelle = tagesschwelle(out, spalte, quantil)
    werte = pd.to_numeric(out[spalte], errors="coerce")
    auffaellig = werte > schwelle
    auffaellig = auffaellig.where(werte.notna(), False)
    out[f"auffaellig_{spalte}"] = auffaellig.to_numpy()

    persistent = pd.Series(False, index=out.index)
    for zid, g in out.groupby("meter"):
        reihe = pd.Series(g[f"auffaellig_{spalte}"].to_numpy(dtype=float),
                          index=pd.DatetimeIndex(g["datum"]))
        reihe = reihe.sort_index()
        reihe = reihe[~reihe.index.duplicated(keep="first")]
        zaehler = reihe.rolling(f"{int(fenster)}D", min_periods=1).sum()
        treffer = (zaehler >= int(min_tage))
        persistent.loc[g.index] = treffer.reindex(
            pd.DatetimeIndex(g["datum"])).to_numpy()
    out[f"persistent_{spalte}"] = persistent.fillna(False).to_numpy()
    return out, float(schwelle)


#--------------------------------------------------------------------------
#Stationsebene
#--------------------------------------------------------------------------

def stationsscore(panel: pd.DataFrame,
                  spalte: str,
                  von: Optional[pd.Timestamp] = None,
                  bis: Optional[pd.Timestamp] = None,
                  min_tage: int = MIN_TAGE_SCORE) -> pd.DataFrame:
    """Scoretabelle je Station, optional auf ein Zeitfenster beschraenkt.

    Spalten der Rueckgabe: ``n_tage``, ``score_mittel`` (Mittel ueber
    die Tage mit Score), ``score_median``, ``anteil_auffaellig`` und
    ``anteil_persistent`` (sofern die Flags aus `persistente_tage`
    vorliegen) sowie ``max_lauf``, die laengste Folge aufeinander
    folgender auffaelliger Kalendertage.

    Stationen mit weniger als `min_tage` Tagen im Fenster bekommen NaN
    in den Kennzahlen und bleiben mit ihrer Tageszahl in der Tabelle.
    """
    teil = panel
    if von is not None:
        teil = teil[pd.DatetimeIndex(teil["datum"]) >= pd.Timestamp(von)]
    if bis is not None:
        teil = teil[pd.DatetimeIndex(teil["datum"]) <= pd.Timestamp(bis)]

    auff = f"auffaellig_{spalte}"
    pers = f"persistent_{spalte}"
    zeilen = []
    for zid, g in teil.groupby("meter"):
        werte = pd.to_numeric(g[spalte], errors="coerce").dropna()
        zeile = {"meter": int(zid), "n_tage": int(len(werte))}
        genug = len(werte) >= int(min_tage)
        zeile["score_mittel"] = float(werte.mean()) if genug else np.nan
        zeile["score_median"] = float(werte.median()) if genug else np.nan
        if auff in g.columns:
            flag = g[auff].fillna(False).astype(bool)
            zeile["anteil_auffaellig"] = float(flag.mean()) if genug else np.nan
            zeile["max_lauf"] = int(_max_lauf(
                pd.DatetimeIndex(g["datum"]), flag.to_numpy()))
        if pers in g.columns:
            zeile["anteil_persistent"] = (
                float(g[pers].fillna(False).astype(bool).mean())
                if genug else np.nan)
        zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def _max_lauf(datum: pd.DatetimeIndex, flag: np.ndarray) -> int:
    """Laengste Folge aufeinander folgender Kalendertage mit gesetztem Flag."""
    if len(flag) == 0:
        return 0
    ordnung = np.argsort(datum.to_numpy())
    tage = pd.DatetimeIndex(datum.to_numpy()[ordnung])
    werte = np.asarray(flag)[ordnung]
    best = lauf = 0
    vorheriger = None
    for tag, gesetzt in zip(tage, werte):
        if not gesetzt:
            lauf = 0
            vorheriger = tag
            continue
        if vorheriger is not None and (tag - vorheriger).days == 1 and lauf > 0:
            lauf += 1
        else:
            lauf = 1
        best = max(best, lauf)
        vorheriger = tag
    return best


def scoretabelle(panel: pd.DataFrame,
                 spalten: Sequence[str],
                 kennzahl: str = "score_mittel",
                 min_tage: int = MIN_TAGE_SCORE) -> pd.DataFrame:
    """Eine Spalte je Detektor, eine Zeile je Station."""
    out = None
    for spalte in spalten:
        teil = stationsscore(panel, spalte, min_tage=min_tage)
        teil = teil[["meter", kennzahl]].rename(columns={kennzahl: spalte})
        out = teil if out is None else out.merge(teil, on="meter", how="outer")
    return out if out is not None else pd.DataFrame(columns=["meter"])


def uebereinstimmung(scores: pd.DataFrame,
                     spalten: Sequence[str],
                     top_n: int = 20) -> tuple:
    """Wie stark stimmen die Detektoren ueberein?

    Zurueck kommen zwei Matrizen: die Rangkorrelation nach Spearman
    ueber alle Stationen und die Ueberschneidung der jeweils `top_n`
    auffaelligsten Stationen als Jaccard-Index. Die Rangkorrelation
    sagt, ob die Detektoren dieselbe Ordnung bilden; der Jaccard-Index
    sagt, ob sie dieselbe Trefferliste erzeugen, und nur die wird in
    der Praxis abgearbeitet.
    """
    teil = scores[list(spalten)].apply(pd.to_numeric, errors="coerce")
    rang = teil.corr(method="spearman")
    mengen = {}
    for spalte in spalten:
        s = scores[["meter", spalte]].dropna()
        s = s.sort_values(spalte, ascending=False).head(int(top_n))
        mengen[spalte] = set(s["meter"].astype(int))
    jaccard = pd.DataFrame(index=list(spalten), columns=list(spalten),
                           dtype=float)
    for a in spalten:
        for b in spalten:
            va, vb = mengen[a], mengen[b]
            jaccard.loc[a, b] = (len(va & vb) / len(va | vb)
                                 if (va | vb) else np.nan)
    return rang, jaccard


#--------------------------------------------------------------------------
#Benennbares Muster
#--------------------------------------------------------------------------

#Reihenfolge ist Prioritaet: die erste zutreffende Regel benennt das Muster
MUSTERREGELN = [
    ("Ruecklauf folgt dem Vorlauf, Verdacht hydraulischer Kurzschluss",
     {"rt_vl_kopplung": "hoch", "dt_mean_loaded": "niedrig"}),
    ("Ruecklauf reagiert kaum, Verdacht festsitzendes oder offenes Ventil",
     {"rt_traege_anteil": "hoch", "rt_d1_abs_mean": "niedrig"}),
    ("unruhige Regelung",
     {"rt_d2_abs_mean": "hoch"}),
    ("Durchfluss ohne nennenswerte Abnahme",
     {"flow_median": "hoch", "last_anteil": "niedrig"}),
    ("Ruecklauf ueber Erwartung ohne weiteres Merkmal",
     {"score_residuum_netz": "hoch"}),
]


def stationsprofil(panel: pd.DataFrame,
                   spalten: Sequence[str],
                   nur_belegte_tage: bool = True) -> pd.DataFrame:
    """Median je Station ueber die uebergebenen Tagesspalten."""
    teil = panel
    if nur_belegte_tage and "genug_stunden" in panel.columns:
        teil = teil[teil["genug_stunden"].fillna(False).astype(bool)]
    vorhanden = [s for s in spalten if s in teil.columns]
    out = teil.groupby("meter")[vorhanden].median()
    out["n_tage"] = teil.groupby("meter").size()
    return out.reset_index()


def muster_je_station(profil: pd.DataFrame,
                      regeln: Sequence = tuple(MUSTERREGELN),
                      quantil_hoch: float = 0.80,
                      quantil_niedrig: float = 0.20) -> pd.DataFrame:
    """Jeder Station ein benennbares Muster zuordnen.

    Die Schwellen sind Quantile ueber die Stationen und damit relativ:
    "hoch" heisst oberhalb des `quantil_hoch`-Quantils aller Stationen,
    nicht oberhalb eines Literaturwerts. Das ist die bewusste
    Gegenentscheidung zur bisherigen Regel-Baseline, deren absolute
    Schwellen auf den echten Daten entweder fast alles oder nichts
    treffen.

    Kennzahlen, deren unteres und oberes Quantil zusammenfallen, streuen
    im Kern der Verteilung nicht. Damit derselbe Wert nicht zugleich als
    hoch und als niedrig gilt, muss ein hoher Wert zusaetzlich ueber dem
    unteren Quantil liegen und ein niedriger unter dem oberen. Ohne
    diese Zusatzbedingung feuert eine Regel auf einer Kennzahl wie
    `rt_traege_anteil`, die auf Tagesebene fast immer null ist, auf
    praktisch jeder Station.

    Die Zuordnung ist eine Beschreibung der Messgroessen und keine
    Diagnose. Sie bereitet die spaetere Handlungsempfehlung vor, indem
    sie sagt, woran die Auffaelligkeit haengt; welcher Eingriff daraus
    folgt, entscheidet das Fachpersonal.
    """
    grenzen = {}
    for spalte in profil.columns:
        if spalte in ("meter", "n_tage"):
            continue
        werte = pd.to_numeric(profil[spalte], errors="coerce").dropna()
        if len(werte) < 5:
            continue
        unten = float(werte.quantile(quantil_niedrig))
        oben = float(werte.quantile(quantil_hoch))
        if not np.isfinite(unten) or not np.isfinite(oben):
            continue
        grenzen[spalte] = (unten, oben)

    zeilen = []
    for _, zeile in profil.iterrows():
        muster, begruendung = "kein eindeutiges Muster", ""
        for name, bedingungen in regeln:
            teile, erfuellt = [], True
            for spalte, richtung in bedingungen.items():
                if spalte not in grenzen or pd.isna(zeile.get(spalte, np.nan)):
                    erfuellt = False
                    break
                unten, oben = grenzen[spalte]
                wert = float(zeile[spalte])
                if richtung == "hoch" and wert >= oben and wert > unten:
                    teile.append(f"{spalte} {wert:.3g} ueber p{int(quantil_hoch * 100)}")
                elif richtung == "niedrig" and wert <= unten and wert < oben:
                    teile.append(f"{spalte} {wert:.3g} unter p{int(quantil_niedrig * 100)}")
                else:
                    erfuellt = False
                    break
            if erfuellt:
                muster, begruendung = name, "; ".join(teile)
                break
        zeilen.append({"meter": int(zeile["meter"]), "muster": muster,
                       "begruendung": begruendung})
    return pd.DataFrame(zeilen)


#--------------------------------------------------------------------------
#Validierung ueber die Begehungen
#--------------------------------------------------------------------------

def fensterscore(panel: pd.DataFrame,
                 spalte: str,
                 meter: int,
                 start,
                 end,
                 min_tage: int = MIN_TAGE_SCORE) -> dict:
    """Stationsscore einer Station in einem Zeitfenster."""
    teil = panel[panel["meter"] == int(meter)]
    tab = stationsscore(teil, spalte, von=start, bis=end, min_tage=min_tage)
    if len(tab) == 0:
        return {"n_tage": 0, "score_mittel": np.nan,
                "anteil_auffaellig": np.nan}
    zeile = tab.iloc[0].to_dict()
    zeile.pop("meter", None)
    return zeile


def vorher_nachher(panel: pd.DataFrame,
                   spalte: str,
                   meter: int,
                   grenzen: Mapping[str, object],
                   kennzahlen: Sequence[str] = ("score_mittel",
                                                "anteil_auffaellig"),
                   min_tage: int = MIN_TAGE_SCORE) -> dict:
    """Score im Vorher- und im Nachher-Fenster plus Differenz.

    `grenzen` hat die vier Schluessel ``vor_start``, ``vor_end``,
    ``nach_start`` und ``nach_end`` - dasselbe Format, das
    `jahresvergleich.winterfenster` liefert.
    """
    vor = fensterscore(panel, spalte, meter, grenzen["vor_start"],
                       grenzen["vor_end"], min_tage)
    nach = fensterscore(panel, spalte, meter, grenzen["nach_start"],
                        grenzen["nach_end"], min_tage)
    out = {"meter": int(meter), "n_tage_vor": vor.get("n_tage", 0),
           "n_tage_nach": nach.get("n_tage", 0)}
    for k in kennzahlen:
        out[f"{k}_vor"] = vor.get(k, np.nan)
        out[f"{k}_nach"] = nach.get(k, np.nan)
        out[f"d_{k}"] = out[f"{k}_nach"] - out[f"{k}_vor"]
    out["auswertbar"] = bool(out["n_tage_vor"] >= int(min_tage)
                             and out["n_tage_nach"] >= int(min_tage))
    return out


def begehungsvalidierung(panel: pd.DataFrame,
                         spalte: str,
                         begehungen: pd.DataFrame,
                         fenster: Callable[[object], Mapping[str, object]],
                         kennzahlen: Sequence[str] = ("score_mittel",
                                                      "anteil_auffaellig"),
                         min_tage: int = MIN_TAGE_SCORE) -> pd.DataFrame:
    """Je Begehung der Score im Winter davor gegen den Winter danach.

    `begehungen` braucht die Spalten ``meter`` und ``datum``. `fenster`
    bildet ein Datum auf die vier Fenstergrenzen ab; im Projekt ist das
    `jahresvergleich.winterfenster` mit fester Wintervariante.
    """
    zeilen = []
    for _, r in begehungen.iterrows():
        if pd.isna(r.get("meter")) or pd.isna(r.get("datum")):
            continue
        grenzen = fenster(r["datum"])
        zeile = vorher_nachher(panel, spalte, int(r["meter"]), grenzen,
                               kennzahlen, min_tage)
        zeile["datum"] = pd.Timestamp(r["datum"])
        if "kategorie" in r.index:
            zeile["kategorie"] = r["kategorie"]
        zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def kontrollbewegung(panel: pd.DataFrame,
                     spalte: str,
                     kontroll_meter: Sequence[int],
                     grenzen: Mapping[str, object],
                     kennzahlen: Sequence[str] = ("score_mittel",
                                                  "anteil_auffaellig"),
                     min_tage: int = MIN_TAGE_SCORE) -> pd.DataFrame:
    """Dieselben Fenster fuer Stationen ohne dokumentierte Begehung."""
    zeilen = []
    for zid in kontroll_meter:
        zeile = vorher_nachher(panel, spalte, int(zid), grenzen, kennzahlen,
                               min_tage)
        zeilen.append(zeile)
    tab = pd.DataFrame(zeilen)
    return tab[tab["auswertbar"]] if len(tab) else tab


def diff_in_diff(panel: pd.DataFrame,
                 spalte: str,
                 begehungen: pd.DataFrame,
                 kontroll_meter: Sequence[int],
                 fenster: Callable[[object], Mapping[str, object]],
                 kennzahlen: Sequence[str] = ("score_mittel",
                                              "anteil_auffaellig"),
                 min_tage: int = MIN_TAGE_SCORE,
                 min_kontrolle: int = 5) -> pd.DataFrame:
    """Begehungsbewegung minus Kontrollbewegung im selben Fensterpaar.

    Die Kontrollgruppe wird ueber die Fenstergrenzen gecacht, weil sich
    alle Begehungen eines Herbstes dieselben Grenzen teilen - dieselbe
    Konstruktion wie in Notebook 07.
    """
    cache: Dict[tuple, pd.DataFrame] = {}
    zeilen = []
    for _, r in begehungen.iterrows():
        if pd.isna(r.get("meter")) or pd.isna(r.get("datum")):
            continue
        grenzen = fenster(r["datum"])
        station = vorher_nachher(panel, spalte, int(r["meter"]), grenzen,
                                 kennzahlen, min_tage)
        if not station["auswertbar"]:
            continue
        key = tuple(pd.Timestamp(grenzen[k]) for k in
                    ("vor_start", "vor_end", "nach_start", "nach_end"))
        if key not in cache:
            cache[key] = kontrollbewegung(panel, spalte, kontroll_meter,
                                          grenzen, kennzahlen, min_tage)
        kontrolle = cache[key]
        if len(kontrolle) < int(min_kontrolle):
            continue
        zeile = {"meter": int(r["meter"]), "datum": pd.Timestamp(r["datum"]),
                 "n_kontrolle": len(kontrolle)}
        for k in kennzahlen:
            zeile[f"d_{k}_station"] = station[f"d_{k}"]
            zeile[f"d_{k}_kontrolle"] = float(kontrolle[f"d_{k}"].median())
            zeile[f"did_{k}"] = (station[f"d_{k}"]
                                 - float(kontrolle[f"d_{k}"].median()))
        zeilen.append(zeile)
    return pd.DataFrame(zeilen)


def gepaarter_test(werte: Sequence[float]) -> dict:
    """Wilcoxon-Vorzeichenrangtest auf eine Differenzreihe.

    Ohne scipy bleibt der p-Wert NaN; die beschreibenden Groessen
    stehen trotzdem da, damit eine Auswertung nicht an der
    Umgebung haengt.
    """
    w = pd.Series(list(werte), dtype=float).dropna()
    out = {"n": int(len(w)), "median": float(w.median()) if len(w) else np.nan,
           "mittel": float(w.mean()) if len(w) else np.nan,
           "q1": float(w.quantile(0.25)) if len(w) else np.nan,
           "q3": float(w.quantile(0.75)) if len(w) else np.nan,
           "p": np.nan}
    if len(w) >= 5 and w.abs().sum() > 0:
        try:
            from scipy import stats
            out["p"] = float(stats.wilcoxon(w)[1])
        except Exception:
            pass
    return out


def validierungsbilanz(did: pd.DataFrame,
                       kennzahl: str = "score_mittel",
                       richtung: str = "sinkt") -> dict:
    """Ergebnis der Begehungsvalidierung fuer einen Detektor.

    `richtung` gleich ``sinkt`` heisst: bestanden ist, wenn der Score
    nach der Begehung faellt und das auch gegen die Kontrollgruppe
    bestehen bleibt. Geprueft wird mit dem gepaarten Test auf der
    Differenz der Differenzen; der reine Vorher/Nachher-Test steht
    daneben, weil er die Witterung mitmisst.
    """
    gepaart = gepaarter_test(did.get(f"d_{kennzahl}_station", pd.Series(dtype=float)))
    did_test = gepaarter_test(did.get(f"did_{kennzahl}", pd.Series(dtype=float)))
    bestanden = (np.isfinite(did_test["p"]) and did_test["p"] < 0.05
                 and ((did_test["median"] < 0) if richtung == "sinkt"
                      else (did_test["median"] > 0)))
    return {"kennzahl": kennzahl, "n": did_test["n"],
            "median_station": gepaart["median"], "p_station": gepaart["p"],
            "median_did": did_test["median"], "p_did": did_test["p"],
            "bestanden": bool(bestanden)}


#--------------------------------------------------------------------------
#Plausibilisierung ueber den Energieeinsatz
#--------------------------------------------------------------------------

def effizienz_je_station(panel: pd.DataFrame,
                         min_heizgradstunden: float = 500.0,
                         nur_belegte_tage: bool = True) -> pd.DataFrame:
    """Energieeinsatz je Heizgradstunde, eine Zeile je Station.

    Die Kennzahl normiert den Verbrauch auf die Witterung und macht
    Stationen verschiedener Jahre und Historienlaengen vergleichbar.
    Ohne Normierung auf die Gebaeudegroesse bleibt sie zwischen den
    Stationen allerdings nur eingeschraenkt vergleichbar - ein grosses
    Gebaeude braucht mehr Energie je Heizgradstunde, ohne schlechter zu
    laufen. Sie taugt deshalb fuer den Gruppenvergleich nach Rang und
    nicht als absoluter Massstab.
    """
    teil = panel
    if nur_belegte_tage and "genug_stunden" in panel.columns:
        teil = teil[teil["genug_stunden"].fillna(False).astype(bool)]
    noetig = {"energie_kwh", "heizgradstunden"}
    if not noetig.issubset(teil.columns):
        raise KeyError(f"Spalten {sorted(noetig - set(teil.columns))} fehlen")
    teil = teil.dropna(subset=["energie_kwh", "heizgradstunden"])
    g = teil.groupby("meter")
    out = pd.DataFrame({
        "energie_kwh": g["energie_kwh"].sum(),
        "heizgradstunden": g["heizgradstunden"].sum(),
        "n_tage": g.size(),
    })
    out["energie_je_kh"] = np.where(
        out["heizgradstunden"] >= float(min_heizgradstunden),
        out["energie_kwh"] / out["heizgradstunden"].replace(0, np.nan),
        np.nan)
    return out.reset_index()


def gruppenvergleich(werte_hoch: Sequence[float],
                     werte_niedrig: Sequence[float]) -> dict:
    """Mann-Whitney-U zwischen auffaelliger und unauffaelliger Gruppe."""
    a = pd.Series(list(werte_hoch), dtype=float).dropna()
    b = pd.Series(list(werte_niedrig), dtype=float).dropna()
    out = {"n_hoch": int(len(a)), "n_niedrig": int(len(b)),
           "median_hoch": float(a.median()) if len(a) else np.nan,
           "median_niedrig": float(b.median()) if len(b) else np.nan,
           "p": np.nan}
    if len(a) >= 3 and len(b) >= 3:
        try:
            from scipy import stats
            out["p"] = float(stats.mannwhitneyu(a, b).pvalue)
        except Exception:
            pass
    return out
