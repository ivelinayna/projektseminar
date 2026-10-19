import numpy as np
import pandas as pd
import pytest

from src import luecken as lu


def _reihe(tage=40, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=tage * 24, freq="h")
    h = idx.hour.to_numpy()
    flow = 300 + 200 * np.sin((h - 6) / 24 * 2 * np.pi) + rng.normal(0, 20, len(idx))
    flow = np.clip(flow, 20, None)
    vl = 75 + rng.normal(0, 1, len(idx))
    dt = 25 + 5 * np.cos(h / 24 * 2 * np.pi)
    rt = vl - dt
    power = lu.K_NENN * flow * dt
    energy = 1000 + np.cumsum(power)
    volume = 500 + np.cumsum(flow) / 1000
    return pd.DataFrame({"energy": energy, "flow": flow, "power": power, "dt": dt,
                         "vl": vl, "rt": rt, "volume": volume}, index=idx)


def _mit_luecken(df):
    d = df.copy()
    #Tagesphase an Tag 10: nur 23 Uhr bleibt
    tag = d.index.normalize() == pd.Timestamp("2024-01-11")
    d.loc[tag & (d.index.hour != 23), :] = np.nan
    #kurze Lücke 2 h
    d.iloc[100:102, :] = np.nan
    #einzelner Kanal fehlt
    d.iloc[200, d.columns.get_loc("rt")] = np.nan
    #langer Block ohne Zählerstand rechts -> modelliert
    d.iloc[600:700, :] = np.nan
    d.iloc[700, d.columns.get_loc("energy")] = np.nan
    d.iloc[700, d.columns.get_loc("volume")] = np.nan
    return d


def test_keine_nan_und_gemessenes_unveraendert():
    roh = _reihe()
    d = _mit_luecken(roh)
    g = lu.fuelle_zaehler(d)
    assert len(g) == len(roh)
    assert not g[lu.MOMENT + lu.STAENDE].isna().any().any()
    gem = g["quelle"] == "gemessen"
    pd.testing.assert_frame_equal(g.loc[gem, lu.MOMENT], d.loc[gem[gem].index, lu.MOMENT],
                                  check_freq=False)
    bek = d["energy"].notna()
    np.testing.assert_allclose(g.loc[bek, "energy"], d.loc[bek, "energy"])


def test_quellen():
    g = lu.fuelle_zaehler(_mit_luecken(_reihe()))
    assert (g["quelle"].iloc[100:102] == "interpoliert").all()
    assert g["quelle"].iloc[200] == "ergaenzt"
    tag = (g.index.normalize() == pd.Timestamp("2024-01-11")) & (g.index.hour != 23)
    assert (g.loc[tag, "quelle"] == "bilanziert").all()
    assert (g.loc[tag, "luecke_h"] == 23).all()
    assert (g["quelle"].iloc[600:700] == "modelliert").all()
    assert set(g["quelle"]) <= set(lu.QUELLEN)


def test_bilanz_tagesphase_trifft_zaehlerstand():
    roh = _reihe()
    g = lu.fuelle_zaehler(_mit_luecken(roh))
    t0 = pd.Timestamp("2024-01-10 23:00")
    t1 = pd.Timestamp("2024-01-11 23:00")
    lu_h = g.loc[t0 + pd.Timedelta(hours=1):t1 - pd.Timedelta(hours=1)]
    dE = roh.loc[t1, "energy"] - roh.loc[t0, "energy"]
    rest = g.attrs["rho_e"] * dE - (g.loc[t0, "power"] + g.loc[t1, "power"]) / 2
    assert lu_h["power"].sum() == pytest.approx(rest, rel=1e-6)
    dV = roh.loc[t1, "volume"] - roh.loc[t0, "volume"]
    rest_v = g.attrs["rho_v"] * 1000 * dV - (g.loc[t0, "flow"] + g.loc[t1, "flow"]) / 2
    assert lu_h["flow"].sum() == pytest.approx(rest_v, rel=1e-6)
    #Stände steigen monoton
    assert (g["energy"].diff().dropna() >= -1e-9).all()


def test_physik_konsistent():
    g = lu.fuelle_zaehler(_mit_luecken(_reihe()))
    luecke = g["quelle"].isin(["bilanziert", "modelliert"])
    np.testing.assert_allclose(g.loc[luecke, "dt"], g.loc[luecke, "vl"] - g.loc[luecke, "rt"])
    np.testing.assert_allclose(g.loc[luecke, "power"],
                               g.attrs["k"] * g.loc[luecke, "flow"] * g.loc[luecke, "dt"])
    assert (g.loc[luecke, "dt"] >= 0).all()


def test_kurze_luecke_linear():
    roh = _reihe()
    d = roh.copy()
    d.iloc[50:53, :] = np.nan
    g = lu.fuelle_zaehler(d)
    erw = np.linspace(roh["vl"].iloc[49], roh["vl"].iloc[53], 5)[1:4]
    np.testing.assert_allclose(g["vl"].iloc[50:53], erw)


def test_zaehlertausch_wird_modelliert():
    roh = _reihe()
    d = roh.copy()
    d.iloc[300:320, :] = np.nan
    #neuer Zähler startet wieder bei kleinem Stand
    d.iloc[320:, d.columns.get_loc("energy")] -= 900
    g = lu.fuelle_zaehler(d)
    assert (g["quelle"].iloc[300:320] == "modelliert").all()
    np.testing.assert_allclose(g["energy"].iloc[320:], d["energy"].iloc[320:])


def test_raster_nur_messspanne():
    d = _reihe().reindex(pd.date_range("2023-12-30", "2024-02-15", freq="h"))
    g = lu.fuelle_zaehler(d)
    assert g.index[0] == pd.Timestamp("2024-01-01")
    assert g.index[-1] == _reihe().index[-1]


def test_randstand_vor_messbeginn_wird_bilanziert():
    roh = _reihe()
    d = roh.copy()
    #nur ein Zählerstand am Anfang, danach fünf Tage nichts
    d.iloc[1:120, :] = np.nan
    d.iloc[0, d.columns.get_indexer(lu.MOMENT)] = np.nan
    g = lu.fuelle_zaehler(d)
    assert g.index[0] == roh.index[0]
    assert (g["quelle"].iloc[0:120] == "bilanziert").all()
    assert g["energy"].iloc[0] == pytest.approx(roh["energy"].iloc[0])
    assert g["power"].iloc[0:120].sum() == pytest.approx(
        g.attrs["rho_e"] * (roh["energy"].iloc[120] - roh["energy"].iloc[0])
        - g["power"].iloc[120] / 2, rel=1e-6)


def test_rho_gleicht_systematischen_versatz_aus():
    roh = _reihe()
    #Leistungsanzeige liest 20 % zu hoch, Zählerstand stimmt
    d = roh.copy()
    d["power"] *= 1.2
    rho_e, rho_v = lu.rho_faktoren(d)
    assert rho_e == pytest.approx(1.2, rel=0.01)
    assert rho_v == pytest.approx(1.0, rel=0.01)


def test_holdout_maske_tagesphase():
    d = _reihe()
    m = lu.holdout_maske(d, "tagesphase", np.random.default_rng(0), tage=7)
    assert m.sum() == 7 * 23
    assert (d.index[m].hour != 23).all()
