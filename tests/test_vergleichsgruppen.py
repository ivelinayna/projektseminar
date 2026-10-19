import numpy as np
import pandas as pd
import pytest

from src import netzvergleich as nv
from src import vergleichsgruppen as vg


def _punkte(start="2023-11-20", ende="2024-03-10", leistung=2.0, meter=1):
    zeit = pd.date_range(start, ende, freq="h", inclusive="left")
    return pd.DataFrame({"meter": meter, "zeit": zeit, "power_kw": leistung})


def test_winterenergie_auf_ganzen_kernwinter_hochgerechnet():
    e = vg.winterenergie({1: _punkte()}, min_punkte=10)
    assert list(e["winter"]) == ["23/24"]
    #Dez. bis Feb. 2023/24 sind 91 Tage
    assert e["waermemenge_kwh"].iloc[0] == pytest.approx(2.0 * 91 * 24)
    assert e["mittlere_leistung_kw"].iloc[0] == pytest.approx(2.0)


def test_winterenergie_luecken_zaehlen_nicht_als_wenig_verbrauch():
    p = _punkte()
    voll = vg.winterenergie({1: p}, min_punkte=10)
    halb = vg.winterenergie({1: p.iloc[::2]}, min_punkte=10)
    assert halb["waermemenge_kwh"].iloc[0] == pytest.approx(
        voll["waermemenge_kwh"].iloc[0])
    assert halb["n_punkte"].iloc[0] < voll["n_punkte"].iloc[0]


def test_winterenergie_zu_wenig_punkte_und_leer():
    e = vg.winterenergie({1: _punkte().iloc[:5], 2: None}, min_punkte=10)
    assert len(e) == 0
    assert list(e.columns) == vg.ENERGIE_SPALTEN


def _tabelle(n=30, winter="23/24"):
    rng = np.random.default_rng(1)
    klein = np.arange(n) < n // 2
    tab = pd.DataFrame({
        "meter": np.arange(1, n + 1), "winter": winter,
        #kleine Stationen um 10 K, große um 30 K
        "spreizung_ref_k": np.where(klein, 10.0, 30.0) + rng.normal(0, 1, n)})
    energie = pd.DataFrame({"meter": tab["meter"], "winter": winter,
                            "waermemenge_kwh": np.where(klein, 1e4, 1e5)
                            * rng.uniform(0.9, 1.1, n)})
    return tab, energie


def test_gruppenbezug_vergleicht_mit_aehnlichem_verbrauch():
    tab, energie = _tabelle()
    #eine große Station mit 20 K ist im Netz Mittelmaß, unter Großen schlecht
    tab.loc[tab["meter"] == 30, "spreizung_ref_k"] = 20.0
    kz = {"spreizung_ref_k": -1}
    netz = nv.netzbezug(tab, kennzahlen=kz)
    gruppe = vg.gruppenbezug(tab, energie, k=10, kennzahlen=kz)
    z_netz = netz.set_index("meter").loc[30, "z_spreizung_ref_k"]
    z_gruppe = gruppe.set_index("meter").loc[30, "z_spreizung_ref_k"]
    assert abs(z_netz) < 1.0
    assert z_gruppe > 3.0
    assert (gruppe["bezug"] == "gruppe").all()
    assert (gruppe["gruppe_n"] == 10).all()
    #Gruppe der großen Station enthält nur große Stationen
    assert gruppe.set_index("meter").loc[30, "gruppe_faktor"] < 1.5


def test_gruppenbezug_ohne_energie_faellt_auf_netz_zurueck():
    tab, energie = _tabelle()
    energie = energie[energie["meter"] != 5]
    kz = {"spreizung_ref_k": -1}
    netz = nv.netzbezug(tab, kennzahlen=kz).set_index("meter")
    gruppe = vg.gruppenbezug(tab, energie, k=10, kennzahlen=kz).set_index("meter")
    assert gruppe.loc[5, "bezug"] == "netz"
    assert gruppe.loc[5, "z_spreizung_ref_k"] == pytest.approx(
        netz.loc[5, "z_spreizung_ref_k"])


def test_gruppenbezug_ohne_referenzausschluss_und_kleiner_winter():
    tab, energie = _tabelle()
    klein_tab, klein_e = _tabelle(n=6, winter="22/23")
    tab = pd.concat([tab, klein_tab], ignore_index=True)
    energie = pd.concat([energie, klein_e], ignore_index=True)
    kz = {"spreizung_ref_k": -1}
    g = vg.gruppenbezug(tab, energie, k=10, kennzahlen=kz,
                        referenz_ausschluss=(30,))
    assert (g.loc[g["winter"] == "22/23", "bezug"] == "zu_klein").all()
    assert g.loc[g["winter"] == "22/23", "z_spreizung_ref_k"].isna().all()
    #Station 30 bekommt einen z-Wert, steht aber in keiner Gruppe
    w = g[g["winter"] == "23/24"].set_index("meter")
    assert np.isfinite(w.loc[30, "z_spreizung_ref_k"])
    assert not w.loc[30, "in_referenz"]


def test_vergleiche_jaccard_neu_weg():
    netz = pd.DataFrame({"meter": [1, 2, 3, 4], "winter": "23/24",
                         "score": [3.0, 2.0, 1.0, 0.0],
                         "auffaellig": [True, True, False, False]})
    gruppe = netz.assign(score=[3.0, 1.0, 2.0, 0.0],
                         auffaellig=[True, False, True, False])
    v = vg.vergleiche(netz, gruppe).iloc[0]
    assert v["auffaellig_netz"] == 2 and v["auffaellig_gruppe"] == 2
    assert v["beide"] == 1
    assert v["jaccard"] == pytest.approx(1 / 3)
    assert v["neu"] == [3] and v["weg"] == [2]
    assert v["spearman"] == pytest.approx(0.8)
