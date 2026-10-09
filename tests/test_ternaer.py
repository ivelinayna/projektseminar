"""
Tests fuer src.ternaer.

Schwerpunkt sind die drei Stellen, an denen die Darstellung kippen
kann: die Projektion in das Dreieck, die stationseigene Normierung und
die Varianzzerlegung der Leistungsmodulation. Dazu die beiden
Gruppenschnitte, damit der Puffer um den Begehungstag und die
Zusammenfassung der Saisonsegmente nicht stillschweigend verrutschen.

Laeuft ohne Rohdaten und ohne Netz:

    python -m pytest tests/test_ternaer.py
"""

import numpy as np
import pandas as pd

from src import season as sn
from src import ternaer as tn


def _reihe(stunden: int = 24 * 40, start: str = "2024-01-01",
           flow: float = 400.0, dt: float = 20.0) -> pd.DataFrame:
    """Konstante Reihe, bei der Leistung und Zaehlerstaende zusammenpassen."""
    idx = pd.date_range(start, periods=stunden, freq="h")
    flow = np.broadcast_to(np.asarray(flow, dtype=float), (stunden,))
    dt = np.broadcast_to(np.asarray(dt, dtype=float), (stunden,))
    power = tn.KWH_PRO_M3_K * flow / 1000.0 * dt
    volumen = flow / 1000.0
    return pd.DataFrame({
        "energy": np.concatenate([[0.0], np.cumsum(power)[:-1]]),
        "volume": np.concatenate([[0.0], np.cumsum(volumen)[:-1]]),
        "flow": flow,
        "power": power,
        "dt": dt,
        "vl": 50.0 + dt,
        "rt": 50.0,
    }, index=idx)


def test_ecken_werden_auf_die_dreieckspunkte_abgebildet():
    x, y = tn.ternaer_xy([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])
    assert np.allclose(x, [0.0, 1.0, 0.5])
    assert np.allclose(y, [0.0, 0.0, np.sqrt(3.0) / 2.0])


def test_anteile_summieren_sich_zu_eins():
    tab = tn.stundenwerte(_reihe(flow=np.linspace(100.0, 800.0, 24 * 40),
                                 dt=np.linspace(5.0, 30.0, 24 * 40)))
    koord = tn.ternaerkoordinaten(tab)
    summe = koord[tn.ANTEILSSPALTEN].sum(axis=1)
    assert np.allclose(summe.dropna(), 1.0)
    assert koord[tn.ANTEILSSPALTEN].min().min() >= 0.0


def test_normierung_kappt_oberhalb_des_quantils():
    #die obersten 5 Prozent liegen per Definition ueber dem Quantil
    tab = tn.stundenwerte(_reihe(flow=np.linspace(100.0, 800.0, 24 * 40)))
    koord = tn.ternaerkoordinaten(tab, quantil=0.95)
    assert koord["flow_n"].max() == 1.0
    anteil_gekappt = float((koord["flow_n"] >= 1.0).mean())
    assert 0.02 < anteil_gekappt < 0.10


def test_stillstandsstunden_fallen_aus_der_punktwolke():
    df = _reihe(24 * 10)
    df.loc[df.index[:24], ["flow", "power", "dt"]] = 0.0
    tab = tn.stundenwerte(df)
    assert len(tab) == 24 * 10 - 24


def test_modulation_ueber_spreizung_wird_als_solche_erkannt():
    #konstanter Durchfluss, nur die Spreizung bewegt sich
    dt = 10.0 + 10.0 * np.sin(np.linspace(0.0, 20.0, 24 * 40))
    tab = tn.stundenwerte(_reihe(flow=400.0, dt=dt))
    zerlegung = tn.modulationszerlegung(tab)
    assert zerlegung["anteil_mod_dt"] > 0.99
    assert abs(zerlegung["anteil_mod_flow"]) < 0.01
    assert np.isclose(zerlegung["summe_mod"], 1.0, atol=1e-6)


def test_modulation_ueber_volumenstrom_wird_als_solche_erkannt():
    flow = 400.0 + 300.0 * np.sin(np.linspace(0.0, 20.0, 24 * 40))
    tab = tn.stundenwerte(_reihe(flow=flow, dt=20.0))
    zerlegung = tn.modulationszerlegung(tab)
    assert zerlegung["anteil_mod_flow"] > 0.99
    assert np.isclose(zerlegung["summe_mod"], 1.0, atol=1e-6)


def test_modulation_bleibt_bei_zu_wenig_punkten_leer():
    tab = tn.stundenwerte(_reihe(10))
    zerlegung = tn.modulationszerlegung(tab, min_punkte=30)
    assert np.isnan(zerlegung["anteil_mod_dt"])
    assert zerlegung["n"] == 10


def test_tageswerte_erhalten_die_leistungsgleichung():
    tab = tn.tageswerte(_reihe(24 * 10))
    assert len(tab) >= 8
    rechts = tn.KWH_PRO_M3_K * tab["flow_lh"] / 1000.0 * tab["dt_k"]
    assert np.allclose(tab["power_kw"], rechts, rtol=1e-9)


def test_begehungsgruppe_blendet_den_puffer_als_umbauphase_aus():
    tab = tn.tageswerte(_reihe(24 * 40))
    mit = tn.begehungsgruppe(tab, "2024-01-21", puffer_tage=7)
    zaehlung = mit["gruppe_begehung"].value_counts()
    assert zaehlung[tn.GRUPPE_UMBAU] == 15
    assert zaehlung[tn.GRUPPE_VORHER] > 0
    assert zaehlung[tn.GRUPPE_NACHHER] > 0


def test_ohne_begehungsdatum_bleibt_die_gruppe_leer():
    tab = tn.tageswerte(_reihe(24 * 10))
    mit = tn.begehungsgruppe(tab, None)
    assert mit["gruppe_begehung"].isna().all()


def test_saisongruppe_fasst_beide_uebergaenge_zusammen():
    tab = pd.DataFrame({"datum": pd.to_datetime(
        ["2024-01-15", "2024-03-15", "2024-07-15", "2024-10-15"])})
    mit = tn.saisongruppe(tab)
    assert list(mit["gruppe_saison"]) == [
        tn.GRUPPE_WINTER, tn.GRUPPE_UEBERGANG, tn.GRUPPE_SOMMER,
        tn.GRUPPE_UEBERGANG]
    assert sn.UEBERGANG_FRUEH in tn.SEGMENT_AUF_GRUPPE


def test_kennzahlen_behalten_leere_gruppen():
    df = _reihe(24 * 40, start="2024-01-01")
    tab = tn.stationstabelle(df, 4711, aufloesung="tag",
                             begehungsdatum="2024-01-21")
    k = tn.kennzahlen(tab, "gruppe_saison", tn.SAISONGRUPPEN, meter=4711)
    assert list(k["gruppe"]) == tn.SAISONGRUPPEN
    assert int(k.loc[k["gruppe"] == tn.GRUPPE_SOMMER, "n"].iloc[0]) == 0
    assert np.isnan(k.loc[k["gruppe"] == tn.GRUPPE_SOMMER,
                          "streuung"].iloc[0])


def test_stationstabelle_liefert_beide_schnitte():
    tab = tn.stationstabelle(_reihe(24 * 40), 4711, aufloesung="stunde",
                             begehungsdatum="2024-01-21")
    assert {"meter", "gruppe_begehung", "gruppe_saison"} <= set(tab.columns)
    assert (tab["meter"] == 4711).all()


def test_leere_reihe_bricht_nicht_ab():
    leer = pd.DataFrame(columns=["energy", "volume", "flow", "power", "dt"],
                        index=pd.DatetimeIndex([], name="Timestamp"))
    assert len(tn.stundenwerte(leer)) == 0
    assert len(tn.tageswerte(leer)) == 0
