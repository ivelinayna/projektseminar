"""Daten für das Wächter-Dashboard: Modellpakete auf die aktuellen Daten anwenden.

Das Dashboard (`src/dashboard_waechter.py`) rechnet selbst nichts. Es liest
nur die Tabellen, die dieses Modul nach ``outputs/dashboard/`` schreibt.
So bleibt die App schnell, braucht kein torch und zeigt immer genau das,
was mit einer bestimmten Paketversion gerechnet wurde.

Ablauf (`python -m src.dashboard_daten`)
----------------------------------------
1. Stundenreihen aus Notebook 00 und DWD-Temperatur laden.
2. **Wächter** anwenden, beide aus ihren Paketen, ohne neu zu lernen:
   Tagesmonitor (Paket ``normalmodell``) und Prognose-LSTM (Paket
   ``prognose_lstm``).
3. **Folie 5** für die letzte Heizperiode mit genug Daten und zum Vergleich
   für die Zeit vor den Begehungen (Paket ``fehlerklassen``).
4. **Netzvergleich und Potenzial** aus dem Kennlinien-Strang
   (`stationsblatt.rechne`): Rang im Netz, Fehlerbild, Abstand zum besten
   Viertel.
5. **Empfehlung** je Station (`empfehlungen`), **Netzeffizienz** je Monat
   (`netzeffizienz`) und das **Optimierungspotenzial** (`potenzial_netz`).

Alles nur mit Zählernummern, keine Adressen.
"""

from __future__ import annotations

import argparse
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import modellpaket as mp

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
AUSGABE = ROOT / "outputs" / "dashboard"
PRUEFSTAND = ROOT / "outputs" / "pruefstand"

TAGE_AKTUELL = 30
#ab so vielen Stationen mit Verschlechterung in 14 Tagen eher Wetter oder Netz (src/aktualisieren.py)
NETZEREIGNIS_STATIONEN = 11
NETZEREIGNIS_TAGE = 14
MIN_WINTERSTUNDEN = 1000
#ab so vielen Kennzahlen außerhalb des Lernbereichs rechnet das Modell über seine Erfahrung hinaus
SONDERFALL_KENNZAHLEN = 2
#eine Station mit mehr als diesem Anteil am Wintervolumen des Netzes ist keine typische Hausstation
SONDERFALL_VOLUMENANTEIL = 0.10
#Monat in der Netzeffizienz nur vergleichbar, wenn mindestens dieser Anteil der Stationen Daten hat
MIN_ANTEIL_STATIONEN = 0.6
MIN_STATIONEN_SAISON = 30
DRINGLICHKEIT = ("hoch", "mittel", "niedrig", "keine")
HANDLUNGEN = ("Reparatur: Regelventil tauschen", "Regelungsoptimierung",
              "Kapazitätsanpassung prüfen", "Dämmung prüfen", "Daten prüfen")


# --- Saison ------------------------------------------------------------------

def letzte_saison(stunden: pd.DataFrame, min_stunden: int = MIN_WINTERSTUNDEN,
                  min_stationen: int = MIN_STATIONEN_SAISON
                  ) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """Jüngste Heizperiode (Oktober bis März), in der genug Stationen Daten haben.

    Rückgabe: (Winter, Sommer danach) als Paare von Datumstexten. Der Sommer
    ist Juni bis August des Jahres, in dem der Winter endet; er darf
    unvollständig sein (dann zählen die Tage, die es gibt).
    """
    s = stunden.dropna(subset=["durchfluss"])
    for jahr in range(int(s["timestamp"].dt.year.max()), 2020, -1):
        von, bis = pd.Timestamp(f"{jahr - 1}-10-01"), pd.Timestamp(f"{jahr}-04-01")
        n = s[(s["timestamp"] >= von) & (s["timestamp"] < bis)].groupby("zaehler").size()
        if int((n >= min_stunden).sum()) >= min_stationen:
            return ((str(von.date()), str(bis.date())),
                    (f"{jahr}-06-01", f"{jahr}-09-01"))
    raise ValueError("keine Heizperiode mit genug Daten")


def winter_name(winter: Tuple[str, str]) -> str:
    a, b = pd.Timestamp(winter[0]).year, pd.Timestamp(winter[1]).year
    return f"{a % 100:02d}/{b % 100:02d}"


# --- Netzeffizienz und Potenzial ----------------------------------------------

def netzeffizienz(stunden: pd.DataFrame, tage: pd.DataFrame) -> pd.DataFrame:
    """Kennzahlen des ganzen Teilnetzes je Monat.

    - ``ruecklauf_c``: volumengewichteter Rücklauf aller Stationen (Stunden)
    - ``spreizung_k``: volumengewichtete Spreizung
    - ``kwh_pro_m3``: Energie / Volumen aus den Zählerständen (Tageswerte
      des Tagesmonitors), die Kennzahl der ÜZ-Folie zur Gesamteffizienz
    - ``aussen_c``: mittlere Außentemperatur, ``stationen``: mit Daten
    """
    s = stunden.dropna(subset=["ruecklauf", "durchfluss"])
    s = s[s["durchfluss"] > 0].assign(monat=lambda d: d["timestamp"].dt.to_period("M"))
    g = s.assign(rl_v=s["ruecklauf"] * s["durchfluss"],
                 dt_v=(s["vorlauf"] - s["ruecklauf"]) * s["durchfluss"]).groupby("monat")
    aus = pd.DataFrame({"ruecklauf_c": g["rl_v"].sum() / g["durchfluss"].sum(),
                        "spreizung_k": g["dt_v"].sum() / g["durchfluss"].sum(),
                        "aussen_c": g["aussen"].mean(),
                        "stationen": g["zaehler"].nunique()})
    if len(tage):
        t = tage[tage["nutzbar"]].assign(monat=lambda d: pd.to_datetime(d["datum"]).dt.to_period("M"))
        e = t.groupby("monat")[["energie_kwh", "volumen_m3"]].sum()
        aus["kwh_pro_m3"] = (e["energie_kwh"] / e["volumen_m3"]).reindex(aus.index)
        aus["energie_mwh"] = (e["energie_kwh"] / 1000).reindex(aus.index)
    aus["vergleichbar"] = aus["stationen"] >= MIN_ANTEIL_STATIONEN * aus["stationen"].max()
    aus.index = aus.index.to_timestamp()
    aus.index.name = "monat"
    return aus.reset_index()


def potenzial_netz(kz: pd.DataFrame, klassen: pd.DataFrame,
                   stunden: pd.DataFrame, winter: Tuple[str, str],
                   sonderfall: Optional[pd.Series] = None) -> Tuple[pd.DataFrame, dict]:
    """Grobe Abschätzung: Wie weit sänke der Netz-Rücklauf, wenn …?

    Ziel je Station ist der Median des lastgewichteten Rücklaufs der
    Optimum-Gruppe (K-Means). Für jede Station mit Handlung ist der
    Überschuss ``max(0, Rücklauf − Ziel)``; gewichtet mit ihrem Anteil am
    Wintervolumen ergibt das den Beitrag zum volumengewichteten
    Netz-Rücklauf. Der Durchfluss bleibt dabei gleich, in Wirklichkeit sinkt
    er mit, die Zahl ist also eine Größenordnung, keine Prognose.

    ``sonderfall`` markiert Stationen, deren Werte weit außerhalb dessen
    liegen, woraus gelernt wurde (z. B. Großverbraucher ohne Anschlusswert).
    Sie können das Netzvolumen dominieren; die Summe wird deshalb mit und
    ohne sie ausgewiesen.
    """
    w = stunden[(stunden["timestamp"] >= winter[0]) & (stunden["timestamp"] < winter[1])]
    volumen = w.groupby("zaehler")["durchfluss"].sum()
    rl = kz["ruecklauf_lastgewichtet"]
    ziel = float(rl[klassen["kmeans"] == "Optimum"].median())
    tab = pd.DataFrame({"ruecklauf_lastgewichtet": rl, "volumen_anteil": volumen / volumen.sum(),
                        "klasse": klassen["klasse"]}).dropna(subset=["ruecklauf_lastgewichtet"])
    tab["sonderfall"] = (sonderfall.reindex(tab.index).fillna(False).astype(bool)
                         if sonderfall is not None else False)
    tab["ueberschuss_k"] = (tab["ruecklauf_lastgewichtet"] - ziel).clip(lower=0)
    tab["beitrag_k"] = tab["ueberschuss_k"] * tab["volumen_anteil"].fillna(0)
    mit = tab["klasse"].isin(["Regelventil tauschen", "Regelparameter optimieren"])
    ohne = tab[~tab["sonderfall"]]
    v_ohne = ohne["volumen_anteil"].sum()
    beitrag_ohne = ohne["ueberschuss_k"] * ohne["volumen_anteil"].fillna(0) / v_ohne if v_ohne else ohne["beitrag_k"] * np.nan
    mit_ohne = ohne["klasse"].isin(["Regelventil tauschen", "Regelparameter optimieren"])
    gesamt = {"ziel_ruecklauf_c": ziel,
              "netz_minus_k_mit_handlung": float(tab.loc[mit, "beitrag_k"].sum()),
              "netz_minus_k_ohne_sonderfaelle": float(beitrag_ohne[mit_ohne].sum()),
              "netz_minus_k_reparatur_ohne_sonderfaelle": float(beitrag_ohne[ohne["klasse"] == "Regelventil tauschen"].sum()),
              "netz_minus_k_regelung_ohne_sonderfaelle": float(beitrag_ohne[ohne["klasse"] == "Regelparameter optimieren"].sum()),
              "volumenanteil_sonderfaelle": float(tab.loc[tab["sonderfall"], "volumen_anteil"].sum()),
              "sonderfaelle": [int(m) for m in tab.index[tab["sonderfall"]]],
              "stationen_mit_handlung": int(mit.sum())}
    return tab, gesamt


# --- Empfehlung ---------------------------------------------------------------

def _ja(wert) -> bool:
    """Wahr nur bei echtem True, fehlende Werte zählen als nein."""
    return wert is not None and not (isinstance(wert, float) and np.isnan(wert)) and bool(wert)


def _handlung(z: pd.Series) -> list:
    #Regelungsoptimierung (K-Means „schlechter“) wird nicht empfohlen: In Notebook 34 landen 24 bzw. 25
    #von 31 Stationen, an denen Durchfluss oder Sollwert eingestellt wurden, bei „kein Handlungsbedarf“
    #Sonderfall: Werte außerhalb dessen, woraus gelernt wurde, oder keine typische Hausstation. Dort ist
    #kein Score geprüft, also zuerst nur die Daten prüfen
    if _ja(z.get("sonderfall")):
        return [HANDLUNGEN[4]]
    h = []
    if z.get("klasse") == "Regelventil tauschen":
        h.append(HANDLUNGEN[0])
    if _ja(z.get("hinweis_vertrag")):
        h.append(HANDLUNGEN[2])
    if _ja(z.get("hinweis_daemmung")):
        h.append(HANDLUNGEN[3])
    if z.get("klasse") == "nicht einstufbar" or _ja(z.get("sonderfall")):
        h.append(HANDLUNGEN[4])
    return h


def empfehlungen(st: pd.DataFrame) -> pd.DataFrame:
    """Handlung, Dringlichkeit und Begründung je Station, nur aus geprüften Teilen (Notebook 34).

    Erwartet je Zähler: ``klasse``, ``p_ventil``, ``hinweis_vertrag``,
    ``hinweis_daemmung``, ``netz_fehlerbild``, ``auslastung``, ``sonderfall``;
    optional ``sommer_durchlauf_anteil`` für die Begründung.

    - hoch: Reparatur, bestätigt durch Ivelinas Fehlerbild „ventil“
      (Test C: 4 von 4 richtig)
    - mittel: Reparatur nur nach dem Ventil-Score des LSTM-Modells
      (LR nur auf dem LSTM-Embedding, Test C: 8 von 11 gefunden bei 4 Fehlalarmen)
    - niedrig: nur Kapazität, Dämmung (Hinweis) oder Daten prüfen

    Innerhalb der Stufe nach Ventil-Score (Test E: unter den ersten 10 nach
    Score hatten 7 einen Ventilbefund, Zufall etwa 2).

    Bewusst nicht dabei, weil die Prüfung es nicht trägt:

    - Regelungsoptimierung (K-Means): erkennt die Maßnahme nicht (Test C, Folie 5)
    - Sortieren nach Verschlechterung im Tagesmonitor: vor Begehungen mit Befund
      gab es nicht mehr davon als bei Kontrollen (alarme.ipynb)
    - Sortieren nach Potenzial: sagt nicht vorher, wo eine Begehung am meisten
      bringt (Test D, rho = 0,16)
    - „hoch“ allein ab Score 0,8: diese Grenze ist nirgends geprüft
    - Reparatur bei Sonderfällen: dort rechnet das Modell außerhalb dessen, woraus
      es gelernt hat; sie bekommen nur „Daten prüfen“
    """
    zeilen = []
    for meter, z in st.iterrows():
        h = _handlung(z)
        rep = HANDLUNGEN[0] in h
        netz_ventil = str(z.get("netz_fehlerbild", "")) == "ventil"
        p = z.get("p_ventil", np.nan)
        gruende = []
        if rep:
            #Score, nicht p: er ist eine Rangfolge, keine Wahrscheinlichkeit (Notebook 34)
            gruende.append(f"Ventilverdacht (Score {p:.2f})".replace(".", ","))
            anteil = z.get("sommer_durchlauf_anteil", np.nan)
            if pd.notna(anteil):
                #die einfache Regel aus Test C als Erklärung neben dem Score
                gruende.append(f"Durchfluss in {anteil:.0%} der Sommernächte")
            if netz_ventil:
                gruende.append("Netzvergleich bestätigt (Fehlerbild Ventil)")
        if HANDLUNGEN[2] in h:
            gruende.append(f"Spitzenlast nur {z.get('auslastung', np.nan):.0%} des Anschlusswerts")
        if HANDLUNGEN[3] in h:
            gruende.append("Dämmungsmodell über der Grenze (Hinweis)")
        if _ja(z.get("sonderfall")):
            gruende.append(f"Sonderfall ({z.get('sonderfall_grund', '')}), erst Messdaten prüfen; "
                           "die Scores sind dort nicht geprüft")
        if rep and netz_ventil:
            stufe = "hoch"
        elif rep:
            stufe = "mittel"
        elif h:
            stufe = "niedrig"
        else:
            stufe = "keine"
        zeilen.append({"zaehler": meter, "handlung": "; ".join(h) or "keine",
                       "dringlichkeit": stufe, "begruendung": "; ".join(gruende)})
    e = pd.DataFrame(zeilen).set_index("zaehler")
    e["rang"] = (e.join(st[["p_ventil"]])
                 .assign(_s=lambda d: d["dringlichkeit"].map({k: i for i, k in enumerate(DRINGLICHKEIT)}))
                 .sort_values(["_s", "p_ventil"], ascending=[True, False], na_position="last", kind="stable")
                 .assign(rang=lambda d: np.arange(1, len(d) + 1))["rang"])
    return e


#Stand vor den Begehungen: Winter 23/24 und Sommer 2024, nur Tage vor der ersten Begehung (Notebook 18).
#Im Dashboard gilt er, solange der Zeitregler vor diesem Tag steht (fehlerklassen.STICHTAG).
WECHSEL_VOR_BEGEHUNG = "2024-09-01"


def sonderfall_gruende(klassen: pd.DataFrame, stunden: pd.DataFrame,
                       winter: Tuple[str, str]) -> Tuple[pd.Series, pd.Series]:
    """Warum der Score an einem Zähler nicht trägt, und sein Anteil am Netzvolumen im Winter.

    Sonderfall: mindestens ``SONDERFALL_KENNZAHLEN`` Kennzahlen außerhalb des Lernbereichs
    oder mehr als ``SONDERFALL_VOLUMENANTEIL`` des Netzvolumens (keine typische Hausstation).
    """
    w = stunden[(stunden["timestamp"] >= winter[0]) & (stunden["timestamp"] < winter[1])]
    anteil = w.groupby("zaehler")["durchfluss"].sum()
    anteil = (anteil / anteil.sum()).reindex(klassen.index).fillna(0)
    grund = pd.Series("", index=klassen.index)
    ausserhalb = klassen["kennzahlen_ausserhalb"] >= SONDERFALL_KENNZAHLEN
    grund[ausserhalb] = klassen.loc[ausserhalb, "kennzahlen_ausserhalb"].map(
        lambda n: f"{int(n)} Kennzahlen außerhalb des Lernbereichs")
    gross = anteil > SONDERFALL_VOLUMENANTEIL
    grund[gross] = [(g + "; " if g else "") + f"{a:.0%} des Netzvolumens im Winter"
                    for g, a in zip(grund[gross], anteil[gross])]
    return grund, anteil


VOR_SPALTEN = {"handlung": "handlung_vor", "dringlichkeit": "dringlichkeit_vor",
               "begruendung": "begruendung_vor", "rang": "rang_vor",
               "p_daemmung": "p_daemmung_vor_begehung", "hinweis_daemmung": "hinweis_daemmung_vor",
               "hinweis_vertrag": "hinweis_vertrag_vor", "auslastung": "auslastung_vor",
               "netz_fehlerbild": "netz_fehlerbild_vor", "sommer_durchlauf_anteil": "sommer_durchlauf_anteil_vor",
               "sonderfall_grund": "sonderfall_grund_vor"}


def empfehlungen_vor_begehung(vorher: pd.DataFrame, kz_vor: pd.DataFrame, fehlerbild: pd.Series,
                              grund: pd.Series) -> pd.DataFrame:
    """Dieselbe Empfehlung wie `empfehlungen`, aber für den Stand vor den Begehungen.

    ``vorher`` kommt aus `fehlerklassen.bewerten` mit den Werten aus der Kreuzvalidierung für
    begangene Zähler (das Modell hat sie beim Lernen nicht gesehen), ``fehlerbild`` ist
    Ivelinas Fehlerbild im Winter 23/24, ``grund`` der Sonderfall-Grund in diesem Winter.
    Rückgabe mit den Spaltennamen aus ``VOR_SPALTEN``.
    """
    st = vorher[["klasse", "p_ventil", "p_daemmung", "auslastung", "hinweis_daemmung",
                 "hinweis_vertrag"]].copy()
    st["netz_fehlerbild"] = fehlerbild.reindex(st.index).fillna("")
    st["sommer_durchlauf_anteil"] = kz_vor["sommer_durchlauf_anteil"].reindex(st.index)
    st["sonderfall_grund"] = grund.reindex(st.index).fillna("")
    st["sonderfall"] = st["sonderfall_grund"] != ""
    aus = st.join(empfehlungen(st))
    return aus[list(VOR_SPALTEN)].rename(columns=VOR_SPALTEN)


#Maßnahmen aus den Begehungen (Notebook 18), so wie sie im Protokoll stehen
BEFUND_TEXT = {"ventil": "Ventil getauscht / Ventilbefund", "daemmung": "Leitungen gedämmt",
               "filter": "Filter gereinigt", "durchfluss": "Durchfluss neu eingestellt",
               "temperatur": "Rücklauf-Sollwert gesenkt", "ueberdimensioniert": "Vertrag verkleinert"}
SOMMERNACHT_AUFFAELLIG = 0.5
#ab diesem Anteil der Heiztage mit Konto am Deckel gilt die Referenz als veraltet (Notebook 34)
DECKEL_ANTEIL = 0.5


def wissensstand(st: pd.DataFrame, labels: Optional[pd.DataFrame] = None,
                 termine: Optional[dict] = None) -> pd.DataFrame:
    """Fünf getrennte Aussagen je Station (Notebook 34, Abschnitt 13).

    - ``symptom``: was die Messwerte jetzt zeigen (Netzvergleich, Sommernächte)
    - ``veraenderung``: was die Wächter gemeldet haben, oder warum sie nicht bewerten
    - ``vermutete_ursache``: Vermutung der Modelle, keine Diagnose
    - ``befund``: was bei einer Begehung dokumentiert wurde
    - ``empfohlene_pruefung``: was als Nächstes geprüft werden soll

    „Keine Meldung“ heißt nie „Station in Ordnung“, und ein Score ist keine
    Fehlerwahrscheinlichkeit.
    """
    zeilen = []
    for meter, z in st.iterrows():
        symptom = []
        if _ja(z.get("netz_auffaellig")):
            fb = str(z.get("netz_fehlerbild") or "")
            symptom.append("im Netzvergleich auffällig" + (f" (Fehlerbild {fb})" if fb else ""))
        anteil = z.get("sommer_durchlauf_anteil", np.nan)
        if pd.notna(anteil) and anteil >= SOMMERNACHT_AUFFAELLIG:
            symptom.append(f"läuft in {100 * anteil:.0f} % der Sommernächte durch")
        veraenderung = []
        tm_status = str(z.get("tm_status", ""))
        if tm_status not in ("überwacht", ""):
            veraenderung.append(f"Tagesmonitor nicht bewertbar ({tm_status})")
        else:
            if int(z.get("tm_verschlechterung", 0) or 0) > 0:
                veraenderung.append(f"Tagesmonitor: {int(z['tm_verschlechterung'])} Verschlechterung(en) in der letzten Heizperiode")
            deckel = z.get("tm_deckel_anteil", np.nan)
            if pd.notna(deckel) and deckel >= DECKEL_ANTEIL:
                #Notebook 34, Fall 1 und 2: ein Konto am Deckel kann nicht neu alarmieren
                veraenderung.append(f"Tagesmonitor: dauerhaft anders als die Referenz ({100 * deckel:.0f} % der Heiztage "
                                    "am Deckel), meldet nichts Neues; Referenz neu lernen")
        lstm_status = str(z.get("lstm_status", ""))
        if lstm_status not in ("überwacht", ""):
            veraenderung.append(f"Prognose-LSTM nicht bewertbar ({lstm_status})")
        elif int(z.get("lstm_alarme_aktuell", 0) or 0) > 0:
            veraenderung.append("Prognose-LSTM: Sprung in den letzten 30 Tagen")
        if not veraenderung:
            veraenderung.append("keine Meldung (heißt nicht: in Ordnung)")
        ursache = []
        klasse = z.get("klasse")
        if klasse == "Regelventil tauschen":
            ursache.append(f"Ventil schließt vermutlich nicht (Modell LSTM, Score {z.get('p_ventil', np.nan):.2f})"
                           .replace(".", ","))
        if _ja(z.get("hinweis_daemmung")):
            ursache.append("Hinweis Dämmung (Forschungsstand)")
        if _ja(z.get("hinweis_vertrag")):
            ursache.append("Anschluss vermutlich zu groß")
        befund = "nie begangen"
        if labels is not None and meter in labels.index:
            l = labels.loc[meter]
            gemacht = [t for k, t in BEFUND_TEXT.items() if _ja(l.get(k))]
            daten = sorted(pd.Timestamp(d) for d in (termine or {}).get(int(meter), []))
            wann = f"Begehung {daten[-1]:%d.%m.%Y}: " if daten else "Begehung: "
            befund = wann + (", ".join(gemacht) if gemacht else "kein Fehler eingetragen")
        zeilen.append({"zaehler": meter, "symptom": "; ".join(symptom) or "keine auffällige Kennzahl",
                       "veraenderung": "; ".join(veraenderung),
                       "vermutete_ursache": "; ".join(ursache) or "keine Vermutung",
                       "befund": befund, "empfohlene_pruefung": z.get("handlung", "keine") or "keine"})
    return pd.DataFrame(zeilen).set_index("zaehler")


NETZ_STATUS = ("Verschlechterung", "Verbesserung", "überwacht, kein Alarm", "keine Daten")
NETZ_FENSTER_TAGE = 14


def netzplan() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Logischer Netzplan aus Nodes_Edges.ods als Knoten mit Lage und Kanten, ohne Adressen.

    Die größte zusammenhängende Komponente wird nach Kamada-Kawai gelegt
    (Abstände folgen den Leitungswegen), kleine Teilnetze stehen darunter.
    Es ist ein Schaltplan der Verbindungen, keine Karte.
    """
    import networkx as nx
    from . import build_graph as bg
    from . import nachbarschaft as nb
    g = bg.build_logical_graph()
    teile = sorted(nx.connected_components(g), key=len, reverse=True)
    pos = {k: tuple(v) for k, v in nx.kamada_kawai_layout(g.subgraph(teile[0])).items()}
    x = -1.0
    for teil in teile[1:]:
        lage = nx.spring_layout(g.subgraph(teil), seed=0, scale=0.08)
        for k, v in lage.items():
            pos[k] = (x + v[0], -1.25 + v[1])
        x += 0.3
    zu_meter = {n: m for m, n in nb.meter_knoten(g).items()}
    nr = {n: i for i, n in enumerate(g.nodes)}
    knoten = pd.DataFrame([{"knoten": nr[n], "zaehler": zu_meter.get(n), "x": pos[n][0], "y": pos[n][1],
                            "art": "Hausstation" if d.get("kind") == "HAST" else "Abzweig"}
                           for n, d in g.nodes(data=True)])
    knoten["zaehler"] = knoten["zaehler"].astype("Int64")
    kanten = pd.DataFrame([{"x0": pos[a][0], "y0": pos[a][1], "x1": pos[b][0], "y1": pos[b][1]}
                           for a, b in g.edges])
    return knoten, kanten


def netz_wochenstatus(alarme: pd.DataFrame, beobachtet: pd.DataFrame, wochen: Sequence,
                      fenster: int = NETZ_FENSTER_TAGE) -> pd.DataFrame:
    """Status je Station und Woche für den Zeitstrahl im Netzgraphen.

    Gezählt werden die ``fenster`` Tage bis zum Ende der Woche: Verschlechterung,
    wenn ein Wächter in dieser Zeit „schlechter“ meldete, sonst Verbesserung bei
    „besser“, sonst „überwacht, kein Alarm“, wenn ein Wächter rechnete, sonst
    „keine Daten“. Kein Alarm heißt nicht: Station in Ordnung.
    """
    a = alarme.assign(datum=pd.to_datetime(alarme["datum"]))
    b = beobachtet.assign(datum=pd.to_datetime(beobachtet["datum"]))
    stationen = sorted(set(b["zaehler"].astype(int)) | set(a["zaehler"].astype(int)))
    zeilen = []
    for woche in pd.to_datetime(list(wochen)):
        bis = woche + pd.Timedelta(days=7)
        von = bis - pd.Timedelta(days=fenster)
        aw = a[(a["datum"] >= von) & (a["datum"] < bis)]
        bw = set(b.loc[(b["datum"] >= von) & (b["datum"] < bis), "zaehler"].astype(int))
        for z in stationen:
            eigen = aw[aw["zaehler"] == z]
            schlecht = eigen[eigen["bewertung"] == "schlechter"]
            if len(schlecht):
                status, text = NETZ_STATUS[0], ", ".join(sorted(set(schlecht["quelle"])))
            elif len(eigen):
                status, text = NETZ_STATUS[1], ", ".join(sorted(set(eigen["quelle"])))
            elif z in bw:
                status, text = NETZ_STATUS[2], ""
            else:
                status, text = NETZ_STATUS[3], ""
            zeilen.append({"woche": woche, "zaehler": z, "status": status, "quelle": text})
    return pd.DataFrame(zeilen)


def netzereignisse(alarme: pd.DataFrame, n: int = NETZEREIGNIS_STATIONEN,
                   tage: int = NETZEREIGNIS_TAGE) -> pd.Series:
    """Je Alarm: Verschlechtern sich in ±``tage``/2 Tagen ≥ ``n`` Stationen?"""
    if len(alarme) == 0:
        return pd.Series(dtype=bool)
    s = alarme[alarme["bewertung"] == "schlechter"]
    d = pd.to_datetime(alarme["datum"]).to_numpy()
    ds, zs = pd.to_datetime(s["datum"]).to_numpy(), s["zaehler"].to_numpy()
    halb = np.timedelta64(tage // 2, "D")
    aus = []
    for datum in d:
        im_fenster = (ds >= datum - halb) & (ds <= datum + halb)
        aus.append(len(set(zs[im_fenster])) >= n)
    return pd.Series(aus, index=alarme.index)


# --- Gesamtlauf ---------------------------------------------------------------

def rechne(ausgabe: Path = AUSGABE, stunden: Optional[pd.DataFrame] = None,
           log=print) -> dict:
    """Alles rechnen und nach ``ausgabe`` schreiben; Rückgabe: Metadaten."""
    from . import alarmbewertung as ab
    from . import fehlerklassen as fk
    from . import normalmodell_waechter as nw
    from . import prognose_waechter as pw
    from . import stationsblatt as sbl

    warnings.filterwarnings("ignore")
    ausgabe = Path(ausgabe)
    ausgabe.mkdir(parents=True, exist_ok=True)
    log("1/5 Daten laden ...")
    if stunden is None:
        stunden = pw.stundenwerte()
    e = nw.eingaben()
    datenende = pd.Timestamp(stunden["timestamp"].max())

    log("2/5 Wächter anwenden (Tagesmonitor, Prognose-LSTM) ...")
    normal_paket = nw.lade()
    normal = nw.anwenden(normal_paket, e["serien"], e["temp"])
    tm_verlauf = normal["verlauf"].rename(columns={"meter": "zaehler"})
    tm_alarme = ab.bewerte_richtung(normal["alarme"]).rename(columns={"meter": "zaehler"})
    tm_alarme["quelle"] = "Tagesmonitor"
    lstm_paket = pw.lade()
    lstm = pw.anwenden(lstm_paket, stunden)
    lstm_ue = lstm[lstm["status"] == "überwacht"]
    la = lstm_ue[lstm_ue["alarm"]].copy()
    kanal = np.where(la["z_rl"].abs() >= la["z_fluss"].abs(), "ruecklauf", "nachtdurchfluss")
    richtung = np.where(kanal == "ruecklauf", np.sign(la["z_rl"]), np.sign(la["z_fluss"])).astype(int)
    lstm_alarme = pd.DataFrame({"zaehler": la["zaehler"].to_numpy(), "datum": la["tag"].to_numpy(),
                                "kanal": kanal, "richtung": richtung})
    #höherer Rücklauf oder mehr Nachtdurchfluss ist schlechter
    lstm_alarme["bewertung"] = np.where(lstm_alarme["richtung"] > 0, "schlechter", "besser")
    lstm_alarme["quelle"] = "Prognose-LSTM"
    alarme = pd.concat([tm_alarme[["quelle", "zaehler", "datum", "kanal", "richtung", "bewertung"]],
                        lstm_alarme], ignore_index=True)
    alarme["datum"] = pd.to_datetime(alarme["datum"])
    alarme["netzereignis"] = False
    tm_teil = alarme["quelle"] == "Tagesmonitor"
    alarme.loc[tm_teil, "netzereignis"] = netzereignisse(alarme[tm_teil]).to_numpy()

    log("3/5 Folie 5: letzte Heizperiode und Stand vor den Begehungen ...")
    fk_paket = fk.lade()
    winter, sommer = letzte_saison(stunden)
    aktuell = fk.saison_bewerten(fk_paket, stunden, winter, sommer)
    kz_akt = fk.kennzahlen(stunden, winter, sommer, anschluss=fk.lade_anschlusswerte())
    vorher = None
    if (PROCESSED / "modell_labels.csv").exists():
        #Stand vor den Begehungen mit dem Encoder aus dem Paket (Embeddings anderer Encoder passen nicht)
        lab = pd.read_csv(PROCESSED / "modell_labels.csv", index_col="zaehler", parse_dates=["erste_begehung"])
        grenze = fk.grenze_vor_begehung(lab, stunden["zaehler"].unique())
        kz_vor = fk.kennzahlen(stunden, fk.WINTER, fk.SOMMER, grenze=grenze,
                               anschluss=fk.lade_anschlusswerte(), vertrag=lab["vertrag_alt_kw"])
        emb_vor = fk.embeddings(fk_paket["netz"], fk_paket["skalierung"], stunden,
                                {"w2324": fk.WINTER, "s2024": fk.SOMMER}, grenze=grenze,
                                min_tage=fk_paket["parameter"].get("emb_min_tage", fk.EMB_MIN_TAGE))
        vorher = fk.bewerten(fk_paket, kz_vor, emb_vor, oof=fk_paket["kreuzvalidierung"])

    log("4/5 Netzvergleich und Potenzial (Kennlinien-Strang) ...")
    sb_e = sbl.eingaben()
    netz = sbl.rechne(sb_e["serien"], sb_e["termine"], sb_e["anschlusswerte"], sb_e["bhkw"],
                      sb_e["ohne_datum"], baujahr=sb_e["baujahr"])
    status = sbl.statustabelle(netz).set_index("meter")
    #Sonderfall: Werte außerhalb des Lernbereichs (NB 22, Abschnitt 8) oder ein
    #Volumen, das für eine Hausstation nicht passt (NB 22: 81050517, 81062289)
    grund, _ = sonderfall_gruende(aktuell, stunden, winter)
    sonderfall = grund != ""
    #derselbe Stand vor den Begehungen, mit Ivelinas Fehlerbild aus Winter 23/24
    vor_tab = None
    if vorher is not None:
        fb = ab.fehlerbild_je_winter(netz["markiert"], list(netz["kennzahlen"]))
        fb = fb[fb["winter"] == winter_name(fk.WINTER)]
        fb = fb.assign(meter=fb["meter"].astype(int)).set_index("meter")["fehlerbild"]
        grund_vor, _ = sonderfall_gruende(vorher, stunden, fk.WINTER)
        vor_tab = empfehlungen_vor_begehung(vorher, kz_vor, fb, grund_vor)
    pot_tab, pot = potenzial_netz(kz_akt, aktuell, stunden, winter, sonderfall)

    log("5/5 Empfehlungen, Netzeffizienz, Tabellen schreiben ...")
    #Tagesmonitor: Verschlechterung in der letzten Heizperiode (wie alarmbewertung.prioritaet_je_winter);
    #LSTM: Alarme in den letzten 30 Tagen jeder Station (die Exporte enden zu verschiedenen Zeiten)
    w0, w1 = pd.Timestamp(winter[0]), pd.Timestamp(winter[1])
    tm_winter = alarme[(alarme["quelle"] == "Tagesmonitor") & (alarme["bewertung"] == "schlechter")
                       & (alarme["datum"] >= w0) & (alarme["datum"] < w1)]
    ende_je = stunden.groupby("zaehler")["timestamp"].max().dt.normalize()
    la = alarme[alarme["quelle"] == "Prognose-LSTM"]
    lstm_neu = la[la["datum"] > la["zaehler"].map(ende_je) - pd.Timedelta(days=TAGE_AKTUELL)]
    st = pd.DataFrame(index=sorted(set(stunden["zaehler"].astype(int))))
    st.index.name = "zaehler"
    st = st.join(aktuell[["klasse", "p_ventil", "p_daemmung", "auslastung", "kmeans",
                          "hinweis_daemmung", "hinweis_vertrag", "kennzahlen_ausserhalb",
                          "stunden_winter", "stunden_sommer"]])
    if vorher is not None:
        st = st.join(vorher[["klasse", "p_ventil"]].rename(columns={"klasse": "klasse_vor_begehung",
                                                                     "p_ventil": "p_ventil_vor_begehung"}))
    st = st.join(kz_akt[["ruecklauf_lastgewichtet", "winter_spreizung_last_k", "sommer_durchlauf_anteil",
                         "sommer_nachtfluss_lph"]])
    st = st.join(pot_tab[["ueberschuss_k", "beitrag_k", "sonderfall"]])
    st["sonderfall"] = st["sonderfall"].fillna(False).astype(bool)
    st["sonderfall_grund"] = grund.reindex(st.index).fillna("")
    st = st.join(status[["anschlusswert_kw", "winter", "rang", "n_stationen", "score", "auffaellig",
                         "chronisch", "fehlerbild", "prioritaet", "potenzial", "potenzial_score",
                         "groesste_luecke", "letzte_begehung", "norm5_kwh_m3", "norm5_abstand_k"]]
                 .rename(columns={"winter": "netz_winter", "rang": "netz_rang", "score": "netz_score",
                                  "auffaellig": "netz_auffaellig", "fehlerbild": "netz_fehlerbild",
                                  "prioritaet": "prioritaet_kennlinien_strang"}))
    #größte Lücke zum besten Viertel in Worten (Notebook 27), z. B. "Spreizung 9,0 K unter dem besten Viertel"
    st["luecke_text"] = [sbl.luecke_text(k, status.at[m, f"bw_abstand_{k}"])
                         if isinstance(k, str) and k and m in status.index and f"bw_abstand_{k}" in status.columns
                         else "" for m, k in zip(st.index, st["groesste_luecke"])]
    st["tm_status"] = normal["status"].reindex(st.index).fillna("keine Tageswerte")
    lstm_status = lstm.groupby("zaehler")["status"].first()
    st["lstm_status"] = lstm_status.reindex(st.index).fillna("nicht vorhergesagt")
    st["tm_verschlechterung"] = tm_winter.groupby("zaehler").size().reindex(st.index).fillna(0).astype(int)
    #Anteil der Heiztage der letzten Heizperiode, an denen ein CUSUM-Konto am Deckel steht
    v = tm_verlauf[(tm_verlauf["datum"] >= w0) & (tm_verlauf["datum"] < w1)]
    am_deckel = v[["s_plus", "s_minus"]].max(axis=1) >= normal_paket["parameter"].get("cusum_max", 10.0) - 1e-9
    st["tm_deckel_anteil"] = (am_deckel.groupby([v["zaehler"], v["datum"]]).any()
                              .groupby(level=0).mean().reindex(st.index))
    st["lstm_alarme_aktuell"] = lstm_neu.groupby("zaehler").size().reindex(st.index).fillna(0).astype(int)
    st["letzter_alarm"] = alarme.groupby("zaehler")["datum"].max().reindex(st.index)
    st["datenende"] = stunden.groupby("zaehler")["timestamp"].max().reindex(st.index)
    st = st.join(empfehlungen(st))
    if vor_tab is not None:
        st = st.join(vor_tab)
    labels = (pd.read_csv(PROCESSED / "modell_labels.csv", index_col="zaehler")
              if (PROCESSED / "modell_labels.csv").exists() else None)
    st = st.join(wissensstand(st, labels, e["termine"]))
    st = st.sort_values("rang")

    eff = netzeffizienz(stunden, normal["tage"])
    termine = pd.DataFrame([(int(m), pd.Timestamp(d)) for m, ds in e["termine"].items() for d in ds],
                           columns=["zaehler", "datum"])
    tm_verlauf.to_parquet(ausgabe / "waechter_tagesmonitor.parquet", index=False)
    lstm_ue[["zaehler", "tag", "heiztag", "rl_gemessen", "rl_erwartet", "fluss_nacht_gemessen",
             "fluss_nacht_erwartet", "z_rl", "z_fluss", "warnung", "alarm", "alarm_cusum"]].to_parquet(
        ausgabe / "waechter_lstm.parquet", index=False)
    alarme.to_parquet(ausgabe / "alarme.parquet", index=False)
    st.reset_index().to_parquet(ausgabe / "stationen.parquet", index=False)
    eff.to_parquet(ausgabe / "netzeffizienz.parquet", index=False)
    termine.to_parquet(ausgabe / "begehungen.parquet", index=False)
    try:
        knoten, kanten = netzplan()
        beob = pd.concat([tm_verlauf[["zaehler", "datum"]],
                          lstm_ue[["zaehler", "tag"]].rename(columns={"tag": "datum"})], ignore_index=True)
        start = pd.Timestamp(tm_verlauf["datum"].min()) if len(tm_verlauf) else pd.Timestamp(winter[0])
        wochen = pd.date_range(start.normalize() - pd.Timedelta(days=start.weekday()), datenende, freq="7D")
        knoten.to_parquet(ausgabe / "netz_knoten.parquet", index=False)
        kanten.to_parquet(ausgabe / "netz_kanten.parquet", index=False)
        netz_wochenstatus(alarme, beob, wochen).to_parquet(ausgabe / "netz_status.parquet", index=False)
    except Exception as exc:          # ohne Nodes_Edges.ods läuft das Dashboard ohne Netzansicht
        log(f"Netzansicht übersprungen: {exc}")

    meta = {"erstellt": datetime.now().isoformat(timespec="seconds"),
            "datenende": str(datenende), "winter": list(winter), "sommer": list(sommer),
            "winter_name": winter_name(winter), "tage_aktuell": TAGE_AKTUELL,
            "pakete": {p.name: p.version for p in (normal_paket["paket"], lstm_paket["paket"],
                                                   fk_paket["paket"])},
            "lstm_schwelle": lstm_paket["parameter"].get("schwelle"),
            "lstm_alarmregel": lstm_paket["parameter"].get("alarmregel"),
            "grenzen": {"ventil": fk_paket["parameter"].get("ventil_grenze"),
                        "daemmung": fk_paket["parameter"].get("daemmung_grenze"),
                        "vertrag": fk_paket["parameter"].get("vertrag_grenze")},
            "potenzial": pot,
            "stationen": int(len(st)),
            "vorher": None if vor_tab is None else {
                "name": "vor den Begehungen", "winter_name": winter_name(fk.WINTER),
                "wechsel": WECHSEL_VOR_BEGEHUNG,
                "grundlage": "Winter 23/24 und Sommer 2024, nur Tage vor der ersten Begehung; "
                             "für begangene Zähler der Wert aus der Kreuzvalidierung",
                "dringlichkeit": st["dringlichkeit_vor"].value_counts().to_dict()},
            "dringlichkeit": st["dringlichkeit"].value_counts().to_dict(),
            "klassen": st["klasse"].value_counts().to_dict()}
    (ausgabe / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str),
                                       encoding="utf-8")
    log(f"fertig: {len(st)} Stationen, Dringlichkeit {meta['dringlichkeit']}, Tabellen in {ausgabe}")
    return meta


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=AUSGABE)
    args = p.parse_args(argv)
    try:
        rechne(args.out)
    except mp.PaketFehler as exc:
        raise SystemExit(f"{exc}\nPakete bauen: Notebook 34, Abschnitt 14") from exc


if __name__ == "__main__":
    main()
