import networkx as nx
import numpy as np
import pandas as pd
import pytest

from src import nachbarschaft as ns


def _graph():
    #a - b - j - c - d, e ohne Kante, j ist ein Knotenpunkt ohne Zähler
    g = nx.Graph()
    for n, z in (("a", 1), ("b", 2.0), ("c", "3"), ("d", 4), ("e", 5)):
        g.add_node(n, kind="HAST", zaehlernummer=z)
    g.add_node("f", kind="HAST", zaehlernummer=np.nan)
    g.add_node("j", kind="junction")
    g.add_edges_from([("a", "b"), ("b", "j"), ("j", "c"), ("c", "d"),
                      ("d", "f")])
    return g


def _kette(n):
    g = nx.path_graph([f"k{i}" for i in range(n)])
    for i in range(n):
        g.nodes[f"k{i}"].update(kind="HAST", zaehlernummer=i + 1)
    return g


def test_meter_knoten():
    k = ns.meter_knoten(_graph())
    assert k == {1: "a", 2: "b", 3: "c", 4: "d", 5: "e"}


def test_nachbarn_nach_kanten():
    g = _graph()
    eins = ns.nachbarn(g, max_kanten=1)
    assert eins[1] == {2} and eins[2] == {1}
    assert eins[3] == {4} and eins[5] == set()
    zwei = ns.nachbarn(g, max_kanten=2)
    assert zwei[2] == {1, 3} and zwei[3] == {2, 4}


def test_paare_ungeordnet_und_eindeutig():
    p = ns.paare({1: {2}, 2: {1, 3}, 3: {2}})
    assert p == [(1, 2), (2, 3)]


def test_join_test_zaehlt_paare_und_erwartung():
    paare = ns.paare(ns.nachbarn(_kette(10), max_kanten=1))
    flags = {m: m <= 3 for m in range(1, 11)}
    r = ns.join_test(paare, flags, n=20000, seed=0)
    assert r["beobachtet"] == 2
    #9 Paare, je Paar 3/10 * 2/9
    assert r["erwartet"] == pytest.approx(0.6, abs=0.05)
    assert 0 < r["p"] < 0.2


def test_join_test_verstreut_ist_unauffaellig():
    paare = ns.paare(ns.nachbarn(_kette(10), max_kanten=1))
    flags = {m: m in (1, 5, 9) for m in range(1, 11)}
    r = ns.join_test(paare, flags, n=2000, seed=0)
    assert r["beobachtet"] == 0 and r["p"] == pytest.approx(1.0)


def test_join_test_nur_stationen_mit_wert():
    paare = [(1, 2), (2, 3), (3, 4)]
    r = ns.join_test(paare, {1: True, 2: True, 4: False}, n=500, seed=0)
    assert r["paare"] == 1 and r["n_stationen"] == 3


def test_join_test_permutiert_nur_stationen_im_graph():
    paare = [(1, 2)]
    flags = {1: True, 2: True, 3: False, 4: False, 5: False}
    alle = ns.join_test(paare, flags, n=2000, seed=0)
    im_graph = ns.join_test(paare, flags, n=2000, seed=0, stationen={1, 2, 3})
    assert alle["n_stationen"] == 5 and im_graph["n_stationen"] == 3
    #1 von 3 Paaren statt 1 von 10 beim Ziehen von 2 Auffälligen
    assert im_graph["erwartet"] == pytest.approx(1 / 3, abs=0.05)
    assert alle["erwartet"] == pytest.approx(0.1, abs=0.03)
    s = ns.score_test([(1, 2), (2, 3)], {m: float(m) for m in range(1, 6)},
                      n=200, seed=0, stationen={1, 2, 3})
    assert s["n_stationen"] == 3


def test_score_test_glatter_verlauf_haengt_zusammen():
    paare = ns.paare(ns.nachbarn(_kette(30), max_kanten=1))
    score = {m: float(m) for m in range(1, 31)}
    r = ns.score_test(paare, score, n=2000, seed=0)
    assert r["beobachtet"] > 0.9
    assert r["p"] < 0.01
    assert abs(r["erwartet"]) < 0.1


def test_radius_nachbarn_luftlinie():
    #1 und 2 etwa 33 m auseinander, 3 gut 1 km weg
    pos = pd.DataFrame({"meter": [1, 2, 3], "lat": [49.8000, 49.8003, 49.8100],
                        "lon": [10.3400, 10.3400, 10.3400]})
    nb = ns.radius_nachbarn(pos, 50)
    assert nb == {1: {2}, 2: {1}, 3: set()}
    assert ns.radius_nachbarn(pos, 20)[1] == set()


def test_positionen_aus_handliste(tmp_path):
    pfad = tmp_path / "koordinaten.csv"
    pd.DataFrame({"adresse": ["Hauptstr. 1", "Weg 2", "Gasse 3", "Ring 4"],
                  "koordinate": ["49.81, 10.34", "10.35, 49.82", "", "kaputt"]}
                 ).to_csv(pfad, index=False)
    adressen = {11: "Hauptstraße 1", 12: "Weg 2", 13: "Gasse 3", 14: "Ring 4",
                15: "Sonstwo 5"}
    pos = ns.positionen_aus_handliste(pfad, adressen).set_index("meter")
    assert sorted(pos.index) == [11, 12]
    assert pos.loc[11, "lat"] == pytest.approx(49.81)
    #Breite und Länge vertauscht eingetragen
    assert pos.loc[12, "lat"] == pytest.approx(49.82)
    assert pos.loc[12, "lon"] == pytest.approx(10.35)
    assert "adresse" not in pos.columns


def test_nachbartabelle():
    nb = {1: {2, 3}, 2: {1}, 3: {1}, 4: set()}
    markiert = pd.DataFrame({"meter": [1, 2, 3, 4],
                             "auffaellig": [True, True, False, True]})
    fb = {1: "ventil", 2: "ventil", 4: "unruhig"}
    t = ns.nachbartabelle(nb, markiert, fb).set_index("meter")
    assert list(t.index) == [1, 2, 4]
    assert t.loc[1, "n_nachbarn"] == 2 and t.loc[1, "n_mit_score"] == 2
    assert t.loc[1, "n_auffaellig"] == 1 and t.loc[1, "n_gleiches_bild"] == 1
    assert t.loc[1, "nachbarn"] == "2, 3"
    assert t.loc[4, "n_nachbarn"] == 0 and t.loc[4, "nachbarn"] == ""
