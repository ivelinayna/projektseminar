"""Tests für den Kennlinienmonitor."""

import numpy as np
import pandas as pd
import pytest

from src import kennlinien_monitor as km
from src import stationsbilder as sb


def _rohdaten(start="2023-01-01", stunden=24 * 60, steigung=1.0,
              achsenabschnitt=1.5, rauschen=0.0, seed=0):
    """Rohdatenrahmen, wie ihn `monitor_station` erwartet.

    Zeitindex, Spalten wie in den Zähler-CSV. Die Leistung bleibt klar
    über der Lastschwelle, damit der Filter in `ternaer.stundenwerte`
    nichts wegwirft.
    """
    rng = np.random.default_rng(seed)
    zeit = pd.date_range(start, periods=stunden, freq="h")
    power = np.exp(rng.uniform(np.log(3.0), np.log(30.0), size=stunden))
    lf = achsenabschnitt + steigung * np.log(power)
    if rauschen:
        lf = lf + rng.normal(0.0, rauschen, size=stunden)
    return pd.DataFrame({"power": power, "flow": np.exp(lf),
                         "dt": np.full(stunden, 20.0),
                         "vl": np.full(stunden, 60.0),
                         "rt": np.full(stunden, 40.0)}, index=zeit)


def _punkte(start="2023-01-01", stunden=24 * 60, steigung=1.0,
            achsenabschnitt=1.5, rauschen=0.0, seed=0):
    """Synthetische Punkttabelle, die exakt auf einer Kennlinie liegt."""
    rng = np.random.default_rng(seed)
    zeit = pd.date_range(start, periods=stunden, freq="h")
    power = np.exp(rng.uniform(np.log(1.0), np.log(20.0), size=stunden))
    lf = achsenabschnitt + steigung * np.log(power)
    if rauschen:
        lf = lf + rng.normal(0.0, rauschen, size=stunden)
    flow = np.exp(lf)
    return pd.DataFrame({"zeit": zeit, "datum": zeit.normalize(),
                         "power_kw": power, "flow_lh": flow,
                         "dt_k": np.full(stunden, 20.0),
                         "rt_c": np.full(stunden, 40.0)})


def test_fit_wie_stationsbilder():
    tab = _punkte(stunden=500, steigung=0.8, rauschen=0.2, seed=1)
    arr = km._arrays(tab)
    eigen = km._fit(arr["lp"], arr["lf"], km.MIN_PUNKTE)
    fremd = sb.kennlinienfit(tab)
    for schluessel in ("steigung", "achsenabschnitt", "r2", "residuum_sd"):
        assert eigen[schluessel] == pytest.approx(fremd[schluessel], rel=1e-9)
    assert eigen["n"] == fremd["n"]


def test_fit_findet_die_vorgegebene_kennlinie():
    tab = _punkte(stunden=400, steigung=0.73, achsenabschnitt=2.1)
    arr = km._arrays(tab)
    fit = km._fit(arr["lp"], arr["lf"], km.MIN_PUNKTE)
    assert fit["steigung"] == pytest.approx(0.73, abs=1e-9)
    assert fit["achsenabschnitt"] == pytest.approx(2.1, abs=1e-9)
    assert fit["r2"] == pytest.approx(1.0, abs=1e-9)


def test_fit_leer_bei_zu_wenig_punkten():
    tab = _punkte(stunden=10)
    arr = km._arrays(tab)
    fit = km._fit(arr["lp"], arr["lf"], km.MIN_PUNKTE)
    assert fit["n"] == 10
    assert np.isnan(fit["steigung"])


def test_arrays_filtert_stillstand():
    tab = _punkte(stunden=100)
    tab.loc[:19, "flow_lh"] = 0.0
    arr = km._arrays(tab)
    assert len(arr["ordinal"]) == 80
    assert np.all(arr["flow"] > 0)


def test_fensterreihe_hat_lueckenloses_raster():
    tab = _punkte(stunden=24 * 40)
    #zehn Tage in der Mitte komplett herausschneiden
    maske = (tab["datum"] < "2023-01-15") | (tab["datum"] >= "2023-01-25")
    f = km.fensterreihe(tab[maske])
    tage = pd.DatetimeIndex(f["datum"])
    assert (tage.to_series().diff().dropna() == pd.Timedelta("1D")).all()
    assert f["datum"].iloc[-1] == pd.Timestamp("2023-02-09")


def test_fensterreihe_dehnt_bei_duennen_daten():
    """Eine Station mit zwei Betriebsstunden am Tag bekommt trotzdem
    Fits, weil das Fenster gedehnt wird."""
    tab = _punkte(stunden=24 * 60)
    duenn = tab[pd.DatetimeIndex(tab["zeit"]).hour.isin([6, 7])]
    starr = km.fensterreihe(duenn, max_fenster_tage=km.FENSTER_TAGE)
    gedehnt = km.fensterreihe(duenn)
    assert starr["steigung"].notna().sum() == 0
    assert gedehnt["steigung"].notna().sum() > 0
    assert gedehnt["breite_tage"].max() <= km.MAX_FENSTER_TAGE


def test_residuum_null_auf_der_eigenen_kennlinie():
    tab = _punkte(stunden=24 * 30, steigung=0.9, achsenabschnitt=1.2)
    fit = km.referenzfit(tab)
    r = km.stundenresiduum(tab, fit)
    assert np.allclose(r["residuum"].to_numpy(), 0.0, atol=1e-9)


def test_tagesresiduum_laesst_duenne_tage_leer():
    tab = _punkte(stunden=24 * 20, rauschen=0.1)
    fit = km.referenzfit(tab)
    r = km.stundenresiduum(tab, fit)
    #an einem Tag nur zwei Stunden stehen lassen
    tag = pd.Timestamp("2023-01-10")
    behalten = (r["datum"] != tag) | (pd.DatetimeIndex(r["zeit"]).hour < 2)
    tages = km.tagesresiduum(r[behalten], min_stunden=km.MIN_STUNDEN_TAG)
    zeile = tages[tages["datum"] == tag].iloc[0]
    assert zeile["n"] == 2
    assert np.isnan(zeile["residuum_median"])
    assert len(tages) == 20


def test_sprungscore_findet_den_sprung_am_richtigen_tag():
    rng = np.random.default_rng(3)
    reihe = np.concatenate([rng.normal(0.0, 0.05, 120),
                            rng.normal(1.0, 0.05, 120)])
    score = km.sprungscore(reihe)
    assert int(np.nanargmax(np.abs(score))) == pytest.approx(120, abs=2)
    assert np.nanmax(np.abs(score)) > km.ALARM_SCHWELLE


def test_sprungscore_ohne_sprung_bleibt_unter_der_schwelle():
    rng = np.random.default_rng(4)
    score = km.sprungscore(rng.normal(0.0, 0.1, 400))
    assert np.nanmax(np.abs(score)) < 8.0


def test_sprungscore_konstant_liefert_keinen_alarm():
    score = km.sprungscore(np.full(200, 2.5))
    assert not np.isfinite(score).any()


def test_sprungscore_ueberbrueckt_luecken():
    """Liegt der Sprung in einer Datenlücke, zählen die nächstgelegenen
    vorhandenen Werte - sonst wäre der Monitor im Sommer blind."""
    reihe = np.concatenate([np.zeros(60), np.full(40, np.nan),
                            np.ones(60)])
    reihe[:60] += np.random.default_rng(5).normal(0, 0.02, 60)
    score = km.sprungscore(reihe)
    treffer = int(np.nanargmax(np.abs(score)))
    assert 55 <= treffer <= 101


def test_sprungscore_leer():
    assert len(km.sprungscore([])) == 0


def test_alarme_unterdrueckt_nachbarn():
    datum = pd.date_range("2023-01-01", periods=200, freq="D")
    score = np.zeros(200)
    score[50] = 6.0
    score[52] = 5.0
    score[150] = -7.0
    a = km.alarme(datum, score, schwelle=3.0, mindestabstand_tage=30)
    assert list(a["datum"]) == [datum[50], datum[150]]
    assert list(a["richtung"]) == ["hoch", "runter"]


def test_alarme_leer_bei_ruhiger_reihe():
    datum = pd.date_range("2023-01-01", periods=50, freq="D")
    a = km.alarme(datum, np.zeros(50))
    assert len(a) == 0
    assert list(a.columns) == ["datum", "score", "richtung"]


def test_leere_eingabe_liefert_leere_tabellen():
    leer = pd.DataFrame(columns=["zeit", "power_kw", "flow_lh", "dt_k"])
    f = km.fensterreihe(leer)
    assert len(f) == 0 and list(f.columns) == km.FENSTER_SPALTEN
    fit = km.referenzfit(leer)
    assert np.isnan(fit["steigung"])
    assert len(km.stundenresiduum(leer, fit)) == 0
    assert len(km.tagesresiduum(pd.DataFrame(columns=["datum", "residuum"]))) == 0


def test_zufallsbasis_rechnet_die_erwartung():
    alarme = pd.DataFrame({"meter": [1, 1], "quelle": ["parameter"] * 2,
                           "kennzahl": ["steigung"] * 2,
                           "datum": pd.to_datetime(["2023-01-01",
                                                    "2023-06-01"]),
                           "score": [4.0, -4.0], "richtung": ["hoch",
                                                              "runter"]})
    abdeckung = pd.DataFrame([{"meter": 1, "tage": 610}])
    basis = km.zufallsbasis(alarme, abdeckung, {1: [pd.Timestamp("2023-03-01")]},
                            toleranz_tage=30)
    erwartet = 1.0 - (1.0 - 61 / 610) ** 2
    assert basis["erwartete_quote"].iloc[0] == pytest.approx(erwartet)


def test_zufallsbasis_ohne_alarm_ist_null():
    alarme = pd.DataFrame({"meter": [2], "quelle": ["parameter"],
                           "kennzahl": ["steigung"],
                           "datum": pd.to_datetime(["2023-01-01"]),
                           "score": [4.0], "richtung": ["hoch"]})
    abdeckung = pd.DataFrame([{"meter": 1, "tage": 610},
                              {"meter": 2, "tage": 610}])
    basis = km.zufallsbasis(alarme, abdeckung, {1: [pd.Timestamp("2023-03-01")]})
    assert basis["erwartete_quote"].iloc[0] == pytest.approx(0.0)


def test_validiere_zaehlt_stationen_ohne_alarm_mit():
    alarme = pd.DataFrame({"meter": [1], "quelle": ["parameter"],
                           "kennzahl": ["steigung"],
                           "datum": pd.to_datetime(["2023-03-10"]),
                           "score": [5.0], "richtung": ["hoch"]})
    termine = {1: [pd.Timestamp("2023-03-01")],
               2: [pd.Timestamp("2023-03-01")]}
    pruef = km.validiere(alarme, termine, toleranz_tage=30)
    assert len(pruef) == 2
    assert bool(pruef[pruef["meter"] == 1]["treffer"].iloc[0]) is True
    assert bool(pruef[pruef["meter"] == 2]["treffer"].iloc[0]) is False
    quote = km.trefferquote(pruef)
    assert quote["faelle"].iloc[0] == 2
    assert quote["treffer"].iloc[0] == 1


def test_validiere_toleranz_wird_eingehalten():
    alarme = pd.DataFrame({"meter": [1], "quelle": ["parameter"],
                           "kennzahl": ["steigung"],
                           "datum": pd.to_datetime(["2023-04-10"]),
                           "score": [5.0], "richtung": ["hoch"]})
    pruef = km.validiere(alarme, {1: [pd.Timestamp("2023-03-01")]},
                         toleranz_tage=30)
    assert int(pruef["abstand_tage"].iloc[0]) == 40
    assert bool(pruef["treffer"].iloc[0]) is False


def test_monitor_station_auf_synthetischem_sprung():
    """Eine Station, die nach einem halben Jahr ihre Kennlinie wechselt,
    muss genau dort einen Alarm erzeugen."""
    vorher = _rohdaten(start="2023-01-01", stunden=24 * 200, steigung=0.1,
                       achsenabschnitt=6.0, rauschen=0.1, seed=7)
    nachher = _rohdaten(start="2023-07-20", stunden=24 * 200, steigung=1.0,
                        achsenabschnitt=1.5, rauschen=0.1, seed=8)
    df = pd.concat([vorher, nachher])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    e = km.monitor_station(df, 4711)

    assert set(e) == {"fenster", "residuum", "alarme", "abdeckung"}
    assert list(e["fenster"].columns)[0] == "meter"
    assert list(e["residuum"].columns)[0] == "meter"
    assert e["abdeckung"]["meter"].iloc[0] == 4711
    assert (e["alarme"]["meter"] == 4711).all()

    param = e["alarme"][e["alarme"]["quelle"] == km.QUELLE_PARAMETER]
    staerkster = param.loc[param["score"].abs().idxmax(), "datum"]
    assert abs((staerkster - pd.Timestamp("2023-07-20")).days) <= 20


def test_monitor_station_ruhige_station_schlaegt_nicht_an():
    df = _rohdaten(stunden=24 * 400, steigung=0.95, rauschen=0.1, seed=9)
    e = km.monitor_station(df, 4712)
    assert len(e["alarme"]) == 0


def test_monitor_alle_stapelt():
    serien = {1: _rohdaten(stunden=24 * 120, seed=11),
              2: _rohdaten(stunden=24 * 120, seed=12)}
    e = km.monitor_alle(serien)
    assert sorted(e["abdeckung"]["meter"]) == [1, 2]
    assert set(e["fenster"]["meter"]) == {1, 2}


def test_monitor_station_ohne_daten():
    leer = pd.DataFrame(columns=["power", "flow", "dt", "rt"],
                        index=pd.DatetimeIndex([]))
    e = km.monitor_station(leer, 1)
    assert len(e["alarme"]) == 0
    assert list(e["alarme"].columns)[0] == "meter"
    assert e["abdeckung"]["tage"].iloc[0] == 0
