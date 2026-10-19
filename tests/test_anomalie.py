"""
Tests fuer src.anomalie.

Zwei Punkte sind hier wichtiger als die Mechanik. Erstens muss das
stationseigene Erwartungswertmodell eine chronisch zu warme Station
*nicht* finden - das ist kein Fehler, sondern die dokumentierte Grenze
des Bezugsrahmens, und wenn ein spaeterer Umbau sie beseitigt, soll der
Test anschlagen. Zweitens muss die Persistenzregel einen kurzen
Ausschlag verwerfen und eine laengere Phase halten.

Laeuft ohne Rohdaten und ohne Netz:

    python -m pytest tests/test_anomalie.py
"""

import numpy as np
import pandas as pd

from src import anomalie as an

RNG = np.random.default_rng(7)


def _panel(n_meter: int = 6, tage: int = 200, start: str = "2024-01-01",
           offsets: dict = None) -> pd.DataFrame:
    """Tagespanel mit bekanntem Zusammenhang rt = 50 - 0,5 t_out + Rauschen."""
    offsets = offsets or {}
    datum = pd.date_range(start, periods=tage, freq="D")
    t_out = 5.0 + 10.0 * np.sin(np.arange(tage) / 40.0)
    zeilen = []
    for zid in range(1, n_meter + 1):
        rt = (50.0 - 0.5 * t_out + offsets.get(zid, 0.0)
              + RNG.normal(0, 0.5, tage))
        #die beiden weiteren Praediktoren muessen streuen, sonst ist die
        #Entwurfsmatrix je Station rangdefizitaer
        zeilen.append(pd.DataFrame({
            "meter": zid, "datum": datum, "t_out_tag": t_out,
            "last_anteil": np.clip(0.8 + RNG.normal(0, 0.05, tage), 0, 1),
            "power_mean": 5.0 + RNG.normal(0, 0.4, tage),
            "rt_median": rt, "genug_stunden": True,
            "heizgradstunden": np.clip(15.0 - t_out, 0, None) * 24,
            "energie_kwh": 100.0,
        }))
    return pd.concat(zeilen, ignore_index=True)


def test_netzmodell_findet_den_bekannten_zusammenhang():
    panel = _panel()
    out, info = an.erwartungsmodell_netz(panel)
    assert info["n_tage"] == len(panel)
    assert np.isclose(info["beta"]["t_out_tag"], -0.5, atol=0.05)
    assert out[f"score_{an.D_RESID_NETZ}"].abs().mean() < 1.0


def test_netzmodell_zeigt_die_chronisch_warme_station():
    panel = _panel(offsets={3: 6.0})
    out, _ = an.erwartungsmodell_netz(panel)
    je_station = out.groupby("meter")[f"score_{an.D_RESID_NETZ}"].mean()
    assert je_station.idxmax() == 3
    assert je_station.loc[3] > 3.0


def test_stationsmodell_sieht_die_chronisch_warme_station_nicht():
    #dokumentierte Grenze des Bezugsrahmens: das eigene Residuum ist im
    #Mittel null, der dauerhafte Offset verschwindet im Achsenabschnitt
    panel = _panel(offsets={3: 6.0})
    out, bilanz = an.erwartungsmodell_station(panel)
    je_station = out.groupby("meter")[f"score_{an.D_RESID_STATION}"].mean()
    assert abs(je_station.loc[3]) < 0.1
    assert bool(bilanz["geschaetzt"].all())


def test_stationsmodell_meldet_zu_kurze_historien():
    panel = _panel(tage=30)
    _, bilanz = an.erwartungsmodell_station(panel, min_tage=60)
    assert not bilanz["geschaetzt"].any()
    assert bilanz["grund"].str.contains("60").all()


def test_persistenz_verwirft_den_kurzen_ausschlag():
    datum = pd.date_range("2024-01-01", periods=60, freq="D")
    werte = np.zeros(60)
    werte[10:13] = 10.0    #drei Tage, kein Befund
    werte[30:45] = 10.0    #fuenfzehn Tage, Befund
    panel = pd.DataFrame({"meter": 1, "datum": datum, "score": werte})
    out, schwelle = an.persistente_tage(panel, "score", schwelle=5.0,
                                        fenster=14, min_tage=7)
    assert schwelle == 5.0
    assert out.loc[out["datum"].isin(datum[10:13]), "persistent_score"].sum() == 0
    assert out["persistent_score"].sum() >= 8


def test_persistenzschwelle_wirkt_auf_die_trefferliste():
    datum = pd.date_range("2024-01-01", periods=60, freq="D")
    werte = np.zeros(60)
    werte[20:30] = 10.0
    panel = pd.DataFrame({"meter": 1, "datum": datum, "score": werte})
    locker, _ = an.persistente_tage(panel, "score", schwelle=5.0,
                                    fenster=14, min_tage=3)
    streng, _ = an.persistente_tage(panel, "score", schwelle=5.0,
                                    fenster=14, min_tage=12)
    assert locker["persistent_score"].sum() > streng["persistent_score"].sum()
    assert streng["persistent_score"].sum() == 0


def test_stationsscore_zaehlt_den_laengsten_lauf():
    datum = pd.date_range("2024-01-01", periods=30, freq="D")
    werte = np.zeros(30)
    werte[5:12] = 9.0
    panel = pd.DataFrame({"meter": 1, "datum": datum, "score": werte})
    panel, _ = an.persistente_tage(panel, "score", schwelle=1.0, min_tage=5)
    tab = an.stationsscore(panel, "score")
    assert tab["max_lauf"].iloc[0] == 7
    assert np.isclose(tab["anteil_auffaellig"].iloc[0], 7 / 30)


def test_uebereinstimmung_erkennt_identische_detektoren():
    scores = pd.DataFrame({"meter": [1, 2, 3, 4, 5],
                           "a": [1.0, 2.0, 3.0, 4.0, 5.0],
                           "b": [2.0, 4.0, 6.0, 8.0, 10.0],
                           "c": [5.0, 4.0, 3.0, 2.0, 1.0]})
    rang, jaccard = an.uebereinstimmung(scores, ["a", "b", "c"], top_n=2)
    assert np.isclose(rang.loc["a", "b"], 1.0)
    assert np.isclose(rang.loc["a", "c"], -1.0)
    assert jaccard.loc["a", "b"] == 1.0
    assert jaccard.loc["a", "c"] == 0.0


def test_muster_benennt_den_kurzschlussverdacht():
    profil = pd.DataFrame({
        "meter": list(range(1, 11)),
        "rt_vl_kopplung": [0.2] * 9 + [0.95],
        "dt_mean_loaded": [25.0] * 9 + [4.0],
        "rt_traege_anteil": [0.1] * 10,
        "rt_d1_abs_mean": [0.5] * 10,
        "rt_d2_abs_mean": [0.3] * 10,
    })
    muster = an.muster_je_station(profil)
    zeile = muster[muster["meter"] == 10].iloc[0]
    assert "Kurzschluss" in zeile["muster"]
    assert "rt_vl_kopplung" in zeile["begruendung"]


def test_muster_uebergeht_kennzahl_ohne_streuung():
    #rt_traege_anteil ist konstant null; ohne Zusatzbedingung gaelte 0
    #zugleich als hoch und als niedrig und die Ventilregel wuerde
    #ueberall feuern
    profil = pd.DataFrame({
        "meter": list(range(1, 11)),
        "rt_vl_kopplung": [0.2] * 10,
        "dt_mean_loaded": [25.0] * 10,
        "rt_traege_anteil": [0.0] * 10,
        "rt_d1_abs_mean": [0.5] * 10,
        "rt_d2_abs_mean": [0.3] * 10,
    })
    muster = an.muster_je_station(profil)
    assert (muster["muster"] == "kein eindeutiges Muster").all()


def test_begehungsvalidierung_findet_den_rueckgang():
    #Station 1 faellt im Nachher-Fenster ab, die Kontrollstationen nicht
    datum = pd.date_range("2024-01-01", periods=240, freq="D")
    grenzen = {"vor_start": datum[0], "vor_end": datum[99],
               "nach_start": datum[140], "nach_end": datum[239]}
    zeilen = []
    for zid in range(1, 8):
        score = np.full(240, 2.0)
        if zid == 1:
            score[140:] = 0.5
        zeilen.append(pd.DataFrame({"meter": zid, "datum": datum,
                                    "score": score}))
    panel = pd.concat(zeilen, ignore_index=True)
    begehungen = pd.DataFrame({"meter": [1], "datum": [datum[120]]})

    tab = an.begehungsvalidierung(panel, "score", begehungen,
                                  lambda d: grenzen,
                                  kennzahlen=("score_mittel",))
    assert bool(tab["auswertbar"].iloc[0])
    assert np.isclose(tab["d_score_mittel"].iloc[0], -1.5)

    did = an.diff_in_diff(panel, "score", begehungen, list(range(2, 8)),
                          lambda d: grenzen, kennzahlen=("score_mittel",))
    assert len(did) == 1
    assert np.isclose(did["d_score_mittel_kontrolle"].iloc[0], 0.0)
    assert np.isclose(did["did_score_mittel"].iloc[0], -1.5)


def test_validierungsbilanz_faellt_ohne_bewegung_durch():
    did = pd.DataFrame({"d_score_mittel_station": np.zeros(10),
                        "did_score_mittel": np.zeros(10)})
    bilanz = an.validierungsbilanz(did)
    assert bilanz["bestanden"] is False


def test_gepaarter_test_liefert_p_wert():
    werte = np.full(12, -1.0) + np.linspace(0, 0.2, 12)
    ergebnis = an.gepaarter_test(werte)
    assert ergebnis["n"] == 12
    assert ergebnis["median"] < 0
    assert ergebnis["p"] < 0.01


def test_effizienz_je_station_normiert_auf_die_witterung():
    panel = _panel(n_meter=2, tage=100)
    eff = an.effizienz_je_station(panel)
    assert len(eff) == 2
    assert (eff["energie_je_kh"] > 0).all()


def test_dynamikscore_uebergeht_kennzahlen_ohne_streuung():
    #rt_traege_anteil ist auf den echten Tagesdaten fast immer null; eine
    #Kennzahl mit MAD null darf den ganzen Score nicht auf NaN ziehen
    n = 60
    panel = pd.DataFrame({
        "meter": 1, "datum": pd.date_range("2024-01-01", periods=n, freq="D"),
        "rt_vl_kopplung": RNG.uniform(0, 1, n),
        "rt_traege_anteil": 0.0,
        "rt_d2_abs_mean": RNG.uniform(1, 10, n),
    })
    out, info = an.score_dynamik(panel)
    assert info["verworfen"] == {"rt_traege_anteil": info["verworfen"][
        "rt_traege_anteil"]}
    assert "rt_traege_anteil" not in info["benutzt"]
    assert out[f"score_{an.D_DYNAMIK}"].notna().all()


def test_dynamikscore_bleibt_leer_wenn_nichts_streut():
    n = 60
    panel = pd.DataFrame({
        "meter": 1, "datum": pd.date_range("2024-01-01", periods=n, freq="D"),
        "rt_vl_kopplung": 0.5, "rt_traege_anteil": 0.0,
        "rt_d2_abs_mean": 3.0,
    })
    out, info = an.score_dynamik(panel)
    assert info["benutzt"] == []
    assert out[f"score_{an.D_DYNAMIK}"].isna().all()


def test_zustandsscore_summiert_die_anteile():
    panel = pd.DataFrame({"meter": [1, 1], "datum": pd.to_datetime(
        ["2024-01-01", "2024-01-02"]), "anteil_c3": [0.2, 0.4],
        "anteil_c4": [0.1, 0.0]})
    out = an.score_zustand(panel, ["anteil_c3", "anteil_c4"])
    assert np.allclose(out[f"score_{an.D_ZUSTAND}"], [0.3, 0.4])


def test_isolation_forest_hebt_den_ausreisser():
    panel = _panel(n_meter=5, tage=60)
    panel.loc[panel.index[:5], "rt_median"] += 40.0
    out, info = an.score_isolation_forest(
        panel, ["rt_median", "t_out_tag", "last_anteil"])
    assert info["n_tage"] == len(panel)
    hoch = out.nlargest(5, f"score_{an.D_IFOREST}").index
    assert set(hoch) >= set(panel.index[:3])


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
    print("alle Anomalietests bestanden")
