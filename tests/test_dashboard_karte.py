"""Aufbereitung der Modellergebnisse für die Netzkarte (src/dashboard_karte.py), ohne Rohdaten."""

import json

import numpy as np
import pandas as pd
import pytest

from src import dashboard_karte as dk


def tage(zaehler, von, bis, spalte="datum"):
    return pd.DataFrame({"zaehler": zaehler, spalte: pd.date_range(von, bis, freq="D")})


def test_hauptkanal_tagesmonitor_vor_lstm():
    tm = tage(1, "2024-01-01", "2024-01-03")
    lstm = pd.concat([tage(1, "2024-01-02", "2024-01-05", "tag"), tage(2, "2024-01-01", "2024-01-02", "tag")])
    k = dk.hauptkanal(tm, lstm).set_index(["zaehler", "datum"])["quelle"]
    assert k[(1, pd.Timestamp("2024-01-02"))] == "Tagesmonitor"
    assert k[(1, pd.Timestamp("2024-01-05"))] == "Prognose-LSTM", "warmer Tag: nur das LSTM rechnet"
    assert k[(2, pd.Timestamp("2024-01-01"))] == "Prognose-LSTM", "ohne Referenz zählt das LSTM"
    assert len(k) == 7


def test_meldung_nur_vom_hauptkanal_faerbt():
    kanal = dk.hauptkanal(tage(1, "2024-01-01", "2024-01-02"), tage(1, "2024-01-01", "2024-01-04", "tag"))
    alarme = pd.DataFrame({"quelle": ["Tagesmonitor", "Prognose-LSTM", "Prognose-LSTM"],
                           "zaehler": [1, 1, 1],
                           "datum": pd.to_datetime(["2024-01-02", "2024-01-02", "2024-01-04"]),
                           "kanal": ["kwh_pro_m3", "ruecklauf", "nachtdurchfluss"],
                           "richtung": [-1, 1, 1], "bewertung": ["schlechter"] * 3,
                           "netzereignis": [True, False, False]})
    m = dk.meldungen(alarme, kanal)
    assert list(m["haupt"]) == [True, False, True]
    j = dk.meldungen_je_zaehler(m, "2024-01-01", 10)["1"]
    assert j[0] == [1, 1, 0, 1, 1, "weniger Abkühlung"]
    assert j[1][4] == 0, "LSTM an einem Tag des Tagesmonitors bleibt Hinweis"
    assert j[2][:2] == [3, 1]


def test_meldungen_ausserhalb_des_zeitraums_fallen_weg():
    alarme = pd.DataFrame({"quelle": ["Tagesmonitor"] * 2, "zaehler": [5, 5],
                           "datum": pd.to_datetime(["2023-12-31", "2024-01-11"]), "kanal": ["log_volumen"] * 2,
                           "richtung": [1, -1], "bewertung": ["schlechter", "besser"], "netzereignis": [False] * 2})
    j = dk.meldungen_je_zaehler(dk.meldungen(alarme, None), "2024-01-01", 11)
    assert j == {"5": [[10, -1, 0, 0, 1, "weniger Wasser"]]}


def test_ueberwacht_als_zeichenkette():
    kanal = dk.hauptkanal(tage(7, "2024-01-02", "2024-01-03"), None)
    assert dk.ueberwacht(kanal, "2024-01-01", 5) == {"7": "01100"}


def test_ventil_stufe():
    assert [dk.ventil_stufe(p) for p in (0.95, 0.5, 0.49, np.nan, None)] == \
        ["Verdacht", "Verdacht", "kein Verdacht", "", ""]


def test_massnahmen_reihenfolge_und_haus():
    assert dk.massnahmen("Dämmung prüfen; Reparatur: Regelventil tauschen") == ["reparatur", "daemmung"]
    assert dk.massnahmen("keine") == [] and dk.massnahmen(np.nan) == []
    assert dk.massnahmen("Regelungsoptimierung") == [], "wird nicht empfohlen"
    a = {"dr": 1, "ma": ["daemmung"], "potenzial": "mittel"}
    b = {"dr": 2, "ma": ["kapazitaet"], "potenzial": "gering"}
    assert dk.haus([a, b]) == {"dr": 2, "ma": "kapazitaet", "po": 2}
    assert dk.haus([{"dr": 0, "ma": [], "potenzial": ""}]) == {"dr": 0, "ma": "keine", "po": 0}
    assert dk.haus([]) is None


def station(**werte):
    basis = {"zaehler": 68956351, "rang": 3, "dringlichkeit": "hoch",
             "handlung": "Reparatur: Regelventil tauschen; Dämmung prüfen", "begruendung": "Ventilverdacht",
             "klasse": "Regelventil tauschen", "p_ventil": 0.912, "sommer_durchlauf_anteil": 0.8,
             "hinweis_daemmung": True, "p_daemmung": 0.7, "hinweis_vertrag": np.nan, "auslastung": 0.9,
             "netz_rang": 2.0, "n_stationen": 84, "netz_winter": "24/25", "netz_fehlerbild": "ventil",
             "potenzial": "hoch", "luecke_text": "Spreizung 9,0 K unter dem besten Viertel",
             "symptom": "", "veraenderung": "keine Meldung", "vermutete_ursache": "", "befund": None,
             "sonderfall_grund": ""}
    basis.update(werte)
    return pd.Series(basis)


def test_eintrag_ist_json_faehig():
    e = dk.eintrag(station())
    json.dumps(e)
    assert e["z"] == "68956351" and e["dr"] == 3 and e["ma"] == ["reparatur", "daemmung"]
    assert e["ventil"] == "Verdacht" and e["p_ventil"] == 0.91
    assert e["kapazitaet"] is False, "fehlender Hinweis zählt als nein"
    assert e["befund"] == "nie begangen" and e["netz_rang"] == 2
    e = dk.eintrag(station(netz_rang=np.nan, n_stationen=np.nan, p_ventil=np.nan))
    assert e["netz_rang"] is None and e["netz_n"] is None and e["ventil"] == ""


def test_karten_daten_und_abgleich():
    st = pd.DataFrame([station(), station(zaehler=72135453, dringlichkeit="keine", handlung="keine")])
    daten = {"stationen": st, "meta": {"winter_name": "24/25", "grenzen": {"ventil": 0.95, "daemmung": None}},
             "alarme": pd.DataFrame(columns=["quelle", "zaehler", "datum", "kanal", "richtung", "bewertung",
                                             "netzereignis"]),
             "tm_tage": tage(68956351, "2024-01-01", "2024-01-02"), "lstm_tage": None, "effizienz": None}
    kd = dk.karten_daten(daten, "2024-01-01 00:00", "2024-01-31 23:00")
    json.dumps(kd)
    assert kd["n_tage"] == 31 and set(kd["stationen"]) == {"68956351", "72135453"}
    assert kd["meta"]["grenzen"]["ventil"] == 0.95 and kd["meta"]["grenzen"]["daemmung"] == 0.5
    assert kd["stationen"]["68956351"]["ventil"] == "kein Verdacht", "Grenze aus meta.json gilt"
    assert kd["ueberwacht"]["68956351"].startswith("11") and "potenzial_k" not in kd["meta"]
    assert dk.abgleich(["068956351", "1"], kd["stationen"]) == {
        "auf_karte_ohne_modell": ["1"], "modell_nicht_auf_karte": ["72135453"]}


def test_lade_meldet_fehlende_tabellen(tmp_path):
    with pytest.raises(FileNotFoundError, match="dashboard_daten"):
        dk.lade(tmp_path)


def test_eintrag_mit_stand_vor_den_begehungen():
    e = dk.eintrag(station())
    assert e["vor"] is None, "ohne Spalten _vor kein Stand davor"
    z = station(dringlichkeit_vor="mittel", handlung_vor="Reparatur: Regelventil tauschen", rang_vor=4,
                begruendung_vor="Ventilverdacht (Score 0,82)", p_ventil_vor_begehung=0.82,
                sommer_durchlauf_anteil_vor=0.9, hinweis_daemmung_vor=False, hinweis_vertrag_vor=np.nan,
                netz_fehlerbild_vor="", sonderfall_grund_vor="", auslastung_vor=0.8, p_daemmung_vor_begehung=0.3)
    e = dk.eintrag(z)
    json.dumps(e)
    assert e["vor"]["dr"] == 2 and e["vor"]["rang"] == 4 and e["vor"]["ma"] == ["reparatur"]
    assert e["vor"]["ventil"] == "Verdacht" and e["vor"]["kapazitaet"] is False
    assert dk.haus([e["vor"]]) == {"dr": 2, "ma": "reparatur", "po": 0}
