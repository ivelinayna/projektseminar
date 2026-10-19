import numpy as np
import pandas as pd
import pytest

from src import alarmbewertung as ab
from src import tagesmonitor as tm


def _verlauf(z, meter=1, kanal="kwh_pro_m3", start="2024-01-01"):
    return pd.DataFrame({"meter": meter, "kanal": kanal,
                         "datum": pd.date_range(start, periods=len(z)),
                         "z": z})


def test_alarme_mit_schwelle_wie_monitor_bei_h5():
    rng = np.random.default_rng(0)
    z = np.r_[rng.normal(0, 1, 60), np.full(20, -2.0)]
    a = ab.alarme_mit_schwelle(_verlauf(z), 5.0)
    _, _, al = tm.cusum(z)
    assert len(a) == len(al) >= 1
    assert list(a["richtung"]) == [r for _, r, _ in al]
    assert a.iloc[-1]["richtung"] == -1


def test_alarme_mit_schwelle_ueber_altem_deckel():
    #mit festem Deckel 10 gäbe es bei h = 15 nie einen Alarm
    z = np.full(30, 3.0)
    assert len(ab.alarme_mit_schwelle(_verlauf(z), 15.0)) == 1
    assert len(ab.alarme_mit_schwelle(_verlauf(z), 15.0,
                                      deckel_faktor=10 / 15)) == 0


def test_alarme_mit_schwelle_leer():
    a = ab.alarme_mit_schwelle(_verlauf([]).iloc[0:0], 5.0)
    assert list(a.columns) == tm.ALARM_SPALTEN and len(a) == 0


def test_bewerte_richtung():
    a = pd.DataFrame({"meter": 1, "datum": pd.Timestamp("2024-01-01"),
                      "kanal": ["kwh_pro_m3", "kwh_pro_m3",
                                "log_volumen", "log_volumen"],
                      "richtung": [-1, 1, 1, -1]})
    assert list(ab.bewerte_richtung(a)["bewertung"]) == \
        ["schlechter", "besser", "schlechter", "besser"]


def test_heizperiode():
    assert ab.heizperiode("23/24") == (pd.Timestamp("2023-10-01"),
                                       pd.Timestamp("2024-04-30"))


def _markiert():
    return pd.DataFrame({
        "meter": [1, 2, 3, 4, 4],
        "winter": ["23/24", "23/24", "23/24", "23/24", "24/25"],
        "score": [1.0, 1.0, 1.0, np.nan, 0.5],
        "auffaellig": [True, True, False, False, False],
        "schlecht_steigung": [True, False, False, False, False],
        "schlecht_spreizung_ref_k": [True, True, False, False, False],
        "schlecht_residuum_sd": [False, False, True, False, False]})


def _alarme():
    return pd.DataFrame({
        "meter": [1, 2, 3, 3],
        "kanal": ["kwh_pro_m3", "kwh_pro_m3", "log_volumen", "log_volumen"],
        "datum": pd.to_datetime(["2024-01-10", "2024-02-01",
                                 "2024-03-01", "2024-06-01"]),
        "richtung": [-1, 1, 1, 1],
        "beginn": pd.to_datetime(["2024-01-01"] * 4)})


def test_prioritaet_je_winter():
    p = ab.prioritaet_je_winter(_markiert(), _alarme()).set_index("meter")
    assert len(p) == 4
    assert p.loc[1, "prioritaet"] == "hoch"
    #Besserungsalarm hebt nicht an
    assert p.loc[2, "prioritaet"] == "mittel"
    assert p.loc[2, "alarme_besser"] == 1
    #Alarm im Juni liegt außerhalb der Heizperiode
    assert p.loc[3, "prioritaet"] == "mittel"
    assert p.loc[3, "alarme_schlechter"] == 1
    assert p.loc[4, "prioritaet"] == "niedrig"


def test_juengster_winter():
    p = ab.prioritaet_je_winter(_markiert(), _alarme())
    assert ab.juengster_winter(p).loc[4, "winter"] == "24/25"


def test_fehlerbild_regeln():
    assert ab.fehlerbild([]) == ""
    assert ab.fehlerbild(["steigung", "spreizung_ref_k", "residuum_sd"]) == "ventil"
    assert ab.fehlerbild(["spreizung_ref_k", "flow_spez_lh_kw"]) == "durchfluss"
    assert ab.fehlerbild(["spreizung_ref_k"]) == ""
    assert ab.fehlerbild(["residuum_sd", "steigung"]) == "unruhig"
    assert ab.fehlerbild(["steigung"]) == "regelung"
    assert set(ab.FEHLERBILD_TEXT) >= {"ventil", "durchfluss", "unruhig"}


def test_fehlerbild_je_winter():
    kz = ["steigung", "spreizung_ref_k", "residuum_sd"]
    f = ab.fehlerbild_je_winter(_markiert(), kz).set_index("meter")
    assert f.loc[1, "fehlerbild"] == "ventil"
    assert f.loc[1, "schlechte_kennzahlen"] == "steigung,spreizung_ref_k"
    assert f.loc[3, "fehlerbild"] == "unruhig"


def test_befund_nach_winter_nimmt_erste_begehung_danach():
    tab = pd.DataFrame({"meter": [1, 2, 3], "winter": ["23/24"] * 3})
    kodiert = pd.DataFrame({
        "meter": [1, 1, 2, 3],
        "datum": pd.to_datetime(["2024-06-01", "2024-09-01",
                                 "2024-03-01", "2025-08-01"]),
        "ventil_stellantrieb": [False, True, True, True],
        "pumpe": [True, False, False, False]})
    b = ab.befund_nach_winter(tab, kodiert, {"ventil": ["ventil_stellantrieb"],
                                             "mech": ["pumpe", "ventil_stellantrieb"]})
    #2: Begehung noch in der Heizperiode, 3: mehr als 400 Tage danach
    assert list(b["meter"]) == [1]
    assert not b.iloc[0]["ventil"] and b.iloc[0]["mech"]


def test_vierfeld():
    v = ab.vierfeld(pd.Series([1, 1, 0, 0, 0]), pd.Series([1, 0, 0, 0, 1]))
    assert (v["merkmal_mit_befund"], v["rest_mit_befund"]) == (1, 1)
    assert v["quote_merkmal"] == 0.5
    assert 0 < v["p (einseitig)"] <= 1


def test_gebiet():
    assert ab.gebiet(0.9) == "überwiegend alt"
    assert ab.gebiet(0.5) == "gemischt"
    assert ab.gebiet(0.1) == "überwiegend neu"
    assert ab.gebiet(np.nan) == "unbekannt"


def _zensusdatei(tmp_path, x, y):
    kopf = ["GITTER_ID_100M", "x_mp_100m", "y_mp_100m", "Insgesamt_Gebaeude",
            *ab.ZENSUS_ALT, *ab.ZENSUS_NEU]
    zeilen = [";".join(kopf),
              ";".join(["id1", str(int(x)), str(int(y)), "10",
                        "4", "–", "2", "–", "2", "1", "–", "–", "–", "1"]),
              ";".join(["id2", "50", "50", "3"] + ["–"] * 10)]
    pfad = tmp_path / "zensus.csv"
    pfad.write_text("\n".join(zeilen), encoding="utf-8")
    return pfad


def test_zensus_gebiet(tmp_path):
    lat, lon = 49.8, 10.4
    gx, gy = ab.gitterzelle([lat], [lon])
    assert gx[0] % 100 == 50 and gy[0] % 100 == 50
    z = ab.lade_zensus(_zensusdatei(tmp_path, gx[0], gy[0]))
    assert z["a1919bis1949"].isna().iloc[0]
    k = pd.DataFrame({"meter": [1, 2], "lat": [lat, 40.0], "lon": [lon, 5.0],
                      "genau": [False, True]})
    g = ab.zensus_gebiet(k, z).set_index("meter")
    assert g.loc[1, "anteil_alt"] == pytest.approx(8 / 10)
    assert g.loc[1, "gebiet_baujahr"] == "überwiegend alt"
    assert g.loc[1, "lage"] == "Straße"
    assert g.loc[2, "gebiet_baujahr"] == "unbekannt"
    assert not any("lat" in c or "x_mp" in c for c in g.columns)


def test_lade_zensus_rahmen(tmp_path):
    z = ab.lade_zensus(_zensusdatei(tmp_path, 1000, 1000),
                       rahmen=(900, 1100, 900, 1100))
    assert len(z) == 1


def test_baujahr_kontext_freitext_vor_zensus():
    labels = pd.DataFrame({"meter": [1, 2, 3], "baujahr": [2005, np.nan, np.nan]})
    geb = pd.DataFrame({"meter": [1, 2, 3, 4],
                        "gebiet_baujahr": ["überwiegend alt", "überwiegend neu",
                                           "gemischt", "überwiegend alt"],
                        "lage": "Straße"})
    b = ab.baujahr_kontext(labels, geb).set_index("meter")
    assert b.loc[1, "baujahr_alt"] == False
    assert b.loc[1, "baujahr_quelle"] == "Begehung"
    assert b.loc[2, "baujahr_quelle"] == "Zensus"
    assert b.loc[2, "baujahr_alt"] == False
    assert pd.isna(b.loc[3, "baujahr_alt"]) and b.loc[3, "baujahr_quelle"] == ""
    assert b.loc[4, "baujahr_alt"] == True


def test_baujahr_kontext_ohne_zensus():
    b = ab.baujahr_kontext(pd.DataFrame({"meter": [1], "baujahr": [1960]}))
    assert b.iloc[0]["baujahr_alt"] == True
    assert b.iloc[0]["gebiet_baujahr"] == "unbekannt"
