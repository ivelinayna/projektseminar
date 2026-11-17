"""Tests für src/merkmalsbau.py mit künstlichen Daten, deren Ergebnis bekannt ist."""
import numpy as np
import pandas as pd
import pytest

from src import merkmalsbau as mb


def _stunden(tage=400, start="2023-09-01", grundlast=1.0, steigung=0.5, seed=0):
    """Eine Station: Leistung = Grundlast + Steigung · Heizgrad, Außentemperatur als Jahresgang."""
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start, periods=tage * 24, freq="h")
    tag = (ts - ts[0]).days.to_numpy()
    aussen_tag = 8 - 10 * np.cos(2 * np.pi * (tag - 20) / 365) + rng.normal(0, 2, tage)[tag]
    leistung = grundlast + steigung * np.clip(15 - aussen_tag, 0, None) / 24 * 24 / 24
    return pd.DataFrame({"zaehler": 1, "timestamp": ts, "aussen": aussen_tag,
                         "leistung": leistung, "durchfluss": 10 + 5 * np.clip(15 - aussen_tag, 0, None),
                         "vorlauf": 70.0, "ruecklauf": 40.0, "spreizung": 30.0})


def test_tage_rechnet_energie_und_wirft_fehlwerte_raus():
    s = _stunden(tage=3)
    s.loc[0, "durchfluss"] = -999
    t = mb.tage(s)
    assert len(t) == 3
    assert t["energie_kwh"].iloc[1] == pytest.approx(s["leistung"].iloc[24:48].sum())
    assert t["fluss_mittel"].iloc[0] == pytest.approx(s["durchfluss"].iloc[1:24].mean())


def test_wetter_fit_findet_grundlast_und_steigung():
    t = mb.tage(_stunden(grundlast=2.0, steigung=0.5))
    g, h = mb.wetter_fit(t, "energie_kwh")
    assert g == pytest.approx(48.0, rel=1e-6)
    assert h == pytest.approx(0.5 * 24 / 24, rel=1e-6)
    assert np.allclose(mb.wetter_rest(t, "energie_kwh", (g, h)), 0, atol=1e-8)


def test_wirkung_erkennt_gesunkene_grundlast():
    vor = _stunden(tage=400, start="2023-09-01", grundlast=2.0)
    nach = _stunden(tage=300, start="2024-10-05", grundlast=1.0, seed=1)
    t = mb.tage(pd.concat([vor, nach]))
    datum = pd.Timestamp("2024-09-22")          # nachher beginnt am 06.10., nach dem Wechsel
    w = mb.wirkung_je_station(t, datum)
    basis = mb.fenster(t, datum)[0]["energie_kwh"].mean()
    assert w["d_grundlast_rel"] == pytest.approx(-24.0 / basis, rel=1e-6)
    assert w["d_energie_rel"] < 0


def _winter(tage=120):
    """Nur Heiztage (unter 15 °C), damit der Durchfluss genau linear an der Kälte hängt."""
    s = _stunden(tage=tage, start="2023-11-15")
    assert s["aussen"].max() < 15
    return s


def test_kopplung_eins_wenn_durchfluss_der_kaelte_folgt():
    t = mb.tage(_winter())
    k = mb.kopplung_verlauf(t).dropna()
    assert len(k) > 80
    assert np.allclose(k, 1.0)


def test_kopplung_bei_luecken_und_doppeltagen():
    t = mb.tage(_winter())
    t = pd.concat([t.drop(index=range(30, 40)), t.iloc[[50]]])
    k = mb.kopplung_verlauf(t).dropna()
    assert k.index.is_unique and np.allclose(k, 1.0)


def test_abkuehlrate_newton():
    ts = pd.date_range("2024-06-01", periods=200, freq="h")
    k = 0.1
    temp = 20 + 50 * np.exp(-k * np.arange(200) % 24 * 0 - k * (np.arange(200) % 20))
    h = pd.DataFrame({"timestamp": ts, "vorlauf": temp, "durchfluss": 0.0})
    erwartet = 1 - np.exp(-k)
    assert mb.abkuehlrate(h, min_stunden=20) == pytest.approx(erwartet, rel=1e-6)
    h["durchfluss"] = 50.0
    assert np.isnan(mb.abkuehlrate(h, min_stunden=20))


def test_saettigung_und_plateau_erkennen_einen_deckel():
    aussen = np.linspace(-6, 12, 120)
    frei = pd.DataFrame({"aussen": aussen, "fluss_p95": 100 + 20 * (12 - aussen)})
    gedeckelt = frei.assign(fluss_p95=np.minimum(frei["fluss_p95"], 300))
    assert mb.fluss_saettigung(frei) == pytest.approx(1.0)
    assert mb.fluss_saettigung(gedeckelt) < 0.9
    f = pd.DataFrame({"durchfluss": np.r_[np.linspace(10, 300, 800), np.full(400, 300.0)]})
    g = pd.DataFrame({"durchfluss": np.linspace(10, 300, 1200)})
    assert mb.fluss_plateau(f) > 0.3 > mb.fluss_plateau(g)


def test_ruecklauf_schwachlast():
    n = 1000
    leistung = np.r_[np.full(500, 1.0), np.full(500, 20.0)]
    h = pd.DataFrame({"leistung": leistung, "durchfluss": 50.0,
                      "ruecklauf": np.where(leistung < 5, 55.0, 35.0)})
    assert mb.ruecklauf_schwachlast(h) == 55.0
    assert len(h) == n


def test_shap_linear_summe_gleich_log_odds():
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(60, 3)), columns=["a", "b", "c"])
    X.iloc[3, 1] = np.nan
    y = (X["a"].fillna(0) + 0.5 * rng.normal(size=60) > 0).astype(int)
    pipe = make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler(),
                         LogisticRegression()).fit(X, y)
    sh, basis = mb.shap_linear(pipe, X)
    assert np.allclose(sh.sum(axis=1) + basis, pipe.decision_function(X))
    assert np.allclose(sh.mean(axis=0), 0, atol=1e-8)
    assert sh["a"].abs().mean() > sh["c"].abs().mean()


def test_holm():
    assert np.allclose(mb.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])


def test_plan_pruefen_richtung_und_placebo():
    y = pd.Series([1] * 10 + [0] * 20)
    x = pd.Series(np.r_[np.linspace(-2, -1, 10), np.linspace(0, 1, 20)])
    g = pd.Series(np.arange(30))
    r = mb.plan_pruefen(x, y, g, richtung=-1, n_perm=500)
    assert r["AUC"] == 1.0 and r["p"] < 0.01
    r = mb.plan_pruefen(x, y, g, richtung=+1, n_perm=500)
    assert r["AUC"] == 0.0 and r["p"] > 0.99
    r = mb.plan_pruefen(x, y, g, richtung=0, n_perm=500)
    assert r["p"] < 0.01


def test_plan_steht_fuer_alle_sechs_befunde():
    assert set(mb.PLAN_WIRKUNG) == set(mb.ZIELE) == set(mb.PLAN_KENNZAHLEN)
    assert all(r in (-1, 0, 1) for _, r, _ in mb.PLAN_WIRKUNG.values())


def test_abkuehlrate_vorher_nachher_sieht_langsamere_abkuehlung():
    def sommer(start, k):
        ts = pd.date_range(start, periods=24 * 40, freq="h")
        temp = 20 + 50 * np.exp(-k * (np.arange(len(ts)) % 20))
        return pd.DataFrame({"zaehler": 7, "timestamp": ts, "vorlauf": temp, "durchfluss": 0.0, "leistung": 0.0})
    st = pd.concat([sommer("2024-06-01", 0.2), sommer("2025-06-01", 0.1)])
    t = mb.abkuehlrate_vorher_nachher(st, pd.Series({7: pd.Timestamp("2024-09-15")}))
    assert t.loc[7, "abkuehlrate_vor"] == pytest.approx(1 - np.exp(-0.2))
    assert t.loc[7, "abkuehlrate_nach"] == pytest.approx(1 - np.exp(-0.1))
    assert t.loc[7, "d_abkuehlrate"] < 0
    leer = mb.abkuehlrate_vorher_nachher(st, pd.Series({7: pd.Timestamp("2025-05-15")}))
    assert leer.empty or 7 not in leer.index


def test_effekt_bei_gleichem_start_nimmt_rueckkehr_zur_mitte_heraus():
    rng = np.random.default_rng(1)
    start = rng.normal(0.2, 0.05, 200)
    gruppe = (start > 0.22).astype(int)                 # Gruppe 1 liegt vorher höher
    aenderung = -0.5 * (start - 0.2) - 0.03 * gruppe + rng.normal(0, 0.005, 200)
    d = pd.DataFrame({"d": aenderung, "s": start, "g": gruppe})
    r = mb.effekt_bei_gleichem_start(d, "d", "s", "g", n=500)
    assert r["Effekt"] == pytest.approx(-0.03, abs=0.005)
    assert r["oben"] < 0 and r["unter 0 in"] == 1.0


def test_auc_innerhalb_faellt_wenn_die_gruppe_alles_erklaert():
    gruppe = np.r_[np.zeros(20), np.ones(20)]
    y = np.r_[np.r_[np.ones(4), np.zeros(16)], np.r_[np.ones(16), np.zeros(4)]]
    score = gruppe + np.random.default_rng(0).normal(0, 0.01, 40)     # Score kennt nur die Gruppe
    from sklearn.metrics import roc_auc_score
    assert roc_auc_score(y, score) > 0.75
    auc, paare = mb.auc_innerhalb(y, score, gruppe)
    assert paare == 2 * 4 * 16 and abs(auc - 0.5) < 0.2
    auc, _ = mb.auc_innerhalb(y, y + gruppe, gruppe)                    # Score trennt in jeder Gruppe
    assert auc == 1.0


def test_stationstyp_gruppe():
    assert mb.stationstyp_gruppe("'YADO|GIRO Typ 1l-1H") == "GIRO 1H"
    assert mb.stationstyp_gruppe("YADO|GIRO Typ 1l-0H-OIS") == "GIRO 0H"
    assert mb.stationstyp_gruppe("Yado Typ Comfort 1l-1H-1DS") == "Comfort"
    assert mb.stationstyp_gruppe(None) == "keine Angabe"


def test_gruppen_zufallstest():
    g = ["a"] * 20 + ["b"] * 20
    assert mb.gruppen_zufallstest(g, [1] * 20 + [0] * 20, n=500) < 0.01
    assert mb.gruppen_zufallstest(g, [1, 0] * 20, n=500) > 0.5
