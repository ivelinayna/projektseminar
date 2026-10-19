import numpy as np
import pandas as pd
import pytest

from src import netzereignisse as ne

TAGE = pd.date_range("2023-11-01", periods=120, freq="D")


def _alarme(zeilen):
    return pd.DataFrame(zeilen, columns=["meter", "kanal", "datum", "richtung",
                                         "beginn"])


def _beobachtet(meters, tage=TAGE):
    return {m: tage for m in meters}


def test_einsaetze_bewertung_und_tag():
    a = _alarme([
        (1, "kwh_pro_m3", "2023-12-10", -1, "2023-12-01"),
        (2, "log_volumen", "2023-12-12", 1, "2023-12-02"),
        (3, "kwh_pro_m3", "2023-12-12", 1, "2023-12-03"),
    ])
    e = ne.einsaetze(a).set_index("meter")
    assert list(e["bewertung"]) == ["schlechter", "schlechter", "besser"]
    assert e.loc[1, "beginn"] == pd.Timestamp("2023-12-01")
    assert list(e.index) == [1, 2, 3]


def test_verschiebe_behaelt_anzahl_und_aktive_tage():
    rng = np.random.default_rng(0)
    A = np.zeros((2, 50), dtype=bool)
    A[0, 10:30] = True
    A[1, :] = True
    E = np.zeros_like(A)
    E[0, [12, 20]] = True
    E[1, 3] = True
    for _ in range(20):
        V = ne.verschiebe(E, A, rng)
        assert V[0].sum() == 2 and V[1].sum() == 1
        assert not (V & ~A).any()


def _cluster_alarme(n_meter=12, tag="2024-01-15", n_im_cluster=8, seed=1):
    #Einzelne Alarme verstreut, dazu ein Tag mit vielen Stationen
    rng = np.random.default_rng(seed)
    zeilen = []
    for m in range(1, n_meter + 1):
        for t in rng.choice(TAGE, size=2, replace=False):
            zeilen.append((m, "kwh_pro_m3", t, -1, t))
    for m in range(1, n_im_cluster + 1):
        zeilen.append((m, "log_volumen", tag, 1, tag))
    return ne.einsaetze(_alarme(zeilen))


def test_netztage_findet_gemeinsamen_tag():
    e = _cluster_alarme()
    r = ne.netztage(e, _beobachtet(range(1, 13)), fenster=1, n=300, seed=0)
    t = r["tage"].set_index("datum")
    assert t.loc[pd.Timestamp("2024-01-15"), "netzereignis"]
    assert t["netzereignis"].sum() <= 3
    assert r["p_global"] < 0.05
    ep = r["episoden"]
    assert len(ep) == 1 and ep.iloc[0]["n_stationen"] >= 8


def test_netztage_ohne_haeufung():
    rng = np.random.default_rng(3)
    zeilen = []
    for m in range(1, 13):
        for t in rng.choice(TAGE, size=2, replace=False):
            zeilen.append((m, "kwh_pro_m3", t, -1, t))
    r = ne.netztage(ne.einsaetze(_alarme(zeilen)), _beobachtet(range(1, 13)),
                    fenster=1, n=300, seed=0)
    assert not r["tage"]["netzereignis"].any()
    assert r["p_global"] > 0.05
    assert len(r["episoden"]) == 0


def test_nachbar_gleichzeitig_kette():
    #Nachbarn 1-2, 3-4, 5-6 starten gleichzeitig, sonst alles weit auseinander
    tage = {1: "2023-11-05", 2: "2023-11-06", 3: "2023-12-01", 4: "2023-12-01",
            5: "2024-01-10", 6: "2024-01-12", 7: "2023-11-20", 8: "2023-12-20",
            9: "2024-02-01", 10: "2024-02-20"}
    e = ne.einsaetze(_alarme([(m, "kwh_pro_m3", t, -1, t)
                              for m, t in tage.items()]))
    paare = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10)]
    r = ne.nachbar_gleichzeitig(e, paare, fenster=3, n=5000, seed=0,
                                stationen=range(1, 11))
    assert r["beobachtet"] == 3 and r["paare"] == 5
    assert r["p"] < 0.01
    assert set(map(tuple, r["treffer"][["meter_a", "meter_b"]].to_numpy())) == {
        (1, 2), (3, 4), (5, 6)}


def test_nachbar_gleichzeitig_zufall():
    tage = {m: TAGE[m * 11].strftime("%Y-%m-%d") for m in range(1, 11)}
    e = ne.einsaetze(_alarme([(m, "kwh_pro_m3", t, -1, t)
                              for m, t in tage.items()]))
    paare = [(i, i + 1) for i in range(1, 10)]
    r = ne.nachbar_gleichzeitig(e, paare, fenster=3, n=2000, seed=0,
                                stationen=range(1, 11))
    assert r["beobachtet"] == 0 and r["p"] == pytest.approx(1.0)


def test_markiere_setzt_flags():
    e = ne.einsaetze(_alarme([
        (1, "kwh_pro_m3", "2023-12-05", -1, "2023-12-01"),
        (2, "kwh_pro_m3", "2023-12-06", -1, "2023-12-02"),
        (3, "kwh_pro_m3", "2024-01-20", -1, "2024-01-20"),
    ]))
    ereignistage = pd.DatetimeIndex(["2024-01-21"])
    m = ne.markiere(e, ereignistage, [(1, 2), (2, 3)], fenster=3).set_index("meter")
    assert m.loc[1, "nachbar_gleichzeitig"] and m.loc[2, "nachbar_gleichzeitig"]
    assert not m.loc[3, "nachbar_gleichzeitig"]
    assert m.loc[3, "netzereignis"] and not m.loc[1, "netzereignis"]


def test_monitor_status_zaehlt_flags_je_winter():
    prio = pd.DataFrame({"meter": [1, 1], "winter": ["22/23", "23/24"],
                         "auffaellig": [False, True],
                         "alarme_schlechter": [0, 1], "alarme_besser": [1, 0],
                         "prioritaet": ["niedrig", "hoch"]})
    markiert = pd.DataFrame({"meter": [1, 1], "winter": ["22/23", "23/24"],
                             "score": [0.1, 2.0], "rang": [30, 1]})
    fb = pd.DataFrame({"meter": [1], "winter": ["23/24"],
                       "fehlerbild": ["ventil"]})
    ueb = pd.DataFrame({"meter": [1], "chronisch": [False]})
    alarme = pd.DataFrame({"meter": [1, 1], "datum": pd.to_datetime(
        ["2022-12-10", "2024-01-10"]), "netzereignis": [True, False],
        "nachbar_gleichzeitig": [False, True]})
    s = ne.monitor_status(prio, markiert, fb, ueb, alarme).set_index("winter")
    assert s.loc["22/23", "alarme_netzereignis"] == 1
    assert s.loc["23/24", "alarme_nachbar"] == 1
    assert s.loc["23/24", "fehlerbild"] == "ventil"
    assert s.loc["22/23", "fehlerbild"] == ""
    assert s.loc["23/24", "prioritaet"] == "hoch"
    assert "adresse" not in s.columns
