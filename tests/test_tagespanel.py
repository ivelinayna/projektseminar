"""
Tests fuer src.tagespanel.

Geprueft wird vor allem, dass das Panel nichts still wegfiltert: Tage
mit wenigen Messstunden bleiben in der Tabelle und sind nur markiert.

Laeuft ohne Rohdaten und ohne Netz:

    python -m pytest tests/test_tagespanel.py
"""

import numpy as np
import pandas as pd

from src import tagespanel as tp


def _reihe(tage: int = 3, start: str = "2024-01-01",
           rt: float = 45.0) -> pd.DataFrame:
    stunden = tage * 24
    idx = pd.date_range(start, periods=stunden, freq="h")
    return pd.DataFrame({
        "energy": np.arange(stunden, dtype=float) * 2.0,
        "volume": np.arange(stunden, dtype=float) * 0.1,
        "flow": 200.0,
        "power": 5.0,
        "dt": 20.0,
        "vl": 70.0,
        "rt": rt,
    }, index=idx)


def test_tagesbasis_mittelt_je_tag():
    basis = tp.tagesbasis(_reihe(3))
    assert len(basis) == 3
    assert np.allclose(basis["rt_mean"], 45.0)
    assert np.allclose(basis["last_anteil"], 1.0)
    assert (basis["n_stunden_basis"] == 24).all()


def test_lastfreie_stunden_zaehlen_nicht_als_last():
    df = _reihe(1)
    df.loc[df.index[:12], "power"] = 0.0
    basis = tp.tagesbasis(df)
    assert np.isclose(basis["last_anteil"].iloc[0], 0.5)


def test_zustandsanteile_summieren_auf_eins():
    idx = pd.date_range("2024-01-01", periods=48, freq="h")
    stunden = pd.DataFrame({
        "Zählernummer": [7] * 48,
        "timestamp": idx,
        "cluster": [0] * 12 + [1] * 12 + [2] * 12 + [0] * 12,
    })
    anteile = tp.zustandsanteile(stunden)
    assert len(anteile) == 2
    spalten = [c for c in anteile.columns if c.startswith("anteil_c")]
    assert np.allclose(anteile[spalten].sum(axis=1), 1.0)
    assert (anteile["n_stunden_cluster"] == 24).all()


def test_panel_markiert_duenne_tage_statt_sie_zu_loeschen():
    df = _reihe(2)
    #zweiter Tag nur vier Stunden
    df = pd.concat([df.iloc[:24], df.iloc[24:28]])
    panel = tp.baue_tagespanel({5: df}, min_stunden=20)
    assert len(panel) == 2
    assert list(panel["genug_stunden"]) == [True, False]


def test_panel_fuehrt_zustand_und_witterung_zusammen():
    df = _reihe(3)
    idx = df.index
    stunden = pd.DataFrame({"Zählernummer": 9, "timestamp": idx,
                            "cluster": np.arange(len(idx)) % 2})
    t_out = pd.DataFrame({"timestamp": idx,
                          "t_out": np.linspace(-2.0, 4.0, len(idx))})
    panel = tp.baue_tagespanel({9: df}, stundencluster=stunden, t_out=t_out)
    assert {"anteil_c0", "anteil_c1", "t_out_tag",
            "heizgradstunden"}.issubset(panel.columns)
    assert panel["t_out_tag"].notna().all()
    assert (panel["heizgradstunden"] > 0).all()
    #Saisonspalte kommt aus season.py und ist im Januar Kernwinter
    assert set(panel["season"]) == {"kernwinter"}


def test_panel_ohne_zustand_und_witterung_bleibt_nutzbar():
    panel = tp.baue_tagespanel({1: _reihe(2)})
    assert {"meter", "datum", "rt_mean", "rt_d1_abs_mean"}.issubset(panel.columns)
    assert "t_out_tag" not in panel.columns


def test_panelbilanz_zaehlt_ohne_zu_filtern():
    panel = tp.baue_tagespanel({1: _reihe(3)})
    bilanz = tp.panelbilanz(panel)
    assert bilanz.loc[0, "bedingung"] == "Stationstage gesamt"
    assert bilanz.loc[0, "tage"] == len(panel)


if __name__ == "__main__":
    test_tagesbasis_mittelt_je_tag()
    test_lastfreie_stunden_zaehlen_nicht_als_last()
    test_zustandsanteile_summieren_auf_eins()
    test_panel_markiert_duenne_tage_statt_sie_zu_loeschen()
    test_panel_fuehrt_zustand_und_witterung_zusammen()
    test_panel_ohne_zustand_und_witterung_bleibt_nutzbar()
    test_panelbilanz_zaehlt_ohne_zu_filtern()
    print("alle Tagespaneltests bestanden")
