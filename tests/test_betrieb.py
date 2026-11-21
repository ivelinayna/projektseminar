import json
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src import betrieb as bt


def _dashboard(tmp_path, n=30):
    """Kleine Ergebnistabelle wie outputs/dashboard/stationen.parquet."""
    ordner = tmp_path / "dashboard"
    ordner.mkdir()
    st = pd.DataFrame({
        "zaehler": np.arange(1000, 1000 + n),
        "rang": np.arange(1, n + 1),
        "dringlichkeit": ["hoch"] * 3 + ["mittel"] * 5 + ["niedrig"] * (n - 8),
        "handlung": ["Reparatur"] * 3 + ["keine"] * (n - 3),
        "klasse": "kein Handlungsbedarf",
        "p_ventil": np.linspace(0.95, 0.05, n),
        "hinweis_daemmung": [True, False] * (n // 2),
        "hinweis_vertrag": False,
        "letzte_begehung": [None] * (n - 4) + ["2024-11-25"] * 4,
        "tm_status": "überwacht",
        "lstm_status": "überwacht",
    })
    st.to_parquet(ordner / "stationen.parquet", index=False)
    (ordner / "meta.json").write_text(json.dumps({"datenende": "2026-07-20 11:00:00",
                                                  "pakete": {"normalmodell": "v1", "fehlerklassen": "v2"}}))
    return ordner


def _protokoll(pfad, zeilen):
    """Vorlage schreiben und Zeilen eintragen, wie es ein Monteur tun würde."""
    from openpyxl import load_workbook
    bt.vorlage_schreiben(pfad)
    wb = load_workbook(pfad)
    ws = wb["Protokoll"]
    for i, z in enumerate(zeilen, start=2):
        for j, wert in enumerate(z, start=1):
            ws.cell(i, j, wert)
    wb.save(pfad)


def test_liste_sichern_und_laden(tmp_path):
    dash = _dashboard(tmp_path)
    listen = tmp_path / "listen"
    pfad = bt.liste_sichern(dash, listen, jetzt=datetime(2026, 12, 1, 8, 30))
    assert pfad.name == "handlungsliste_2026-12-01_0830.csv"
    df = bt.letzte_liste(listen)
    assert len(df) == 30
    assert df["paket_normalmodell"].iloc[0] == "v1"
    assert df["datenende"].iloc[0] == "2026-07-20 11:00:00"
    #eine zweite Sicherung überschreibt nichts, die jüngste gilt
    bt.liste_sichern(dash, listen, jetzt=datetime(2026, 12, 8, 8, 30))
    assert len(bt.listen_laden(listen)) == 60
    assert bt.letzte_liste(listen)["stand"].iloc[0] == pd.Timestamp("2026-12-08 08:30")


def test_listenstand_vor_der_begehung(tmp_path):
    dash = _dashboard(tmp_path)
    listen = tmp_path / "listen"
    bt.liste_sichern(dash, listen, jetzt=datetime(2026, 12, 1, 8, 0))
    bt.liste_sichern(dash, listen, jetzt=datetime(2026, 12, 15, 8, 0))
    df = bt.listen_laden(listen)
    assert bt.listenstand_vor(df, 1000, pd.Timestamp("2026-11-30")) is None
    assert bt.listenstand_vor(df, 1000, pd.Timestamp("2026-12-01"))["stand"] == pd.Timestamp("2026-12-01 08:00")
    assert bt.listenstand_vor(df, 1000, pd.Timestamp("2026-12-20"))["stand"] == pd.Timestamp("2026-12-15 08:00")


def test_vorlage_hat_alle_spalten(tmp_path):
    from openpyxl import load_workbook
    pfad = bt.vorlage_schreiben(tmp_path / "vorlage.xlsx")
    wb = load_workbook(pfad)
    kopf = [c.value for c in wb["Protokoll"][1]]
    assert kopf == list(bt.PROTOKOLL_SPALTEN)
    assert wb["Auswahl"].sheet_state == "hidden"
    assert "Hinweise" in wb.sheetnames


def test_protokolle_einlesen_prueft_und_verknuepft(tmp_path):
    dash = _dashboard(tmp_path)
    listen = tmp_path / "listen"
    bt.liste_sichern(dash, listen, jetzt=datetime(2026, 12, 1, 8, 0))
    ordner = tmp_path / "protokolle"
    _protokoll(ordner / "protokoll_dez.xlsx", [
        [1000, datetime(2026, 12, 3), "ja", "Regelventil / Stellantrieb", None, "klemmt", "Bauteil getauscht",
         "Stellantrieb", None, None],
        [1001, datetime(2026, 12, 4), "nein", None, None, None, "keine", None, None, None],
        [1002, datetime(2026, 12, 4), "ja", None, None, "?", None, None, None, None],          #Fehlerart fehlt
        [None, datetime(2026, 12, 4), "ja", "Dämmung", None, None, None, None, None, None],    #Zähler fehlt
        [1003, datetime(2027, 6, 1), "nein", None, None, None, None, None, None, None],         #Zukunft
        [1004, datetime(2026, 12, 5), "unklar", None, None, None, None, None, None, None],
        [1000, datetime(2026, 12, 3), "nein", None, None, None, None, None, None, None],        #doppelt
        [1005, "05.12.2026", "ja", "Dämmung", "Exotisch", "Rohr blank", "Sonstiges", None, "2025", None],
    ])
    #die Vorlage selbst im Ordner wird nicht eingelesen
    bt.vorlage_schreiben(ordner / bt.VORLAGE_NAME)
    ziel = tmp_path / "rueckmeldungen.csv"
    df, hinweise = bt.protokolle_einlesen(ordner, listen, ziel, heute=pd.Timestamp("2026-12-10"))
    assert list(df["zaehler"]) == [1000, 1001, 1004, 1005]
    text = "\n".join(hinweise)
    assert "Zeile 4: 'Etwas kaputt?' ist ja, aber keine Fehlerart" in text
    assert "Zeile 5: Zählernummer fehlt" in text
    assert "Zeile 6: Datum 01.06.2027 liegt in der Zukunft" in text
    assert "Zeile 8: Begehung 1000 am 03.12.2026 doppelt" in text
    assert "unbekannte Fehlerart 'Exotisch'" in text

    z = df.set_index("zaehler")
    assert z.loc[1000, "befund_ventil"] is True or z.loc[1000, "befund_ventil"] == True  # noqa: E712
    assert z.loc[1001, "befund_ventil"] == False  # noqa: E712
    assert pd.isna(z.loc[1004, "befund_ventil"])
    assert z.loc[1005, "befund_daemmung"] == True  # noqa: E712
    assert z.loc[1005, "fehlerart_2"] == "sonstiges"
    #Listenstand vor der Begehung: Station 1000 stand auf Rang 1 mit Dringlichkeit hoch
    assert z.loc[1000, "liste_dringlichkeit"] == "hoch"
    assert z.loc[1000, "liste_rang"] == 1
    assert z.loc[1000, "liste_stand"] == "2026-12-01T08:00"
    #die Datei lässt sich wieder laden
    assert len(bt.rueckmeldungen_laden(ziel)) == 4


def test_leere_protokolle_ergeben_lesbare_datei(tmp_path):
    ziel = tmp_path / "rueckmeldungen.csv"
    df, _ = bt.protokolle_einlesen(tmp_path / "leer", tmp_path / "listen", ziel)
    assert df.empty
    assert bt.rueckmeldungen_laden(ziel).empty


def test_pruefung_planen_und_auswerten(tmp_path):
    dash = _dashboard(tmp_path)
    listen = tmp_path / "listen"
    bt.liste_sichern(dash, listen, jetzt=datetime(2026, 12, 1, 8, 0))
    ziel = tmp_path / "betrieb"
    rm = tmp_path / "rueckmeldungen.csv"
    ordner = bt.pruefung_planen(anzahl=5, seed=7, listen_ordner=listen, rueckmeldungen=rm, ziel=ziel,
                                jetzt=datetime(2026, 12, 2, 9, 0))
    plan = json.loads((ordner / "plan.json").read_text(encoding="utf-8"))
    schluessel = pd.read_csv(ordner / "schluessel.csv")
    liste = pd.read_csv(ordner / "begehungsliste.csv")
    assert plan["seed"] == 7 and plan["anzahl_je_gruppe"] == 5
    #Gruppe hoch: die fünf höchsten Ventil-Scores, nie begangene Stationen
    assert sorted(schluessel.loc[schluessel["gruppe"] == "hoch", "zaehler"]) == [1000, 1001, 1002, 1003, 1004]
    zufall = set(schluessel.loc[schluessel["gruppe"] == "zufall", "zaehler"])
    assert len(zufall) == 5 and not zufall & {1000, 1001, 1002, 1003, 1004}
    assert not zufall & {1026, 1027, 1028, 1029}  #schon begangen
    #die Begehungsliste verrät die Gruppe nicht
    assert list(liste.columns) == ["nr", "zaehler"]
    assert set(liste["zaehler"]) == set(schluessel["zaehler"])
    #ein festgelegter Plan wird nicht überschrieben
    with pytest.raises(SystemExit):
        bt.pruefung_planen(anzahl=5, seed=7, listen_ordner=listen, rueckmeldungen=rm, ziel=ziel,
                           jetzt=datetime(2026, 12, 2, 9, 0))
    #gleicher Seed, gleiche Auswahl
    nochmal = bt.pruefung_planen(anzahl=5, seed=7, listen_ordner=listen, rueckmeldungen=rm, ziel=ziel,
                                 jetzt=datetime(2026, 12, 2, 9, 1))
    assert set(pd.read_csv(nochmal / "schluessel.csv")["zaehler"]) == set(schluessel["zaehler"])

    #Rückmeldungen: in Gruppe hoch 4 von 5 mit Ventilbefund, in Gruppe zufall 0 von 5
    hoch = sorted(schluessel.loc[schluessel["gruppe"] == "hoch", "zaehler"])
    zeilen = [{"zaehler": z, "datum": "2026-12-10", "befund_ventil": i < 4, "befund_daemmung": False,
               "befund_anschluss": False} for i, z in enumerate(hoch)]
    zeilen += [{"zaehler": z, "datum": "2026-12-11", "befund_ventil": False, "befund_daemmung": False,
                "befund_anschluss": False} for z in sorted(zufall)]
    #eine Begehung vor dem Plan zählt nicht
    zeilen.append({"zaehler": hoch[4], "datum": "2026-11-20", "befund_ventil": True,
                   "befund_daemmung": False, "befund_anschluss": False})
    pd.DataFrame(zeilen).to_csv(rm, index=False)
    text = bt.pruefung_auswerten(ordner, rueckmeldungen=rm)
    assert "hoch    geplant 5, begangen 5, gewertet 5, Ventilbefund 4 von 5 (80 %)" in text
    assert "zufall  geplant 5, begangen 5, gewertet 5, Ventilbefund 0 von 5 (0 %)" in text
    assert "p (einseitig) = 0,024" in text
    assert (ordner / "auswertung.txt").exists()
    assert "WARNUNG" not in text


def test_auswertung_meldet_veraenderten_schluessel(tmp_path):
    dash = _dashboard(tmp_path)
    listen = tmp_path / "listen"
    bt.liste_sichern(dash, listen, jetzt=datetime(2026, 12, 1, 8, 0))
    ordner = bt.pruefung_planen(anzahl=3, seed=1, listen_ordner=listen, rueckmeldungen=tmp_path / "rm.csv",
                                ziel=tmp_path / "b", jetzt=datetime(2026, 12, 2, 9, 0))
    with open(ordner / "schluessel.csv", "a", encoding="utf-8") as f:
        f.write("9999,hoch,0.99,1,hoch,False,False\n")
    text = bt.pruefung_auswerten(ordner, rueckmeldungen=tmp_path / "rm.csv")
    assert "WARNUNG: schluessel.csv wurde nach dem Festlegen verändert" in text
    assert "noch keine Rückmeldungen" in text


def test_zu_wenige_stationen_fuer_die_stichprobe(tmp_path):
    dash = _dashboard(tmp_path, n=10)
    listen = tmp_path / "listen"
    bt.liste_sichern(dash, listen, jetzt=datetime(2026, 12, 1, 8, 0))
    with pytest.raises(SystemExit, match="Nur 6 nie begangene"):
        bt.pruefung_planen(anzahl=5, listen_ordner=listen, rueckmeldungen=tmp_path / "rm.csv",
                           ziel=tmp_path / "b")
