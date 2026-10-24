"""Prognose-LSTM-Wächter (src/prognose_waechter.py): Logik ohne Netz und ohne Rohdaten."""

import numpy as np
import pandas as pd
import pytest

from src import prognose_waechter as pw


def stunden(tage=12, zaehler=(1,), luecke_tag=None, aussen=5.0):
    zeilen = []
    for z in zaehler:
        idx = pd.date_range("2024-01-01", periods=24 * tage, freq="h")
        df = pd.DataFrame({"zaehler": z, "timestamp": idx, "ruecklauf": 40.0, "durchfluss": 100.0,
                           "vorlauf": 70.0, "aussen": aussen})
        if luecke_tag is not None and z == zaehler[0]:
            df.loc[df["timestamp"].dt.normalize() == pd.Timestamp("2024-01-01") + pd.Timedelta(days=luecke_tag),
                   "ruecklauf"] = np.nan
        zeilen.append(df)
    return pd.concat(zeilen, ignore_index=True)


def test_tagesfeld_und_vorgeschichte():
    werte, tage = pw.tagesfeld(stunden(tage=12, zaehler=(1, 2), luecke_tag=3))
    assert werte.shape == (2 * 12 - 1, 24, 4)
    t1 = tage[tage["zaehler"] == 1]
    #Tag 3 fehlt bei Zähler 1: erst ab Tag 11 gibt es wieder 7 lückenlose Vortage
    assert t1["mit_vorgeschichte"].sum() == 1
    assert tage[tage["zaehler"] == 2]["mit_vorgeschichte"].sum() == 5
    assert tage["heiztag"].all()


def test_wochenmittel_ist_mittel_der_vortage():
    werte = np.zeros((10, 24, 4), dtype=np.float32)
    werte[:, :, pw.RL] = np.arange(10)[:, None]
    rl, fl = pw.wochenmittel(werte, np.array([8]))
    assert rl[0, 0] == pytest.approx(np.mean(np.arange(1, 8)))


def abw_tabelle(z_rl, z_fluss=None, start="2024-01-01"):
    n = len(z_rl)
    return pd.DataFrame({"zaehler": 1, "tag": pd.date_range(start, periods=n, freq="D"),
                         "heiztag": True, "z_rl": z_rl,
                         "z_fluss": np.zeros(n) if z_fluss is None else z_fluss})


def test_warnung_braucht_zwei_tage_und_alarm_ruhe():
    z = np.array([0, 5, 0, 5, 5, 5, 0, 0, 5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 5, 5], dtype=float)
    a = abw_tabelle(z)
    w = pw.warnungen(a, 4)
    assert list(np.flatnonzero(w)) == [4, 5, 9, 19]
    alarm = pw.alarme_aus_warnungen(a, w, ruhe=7)
    #Tag 9 liegt nur 4 Tage nach der letzten Warnung, Tag 19 zehn Tage danach
    assert list(np.flatnonzero(alarm)) == [4, 19]


def test_warnung_nicht_ueber_luecken():
    a = abw_tabelle(np.array([5, 5.0]))
    a.loc[1, "tag"] = a.loc[0, "tag"] + pd.Timedelta(days=3)
    assert not pw.warnungen(a, 4).any()


def test_cusum_sammelt_kleine_verschiebung():
    z = np.r_[np.zeros(20), np.full(20, 1.0)]
    a = abw_tabelle(z)
    kal = pd.DataFrame({"phi_rl": [0.0], "phi_fluss": [0.0]}, index=[1])
    c = pw.cusum_alarme(a, kal, k=0.5, h=5)
    tag = np.flatnonzero(c["cusum_alarm"].to_numpy())
    assert len(tag) == 1 and 30 <= tag[0] <= 32, "eine Verschiebung um 1 Streuung meldet nach etwa 11 Tagen"
    assert not pw.warnungen(a, 4).any(), "die Schwellenregel sieht sie nicht"
    #mit Ähnlichkeit der Folgetage dauert es länger
    kal_phi = pd.DataFrame({"phi_rl": [0.5], "phi_fluss": [0.0]}, index=[1])
    c2 = pw.cusum_alarme(a, kal_phi, k=0.5, h=5)
    assert not c2["cusum_alarm"].any() or np.flatnonzero(c2["cusum_alarm"].to_numpy())[0] > tag[0]


def test_kalibrieren_wie_notebook_21():
    rng = np.random.default_rng(0)
    n = 40
    val = pd.DataFrame({"zaehler": np.repeat([1, 2], n), "tag": np.tile(pd.date_range("2024-01-01", periods=n), 2),
                        "heiztag": np.tile(np.arange(n) % 2 == 0, 2),
                        "res_rl": rng.normal(1.0, 2.0, 2 * n), "res_fluss_nacht": rng.normal(0, 1.0, 2 * n)})
    kal, faktor = pw.kalibrieren(val)
    assert set(kal.index) == {1, 2}
    assert (kal["fl_mad"] >= pw.MIN_FL_MAD).all(), "Untergrenze 5 l/h"
    assert kal.loc[1, "rl_mitte"] == pytest.approx(val[val["zaehler"] == 1]["res_rl"].median())
    assert set(faktor.index) == {True, False} and (faktor >= pw.MIN_FAKTOR).all().all()
    assert ((kal["phi_rl"] >= 0) & (kal["phi_rl"] <= pw.PHI_MAX)).all()
    zu_wenig = val[val["tag"] < "2024-01-06"]
    kal2, _ = pw.kalibrieren(zu_wenig)
    assert kal2.empty, "weniger als 10 Validierungstage: keine Kalibrierung"
