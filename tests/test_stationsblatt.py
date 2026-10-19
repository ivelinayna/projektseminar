"""Tests für das Stationsblatt."""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from src import stationsblatt as bl
from src import tagesmonitor as tm


def _fenster(werte, tage=3, spalte="steigung"):
    """Fenstertabelle mit konstantem Wert je Station über einige Tage."""
    zeilen = []
    for d in pd.date_range("2024-01-01", periods=tage):
        for m, v in werte.items():
            zeilen.append({"meter": m, "datum": d, spalte: v})
    return pd.DataFrame(zeilen)


def test_netzband_quantile():
    band = bl.netzband(_fenster({m: float(m) for m in range(1, 12)}),
                       "steigung", min_stationen=5)
    assert list(band.columns) == ["datum", "n", "q10", "q50", "q90"]
    assert len(band) == 3
    assert band["n"].eq(11).all()
    assert band["q50"].iloc[0] == pytest.approx(6.0)
    assert band["q10"].iloc[0] == pytest.approx(np.quantile(np.arange(1, 12), 0.1))
    assert band["q90"].iloc[0] == pytest.approx(np.quantile(np.arange(1, 12), 0.9))


def test_netzband_luecke_unter_min_stationen():
    band = bl.netzband(_fenster({1: 1.0, 2: 2.0, 3: 3.0}), "steigung",
                       min_stationen=5)
    assert band["n"].eq(3).all()
    assert band[["q10", "q50", "q90"]].isna().all().all()


def test_netzband_ohne_bhkw():
    werte = {m: 1.0 for m in range(1, 6)}
    werte[99] = 50.0
    band = bl.netzband(_fenster(werte), "steigung", ausschluss=[99],
                       min_stationen=5)
    assert band["n"].eq(5).all()
    assert band["q90"].iloc[0] == pytest.approx(1.0)


def test_netzband_nan_zaehlt_nicht():
    werte = {m: float(m) for m in range(1, 11)}
    werte[11] = np.nan
    band = bl.netzband(_fenster(werte), "steigung", min_stationen=5)
    assert band["n"].eq(10).all()


def test_netzband_leer():
    band = bl.netzband(pd.DataFrame(), "steigung")
    assert list(band.columns) == ["datum", "n", "q10", "q50", "q90"]
    assert len(band) == 0


def _netzwerte():
    return {m: 1.0 + 0.05 * (m % 5) for m in range(1, 21)}


def test_netz_z_tag_flache_steigung_ist_schlecht():
    werte = _netzwerte()
    werte[50] = 0.0
    z = bl.netz_z_tag(_fenster(werte), "steigung", min_stationen=10)
    assert list(z.columns) == ["meter", "datum", "z"]
    assert (z.loc[z["meter"] == 50, "z"] > 3).all()


def test_netz_z_tag_spreizung_klein_ist_schlecht():
    werte = {m: 20.0 + m for m in range(1, 21)}
    werte[50] = 3.0
    z = bl.netz_z_tag(_fenster(werte, spalte="dt_median_k"), "dt_median_k",
                      min_stationen=10)
    assert (z.loc[z["meter"] == 50, "z"] > 3).all()


def test_netz_z_tag_bhkw_bekommt_wert_ohne_mitzubestimmen():
    werte = _netzwerte()
    ohne = bl.netz_z_tag(_fenster(werte), "steigung", min_stationen=10)
    werte[99] = 100.0
    mit = bl.netz_z_tag(_fenster(werte), "steigung", ausschluss=[99],
                        min_stationen=10)
    assert np.isfinite(mit.loc[mit["meter"] == 99, "z"]).all()
    a = ohne[ohne["meter"] == 1]["z"].to_numpy()
    b = mit[mit["meter"] == 1]["z"].to_numpy()
    assert a == pytest.approx(b)


def test_netz_z_tag_unter_min_stationen_leer():
    z = bl.netz_z_tag(_fenster({1: 1.0, 2: 2.0}), "steigung", min_stationen=10)
    assert len(z) == 0
    assert list(z.columns) == ["meter", "datum", "z"]


def _rohdaten(start="2023-12-01", tage=456, steigung=1.0,
              achsenabschnitt=1.5, rauschen=0.1, seed=0, kwh_pro_m3=20.0):
    """Stundenreihe im Schema von `ternaer.lade_serien`, wie in
    tests/test_kennlinien_monitor.py. 456 Tage ab 01.12.2023 decken die
    Kernwinter 23/24 und 24/25 ab. Energie und Volumen sind kumulativ
    und nur für den Tagesmonitor da; ihr Verhältnis ist ``kwh_pro_m3``."""
    rng = np.random.default_rng(seed)
    zeit = pd.date_range(start, periods=24 * tage, freq="h")
    power = np.exp(rng.uniform(np.log(3.0), np.log(30.0), size=len(zeit)))
    lf = achsenabschnitt + steigung * np.log(power)
    lf = lf + rng.normal(0.0, rauschen, size=len(zeit))
    volumen = power / kwh_pro_m3 * (1 + rng.normal(0.0, 0.05, len(zeit)))
    return pd.DataFrame({"power": power, "flow": np.exp(lf),
                         "dt": np.full(len(zeit), 20.0),
                         "vl": np.full(len(zeit), 60.0),
                         "rt": np.full(len(zeit), 40.0),
                         "energy": np.cumsum(power),
                         "volume": np.cumsum(volumen)}, index=zeit)


REPARATUR = pd.Timestamp("2024-09-09")


def _tagestemperatur():
    tage = pd.date_range("2023-11-01", "2025-04-01", freq="D")
    i = np.arange(len(tage))
    #Wetterwechsel im Wochentakt, sonst ist die Kernwinter-Spanne zu klein
    return pd.Series(7 + 9 * np.sin(2 * np.pi * (i - 150) / 365)
                     + 3 * np.sin(2 * np.pi * i / 9), index=tage)


def _netz():
    serien = {m: _rohdaten(steigung=0.9 + 0.02 * i,
                           achsenabschnitt=1.4 + 0.02 * i, seed=i)
              for i, m in enumerate(range(1, 13))}
    #900: Volumenstrom hängt bis zur Reparatur nicht an der Leistung,
    #die Abkühlung ist bis dahin schlecht
    vor = _rohdaten(steigung=0.0, achsenabschnitt=4.5, seed=40, kwh_pro_m3=10.0)
    nach = _rohdaten(steigung=1.0, achsenabschnitt=1.5, seed=41, kwh_pro_m3=25.0)
    vor = vor[vor.index < REPARATUR]
    nach = nach[nach.index >= REPARATUR].copy()
    #Zählerstände nahtlos fortsetzen
    for spalte in ("energy", "volume"):
        nach[spalte] += vor[spalte].iloc[-1] - nach[spalte].iloc[0]
    serien[900] = pd.concat([vor, nach])
    serien[901] = _rohdaten(seed=42)
    serien[950] = _rohdaten(seed=43)
    serien[999] = pd.DataFrame(columns=["power", "flow", "dt", "vl", "rt"],
                               index=pd.DatetimeIndex([]))
    #960: nur Temperaturen, wie die Fühler im Heizhaus
    fuehler = _rohdaten(seed=44)
    fuehler[["power", "flow", "dt", "energy", "volume"]] = 0.0
    serien[960] = fuehler
    return bl.rechne(serien, termine={900: [REPARATUR]},
                     anschlusswerte={m: 20.0 for m in serien},
                     bhkw={950}, ohne_datum={901}, min_stationen=5,
                     tagestemperatur=_tagestemperatur())


@pytest.fixture(scope="module")
def netz():
    return _netz()


@pytest.fixture(scope="module")
def status(netz):
    return bl.statustabelle(netz)


def _zeile(status, meter):
    return status[status["meter"] == meter].iloc[0]


def test_rechne_liefert_alle_teile(netz):
    for schluessel in ("meters", "punkte", "tabelle", "ausschluss",
                       "markiert", "kennzahlen", "uebersicht", "vergleich",
                       "monitor", "baender", "z_tag", "termine",
                       "anschlusswerte", "bhkw", "ohne_datum", "tagesmonitor",
                       "prioritaet", "baujahr"):
        assert schluessel in netz
    assert netz["meters"] == sorted(netz["meters"])
    assert set(netz["baender"]) == set(bl.KANAELE)
    m = netz["markiert"]
    z = m[(m["meter"] == 900) & (m["winter"] == "23/24")].iloc[0]
    assert bool(z["auffaellig"])


def test_statustabelle_eine_zeile_je_zaehler(netz, status):
    assert list(status.columns) == bl.STATUS_SPALTEN
    assert sorted(status["meter"]) == netz["meters"]


def test_statustabelle_ohne_adressen(status):
    for spalte in status.columns:
        klein = spalte.lower()
        assert "adress" not in klein and "address" not in klein
        assert "strasse" not in klein and "straße" not in klein


def test_statustabelle_station_ohne_daten(status):
    z = _zeile(status, 999)
    assert z["grund"] == "keine_daten"
    assert z["winter"] == ""
    assert z["hinweis"] == ""
    assert int(z["n_winter_score"]) == 0


def test_statustabelle_wintervergleich(status):
    z = _zeile(status, 900)
    assert z["winter"] == "24/25"
    assert z["wv_status"] == "ok"
    assert z["wv_datum"] == "2024-09-09"
    assert (z["wv_winter_vor"], z["wv_winter_nach"]) == ("23/24", "24/25")
    assert abs(z["wv_steigung_vor"]) < 0.1
    assert z["wv_steigung_nach"] == pytest.approx(1.0, abs=0.1)
    assert z["wv_rang_vor"] == 1
    assert z["letzte_begehung"] == "2024-09-09"
    assert np.isfinite(z["netz_z_steigung_aktuell"])
    assert z["datum_z_steigung"] != ""


def test_statustabelle_kontext(status):
    assert bool(_zeile(status, 901)["begangen_ohne_datum"])
    assert bool(_zeile(status, 950)["bhkw"])
    assert not bool(_zeile(status, 1)["bhkw"])
    assert _zeile(status, 1)["wv_status"] == ""


def test_statustabelle_tagesmonitor(status):
    z = _zeile(status, 900)
    assert z["tm_status"] == "ok"
    assert int(z["tm_alarme"]) >= 1
    assert z["tm_letzter_alarm"] >= "2024-09-09"
    assert _zeile(status, 999)["tm_status"] == tm.KEINE_HEIZTAGE
    assert int(_zeile(status, 999)["tm_alarme"]) == 0


def test_tagesmonitor_alarm_nach_reparatur(netz):
    a = netz["tagesmonitor"]["alarme"]
    a = a[(a["meter"] == 900) & (a["kanal"] == "kwh_pro_m3")]
    nach = a[a["datum"] >= REPARATUR]
    assert len(nach) >= 1
    assert nach.iloc[0]["richtung"] == 1
    assert nach.iloc[0]["datum"] <= REPARATUR + pd.Timedelta(days=5)


def test_statustabelle_norm5(status):
    z = _zeile(status, 1)
    assert z["norm5_winter"] == "24/25"
    assert z["norm5_kwh_m3"] == pytest.approx(20.0, abs=1.0)
    assert np.isfinite(z["norm5_abstand_k"])


def test_statustext_tagesmonitor(status):
    text = bl.statustext(_zeile(status, 900))
    assert "Tagesmonitor" in text
    assert "Abkühlung" in text
    assert "5 °C" in bl.statustext(_zeile(status, 1))
    text = bl.statustext(_zeile(status, 999))
    assert "Tagesmonitor: keine nutzbaren Heiztage" in text


def test_hinweis():
    assert bl.hinweis(["steigung", "spreizung_ref_k"]) == \
        "Steigung niedrig, Referenzspreizung klein"
    assert bl.hinweis([]) == "Im Netzvergleich unauffällig"
    assert bl.hinweis([], hat_score=False) == ""


def test_de_formatiert_deutsch():
    assert bl._de(1.5) == "1,50"
    assert bl._de(-0.114, 2) == "-0,11"
    assert bl._de(0.3, 1, vorzeichen=True) == "+0,3"
    assert bl._de(np.nan) == "–"
    assert bl._de(None) == "–"


def test_statustext_mit_wintervergleich(status):
    text = bl.statustext(_zeile(status, 900))
    assert "Kernwinter 24/25" in text
    assert "23/24 → 24/25" in text
    assert "2024-09-09" in text
    assert "Tagesmonitor (CUSUM)" in text
    assert "Monitor-Alarme" not in text


def test_kein_fensteralarm_in_status(status):
    assert "n_alarme" not in status.columns


def test_statustext_spreizung_ohne_steigung(status):
    z = _zeile(status, 900).to_dict()
    z.update(netz_z_steigung_aktuell=np.nan, datum_z_steigung="",
             netz_z_spreizung_aktuell=2.5, datum_z_spreizung="2025-02-01")
    text = bl.statustext(z)
    assert "Netz-z Spreizung am 2025-02-01: +2,5" in text
    assert "Netz-z Steigung" not in text


def test_statustext_ohne_daten(status):
    text = bl.statustext(_zeile(status, 999))
    assert bl.GRUNDTEXT["keine_daten"] in text
    assert "nan" not in text.lower()


def test_statustext_ohne_datum_und_bhkw(status):
    assert "Datum unbekannt" in bl.statustext(_zeile(status, 901))
    assert "BHKW" in bl.statustext(_zeile(status, 950))


def test_statustabelle_prioritaet_und_fehlerbild(netz, status):
    z = _zeile(status, 900)
    assert z["prioritaet"] in ("hoch", "mittel", "niedrig")
    #Nach der Reparatur steigt die Abkühlung, das ist kein Verschlechterungsalarm
    assert 0 <= int(z["tm_alarme_schlechter"]) < int(z["tm_alarme"])
    assert _zeile(status, 999)["prioritaet"] == ""
    m = netz["markiert"]
    v = m[(m["meter"] == 900) & (m["winter"] == "23/24")].iloc[0]
    assert bool(v["schlecht_steigung"]) and bool(v["schlecht_spreizung_ref_k"])
    p = netz["prioritaet"]
    assert p[(p["meter"] == 900) & (p["winter"] == "23/24")
             ]["auffaellig"].iloc[0]


def test_statustext_prioritaet_fehlerbild_baujahr(status):
    z = _zeile(status, 900).to_dict()
    z.update(fehlerbild="ventil", prioritaet="hoch", auffaellig=True,
             alarme_schlechter_winter=2, baujahr=1972.0,
             baujahr_quelle="Begehung")
    text = bl.statustext(z)
    assert "Fehlerbild: Volumenstrom folgt der Leistung kaum" in text
    assert "Priorität 24/25: hoch (Netz auffällig, 2 Alarme verschlechtert)" in text
    assert "Baujahr 1972 (Begehung)" in text
    assert "davon" in text and "schlechter" in text
    z.update(baujahr=np.nan, baujahr_quelle="Zensus",
             gebiet_baujahr="überwiegend neu")
    assert "Baujahrgebiet überwiegend neu" in bl.statustext(z)


def test_statustabelle_baujahr(netz):
    bj = pd.DataFrame({"meter": [900, 1], "baujahr_begehung": [1965.0, np.nan],
                       "gebiet_baujahr": ["gemischt", "überwiegend alt"],
                       "baujahr_quelle": ["Begehung", "Zensus"]})
    s = bl.statustabelle(dict(netz, baujahr=bj))
    assert _zeile(s, 900)["baujahr"] == 1965
    assert _zeile(s, 1)["gebiet_baujahr"] == "überwiegend alt"
    assert _zeile(s, 2)["gebiet_baujahr"] == "unbekannt"


def test_zeichne_stationsblatt(netz, status):
    import matplotlib.pyplot as plt
    for meter in (900, 999, 950):
        fig = bl.zeichne_stationsblatt(meter, netz,
                                       _zeile(status, meter))
        assert len(fig.axes) == 6
        titel = fig._suptitle.get_text()
        assert f"Zähler {meter}" in titel
        plt.close(fig)


def test_exportiere(netz, tmp_path):
    tab = bl.exportiere(netz, out_dir=tmp_path, dpi=40, meters=[900, 999])
    assert (tmp_path / "900.png").stat().st_size > 0
    assert (tmp_path / "999.png").exists()
    gelesen = pd.read_csv(tmp_path / "status.csv")
    assert list(gelesen.columns) == bl.STATUS_SPALTEN
    assert sorted(gelesen["meter"]) == netz["meters"]
    assert len(tab) == len(netz["meters"])


def test_exportiere_unbekannter_zaehler(netz, tmp_path):
    with pytest.raises(KeyError):
        bl.exportiere(netz, out_dir=tmp_path, meters=[123456])


def test_messstelle_ohne_durchfluss(netz, status):
    assert netz["messstellen"] == {960}
    z = _zeile(status, 960)
    assert z["grund"] == "keine_hast"
    assert "keine Übergabestation" in bl.statustext(z)


def test_exportiere_kein_blatt_fuer_messstelle(netz, tmp_path):
    (tmp_path / "960.png").write_bytes(b"alt")
    tab = bl.exportiere(netz, out_dir=tmp_path, dpi=40, meters=[960, 999])
    assert not (tmp_path / "960.png").exists()
    assert (tmp_path / "999.png").exists()
    assert 960 in set(tab["meter"])


def test_netzband_bestes_viertel():
    werte = {m: float(m) for m in range(1, 9)}
    band = bl.netzband(_fenster(werte), "steigung", min_stationen=5,
                       best_vorzeichen=-1)
    #Steigung: größer ist besser, also oberes Achtel als Median des besten Viertels
    assert band["best"].iloc[0] == pytest.approx(np.quantile(np.arange(1, 9), 0.875))


def test_statustabelle_potenzial(netz, status):
    assert "potenzial" in netz
    gueltig = status[status["winter"] != ""]
    assert gueltig["potenzial"].isin(["gering", "mittel", "hoch"]).all()
    assert _zeile(status, 999)["potenzial"] == ""
    #ohne Lücke steht keine Kennzahl drin, mit Lücke eine aus dem Score
    luecken = set(gueltig["groesste_luecke"]) - {""}
    assert luecken <= set(netz["kennzahlen"])
    z = _zeile(status, 1)
    assert "Gegen bestes Viertel: Potenzial" in bl.statustext(z)


def test_luecke_text():
    assert bl.luecke_text("spreizung_ref_k", 12.34) == \
        "Spreizung 12,3 K unter dem besten Viertel"
    assert bl.luecke_text("rl_ueber_50_anteil", 0.25) == \
        "RL > 50 °C 25 Prozentpunkte über dem besten Viertel"
    assert bl.luecke_text("steigung", 0.2) == "Steigung 0,20 unter dem besten Viertel"
