"""Prüfstand (src/pruefstand.py): ohne Rohdaten lauffähig."""

import numpy as np
import pandas as pd
import pytest

from src import pruefstand as ps


def tage(zaehler, von="2024-10-01", n=120):
    d = pd.date_range(von, periods=n, freq="D")
    return pd.DataFrame({"zaehler": np.repeat(zaehler, n), "datum": np.tile(d, len(zaehler))})


def test_trefferpruefung_zaehlt_treffer_und_kontrollen():
    stationen = list(range(1, 9))
    beob = tage(stationen)
    faelle = pd.DataFrame({"zaehler": [1], "datum": [pd.Timestamp("2024-11-01")]})
    termine = {1: [pd.Timestamp("2024-11-01")], 2: [pd.Timestamp("2024-11-05")]}
    alarme = pd.DataFrame({"zaehler": [1, 3, 4], "datum": pd.to_datetime(
        ["2024-11-10", "2024-11-20", "2025-03-01"])})
    t = ps.trefferpruefung(alarme, beob, faelle, termine)
    assert len(t) == 1
    z = t.iloc[0]
    assert bool(z["treffer"])
    #Station 2 hat selbst eine Begehung im Fenster und ist keine Kontrolle
    assert z["n_kontrolle"] == 6
    #nur Station 3 alarmiert im Fenster (Station 4 erst nach dem Fenster)
    assert z["kontrollquote"] == pytest.approx(1 / 6)
    b = ps.bilanz(t, "x")
    assert b["Treffer"] == 1 and b["Hebel"] == pytest.approx(6.0)


def test_trefferpruefung_braucht_beobachtete_tage():
    beob = tage(list(range(1, 9)), von="2025-06-01")
    faelle = pd.DataFrame({"zaehler": [1], "datum": [pd.Timestamp("2024-11-01")]})
    t = ps.trefferpruefung(beob.iloc[:0].assign(), beob, faelle, {})
    assert t.empty


def test_gemeinsame_tage_und_budget():
    a, b = tage([1, 2], n=10), tage([2, 3], n=5)
    g = ps.gemeinsame_tage(a, b)
    assert set(g["zaehler"]) == {2} and len(g) == 5
    alarme = pd.DataFrame({"zaehler": [2, 2, 1], "datum": pd.to_datetime(["2024-10-02", "2024-10-09", "2024-10-02"])})
    assert len(ps.auf_tagen(alarme, g)) == 1

    def alarme_fuer(s):
        return pd.DataFrame({"zaehler": [2] * int(5 - s), "datum": pd.date_range("2024-10-01", periods=int(5 - s))})
    wert, tafel = ps.budget_anpassen(alarme_fuer, [1, 2, 3, 4], 2, g)
    assert wert == 3 and list(tafel["alarme"]) == [4, 3, 2, 1]


def test_mcnemar():
    a = pd.Series([True, True, True, False, False])
    b = pd.Series([True, False, False, False, True])
    m = ps.mcnemar(a, b)
    assert (m["nur A"], m["nur B"], m["beide"], m["keiner"]) == (2, 1, 1, 1)
    assert 0 < m["p (McNemar)"] <= 1


def test_einrechnen_bypass_mischt_ruecklauf():
    werte = np.zeros((10, 24, 3), dtype=np.float32)
    werte[:, :, 0] = 40.0     # Rücklauf
    werte[:, :, 1] = 100.0    # Durchfluss
    werte[:, :, 2] = 70.0     # Vorlauf
    feld = ps.einrechnen(werte, np.array([[2, 3]]), "Bypass 100")
    assert feld[2, 0, 1] == pytest.approx(200.0)
    assert feld[2, 0, 0] == pytest.approx(55.0)
    assert feld[1, 0, 1] == pytest.approx(100.0)
    assert werte[2, 0, 1] == pytest.approx(100.0), "Original bleibt unverändert"
    with pytest.raises(ValueError):
        ps.einrechnen(werte, np.array([[1]]), "Unsinn")


def test_auc_werkzeuge():
    y = np.array([0, 0, 0, 0, 1, 1, 1, 0, 1, 0])
    perfekt = y + 0.01 * np.arange(10)
    auc, unten, oben = ps.auc_mit_intervall(y, perfekt, n=200)
    assert auc == pytest.approx(1.0) and unten <= auc <= oben
    assert ps.precision_at_k(y, perfekt, k=4) == pytest.approx(1.0)
    assert ps.zufallstest(y, perfekt, n=500) < 0.05
    d, du, do = ps.auc_differenz(y, perfekt, -perfekt, n=200)
    assert d == pytest.approx(1.0) and du > 0


def test_holm_und_bewerte_scores():
    h = ps.holm([0.01, 0.04, np.nan, 0.03])
    assert np.isnan(h[2]) and h[0] == pytest.approx(0.03) and h[1] == pytest.approx(0.06)
    y = pd.Series([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 0], index=range(12))
    scores = {"gut": y + 0.01 * pd.Series(range(12)), "zufall": pd.Series(np.arange(12) % 3, index=range(12)),
              "luecke": pd.Series([np.nan] + list(range(11)), index=range(12), dtype=float)}
    t = ps.bewerte_scores(y, scores, bezug="zufall", n_boot=200, n_zufall=500)
    assert set(t["Stationen"]) == {11}, "nur Stationen, die alle Kandidaten haben"
    assert t.set_index("Kandidat").loc["zufall", "gegen Bezug"] == "Bezug"
    assert t.set_index("Kandidat").loc["gut", "AUC"] == pytest.approx(1.0)


def test_vierfelder_und_kappa():
    v = pd.Series([True, True, False, False], index=list("abcd"))
    b = pd.Series([True, False, True, False], index=list("abcd"))
    f = ps.vierfelder(v, b)
    assert (f["richtig ja"], f["falsch ja"], f["übersehen"], f["richtig nein"]) == (1, 1, 1, 1)
    assert f["Precision"] == pytest.approx(0.5)
    assert ps.kappa(v, v) == pytest.approx(1.0)


def test_bewerte_scores_paarweise_behaelt_stationen():
    y = pd.Series([0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 1, 0], index=range(12))
    bezug = y + 0.01 * pd.Series(range(12))
    luecke = pd.Series([np.nan, np.nan] + list(range(10)), index=range(12), dtype=float)
    t = ps.bewerte_scores(y, {"bezug": bezug, "luecke": luecke}, bezug="bezug",
                          n_boot=200, n_zufall=200, paarweise=True).set_index("Kandidat")
    assert t.loc["bezug", "Stationen"] == 12 and t.loc["luecke", "Stationen"] == 10
    assert np.isfinite(t.loc["luecke", "Δ zum Bezug"])
