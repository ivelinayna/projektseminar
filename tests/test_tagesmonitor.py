import numpy as np
import pandas as pd
import pytest

from src import tagesmonitor as tm


def stundenreihe(tage=3, fluss_lh=500.0, leistung_kw=10.0,
                 start="2024-01-01"):
    idx = pd.date_range(start, periods=24 * tage, freq="h")
    fluss = np.full(len(idx), fluss_lh)
    leistung = np.full(len(idx), leistung_kw)
    return pd.DataFrame({
        "energy": np.cumsum(leistung) + 1000.0,
        "flow": fluss, "power": leistung,
        "dt": np.full(len(idx), 20.0), "vl": np.full(len(idx), 70.0),
        "rt": np.full(len(idx), 50.0),
        "volume": np.cumsum(fluss / 1000.0) + 100.0,
    }, index=pd.DatetimeIndex(idx, name="Timestamp"))


def test_tageswerte_aus_zaehlerstaenden():
    t = tm.tageswerte(stundenreihe(tage=3))
    assert len(t) == 3
    mitte = t.iloc[1]
    assert mitte["energie_kwh"] == pytest.approx(240.0)
    assert mitte["volumen_m3"] == pytest.approx(12.0)
    assert mitte["n_stunden"] == 24
    assert mitte["kwh_pro_m3"] == pytest.approx(20.0)
    assert mitte["log_volumen"] == pytest.approx(np.log(12.0))


def test_tageswerte_bei_tagesaufloesung():
    s = stundenreihe(tage=5)
    s = s[s.index.hour == 23]
    t = tm.tageswerte(s)
    assert (t["n_stunden"] == 1).all()
    assert t["energie_kwh"].iloc[2] == pytest.approx(240.0)


def test_tagestemperatur_braucht_genug_stunden():
    ts = pd.date_range("2024-01-01", periods=48, freq="h")
    w = pd.DataFrame({"timestamp": ts, "t_out": np.r_[np.full(24, 2.0),
                                                      np.full(24, 6.0)]})
    w.loc[30:45, "t_out"] = np.nan
    t = tm.tagestemperatur(w, min_stunden=20)
    assert t.loc[pd.Timestamp("2024-01-01")] == pytest.approx(2.0)
    assert np.isnan(t.loc[pd.Timestamp("2024-01-02")])


def _tage(**spalten):
    n = len(next(iter(spalten.values())))
    basis = {"meter": [1] * n,
             "datum": pd.date_range("2024-01-01", periods=n, freq="D"),
             "n_stunden": [24] * n, "fluss_mittel_lh": [500.0] * n,
             "leistung_mittel_kw": [10.0] * n, "energie_kwh": [240.0] * n,
             "volumen_m3": [12.0] * n, "t_mittel_c": [0.0] * n}
    basis.update(spalten)
    d = pd.DataFrame(basis)
    d["kwh_pro_m3"] = d["energie_kwh"] / d["volumen_m3"]
    return d


def test_markiere_gruende_und_nichts_wird_geloescht():
    d = _tage(energie_kwh=[240.0, -5.0, 2.0, 240.0, 0.0, 240.0, np.nan],
              volumen_m3=[12.0, 12.0, 12.0, 2.0, 12.0, 12.0, 12.0],
              t_mittel_c=[0.0, 0, 0, 0, 0, np.nan, 0])
    m = tm.markiere(d)
    assert len(m) == len(d)
    g = m["grund"].tolist()
    assert g[0] == ""
    assert "ruecksprung" in g[1]
    assert "wenig_energie" in g[2]
    assert "unplausibel" in g[3]
    assert "zaehler_steht" in g[4]
    assert "nach_stillstand" in g[5] and "ohne_wetter" in g[5]
    assert "kein_zaehlerstand" in g[6]
    assert m["nutzbar"].tolist() == [True] + [False] * 6


def test_markiere_ignoriert_wenig_stunden_fuer_nutzbar():
    m = tm.markiere(_tage(n_stunden=[1, 24]))
    assert "wenig_stunden" in m["grund"].iloc[0]
    assert m["nutzbar"].all()


def test_markiere_heiztag():
    m = tm.markiere(_tage(t_mittel_c=[14.9, 15.0]))
    assert m["heiztag"].tolist() == [True, False]


def test_ausschlusstabelle_zaehlt_gruende():
    m = tm.markiere(_tage(energie_kwh=[240.0, 2.0, 2.0]))
    tab = tm.ausschlusstabelle(m).set_index("grund")
    assert tab.loc["wenig_energie", "tage"] == 2
    assert tab.loc["wenig_energie", "stationen"] == 1


def _modelltage(meter, start, tage, t=None, kwh=None, vol=None):
    datum = pd.date_range(start, periods=tage, freq="D")
    t = 2.5 + 7.5 * np.sin(np.arange(tage) / 10) if t is None else t
    kwh = 20 - 0.5 * t if kwh is None else kwh
    vol = 3 - 0.1 * t if vol is None else vol
    return pd.DataFrame({"meter": meter, "datum": datum, "t_mittel_c": t,
                         "kwh_pro_m3": kwh, "log_volumen": vol})


def test_referenz_ein_jahr_und_vor_begehung():
    mt = pd.concat([_modelltage(1, "2022-01-01", 800),
                    _modelltage(2, "2022-01-01", 800)])
    ref = tm.referenz(mt, {2: [pd.Timestamp("2022-06-01")]})
    assert ref.at[1, "ref_ende"] == pd.Timestamp("2023-01-01")
    assert ref.at[1, "ende_grund"] == "ein Jahr"
    assert ref.at[2, "ref_ende"] == pd.Timestamp("2022-05-18")
    assert ref.at[2, "ende_grund"] == "vor Begehung"
    assert (ref["status"] == "ok").all()


def test_referenz_status():
    mt = pd.concat([
        _modelltage(1, "2022-01-01", 30),
        _modelltage(2, "2022-01-01", 400, t=np.full(400, 3.0)),
        _modelltage(3, "2022-01-01", 200)])
    ref = tm.referenz(mt, {})
    assert ref.at[1, "status"] == "zu wenige Referenztage"
    assert ref.at[2, "status"] == "zu kleine Temperaturspanne"
    assert ref.at[3, "status"] == "keine Tage nach der Referenz"


def test_kennlinie_gerade_und_klassen():
    t = np.linspace(-10, 10, 200)
    k = tm.lerne_kennlinie("gerade", t, 3 + 2 * t)
    assert k["a"] == pytest.approx(3) and k["b"] == pytest.approx(2)
    k = tm.lerne_kennlinie("klassen", t, 3 + 2 * t)
    assert k["form"] == "klassen"
    assert tm.kennlinienwert(k, 0.0) == pytest.approx(3, abs=0.5)
    #zu wenige Tage je Klasse -> Gerade als Ersatz
    k = tm.lerne_kennlinie("klassen", t[:10], 3 + 2 * t[:10])
    assert k["form"] == "gerade"


def test_streuung_und_autokorrelation():
    rng = np.random.default_rng(0)
    assert tm.robuste_streuung(rng.normal(0, 2, 20000)) == pytest.approx(2, rel=0.05)
    assert tm.autokorrelation(np.array([1.0, 2.0])) == 0.0
    assert tm.autokorrelation(np.ones(10)) == 0.0
    assert tm.autokorrelation(np.cumsum(rng.normal(size=2000))) > 0.9


def test_cusum_alarm_beginn_und_deckel():
    z = np.r_[np.zeros(5), np.full(10, 2.0)]
    sp, sm, alarme = tm.cusum(z)
    #1,5 je Tag ab Index 5: 1,5 3 4,5 6 -> Alarm an Index 8, Lauf beginnt 5
    assert alarme == [(8, 1, 5)]
    assert sp.max() == 10.0
    assert (sm == 0).all()


def test_cusum_neuer_alarm_erst_nach_nullstand():
    z = np.r_[np.full(6, 2.0), np.full(12, -2.0), np.full(6, 2.0)]
    _, _, alarme = tm.cusum(z)
    richtungen = [a[1] for a in alarme]
    assert richtungen == [1, -1, 1]


def test_monitor_findet_sprung_nach_referenz():
    rng = np.random.default_rng(1)
    n = 700
    t = 5 + 6 * np.sin(np.arange(n) / 20)
    kwh = 20 - 0.5 * t + rng.normal(0, 0.3, n)
    kwh[500:] -= 3
    mt = _modelltage(7, "2022-01-01", n, t=t, kwh=kwh,
                     vol=3 - 0.1 * t + rng.normal(0, 0.05, n))
    ref = tm.referenz(mt, {})
    mod, modtab = tm.modelle(mt, ref)
    assert set(modtab["kanal"]) == set(tm.KANAELE)
    verlauf, alarme = tm.monitor(mt, ref, mod)
    assert verlauf["datum"].min() >= ref.at[7, "ref_ende"]
    sprung = mt["datum"].iloc[500]
    a = alarme[(alarme["kanal"] == "kwh_pro_m3")
               & (alarme["datum"] >= sprung)].sort_values("datum")
    assert len(a) >= 1
    erster = a.iloc[0]
    assert erster["richtung"] == -1
    assert erster["datum"] <= sprung + pd.Timedelta(days=10)
    assert {"residuum", "z", "s_plus", "s_minus"} <= set(verlauf.columns)


def test_faelle_aus_kodierten_begehungen():
    k = pd.DataFrame({"meter": [1.0, 1.0, 2.0, np.nan],
                      "datum": pd.to_datetime(["2024-01-05", "2024-01-05",
                                               "2024-02-01", "2024-03-01"]),
                      "kategorie": ["a", "a", "b", "c"],
                      "pumpe": [False, True, False, True],
                      "regler_parameter": [True, False, True, False]})
    f = tm.faelle(k)
    assert len(f) == 2
    assert f.set_index("meter").loc[1, "mechanisch"]
    assert not f.set_index("meter").loc[2, "mechanisch"]


def _beobachtet(meter, start="2024-01-01", tage=200):
    return {m: pd.DatetimeIndex(pd.date_range(start, periods=tage, freq="D"))
            for m in meter}


def test_treffertest_gegen_kontrollen():
    datum = pd.Timestamp("2024-03-01")
    faelle = pd.DataFrame({"meter": [1], "datum": [datum],
                           "mechanisch": [True], "kategorie": ["x"]})
    alarme = pd.DataFrame({"meter": [1, 2, 9],
                           "kanal": ["kwh_pro_m3"] * 3,
                           "datum": [datum + pd.Timedelta(days=3),
                                     datum + pd.Timedelta(days=10),
                                     datum + pd.Timedelta(days=10)]})
    beob = _beobachtet(range(1, 9))
    beob[9] = beob[1]
    #Station 9 hatte selbst eine Begehung kurz vorher -> keine Kontrolle
    termine = {1: [datum], 9: [datum - pd.Timedelta(days=30)]}
    t = tm.treffertest(faelle, alarme, beob, termine,
                       pruefungen={"Abkühlung": ["kwh_pro_m3"]})
    assert len(t) == 1
    z = t.iloc[0]
    assert z["treffer"]
    assert z["n_kontrolle"] == 7
    assert z["kontrollquote"] == pytest.approx(1 / 7)
    b = tm.bilanz(t, ["pruefung"])
    assert b.loc[0, "Hebel"] == pytest.approx(7.0)


def test_treffertest_braucht_beobachtbare_station():
    datum = pd.Timestamp("2024-03-01")
    faelle = pd.DataFrame({"meter": [1], "datum": [datum],
                           "mechanisch": [False], "kategorie": ["x"]})
    beob = _beobachtet(range(2, 9))
    t = tm.treffertest(faelle, pd.DataFrame(columns=["meter", "kanal", "datum"]),
                       beob, {1: [datum]},
                       pruefungen={"Abkühlung": ["kwh_pro_m3"]})
    assert len(t) == 0


def test_wirkung_did_gegen_kontrollen():
    datum = pd.Timestamp("2024-03-01")
    tage = pd.date_range("2023-12-01", "2024-06-01", freq="D")
    zeilen = []
    for m in range(1, 8):
        res = np.where(tage > datum, 1.0 if m == 1 else 0.2, 0.0)
        zeilen.append(pd.DataFrame({"meter": m, "kanal": "kwh_pro_m3",
                                    "datum": tage, "residuum": res}))
    verlauf = pd.concat(zeilen, ignore_index=True)
    faelle = pd.DataFrame({"meter": [1], "datum": [datum],
                           "mechanisch": [True], "kategorie": ["x"]})
    w = tm.wirkung(verlauf, faelle, {1: [datum]})
    assert len(w) == 1
    assert w.loc[0, "delta"] == pytest.approx(1.0)
    assert w.loc[0, "delta_kontrolle"] == pytest.approx(0.2)
    assert w.loc[0, "did"] == pytest.approx(0.8)
    assert w.loc[0, "n_kontrolle"] == 6


def test_norm_winter_abstand_und_bhkw():
    zeilen = []
    datum = pd.date_range("2023-12-01", "2024-02-29", freq="D")
    t = np.linspace(-6, 10, len(datum))
    for m in range(1, 24):
        versatz = 0.0 if m != 5 else -11.5
        zeilen.append(pd.DataFrame({"meter": m, "datum": datum, "t_mittel_c": t,
                                    "kwh_pro_m3": 30 + versatz - t}))
    bhkw = pd.DataFrame({"meter": 86792512, "datum": datum, "t_mittel_c": t,
                         "kwh_pro_m3": 1.0 - t})
    mt = pd.concat(zeilen + [bhkw], ignore_index=True)
    n = tm.norm_winter(mt).set_index("meter")
    assert n.loc[1, "winter"] == "23/24"
    assert n.loc[1, "norm_kwh_m3"] == pytest.approx(25.0)
    assert n.loc[5, "abstand_k"] == pytest.approx(10.0)
    assert n.loc[1, "abstand_k"] == pytest.approx(0.0)
    assert n.loc[86792512, "bhkw"]
    assert n.loc[1, "n_stationen"] == 23


def test_norm_winter_zu_wenige_stationen():
    datum = pd.date_range("2023-12-01", "2024-02-29", freq="D")
    t = np.linspace(-6, 10, len(datum))
    mt = pd.concat([pd.DataFrame({"meter": m, "datum": datum, "t_mittel_c": t,
                                  "kwh_pro_m3": 30 - t}) for m in range(3)])
    n = tm.norm_winter(mt)
    assert n["abstand_k"].isna().all()


def test_stationsstand_fasst_alarme_zusammen():
    ref = pd.DataFrame({"status": ["ok", "zu wenige Referenztage"]},
                       index=pd.Index([1, 2], name="meter"))
    alarme = pd.DataFrame({
        "meter": [1, 1], "kanal": ["kwh_pro_m3", "log_volumen"],
        "datum": pd.to_datetime(["2024-01-05", "2024-02-01"]),
        "richtung": [-1, 1], "beginn": pd.to_datetime(["2024-01-01", "2024-01-20"])})
    s = tm.stationsstand(1, ref, alarme)
    assert s["tm_status"] == "ok"
    assert s["tm_alarme"] == 2
    assert s["tm_letzter_alarm"] == pd.Timestamp("2024-02-01")
    assert s["tm_letzter_kanal"] == "log_volumen"
    assert s["tm_letzte_richtung"] == 1
    s = tm.stationsstand(2, ref, alarme.iloc[:0])
    assert s["tm_status"] == "zu wenige Referenztage"
    assert s["tm_alarme"] == 0
    s = tm.stationsstand(3, ref, alarme)
    assert s["tm_status"] == tm.KEINE_HEIZTAGE


def test_tageswerte_ohne_zaehlerstaende():
    s = stundenreihe(tage=2).drop(columns=["energy", "volume"])
    t = tm.tageswerte(s)
    assert len(t) == 2
    assert t["energie_kwh"].isna().all()


def test_norm_aktuell_nimmt_juengsten_winter():
    n = pd.DataFrame({"meter": [1, 1, 1], "winter": ["22/23", "23/24", "24/25"],
                      "abstand_k": [1.0, 2.0, np.nan]})
    a = tm.norm_aktuell(n)
    assert a.loc[1, "winter"] == "23/24"
