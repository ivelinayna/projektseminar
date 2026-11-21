import pandas as pd

from src.aktualisieren import bericht


def _status(**ueber):
    zeilen = [
        dict(meter=1, winter="24/25", prioritaet="hoch", rang=2,
             fehlerbild="Rücklauf zu warm", alarme_schlechter_winter=3,
             letzte_begehung=None, auffaellig=True, tm_status="ok"),
        dict(meter=2, winter="24/25", prioritaet="niedrig", rang=40,
             fehlerbild=None, alarme_schlechter_winter=0,
             letzte_begehung="2025-01-10", auffaellig=False, tm_status="ok"),
        dict(meter=3, winter=None, prioritaet=None, rang=None,
             fehlerbild=None, alarme_schlechter_winter=0,
             letzte_begehung=None, auffaellig=False,
             tm_status="zu wenig Referenztage"),
    ]
    df = pd.DataFrame(zeilen)
    for k, v in ueber.items():
        df[k] = v
    return df


def _alarme():
    return pd.DataFrame({
        "meter": [1, 2, 2],
        "datum": pd.to_datetime(["2026-03-28", "2026-03-30", "2026-01-05"]),
        "bewertung": ["schlechter", "besser", "schlechter"],
    })


def test_bericht_hoch_und_aktuelle_alarme():
    text = bericht(_status(), _alarme(), pd.Timestamp("2026-03-31 23:00"))
    assert "Priorität im Kernwinter 24/25: 1 hoch, 0 mittel, 1 niedrig" in text
    assert "1  Rang 2, Rücklauf zu warm, 3 Alarme verschlechtert, keine Begehung" in text
    #der Januar-Alarm liegt außerhalb der 14 Tage
    assert "verschlechtert: 1 Stationen: 1\n" in text
    assert "verbessert: 1 Stationen: 2\n" in text
    assert "nicht aktiv bei 1 Stationen" in text
    assert "Geändert" not in text


def test_bericht_aenderungen_gegenueber_vorlauf():
    vorher = _status()
    vorher.loc[vorher["meter"] == 1, "prioritaet"] = "mittel"
    vorher.loc[vorher["meter"] == 2, "auffaellig"] = True
    vorher = vorher[vorher["meter"] != 3]
    #status.csv liest fehlende Werte als NaN, die frische Tabelle hat leere Strings
    jetzt = _status()
    jetzt.loc[jetzt["meter"] == 3, "prioritaet"] = ""
    vorher = pd.concat([vorher, _status().iloc[[2]]])
    vorher.loc[vorher["meter"] == 3, "prioritaet"] = float("nan")
    text = bericht(jetzt, _alarme().iloc[:0], pd.Timestamp("2026-03-31"),
                   vorher=vorher)
    assert "  keine" in text
    assert "1  Priorität mittel -> hoch" in text
    assert "2  jetzt unauffällig im Netzvergleich" in text
    assert "3  " not in text


def test_bericht_leere_begehung():
    status = _status(letzte_begehung="")
    text = bericht(status, _alarme(), pd.Timestamp("2026-03-31"))
    assert "keine Begehung bekannt" in text
    assert "letzte Begehung \n" not in text


def test_bericht_potenzial():
    status = _status(potenzial=["mittel", "hoch", ""],
                     potenzial_score=[1.2, 2.4, None],
                     groesste_luecke=["steigung", "spreizung_ref_k", ""],
                     bw_abstand_spreizung_ref_k=[0.0, 9.14, None])
    text = bericht(status, _alarme(), pd.Timestamp("2026-03-31"))
    assert "Potenzial gegen das beste Viertel in 24/25: 1 hoch, 1 mittel, 0 gering" in text
    assert "2  Priorität niedrig, Spreizung 9,1 K unter dem besten Viertel" in text
    assert "1  Priorität hoch, größte" not in text


def test_bericht_messstelle_nicht_mitgezaehlt():
    status = _status(grund=["", "", "keine_hast"])
    text = bericht(status, _alarme(), pd.Timestamp("2026-03-31"))
    assert "1 Messstelle ohne Übergabestation (nur Temperaturen) nicht bewertet: 3" in text
    assert "nicht aktiv" not in text
    assert "ohne Einstufung" not in text


def _reihe(ende):
    idx = pd.date_range("2025-01-01", ende, freq="1h")
    return pd.DataFrame({"vor": 70.0}, index=idx)


def test_karten_ende_bleibt_beim_abgabestand():
    from src.aktualisieren import KARTE_ENDE_MIN, karten_ende
    #die meisten Zähler enden im Juli 2025, einzelne Nachlieferungen bis 2026 zählen nicht
    serien = {i: _reihe("2025-07-31 23:00") for i in range(5)}
    serien[99] = _reihe("2026-07-15 23:00")
    assert karten_ende(serien) == KARTE_ENDE_MIN


def test_karten_ende_rueckt_mit_der_mehrheit():
    from src.aktualisieren import karten_ende
    serien = {i: _reihe("2026-03-31 23:00") for i in range(4)}
    serien[9] = _reihe("2025-07-31 23:00")
    assert karten_ende(serien) == pd.Timestamp("2026-03-31 23:00")


def test_karten_ende_ohne_reihen():
    from src.aktualisieren import KARTE_ENDE_MIN, karten_ende
    assert karten_ende({}) == KARTE_ENDE_MIN


def test_notebook_ausfuehren_mit_magie_und_umgebung(tmp_path):
    import pytest
    nbformat = pytest.importorskip("nbformat")
    pytest.importorskip("nbclient")
    pytest.importorskip("ipykernel")
    from src.aktualisieren import notebook_ausfuehren

    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_markdown_cell("Test"),
        nbformat.v4.new_code_cell("import os\nwert = os.environ['TEST_WERT']"),
        nbformat.v4.new_code_cell("%time zahl = 2\nprint('wert', wert, zahl)"),
    ]
    pfad = tmp_path / "test.ipynb"
    nbformat.write(nb, pfad)
    log = tmp_path / "test.log"
    assert notebook_ausfuehren(pfad, log=log, umgebung={"TEST_WERT": "abc"}) == 2
    assert "wert abc 2" in log.read_text(encoding="utf-8")
    #das Notebook selbst bleibt unverändert
    assert nbformat.read(pfad, as_version=4).cells[2].outputs == []


def test_notebook_ausfuehren_meldet_fehler(tmp_path):
    import pytest
    nbformat = pytest.importorskip("nbformat")
    pytest.importorskip("nbclient")
    pytest.importorskip("ipykernel")
    from src.aktualisieren import notebook_ausfuehren

    nb = nbformat.v4.new_notebook()
    nb.cells = [nbformat.v4.new_code_cell("raise ValueError('kaputt')")]
    pfad = tmp_path / "fehler.ipynb"
    nbformat.write(nb, pfad)
    with pytest.raises(RuntimeError, match="fehler.ipynb.*kaputt"):
        notebook_ausfuehren(pfad)
