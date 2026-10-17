"""
Tests fuer src.performance (Kennzahl kWh/m3 und Regression gegen t_out).

Nur konstruierte Stundendaten, kein Netzzugriff, keine Rohdaten. Die
Zaehler sind so gebaut, dass Energie, Volumen und Performance exakt
bekannt sind; die Regressionsteile laufen gegen analytisch vorgegebene
Geraden, damit Steigung, Delta und Prozentwert nachrechenbar bleiben.

Laeuft mit:

    python -m pytest tests/test_performance.py
"""

import numpy as np
import pandas as pd
import pytest

from src import performance as perf


def _zaehler(start: str = "2024-01-01", days: int = 10,
             kwh_pro_h: float = 12.0, m3_pro_h: float = 0.6,
             rt: float = 45.0, power: float = 12.0) -> pd.DataFrame:
    """Konstanter Zaehler mit exakt bekannter Performance kwh/m3."""
    hours = days * 24
    ts = pd.date_range(start, periods=hours, freq="h")
    schritt = np.arange(hours, dtype=float)
    return pd.DataFrame({
        "energy": schritt * kwh_pro_h,
        "flow": np.full(hours, m3_pro_h * 1000.0),
        "power": np.full(hours, power),
        "dt": np.full(hours, 70.0 - rt),
        "vl": np.full(hours, 70.0),
        "rt": np.full(hours, rt),
        "volume": schritt * m3_pro_h,
    }, index=ts.rename("Timestamp"))


#--------------------------------------------------------------------------
#Differenzierung der kumulativen Kanaele
#--------------------------------------------------------------------------

def test_konstanter_zaehler_liefert_exakte_tagesmengen():
    tab = perf.tagesdifferenzen(_zaehler(days=5, kwh_pro_h=12.0,
                                         m3_pro_h=0.6))
    #erster Tag hat nur 23 Intervalle, weil das erste keinen Vorgaenger hat
    voll = tab.iloc[1:]
    assert (voll["n_stunden"] == 24).all()
    assert np.allclose(voll["energie_kwh"], 24 * 12.0)
    assert np.allclose(voll["volumen_m3"], 24 * 0.6)
    assert tab.iloc[0]["n_stunden"] == 23


def test_ruecksprung_des_zaehlerstands_wird_nicht_als_verbrauch_gezaehlt():
    df = _zaehler(days=4)
    #Geraetetausch am dritten Tag: Zaehlerstand faellt auf null zurueck
    ab = df.index >= df.index[0] + pd.Timedelta(days=2)
    df.loc[ab, "energy"] = df.loc[ab, "energy"] - df.loc[ab, "energy"].iloc[0]
    df.loc[ab, "volume"] = df.loc[ab, "volume"] - df.loc[ab, "volume"].iloc[0]

    tab = perf.tagesdifferenzen(df).set_index("datum")
    tag = pd.Timestamp("2024-01-03")
    #genau ein Intervall ist der Ruecksprung, es faellt raus statt negativ
    assert tab.loc[tag, "n_verworfen"] == 1
    assert tab.loc[tag, "energie_kwh"] > 0
    assert (tab["energie_kwh"] >= 0).all()
    assert (tab["volumen_m3"] >= 0).all()


def test_messluecke_wird_nicht_ueberbrueckt():
    df = _zaehler(days=4)
    luecke = pd.Timestamp("2024-01-03 02:00")
    df = df.drop(index=pd.date_range(luecke, periods=6, freq="h"))

    tab = perf.tagesdifferenzen(df).set_index("datum")
    tag = pd.Timestamp("2024-01-03")
    #6 fehlende Stunden: 6 Intervalle fehlen, das Intervall ueber die
    #Luecke wird zusaetzlich verworfen statt 7 Stunden Verbrauch zu buchen
    assert tab.loc[tag, "n_stunden"] == 17
    assert np.isclose(tab.loc[tag, "energie_kwh"], 17 * 12.0)


def test_absurder_vorwaertssprung_wird_verworfen():
    df = _zaehler(days=3)
    ab = df.index >= pd.Timestamp("2024-01-02 12:00")
    df.loc[ab, "energy"] = df.loc[ab, "energy"] + 90000.0

    tab = perf.tagesdifferenzen(df).set_index("datum")
    assert tab.loc[pd.Timestamp("2024-01-02"), "n_verworfen"] == 1
    assert tab.loc[pd.Timestamp("2024-01-02"), "energie_kwh"] < 1000


def test_fehlende_pflichtspalte_bricht_verstaendlich_ab():
    df = _zaehler(days=2).drop(columns=["volume"])
    with pytest.raises(KeyError, match="volume"):
        perf.tagesdifferenzen(df)


def test_leere_reihe_liefert_leere_tabelle_ohne_fehler():
    leer = _zaehler(days=1).iloc[0:0]
    assert len(perf.tagesdifferenzen(leer)) == 0
    assert len(perf.tagesperformance(leer)) == 0


#--------------------------------------------------------------------------
#Kennzahl, Kelvin-Umrechnung, Flags
#--------------------------------------------------------------------------

def test_performance_ist_energie_durch_volumen():
    tab = perf.tagesperformance(_zaehler(days=5, kwh_pro_h=12.0,
                                         m3_pro_h=0.6))
    assert np.allclose(tab["performance"].dropna(), 20.0)


def test_kelvin_umrechnung_trifft_die_gemessene_spreizung():
    #Spreizung 25 K bei 1,163 kWh/(m3 K) -> 29,075 kWh/m3
    kwh = 25.0 * perf.KWH_PRO_M3_K
    df = _zaehler(days=4, kwh_pro_h=kwh, m3_pro_h=1.0, rt=45.0)
    df["dt"] = 25.0
    df["vl"] = df["rt"] + 25.0

    tab = perf.tagesperformance(df)
    gueltig = tab[tab["gueltig"]]
    assert np.allclose(gueltig["spreizung_k"], 25.0)
    assert np.allclose(gueltig["dt_gewichtet"], 25.0)
    assert gueltig["dt_abweichung_k"].abs().max() < 1e-9


def test_kleines_volumen_wird_geflaggt_und_nicht_geteilt():
    df = _zaehler(days=4, kwh_pro_h=0.05, m3_pro_h=0.001)
    tab = perf.tagesperformance(df, min_volume_m3=0.5)
    assert tab["volumen_zu_klein"].all()
    assert tab["performance"].isna().all()
    assert not tab["gueltig"].any()
    #Zeilen bleiben stehen, es wird nichts still entfernt
    assert len(tab) == 4


def test_plausibilitaetsband_flaggt_statt_zu_loeschen():
    df = _zaehler(days=3, kwh_pro_h=600.0, m3_pro_h=0.6)
    tab = perf.tagesperformance(df, band=(-2.0, 70.0))
    assert tab["ausserhalb_band"].all()
    assert tab["performance"].notna().all()
    assert not tab["gueltig"].any()


def test_filterbilanz_zaehlt_jede_bedingung_aus():
    tab = perf.tagesperformance(_zaehler(days=5))
    bilanz = perf.filterbilanz(tab).set_index("bedingung")
    assert bilanz.loc["Tagesreihen gesamt", "tage"] == 5
    #Tag 1 hat nur 23 Intervalle und faellt an der Mindeststundenzahl nicht
    #durch (23 >= 20), also sind alle fuenf Tage gueltig
    assert bilanz.loc["gueltig", "tage"] == 5


def test_abdeckung_gering_greift_bei_kurzem_tag():
    df = _zaehler(days=3)
    df = df.drop(index=pd.date_range("2024-01-02 00:00", periods=10, freq="h"))
    tab = perf.tagesperformance(df, min_stunden=20).set_index("datum")
    assert bool(tab.loc[pd.Timestamp("2024-01-02"), "abdeckung_gering"])
    assert not bool(tab.loc[pd.Timestamp("2024-01-02"), "gueltig"])


def test_performance_tabelle_stapelt_mehrere_zaehler():
    serien = {11: _zaehler(days=3), 22: _zaehler(days=3, kwh_pro_h=18.0)}
    tab = perf.performance_tabelle(serien)
    assert set(tab["meter"]) == {11, 22}
    assert len(tab) == 6
    assert tab.columns[0] == "meter"


#--------------------------------------------------------------------------
#Aussentemperatur
#--------------------------------------------------------------------------

def test_tagesmittel_ignoriert_zu_kurze_tage():
    ts = pd.date_range("2024-01-01", periods=36, freq="h")
    t_out = pd.DataFrame({"timestamp": ts,
                          "t_out": np.linspace(0.0, 10.0, len(ts))})
    tages = perf.tagesmittel_temperatur(t_out, min_stunden=20).set_index("datum")
    assert pd.notna(tages.loc[pd.Timestamp("2024-01-01"), "t_out_tag"])
    #zweiter Tag hat nur 12 Stunden
    assert pd.isna(tages.loc[pd.Timestamp("2024-01-02"), "t_out_tag"])


def test_join_der_aussentemperatur_haelt_die_zeilenzahl():
    tab = perf.tagesperformance(_zaehler(days=3))
    tab.insert(0, "meter", 1)
    ts = pd.date_range("2024-01-01", periods=72, freq="h")
    t_out = pd.DataFrame({"timestamp": ts, "t_out": np.full(len(ts), 5.0)})
    mit = perf.mit_aussentemperatur(tab, t_out)
    assert len(mit) == len(tab)
    assert np.allclose(mit["t_out_tag"], 5.0)


#--------------------------------------------------------------------------
#Gruppenzuordnung
#--------------------------------------------------------------------------

def test_fester_stichtag_trennt_an_einem_datum():
    tab = pd.DataFrame({"meter": [1, 1, 2],
                        "datum": pd.to_datetime(["2024-09-29", "2024-10-05",
                                                 "2024-09-30"])})
    g = perf.gruppe_fester_stichtag(tab, "2024-09-30")
    assert list(g["gruppe"]) == [perf.GRUPPE_VOR, perf.GRUPPE_NACH,
                                 perf.GRUPPE_VOR]


def test_stationseigener_stichtag_schliesst_begehungstag_aus():
    tab = pd.DataFrame({
        "meter": [1, 1, 1, 2],
        "datum": pd.to_datetime(["2024-03-01", "2024-03-10", "2024-03-20",
                                 "2024-03-10"]),
    })
    g = perf.gruppe_je_station(tab, {1: "2024-03-10"})
    assert g.loc[0, "gruppe"] == perf.GRUPPE_VOR
    #Begehungstag selbst gehoert in keine Gruppe
    assert pd.isna(g.loc[1, "gruppe"])
    assert g.loc[2, "gruppe"] == perf.GRUPPE_NACH
    #Station ohne Begehungsdatum bleibt in der Tabelle, aber ohne Gruppe
    assert pd.isna(g.loc[3, "gruppe"])
    assert len(g) == 4


def test_puffer_blendet_einregelphase_aus():
    tab = pd.DataFrame({"meter": [1] * 5,
                        "datum": pd.to_datetime(
                            ["2024-03-04", "2024-03-08", "2024-03-10",
                             "2024-03-12", "2024-03-16"])})
    g = perf.gruppe_je_station(tab, {1: "2024-03-10"}, puffer_tage=3)
    assert g.loc[0, "gruppe"] == perf.GRUPPE_VOR
    assert g.loc[4, "gruppe"] == perf.GRUPPE_NACH
    #die drei Tage im Puffer bleiben ohne Gruppe
    assert g.loc[1:3, "gruppe"].isna().all()


#--------------------------------------------------------------------------
#Regression
#--------------------------------------------------------------------------

def _gerade(steigung: float, abschnitt: float, gruppe: str,
            n: int = 60, rauschen: float = 0.0, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    x = np.linspace(-10.0, 25.0, n)
    y = abschnitt + steigung * x + rng.normal(0.0, rauschen, n)
    return pd.DataFrame({
        "meter": np.arange(n) % 5,
        "datum": pd.date_range("2024-01-01", periods=n, freq="D"),
        "t_out_tag": x,
        "performance": y,
        "volumen_m3": np.full(n, 2.0),
        "gruppe": gruppe,
    })


def test_regression_findet_die_vorgegebene_gerade_exakt():
    r = perf.regression(_gerade(-0.5, 20.0, perf.GRUPPE_VOR))
    assert r["steigung"] == pytest.approx(-0.5, abs=1e-9)
    assert r["achsenabschnitt"] == pytest.approx(20.0, abs=1e-9)
    assert r["r2"] == pytest.approx(1.0, abs=1e-9)
    assert r["n"] == 60


def test_regression_meldet_verworfene_zeilen_statt_sie_zu_verschweigen():
    tab = _gerade(-0.5, 20.0, perf.GRUPPE_VOR, n=20)
    tab.loc[0:4, "t_out_tag"] = np.nan
    r = perf.regression(tab)
    assert r["n"] == 15
    assert r["n_verworfen"] == 5


def test_konfidenzintervall_der_steigung_umschliesst_den_wahren_wert():
    tab = _gerade(-0.5, 20.0, perf.GRUPPE_VOR, n=300, rauschen=2.0, seed=7)
    r = perf.regression(tab)
    lo, hi = r["steigung_ci"]
    assert lo < -0.5 < hi
    assert r["steigung_p"] < 0.01


def test_interaktionsmodell_erkennt_steigungsunterschied():
    tab = pd.concat([
        _gerade(-0.588, 21.1, perf.GRUPPE_VOR, n=200, rauschen=1.0, seed=1),
        _gerade(-0.423, 21.77, perf.GRUPPE_NACH, n=200, rauschen=1.0, seed=2),
    ], ignore_index=True)
    m = perf.interaktionsmodell(tab)
    assert m["steigungsdifferenz"] == pytest.approx(0.165, abs=0.03)
    assert m["steigungsdifferenz_p"] < 0.001
    lo, hi = m["steigungsdifferenz_ci"]
    assert lo < 0.165 < hi


def test_interaktionsmodell_findet_keinen_unterschied_wo_keiner_ist():
    tab = pd.concat([
        _gerade(-0.5, 20.0, perf.GRUPPE_VOR, n=200, rauschen=2.0, seed=3),
        _gerade(-0.5, 20.0, perf.GRUPPE_NACH, n=200, rauschen=2.0, seed=4),
    ], ignore_index=True)
    m = perf.interaktionsmodell(tab)
    assert m["steigungsdifferenz_p"] > 0.05


def _stationsversatz(n_stationen: int = 8, n_tage: int = 120,
                     seed: int = 11) -> pd.DataFrame:
    """Jede Station hat ein eigenes Niveau - Tage sind damit korreliert."""
    rng = np.random.default_rng(seed)
    teile = []
    for s in range(n_stationen):
        x = rng.uniform(-10.0, 25.0, n_tage)
        versatz = rng.normal(0.0, 4.0)
        teile.append(pd.DataFrame({
            "meter": s,
            "t_out_tag": x,
            "performance": 20.0 - 0.5 * x + versatz
                           + rng.normal(0.0, 0.5, n_tage),
            "volumen_m3": 2.0,
            "gruppe": perf.GRUPPE_VOR if s % 2 == 0 else perf.GRUPPE_NACH,
        }))
    return pd.concat(teile, ignore_index=True)


def test_clusterrobuste_fehler_sind_weiter_als_die_lehrbuchformel():
    tab = _stationsversatz()
    naiv = perf.regression(tab)
    robust = perf.regression(tab, cluster="meter")
    #die Punktschaetzung darf sich nicht aendern
    assert robust["steigung"] == pytest.approx(naiv["steigung"], abs=1e-12)
    assert robust["achsenabschnitt"] == pytest.approx(
        naiv["achsenabschnitt"], abs=1e-12)
    assert robust["n"] == naiv["n"]
    assert robust["n_cluster"] == 8
    #Stationsversatz trifft vor allem den Achsenabschnitt
    assert robust["fit"]["se"][0] > 3 * naiv["fit"]["se"][0]
    assert robust["fit"]["dof"] == 7


def test_interaktionsmodell_nimmt_cluster_entgegen():
    tab = _stationsversatz()
    m = perf.interaktionsmodell(tab, cluster="meter")
    assert m["n_cluster"] == 8
    #kein echter Steigungsunterschied im konstruierten Beispiel
    assert m["steigungsdifferenz_p"] > 0.05


def test_ols_lehnt_zu_wenige_cluster_ab():
    tab = _stationsversatz(n_stationen=2, n_tage=50)
    with pytest.raises(ValueError, match="zu wenige Cluster"):
        perf.regression(tab, cluster="meter")


def test_interaktionsmodell_braucht_genau_zwei_gruppen():
    tab = _gerade(-0.5, 20.0, perf.GRUPPE_VOR, n=30)
    with pytest.raises(ValueError, match="zwei Gruppen"):
        perf.interaktionsmodell(tab)


#--------------------------------------------------------------------------
#Delta am Bezugspunkt, gegen die Zahlen der Folie gerechnet
#--------------------------------------------------------------------------

def test_delta_reproduziert_die_zahlen_der_uez_folie():
    #Franks Geraden, Bezugspunkt 8,8 Grad C: Differenz 2,12 kWh/m3 bei
    #15,9 kWh/m3 unoptimiert, also 13,3 Prozent
    d = perf.delta_am_bezugspunkt(steigung_vor=-0.588, achsenabschnitt_vor=21.1,
                                  steigung_nach=-0.423, achsenabschnitt_nach=21.77,
                                  t_ref=8.8)
    assert d["y_vor"] == pytest.approx(15.926, abs=0.01)
    assert d["delta_kwh_m3"] == pytest.approx(2.122, abs=0.01)
    assert d["delta_prozent"] == pytest.approx(13.3, abs=0.2)
    assert d["delta_k"] == pytest.approx(2.122 / 1.163, abs=0.01)


def test_delta_ist_null_wenn_die_geraden_identisch_sind():
    d = perf.delta_am_bezugspunkt(-0.5, 20.0, -0.5, 20.0, t_ref=9.0)
    assert d["delta_kwh_m3"] == pytest.approx(0.0, abs=1e-12)
    assert d["delta_prozent"] == pytest.approx(0.0, abs=1e-12)


def test_delta_aus_interaktion_deckt_sich_mit_den_getrennten_fits():
    tab = pd.concat([
        _gerade(-0.588, 21.1, perf.GRUPPE_VOR, n=200, rauschen=1.0, seed=11),
        _gerade(-0.423, 21.77, perf.GRUPPE_NACH, n=200, rauschen=1.0, seed=12),
    ], ignore_index=True)
    fits = perf.regression_je_gruppe(tab).set_index("gruppe")
    t_ref = float(tab["t_out_tag"].mean())
    getrennt = perf.delta_am_bezugspunkt(
        fits.loc[perf.GRUPPE_VOR, "steigung"],
        fits.loc[perf.GRUPPE_VOR, "achsenabschnitt"],
        fits.loc[perf.GRUPPE_NACH, "steigung"],
        fits.loc[perf.GRUPPE_NACH, "achsenabschnitt"],
        t_ref)
    gemeinsam = perf.delta_aus_interaktion(perf.interaktionsmodell(tab), t_ref)
    assert gemeinsam["delta_kwh_m3"] == pytest.approx(
        getrennt["delta_kwh_m3"], abs=1e-9)
    lo, hi = gemeinsam["delta_ci"]
    assert lo < getrennt["delta_kwh_m3"] < hi


#--------------------------------------------------------------------------
#Ueberdeckung der Temperaturbereiche
#--------------------------------------------------------------------------

def test_ueberdeckung_zeigt_verschobene_temperaturbereiche():
    warm = _gerade(-0.5, 20.0, perf.GRUPPE_VOR, n=50)
    kalt = _gerade(-0.5, 20.0, perf.GRUPPE_NACH, n=50)
    kalt["t_out_tag"] = kalt["t_out_tag"] - 20.0
    ueb = perf.temperaturueberdeckung(pd.concat([warm, kalt]),
                                      t_ref=8.0).set_index("gruppe")
    assert ueb.loc[perf.GRUPPE_VOR, "mittel"] > ueb.loc[perf.GRUPPE_NACH, "mittel"]
    assert bool(ueb.loc[perf.GRUPPE_VOR, "t_ref_im_bereich"])
    assert not bool(ueb.loc[perf.GRUPPE_NACH, "t_ref_im_bereich"])
    assert ueb.loc[perf.GRUPPE_NACH, "n_nahe_t_ref"] == 0


#--------------------------------------------------------------------------
#Grafik
#--------------------------------------------------------------------------

def test_blasen_aggregat_gewichtet_mit_dem_volumen():
    #zwei Tage derselben Station in derselben Temperaturklasse:
    #10 kWh/1 m3 und 30 kWh/3 m3 ergeben zusammen 40/4 = 10 kWh/m3
    tab = pd.DataFrame({
        "meter": [7, 7],
        "t_out_tag": [8.2, 9.4],
        "performance": [10.0, 10.0],
        "volumen_m3": [1.0, 3.0],
        "gruppe": perf.GRUPPE_VOR,
    })
    agg = perf.blasen_aggregat(tab, klassenbreite=2.0)
    assert len(agg) == 1
    zeile = agg.iloc[0]
    assert zeile["t_out_tag"] == pytest.approx(9.0)
    assert zeile["performance"] == pytest.approx(10.0)
    assert zeile["volumen_m3"] == pytest.approx(4.0)
    assert zeile["tage"] == 2


def test_blasen_aggregat_mittelt_volumengewichtet_nicht_arithmetisch():
    tab = pd.DataFrame({
        "meter": [7, 7],
        "t_out_tag": [8.2, 9.4],
        "performance": [5.0, 25.0],
        "volumen_m3": [3.0, 1.0],
        "gruppe": perf.GRUPPE_VOR,
    })
    agg = perf.blasen_aggregat(tab, klassenbreite=2.0)
    #arithmetisch waeren es 15, volumengewichtet (15+25)/4 = 10
    assert agg.iloc[0]["performance"] == pytest.approx(10.0)


def test_blasen_aggregat_trennt_stationen_gruppen_und_klassen():
    tab = pd.DataFrame({
        "meter": [1, 1, 2, 1],
        "t_out_tag": [1.0, 5.0, 1.0, 1.0],
        "performance": [20.0, 18.0, 20.0, 20.0],
        "volumen_m3": [2.0, 2.0, 2.0, 2.0],
        "gruppe": [perf.GRUPPE_VOR, perf.GRUPPE_VOR, perf.GRUPPE_VOR,
                   perf.GRUPPE_NACH],
    })
    agg = perf.blasen_aggregat(tab, klassenbreite=2.0)
    assert len(agg) == 4
    assert agg["volumen_m3"].sum() == pytest.approx(8.0)


def test_blasendiagramm_zeichnet_beide_gruppen_ohne_anzeige():
    import matplotlib
    matplotlib.use("Agg")

    tab = pd.concat([
        _gerade(-0.588, 21.1, perf.GRUPPE_VOR, n=40, rauschen=1.0, seed=5),
        _gerade(-0.423, 21.77, perf.GRUPPE_NACH, n=40, rauschen=1.0, seed=6),
    ], ignore_index=True)
    fits = perf.regression_je_gruppe(tab)
    d = perf.delta_am_bezugspunkt(
        fits.loc[0, "steigung"], fits.loc[0, "achsenabschnitt"],
        fits.loc[1, "steigung"], fits.loc[1, "achsenabschnitt"], t_ref=8.0)
    ax = perf.blasendiagramm(tab, fits, t_ref=8.0, delta=d)
    assert len(ax.collections) == 2
    assert len(ax.lines) >= 2
    assert "kWh/m³" in ax.get_ylabel()
