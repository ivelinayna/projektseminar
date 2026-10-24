"""
Tests fuer src.zeitreihenmodell (ARIMA/SARIMAX mit scipy).

Nur synthetische Tagesreihen. Die Reihe folgt einer bekannten Kennlinie
(Ruecklauf sinkt mit steigender Aussentemperatur) plus AR(1)-Fehler;
geprueft wird, dass die Schaetzung die Koeffizienten wiederfindet, dass
Luecken keine Fehler ausloesen und dass ein eingebauter Sprung nach dem
Begehungsdatum als positive Abweichung ankommt.

Laeuft mit:

    python -m pytest tests/test_zeitreihenmodell.py
"""

import numpy as np
import pandas as pd
import pytest

from src import zeitreihenmodell as zm


def _tage(n: int = 200, sprung_ab: int = None, sprung: float = 0.0,
          seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2023-11-01", periods=n, freq="D")
    t = 4 + 6 * np.sin(np.arange(n) / 25.0) + rng.normal(0, 1.5, n)
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.6 * e[i - 1] + rng.normal(0, 0.5)
    y = 40.0 - 0.8 * t + e
    if sprung_ab is not None:
        y[sprung_ab:] += sprung
    frame = pd.DataFrame({"y": y, "t_out": t}, index=index)
    frame["t_out_l1"] = frame["t_out"].shift(1)
    return frame


def test_koeffizienten_polynom():
    c = zm._koeffizienten(np.array([0.5]), np.array([0.3]), d=0, s=7)
    assert c[0] == 1.0 and c[1] == -0.5 and c[7] == -0.3 and c[8] == pytest.approx(0.15)
    c1 = zm._koeffizienten(np.array([]), np.array([]), d=1, s=7)
    assert list(c1) == [1.0, -1.0]


def test_fit_findet_kennlinie_und_ar():
    tage = _tage()
    anp = zm.fit(tage, zm.ModellSpec("arx", p=1, exog=("t_out",)))
    assert anp.ok
    assert anp.beta[0] == pytest.approx(40.0, abs=1.5)
    assert anp.beta[1] == pytest.approx(-0.8, abs=0.1)
    assert anp.phi[0] == pytest.approx(0.6, abs=0.15)


def test_fit_mit_luecken_und_zu_wenig_daten():
    tage = _tage()
    tage.loc[tage.index[50:60], "y"] = np.nan
    anp = zm.fit(tage, zm.ModellSpec("arx", p=1, P=1, exog=("t_out",)))
    assert anp.ok and np.isfinite(anp.sigma2)
    kurz = zm.fit(tage.iloc[:6], zm.ModellSpec("arx", p=1, exog=("t_out",)))
    assert not kurz.ok
    assert np.isnan(zm.prognose(kurz, tage.iloc[:6], tage.iloc[6:9])).all()


def test_prognose_ohne_ar_ist_kennlinie():
    tage = _tage()
    spec = zm.ModellSpec("kennlinie", p=0, exog=("t_out",))
    anp = zm.fit(tage.iloc[:100], spec)
    pred = zm.prognose(anp, tage.iloc[:100], tage.iloc[100:110])
    erwartet = anp.beta[0] + anp.beta[1] * tage["t_out"].iloc[100:110].to_numpy()
    np.testing.assert_allclose(pred, erwartet)


def test_arima_mit_differenz_prognostiziert_letzten_wert():
    tage = _tage()
    spec = zm.ModellSpec("arima_010", p=0, d=1, konstante=False)
    anp = zm.fit(tage.iloc[:100], spec)
    pred = zm.prognose(anp, tage.iloc[:100], tage.iloc[100:105])
    np.testing.assert_allclose(pred, tage["y"].iloc[99])


def test_wirkung_begehung_erkennt_sprung():
    tage = _tage(n=200, sprung_ab=101, sprung=6.0)
    spec = zm.ModellSpec("arx", p=1, exog=("t_out",))
    w = zm.wirkung_begehung(tage, tage.index[100], spec)
    assert w is not None
    assert w["abw"] > 3.0
    ohne = zm.wirkung_begehung(_tage(n=200), tage.index[100], spec)
    assert abs(ohne["abw"]) < 2.0


def test_wirkung_begehung_zu_wenig_historie():
    tage = _tage()
    spec = zm.ModellSpec("arx", p=1, exog=("t_out",))
    assert zm.wirkung_begehung(tage, tage.index[10], spec) is None


def test_rollender_vergleich_ueberspringt_begehungsfenster():
    tage = _tage(n=200)
    spec = zm.ModellSpec("kennlinie", p=0, exog=("t_out",))
    alle = zm.rollender_vergleich(tage, [spec])
    gesperrt = zm.rollender_vergleich(tage, [spec], sperrdaten=[tage.index[100]])
    assert set(alle["modell"]) == {"kennlinie", "naiv_7"}
    assert len(gesperrt) < len(alle)
    assert (alle["mae"] >= 0).all()


def test_tagesreihe_maskiert_stillstand_und_sommer():
    idx = pd.date_range("2024-01-01", periods=48, freq="h")
    df = pd.DataFrame({"power": 5.0, "rt": 40.0}, index=idx)
    df.loc[idx[24:], "power"] = 0.0
    t = pd.DataFrame({"timestamp": idx, "t_out": 5.0})
    tage = zm.tagesreihe(df, t)
    assert tage["y"].iloc[0] == pytest.approx(40.0)
    assert np.isnan(tage["y"].iloc[1])
    warm = pd.DataFrame({"timestamp": idx, "t_out": 20.0})
    assert tage.shape[0] == 2
    assert zm.tagesreihe(df, warm)["y"].isna().all()
