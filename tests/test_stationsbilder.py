"""
Tests fuer src.stationsbilder.

Die drei Darstellungen sollen dieselbe Station zeigen wie das
Ternaerdiagramm, nur ohne dessen Normierung. Deshalb steht hier an
erster Stelle die Identitaet zwischen der Kennliniensteigung und dem
Durchflussanteil aus der Modulationszerlegung: faellt sie, sind die
Bilder nicht mehr vergleichbar und einer der beiden Wege rechnet falsch.
Dazu die Stellen, an denen die Darstellung still kippen kann - das
Isoliniengitter, die Luecken im Tag-Stunde-Raster und die
Anteilsachse der Dauerlinie.

Laeuft ohne Rohdaten und ohne Netz:

    python -m pytest tests/test_stationsbilder.py
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from src import season as sn
from src import stationsbilder as sb
from src import ternaer as tn


def _reihe(stunden: int = 24 * 60, start: str = "2024-01-01",
           flow: float = 400.0, dt: float = 20.0,
           rt: float = 50.0) -> pd.DataFrame:
    """Reihe, bei der Leistung, Spreizung und Zaehlerstaende zusammenpassen."""
    idx = pd.date_range(start, periods=stunden, freq="h")
    flow = np.broadcast_to(np.asarray(flow, dtype=float), (stunden,)).copy()
    dt = np.broadcast_to(np.asarray(dt, dtype=float), (stunden,)).copy()
    rt = np.broadcast_to(np.asarray(rt, dtype=float), (stunden,)).copy()
    power = tn.KWH_PRO_M3_K * flow / 1000.0 * dt
    volumen = flow / 1000.0
    return pd.DataFrame({
        "energy": np.concatenate([[0.0], np.cumsum(power)[:-1]]),
        "volume": np.concatenate([[0.0], np.cumsum(volumen)[:-1]]),
        "flow": flow,
        "power": power,
        "dt": dt,
        "vl": rt + dt,
        "rt": rt,
    }, index=idx)


def test_steigung_ist_der_durchflussanteil_aus_dem_ternaerdiagramm():
    #cov(logP, logV) / var(logP) ist zugleich die Steigung der Regression
    #von logV auf logP. Beide Module muessen dieselbe Zahl liefern, sonst
    #zeigen Dreieck und Kennlinie verschiedene Stationen.
    rng = np.random.default_rng(7)
    n = 24 * 60
    flow = np.exp(rng.normal(np.log(300.0), 0.6, n))
    dt = np.exp(rng.normal(np.log(18.0), 0.3, n))
    tab = sb.punkttabelle(_reihe(n, flow=flow, dt=dt), 1)
    assert sb.kennlinienfit(tab)["steigung"] == pytest.approx(
        tn.modulationszerlegung(tab)["anteil_mod_flow"], abs=1e-9)


def test_reine_durchflussmodulation_ergibt_steigung_eins():
    #konstante Spreizung, nur der Volumenstrom bewegt sich
    flow = np.linspace(80.0, 900.0, 24 * 60)
    tab = sb.punkttabelle(_reihe(flow=flow, dt=20.0), 1)
    fit = sb.kennlinienfit(tab)
    assert fit["steigung"] == pytest.approx(1.0, abs=1e-6)
    assert fit["r2"] == pytest.approx(1.0, abs=1e-6)
    assert fit["residuum_sd"] == pytest.approx(0.0, abs=1e-6)
    assert fit["dt_median_k"] == pytest.approx(20.0, abs=1e-6)


def test_konstanter_volumenstrom_ergibt_steigung_null():
    #der Fall des festsitzenden Ventils: Last aendert sich, Durchfluss nicht
    tab = sb.punkttabelle(_reihe(flow=400.0,
                                 dt=np.linspace(4.0, 40.0, 24 * 60)), 1)
    fit = sb.kennlinienfit(tab)
    assert fit["steigung"] == pytest.approx(0.0, abs=1e-6)
    assert fit["n"] > sb.MIN_PUNKTE


def test_fit_bleibt_leer_unter_der_mindestpunktzahl():
    tab = sb.punkttabelle(_reihe(40), 1)
    fit = sb.kennlinienfit(tab.head(10))
    assert fit["n"] == 10
    assert np.isnan(fit["steigung"])
    assert np.isnan(fit["r2"])


def test_isolinie_trifft_die_gemessene_spreizung():
    #die im Bild gezeichneten Geraden V = P * 1000 / (c * dT) muessen die
    #Punktwolke genau dort schneiden, wo die Station diese Spreizung faehrt
    tab = sb.punkttabelle(_reihe(flow=np.linspace(100.0, 800.0, 24 * 60),
                                 dt=30.0), 1)
    erwartet = tab["power_kw"] * 1000.0 / (sb.KWH_PRO_M3_K * 30.0)
    assert np.allclose(tab["flow_lh"], erwartet, rtol=1e-6)


def test_punkttabelle_traegt_den_ruecklauf_nach():
    df = _reihe(rt=np.linspace(35.0, 65.0, 24 * 60))
    stunde = sb.punkttabelle(df, 1, aufloesung="stunde")
    tag = sb.punkttabelle(df, 1, aufloesung="tag")
    assert "rt_c" in stunde.columns and "rt_c" in tag.columns
    assert stunde["rt_c"].notna().all()
    assert tag["rt_c"].between(35.0, 65.0).all()


def test_carpetmatrix_hat_24_zeilen_und_lueckenlose_tage():
    df = _reihe(24 * 30)
    gitter = sb.carpetmatrix(df, "rt")
    assert list(gitter.index) == list(range(24))
    assert gitter.shape[1] == 30
    assert (gitter.columns.to_series().diff().dropna()
            == pd.Timedelta(days=1)).all()


def test_carpetmatrix_laesst_fehlende_stunden_leer():
    #Stillstand ist hier Information, keine Zeile zum Wegwerfen
    df = _reihe(24 * 30)
    df = df.drop(df.index[(df.index.hour == 3)])
    gitter = sb.carpetmatrix(df, "rt")
    assert gitter.loc[3].isna().all()
    assert gitter.loc[4].notna().any()
    assert gitter.shape[1] == 30


def test_carpetmatrix_haelt_die_luecke_zwischen_zwei_messphasen():
    frueh = _reihe(24 * 5, start="2024-01-01")
    spaet = _reihe(24 * 5, start="2024-03-01")
    gitter = sb.carpetmatrix(pd.concat([frueh, spaet]), "rt")
    assert gitter.shape[1] == 65
    assert gitter["2024-02-01"].isna().all()


def test_nachtabsenkung_folgt_dem_eingebauten_tagesgang():
    n = 24 * 60
    idx = pd.date_range("2024-01-01", periods=n, freq="h")
    #tagsueber 60 Grad, nachts 48, also zwoelf Kelvin Unterschied
    rt = np.where(np.isin(idx.hour, sb.TAG_STUNDEN), 60.0, 48.0)
    kennzahl = sb.carpetkennzahlen(_reihe(n, rt=rt), meter=1)
    assert kennzahl["nachtabsenkung_k"] == pytest.approx(12.0, abs=1e-6)
    assert kennzahl["n_stunden"] == n
    assert kennzahl["stillstand_anteil"] == pytest.approx(0.0)


def test_sommernachtanteil_zaehlt_nur_sommernaechte():
    #durchgehender Durchfluss im Januar, im Juli nur tagsueber
    jan = _reihe(24 * 31, start="2024-01-01", flow=400.0)
    jul = _reihe(24 * 31, start="2024-07-01", flow=400.0)
    nacht = np.isin(pd.DatetimeIndex(jul.index).hour, sb.NACHT_STUNDEN)
    jul.loc[nacht, ["flow", "power"]] = 0.0
    kennzahl = sb.carpetkennzahlen(pd.concat([jan, jul]), meter=1)
    assert sn.season_of_month(7) == sn.SOMMER
    assert kennzahl["sommer_nacht_anteil"] == pytest.approx(0.0)


def test_dauerlinie_faellt_monoton_und_deckt_die_volle_zeit_ab():
    anteil, sortiert = sb.dauerlinie([3.0, 1.0, np.nan, 2.0, 5.0])
    assert list(sortiert) == [5.0, 3.0, 2.0, 1.0]
    assert anteil[0] == pytest.approx(25.0)
    assert anteil[-1] == pytest.approx(100.0)
    assert (np.diff(sortiert) <= 0).all()


def test_dauerlinie_vertraegt_leere_eingaben():
    anteil, sortiert = sb.dauerlinie([])
    assert len(anteil) == 0 and len(sortiert) == 0


def test_dauerlinienkennzahlen_zaehlen_die_ueberschreitung():
    #drei Viertel der Stunden ueber der Schwelle
    n = 24 * 60
    rt = np.where(np.arange(n) % 4 == 0, 40.0, 60.0)
    tab = sb.punkttabelle(_reihe(n, rt=rt), 1)
    zahlen = sb.dauerlinienkennzahlen(tab, "gruppe_saison",
                                      [tn.GRUPPE_WINTER], meter=1)
    zeile = zahlen.iloc[0]
    assert zeile["ueber_schwelle_anteil"] == pytest.approx(0.75, abs=0.01)
    assert zeile["p10"] == pytest.approx(60.0)
    assert zeile["p90"] == pytest.approx(40.0)
    assert zeile["spanne_p10_p90"] == pytest.approx(20.0)


def test_kennlinienkennzahlen_behalten_das_absolute_niveau():
    #genau die Information, die die Normierung des Dreiecks wegwirft
    tab = sb.punkttabelle(_reihe(flow=400.0,
                                 dt=np.linspace(10.0, 30.0, 24 * 60)), 1)
    zahlen = sb.kennlinienkennzahlen(tab, "gruppe_saison", [tn.GRUPPE_WINTER],
                                     meter=1)
    zeile = zahlen.iloc[0]
    assert zeile["flow_median_lh"] == pytest.approx(400.0, abs=1e-6)
    assert zeile["power_median_kw"] > 0
    assert zeile["n"] == len(tab)


def test_leere_eingaben_liefern_leere_tabellen_statt_fehler():
    leer = pd.DataFrame(columns=["energy", "volume", "flow", "power",
                                 "dt", "vl", "rt"],
                        index=pd.DatetimeIndex([], name="zeit"))
    tab = sb.punkttabelle(leer, 1)
    assert len(tab) == 0 and "rt_c" in tab.columns
    assert sb.kennlinienfit(tab)["n"] == 0
    assert sb.carpetmatrix(leer, "rt").empty
    assert sb.carpetkennzahlen(leer, meter=1)["n_stunden"] == 0
    assert len(sb.kennlinienkennzahlen(tab, "gruppe_saison",
                                       list(sb.SAISONGRUPPEN))) == 3


def test_export_legt_je_station_und_bildart_eine_datei_an(tmp_path):
    serien = {11: _reihe(24 * 40, flow=np.linspace(100.0, 700.0, 24 * 40)),
              12: _reihe(24 * 40, dt=np.linspace(8.0, 32.0, 24 * 40))}
    ergebnis = sb.exportiere(serien, tmp_path,
                             begehungsdatum={11: pd.Timestamp("2024-01-20")})
    for meter in serien:
        assert (tmp_path / "kennlinie" / "stunde" / f"{meter}.png").exists()
        assert (tmp_path / "carpet" / f"{meter}.png").exists()
        assert (tmp_path / "dauerlinie" / f"{meter}.png").exists()
    assert set(ergebnis) == {"kennlinie", "carpet", "dauerlinie"}
    assert len(ergebnis["carpet"]) == 2
    assert set(ergebnis["kennlinie"]["meter"]) == {11, 12}
