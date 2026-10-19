"""
Tests für src.clustervalidierung.

Laufen ohne Rohdaten und ohne Netz: die Zähler-CSVs werden als kleine
synthetische Exporte in tmp_path geschrieben, alle übrigen Funktionen
arbeiten auf konstruierten DataFrames mit bekanntem Sollwert.

Standalone lauffähig:

    python -m pytest tests/test_clustervalidierung.py
"""

import numpy as np
import pandas as pd
import pytest

from src import clustervalidierung as cv


def _export(path, zid, stunden=400, power=None, start="2024-01-01"):
    """Einen materialisierten Zählerexport im 8-Spalten-Schema schreiben."""
    ts = pd.date_range(start, periods=stunden, freq="h")
    rng = np.random.default_rng(zid)
    if power is None:
        power = rng.uniform(1.0, 20.0, stunden)
    power = np.asarray(power, dtype=float)
    df = pd.DataFrame({
        "Timestamp": ts,
        "Energy (kWh)": np.cumsum(power),
        "Volume flow (l/h)": power * 25.0,
        "Power (kW)": power,
        "Temperature difference (°C)": 25.0 + rng.normal(0, 2, stunden),
        "Flow temperature (°C)": 70.0 + rng.normal(0, 2, stunden),
        "Return temperature (°C)": 45.0 + rng.normal(0, 2, stunden),
        "Volume (m³)": np.cumsum(power) / 40.0,
    })
    df.to_csv(path / f"{zid}.csv", index=False)
    return df


#--------------------------------------------------------------------------
#Stundenpanel
#--------------------------------------------------------------------------

def test_normierung_teilt_durch_eigenes_quantil():
    df = pd.DataFrame({
        "Zählernummer": [1] * 5 + [2] * 5,
        "power": [0.0, 1.0, 2.0, 3.0, 4.0, 0.0, 10.0, 20.0, 30.0, 40.0],
        "flow": [0.0, 10.0, 20.0, 30.0, 40.0, 0.0, 1.0, 2.0, 3.0, 4.0],
    })
    out = cv.normiere_station(df, quantil=1.0)
    #die groesste Stunde jeder Station wird per Konstruktion zu 1
    assert out.loc[4, "power_norm"] == pytest.approx(1.0)
    assert out.loc[9, "power_norm"] == pytest.approx(1.0)
    #ohne Normierung waere Station 2 zehnmal so weit vom Ursprung entfernt
    assert out.loc[3, "power_norm"] == pytest.approx(out.loc[8, "power_norm"])


def test_normierung_meldet_nan_statt_division_durch_null():
    df = pd.DataFrame({"Zählernummer": [1, 1], "power": [0.0, 0.0],
                       "flow": [0.0, 0.0]})
    out = cv.normiere_station(df)
    assert out["power_norm"].isna().all()


def test_panel_schliesst_dauerstillstand_mit_grund_aus(tmp_path):
    _export(tmp_path, 11)
    _export(tmp_path, 22, power=np.zeros(400))
    panel, ausschluss = cv.lade_stundenpanel(tmp_path)
    assert set(panel["Zählernummer"]) == {11}
    assert list(ausschluss["Zählernummer"]) == [22]
    assert "Dauerstillstand" in ausschluss.loc[0, "grund"]
    #Ausschluss wird tabelliert, nicht still verworfen
    assert int(ausschluss.loc[0, "n_stunden"]) == 400


def test_panel_schliesst_zu_kurze_historie_aus(tmp_path):
    _export(tmp_path, 11)
    _export(tmp_path, 33, stunden=20)
    panel, ausschluss = cv.lade_stundenpanel(tmp_path, min_stunden=100)
    assert set(panel["Zählernummer"]) == {11}
    assert "vollständige Stunden" in ausschluss.loc[0, "grund"]


def test_panel_hat_die_betriebsfeatures_und_keine_luecken(tmp_path):
    _export(tmp_path, 11)
    panel, _ = cv.lade_stundenpanel(tmp_path)
    for spalte in cv.BETRIEBS_FEATURES:
        assert spalte in panel.columns
    assert not panel[cv.BETRIEBS_FEATURES].isna().any().any()


def test_panel_leer_wenn_kein_zaehler_uebrig_bleibt(tmp_path):
    _export(tmp_path, 22, power=np.zeros(400))
    panel, ausschluss = cv.lade_stundenpanel(tmp_path)
    assert panel.empty
    assert len(ausschluss) == 1


def test_mit_kontext_ergaenzt_monat_stunde_saison_und_temperatur(tmp_path):
    _export(tmp_path, 11, stunden=200, start="2024-02-01")
    panel, _ = cv.lade_stundenpanel(tmp_path)
    temp = pd.DataFrame({
        "timestamp": pd.date_range("2024-02-01", periods=200, freq="h"),
        "t_out": np.linspace(-5.0, 5.0, 200),
    })
    out = cv.mit_kontext(panel, temp)
    assert set(out["monat"]) == {2}
    assert set(out["season"]) == {"kernwinter"}
    assert out["t_out"].notna().all()
    assert out["stunde"].between(0, 23).all()


#--------------------------------------------------------------------------
#Stabilität und Profile
#--------------------------------------------------------------------------

def _drei_wolken(n=120, seed=0):
    rng = np.random.default_rng(seed)
    zentren = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
    X = np.vstack([c + rng.normal(0, 0.3, (n, 2)) for c in zentren])
    y = np.repeat([0, 1, 2], n)
    return X, y


def test_bootstrap_ari_ist_hoch_bei_klarer_struktur():
    X, _ = _drei_wolken()
    r = cv.bootstrap_ari(cv.fit_minibatch_kmeans, X, 3, n_boot=8)
    assert r["n_laeufe"] == 8
    assert r["ari_mean"] > 0.9


def test_bootstrap_ari_ist_niedrig_auf_strukturlosem_rauschen():
    rng = np.random.default_rng(1)
    X = rng.normal(0, 1, (300, 2))
    r = cv.bootstrap_ari(cv.fit_minibatch_kmeans, X, 5, n_boot=8)
    assert r["ari_mean"] < 0.8


def test_bootstrap_ari_stichprobe_begrenzt_den_rechenaufwand():
    X, _ = _drei_wolken(n=400)
    r = cv.bootstrap_ari(cv.fit_minibatch_kmeans, X, 3, n_boot=3,
                         stichprobe=100)
    assert r["n_laeufe"] == 3
    assert np.isfinite(r["ari_mean"])


def test_silhouette_stichprobe_gibt_nan_bei_einem_cluster():
    X, _ = _drei_wolken()
    assert np.isnan(cv.silhouette_stichprobe(X, np.zeros(len(X), dtype=int)))


def test_zentroid_profil_zeigt_originaleinheiten():
    X = np.array([[10.0, 60.0], [12.0, 62.0], [30.0, 40.0], [32.0, 42.0]])
    profil = cv.zentroid_profil(X, [0, 0, 1, 1], ["dt", "rt"])
    assert profil.loc[0, "dt"] == pytest.approx(11.0)
    assert profil.loc[1, "rt"] == pytest.approx(41.0)
    assert profil["anteil_%"].sum() == pytest.approx(100.0)


def test_zentroid_zuordnung_findet_das_gegenstueck_trotz_anderer_nummern():
    a = pd.DataFrame({"dt": [5.0, 30.0], "rt": [60.0, 40.0]}, index=[0, 1])
    b = pd.DataFrame({"dt": [31.0, 6.0], "rt": [41.0, 59.0]}, index=[0, 1])
    zu = cv.zentroid_zuordnung(a, b, ["dt", "rt"])
    assert list(zu["cluster_b"]) == [1, 0]


#--------------------------------------------------------------------------
#Saisonkontrolle
#--------------------------------------------------------------------------

def test_cramers_v_null_bei_unabhaengigkeit_und_eins_bei_deckung():
    unabhaengig = pd.DataFrame([[25, 25], [25, 25]])
    assert cv.cramers_v(unabhaengig) == pytest.approx(0.0)
    deterministisch = pd.DataFrame([[50, 0], [0, 50]])
    assert cv.cramers_v(deterministisch) == pytest.approx(1.0)


def test_kontext_erklaerbarkeit_erkennt_reinen_saisoneffekt():
    #Cluster ist hier per Konstruktion eine Funktion der Aussentemperatur
    rng = np.random.default_rng(3)
    t_out = rng.uniform(-10, 25, 2000)
    labels = (t_out > 8).astype(int)
    kontext = pd.DataFrame({"t_out": t_out, "stunde": rng.integers(0, 24, 2000)})
    tab = cv.kontext_erklaerbarkeit(labels, kontext,
                                    {"nur t_out": ["t_out"],
                                     "nur Stunde": ["stunde"]}, cv=3)
    nur_t = tab.set_index("merkmale").loc["nur t_out"]
    nur_h = tab.set_index("merkmale").loc["nur Stunde"]
    assert nur_t["genauigkeit"] > 0.95
    #die Tageszeit traegt nichts bei, bleibt also an der Trivialrate
    assert nur_h["abstand"] < 0.05


def test_kontext_erklaerbarkeit_bleibt_an_der_trivialrate_ohne_zusammenhang():
    rng = np.random.default_rng(4)
    labels = rng.integers(0, 3, 1500)
    kontext = pd.DataFrame({"t_out": rng.uniform(-10, 25, 1500)})
    tab = cv.kontext_erklaerbarkeit(labels, kontext, {"nur t_out": ["t_out"]},
                                    cv=3)
    assert tab.loc[0, "abstand"] < 0.05


def test_kontext_kreuztabelle_zeilen_summieren_auf_eins():
    labels = [0, 0, 1, 1, 1]
    monat = pd.Series([1, 2, 1, 2, 2], name="monat")
    tab = cv.kontext_kreuztabelle(labels, monat)
    assert tab.sum(axis=1).round(6).eq(1.0).all()


#--------------------------------------------------------------------------
#Feature-Gewichtung
#--------------------------------------------------------------------------

def test_redundanz_auswahl_behaelt_je_gruppe_ein_feature():
    rng = np.random.default_rng(5)
    a = rng.normal(0, 1, 300)
    df = pd.DataFrame({
        "a": a,
        "a_kopie": a + rng.normal(0, 0.01, 300),
        "b": rng.normal(0, 1, 300),
    })
    behalten, bilanz = cv.redundanz_auswahl(df, schwelle=0.8)
    assert behalten == ["a", "b"]
    assert bilanz.loc[0, "feature"] == "a_kopie"
    assert bilanz.loc[0, "redundant_zu"] == "a"


def test_redundanz_auswahl_respektiert_die_prioritaet():
    rng = np.random.default_rng(6)
    a = rng.normal(0, 1, 300)
    df = pd.DataFrame({"a": a, "a_kopie": a + rng.normal(0, 0.01, 300)})
    behalten, _ = cv.redundanz_auswahl(df, schwelle=0.8, prioritaet=["a_kopie"])
    assert behalten == ["a_kopie"]


def test_redundanz_auswahl_verwirft_nichts_unter_der_schwelle():
    rng = np.random.default_rng(7)
    df = pd.DataFrame({"a": rng.normal(0, 1, 300), "b": rng.normal(0, 1, 300)})
    behalten, bilanz = cv.redundanz_auswahl(df, schwelle=0.8)
    assert behalten == ["a", "b"]
    assert bilanz.empty


def test_gewichtungsvarianten_liefern_die_erwarteten_dimensionen():
    rng = np.random.default_rng(8)
    a = rng.normal(0, 1, 200)
    df = pd.DataFrame({"a": a, "a_kopie": a + rng.normal(0, 0.01, 200),
                       "b": rng.normal(0, 1, 200)})
    varianten = cv.gewichtungsvarianten(df, ["a", "a_kopie", "b"],
                                        auswahl=["a", "b"], pca_varianz=0.9,
                                        gewichte={"a": 2.0})
    assert varianten["alle gleich"].shape[1] == 3
    assert varianten["auswahl"].shape[1] == 2
    #zwei der drei Spalten sind faktisch dieselbe Richtung, 90 % Varianz
    #brauchen daher weniger als drei Komponenten
    assert varianten["pca"].shape[1] < 3
    assert varianten["fachgewichtet"].shape[1] == 3


def test_fachgewichtung_streckt_die_gewichtete_achse():
    df = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [0.0, 1.0, 2.0, 3.0]})
    varianten = cv.gewichtungsvarianten(df, ["a", "b"], gewichte={"a": 3.0})
    g = varianten["fachgewichtet"]
    assert g[:, 0].std() == pytest.approx(3.0 * g[:, 1].std())


#--------------------------------------------------------------------------
#Leistungsklassen
#--------------------------------------------------------------------------

@pytest.mark.parametrize("kw, erwartet", [
    (3.0, "bis 5 kW"),
    (5.0, "bis 5 kW"),
    (7.5, "5-10 kW"),
    (10.0, "5-10 kW"),
    (10.1, "über 10 kW"),
    (500.0, "über 10 kW"),
])
def test_leistungsklasse_grenzen_gehoeren_nach_unten(kw, erwartet):
    assert cv.leistungsklasse(kw) == erwartet


@pytest.mark.parametrize("wert", [None, np.nan, "", "k.A."])
def test_leistungsklasse_ohne_anschlusswert_ist_unbekannt(wert):
    assert cv.leistungsklasse(wert) == "unbekannt"


def test_mit_leistungsklasse_ist_geordnet_kategorial():
    df = pd.DataFrame({"anschlusswert_kw": [4.0, 8.0, 50.0, np.nan]})
    out = cv.mit_leistungsklasse(df)
    assert list(out["leistungsklasse"]) == ["bis 5 kW", "5-10 kW",
                                            "über 10 kW", "unbekannt"]
    assert out["leistungsklasse"].cat.ordered
