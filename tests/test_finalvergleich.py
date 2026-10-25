"""Tests für src/finalvergleich.py (Notebook 34)."""

import numpy as np
import pandas as pd
import pytest

from src import finalvergleich as fv
from src import prognose_waechter as pw
from src import tagesmonitor as tm


def _serie(tage=40, fluss=300.0, vl=70.0, rt=40.0):
    idx = pd.date_range("2025-01-01", periods=24 * tage, freq="h")
    f = np.full(len(idx), fluss)
    p = fv.KWH_JE_LH_K * f * (vl - rt)
    return pd.DataFrame({"flow": f, "vl": vl, "rt": rt, "dt": vl - rt, "power": p,
                         "energy": np.cumsum(p), "volume": np.cumsum(f / 1000.0)}, index=idx)


def test_bypass_haelt_leistung_und_energie():
    s = _serie()
    g = fv.stoerung_einrechnen(s, "2025-01-10", "bypass", 50.0, tage=10)
    im = (g.index >= "2025-01-10") & (g.index < "2025-01-20")
    assert np.allclose(g.loc[im, "flow"], 350.0)
    assert np.allclose(g.loc[im, "power"], s.loc[im, "power"])
    assert np.allclose(g["energy"], s["energy"])
    #Rücklauf mischt sich mit Vorlaufwasser
    assert np.allclose(g.loc[im, "rt"], (40 * 300 + 70 * 50) / 350)
    #Volumen: 50 l/h über 240 h, danach bleibt der Versatz
    assert g["volume"].iloc[-1] - s["volume"].iloc[-1] == pytest.approx(50 * 240 / 1000)
    assert np.allclose(g.loc[~im & (g.index < "2025-01-10"), "volume"],
                       s.loc[~im & (s.index < "2025-01-10"), "volume"])


def test_ruecklauf_plus_5k_bei_gleicher_leistung():
    s = _serie()
    g = fv.stoerung_einrechnen(s, "2025-01-10", "ruecklauf", 5.0, tage=5)
    im = (g.index >= "2025-01-10") & (g.index < "2025-01-15")
    assert np.allclose(g.loc[im, "rt"], 45.0)
    assert np.allclose(g.loc[im, "flow"], 300 * 30 / 25)
    assert np.allclose(g.loc[im, "power"], s.loc[im, "power"])
    assert g["volume"].iloc[-1] > s["volume"].iloc[-1]


def test_rampe_steigt_langsam():
    s = _serie()
    g = fv.stoerung_einrechnen(s, "2025-01-01", "rampe", 5.0, tage=30)
    anstieg = (g["rt"] - s["rt"]).resample("D").mean()
    assert anstieg.iloc[0] < 0.2
    assert anstieg.iloc[15] == pytest.approx(2.5, abs=0.2)
    assert anstieg.iloc[29] == pytest.approx(5.0, abs=0.2)


def test_hysterese_pendelt_bei_gleicher_tagesmenge():
    s = _serie()
    g = fv.stoerung_einrechnen(s, "2025-01-10", "hysterese", 0.3, tage=5)
    im = (g.index >= "2025-01-10") & (g.index < "2025-01-15")
    assert set(np.round(g.loc[im, "flow"].unique(), 6)) == {210.0, 390.0}
    assert g.loc[im, "flow"].mean() == pytest.approx(300.0)
    assert np.allclose(g.loc[im, "power"], s.loc[im, "power"])


def test_fuehler_haengt():
    s = _serie()
    s.loc["2025-01-10":"2025-01-20", "rt"] = np.linspace(40, 45, len(s.loc["2025-01-10":"2025-01-20"]))
    g = fv.stoerung_einrechnen(s, "2025-01-10", "fuehler", None, tage=5)
    im = (g.index >= "2025-01-10") & (g.index < "2025-01-15")
    assert g.loc[im, "rt"].nunique() == 1
    assert g.loc[im, "rt"].iloc[0] == pytest.approx(40.0)


def test_ohne_ueberschneidung_bleibt_gleich():
    s = _serie()
    g = fv.stoerung_einrechnen(s, "2026-01-01", "bypass", 50.0)
    pd.testing.assert_frame_equal(g, s)


def test_ivelina_alarme_wie_tagesmonitor():
    rng = np.random.default_rng(1)
    z = np.r_[rng.normal(0, 1, 60), rng.normal(2, 1, 30)]
    v = pd.DataFrame({"meter": 1, "kanal": "kwh_pro_m3",
                      "datum": pd.date_range("2024-01-01", periods=len(z)), "z": z})
    a = fv.ivelina_alarme(v, tm.CUSUM_H)
    _, _, ref = tm.cusum(z)
    assert len(a) == len(ref)
    assert list(a["richtung"]) == [r for _, r, _ in ref]


def test_lstm_cusum_wie_prognose_waechter():
    rng = np.random.default_rng(2)
    n = 120
    z = pd.DataFrame({"zaehler": 7, "tag": pd.date_range("2024-02-01", periods=n), "heiztag": True,
                      "z_rl": np.r_[rng.normal(0, 1, 80), rng.normal(3, 1, 40)],
                      "z_fluss": rng.normal(0, 1, n)})
    kal = pd.DataFrame({"phi_rl": [0.2], "phi_fluss": [0.1]}, index=pd.Index([7], name="zaehler"))
    a = fv.lstm_alarme(z, kal, "cusum", 5.0)
    ref = pw.cusum_alarme(z, kal, h=5.0)
    assert len(a) == int(ref["cusum_kanal"].str.count(",").add(1).where(ref["cusum_alarm"], 0).sum())


def test_gleiche_alarmlast_nimmt_naechsten_wert():
    tage = pd.DataFrame({"zaehler": [1] * 10, "datum": pd.date_range("2024-04-01", periods=10)})

    def alarme(w):
        n = int(10 // w)
        return pd.DataFrame({"zaehler": [1] * n, "datum": tage["datum"].iloc[:n].to_numpy()})

    w, tab = fv.gleiche_alarmlast(alarme, [1.0, 2.0, 5.0], 5, tage)
    assert w == 2.0
    assert tab.set_index("wert")["alarme"].to_dict() == {1.0: 10, 2.0: 5, 5.0: 2}


def test_vierfeld_und_auc():
    v = fv.vierfeld([1, 1, 0, 0, 0], [1, 0, 1, 0, 0])
    assert (v["gefunden"], v["übersehen"], v["Fehlalarm"], v["richtig ruhig"]) == (1, 1, 1, 2)
    assert v["Precision"] == pytest.approx(0.5)
    auc, lo, hi = fv.bootstrap_auc([0, 0, 1, 1, 0, 1], [0.1, 0.2, 0.8, 0.9, 0.3, 0.7], n=200)
    assert auc == 1.0 and lo == 1.0


def test_folie5_klassen():
    lab = pd.DataFrame({"ventil": [True, False, False], "durchfluss": [False, True, False],
                        "temperatur": [True, False, False]}, index=[1, 2, 3])
    assert list(fv.folie5_befund(lab)) == [fv.F5_REPARATUR, fv.F5_REGELUNG, fv.F5_KEINE]
    fb = pd.Series(["ventil", "unruhig", ""], index=[1, 2, 3])
    assert list(fv.folie5_ivelina(fb)) == [fv.F5_REPARATUR, fv.F5_REGELUNG, fv.F5_KEINE]
