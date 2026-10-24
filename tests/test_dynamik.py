"""
Tests fuer src.dynamik.

Die Kernfrage ist, ob ueber Messluecken hinweg differenziert wird. Eine
Ableitung ueber eine dreitaegige Luecke ist kein Gradient, sondern ein
Mittelwert ueber alles, was dazwischen passiert ist - sie muss NaN
bleiben und darf nicht als 0 durchgehen.

Laeuft ohne Rohdaten und ohne Netz:

    python -m pytest tests/test_dynamik.py
"""

import numpy as np
import pandas as pd

from src import dynamik as dyn


def _reihe(stunden: int = 48, start: str = "2024-01-01") -> pd.DataFrame:
    idx = pd.date_range(start, periods=stunden, freq="h")
    return pd.DataFrame({
        "rt": np.linspace(40.0, 40.0 + 0.5 * (stunden - 1), stunden),
        "vl": 70.0,
        "power": 5.0,
        "flow": 200.0,
        "dt": 25.0,
    }, index=idx)


def test_erste_ableitung_konstanter_anstieg():
    df = _reihe(24)
    abl = dyn.ableitungen(df, ("rt",))
    d1 = abl["rt_d1"].dropna()
    assert len(d1) == 23
    assert np.allclose(d1.to_numpy(), 0.5)
    #zweite Ableitung eines linearen Verlaufs ist null
    assert np.allclose(abl["rt_d2"].dropna().to_numpy(), 0.0, atol=1e-9)


def test_keine_ableitung_ueber_luecke():
    df = _reihe(24)
    #drei Tage Luecke zwischen Stunde 11 und Stunde 12
    idx = list(df.index[:12]) + list(df.index[12:] + pd.Timedelta(days=3))
    df.index = pd.DatetimeIndex(idx)
    abl = dyn.ableitungen(df, ("rt",))
    #die Stelle direkt nach der Luecke hat keine erste Ableitung
    assert np.isnan(abl["rt_d1"].iloc[12])
    #und die darauf folgende keine zweite, weil der Vorgaenger fehlt
    assert np.isnan(abl["rt_d2"].iloc[13])
    assert np.isfinite(abl["rt_d1"].iloc[13])


def test_traeger_ruecklauf_wird_erkannt():
    df = _reihe(24)
    df["rt"] = 55.0   #bewegt sich ueberhaupt nicht
    tag = dyn.tagesdynamik(df)
    assert len(tag) == 1
    assert tag["rt_traege_anteil"].iloc[0] == 1.0
    assert tag["rt_d1_abs_mean"].iloc[0] == 0.0


def test_zu_wenige_stunden_geben_nan():
    df = _reihe(6)
    tag = dyn.tagesdynamik(df, min_stunden=12)
    assert np.isnan(tag["rt_d1_abs_mean"].iloc[0])
    #die Zaehlspalte bleibt stehen, damit der Grund sichtbar ist
    assert tag["n_dyn"].iloc[0] == 5


def test_kopplung_zwischen_vor_und_ruecklauf():
    idx = pd.date_range("2024-01-01", periods=24, freq="h")
    vl = 70.0 + np.sin(np.arange(24) / 3.0)
    df = pd.DataFrame({"rt": 0.8 * vl - 10.0, "vl": vl, "power": 5.0,
                       "flow": 200.0, "dt": 20.0}, index=idx)
    tag = dyn.tagesdynamik(df)
    assert tag["rt_vl_kopplung"].iloc[0] > 0.99


def test_reaktionszeit_folgt_der_zeitkonstante():
    #Sprung in Stunde 10, Ruecklauf naehert sich mit tau = 2 h um 10 K an
    idx = pd.date_range("2024-01-01", periods=36, freq="h")
    power = np.where(np.arange(36) >= 10, 8.0, 0.0)
    rt = np.full(36, 40.0)
    for i in range(10, 36):
        rt[i] = 40.0 + 10.0 * (1 - np.exp(-(i - 9) / 2.0))
    df = pd.DataFrame({"rt": rt, "vl": 70.0, "power": power, "flow": 100.0,
                       "dt": 20.0}, index=idx)
    ereignisse = dyn.lastwechsel(df)
    assert len(ereignisse) == 1
    zeile = ereignisse.iloc[0]
    assert zeile["sprung_kw"] == 8.0
    #63 Prozent der Auslenkung sind nach rund zwei Stunden erreicht
    assert 1.0 <= zeile["reaktionszeit_h"] <= 3.0


def test_luecke_im_reaktionsfenster_wird_uebersprungen():
    idx = list(pd.date_range("2024-01-01", periods=12, freq="h"))
    idx += list(pd.date_range("2024-01-03", periods=6, freq="h"))
    power = np.where(np.arange(18) >= 10, 8.0, 0.0)
    df = pd.DataFrame({"rt": np.linspace(40, 50, 18), "vl": 70.0,
                       "power": power, "flow": 100.0, "dt": 20.0},
                      index=pd.DatetimeIndex(idx))
    ereignisse = dyn.lastwechsel(df)
    assert len(ereignisse) == 1
    assert not bool(ereignisse["vollstaendig"].iloc[0])
    assert np.isnan(ereignisse["reaktionszeit_h"].iloc[0])


def test_tabelle_stapelt_mit_zaehlernummer():
    serien = {11: _reihe(48), 22: _reihe(48)}
    tab = dyn.dynamik_tabelle(serien)
    assert set(tab["meter"]) == {11, 22}
    assert len(tab) == 4


if __name__ == "__main__":
    test_erste_ableitung_konstanter_anstieg()
    test_keine_ableitung_ueber_luecke()
    test_traeger_ruecklauf_wird_erkannt()
    test_zu_wenige_stunden_geben_nan()
    test_kopplung_zwischen_vor_und_ruecklauf()
    test_reaktionszeit_folgt_der_zeitkonstante()
    test_luecke_im_reaktionsfenster_wird_uebersprungen()
    test_tabelle_stapelt_mit_zaehlernummer()
    print("alle Dynamiktests bestanden")
