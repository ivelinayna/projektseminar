import os
import time
import warnings

import numpy as np
import pandas as pd
import pytest

from src import nb00_daten as nb00
from src import ternaer as tn

SCHEMA = list(nb00.SPALTEN_MAP)


def _nb00_datei(pfad, start="2024-01-01", stunden=6, leer=(2,)):
    #wie NB 00: lueckenloses Raster, nicht gemessene Stunden als NaN-Zeile
    ts = pd.date_range(start, periods=stunden, freq="h")
    df = pd.DataFrame({"Timestamp": ts})
    for i, sp in enumerate(SCHEMA):
        df[sp] = np.arange(stunden, dtype=float) + i
    df.loc[list(leer), SCHEMA] = np.nan
    df.to_csv(pfad, index=False)
    return df


@pytest.fixture
def ablage(tmp_path):
    raw = tmp_path / "data" / "raw"
    meter = tmp_path / "data" / "processed" / "real_meters"
    raw.mkdir(parents=True)
    meter.mkdir(parents=True)
    return raw, meter


def test_fehlende_ausgabe_nennt_notebook_00(ablage):
    raw, meter = ablage
    with pytest.raises(FileNotFoundError, match="00_eda_hast_stationsprofile"):
        nb00.lade_serien(meter)


def test_leere_rasterzeilen_fallen_heraus_maskierte_werte_bleiben(ablage):
    raw, meter = ablage
    _nb00_datei(meter / "111.csv")
    df = pd.read_csv(meter / "111.csv")
    df.loc[4, "Volume flow (l/h)"] = np.nan
    df.to_csv(meter / "111.csv", index=False)

    s = nb00.lade_serien(meter)[111]
    assert len(s) == 5
    assert pd.Timestamp("2024-01-01 02:00") not in s.index
    assert np.isnan(s.loc[pd.Timestamp("2024-01-01 04:00"), "flow"])
    assert list(s.columns) == nb00.MESSSPALTEN

    roh = nb00.lade_serien(meter, leere_stunden_entfernen=False)[111]
    assert len(roh) == 6


def test_ternaer_lade_serien_nutzt_denselben_weg(ablage):
    raw, meter = ablage
    _nb00_datei(meter / "111.csv")
    _nb00_datei(meter / "222.csv")
    a = tn.lade_serien(meter, zaehler=[222])
    assert list(a) == [222]
    pd.testing.assert_frame_equal(a[222], nb00.lade_serien(meter)[222])


def test_warnung_wenn_rohdaten_neuer_als_nb00(ablage):
    raw, meter = ablage
    _nb00_datei(meter / "111.csv")
    alt = time.time() - 3600
    os.utime(meter / "111.csv", (alt, alt))
    (raw / "111_2025n.csv").write_text("x", encoding="utf-8")
    with pytest.warns(UserWarning, match="erneut ausführen"):
        nb00.pruefe_ausgabe(meter)


def test_keine_warnung_bei_aktueller_ausgabe(ablage):
    raw, meter = ablage
    (raw / "111_2025n.csv").write_text("x", encoding="utf-8")
    alt = time.time() - 3600
    os.utime(raw / "111_2025n.csv", (alt, alt))
    _nb00_datei(meter / "111.csv")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert nb00.pruefe_ausgabe(meter) == 1


def test_nicht_aufbereitet_listet_uebersprungene_zaehler(ablage):
    raw, meter = ablage
    (raw / "111__n.csv").write_text("x", encoding="utf-8")
    (raw / "333_2025n.csv").write_text("x", encoding="utf-8")
    (raw / "Nodes_Edges.ods").write_text("x", encoding="utf-8")
    _nb00_datei(meter / "111.csv")
    tab = nb00.nicht_aufbereitet(meter)
    assert tab["meter"].tolist() == [333]


def test_lange_reihen_findet_nachlieferung():
    def serie(ende):
        return pd.DataFrame({"power": [1.0]}, index=[pd.Timestamp(ende)])
    serien = {1: serie("2025-07-11"), 2: serie("2025-07-11"),
              3: serie("2025-07-10"), 4: serie("2026-07-20")}
    assert nb00.lange_reihen(serien) == [4]


def test_zaehlerstaende_integrieren_ergaenzt_nur_luecken():
    idx = pd.date_range("2024-01-01", periods=4, freq="h")
    s = pd.DataFrame({"energy": [10.0, 12.0, np.nan, np.nan],
                      "volume": [1.0, 1.1, np.nan, np.nan],
                      "power": [2.0, 2.0, 3.0, 4.0],
                      "flow": [100.0, 100.0, 200.0, 300.0],
                      "dt": 20.0, "vl": 70.0, "rt": 50.0}, index=idx)
    out = nb00.zaehlerstaende_integrieren(s)
    assert out["energy"].tolist() == [10.0, 12.0, 15.0, 19.0]
    assert out["volume"].round(3).tolist() == [1.0, 1.1, 1.3, 1.6]
    assert out["zaehlerstand_integriert"].tolist() == [False, False, True, True]
    assert isinstance(out.index, pd.DatetimeIndex)


def test_lade_serien_ergaenzt_nur_wo_leistung_gemessen(ablage):
    raw, meter = ablage
    df = _nb00_datei(meter / "111.csv", stunden=6, leer=())
    df.loc[3:4, ["Energy (kWh)", "Volume (m³)"]] = np.nan
    df.loc[4, ["Power (kW)", "Volume flow (l/h)"]] = np.nan
    df.to_csv(meter / "111.csv", index=False)

    s = nb00.lade_serien(meter)[111]
    assert s.attrs["zaehlerstand_integriert"] == 1
    assert s.loc[pd.Timestamp("2024-01-01 03:00"), "energy"] == 2.0 + 5.0
    assert np.isnan(s.loc[pd.Timestamp("2024-01-01 04:00"), "energy"])
    assert s.loc[pd.Timestamp("2024-01-01 05:00"), "energy"] == 5.0
    assert "zaehlerstand_integriert" not in s.columns

    ohne = nb00.lade_serien(meter, zaehlerstaende_ergaenzen=False)[111]
    assert np.isnan(ohne.loc[pd.Timestamp("2024-01-01 03:00"), "energy"])


def test_stationsfeatures_ergaenzt_nachlieferung_sonst_wie_features(ablage):
    from src import features as ft

    raw, meter = ablage
    _nb00_datei(meter / "111.csv", stunden=48, leer=())
    #222: leere Anfangszeile und Energie/Volumen am Ende nur als Momentanwert
    df = _nb00_datei(meter / "222.csv", stunden=48, leer=(0,))
    df.loc[40:, ["Energy (kWh)", "Volume (m³)"]] = np.nan
    df.to_csv(meter / "222.csv", index=False)

    alt = ft.features_for_directory(meter).set_index("Zählernummer")
    neu = nb00.stationsfeatures(meter).set_index("Zählernummer")
    spalten = [c for c in alt.columns if c != "address"]

    pd.testing.assert_series_equal(alt.loc[111, spalten], neu.loc[111, spalten])
    assert np.isnan(alt.loc[222, "energy_kwh_year"])
    assert np.isfinite(neu.loc[222, "energy_kwh_year"])
    assert np.isfinite(neu.loc[222, "volume_m3_year"])
    assert np.isfinite(neu.loc[222, "full_load_hours"])
