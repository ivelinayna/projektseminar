"""Datenschicht des Wächter-Dashboards (src/dashboard_daten.py), ohne Rohdaten."""

import numpy as np
import pandas as pd
import pytest

from src import dashboard_daten as dd
from src import fehlerklassen as fk


def stationen(**spalten):
    basis = {"klasse": "kein Handlungsbedarf", "p_ventil": 0.1, "hinweis_vertrag": False,
             "hinweis_daemmung": False, "netz_fehlerbild": "", "tm_verschlechterung": 0,
             "lstm_alarme_aktuell": 0, "potenzial_score": 1.0, "auslastung": 0.9, "sonderfall": False,
             "sonderfall_grund": ""}
    n = max(len(v) for v in spalten.values())
    tab = pd.DataFrame({k: spalten.get(k, [v] * n) for k, v in basis.items()}, index=range(1, n + 1))
    return tab


def test_empfehlung_stufen():
    st = stationen(klasse=["Regelventil tauschen", "Regelventil tauschen", "Regelventil tauschen",
                           "Regelparameter optimieren", "kein Handlungsbedarf", "kein Handlungsbedarf",
                           "nicht einstufbar"],
                   p_ventil=[0.85, 0.6, 0.6, 0.2, 0.1, 0.1, np.nan],
                   netz_fehlerbild=["", "ventil", "", "", "", "", ""],
                   hinweis_vertrag=[False, False, False, False, True, np.nan, False],
                   tm_verschlechterung=[0, 0, 3, 0, 5, 0, 0])
    e = dd.empfehlungen(st)
    #hoch nur mit Ivelinas Fehlerbild, ein Score ab 0,8 allein reicht nicht
    assert list(e["dringlichkeit"]) == ["mittel", "hoch", "mittel", "keine", "niedrig", "keine", "niedrig"]
    #K-Means „schlechter“ wird nicht als Regelungsoptimierung empfohlen
    assert e.loc[4, "handlung"] == "keine"
    assert "Kapazitätsanpassung" in e.loc[5, "handlung"]
    assert e.loc[6, "handlung"] == "keine", "fehlender Hinweis zählt als nein"
    assert "Daten prüfen" in e.loc[7, "handlung"]
    assert "Netzvergleich bestätigt" in e.loc[2, "begruendung"]
    assert "Score 0,85" in e.loc[1, "begruendung"] and "Tagesmonitor" not in e.loc[3, "begruendung"]
    #Reihenfolge: Stufe, dann Ventil-Score; eine Verschlechterung im Tagesmonitor zieht nicht vor
    assert list(e.sort_values("rang").index) == [2, 1, 3, 5, 7, 4, 6]


def test_sonderfall_braucht_datenpruefung():
    st = stationen(klasse=["Regelventil tauschen"], p_ventil=[0.95], sonderfall=[True],
                   sonderfall_grund=["31% des Netzvolumens im Winter"])
    e = dd.empfehlungen(st)
    #außerhalb des Gelernten ist kein Score geprüft: nur Daten prüfen, keine Reparatur
    assert e.loc[1, "handlung"] == "Daten prüfen"
    assert e.loc[1, "dringlichkeit"] == "niedrig"
    assert "Sonderfall" in e.loc[1, "begruendung"]


def test_letzte_saison():
    zeilen = []
    for z in range(40):
        idx = pd.date_range("2023-10-01", "2025-07-10", freq="h")
        if z >= 35:
            idx = idx[idx < "2024-06-01"]
        zeilen.append(pd.DataFrame({"zaehler": z, "timestamp": idx, "durchfluss": 1.0}))
    s = pd.concat(zeilen)
    winter, sommer = dd.letzte_saison(s, min_stationen=30)
    assert winter == ("2024-10-01", "2025-04-01") and sommer[0] == "2025-06-01"
    assert dd.winter_name(winter) == "24/25"


def test_potenzial_mit_und_ohne_sonderfall():
    idx = pd.date_range("2024-10-01", periods=48, freq="h")
    s = pd.concat([pd.DataFrame({"zaehler": z, "timestamp": idx, "durchfluss": f})
                   for z, f in ((1, 100.0), (2, 100.0), (3, 800.0))])
    kz = pd.DataFrame({"ruecklauf_lastgewichtet": [40.0, 50.0, 60.0]}, index=[1, 2, 3])
    kl = pd.DataFrame({"kmeans": ["Optimum", "schlechter", "schlechter"],
                       "klasse": ["kein Handlungsbedarf", "Regelparameter optimieren", "Regelventil tauschen"]},
                      index=[1, 2, 3])
    tab, g = dd.potenzial_netz(kz, kl, s, ("2024-10-01", "2025-04-01"),
                               sonderfall=pd.Series([False, False, True], index=[1, 2, 3]))
    assert g["ziel_ruecklauf_c"] == pytest.approx(40.0)
    assert g["netz_minus_k_mit_handlung"] == pytest.approx(10 * 0.1 + 20 * 0.8)
    assert g["netz_minus_k_ohne_sonderfaelle"] == pytest.approx(10 * 0.5)
    assert g["sonderfaelle"] == [3]


def test_netzereignisse():
    a = pd.DataFrame({"zaehler": range(12), "datum": pd.Timestamp("2025-01-10"), "bewertung": "schlechter"})
    a.loc[11, "datum"] = pd.Timestamp("2025-03-01")
    ne = dd.netzereignisse(a, n=11, tage=14)
    assert ne.iloc[:11].all() and not ne.iloc[11]


def test_kmeans_einstufen():
    km = {"merkmale": fk.KMEANS_MERKMALE, "mittel": [0, 0, 0], "skala": [1, 1, 1],
          "zentren": [[0, 0, 40], [0, 0, 60]], "optimum": 0}
    kz = pd.DataFrame({"anteil_volumenstrom": [0, 0, np.nan], "streubreite_betriebspunkte": [0, 0, 0],
                       "ruecklauf_lastgewichtet": [42.0, 58.0, 50.0]}, index=[1, 2, 3])
    e = fk.kmeans_einstufen(km, kz)
    assert e.loc[1] == "Optimum" and e.loc[2] == "schlechter" and pd.isna(e.loc[3])


def test_wissensstand_trennt_die_aussagen():
    st = stationen(klasse=["Regelventil tauschen", "kein Handlungsbedarf", "kein Handlungsbedarf"],
                   p_ventil=[0.9, 0.1, 0.1])
    st["netz_auffaellig"] = [True, False, False]
    st["netz_fehlerbild"] = ["ventil", "", ""]
    st["sommer_durchlauf_anteil"] = [0.8, 0.1, np.nan]
    st["tm_status"] = ["überwacht", "überwacht", "zu wenige Referenztage"]
    st["lstm_status"] = ["überwacht", "überwacht", "nicht kalibriert"]
    st["handlung"] = ["Reparatur: Regelventil tauschen", "keine", "keine"]
    labels = pd.DataFrame({"ventil": [True], "daemmung": [False], "filter": [True], "durchfluss": [False],
                           "temperatur": [False], "ueberdimensioniert": [np.nan]}, index=[1])
    w = dd.wissensstand(st, labels, {1: [pd.Timestamp("2024-09-09")]})
    assert "Fehlerbild ventil" in w.loc[1, "symptom"] and "80 %" in w.loc[1, "symptom"]
    assert w.loc[1, "befund"] == "Begehung 09.09.2024: Ventil getauscht / Ventilbefund, Filter gereinigt"
    assert "Score 0,90" in w.loc[1, "vermutete_ursache"]
    assert w.loc[2, "veraenderung"].startswith("keine Meldung (heißt nicht: in Ordnung)")
    assert w.loc[2, "befund"] == "nie begangen"
    assert "nicht bewertbar" in w.loc[3, "veraenderung"]
    #Konto am Deckel: Referenz veraltet, der Wächter meldet nichts Neues
    st["tm_deckel_anteil"] = [0.1, 0.8, np.nan]
    w = dd.wissensstand(st, labels, {1: [pd.Timestamp("2024-09-09")]})
    assert "Referenz neu lernen" in w.loc[2, "veraenderung"] and "80 %" in w.loc[2, "veraenderung"]
    assert "Referenz" not in w.loc[1, "veraenderung"]


def test_netz_wochenstatus():
    alarme = pd.DataFrame({"zaehler": [1, 2], "datum": pd.to_datetime(["2025-01-08", "2025-01-09"]),
                           "bewertung": ["schlechter", "besser"], "quelle": ["Tagesmonitor", "Prognose-LSTM"]})
    beob = pd.DataFrame({"zaehler": [1, 2, 3], "datum": pd.to_datetime(["2025-01-07"] * 3)})
    s = dd.netz_wochenstatus(alarme, beob, [pd.Timestamp("2025-01-06"), pd.Timestamp("2025-02-03")])
    w1 = s[s["woche"] == "2025-01-06"].set_index("zaehler")
    assert w1.loc[1, "status"] == "Verschlechterung" and w1.loc[1, "quelle"] == "Tagesmonitor"
    assert w1.loc[2, "status"] == "Verbesserung"
    assert w1.loc[3, "status"] == "überwacht, kein Alarm"
    assert (s[s["woche"] == "2025-02-03"]["status"] == "keine Daten").all()


def test_sonderfall_gruende_kennzahlen_und_volumen():
    klassen = pd.DataFrame({"kennzahlen_ausserhalb": [0, 3, 0]}, index=[1, 2, 3])
    ts = pd.date_range("2023-12-01", periods=48, freq="h")
    stunden = pd.concat([pd.DataFrame({"zaehler": z, "timestamp": ts, "durchfluss": f})
                         for z, f in ((1, 10.0), (2, 10.0), (3, 200.0))])
    grund, anteil = dd.sonderfall_gruende(klassen, stunden, ("2023-10-01", "2024-04-01"))
    assert grund[1] == ""
    assert grund[2] == "3 Kennzahlen außerhalb des Lernbereichs"
    assert "des Netzvolumens im Winter" in grund[3] and anteil[3] > 0.9


def test_empfehlungen_vor_begehung_gleiche_logik():
    vorher = pd.DataFrame({"klasse": ["Regelventil tauschen", "Regelventil tauschen", "kein Handlungsbedarf"],
                           "p_ventil": [0.9, 0.7, 0.1], "p_daemmung": [0.2, 0.6, 0.1], "auslastung": [0.9, 0.9, 0.5],
                           "hinweis_daemmung": [False, True, False], "hinweis_vertrag": [False, False, True]},
                          index=[11, 12, 13])
    kz_vor = pd.DataFrame({"sommer_durchlauf_anteil": [1.0, 0.8, 0.0]}, index=[11, 12, 13])
    fb = pd.Series({11: "ventil", 12: ""})
    t = dd.empfehlungen_vor_begehung(vorher, kz_vor, fb, pd.Series("", index=[11, 12, 13]))
    assert set(dd.VOR_SPALTEN.values()) <= set(t.columns)
    assert t.loc[11, "dringlichkeit_vor"] == "hoch" and t.loc[12, "dringlichkeit_vor"] == "mittel"
    assert t.loc[13, "dringlichkeit_vor"] == "niedrig"
    assert list(t.sort_values("rang_vor").index) == [11, 12, 13]
    assert "Durchfluss in 100% der Sommernächte" in t.loc[11, "begruendung_vor"]
