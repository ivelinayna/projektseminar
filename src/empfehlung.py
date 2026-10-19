"""
Vom Anomaliescore zur Handlungsempfehlung.

Warum dieses Modul
------------------
Notebook 10 hat zwei Detektoren hinterlassen, die die Begehungs-
validierung bestanden haben, und eine Trefferliste von 21 Stationen.
Ein Score sagt der UEZ aber nur, dass etwas nicht stimmt, nicht was.
Dieses Modul schliesst die Luecke: es benennt je Station ein Muster,
leitet daraus eine Massnahme in der Sprache des Monteurs ab und stuft
den Handlungsbedarf ein.

Was an der ersten Musterzuordnung nicht funktioniert hat
--------------------------------------------------------
`anomalie.muster_je_station` ordnet jeder Station die erste zutreffende
Regel zu. Zwei Konstruktionsfehler fallen dabei zusammen. Erstens sind
die Regeln Konjunktionen aus Quantilsbedingungen: eine Bedingung "oberes
Quintil" trifft 20 Stationen, zwei davon bei nahezu unabhaengigen
Kennzahlen nur noch rund vier. Zweitens wird die Zuordnung auf alle 100
Stationen angewendet, obwohl die meisten unauffaellig sind - eine
gesunde Station bekommt dann die Restkategorie, als waere sie ein
ungeklaerter Fall. Von 59 Stationen ohne Muster waren 47 schlicht
unauffaellig.

Die Antwort darauf sind drei Aenderungen. Die Musterzuordnung laeuft nur
noch auf den Stationen, die von einem der beiden validierten Detektoren
als auffaellig markiert sind; alle anderen heissen ``unauffaellig`` und
tauchen in der Trefferliste nicht auf. Statt harter Konjunktionen
bekommt jedes Muster eine Evidenz, die sich aus robusten z-Werten der
beteiligten Kennzahlen mittelt; zugeordnet wird das Muster mit der
hoechsten Evidenz, sofern diese ueber `MIN_EVIDENZ` liegt. Und der
Katalog ist um die Muster erweitert, die in den auffaelligen Stationen
tatsaechlich sichtbar sind: der Sommerruecklauf, die Station ohne
nennenswerte Abnahme und die Verschlechterung gegenueber dem eigenen
Normalbetrieb, die ueber das stationseigene Residuum laeuft und im
ersten Katalog gar nicht vorkam.

Was die Muster nicht sind
-------------------------
Ein Muster ist eine Beschreibung der Messgroessen, keine Diagnose. "Der
Ruecklauf folgt dem Vorlauf bei hohem Durchfluss und geringer Abnahme"
ist mit einem hydraulischen Kurzschluss konsistent, beweist ihn aber
nicht; dieselbe Signatur kann von einer falsch eingebundenen Zirkulation
oder einem offenen Bypass kommen. Die Massnahmen sind entsprechend als
Pruefauftrag formuliert und nicht als Reparaturanweisung. Welche
Massnahme am Ende zu welchem Muster gehoert, ist eine fachliche
Entscheidung der UEZ; der Katalog hier ist ein begruendeter Vorschlag.

Schweregrad
-----------
Der Schweregrad speist sich aus drei nachvollziehbaren Groessen: wie
weit die Station vom erwarteten Ruecklauf abweicht, wie dauerhaft sie
das tut, und wie viel Volumenstrom der zu warme Ruecklauf zusaetzlich
kostet. Alle drei werden auf 0 bis 1 normiert, gewichtet und zu Punkten
verrechnet. Gewichte und Deckel stehen als Konstanten oben im Modul und
sind Startwerte, keine validierten Groessen.

Der Verbrauch je Heizgradstunde, den Notebook 10 als Plausibilisierung
benutzt, taugt als Schweregradkomponente nicht. Er ist nicht auf die
Gebaeudegroesse normiert, ein grosses Haus liegt dort zwangslaeufig
oben, und der Versuch, ihn ueber die mittlere Leistung zu normieren,
scheitert an den Stationen mit nahezu keiner Abnahme. Verwendet wird
stattdessen der Mehrdurchfluss: liefert eine Station dieselbe Waerme
mit einer um delta K zu kleinen Spreizung, muss sie den Volumenstrom um
etwa delta geteilt durch die Spreizung erhoehen. Diese Groesse ist
dimensionslos, groessenunabhaengig und direkt verstaendlich. Der
Verbrauch je Heizgradstunde bleibt als informative Spalte in der Liste.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import anomalie as an

#Ab dieser Evidenz gilt ein Muster als benannt. Die Evidenz ist ein
#Mittel robuster z-Werte, 0,6 entspricht also gut einem halben
#robusten Sigma ueber alle beteiligten Kennzahlen.
MIN_EVIDENZ = 0.6

#Persistenzanteil, ab dem eine Station als auffaellig in die
#Trefferliste kommt. Entspricht der Schwelle aus Notebook 10.
MIN_PERSISTENZ = 0.10

#Deckel der Schweregradkomponenten: ab diesen Werten zaehlt die
#Komponente voll. Der Ruecklaufdeckel ist bewusst grob - 15 K ueber der
#Netzerwartung ist ein Fall, bei dem niemand mehr diskutiert. Beim
#Mehrdurchfluss gilt ein Drittel ueber dem noetigen Volumenstrom als
#voller Ausschlag.
DECKEL_ABWEICHUNG_K = 15.0
DECKEL_PERSISTENZ = 0.50
DECKEL_MEHRDURCHFLUSS = 0.33

#Gewichte der drei Komponenten, Summe 1
W_ABWEICHUNG = 0.45
W_PERSISTENZ = 0.35
W_EFFIZIENZ = 0.20

#Punktegrenzen der Schweregradstufen
STUFE_HOCH = 55.0
STUFE_MITTEL = 30.0

#Restkategorie, bewusst so benannt, dass sie nicht nach Entwarnung klingt
OHNE_MUSTER = "auffaellig ohne klares Muster"
UNAUFFAELLIG = "unauffaellig"

assert abs(W_ABWEICHUNG + W_PERSISTENZ + W_EFFIZIENZ - 1.0) < 1e-9


#--------------------------------------------------------------------------
#Musterkatalog
#--------------------------------------------------------------------------

#Jedes Muster nennt seine Kennzahlen mit Richtung und Gewicht, einen
#Klartext fuer den Monteur und einen Hinweis, worauf vor Ort zu achten
#ist. "hoch" heisst, ein hoher robuster z-Wert spricht fuer das Muster,
#"niedrig" das Gegenteil. Die Gewichte sind relativ innerhalb eines
#Musters und muessen sich nicht zu eins summieren.
MUSTERKATALOG: Sequence[Dict[str, object]] = (
    {
        "name": "Durchfluss ohne Auskuehlung, Verdacht hydraulischer Kurzschluss",
        "indikatoren": {"dt_winter": ("niedrig", 1.5),
                        "flow": ("hoch", 1.0),
                        "last": ("niedrig", 0.5),
                        "anteil_kurzschluss": ("hoch", 1.0)},
        "massnahme": ("Volumenstrom am Regelventil begrenzen, Bypass und "
                      "Beimischung auf Kurzschluss pruefen, Schmutzfaenger "
                      "kontrollieren"),
        "achten_auf": ("Vorlauf und Ruecklauf liegen dicht beieinander, "
                       "obwohl kaum Waerme abgenommen wird"),
    },
    {
        "name": "Hoher Ruecklauf im Sommer, Verdacht Zirkulations- oder Speicherverlust",
        "indikatoren": {"rt_delta_saison": ("hoch", 1.5),
                        "last_sommer": ("niedrig", 0.75),
                        "rt_sommer": ("hoch", 0.75)},
        "massnahme": ("Zeitprogramm der Zirkulationspumpe und der "
                      "Warmwasserbereitung pruefen, Speicherladung und "
                      "Daemmung der Zirkulationsleitung ansehen"),
        "achten_auf": ("der Ruecklauf liegt im Sommer ueber dem Winterwert, "
                       "obwohl im Sommer kaum geheizt wird"),
    },
    {
        "name": "Unruhige Regelung",
        "indikatoren": {"d2": ("hoch", 1.5), "d1": ("hoch", 1.0)},
        "massnahme": ("Regler und Stellantrieb pruefen, Regelparameter und "
                      "Sitz der Fuehler kontrollieren"),
        "achten_auf": ("die Ruecklauftemperatur schwankt staendig, der "
                       "Regler findet keine Ruhe"),
    },
    {
        "name": "Ruecklauf reagiert kaum, Verdacht festsitzendes oder offenes Ventil",
        "indikatoren": {"traege": ("hoch", 1.0), "reak": ("hoch", 1.0),
                        "d1": ("niedrig", 1.0)},
        "massnahme": ("Stellantrieb auf Gaengigkeit pruefen, Ventil auf "
                      "Festsitzen oder Dauerstellung offen pruefen"),
        "achten_auf": ("die Ruecklauftemperatur bewegt sich auch dann kaum, "
                       "wenn sich die Abnahme aendert"),
    },
    {
        "name": "Keine nennenswerte Abnahme bei warmem Ruecklauf",
        "indikatoren": {"last": ("niedrig", 1.5), "flow": ("niedrig", 1.0),
                        "rt_winter": ("hoch", 1.0)},
        "massnahme": ("vor Ort klaeren, ob das Objekt ueberhaupt genutzt "
                      "wird, Hausanschluss und Zirkulation pruefen, "
                      "Anschlussleistung gegebenenfalls anpassen"),
        "achten_auf": ("die Station haelt Temperatur, ohne dass Waerme "
                       "abgenommen wird"),
    },
    {
        "name": "Ruecklauf dauerhaft ueber der Netzerwartung",
        "indikatoren": {"score_netz": ("hoch", 1.5),
                        "dt_winter": ("niedrig", 0.75),
                        "perf": ("niedrig", 0.5)},
        "generisch": True,
        "massnahme": ("hydraulischen Abgleich pruefen, Heizkurve und "
                      "Ruecklaufbegrenzung nachstellen, Schmutzfaenger "
                      "reinigen"),
        "achten_auf": ("die Station laeuft dauerhaft waermer zurueck als "
                       "vergleichbare Haeuser bei gleicher Witterung"),
    },
    {
        "name": "Verschlechterung gegenueber dem eigenen Normalbetrieb",
        "indikatoren": {"score_station": ("hoch", 1.5),
                        "pers_station": ("hoch", 1.0)},
        "generisch": True,
        "massnahme": ("pruefen, was sich geaendert hat: Regeleinstellungen "
                      "und Ventilstellungen mit dem letzten "
                      "Begehungsprotokoll abgleichen"),
        "achten_auf": ("die Station laeuft schlechter als sie selbst frueher "
                       "lief, unabhaengig vom Netzvergleich"),
    },
)

#Massnahme fuer die Restkategorie. Keine Vorabdiagnose heisst nicht
#keine Handlung - die Station ist auffaellig, nur nicht erklaert.
MASSNAHME_OHNE_MUSTER = ("Begehung ohne Vorabdiagnose: Anlage vollstaendig "
                         "aufnehmen, Regelung, Ventile und Zirkulation der "
                         "Reihe nach pruefen")


#--------------------------------------------------------------------------
#Stationskennzahlen
#--------------------------------------------------------------------------

def kennzahlen(panel: pd.DataFrame,
               kurzschluss_spalte: Optional[str] = None,
               nur_belegte_tage: bool = True) -> pd.DataFrame:
    """Eine Zeile je Station mit allen Groessen, die der Katalog braucht.

    Aggregiert wird ueber den Median der Tageswerte, bei den
    Zustandsanteilen ueber den Mittelwert - ein Anteil ist bereits eine
    Haeufigkeit, sein Median ueber die Tage waere meist null.
    Saisongroessen kommen aus `season`: ``kernwinter`` und ``sommer``.
    Stationen ohne Sommer- oder Wintertage bekommen dort NaN, das
    schliesst sie von den saisonabhaengigen Mustern aus, nicht von den
    uebrigen.
    """
    teil = panel
    if nur_belegte_tage and "genug_stunden" in panel.columns:
        teil = teil[teil["genug_stunden"].fillna(False).astype(bool)]

    netz = f"score_{an.D_RESID_NETZ}"
    station = f"score_{an.D_RESID_STATION}"
    agg = {"rt": ("rt_median", "median"),
           "dt": ("dt_mean_loaded", "median"),
           "last": ("last_anteil", "median"),
           "flow": ("flow_median", "median"),
           "kopp": ("rt_vl_kopplung", "median"),
           "d1": ("rt_d1_abs_mean", "median"),
           "d2": ("rt_d2_abs_mean", "median"),
           "traege": ("rt_traege_anteil", "median"),
           "reak": ("reaktionszeit_h", "median"),
           "perf": ("performance", "median"),
           "spanne": ("rt_spanne_k", "median"),
           "power": ("power_mean", "median")}
    agg = {k: v for k, v in agg.items() if v[0] in teil.columns}
    out = teil.groupby("meter").agg(**agg)
    out["n_tage"] = teil.groupby("meter").size()
    for name, spalte in ((("score_netz"), netz), (("score_station"), station)):
        if spalte in teil.columns:
            out[name] = teil.groupby("meter")[spalte].mean()
        pers = f"persistent_{spalte}"
        if pers in teil.columns:
            ziel = "pers_netz" if name == "score_netz" else "pers_station"
            out[ziel] = (teil.groupby("meter")[pers]
                         .apply(lambda s: s.fillna(False).astype(bool).mean()))

    if "season" in teil.columns:
        winter = teil[teil["season"] == "kernwinter"]
        sommer = teil[teil["season"] == "sommer"]
        out["rt_winter"] = winter.groupby("meter")["rt_median"].median()
        out["dt_winter"] = winter.groupby("meter")["dt_mean_loaded"].median()
        out["rt_sommer"] = sommer.groupby("meter")["rt_median"].median()
        out["last_sommer"] = sommer.groupby("meter")["last_anteil"].median()
        out["rt_delta_saison"] = out["rt_sommer"] - out["rt_winter"]

    if kurzschluss_spalte is None:
        kurzschluss_spalte = _kurzschluss_spalte(teil)
    if kurzschluss_spalte and kurzschluss_spalte in teil.columns:
        out["anteil_kurzschluss"] = teil.groupby("meter")[kurzschluss_spalte].mean()

    return out.reset_index()


def _kurzschluss_spalte(panel: pd.DataFrame) -> Optional[str]:
    """Spalte des Zustands mit Kurzschlussverdacht, falls im Panel.

    Notebook 10 bestimmt den Zustand datengetrieben und gibt ihn an das
    Panel weiter. Fehlt diese Information, faellt die Funktion auf None
    zurueck und das zugehoerige Muster verliert eine seiner Kennzahlen,
    ohne auszufallen.
    """
    name = panel.attrs.get("kurzschlussspalte")
    if isinstance(name, str) and name in panel.columns:
        return name
    nummer = panel.attrs.get("kurzschlusscluster")
    if nummer is not None and f"anteil_c{int(nummer)}" in panel.columns:
        return f"anteil_c{int(nummer)}"
    return None


def effizienz(panel: pd.DataFrame,
              profil: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Verbrauch je Heizgradstunde und geschaetzter Mehrdurchfluss.

    `anomalie.effizienz_je_station` liefert den Verbrauch je
    Heizgradstunde. Die Groesse bleibt hier erhalten, weil sie in
    Notebook 10 als Plausibilisierung dient, taugt aber nicht als
    absoluter Massstab: sie ist nicht auf die Gebaeudegroesse normiert.

    Der Mehrdurchfluss dagegen ist groessenunabhaengig. Liefert eine
    Station dieselbe Waerme mit einer um `abweichung_k` zu kleinen
    Spreizung, dann waere die gesunde Spreizung um diesen Betrag
    groesser, und der noetige Volumenstrom steigt um etwa
    ``abweichung_k / spreizung``. ``verlust_kwh_je_kh`` multipliziert
    diesen Anteil mit dem Verbrauch je Heizgradstunde und ist damit eine
    grobe Schaetzung der zusaetzlich umgewaelzten Energie je
    Heizgradstunde - grob deshalb, weil Netzverluste, Vorlauftemperatur
    und Pumpenkennlinie nicht eingehen.
    """
    eff = an.effizienz_je_station(panel)
    if profil is None:
        return eff
    teil = profil[["meter"]].copy()
    netz = pd.to_numeric(profil.get("score_netz", np.nan), errors="coerce")
    station = pd.to_numeric(profil.get("score_station", np.nan), errors="coerce")
    teil["abweichung_k"] = pd.concat([netz, station], axis=1).max(axis=1).to_numpy()
    spreizung = pd.to_numeric(profil.get("dt_winter", np.nan), errors="coerce")
    ersatz = pd.to_numeric(profil.get("dt", np.nan), errors="coerce")
    teil["spreizung_k"] = spreizung.fillna(ersatz).to_numpy()
    eff = eff.merge(teil, on="meter", how="outer")
    anteil = eff["abweichung_k"].clip(lower=0) / eff["spreizung_k"]
    eff["mehrdurchfluss"] = anteil.replace([np.inf, -np.inf], np.nan)
    eff["verlust_kwh_je_kh"] = eff["mehrdurchfluss"] * eff["energie_je_kh"]
    return eff


#--------------------------------------------------------------------------
#Musterzuordnung ueber Evidenz
#--------------------------------------------------------------------------

def robuste_z(profil: pd.DataFrame,
              spalten: Optional[Sequence[str]] = None,
              skala: str = "rang") -> pd.DataFrame:
    """Vergleichbare z-Werte je Kennzahl ueber die Stationen.

    Zwei Skalen stehen zur Wahl. ``mad`` normiert mit Median und
    mittlerer absoluter Abweichung. Das ist robust gegen Ausreisser,
    scheitert aber an den stark schiefen Kennzahlen dieses Datensatzes:
    der Median des Volumenstroms liegt bei 38 l/h, das Maximum bei
    14.500, und ein Viertel der Stationen steht auf null. Die MAD ist
    dort so klein, dass einzelne Stationen z-Werte jenseits von 80
    bekommen und jede Kappung willkuerlich wird.

    ``rang`` wandelt deshalb jede Kennzahl erst in ihren Rang und diesen
    ueber die inverse Normalverteilung in einen z-Wert um. Die Skala ist
    danach fuer alle Kennzahlen dieselbe, unabhaengig von der Form der
    Verteilung. Der Preis ist, dass der Abstand zwischen den Werten
    verloren geht: eine Station mit dem zehnfachen Volumenstrom des
    Nachbarn steht nur noch einen Rang weiter. Fuer die Musterzuordnung
    ist das richtig, weil dort die relative Lage zaehlt; fuer den
    Schweregrad wird bewusst mit den Rohwerten gerechnet.

    Bindungen bekommen denselben mittleren Rang. Dass 25 Stationen mit
    Volumenstrom null alle auf demselben z-Wert landen, ist gewollt -
    sie sind in dieser Kennzahl nicht unterscheidbar.
    """
    spalten = [s for s in (spalten or profil.columns)
               if s not in ("meter", "n_tage")]
    out = pd.DataFrame({"meter": profil["meter"].astype(int)})
    for spalte in spalten:
        werte = pd.to_numeric(profil[spalte], errors="coerce")
        if skala == "rang":
            out[spalte] = _normalscore(werte)
            continue
        median = werte.median()
        mad = (werte - median).abs().median()
        streu = 1.4826 * mad if mad > 0 else werte.std(ddof=0)
        if not streu or not np.isfinite(streu):
            out[spalte] = np.nan
            continue
        out[spalte] = (werte - median) / streu
    return out


def _normalscore(werte: pd.Series) -> pd.Series:
    """Rang in z-Wert umrechnen, fehlende Werte bleiben fehlend."""
    gueltig = werte.notna()
    n = int(gueltig.sum())
    out = pd.Series(np.nan, index=werte.index, dtype=float)
    if n < 3:
        return out
    rang = werte[gueltig].rank(method="average")
    p = (rang - 0.5) / n
    try:
        from scipy import stats
        out.loc[gueltig] = stats.norm.ppf(p)
    except Exception:
        #Naeherung ohne scipy: Logit-Skala, auf aehnliche Breite gestreckt
        out.loc[gueltig] = np.log(p / (1 - p)) / 1.702
    return out


def musterzuordnung(profil: pd.DataFrame,
                    katalog: Sequence = MUSTERKATALOG,
                    min_evidenz: float = MIN_EVIDENZ,
                    grenze: float = 3.0) -> pd.DataFrame:
    """Jeder Station das Muster mit der hoechsten Evidenz zuordnen.

    Die Evidenz eines Musters ist das gewichtete Mittel der gerichteten
    robusten z-Werte seiner Kennzahlen, auf `grenze` gekappt, damit eine
    einzelne extreme Kennzahl ein Muster nicht allein traegt. Fehlende
    Kennzahlen gehen nicht mit null ein, sondern fallen aus dem Mittel
    heraus; wie viele uebrig blieben, steht in ``n_kennzahlen``.

    Zwei Muster im Katalog sind als ``generisch`` markiert: der
    dauerhaft zu warme Ruecklauf gegenueber dem Netz und die
    Verschlechterung gegenueber dem eigenen Normalbetrieb. Beide sagen
    im Kern nur, welcher Detektor angeschlagen hat, und wuerden die
    spezifischen Muster sonst verdraengen, weil ihre Kennzahlen
    dieselben sind, die die Station ueberhaupt auffaellig gemacht haben.
    Sie kommen deshalb erst zum Zug, wenn kein spezifisches Muster die
    Mindestevidenz erreicht.

    Die Rueckgabe enthaelt neben dem Muster auch das zweitbeste und den
    Abstand. Ein kleiner Abstand heisst, dass die Zuordnung auf der
    Kippe steht - diese Faelle gehoeren in jede Auswertung, statt als
    eindeutig ausgegeben zu werden.
    """
    z = robuste_z(profil)
    zeilen = []
    for i, meter in enumerate(z["meter"]):
        bewertung = []
        for muster in katalog:
            summe, gewicht, n = 0.0, 0.0, 0
            teile = []
            for spalte, (richtung, g) in muster["indikatoren"].items():
                if spalte not in z.columns:
                    continue
                wert = z[spalte].iloc[i]
                if not np.isfinite(wert):
                    continue
                beitrag = wert if richtung == "hoch" else -wert
                beitrag = float(np.clip(beitrag, -grenze, grenze))
                summe += g * beitrag
                gewicht += g
                n += 1
                teile.append((spalte, beitrag, profil[spalte].iloc[i]))
            if n == 0 or gewicht == 0:
                continue
            bewertung.append({"name": muster["name"], "evidenz": summe / gewicht,
                              "n": n, "teile": teile,
                              "generisch": bool(muster.get("generisch", False))})
        bewertung.sort(key=lambda b: b["evidenz"], reverse=True)
        spezifisch = [b for b in bewertung if not b["generisch"]]
        passend = [b for b in spezifisch if b["evidenz"] >= min_evidenz]
        #ein spezifisches Muster schlaegt die beiden Auffangmuster, sobald
        #es die Mindestevidenz nimmt; verglichen wird dann innerhalb der
        #spezifischen Muster, sonst ueber den ganzen Katalog
        pool = spezifisch if passend else bewertung
        bester = pool[0] if pool else None
        zweiter = pool[1] if len(pool) > 1 else None
        if bester is not None and bester["evidenz"] >= min_evidenz:
            zeilen.append({
                "meter": int(meter),
                "muster": bester["name"],
                "evidenz": round(float(bester["evidenz"]), 3),
                "n_kennzahlen": bester["n"],
                "zweitmuster": zweiter["name"] if zweiter else "",
                "abstand": (round(float(bester["evidenz"] - zweiter["evidenz"]), 3)
                            if zweiter else np.nan),
                "begruendung": _begruendung(bester["teile"]),
            })
        else:
            zeilen.append({
                "meter": int(meter),
                "muster": OHNE_MUSTER,
                "evidenz": (round(float(bester["evidenz"]), 3)
                            if bester else np.nan),
                "n_kennzahlen": bester["n"] if bester else 0,
                "zweitmuster": bester["name"] if bester else "",
                "abstand": np.nan,
                "begruendung": ("keine Kennzahl weicht deutlich genug ab, "
                                "um ein Muster zu tragen"),
            })
    return pd.DataFrame(zeilen)


def _begruendung(teile: Sequence[Tuple[str, float, float]],
                 hoechstens: int = 3) -> str:
    """Die staerksten Kennzahlen eines Musters als lesbarer Satz."""
    stark = sorted(teile, key=lambda t: abs(t[1]), reverse=True)[:hoechstens]
    return "; ".join(f"{name} {wert:.3g} ({beitrag:+.1f} Sigma)"
                     for name, beitrag, wert in stark)


def auffaellige_stationen(profil: pd.DataFrame,
                          min_persistenz: float = MIN_PERSISTENZ) -> pd.Series:
    """Welche Stationen von einem der validierten Detektoren kommen.

    Geprueft wird der Persistenzanteil beider Residuendetektoren. Die
    Oder-Verknuepfung ist Absicht: die beiden messen nachweislich
    Verschiedenes, ihre Rangkorrelation liegt bei 0,10. Wer nur den
    netzweiten nimmt, verliert die Stationen, die sich gegenueber ihrer
    eigenen Vergangenheit verschlechtert haben.
    """
    netz = _zahlenspalte(profil, "pers_netz")
    station = _zahlenspalte(profil, "pers_station")
    return (netz.fillna(0) > min_persistenz) | (station.fillna(0) > min_persistenz)


#--------------------------------------------------------------------------
#Schweregrad
#--------------------------------------------------------------------------

def _zahlenspalte(df: pd.DataFrame, name: str) -> pd.Series:
    """Spalte als Zahlenreihe, fehlende Spalten als Reihe aus NaN."""
    if name not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float, name=name)
    return pd.to_numeric(df[name], errors="coerce")


def schweregrad(profil: pd.DataFrame,
                eff: Optional[pd.DataFrame] = None,
                gewichte: Optional[Mapping[str, float]] = None,
                deckel: Optional[Mapping[str, float]] = None) -> pd.DataFrame:
    """Punkte 0 bis 100 je Station aus drei offengelegten Komponenten.

    Die Abweichungskomponente nimmt das groessere der beiden
    Residuenmittel in Kelvin und teilt durch `DECKEL_ABWEICHUNG_K`; die
    Persistenzkomponente den groesseren der beiden Persistenzanteile;
    die Effizienzkomponente den geschaetzten Mehrdurchfluss. Jede
    Komponente ist einzeln in der Rueckgabe sichtbar, damit sich jede
    Punktzahl zurueckrechnen laesst.

    Dass alle drei Komponenten aus derselben Richtung kommen - ein zu
    warmer Ruecklauf - ist kein Versehen, aber eine Einschraenkung: ein
    Fehler, der sich nicht im Ruecklauf zeigt, bekommt hier keine
    Punkte.
    """
    g = {"abweichung": W_ABWEICHUNG, "persistenz": W_PERSISTENZ,
         "effizienz": W_EFFIZIENZ}
    g.update(gewichte or {})
    d = {"abweichung": DECKEL_ABWEICHUNG_K, "persistenz": DECKEL_PERSISTENZ,
         "effizienz": DECKEL_MEHRDURCHFLUSS}
    d.update(deckel or {})

    out = profil[["meter"]].copy()
    netz = _zahlenspalte(profil, "score_netz")
    station = _zahlenspalte(profil, "score_station")
    abweichung = pd.concat([netz, station], axis=1).max(axis=1)
    out["abweichung_k"] = abweichung.to_numpy()
    out["komp_abweichung"] = (out["abweichung_k"] / d["abweichung"]).clip(0, 1)

    p_netz = _zahlenspalte(profil, "pers_netz")
    p_station = _zahlenspalte(profil, "pers_station")
    persistenz = pd.concat([p_netz, p_station], axis=1).max(axis=1)
    out["persistenz"] = persistenz.to_numpy()
    out["komp_persistenz"] = (out["persistenz"] / d["persistenz"]).clip(0, 1)

    if eff is not None and "mehrdurchfluss" in eff.columns:
        spalten = [s for s in ("meter", "mehrdurchfluss", "verlust_kwh_je_kh",
                               "energie_je_kh") if s in eff.columns]
        zusatz = profil[["meter"]].merge(eff[spalten], on="meter", how="left")
        for s in spalten[1:]:
            out[s] = zusatz[s].to_numpy()
    else:
        out["mehrdurchfluss"] = np.nan
    out["komp_effizienz"] = (out["mehrdurchfluss"] / d["effizienz"]).clip(0, 1)

    #fehlende Effizienzangabe darf den Schweregrad nicht senken, deshalb
    #wird in diesem Fall nur ueber die beiden anderen Komponenten gemittelt
    fehlt = out["komp_effizienz"].isna()
    gewichtet = (g["abweichung"] * out["komp_abweichung"].fillna(0)
                 + g["persistenz"] * out["komp_persistenz"].fillna(0)
                 + g["effizienz"] * out["komp_effizienz"].fillna(0))
    teiler = np.where(fehlt, g["abweichung"] + g["persistenz"], 1.0)
    out["punkte"] = (100 * gewichtet / teiler).round(1)
    out["stufe"] = np.where(out["punkte"] >= STUFE_HOCH, "hoch",
                            np.where(out["punkte"] >= STUFE_MITTEL,
                                     "mittel", "niedrig"))
    return out


#--------------------------------------------------------------------------
#Trefferliste
#--------------------------------------------------------------------------

#Spalten des Exports. Bewusst ohne Adresse, Kundenname oder Koordinate -
#die UEZ ordnet die Zaehlernummer selbst zu, ausliefern duerfen wir sie
#nicht.
EXPORTSPALTEN = ["meter", "muster", "stufe", "punkte", "massnahme",
                 "begruendung_kurz", "evidenz", "zweitmuster", "abstand",
                 "persistenz", "abweichung_k", "mehrdurchfluss",
                 "verlust_kwh_je_kh", "n_tage"]


def trefferliste(profil: pd.DataFrame,
                 eff: Optional[pd.DataFrame] = None,
                 katalog: Sequence = MUSTERKATALOG,
                 min_persistenz: float = MIN_PERSISTENZ,
                 min_evidenz: float = MIN_EVIDENZ) -> pd.DataFrame:
    """Priorisierte Liste der auffaelligen Stationen.

    Die Musterzuordnung laeuft auf allen Stationen, weil die z-Werte
    ihre Bezugsverteilung aus dem ganzen Netz ziehen; in die Liste
    kommen aber nur die auffaelligen. Unauffaellige Stationen bekommen
    das Muster ``unauffaellig`` und bleiben in der Rueckgabe von
    `musterzuordnung` nachvollziehbar, tauchen in der Trefferliste
    jedoch nicht auf.
    """
    muster = musterzuordnung(profil, katalog, min_evidenz)
    grad = schweregrad(profil, eff)
    tab = (profil[["meter", "n_tage"]].merge(muster, on="meter", how="left")
           .merge(grad, on="meter", how="left"))
    tab["auffaellig"] = auffaellige_stationen(profil, min_persistenz).to_numpy()
    tab.loc[~tab["auffaellig"], "muster"] = UNAUFFAELLIG

    massnahmen = {m["name"]: m["massnahme"] for m in katalog}
    achten = {m["name"]: m["achten_auf"] for m in katalog}
    tab["massnahme"] = tab["muster"].map(massnahmen).fillna(
        MASSNAHME_OHNE_MUSTER)
    tab["begruendung_kurz"] = [
        _satz(zeile, achten) for _, zeile in tab.iterrows()]

    treffer = tab[tab["auffaellig"]].copy()
    treffer = treffer.sort_values("punkte", ascending=False)
    return treffer[[s for s in EXPORTSPALTEN if s in treffer.columns]]\
        .reset_index(drop=True)


def _satz(zeile: pd.Series, achten: Mapping[str, str]) -> str:
    """Ein Satz, der die Einstufung ohne Modellsprache erklaert."""
    hinweis = achten.get(zeile["muster"])
    pers = zeile.get("persistenz", np.nan)
    anteil = f"{100 * pers:.0f} Prozent" if np.isfinite(pers) else "einem Teil"
    if hinweis:
        return (f"An {anteil} der ausgewerteten Tage auffaellig; {hinweis}.")
    return (f"An {anteil} der ausgewerteten Tage auffaellig, ohne dass eine "
            f"einzelne Kennzahl die Ursache eingrenzt.")


def musterbilanz(profil: pd.DataFrame,
                 katalog: Sequence = MUSTERKATALOG,
                 min_persistenz: float = MIN_PERSISTENZ,
                 min_evidenz: float = MIN_EVIDENZ) -> pd.DataFrame:
    """Wie oft jedes Muster vergeben wird, getrennt nach auffaellig.

    Diese Tabelle ist die ehrliche Gegenprobe zur Trefferliste: sie
    zeigt, wie gross die Restkategorie unter den auffaelligen Stationen
    wirklich ist und wie viele Stationen nur deshalb kein Muster haben,
    weil sie unauffaellig sind.
    """
    muster = musterzuordnung(profil, katalog, min_evidenz)
    auff = auffaellige_stationen(profil, min_persistenz)
    muster = muster.merge(profil[["meter"]].assign(auffaellig=auff.to_numpy()),
                          on="meter", how="left")
    muster.loc[~muster["auffaellig"], "muster"] = UNAUFFAELLIG
    out = (muster.groupby(["muster", "auffaellig"]).size()
           .reset_index(name="n_stationen"))
    return out.sort_values(["auffaellig", "n_stationen"], ascending=[False, False])


def rangliste_messdaten(treffer: pd.DataFrame) -> pd.DataFrame:
    """Rangliste der Muster aus den Messdaten, als Gegenstueck zu den Texten.

    Gezaehlt werden Stationen, nicht Begehungen. Der Vergleich mit der
    Rangliste aus den Begehungstexten ist deshalb einer zwischen zwei
    verschieden erhobenen Groessen und kein Konsistenztest.
    """
    if not len(treffer):
        return pd.DataFrame(columns=["muster", "n_stationen", "anteil",
                                     "n_hoch", "n_mittel", "n_niedrig"])
    out = (treffer.groupby("muster")
           .agg(n_stationen=("meter", "size"),
                n_hoch=("stufe", lambda s: int((s == "hoch").sum())),
                n_mittel=("stufe", lambda s: int((s == "mittel").sum())),
                n_niedrig=("stufe", lambda s: int((s == "niedrig").sum())))
           .reset_index())
    out["anteil"] = out["n_stationen"] / len(treffer)
    return out.sort_values("n_stationen", ascending=False).reset_index(drop=True)


def abdeckung(treffer: pd.DataFrame,
              stufen: Sequence[str] = ("hoch", "mittel", "niedrig")) -> pd.DataFrame:
    """Wie viele Begehungen decken welchen Anteil der Auffaelligkeit ab.

    Gerechnet wird kumulativ ueber die nach Punkten sortierte Liste:
    nach n Begehungen ist der Anteil der Punktsumme abgedeckt, der in
    den ersten n Stationen steckt. Das ist eine Buchhaltung ueber den
    eigenen Score und kein Nachweis, dass die Begehung etwas bewirkt.
    """
    teil = treffer[treffer["stufe"].isin(stufen)].sort_values(
        "punkte", ascending=False)
    if not len(teil):
        return pd.DataFrame(columns=["n_begehungen", "anteil_punkte",
                                     "anteil_stationen"])
    punkte = pd.to_numeric(teil["punkte"], errors="coerce").fillna(0)
    out = pd.DataFrame({
        "n_begehungen": np.arange(1, len(teil) + 1),
        "anteil_punkte": punkte.cumsum().to_numpy() / punkte.sum(),
    })
    out["anteil_stationen"] = out["n_begehungen"] / len(teil)
    return out


def nutzenbilanz(treffer: pd.DataFrame,
                 wintervergleich: pd.DataFrame) -> Dict[str, object]:
    """Gegenprobe der Trefferliste an den ausgewerteten Begehungen.

    Der Wintervergleich teilt jede auswertbare Begehung danach ein, ob
    der Ruecklauf im Winter davor und im Winter danach ueber der
    Schwelle lag. Begehungen mit schlechtem Zustand vorher und nachher
    haben den Zustand nicht verbessert; genau die sollte ein nuetzliches
    Modell vorher kennen. Verglichen wird deshalb der Zustand nach der
    Begehung mit dem heutigen Befund der Trefferliste.

    Das ist keine Vorhersage. Die Trefferliste wird aus dem gesamten
    Beobachtungszeitraum gerechnet, der die Zeit nach der Begehung
    einschliesst. Die Zahl sagt, wie zuverlaessig das Modell einen
    weiter bestehenden Missstand benennt, nicht ob es ihn vorausgesagt
    haette.
    """
    w = wintervergleich
    if "auswertbar" in w.columns:
        w = w[w["auswertbar"].fillna(False).astype(bool)]
    w = w.dropna(subset=["zustand_vor", "zustand_nach"]).copy()
    w["meter"] = pd.to_numeric(w["meter"], errors="coerce").astype("Int64")

    erkannt = set(pd.to_numeric(treffer["meter"], errors="coerce").dropna()
                  .astype(int))
    w["erkannt"] = w["meter"].astype(float).astype(int).isin(erkannt)

    tafel = pd.crosstab([w["zustand_vor"], w["zustand_nach"]], w["erkannt"])
    tafel = tafel.rename(columns={True: "in_trefferliste",
                                  False: "nicht_erkannt"})
    schlecht_nach = w[w["zustand_nach"] == "schlecht"]
    gut_nach = w[w["zustand_nach"] == "gut"]
    ohne_wirkung = w[(w["zustand_vor"] == "schlecht")
                     & (w["zustand_nach"] == "schlecht")]
    return {
        "tafel": tafel.reset_index(),
        "n_begehungen": int(len(w)),
        "n_ohne_wirkung": int(len(ohne_wirkung)),
        "anteil_ohne_wirkung": float(len(ohne_wirkung) / len(w)) if len(w) else np.nan,
        "ohne_wirkung_erkannt": int(ohne_wirkung["erkannt"].sum()),
        "trefferquote_schlecht": float(schlecht_nach["erkannt"].mean())
        if len(schlecht_nach) else np.nan,
        "fehlalarm_gut": float(gut_nach["erkannt"].mean())
        if len(gut_nach) else np.nan,
        "meter_ohne_wirkung": sorted(int(m) for m in ohne_wirkung["meter"]),
    }


def exportiere(treffer: pd.DataFrame, pfad: str) -> str:
    """Trefferliste als CSV, bewusst ohne Adress- und Kundenbezug.

    Ausgegeben wird nur die Zaehlernummer. Der Netzbetreiber kann die
    Adresse aus seinen eigenen Stammdaten ergaenzen; aus diesem Projekt
    geht sie nicht hinaus. Zusaetzlich wird geprueft, dass keine Spalte
    mit Adress- oder Namensbezug mitlaeuft.
    """
    verboten = [s for s in treffer.columns
                if any(w in s.lower() for w in
                       ("adresse", "address", "strasse", "name", "kunde",
                        "ort", "plz", "lat", "lon", "geometry"))]
    if verboten:
        raise ValueError(f"Spalten mit Personenbezug im Export: {verboten}")
    import os
    os.makedirs(os.path.dirname(pfad) or ".", exist_ok=True)
    treffer.to_csv(pfad, index=False, encoding="utf-8")
    return pfad


#--------------------------------------------------------------------------
#Erklaerbares Baummodell
#--------------------------------------------------------------------------

#Merkmale des Baums. Der Ruecklauf selbst steht bewusst nicht darin: die
#Zielgroesse ist das Residuum des Ruecklaufs, ein Baum auf `rt_median`
#wuerde seine eigene Zielgroesse lernen und nichts erklaeren. Aus dem
#selben Grund fehlen Spreizung und Ruecklaufspanne - beide sind
#rechnerisch aus Vorlauf minus Ruecklauf gebildet, ein Baum darauf sagt
#nur, dass ein warmer Ruecklauf die Spreizung klein macht. Uebrig
#bleiben Groessen, die den Betriebszustand unabhaengig beschreiben.
BAUMMERKMALE = ("last_anteil", "flow_median", "rt_vl_kopplung",
                "rt_d1_abs_mean", "rt_d2_abs_mean", "rt_traege_anteil",
                "reaktionszeit_h", "power_mean", "t_out_tag",
                "n_lastwechsel")

#Vergleichssatz mit Spreizung, nur um den Unterschied zu zeigen
BAUMMERKMALE_MIT_SPREIZUNG = BAUMMERKMALE + ("dt_mean_loaded", "rt_spanne_k")


def baumdaten(panel: pd.DataFrame,
              merkmale: Sequence[str] = BAUMMERKMALE,
              ziel: Optional[str] = None,
              nur_belegte_tage: bool = True) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Merkmalsmatrix, Zielgroesse und Gruppenschluessel fuer den Baum.

    Gerechnet wird auf Stationstagen und nicht auf Stationsmitteln, weil
    100 Zeilen fuer einen Baum zu wenig sind. Die Gruppe ist die Station;
    sie wird gebraucht, damit die Kreuzvalidierung ganze Stationen
    heraushaelt. Ohne das waeren Trainings- und Testzeilen derselben
    Station im selben Modell, und jede Guetezahl waere geschoent.
    """
    ziel = ziel or f"score_{an.D_RESID_NETZ}"
    teil = panel
    if nur_belegte_tage and "genug_stunden" in panel.columns:
        teil = teil[teil["genug_stunden"].fillna(False).astype(bool)]
    vorhanden = [m for m in merkmale if m in teil.columns]
    teil = teil.dropna(subset=vorhanden + [ziel, "meter"])
    return teil[vorhanden].copy(), teil[ziel].copy(), teil["meter"].copy()


def fitte_baum(X: pd.DataFrame, y: pd.Series, tiefe: int = 3,
               min_blatt: int = 200, seed: int = an.SEED):
    """Flacher Regressionsbaum auf den Betriebskennzahlen.

    Die Tiefe ist absichtlich klein. Ein tiefer Baum sagt besser vorher
    und erklaert nichts mehr; hier geht es um die Frage, an welchen
    Kennzahlen ein zu warmer Ruecklauf haengt, und die Antwort soll auf
    eine Folie passen.
    """
    from sklearn.tree import DecisionTreeRegressor
    baum = DecisionTreeRegressor(max_depth=int(tiefe),
                                 min_samples_leaf=int(min_blatt),
                                 random_state=int(seed))
    baum.fit(X, y)
    return baum


def baum_stabilitaet(X: pd.DataFrame, y: pd.Series, gruppen: pd.Series,
                     tiefe: int = 3, min_blatt: int = 200,
                     n_folds: int = 5, seed: int = an.SEED) -> pd.DataFrame:
    """Kreuzvalidierung nach Stationen, Guete und erste Trennung je Fold.

    Berichtet werden je Fold das Bestimmtheitsmass auf den
    herausgehaltenen Stationen und die Variable der Wurzel. Wechselt die
    Wurzelvariable von Fold zu Fold, ist der Baum als Erklaerung nicht
    belastbar, egal wie die Gueteszahlen aussehen.
    """
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import r2_score

    zeilen = []
    kf = GroupKFold(n_splits=int(n_folds))
    for i, (tr, te) in enumerate(kf.split(X, y, groups=gruppen), start=1):
        baum = fitte_baum(X.iloc[tr], y.iloc[tr], tiefe, min_blatt, seed)
        vorher = baum.predict(X.iloc[te])
        wurzel = X.columns[baum.tree_.feature[0]] if baum.tree_.feature[0] >= 0 else ""
        wichtig = pd.Series(baum.feature_importances_, index=X.columns)
        zeilen.append({
            "fold": i,
            "n_train": int(len(tr)), "n_test": int(len(te)),
            "r2_test": float(r2_score(y.iloc[te], vorher)),
            "wurzel": wurzel,
            "schwelle": float(baum.tree_.threshold[0]),
            "wichtigste": wichtig.idxmax(),
            "anteil_wichtigste": float(wichtig.max()),
        })
    return pd.DataFrame(zeilen)


def baumtext(baum, merkmale: Sequence[str], stellen: int = 1) -> str:
    """Den Baum als lesbaren Text, ohne sklearn-Jargon."""
    from sklearn.tree import export_text
    text = export_text(baum, feature_names=list(merkmale), decimals=stellen)
    return text.replace("|---", "+--").replace("value:", "Ruecklaufresiduum:")
